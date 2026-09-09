import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import get_profile
from .social import SocialAuthError, _username_base, create_user_unique
from .validators import validate_deliverable_email
from .verification import send_verification_email

User = get_user_model()


def _check_deliverable(value):
    """Adapt the Django-style validator to a DRF field error."""
    try:
        validate_deliverable_email(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages[0])
    return value


class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class MeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]
        extra_kwargs = {"email": {"required": False}}

    def update(self, instance, validated_data):
        moved = (
            "email" in validated_data
            and (validated_data["email"] or "").lower() != (instance.email or "").lower()
        )
        user = super().update(instance, validated_data)

        if moved:
            # Load-bearing: a verified account that changes its address would
            # otherwise stay verified on an address nobody proved - which is
            # the linking hole again, through a different door.
            profile = get_profile(user)
            if profile.email_verified:
                profile.email_verified = False
                profile.save(update_fields=["email_verified"])
            send_verification_email(user)

        return user

    def validate_email(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Enter an email address.")

        taken = User.objects.filter(email__iexact=value)
        if self.instance:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError(
                "An account with that email already exists."
            )
        # Same rule as signup: moving to an unreachable address would strand
        # the account exactly as creating one there would.
        return _check_deliverable(value)


class SocialLoginSerializer(serializers.Serializer):
    credential = serializers.CharField(
        required=False, allow_blank=True,
        help_text="Google: the ID token from Google Identity Services.",
    )
    code = serializers.CharField(
        required=False, allow_blank=True,
        help_text="LinkedIn: the authorisation code from the redirect.",
    )


class RegisterSerializer(serializers.ModelSerializer):
    # No `validators=[validate_password]` here on purpose. A field validator is
    # handed the value alone, so `validate_password` runs with user=None and
    # UserAttributeSimilarityValidator - the one that stops somebody using
    # their own email address as their password - silently checks nothing.
    # It is run in validate() below instead, against the account as submitted.
    password = serializers.CharField(write_only=True)
    # Optional: most people sign up with an email and never want a handle.
    # Declaring it by hand loses the validators ModelSerializer would have
    # built, so they are put back explicitly.
    username = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
        validators=[
            UnicodeUsernameValidator(),
            UniqueValidator(
                queryset=User.objects.all(),
                message="A user with that username already exists.",
            ),
        ],
        help_text="Optional. Derived from the email address when left out.",
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password"]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
        }

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with that email already exists."
            )
        # After the uniqueness check, so a returning customer is told the
        # useful thing rather than being sent to fix an address that is fine.
        return _check_deliverable(value)

    def validate(self, attrs):
        # An unsaved instance carrying what was typed, purely so the similarity
        # validator has something to compare against. It is never saved - the
        # real user is built in create().
        candidate = User(
            username=(attrs.get("username") or "").strip(),
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs.get("password"), user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        username = (validated_data.pop("username", "") or "").strip()
        password = validated_data.pop("password")

        if username:
            user = User.objects.create_user(
                username=username, password=password, **validated_data
            )
        else:
            try:
                user = create_user_unique(
                    # secrets, not the pk: the fallback only matters for an
                    # address whose local part is entirely punctuation.
                    base=_username_base(validated_data.get("email", ""), secrets.token_hex(4)),
                    password=password,
                    **validated_data,
                )
            except SocialAuthError:
                raise serializers.ValidationError(
                    {"username": "Could not derive a username, please choose one."}
                )

        # email_verified stays False - nothing here proved the address is
        # theirs, and a social sign-in must not link to it until it does.
        group, _ = Group.objects.get_or_create(name="Customer")
        user.groups.add(group)
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """Asking for a link. Takes an address and admits nothing about it."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Spending a link.

    `validate_password` needs the user to run its similarity check, and the
    user is only known once the token is read - so the token is resolved here
    rather than in the view, and the resolved user is handed back on the
    serializer for the view to act on.
    """

    token = serializers.CharField()
    password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        from .passwords import ResetError, read_token

        try:
            user = read_token(attrs["token"])
        except ResetError as exc:
            raise serializers.ValidationError({"token": str(exc)})

        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        attrs["user"] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """Changing a password you already know.

    The current one is required even though the caller is authenticated: a
    token in somebody else's hands is exactly the case this stops, and without
    it a stolen token converts straight into a stolen account.
    """

    current_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("That is not your current password.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user

        if attrs["current_password"] == attrs["password"]:
            raise serializers.ValidationError(
                {"password": "Choose a password you have not just been using."}
            )

        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs
