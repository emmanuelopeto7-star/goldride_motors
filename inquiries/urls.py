from django.urls import path
from .views import InquiryCreateView

urlpatterns = [
    path("", InquiryCreateView.as_view()),
]