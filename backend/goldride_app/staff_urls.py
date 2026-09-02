from django.urls import path

from .overview_views import StaffOverviewView
from .team_views import StaffTeamDetailView, StaffTeamListView
from .staff_views import (
    StaffHeroBannerDetailView,
    StaffHeroBannerListView,
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
    StaffRecordPaymentView,
    StaffCorrectPaymentView,
    StaffPaymentHistoryView,
    StaffReconcileAllView,
    StaffReconciliationRunsView,
    StaffReconcileOneView,
    StaffSourcedUnitDetailView,
    StaffSourcedUnitListView,
)

urlpatterns = [
    path("overview/", StaffOverviewView.as_view()),

    path("cars/", StaffCarListView.as_view()),
    path("cars/<int:pk>/", StaffCarDetailView.as_view()),
    path("cars/<int:pk>/extend/", StaffCarExtendView.as_view()),
    path("car-images/", StaffCarImageView.as_view()),
    path("car-images/<int:pk>/", StaffCarImageDetailView.as_view()),

    path("team/", StaffTeamListView.as_view()),
    path("team/<int:pk>/", StaffTeamDetailView.as_view()),

    path("hero-banners/", StaffHeroBannerListView.as_view()),
    path("hero-banners/<int:pk>/", StaffHeroBannerDetailView.as_view()),

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
    path("payments/<uuid:reference>/record/", StaffRecordPaymentView.as_view()),
    path("payments/<uuid:reference>/reconcile/", StaffReconcileOneView.as_view()),
    path("payments/reconcile/", StaffReconcileAllView.as_view()),
    path("payments/reconciliation-runs/", StaffReconciliationRunsView.as_view()),
    path("payments/<uuid:reference>/history/", StaffPaymentHistoryView.as_view()),
    path("payments/<uuid:reference>/correct/", StaffCorrectPaymentView.as_view()),
]
