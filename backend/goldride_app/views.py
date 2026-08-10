from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, permissions, serializers
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import RegisterSerializer


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
