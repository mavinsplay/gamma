from django.urls import path

from shop import views, views_billing

urlpatterns = [
    path("billing-api/", views_billing.billing_api, name="billing_api"),
    path(
        "billing-server-api/",
        views_billing.billing_server_api,
        name="billing_server_api",
    ),
    path(
        "billing-payout-api/",
        views_billing.billing_payout_api,
        name="billing_payout_api",
    ),
    path(
        "billing-payout-job-api/",
        views_billing.billing_payout_job_api,
        name="billing_payout_job_api",
    ),
    path(
        "billing-autopayout-api/",
        views_billing.billing_autopayout_api,
        name="billing_autopayout_api",
    ),
    path(
        "billing-blacklist-api/",
        views_billing.billing_blacklist_api,
        name="billing_blacklist_api",
    ),
    path(
        "billing-ledger-api/",
        views_billing.billing_ledger_api,
        name="billing_ledger_api",
    ),
    path("buy-api/", views.buy_tariff_api, name="buy_tariff_api"),
    path("topup-api/", views.topup_api, name="topup_api"),
    path("buy-slot-api/", views.buy_slot_api, name="buy_slot_api"),
    path("extend-sub-api/", views.extend_sub_api, name="extend_sub_api"),
    path(
        "get-sub-link-api/",
        views.get_subscription_link_api,
        name="get_subscription_link_api",
    ),
    path(
        "delete-hwid-device-api/",
        views.delete_hwid_device_api,
        name="delete_hwid_device_api",
    ),
    path(
        "check-payment-api/<int:order_id>/",
        views.check_payment_api,
        name="check_payment_api",
    ),
    path("success/<int:sub_id>/", views.success_view, name="payment_success"),
    path("fail/<int:sub_id>/", views.fail_view, name="payment_fail"),
    path("sync-data-api/", views.sync_data_api, name="sync_data_api"),
    path("payments-api/", views.payments_api, name="payments_api"),
    path(
        "update-preferences-api/",
        views.update_preferences_api,
        name="update_preferences_api",
    ),
    path("promo-api/", views.promo_api, name="promo_api"),
    path(
        "topup-whitelist-traffic-api/",
        views.topup_whitelist_traffic_api,
        name="topup_whitelist_traffic_api",
    ),
    path(
        "platega-callback/",
        views.platega_callback,
        name="platega_callback",
    ),
]
