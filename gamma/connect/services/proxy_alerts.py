"""Переходы конфигов Xray Checker -> события для алертов админу.

Чистая логика поверх ProxyCheckStatus: бот только форматирует
и отправляет тексты. Первый опрос конфига события не даёт
(только запоминает состояние), дальше — одно событие на переход.
"""

from connect.models import ProxyCheckStatus

__all__ = [
    "OFFLINE",
    "ONLINE",
    "collect_proxy_events",
    "get_muted_proxy_ids",
    "mark_proxy_alert_sent",
]

OFFLINE = "OFFLINE"
ONLINE = "ONLINE"


def collect_proxy_events(proxies):
    """Сверить конфиги с БД и вернуть [(kind, proxy)] переходов.

    kind — "OFFLINE" или "ONLINE". Состояние last_known_online
    обновляется сразу; пометка last_alert_sent ставится отдельно
    через mark_proxy_alert_sent — только после успешной отправки.
    """
    statuses = {s.stable_id: s for s in ProxyCheckStatus.objects.all()}
    events = []

    for proxy in proxies or []:
        if not isinstance(proxy, dict):
            continue

        stable_id = str(proxy.get("stableId") or "")
        if not stable_id:
            continue

        is_online = bool(proxy.get("online"))
        status = statuses.get(stable_id)
        if status is None:
            statuses[stable_id] = ProxyCheckStatus.objects.create(
                stable_id=stable_id,
                last_known_online=is_online,
            )
            continue

        if status.last_known_online is True and not is_online:
            if status.last_alert_sent != OFFLINE:
                events.append((OFFLINE, proxy))
        elif status.last_known_online is False and is_online:
            if status.last_alert_sent != ONLINE:
                events.append((ONLINE, proxy))

        if status.last_known_online != is_online:
            status.last_known_online = is_online
            status.save(update_fields=["last_known_online"])

    return events


def mark_proxy_alert_sent(stable_id, kind):
    """Запомнить отправленный алерт (защита от спама)."""
    ProxyCheckStatus.objects.filter(stable_id=stable_id).update(
        last_alert_sent=kind,
    )


def get_muted_proxy_ids():
    """Stable ID конфигов с выключенными уведомлениями."""
    return set(
        ProxyCheckStatus.objects.filter(
            notifications_enabled=False,
        ).values_list("stable_id", flat=True),
    )
