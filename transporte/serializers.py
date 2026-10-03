from rest_framework import serializers

from .models import Carga, Transporte
from .services import CargaIncompativel, faixa_ideal_de_frutas


class CargaSerializer(serializers.ModelSerializer):
    fruta_nome = serializers.CharField(source='fruta.nome', read_only=True)

    class Meta:
        model = Carga
        fields = ['id', 'transporte', 'fruta', 'fruta_nome', 'lote', 'quantidade_kg', 'data_cadastro']
        read_only_fields = ['id', 'data_cadastro']

    def validate(self, dados):
        transporte = dados.get('transporte', getattr(self.instance, 'transporte', None))
        fruta = dados.get('fruta', getattr(self.instance, 'fruta', None))

        if transporte.status in ('concluido', 'cancelado'):
            raise serializers.ValidationError('Não é possível alterar a carga de um transporte concluído ou cancelado.')

        # Carga mista: a nova fruta precisa ter faixa em comum com as que ja estao no caminhao.
        frutas = set(transporte.cargas.values_list('fruta_id', flat=True))
        if self.instance is not None:
            frutas.discard(self.instance.fruta_id)
        frutas.add(fruta.id)
        try:
            faixa_ideal_de_frutas(frutas)
        except CargaIncompativel as erro:
            raise serializers.ValidationError(str(erro))
        return dados


class TransporteSerializer(serializers.ModelSerializer):
    cargas = CargaSerializer(many=True, read_only=True)

    class Meta:
        model = Transporte
        fields = [
            'id', 'origem', 'destino', 'veiculo', 'dispositivo',
            'data_hora_inicio', 'data_hora_fim', 'status', 'data_cadastro', 'cargas',
        ]
        # O status so muda pelas acoes /iniciar/ e /concluir/ (regras de transicao).
        read_only_fields = ['id', 'status', 'data_cadastro']

    def validate(self, dados):
        def valor(campo):
            return dados.get(campo, getattr(self.instance, campo, None))

        if valor('origem') == valor('destino'):
            raise serializers.ValidationError('Origem e destino devem ser diferentes.')
        fim = valor('data_hora_fim')
        if fim is not None and fim <= valor('data_hora_inicio'):
            raise serializers.ValidationError('O fim deve ser depois do início.')
        return dados
