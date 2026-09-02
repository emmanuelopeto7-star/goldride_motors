from django.urls import path

from .views import (
    DealerActivateView,
    DealerApplyView,
    DealerListingDetailView,
    DealerListingImageDetailView,
    DealerListingImageView,
    DealerListingListView,
    DealerMeView,
)

urlpatterns = [
    # Public: one way in, no way to read the applications back out.
    path("apply/", DealerApplyView.as_view()),
    path("activate/<str:token>/", DealerActivateView.as_view()),

    # The portal. Everything below is scoped to the signed-in dealership.
    path("me/", DealerMeView.as_view()),
    path("listings/", DealerListingListView.as_view()),
    path("listings/<int:pk>/", DealerListingDetailView.as_view()),
    path("listings/<int:pk>/images/", DealerListingImageView.as_view()),
    path(
        "listings/<int:pk>/images/<int:image_id>/",
        DealerListingImageDetailView.as_view(),
    ),
]
