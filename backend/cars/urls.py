from django.urls import path
from .views import CarMakesView, carListVeiw, carDetailView

urlpatterns = [
    path("", carListVeiw.as_view()),
    # Before <int:pk>/ so "makes" is never read as a car id.
    path("makes/", CarMakesView.as_view()),
    path("<int:pk>/", carDetailView.as_view()),
]