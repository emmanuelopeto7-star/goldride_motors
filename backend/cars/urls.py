from django.urls import path
from .views import CarMakesView, CarModelsView, carListVeiw, carDetailView

urlpatterns = [
    path("", carListVeiw.as_view()),
    # Before <int:pk>/ so "makes" and "models" are never read as car ids.
    path("makes/", CarMakesView.as_view()),
    path("models/", CarModelsView.as_view()),
    path("<int:pk>/", carDetailView.as_view()),
]