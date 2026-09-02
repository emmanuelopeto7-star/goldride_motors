from django.urls import path

from .views import MyConversationReadView, MyConversationView, MyThreadsView

urlpatterns = [
    path("", MyThreadsView.as_view()),
    path("<int:ticket_id>/", MyConversationView.as_view()),
    path("<int:ticket_id>/read/", MyConversationReadView.as_view()),
]
