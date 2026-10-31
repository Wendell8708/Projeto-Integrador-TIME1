from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

# Nome do grupo no Django -> "role" que o front recebe (JSON 1 do plano).
ROLES = {'Administrador': 'admin', 'Operador': 'operator', 'Visualizador': 'viewer'}


def role_do_usuario(usuario):
    if usuario.is_superuser:
        return 'admin'
    for grupo in usuario.groups.values_list('name', flat=True):
        if grupo in ROLES:
            return ROLES[grupo]
    return None


def dados_basicos(usuario):
    return {
        'id': usuario.id,
        'name': usuario.get_full_name() or usuario.username,
        'email': usuario.email,
        'role': role_do_usuario(usuario),
    }


class LoginSerializer(serializers.Serializer):
    """Login por e-mail e senha. Devolve os tokens e o usuario (JSON 1 do plano)."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, dados):
        erro = serializers.ValidationError('E-mail ou senha inválidos.', code='authorization')
        encontrados = list(User.objects.filter(email__iexact=dados['email'])[:2])
        if len(encontrados) != 1:
            raise erro  # nao existe, ou o e-mail esta repetido (nao da para saber qual conta)
        usuario = authenticate(username=encontrados[0].username, password=dados['password'])
        if usuario is None or not usuario.is_active:
            raise erro

        refresh = RefreshToken.for_user(usuario)
        return {'access': str(refresh.access_token), 'refresh': str(refresh), 'user': dados_basicos(usuario)}


class MeSerializer(serializers.ModelSerializer):
    """Dados do usuario logado, para o front saber quem e e o que pode fazer."""

    name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'username', 'role', 'is_superuser', 'groups', 'permissions']
        read_only_fields = fields

    def get_name(self, usuario) -> str:
        return usuario.get_full_name() or usuario.username

    def get_role(self, usuario) -> str | None:
        return role_do_usuario(usuario)

    def get_groups(self, usuario) -> list[str]:
        return sorted(usuario.groups.values_list('name', flat=True))

    def get_permissions(self, usuario) -> list[str]:
        # Ex.: ["iot.view_reading", "transporte.add_shipment"]
        return sorted(usuario.get_all_permissions())
