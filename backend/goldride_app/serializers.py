from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

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
        user = User.objects.create_user(**validated_data)
        group, _ = Group.objects.get_or_create(name="Customer")
        user.groups.add(group)
        return user
