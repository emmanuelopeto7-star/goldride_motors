from django.urls import path
from.views import InitiatePaymentView

urlpatterns = [
    path("initiate/", InitiatePaymentView.as_view()),
]