from django.urls import path

from .views import (
    ApprovePurchaseRequestView,
    PurchaseRequestCreateView,
    RejectPurchaseRequestView,
    StaffPurchaseRequestListView,
)

urlpatterns = [
    path("", PurchaseRequestCreateView.as_view()),
    path("staff/", StaffPurchaseRequestListView.as_view()),
    path("staff/<int:pk>/approve/", ApprovePurchaseRequestView.as_view()),
    path("staff/<int:pk>/reject/", RejectPurchaseRequestView.as_view()),
]
