"""Вывод средств через браузер (Payout API не одобрен).

Playwright открывает кабинет my.platega.io и проходит флоу как человек:
раздел выводов -> «Вывести средства» -> вкладка «Карта» -> сохранённая
карта -> сумма в рублях -> «Подтвердить».

Сессия переиспользуется (storage_state в профиле), при протухании —
авто-реlogin по кредсам из .env. Каждый шаг пишет скриншот в профиль.

Карта-назначение — сохранённая на сайте (ищем по ****1234), полный PAN
нигде не нужен и не хранится.

Playwright импортируется лениво внутри run-функций, чтобы модуль
импортировался и без установленного браузера (тесты, IDE).
"""

import asyncio
import logging
import math
from pathlib import Path
import re

from django.conf import settings

logger = logging.getLogger(__name__)

__all__ = [
    "SELECTORS",
    "UiPayoutError",
    "compute_withdraw_all",
    "configured_last4",
    "mask_pan",
    "run_ui_card_payout",
    "should_autopayout",
    "ui_payout_configured",
]


SELECTORS = {
    # Форма логина (/auth/login). Поле логина — обычный type="text"
    # с плейсхолдером, поэтому ищем и по нему тоже.
    "login_user": 'input[type="email"], input[name="email"], '
    'input[name="login"], input[placeholder*="Логин"], '
    'input[placeholder*="Login"], input[placeholder*="mail"]',
    "login_pass": 'input[type="password"], input[name="password"], '
    'input[placeholder*="Пароль"]',
    "login_submit": 'button[type="submit"], button:has-text("Войти")',
    "login_markers": '.login-form, form[action*="login"], '
    ':text("Вход в личный кабинет")',
    # Раздел «Вывод средств». XPath с точным текстом: на странице есть
    # одноимённые пункты мобильного меню, has-text давал бы дубли.
    "withdraw_open": '//button[.//p[normalize-space()="Вывести средства"]]',
    # Модалка «Создать вывод»
    "modal": ':text("Создать вывод")',
    "card_tab": '//button[normalize-space()="Карта"]',
    "card_opener": 'button:has-text("Выберите карту")',
    "amount_input": 'input[placeholder*="Например"], input[name="amount"]',
    "confirm": '//button[normalize-space()="Подтвердить"]',
    # Признак успеха после отправки.
    "success_markers": ':text("успешно"), :text("success"), '
    ':text("создан"), :text("created"), :text("в обработке")',
    # Признак ошибки заявки на странице.
    "error_markers": '.error, .alert-danger, [role="alert"]',
}

ACTION_TIMEOUT_MS = 15000
CONFIRM_RETRIES = 6


class UiPayoutError(Exception):
    """Ошибка браузерного вывода. Секреты сюда не попадают."""

    def __init__(self, message, screenshot=None):
        super().__init__(message)
        self.screenshot = screenshot


def mask_pan(pan):
    """Только последние 4 цифры — для логов, БД и Telegram."""
    digits = "".join(ch for ch in str(pan or "") if ch.isdigit())
    if len(digits) < 4:
        return "****"

    return f"**** {digits[-4:]}"


def configured_last4():
    """Настроенные последние 4 цифры карты или ''."""
    digits = "".join(
        ch
        for ch in str(getattr(settings, "PLATEGA_PAYOUT_CARD_LAST4", ""))
        if ch.isdigit()
    )
    return digits[-4:] if len(digits) >= 4 else ""


def compute_withdraw_all(
    rub_balance,
    fee_usd=0.5,
    usd_rub_rate=80,
    payout_min=1000,
    payout_max=87500,
):
    """Сумма «вывести всё», ₽: баланс минус комиссия, в лимитах.

    Возвращает 0, если вывести нечего (меньше минимума).
    """
    try:
        balance = float(rub_balance or 0)
        fee_rub = float(fee_usd or 0) * float(usd_rub_rate or 0)
    except (TypeError, ValueError):
        return 0

    amount = math.floor(min(balance, payout_max)) - math.ceil(fee_rub)
    if amount < payout_min:
        return 0

    return int(amount)


def should_autopayout(balance, threshold, payout_min=1000):
    """Пора ли выводить автоматически: баланс не ниже порога и минимума."""
    try:
        return float(balance or 0) >= max(
            float(threshold or 0),
            float(payout_min or 0),
        )
    except (TypeError, ValueError):
        return False


def ui_payout_configured():
    """Всё ли задано для UI-вывода: доступ, URL, карта-назначение."""
    ready = (
        getattr(settings, "PLATEGA_UI_LOGIN", "")
        and getattr(settings, "PLATEGA_UI_PASSWORD", "")
        and getattr(settings, "PLATEGA_UI_LOGIN_URL", "")
        and getattr(settings, "PLATEGA_UI_PAYOUT_URL", "")
        and configured_last4()
    )
    return bool(ready)


async def _shot(page, shots_dir, name):
    """Скриншот шага. Не падает, если страница уже закрыта."""
    try:
        path = shots_dir / f"{name}.png"
        await page.screenshot(path=str(path))
        return str(path)
    except Exception as e:
        logger.warning("[platega-ui] screenshot %s failed: %s", name, e)
        return ""


async def _goto_ready(page, url):
    """Переход + ожидание прорисовки SPA (networkidle с капой)."""
    await page.goto(url, wait_until="domcontentloaded")
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


async def _fail(page, shots_dir, message):
    shot = await _shot(page, shots_dir, "error")
    try:
        html_path = shots_dir / "error.html"
        html_path.write_text(await page.content(), encoding="utf-8")
    except Exception as e:
        logger.warning("[platega-ui] html dump failed: %s", e)

    raise UiPayoutError(message, screenshot=shot)


async def _on_login_page(page):
    # "/login" покрывает и /login, и /auth/login.
    if "/login" in page.url:
        return True

    marker = await page.query_selector(SELECTORS["login_markers"])
    user_field = await page.query_selector(SELECTORS["login_user"])
    return marker is not None or user_field is not None


async def _fill_verified(page, selector, value, name):
    """Ввод как человек: клик, посимвольный набор, сверка значения.

    React-формы иногда игнорируют программное заполнение — сверяем
    прочитанное значение с ожидаемым, иначе fallback через нативный
    сеттер + события. Возвращает True/False, секреты не логирует.
    """
    locator = page.locator(selector).first
    await locator.click()
    await locator.fill("")
    await locator.press_sequentially(value, delay=25)
    if await locator.input_value() == value:
        return True

    logger.warning("[platega-ui] typed %s mismatch, js fallback", name)
    await page.evaluate(
        """([sel, val]) => {
            const el = document.querySelector(sel);
            if (!el) return;
            const proto = el instanceof HTMLTextAreaElement
                ? HTMLTextAreaElement.prototype
                : HTMLInputElement.prototype;
            const desc = Object.getOwnPropertyDescriptor(proto, 'value');
            if (desc && desc.set) {
                desc.set.call(el, val);
            } else {
                el.value = val;
            }
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        [selector, value],
    )
    return await locator.input_value() == value


async def _visible_error_text(page):
    """Текст видимой ошибки/тоста на странице (для диагностики)."""
    for selector in (
        '[role="alert"]',
        ".error",
        ".toast",
        '[class*="toast"]',
        '[class*="notification"]',
    ):
        try:
            el = await page.query_selector(selector)
            if el is not None and await el.is_visible():
                text = (await el.inner_text() or "").strip()
                if text:
                    return text[:200]
        except Exception:
            pass

    return ""


async def _login(page, shots, login_url, login, password):
    # Важно: Django по умолчанию показывает только WARNING+, поэтому
    # вся диагностика входа — warning, иначе её не видно в консоли.
    logger.warning("[platega-ui] logging in, url=%s", page.url)
    await _goto_ready(page, login_url)
    if not await _fill_verified(
        page,
        SELECTORS["login_user"],
        login,
        "login",
    ):
        await _fail(page, shots, "login field not fillable")

    # Пароль в логи не пишем никогда.
    if not await _fill_verified(
        page,
        SELECTORS["login_pass"],
        password,
        "password",
    ):
        await _fail(page, shots, "password field not fillable")

    await _shot(page, shots, "login-filled")

    # Перехват ВСЕХ ответов сети: видно, уходит ли запрос вообще.
    # Тел не логируем (там могут быть токены), только статусы;
    # текст ошибки читаем отдельно и только при неуспехе.
    api_calls = []

    def _on_response(response):
        try:
            api_calls.append(response)
        except Exception:
            pass

    page.on("response", _on_response)
    submit = page.locator(SELECTORS["login_submit"]).first
    try:
        logger.warning(
            "[platega-ui] submit visible=%s enabled=%s",
            await submit.is_visible(),
            await submit.is_enabled(),
        )
    except Exception as e:
        logger.warning("[platega-ui] submit state unknown: %s", e)

    async def _wait_gone():
        # Успешный вход уводит со страницы логина (редирект на дашборд).
        await page.wait_for_url(
            lambda url: "/login" not in str(url),
            timeout=15000,
        )

    await page.click(SELECTORS["login_submit"])
    try:
        await _wait_gone()
    except Exception:
        # Fallback: Enter в поле пароля шлёт форму нативно.
        logger.warning("[platega-ui] click did not navigate, trying Enter")
        await page.click(SELECTORS["login_pass"])
        await page.keyboard.press("Enter")
        try:
            await _wait_gone()
        except Exception:
            await page.wait_for_load_state("networkidle")

    logger.warning("[platega-ui] after submit url=%s", page.url)
    for response in api_calls:
        try:
            status = response.status
            url = str(response.url or "").split("?")[0][-100:]
        except Exception:
            continue

        detail = ""
        if status >= 400:
            try:
                payload = await response.json()
                if isinstance(payload, dict):
                    for key in ("message", "error", "detail", "msg"):
                        if payload.get(key):
                            detail = f": {str(payload[key])[:150]}"
                            break
            except Exception:
                pass

        logger.warning("[platega-ui] net %s %s%s", status, url, detail)


def _last4_selector(last4):
    return f'text="**** {last4}"'


async def _select_saved_card(page, shots, last4):
    """Выбор сохранённой карты в модалке «Создать вывод».

    Закрытый список показывает либо саму карту (**** 3710 — уже
    выбрана), либо «Выберите карту» — тогда открываем и кликаем опцию.
    В истории выводов маски буллетами (••••), в модалке — звёздочками,
    поэтому совпадений с историей нет.
    """
    selector = _last4_selector(last4)
    for el in await page.query_selector_all(selector):
        try:
            if await el.is_visible():
                logger.info("[platega-ui] card **** %s already visible", last4)
                await _shot(page, shots, "card-selected")
                return
        except Exception:
            pass

    opener = page.locator(SELECTORS["card_opener"])
    try:
        has_opener = await opener.count() > 0
    except Exception:
        has_opener = False

    if not has_opener:
        await _fail(page, shots, "card dropdown not found")

    await opener.first.click()
    try:
        await page.wait_for_selector(selector, state="visible", timeout=10000)
    except Exception:
        await _fail(page, shots, f"saved card **** {last4} not found in list")

    for el in await page.query_selector_all(selector):
        try:
            if await el.is_visible():
                await el.click()
                break
        except Exception:
            pass

    await page.wait_for_timeout(500)
    await _shot(page, shots, "card-selected")


async def _fill_amount_until_confirmed(page, shots, amount, payout_min):
    """Ввод суммы; кнопка disabled при превышении доступного —
    уменьшаем на 5% до победного. Возвращает итоговую сумму."""
    actual = amount
    for attempt in range(CONFIRM_RETRIES):
        await page.fill(SELECTORS["amount_input"], str(actual))
        await page.wait_for_timeout(800)
        confirm = await page.query_selector(SELECTORS["confirm"])
        if confirm is not None and await confirm.is_enabled():
            await _shot(page, shots, "filled")
            return actual

        logger.warning("[platega-ui] confirm disabled for %s, retry", actual)
        await _shot(page, shots, f"filled-retry-{attempt}")
        actual = math.floor(actual * 0.95)
        if actual < payout_min:
            break

    await _fail(
        page,
        shots,
        "confirm button stays disabled (check balance/limits)",
    )
    raise AssertionError("unreachable")


def _parse_usdt_amount(text):
    """Первое число перед USDT в тексте («Доступно к выводу 3.31 USDT»).

    Возвращает float или None.
    """
    match = re.search(r"([\d\s.,]+)\s*USDT", str(text or ""))
    if not match:
        return None

    try:
        value = float(match.group(1).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None

    return value if value > 0 else None


async def _read_available_usdt(page, shots):
    """Сколько доступно к выводу по данным самого сайта (USDT)."""
    try:
        label = await page.query_selector(':text("Доступно к выводу")')
        if label is None:
            return None

        box = await label.evaluate_handle(
            "e => (e.parentElement && e.parentElement.parentElement) || e",
        )
        text = await box.inner_text()
        amount = _parse_usdt_amount(text)
        logger.info("[platega-ui] site available: %s USDT", amount)
        await _shot(page, shots, "available")
        return amount
    except Exception as e:
        logger.warning("[platega-ui] available read failed: %s", e)
        return None


async def run_ui_card_payout(
    amount_rub,
    login=None,
    password=None,
    card_last4=None,
    login_url=None,
    payout_url=None,
    profile_dir=None,
    timeout_s=180,
    dry_run=False,
    is_max=False,
):
    """Вывод через сайт. Возвращает dict, бросает UiPayoutError.

    dry_run=True — проходит все шаги со скриншотами, но НЕ нажимает
    «Подтвердить» (проверка селекторов).
    is_max=True — стартовую сумму считаем из «Доступно к выводу»
    на сайте (его баланс, курс и комиссия), amount лишь запасной план.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise UiPayoutError("playwright not installed")

    # strip: хвостовой пробел в строке .env — частая причина фейлов.
    login = (login or getattr(settings, "PLATEGA_UI_LOGIN", "")).strip()
    password = (
        password or getattr(settings, "PLATEGA_UI_PASSWORD", "")
    ).strip()
    last4 = "".join(
        ch for ch in str(card_last4 or configured_last4()) if ch.isdigit()
    )[-4:]
    login_url = (
        login_url or getattr(settings, "PLATEGA_UI_LOGIN_URL", "")
    ).strip()
    payout_url = (
        payout_url or getattr(settings, "PLATEGA_UI_PAYOUT_URL", "")
    ).strip()
    if not profile_dir:
        profile_dir = getattr(
            settings,
            "PLATEGA_UI_PROFILE_DIR",
            "./platega_profile",
        )

    profile = Path(profile_dir)
    payout_min = int(getattr(settings, "PLATEGA_PAYOUT_MIN", 1000))
    try:
        amount = int(amount_rub)
    except (TypeError, ValueError):
        raise UiPayoutError("bad amount")

    if not (login and password and login_url and payout_url):
        raise UiPayoutError("ui payout not configured (login/urls)")

    if not last4:
        raise UiPayoutError("payout card not configured")

    if amount < payout_min and not is_max:
        raise UiPayoutError("bad amount")

    profile.mkdir(parents=True, exist_ok=True)
    shots = profile / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    state_file = profile / "storage_state.json"

    logger.warning(
        "[platega-ui] payout start amount=%s card=**** %s dry_run=%s "
        "is_max=%s",
        amount,
        last4,
        dry_run,
        is_max,
    )

    async def _run():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    # В Docker процесс — root, без этого Chromium не
                    # стартует; /dev/shm там же крошечный.
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            ctx = await browser.new_context(
                storage_state=(
                    str(state_file) if state_file.exists() else None
                ),
            )
            ctx.set_default_timeout(ACTION_TIMEOUT_MS)
            try:
                page = await ctx.new_page()
                await _goto_ready(page, payout_url)
                if await _on_login_page(page):
                    await _login(page, shots, login_url, login, password)
                    await _goto_ready(page, payout_url)
                    if await _on_login_page(page):
                        err_text = await _visible_error_text(page)
                        await _fail(
                            page,
                            shots,
                            "login failed (check credentials)"
                            + (f": {err_text}" if err_text else ""),
                        )

                try:
                    await ctx.storage_state(path=str(state_file))
                except Exception as e:
                    logger.warning("[platega-ui] state save failed: %s", e)

                await _shot(page, shots, "payout-page")
                try:
                    await page.wait_for_selector(
                        SELECTORS["withdraw_open"],
                        state="visible",
                        timeout=30000,
                    )
                except Exception:
                    await _fail(
                        page,
                        shots,
                        "withdraw button not found "
                        "(check error.html screenshot)",
                    )

                await page.click(SELECTORS["withdraw_open"])
                try:
                    await page.wait_for_selector(
                        SELECTORS["modal"],
                        state="visible",
                        timeout=30000,
                    )
                except Exception:
                    await _fail(page, shots, "payout modal did not open")

                await _shot(page, shots, "modal")
                await page.click(SELECTORS["card_tab"])
                await page.wait_for_timeout(500)
                await _select_saved_card(page, shots, last4)
                start = amount
                site_available = None
                if is_max:
                    # Максимум считает сайт: доступно минус комиссия.
                    site_available = await _read_available_usdt(page, shots)
                    if site_available is not None:
                        from shop.services.billing import get_usd_rub_rate

                        rate, _rate_src = get_usd_rub_rate()
                        payout_max = int(
                            getattr(
                                settings,
                                "PLATEGA_PAYOUT_MAX",
                                87500,
                            ),
                        )
                        start = min(
                            payout_max,
                            math.floor(max(0.0, site_available - 0.5) * rate),
                        )
                        if start < payout_min and not dry_run:
                            await _fail(
                                page,
                                shots,
                                "available "
                                f"{site_available} USDT below minimum",
                            )
                    elif amount < payout_min and not dry_run:
                        await _fail(
                            page,
                            shots,
                            "cannot determine max amount",
                        )

                if dry_run:
                    # Проверка селекторов, баланс не важен: сумму просто
                    # вписываем, активность кнопки не проверяем.
                    await page.fill(SELECTORS["amount_input"], str(amount))
                    await _shot(page, shots, "filled")
                    return {
                        "status": "DRY_RUN",
                        "amount_rub": amount,
                        "actual_amount_rub": amount,
                        "site_available_usdt": site_available,
                        "shots": ["filled"],
                    }

                actual = await _fill_amount_until_confirmed(
                    page,
                    shots,
                    start,
                    payout_min,
                )

                await page.click(SELECTORS["confirm"])
                try:
                    await page.wait_for_selector(
                        SELECTORS["modal"],
                        state="hidden",
                        timeout=15000,
                    )
                    modal_gone = True
                except Exception:
                    modal_gone = False

                await _shot(page, shots, "submitted")
                err = await page.query_selector(SELECTORS["error_markers"])
                if err is not None:
                    err_text = (await err.inner_text() or "").strip()[:200]
                    await _fail(
                        page,
                        shots,
                        f"site error: {err_text or 'unknown'}",
                    )

                success = await page.query_selector(
                    SELECTORS["success_markers"],
                )
                page_text = ""
                if success is not None:
                    page_text = (await success.inner_text() or "").strip()[
                        :200
                    ]

                if not modal_gone and success is None:
                    await _fail(page, shots, "no success confirmation")

                await _shot(page, shots, "done")
                logger.warning(
                    "[platega-ui] payout done requested=%s actual=%s "
                    "card=**** %s",
                    amount,
                    actual,
                    last4,
                )
                return {
                    "status": "DONE",
                    "amount_rub": amount,
                    "actual_amount_rub": actual,
                    "site_available_usdt": site_available,
                    "page_text": page_text,
                    "shots": ["payout-page", "modal", "filled", "done"],
                }
            finally:
                await ctx.close()
                await browser.close()

    try:
        return await asyncio.wait_for(_run(), timeout=timeout_s)
    except asyncio.TimeoutError:
        raise UiPayoutError(f"timeout after {timeout_s}s")
