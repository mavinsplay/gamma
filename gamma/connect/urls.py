from django.urls import path

from connect.views import open_sub_redirect, set_node_status_api

__all__ = ()

urlpatterns = [
    path(
        "set-node-status-api/",
        set_node_status_api,
        name="set_node_status_api",
    ),
    path("open-sub/", open_sub_redirect, name="open_sub_redirect"),
]
