from django.urls import path

from .views import (
    InitiatePaymentView,
    MpesaCallbackView,
    MyPaymentDispatchView,
    MyPaymentsView,
    PaystackWebhookView,
)


urlpatterns = [
    path("initiate/", InitiatePaymentView.as_view()),
    path("webhook/", PaystackWebhookView.as_view()),
    path("mpesa/callback/", MpesaCallbackView.as_view()),
    path("mine/", MyPaymentsView.as_view()),
    path("mine/<uuid:reference>/pay/", MyPaymentDispatchView.as_view()),
]
