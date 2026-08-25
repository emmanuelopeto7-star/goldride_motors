"""Adding and removing staff, without opening the Django admin.

Two rules run through all of it:

Removing somebody deactivates the account rather than deleting it. Their name
is on decisions - who approved a sale, who answered an enquiry - and several
of those relations are PROTECT, so a delete would either fail or take the
record with it. A deactivated account cannot sign in, which is what "remove"
actually means here.

And nobody may act on themselves. Not a matter of trust: it is what stops the
last manager quietly locking everyone out of the queue, including themselves.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied

from .permissions import IsManager
from .team_serializers import StaffMemberSerializer

User = get_user_model()


class StaffTeamListView(generics.ListCreateAPIView):
    """Everyone who can sign in to the dashboard."""

    serializer_class = StaffMemberSerializer
    permission_classes = [IsManager]
    pagination_class = None

    def get_queryset(self):
        # Customers are not staff and do not belong on this screen. Superusers
        # do: they hold every permission, and a list of who can do what that
        # leaves them out is worse than no list.
        return (
            User.objects.filter(
                Q(groups__name__in=["Sales", "Manager"]) | Q(is_superuser=True)
            )
            .distinct()
            .order_by("-is_active", "username")
        )


class StaffTeamDetailView(generics.RetrieveUpdateAPIView):
    """Change somebody's role, or put their account beyond use.

    Deliberately no DELETE. See the module docstring.
    """

    queryset = User.objects.all()
    serializer_class = StaffMemberSerializer
    permission_classes = [IsManager]

    def check_object_permissions(self, request, user):
        super().check_object_permissions(request, user)

        if request.method in ("PATCH", "PUT"):
            if user == request.user:
                raise PermissionDenied(
                    "You cannot change your own role or switch off your own "
                    "account. Ask another manager."
                )
            if user.is_superuser:
                raise PermissionDenied(
                    "The owner's account is managed in Django admin, not here."
                )

    @extend_schema(
        description="Change a colleague's role, or deactivate them. "
                    "Deactivating is how an account is retired - the record of "
                    "what they approved and answered stays readable."
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
