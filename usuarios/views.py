from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .serializers import LoginSerializer, MeSerializer


class LoginView(APIView):
    """POST /api/v1/auth/login -> {"access", "refresh", "user": {id, name, email, role}}."""

    permission_classes = [AllowAny]
    authentication_classes = []
    # Limite de tentativas por IP (escopo 'login' em DEFAULT_THROTTLE_RATES): freia forca bruta.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    @extend_schema(request=LoginSerializer, responses=inline_serializer('LoginResponse', {
        'access': serializers.CharField(),
        'refresh': serializers.CharField(),
        'user': inline_serializer('LoginUser', {
            'id': serializers.IntegerField(), 'name': serializers.CharField(),
            'email': serializers.EmailField(), 'role': serializers.CharField(allow_null=True),
        }),
    }))
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class MeView(APIView):
    """GET /api/v1/auth/me -> dados, papel, grupos e permissoes de quem esta logado."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)
