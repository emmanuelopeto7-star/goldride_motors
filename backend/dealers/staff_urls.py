from django.urls import path

from .staff_views import (
    StaffApproveApplicationView,
    StaffApproveListingView,
    StaffDealerApplicationDetailView,
    StaffDealerApplicationListView,
    StaffDealerDocumentView,
    StaffDealerDetailView,
    StaffDealerListView,
    StaffDealerListingDetailView,
    StaffDealerListingListView,
    StaffRejectApplicationView,
    StaffRejectListingView,
)

urlpatterns = [
    path("applications/", StaffDealerApplicationListView.as_view()),
    path("applications/<int:pk>/", StaffDealerApplicationDetailView.as_view()),
    path("applications/<int:pk>/approve/", StaffApproveApplicationView.as_view()),
    path("applications/<int:pk>/reject/", StaffRejectApplicationView.as_view()),

    path("documents/<int:pk>/", StaffDealerDocumentView.as_view()),

    path("listings/", StaffDealerListingListView.as_view()),
    path("listings/<int:pk>/", StaffDealerListingDetailView.as_view()),
    path("listings/<int:pk>/approve/", StaffApproveListingView.as_view()),
    path("listings/<int:pk>/reject/", StaffRejectListingView.as_view()),

    path("", StaffDealerListView.as_view()),
    path("<int:pk>/", StaffDealerDetailView.as_view()),
]
