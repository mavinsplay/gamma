from django.urls import path
from .views import set_node_status_api, open_sub_redirect

urlpatterns = [
    path(
        "set-node-status-api/", set_node_status_api, name="set_node_status_api"
    ),
    path("open-sub/", open_sub_redirect, name="open_sub_redirect"),
]
