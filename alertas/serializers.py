from rest_framework import serializers

from .models import Alerta


class AlertaSerializer(serializers.ModelSerializer):
    reconhecido_por_nome = serializers.CharField(source='reconhecido_por.username', read_only=True, default=None)

    class Meta:
        model = Alerta
        fields = [
            'id', 'transporte', 'leitura', 'tipo', 'severidade', 'status',
            'valor_medido', 'limite_violado',
            'criado_em', 'reconhecido_por_nome', 'reconhecido_em', 'resolvido_em',
        ]
        read_only_fields = fields  # alertas sao criados pelo sistema, nunca pela API
