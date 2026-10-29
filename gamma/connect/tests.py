from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import override_settings, TestCase
from django.urls import reverse
import requests

from connect.models import ProxyCheckStatus
from connect.services.xray_checker import get_checker_proxies

__all__ = (
    "OpenSubscriptionRedirectTests",
    "XrayCheckerTests",
    "ProxyAlertTests",
)


class OpenSubscriptionRedirectTests(TestCase):
    def test_rejects_xss_payload(self):
        response = self.client.get(
            reverse("open_sub_redirect"),
            {"link": "</script><script>alert(1)</script>"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "alert(1)")

    def test_allows_https_subscription_link(self):
        response = self.client.get(
            reverse("open_sub_redirect"),
            {"link": "https://subscription.example/test"},
        )

        self.assertContains(
            response,
            "happ://add/https://subscription.example/test",
        )


class XrayCheckerTests(TestCase):
    def setUp(self):
        cache.clear()

    def _resp(self, payload, status=200):
        resp = MagicMock()
        resp.status_code = status
        resp.ok = status < 400
        resp.json = MagicMock(return_value=payload)
        return resp

    @override_settings(XRAY_CHECKER_URL="")
    def test_disabled_without_url(self):
        proxies, error = get_checker_proxies()

        self.assertEqual(proxies, [])
        self.assertEqual(error, "disabled")

    @override_settings(
        XRAY_CHECKER_URL="http://checker:2112",
        XRAY_CHECKER_USER="user",
        XRAY_CHECKER_PASSWORD="pass",
    )
    @patch("connect.services.xray_checker.requests.get")
    def test_parses_proxies(self, mock_get):
        mock_get.return_value = self._resp(
            {
                "success": True,
                "data": [
                    {
                        "stableId": "a1b2c3d4e5f60718",
                        "name": "DE-1",
                        "subName": "Gamma VPN",
                        "groupName": "eu",
                        "server": "203.0.113.10",
                        "port": 443,
                        "protocol": "vless",
                        "online": True,
                        "latencyMs": 87,
                        "lastCheck": 1751130000,
                        "metricsLabels": {
                            "location": "Germany",
                        },
                    },
                ],
            },
        )

        proxies, error = get_checker_proxies()

        self.assertIsNone(error)
        self.assertEqual(len(proxies), 1)
        proxy = proxies[0]
        self.assertEqual(proxy["stableId"], "a1b2c3d4e5f60718")
        self.assertEqual(proxy["protocol"], "vless")
        self.assertEqual(proxy["address"], "203.0.113.10:443")
        self.assertTrue(proxy["online"])
        self.assertEqual(proxy["latencyMs"], 87)
        self.assertEqual(proxy["location"], "Germany")

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["auth"], ("user", "pass"))

    @override_settings(XRAY_CHECKER_URL="http://checker:2112")
    @patch("connect.services.xray_checker.requests.get")
    def test_auth_error(self, mock_get):
        mock_get.return_value = self._resp(
            {"success": False, "error": "nope"},
        )
        mock_get.return_value.status_code = 401
        mock_get.return_value.ok = False

        proxies, error = get_checker_proxies()

        self.assertEqual(proxies, [])
        self.assertEqual(error, "auth_error")

    @override_settings(XRAY_CHECKER_URL="http://checker:2112")
    @patch("connect.services.xray_checker.requests.get")
    def test_connection_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("down")

        proxies, error = get_checker_proxies()

        self.assertEqual(proxies, [])
        self.assertEqual(error, "connection_error")

    @override_settings(XRAY_CHECKER_URL="http://checker:2112")
    @patch("connect.services.xray_checker.requests.get")
    def test_results_are_cached(self, mock_get):
        mock_get.return_value = self._resp(
            {"success": True, "data": []},
        )

        get_checker_proxies()
        get_checker_proxies()

        self.assertEqual(mock_get.call_count, 1)

    @override_settings(XRAY_CHECKER_URL="http://checker:2112")
    @patch("connect.services.xray_checker.requests.get")
    def test_country_from_proxy_name(self, mock_get):
        mock_get.return_value = self._resp(
            {
                "success": True,
                "data": [
                    {
                        "stableId": "a",
                        "name": "whitelist-xhttp-USA us",
                    },
                    {
                        "stableId": "b",
                        "name": "DE-1",
                    },
                    {
                        "stableId": "c",
                        "name": "Just a server",
                    },
                    {
                        "stableId": "d",
                        "name": "xray-Germany \U0001f1e9\U0001f1ea",
                    },
                ],
            },
        )

        proxies, error = get_checker_proxies()

        self.assertIsNone(error)
        by_id = {p["stableId"]: p for p in proxies}
        self.assertEqual(by_id["a"]["countryCode"], "us")
        self.assertEqual(by_id["a"]["displayName"], "whitelist-xhttp-USA")
        self.assertEqual(by_id["b"]["countryCode"], "de")
        self.assertEqual(by_id["c"]["countryCode"], None)
        self.assertEqual(by_id["d"]["countryCode"], "de")
        self.assertEqual(by_id["d"]["displayName"], "xray-Germany")


class ProxyAlertTests(TestCase):
    def _proxy(self, online=True):
        return {
            "stableId": "aaa",
            "name": "DE-1",
            "protocol": "vless",
            "address": "203.0.113.10:443",
            "online": online,
            "latencyMs": 50,
            "lastCheck": 1751130000,
        }

    def test_first_sight_creates_state_without_event(self):
        from connect.services.proxy_alerts import collect_proxy_events

        events = collect_proxy_events([self._proxy(online=False)])

        self.assertEqual(events, [])
        status = ProxyCheckStatus.objects.get(stable_id="aaa")
        self.assertFalse(status.last_known_online)
        self.assertIsNone(status.last_alert_sent)

    def test_offline_transition_emits_event_once(self):
        from connect.models import ProxyCheckStatus
        from connect.services.proxy_alerts import (
            collect_proxy_events,
            mark_proxy_alert_sent,
        )

        ProxyCheckStatus.objects.create(
            stable_id="aaa",
            last_known_online=True,
        )

        events = collect_proxy_events([self._proxy(online=False)])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "OFFLINE")

        mark_proxy_alert_sent("aaa", "OFFLINE")
        events = collect_proxy_events([self._proxy(online=False)])
        self.assertEqual(events, [])

    def test_online_recovery_emits_event(self):
        from connect.models import ProxyCheckStatus
        from connect.services.proxy_alerts import collect_proxy_events

        ProxyCheckStatus.objects.create(
            stable_id="aaa",
            last_known_online=False,
            last_alert_sent="OFFLINE",
        )

        events = collect_proxy_events([self._proxy(online=True)])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "ONLINE")

    def test_no_event_without_transition(self):
        from connect.models import ProxyCheckStatus
        from connect.services.proxy_alerts import collect_proxy_events

        ProxyCheckStatus.objects.create(
            stable_id="aaa",
            last_known_online=True,
            last_alert_sent="OFFLINE",
        )

        events = collect_proxy_events([self._proxy(online=True)])

        self.assertEqual(events, [])

    def test_muted_ids(self):
        from connect.models import ProxyCheckStatus
        from connect.services.proxy_alerts import get_muted_proxy_ids

        ProxyCheckStatus.objects.create(
            stable_id="muted-1",
            notifications_enabled=False,
        )
        ProxyCheckStatus.objects.create(
            stable_id="loud-1",
            notifications_enabled=True,
        )

        self.assertEqual(get_muted_proxy_ids(), {"muted-1"})

    @override_settings(ADMIN_TELEGRAM_ID=111)
    @patch("connect.views.verify_telegram_init_data")
    def test_toggle_proxy_notifications(self, mock_verify):
        mock_verify.return_value = (True, {"id": 111, "username": "a"})
        url = reverse("toggle_proxy_notifications_api")

        response = self.client.post(
            url,
            {"stable_id": "aaa", "init_data": "x"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"success": True, "notifications_enabled": False},
        )

        response = self.client.post(
            url,
            {"stable_id": "aaa", "init_data": "x"},
        )
        self.assertEqual(response.json()["notifications_enabled"], True)

        mock_verify.return_value = (True, {"id": 222, "username": "u"})
        response = self.client.post(
            url,
            {"stable_id": "aaa", "init_data": "x"},
        )
        self.assertEqual(response.status_code, 403)

        mock_verify.return_value = (True, {"id": 111, "username": "a"})
        response = self.client.post(url, {"init_data": "x"})
        self.assertEqual(response.status_code, 400)
