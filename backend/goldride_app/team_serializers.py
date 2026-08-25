"""Staff accounts, from the dashboard rather than the Django admin."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

User = get_user_model()

ROLES = ["Sales", "Manager"]


class StaffMemberSerializer(serializers.ModelSerializer):
    """A member of staff and what they may do.

    Role is a single value here rather than a list of groups. The database
    models it as group membership, but nobody thinks of a colleague as "in
    the Sales group" - they are sales, or they are a manager - and letting the
    two drift apart is how someone ends up with both.
    """

    # Write-only: there is no `user.role` to read - the role is worked out
    # from group membership in to_representation below.
    role = serializers.ChoiceField(choices=ROLES, write_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    # Declared explicitly with a default. DRF gives BooleanField HTML-checkbox
    # semantics - a field missing from form data reads as False - so a client
    # posting a new colleague without mentioning is_active was creating them
    # already deactivated, unable to sign in and with nothing to say why.
    # PATCH is partial, so this default never fires on an update.
    is_active = serializers.BooleanField(required=False, default=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "full_name",
            "role", "is_active", "is_superuser", "last_login", "date_joined",
            "password",
        ]
        read_only_fields = ["last_login", "date_joined", "is_superuser"]

    def get_full_name(self, user):
        return user.get_full_name()

    def validate_password(self, password):
        validate_password(password)
        return password

    def validate(self, attrs):
        # A password is only required when the account is being made. Changing
        # somebody's password afterwards is deliberately not offered here -
        # that is theirs to do, not a colleague's.
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": ["Set a password for the new account."]}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        role = validated_data.pop("role")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        Group.objects.get_or_create(name=role)[0].user_set.add(user)
        return user

    @transaction.atomic
    def update(self, user, validated_data):
        role = validated_data.pop("role", None)
        # Not through this endpoint - see validate().
        validated_data.pop("password", None)

        for field, value in validated_data.items():
            setattr(user, field, value)
        user.save()

        if role is not None:
            for name in ROLES:
                group = Group.objects.get_or_create(name=name)[0]
                if name == role:
                    group.user_set.add(user)
                else:
                    group.user_set.remove(user)
        return user

    def to_representation(self, user):
        data = super().to_representation(user)
        names = set(user.groups.values_list("name", flat=True))
        # Superusers pass every permission check without holding a group, so
        # showing them as "no role" would be a lie about what they can do.
        if user.is_superuser:
            data["role"] = "Manager"
        else:
            data["role"] = "Manager" if "Manager" in names else (
                "Sales" if "Sales" in names else None
            )
        return data
