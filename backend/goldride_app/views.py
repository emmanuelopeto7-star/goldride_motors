from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, permissions, serializers
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from django.contrib.auth import authenticate, get_user_model

from .serializers import (
    EmailLoginSerializer,
    MeUpdateSerializer,
    RegisterSerializer,
    SocialLoginSerializer,
)
from .social import (
    SocialAuthError,
    get_or_create_social_user,
    verify_google,
    verify_linkedin,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "username": user.username,
                "email": user.email,
                "roles": list(user.groups.values_list("name", flat=True)),
                "token": token.key,
            },
            status=201,
        )


class EmailLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=EmailLoginSerializer,
        responses={200: inline_serializer('EmailLogin', {
            'token': serializers.CharField(),
        })},
        description="Sign in with an email address and password. Returns the same "
                    "token as /api/auth/login/, which takes a username instead.",
    )
    def post(self, request):
        email = (request.data.get("email") or "").strip()
        password = request.data.get("password") or ""

        # Load-bearing: unverified social users carry email="", so a request
        # with no email would otherwise match one of them on the lookup below.
        if not email or not password:
            return Response({"detail": "Incorrect email or password."}, status=400)

        # One message for every failure - a distinct "no such account" would
        # tell a stranger which addresses are registered here.
        match = User.objects.filter(email__iexact=email).first()
        user = authenticate(username=match.username, password=password) if match else None

        if user is None:
            return Response({"detail": "Incorrect email or password."}, status=400)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})


class SocialLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social"

    @extend_schema(
        request=SocialLoginSerializer,
        responses={200: inline_serializer('SocialLogin', {
            'token': serializers.CharField(),
            'username': serializers.CharField(),
            'email': serializers.EmailField(),
            'roles': serializers.ListField(child=serializers.CharField()),
            'created': serializers.BooleanField(),
        })},
        description="Sign in with Google or LinkedIn. Google sends `credential` "
                    "(an ID token); LinkedIn sends `code` from the redirect. "
                    "Returns the same token as a normal login.",
    )
    def post(self, request, provider):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            if provider == "google":
                credential = data.get("credential")
                if not credential:
                    return Response({"error": "credential is required"}, status=400)
                profile = verify_google(credential)

            elif provider == "linkedin":
                code = data.get("code")
                if not code:
                    return Response({"error": "code is required"}, status=400)
                profile = verify_linkedin(code)

            else:
                return Response({"error": "unknown provider"}, status=404)

        except SocialAuthError as exc:
            return Response({"error": str(exc)}, status=400)

        user, created = get_or_create_social_user(provider, profile)

        if not user.is_active:
            return Response({"error": "this account is disabled"}, status=403)

        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "username": user.username,
            "email": user.email,
            "roles": list(user.groups.values_list("name", flat=True)),
            "created": created,
        })


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: inline_serializer('Me', {
            'username': serializers.CharField(),
            'email': serializers.EmailField(),
            'is_staff': serializers.BooleanField(),
            'is_superuser': serializers.BooleanField(),
            'roles': serializers.ListField(child=serializers.CharField()),
        })},
        description="The signed-in user and their roles. Use this to decide what the UI shows.",
    )
    def get(self, request):
        return Response(self._payload(request.user))

    @extend_schema(
        request=MeUpdateSerializer,
        responses={200: MeUpdateSerializer},
        description="Update your own details. Social sign-ins whose provider did "
                    "not verify an address arrive with none - this is how they add one.",
    )
    def patch(self, request):
        serializer = MeUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._payload(request.user))

    def _payload(self, user):
        return {
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "roles": list(user.groups.values_list("name", flat=True)),
            # The frontend uses this to prompt before letting them transact.
            "needs_email": not user.email,
            "has_password": user.has_usable_password(),
            "providers": list(
                user.social_accounts.values_list("provider", flat=True)
            ),
        }
