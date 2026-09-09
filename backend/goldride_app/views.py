from urllib.parse import quote

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, permissions, serializers
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import redirect

from .models import get_profile
from .passwords import send_reset_email, set_password
from .serializers import (
    EmailLoginSerializer,
    MeUpdateSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    SocialLoginSerializer,
)
from .social import (
    EmailInUse,
    SocialAuthError,
    get_or_create_social_user,
    verify_google,
    verify_linkedin,
)
from .verification import VerificationError, confirm, send_verification_email

User = get_user_model()

PROVIDER_NAMES = {"google": "Google", "linkedin": "LinkedIn"}


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # They can use the site straight away; the link only decides whether
        # a social sign-in may ever attach itself to this account.
        send_verification_email(user)

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
        responses={200: inline_serializer('EmailLoginResponse', {
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


class VerifyEmailView(APIView):
    """The link in the email. Opened by a browser, not by the app."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "verify"

    @extend_schema(
        request=None,
        responses={302: None},
        description="Confirm an email address from the link that was mailed "
                    "to it, then bounce the browser back to the site with "
                    "`?verified=1` or `?verified=0&reason=...`.",
    )
    def get(self, request, token):
        target = settings.FRONTEND_URL.rstrip("/")
        try:
            confirm(token)
        except VerificationError as exc:
            return redirect(f"{target}/?verified=0&reason={quote(str(exc))}")

        return redirect(f"{target}/?verified=1")


class ResendVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "verify"

    @extend_schema(
        request=None,
        responses={200: inline_serializer('ResendVerification', {
            'detail': serializers.CharField(),
        })},
        description="Send the confirmation email again. Answers the same way "
                    "whether or not anything was sent.",
    )
    def post(self, request):
        if get_profile(request.user).email_verified:
            return Response({"detail": "That address is already confirmed."})

        send_verification_email(request.user)
        # Deliberately vague: an account with no address gets the same reply,
        # and nothing here should be a way to probe account state.
        return Response({"detail": "Check your email for the link."})


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=None,
        responses={204: None},
        description="Sign out by destroying the caller's token. Tokens never "
                    "expire on their own, so clearing the browser's storage "
                    "would leave a working key behind.",
    )
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=204)


class SocialLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "social"

    @extend_schema(
        request=SocialLoginSerializer,
        responses={
            200: inline_serializer('SocialLoginResponse', {
                'token': serializers.CharField(),
                'username': serializers.CharField(),
                'email': serializers.EmailField(),
                'roles': serializers.ListField(child=serializers.CharField()),
                'created': serializers.BooleanField(),
            }),
            409: inline_serializer('SocialLoginConflict', {
                'detail': serializers.CharField(),
                'code': serializers.CharField(),
            }),
        },
        description="Sign in with Google or LinkedIn. Google sends `credential` "
                    "(an ID token); LinkedIn sends `code` from the redirect. "
                    "Returns the same token as a normal login. A 409 with "
                    "`code: email_in_use` means the address is already on an "
                    "account whose email was never verified - that account has "
                    "to sign in with its password first.",
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

        try:
            user, created = get_or_create_social_user(provider, profile)
        except EmailInUse:
            # Not an enumeration leak: the provider already vouched that this
            # caller controls the address, so they are being told about their
            # own account, not somebody else's.
            name = PROVIDER_NAMES.get(provider, provider)
            return Response(
                {
                    "detail": f"An account with this email already exists. "
                              f"Sign in with your password to connect {name}.",
                    "code": EmailInUse.code,
                },
                status=409,
            )

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
            'needs_email': serializers.BooleanField(),
            'email_verified': serializers.BooleanField(),
            'has_password': serializers.BooleanField(),
            'providers': serializers.ListField(child=serializers.CharField()),
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
            "email_verified": get_profile(user).email_verified,
            "has_password": user.has_usable_password(),
            "providers": list(
                user.social_accounts.values_list("provider", flat=True)
            ),
        }


class PasswordResetRequestView(APIView):
    """Ask for a reset link.

    Always answers the same way. Whether an address has an account here is
    exactly the fact an attacker wants from this endpoint - a different answer
    for a hit and a miss turns it into a free membership oracle, and this site
    holds enough about its customers that membership alone is worth having.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    ANSWER = {
        "detail": "If that address has an account, a reset link is on its way."
    }

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: inline_serializer(
            'PasswordResetRequested', {'detail': serializers.CharField()}
        )},
        description="Request a password reset link. The response is identical "
                    "whether or not the address has an account.",
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True
        ).first()

        if user is not None:
            # Social-only accounts have an unusable password. Sending a link
            # would work, and would quietly bolt a password onto an account
            # whose owner only ever proved themselves to Google - so it is
            # refused, silently, like every other miss here.
            if user.has_usable_password():
                send_reset_email(user)

        return Response(self.ANSWER)


class PasswordResetConfirmView(APIView):
    """Spend a reset link and set the new password."""

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: inline_serializer(
            'PasswordResetDone', {'detail': serializers.CharField()}
        )},
        description="Set a new password using a link from the reset email. "
                    "The link works once; every API token on the account is "
                    "revoked, so any other session has to sign in again.",
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        set_password(
            serializer.validated_data["user"],
            serializer.validated_data["password"],
        )
        return Response({"detail": "Your password has been changed. Please sign in."})


class PasswordChangeView(APIView):
    """Change the password on the account you are signed in to."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={200: inline_serializer(
            'PasswordChanged', {'detail': serializers.CharField(),
                                'token': serializers.CharField()}
        )},
        description="Change your own password. Requires the current one. "
                    "Every existing API token is revoked and a fresh one is "
                    "returned, so this session continues and others do not.",
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        set_password(user, serializer.validated_data["password"])

        # set_password revoked every token including the one that authenticated
        # this call. Handing back a fresh one keeps the caller signed in here
        # while every other device is signed out - which is the point.
        token = Token.objects.create(user=user)
        return Response({"detail": "Your password has been changed.", "token": token.key})
