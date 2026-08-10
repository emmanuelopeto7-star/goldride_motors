"""
URL configuration for goldride_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.authtoken.views import obtain_auth_token

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from goldride_app.views import MeView, RegisterView, SocialLoginView
from imports.views import MyOrdersView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/cars/', include('cars.urls')),
    path('api/inquiries/', include('inquiries.urls')),
    path('api/track/', include('imports.urls')),
    path('api/auth/login/', obtain_auth_token),
    path('api/auth/register/', RegisterView.as_view()),
    path('api/auth/social/<str:provider>/', SocialLoginView.as_view()),
    path('api/me/', MeView.as_view()),
    path('api/my/orders/', MyOrdersView.as_view()),
    path('api/purchases/', include('purchases.urls')),
    path('api/staff/', include('goldride_app.staff_urls')),
    path('api/payments/', include('payments.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
