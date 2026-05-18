from django.urls import path

from user import views

urlpatterns = [
    path("login-page/", views.login_view, name="login_page"),
    path(
        "login-callback/",
        views.telegram_login_callback,
        name="telegram_login_callback",
    ),
    path("status/", views.get_user_status, name="user_status"),
    path("logout/", views.logout_view, name="logout"),
]
