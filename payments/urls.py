from django.urls import path
from .views import InitiatePaymentView, PaystackWebhookView, MpesaCallbackView


urlpatterns = [
    path("initiate/", InitiatePaymentView.as_view()),
    path("webhook/", PaystackWebhookView.as_view()),
    path("mpesa/callback/", MpesaCallbackView.as_view()),
]