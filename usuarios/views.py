
import json
import logging
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from decouple import config

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes

from drf_spectacular.utils import extend_schema, inline_serializer

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import LoginSerializer, MeSerializer


logger = logging.getLogger(__name__)
User = get_user_model()


class LoginView(APIView):
    """Login por e-mail e senha."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    @extend_schema(
        request=LoginSerializer,
        responses=inline_serializer(
            'LoginResponse',
            {
                'access': serializers.CharField(),
                'refresh': serializers.CharField(),
                'user': inline_serializer(
                    'LoginUser',
                    {
                        'id': serializers.IntegerField(),
                        'name': serializers.CharField(),
                        'email': serializers.EmailField(),
                        'role': serializers.CharField(
                            allow_null=True
                        ),
                    }
                ),
            }
        )
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class MeView(APIView):
    """Retorna os dados do usuário autenticado."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutView(APIView):
    """Invalida o refresh token do usuário."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=LogoutSerializer)
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(
                serializer.validated_data['refresh']
            )

            if str(token['user_id']) != str(request.user.pk):
                return Response(
                    {
                        'detail':
                        'O token não pertence ao usuário.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            token.blacklist()

            return Response({
                'detail': 'Logout realizado com sucesso.'
            })

        except (TokenError, KeyError, ValueError):
            return Response(
                {
                    'detail':
                    'Refresh token inválido ou expirado.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetView(APIView):
    """Solicita a recuperação da senha por e-mail."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    @extend_schema(request=PasswordResetSerializer)
    def post(self, request):
        serializer = PasswordResetSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        resposta = {
            'detail': (
                'Se o e-mail estiver cadastrado, '
                'você receberá instruções para '
                'redefinir sua senha.'
            )
        }

        usuarios = User.objects.filter(
            email__iexact=email,
            is_active=True
        )

        for usuario in usuarios:
            if not usuario.has_usable_password():
                continue

            uid = urlsafe_base64_encode(
                force_bytes(usuario.pk)
            )

            token = default_token_generator.make_token(
                usuario
            )

            base_url = config(
                'PASSWORD_RESET_URL',
                default=''
            )

            api_key = config(
                'RESEND_API_KEY',
                default=''
            )

            remetente = config(
                'RESEND_FROM_EMAIL',
                default=''
            )

            if not all([base_url, api_key, remetente]):
                logger.error(
                    'Serviço de recuperação de senha '
                    'não configurado.'
                )
                break

            separador = '&' if '?' in base_url else '?'

            link = (
                base_url
                + separador
                + urlencode({
                    'uid': uid,
                    'token': token
                })
            )

            mensagem = {
                'from': remetente,
                'to': [usuario.email],
                'subject': 'Recuperação de senha',
                'text': (
                    'Recebemos uma solicitação para '
                    'redefinir sua senha.\n\n'
                    f'Acesse: {link}\n\n'
                    'Se não foi você, ignore esta mensagem.'
                ),
            }

            requisicao = Request(
                'https://api.resend.com/emails',
                data=json.dumps(mensagem).encode('utf-8'),
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                method='POST'
            )

            try:
                with urlopen(requisicao, timeout=10):
                    pass
            except Exception:
                logger.exception(
                    'Falha no envio de recuperação de senha.'
                )

        return Response(resposta)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False
    )


class PasswordResetConfirmView(APIView):
    """Valida o token e registra a nova senha."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    @extend_schema(request=PasswordResetConfirmSerializer)
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        dados = serializer.validated_data

        try:
            usuario_id = force_str(
                urlsafe_base64_decode(dados['uid'])
            )

            usuario = User.objects.get(
                pk=usuario_id,
                is_active=True
            )

        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            return Response(
                {'detail': 'Link inválido ou expirado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not default_token_generator.check_token(
            usuario,
            dados['token']
        ):
            return Response(
                {'detail': 'Link inválido ou expirado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            validate_password(
                dados['password'],
                user=usuario
            )
        except ValidationError as erro:
            return Response(
                {'password': erro.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        usuario.set_password(dados['password'])
        usuario.save(update_fields=['password'])

        return Response({
            'detail': 'Senha alterada com sucesso.'
        })
