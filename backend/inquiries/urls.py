from django.urls import path
from .views import InquiryCreateView
from .views import InquiryListView
from .views import StaffInquiryDetailView

urlpatterns = [
    path("", InquiryCreateView.as_view()),
     path("all/", InquiryListView.as_view()),
     path("<int:pk>/", StaffInquiryDetailView.as_view()),

]