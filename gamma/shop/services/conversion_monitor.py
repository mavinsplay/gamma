"""Read completed Platega conversions; never initiate a payout/conversion."""

import asyncio
from datetime import datetime, timedelta
from html import escape
import json
import logging
from pathlib import Path
import re
from urllib.parse import urljoin

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from shop.models import AdminNotification, BillingSetting
from shop.services.platega_ui import (
    _goto_ready,
    _login,
    _on_login_page,
    ACTION_TIMEOUT_MS,
    UiPayoutError,
)

__all__ = ["check_conversions", "read_ui_conversions"]

logger = logging.getLogger(__name__)
STATE_KEY = "platega_conversion_monitor"
CHECK_INTERVAL = timedelta(hours=12)
UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b",
    re.I,
)


def _completed_conversions(headers, rows):
    """Fail closed if the site's table no longer has recognizable columns."""
    normalized = [header.strip().lower() for header in headers]
    status_index = next(
        (
            i
            for i, header in enumerate(normalized)
            if "статус" in header or "status" in header
        ),
        None,
    )
    if status_index is None:
        raise UiPayoutError("Conversion table has no status column")

    id_index = next(
        (
            i
            for i, header in enumerate(normalized)
            if header == "id"
            or header.startswith("id ")
            or "идентификатор" in header
        ),
        None,
    )
    completed = []
    for row in rows:
        if len(row) != len(headers):
            raise UiPayoutError("Unexpected conversion table row")

        status = row[status_index].strip().lower().replace("ё", "е")
        if status not in {
            "подтвержден",
            "подтверждена",
            "успешно",
            "успешная",
            "успешен",
            "завершена",
            "завершен",
            "выполнена",
            "выполнено",
            "confirmed",
            "completed",
            "success",
            "successful",
        }:
            if status in {
                "в обработке",
                "ожидание",
                "ожидает",
                "отменена",
                "отменен",
                "ошибка",
                "неуспешно",
                "неуспешная",
                "pending",
                "processing",
                "canceled",
                "cancelled",
                "failed",
            }:
                continue

            raise UiPayoutError("Unknown conversion status")

        identifier = row[id_index].strip() if id_index is not None else ""
        if not identifier:
            match = UUID_PATTERN.search(" ".join(row))
            identifier = match.group(0).lower() if match else ""

        if not identifier or len(identifier) > 100:
            raise UiPayoutError("Conversion has no stable identifier")

        details = ""
        for header, value in zip(headers, row):
            if not header.strip():
                continue

            line = f"{escape(header[:100])}: {escape(value[:250])}\n"
            if len(details) + len(line) <= 3000:
                details += line

        completed.append({"id": identifier, "details": details.rstrip()})

    return completed


async def read_ui_conversions():
    from playwright.async_api import async_playwright

    profile = Path(settings.PLATEGA_UI_PROFILE_DIR)
    shots = profile / "conversion-screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    state_file = profile / "storage_state.json"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        try:
            context = await browser.new_context(
                storage_state=str(state_file) if state_file.exists() else None,
            )
            context.set_default_timeout(ACTION_TIMEOUT_MS)
            page = await context.new_page()
            entry_url = (
                settings.PLATEGA_UI_CONVERSIONS_URL
                or settings.PLATEGA_UI_PAYOUT_URL
            )
            await _goto_ready(page, entry_url)
            if await _on_login_page(page):
                await _login(
                    page,
                    shots,
                    settings.PLATEGA_UI_LOGIN_URL,
                    settings.PLATEGA_UI_LOGIN.strip(),
                    settings.PLATEGA_UI_PASSWORD.strip(),
                )
                await _goto_ready(page, entry_url)
                if await _on_login_page(page):
                    raise UiPayoutError("Conversion monitor login failed")

            await context.storage_state(path=str(state_file))
            if not settings.PLATEGA_UI_CONVERSIONS_URL:
                link = page.locator('a[href$="/conversions"]').first
                await link.wait_for(state="attached")
                url = urljoin(page.url, await link.get_attribute("href"))
                await _goto_ready(page, url)

            await page.locator("table").wait_for(state="visible")
            completed = []
            previous_rows = None
            for _ in range(100):
                headers = await page.locator(
                    "table thead th",
                ).all_inner_texts()
                rows = await page.locator("table tbody tr").evaluate_all(
                    "rows => rows.map(row => Array.from("
                    "row.querySelectorAll('td'),"
                    " cell => cell.innerText.trim()))",
                )
                if rows == previous_rows:
                    raise UiPayoutError(
                        "Conversion pagination did not advance",
                    )
                # Empty tables often contain one full-width placeholder cell.
                if (
                    len(rows) == 1
                    and len(rows[0]) == 1
                    and rows[0][0].strip().lower()
                    in {
                        "нет данных",
                        "нет записей",
                        "ничего не найдено",
                        "no data",
                        "no results",
                    }
                ):
                    rows = []

                completed.extend(_completed_conversions(headers, rows))
                next_page = page.locator(
                    'button[aria-label="Следующая страница"], '
                    'button[aria-label="Next page"], '
                    'button[title="Следующая страница"], '
                    'button:has-text("Следующая"), '
                    "button:has(svg.lucide-chevron-right)",
                )
                if await next_page.count() == 0:
                    break

                next_page = next_page.first
                if (
                    not await next_page.is_visible()
                    or not await next_page.is_enabled()
                ):
                    break

                previous_rows = rows
                await next_page.click()
                await page.wait_for_function(
                    "old => JSON.stringify(Array.from("
                    "document.querySelectorAll("
                    "'table tbody tr'), row => Array.from("
                    "row.querySelectorAll("
                    "'td'), cell => cell.innerText.trim())))"
                    " !== JSON.stringify(old)",
                    arg=rows,
                )
            else:
                raise UiPayoutError("Too many conversion pages")

            return completed
        finally:
            await browser.close()


def _load_state():
    value = (
        BillingSetting.objects.filter(key=STATE_KEY)
        .values_list(
            "value",
            flat=True,
        )
        .first()
    )
    return json.loads(value) if value else {}


@transaction.atomic
def _record_conversions(conversions, checked_at):
    row, _ = BillingSetting.objects.get_or_create(key=STATE_KEY)
    row = BillingSetting.objects.select_for_update().get(pk=row.pk)
    state = json.loads(row.value) if row.value else {}
    seen = set(state.get("seen", []))
    for conversion in conversions:
        if state.get("initialized") and conversion["id"] not in seen:
            AdminNotification.objects.get_or_create(
                event_key=f"conversion:{conversion['id']}",
                defaults={
                    "text": "💵 Platega: конвертация завершена\n"
                    + conversion["details"],
                },
            )

        seen.add(conversion["id"])

    row.value = json.dumps(
        {
            "initialized": True,
            "seen": sorted(seen),
            "next_check": (checked_at + CHECK_INTERVAL).isoformat(),
        },
    )
    row.save(update_fields=["value", "updated_at"])


@transaction.atomic
def _record_failure(checked_at):
    row, _ = BillingSetting.objects.get_or_create(key=STATE_KEY)
    row = BillingSetting.objects.select_for_update().get(pk=row.pk)
    state = json.loads(row.value) if row.value else {}
    # Keep the last successful baseline; retry after an hour, survive restart.
    state["next_check"] = (checked_at + timedelta(hours=1)).isoformat()
    row.value = json.dumps(state)
    row.save(update_fields=["value", "updated_at"])
    AdminNotification.objects.get_or_create(
        event_key=f"conversion-monitor-error:{checked_at.date()}",
        defaults={
            "text": "⚠️ Не удалось проверить конвертации Platega. "
            "Повтор через час. Проверьте доступ к кабинету и журнал бота.",
        },
    )


async def check_conversions():
    if not (
        settings.ADMIN_TELEGRAM_ID
        and settings.PLATEGA_UI_LOGIN
        and settings.PLATEGA_UI_PASSWORD
        and (
            settings.PLATEGA_UI_CONVERSIONS_URL
            or settings.PLATEGA_UI_PAYOUT_URL
        )
    ):
        return

    state = await sync_to_async(_load_state)()
    checked_at = timezone.now()
    if state.get(
        "next_check",
    ) and checked_at < datetime.fromisoformat(
        state["next_check"],
    ):
        return

    try:
        conversions = await asyncio.wait_for(
            read_ui_conversions(),
            timeout=180,
        )
        await sync_to_async(_record_conversions)(conversions, checked_at)
    except Exception as error:
        detail = (
            str(error)
            if isinstance(error, UiPayoutError)
            else type(error).__name__
        )
        logger.warning("Conversion check failed: %s", detail)
        await sync_to_async(_record_failure)(checked_at)
