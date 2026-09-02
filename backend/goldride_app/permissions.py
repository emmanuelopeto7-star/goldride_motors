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


class IsDealer(permissions.BasePermission):
    """An approved dealership, signed in.

    No superuser bypass, for the same reason IsCustomer has none: every dealer
    endpoint is scoped to `request.user.dealer`, and an account with no
    dealership behind it has no listings to be scoped to. A superuser who
    needs to see a dealer's submissions has the staff screens.
    """

    message = "This endpoint is for dealer accounts."

    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated
            and user.groups.filter(name="Dealer").exists()
            and hasattr(user, "dealer")
            and user.dealer.is_active
        )
