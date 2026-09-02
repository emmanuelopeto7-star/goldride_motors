from django.urls import path

from .consumers import CustomerChatConsumer, StaffChatConsumer

websocket_urlpatterns = [
    path("ws/chat/<int:ticket_id>/", CustomerChatConsumer.as_asgi()),
    path("ws/staff/chat/<int:ticket_id>/", StaffChatConsumer.as_asgi()),
]
