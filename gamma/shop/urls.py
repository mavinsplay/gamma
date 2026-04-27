from django.urls import path

from shop import views


urlpatterns = [
    path("checkout/<int:tariff_id>/", views.checkout_view, name="checkout"),
    path(
        "payment/<int:order_id>/",
        views.mock_payment_view,
        name="mock_payment",
    ),
    path("success/<int:sub_id>/", views.success_view, name="payment_success"),
]
