from django.test import TestCase
from django.urls import reverse


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
