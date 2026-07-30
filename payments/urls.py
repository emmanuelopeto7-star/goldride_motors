from django.urls import path
from .views import InitiatePaymentView, PaystackWebhookView


urlpatterns = [
    path("initiate/", InitiatePaymentView.as_view()),
    path("webhook/", PaystackWebhookView.as_view()),
]