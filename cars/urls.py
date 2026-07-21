from django.urls import path
from .views import carListVeiw

urlpatterns = [
     path("", carListVeiw.as_view()),
]