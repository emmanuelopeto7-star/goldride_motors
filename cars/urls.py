from django.urls import path
from .views import carListVeiw, carDetailView

urlpatterns = [
     path("", carListVeiw.as_view()),
    path("<int:pk>/", carDetailView.as_view()),
]