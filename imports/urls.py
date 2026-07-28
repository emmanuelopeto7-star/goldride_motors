from django.urls import path
from .views import TrackingView

urlpatterns=[
     path("<uuid:token>/", TrackingView.as_view()),
]