from django.urls import path

from .views import (
    TicketClaimView,
    TicketCloseView,
    TicketDetailView,
    TicketListView,
    TicketReleaseView,
    TicketReplyView,
)

urlpatterns = [
    path("", TicketListView.as_view()),
    path("<int:pk>/", TicketDetailView.as_view()),
    path("<int:pk>/claim/", TicketClaimView.as_view()),
    path("<int:pk>/release/", TicketReleaseView.as_view()),
    path("<int:pk>/reply/", TicketReplyView.as_view()),
    path("<int:pk>/close/", TicketCloseView.as_view()),
]
