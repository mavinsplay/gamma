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
    path("checkout/<int:tariff_id>/", views.checkout_view, name="checkout"),
    path(
        "payment/<int:order_id>/",
        views.mock_payment_view,
        name="mock_payment",
    ),
    path("success/<int:sub_id>/", views.success_view, name="payment_success"),
    path("sync-data-api/", views.sync_data_api, name="sync_data_api"),
    path(
        "update-preferences-api/",
        views.update_preferences_api,
        name="update_preferences_api",
    ),
    path("promo-api/", views.promo_api, name="promo_api"),
]
