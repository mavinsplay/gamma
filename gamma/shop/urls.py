from django.urls import path

from shop import views

urlpatterns = [
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
]
