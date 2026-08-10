from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, permissions, serializers
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import RegisterSerializer, SocialLoginSerializer
from .social import (
    SocialAuthError,
    get_or_create_social_user,
    verify_google,
    verify_linkedin,
)


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
        user = request.user
        return Response({
            "username": user.username,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "roles": list(user.groups.values_list("name", flat=True)),
        })
