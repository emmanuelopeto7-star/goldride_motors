import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .social import SocialAuthError, _username_base, create_user_unique

User = get_user_model()


class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class MeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]
        extra_kwargs = {"email": {"required": False}}

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
        return value


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
    password = serializers.CharField(write_only=True, validators=[validate_password])
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
        return value

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
