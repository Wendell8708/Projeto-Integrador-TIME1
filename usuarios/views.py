
import logging


from django.contrib.auth import get_user_model
from django.db.models import Q
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from drf_spectacular.utils import extend_schema, inline_serializer

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from django.conf import settings

from . import dois_fatores
from .acesso import eh_plataforma
from .convite import enviar_recuperacao
from .gestao import SoPlataforma, UsuarioGestaoSerializer, CriarUsuarioSerializer, criar_usuario, listar_usuarios
from .permissions import PodeMontarViagem
from .serializers import LoginSerializer, MeSerializer, emitir_tokens


logger = logging.getLogger(__name__)
User = get_user_model()


def eh_conta_demonstracao(usuario):
    """
    Conta listada em MFA_CONTAS_DEMONSTRACAO (ex.: a conta compartilhada da
    apresentacao). Nunca vale para a plataforma: admin sempre passa pelo 2FA.
    """
    email = (usuario.email or '').lower()
    return bool(email) and email in settings.MFA_CONTAS_DEMONSTRACAO and not eh_plataforma(usuario)


class LoginView(APIView):
    """
    Etapa 1 do login: e-mail e senha.

    Com a senha certa, NAO devolve o token de acesso. Devolve um token
    temporario (mfa_token) que so serve para a etapa 2:
      - mfa_setup_required=true  -> primeiro acesso: cadastrar o autenticador
        (POST /auth/2fa/setup e depois /auth/2fa/activate);
      - mfa_setup_required=false -> informar o codigo (POST /auth/2fa/verify).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    @extend_schema(
        request=LoginSerializer,
        responses=inline_serializer(
            'LoginResponse',
            {
                'mfa_required': serializers.BooleanField(),
                'mfa_setup_required': serializers.BooleanField(),
                'mfa_token': serializers.CharField(),
                'expires_in': serializers.IntegerField(),
            }
        )
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.validated_data['usuario']
        if eh_conta_demonstracao(usuario):
            # Excecao configurada no ambiente (MFA_CONTAS_DEMONSTRACAO): entra so com a senha.
            dois_fatores.registrar_dispensa(request, usuario)
            return Response(emitir_tokens(usuario))
        return Response({
            'mfa_required': True,
            'mfa_setup_required': not dois_fatores.tem_2fa_ativo(usuario),
            'mfa_token': dois_fatores.criar_token_temporario(usuario),
            'expires_in': settings.MFA_TOKEN_MAX_AGE,
        })


# ---------------------------------------------------------------------------
# Etapa 2 do login: segundo fator (TOTP)
# ---------------------------------------------------------------------------

class TokenTemporarioInput(serializers.Serializer):
    mfa_token = serializers.CharField()


class CodigoInput(TokenTemporarioInput):
    code = serializers.CharField(required=False, allow_blank=True)
    recovery_code = serializers.CharField(required=False, allow_blank=True)


class Etapa2FAView(APIView):
    """Base das rotas /auth/2fa/*: sem JWT (ainda nao ha), com limite de tentativas."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'mfa'

    def usuario_ou_erro(self, token):
        usuario = dois_fatores.usuario_do_token(token, User)
        if usuario is None:
            return None, Response(
                {'detail': 'Sessão de login expirada. Entre com e-mail e senha de novo.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return usuario, None


class SetupView(Etapa2FAView):
    """
    POST /auth/2fa/setup {mfa_token}
    Primeiro acesso: gera o segredo e devolve o QR Code para o aplicativo autenticador.
    """

    @extend_schema(request=TokenTemporarioInput)
    def post(self, request):
        entrada = TokenTemporarioInput(data=request.data)
        entrada.is_valid(raise_exception=True)
        usuario, erro = self.usuario_ou_erro(entrada.validated_data['mfa_token'])
        if erro:
            return erro
        if dois_fatores.tem_2fa_ativo(usuario):
            # Impede que alguem com a senha "recadastre" o autenticador de outra pessoa.
            dois_fatores.registrar_recusa(request, usuario, 'tentativa de recadastro com 2FA ativo')
            return Response({'detail': 'O autenticador já está configurado nesta conta.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(dois_fatores.iniciar_cadastro(usuario))


class ActivateView(Etapa2FAView):
    """
    POST /auth/2fa/activate {mfa_token, code}
    Confirma o cadastro com o primeiro codigo do aplicativo. Devolve os tokens
    e os 10 codigos de recuperacao (mostrados UMA vez).
    """

    @extend_schema(request=CodigoInput)
    def post(self, request):
        entrada = CodigoInput(data=request.data)
        entrada.is_valid(raise_exception=True)
        usuario, erro = self.usuario_ou_erro(entrada.validated_data['mfa_token'])
        if erro:
            return erro
        codigos = dois_fatores.ativar(usuario, entrada.validated_data.get('code'))
        if codigos is None:
            dois_fatores.registrar_recusa(request, usuario, 'codigo invalido na ativacao')
            return Response({'detail': 'Código inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({**emitir_tokens(usuario), 'recovery_codes': codigos})


class VerifyView(Etapa2FAView):
    """
    POST /auth/2fa/verify {mfa_token, code} ou {mfa_token, recovery_code}
    Acessos seguintes: confere o codigo e, se valido, devolve os tokens.
    """

    @extend_schema(request=CodigoInput)
    def post(self, request):
        entrada = CodigoInput(data=request.data)
        entrada.is_valid(raise_exception=True)
        usuario, erro = self.usuario_ou_erro(entrada.validated_data['mfa_token'])
        if erro:
            return erro
        if not dois_fatores.tem_2fa_ativo(usuario):
            return Response({'detail': 'Configure o autenticador primeiro (/auth/2fa/setup).'},
                            status=status.HTTP_400_BAD_REQUEST)

        recuperacao = entrada.validated_data.get('recovery_code')
        if recuperacao:
            if dois_fatores.usar_codigo_recuperacao(usuario, recuperacao):
                return Response(emitir_tokens(usuario))
            dois_fatores.registrar_recusa(request, usuario, 'codigo de recuperacao invalido ou ja usado')
            return Response({'detail': 'Código de recuperação inválido ou já utilizado.'},
                            status=status.HTTP_400_BAD_REQUEST)

        resultado = dois_fatores.verificar_codigo(usuario, entrada.validated_data.get('code'))
        if resultado == 'ok':
            return Response(emitir_tokens(usuario))
        if resultado == 'reutilizado':
            dois_fatores.registrar_recusa(request, usuario, 'codigo ja utilizado')
            return Response({'detail': 'Este código já foi utilizado. Aguarde o próximo.'},
                            status=status.HTTP_400_BAD_REQUEST)
        dois_fatores.registrar_recusa(request, usuario, 'codigo invalido ou vencido')
        return Response({'detail': 'Código inválido ou vencido.'}, status=status.HTTP_400_BAD_REQUEST)


class RecoveryCodesView(APIView):
    """
    POST /auth/2fa/recovery-codes {code}   (usuario ja logado, com JWT)
    Gera codigos de recuperacao novos (os antigos deixam de valer). Pede um
    codigo atual do aplicativo: quem roubou so o token nao consegue.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'mfa'

    @extend_schema(request=inline_serializer('RecoveryCodesInput', {'code': serializers.CharField()}))
    def post(self, request):
        if dois_fatores.verificar_codigo(request.user, request.data.get('code')) != 'ok':
            dois_fatores.registrar_recusa(request, request.user, 'codigo invalido ao gerar codigos de recuperacao')
            return Response({'detail': 'Código inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'recovery_codes': dois_fatores.gerar_codigos_recuperacao(request.user)})


# ---------------------------------------------------------------------------
# Lista de compradores e motoristas (formulario de viagem do vendedor)
# ---------------------------------------------------------------------------

GRUPO_DO_PAPEL = {'buyer': 'Comprador', 'driver': 'Motorista'}
LIMITE_LISTA = 50


class UsuarioResumoSerializer(serializers.Serializer):
    """So id e nome: o minimo para o select do formulario (LGPD: sem e-mail)."""

    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()

    def get_name(self, usuario) -> str:
        return usuario.get_full_name() or usuario.username


class UsersView(APIView):
    """
    GET  /auth/users?role=buyer|driver[&search=texto]
         Para o vendedor escolher o comprador e o motorista ao montar a viagem.
         So quem pode criar viagem acessa; devolve so id e nome (sem e-mail).
    GET  /auth/users            (sem role) lista completa: so a plataforma (tela "Usuarios").
    POST /auth/users            cria usuario e manda o convite: so a plataforma (ver gestao.py).
    """

    def get_permissions(self):
        if self.request.method == 'POST':
            return [SoPlataforma()]
        return [PodeMontarViagem()]

    @extend_schema(responses=UsuarioResumoSerializer(many=True))
    def get(self, request):
        papel = request.query_params.get('role', '')
        if not papel and eh_plataforma(request.user):
            return Response(UsuarioGestaoSerializer(listar_usuarios(), many=True).data)
        if papel not in GRUPO_DO_PAPEL:
            return Response({'detail': 'Informe role=buyer ou role=driver.'}, status=status.HTTP_400_BAD_REQUEST)

        usuarios = User.objects.filter(is_active=True, groups__name=GRUPO_DO_PAPEL[papel])
        busca = request.query_params.get('search', '').strip()[:100]
        if busca:
            usuarios = usuarios.filter(
                Q(first_name__icontains=busca) | Q(last_name__icontains=busca) | Q(username__icontains=busca)
            )
        usuarios = usuarios.distinct().order_by('first_name', 'last_name', 'username')[:LIMITE_LISTA]
        return Response(UsuarioResumoSerializer(usuarios, many=True).data)

    @extend_schema(request=CriarUsuarioSerializer)
    def post(self, request):
        return criar_usuario(request)


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

        usuarios = User.objects.filter(email__iexact=email, is_active=True)

        # Vale tambem para quem foi convidado e ainda nao definiu a senha
        # (conta sem senha utilizavel): o convite vence em 3 dias e a pessoa
        # pode pedir um link novo por aqui.
        for usuario in usuarios:
            enviar_recuperacao(usuario)

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
