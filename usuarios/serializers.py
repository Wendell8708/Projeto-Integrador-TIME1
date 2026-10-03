from django.contrib.auth.models import User
from rest_framework import serializers


class UsuarioLogadoSerializer(serializers.ModelSerializer):
    """Dados do usuario logado, para o React saber quem e e o que pode fazer."""

    grupos = serializers.SerializerMethodField()
    permissoes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_superuser', 'grupos', 'permissoes',
        ]
        read_only_fields = fields

    def get_grupos(self, usuario):
        return sorted(usuario.groups.values_list('name', flat=True))

    def get_permissoes(self, usuario):
        # Ex.: ["iot.view_leitura", "transporte.add_transporte"]
        return sorted(usuario.get_all_permissions())
