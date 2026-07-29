from django.urls import path
from .views import InquiryCreateView
from .views import InquiryListView

urlpatterns = [
    path("", InquiryCreateView.as_view()),
     path("all/", InquiryListView.as_view()),

]