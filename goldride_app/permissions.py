from rest_framework import permissions


class IsCustomer(permissions.BasePermission):
    message = "This endpoint is for customer accounts."

    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and user.groups.filter(name="Customer").exists()


class IsSales(permissions.BasePermission):
    message = "This endpoint is for sales staff."

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        return user.is_superuser or user.groups.filter(name__in=["Sales", "Manager"]).exists()


class IsManager(permissions.BasePermission):
    message = "This endpoint is for managers."

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        return user.is_superuser or user.groups.filter(name="Manager").exists()
