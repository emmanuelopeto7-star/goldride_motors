from django.urls import path

from .staff_views import (
    StaffCarDetailView,
    StaffCarExtendView,
    StaffCarImageDetailView,
    StaffCarImageView,
    StaffCarListView,
    StaffImportRequestDetailView,
    StaffImportRatesView,
    StaffImportRequestListView,
    StaffMilestoneView,
    StaffNotifySourcedView,
    StaffOrderDetailView,
    StaffOrderListView,
    StaffPaymentDispatchView,
    StaffPaymentListView,
    StaffPushToStockView,
    StaffReactivateOrderView,
    StaffReconcileAllView,
    StaffReconcileOneView,
    StaffSourcedUnitDetailView,
    StaffSourcedUnitListView,
)

urlpatterns = [
    path("cars/", StaffCarListView.as_view()),
    path("cars/<int:pk>/", StaffCarDetailView.as_view()),
    path("cars/<int:pk>/extend/", StaffCarExtendView.as_view()),
    path("car-images/", StaffCarImageView.as_view()),
    path("car-images/<int:pk>/", StaffCarImageDetailView.as_view()),

    path("orders/", StaffOrderListView.as_view()),
    path("orders/<int:pk>/", StaffOrderDetailView.as_view()),
    path("orders/<int:pk>/reactivate/", StaffReactivateOrderView.as_view()),
    path("milestones/", StaffMilestoneView.as_view()),

    path("import-rates/", StaffImportRatesView.as_view()),
    path("import-requests/", StaffImportRequestListView.as_view()),
    path("import-requests/<int:pk>/", StaffImportRequestDetailView.as_view()),
    path("import-requests/<int:pk>/notify/", StaffNotifySourcedView.as_view()),
    path("sourced-units/", StaffSourcedUnitListView.as_view()),
    path("sourced-units/<int:pk>/", StaffSourcedUnitDetailView.as_view()),
    path(
        "sourced-units/<int:pk>/push-to-stock/",
        StaffPushToStockView.as_view(),
    ),

    path("payments/", StaffPaymentListView.as_view()),
    path("payments/<uuid:reference>/dispatch/", StaffPaymentDispatchView.as_view()),
    path("payments/<uuid:reference>/reconcile/", StaffReconcileOneView.as_view()),
    path("payments/reconcile/", StaffReconcileAllView.as_view()),
]
