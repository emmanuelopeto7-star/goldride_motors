from django.urls import path

from .views import StaffConversationReadView, StaffConversationView, StaffInboxView

urlpatterns = [
    path("", StaffInboxView.as_view()),
    path("<int:ticket_id>/", StaffConversationView.as_view()),
    path("<int:ticket_id>/read/", StaffConversationReadView.as_view()),
]
