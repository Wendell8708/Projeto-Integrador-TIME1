from rest_framework import serializers

from .models import Shipment, ShipmentItem
from .services import IncompatibleCargo, fruit_range_for


class ShipmentItemSerializer(serializers.ModelSerializer):
    fruit_name = serializers.CharField(source='fruit.name', read_only=True)

    class Meta:
        model = ShipmentItem
        fields = ['id', 'shipment', 'fruit', 'fruit_name', 'lot', 'quantity_kg', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate(self, dados):
        viagem = dados.get('shipment', getattr(self.instance, 'shipment', None))
        fruta = dados.get('fruit', getattr(self.instance, 'fruit', None))

        if viagem.status in ('completed', 'cancelled'):
            raise serializers.ValidationError('Não é possível alterar a carga de uma viagem concluída ou cancelada.')

        # Carga mista: a nova fruta precisa ter faixa em comum com as que ja estao no caminhao.
        frutas = set(viagem.items.values_list('fruit_id', flat=True))
        if self.instance is not None:
            frutas.discard(self.instance.fruit_id)
        frutas.add(fruta.id)
        try:
            fruit_range_for(frutas)
        except IncompatibleCargo as erro:
            raise serializers.ValidationError(str(erro))
        return dados


class ShipmentSerializer(serializers.ModelSerializer):
    items = ShipmentItemSerializer(many=True, read_only=True)

    class Meta:
        model = Shipment
        fields = [
            'id', 'origin', 'destination', 'vehicle', 'device', 'created_by',
            'status', 'started_at', 'ended_at', 'items', 'created_at', 'updated_at',
        ]
        # O status so muda pelas acoes /start e /finish (regras de transicao).
        read_only_fields = ['id', 'created_by', 'status', 'created_at', 'updated_at']

    def validate(self, dados):
        def valor(campo):
            return dados.get(campo, getattr(self.instance, campo, None))

        if valor('origin') == valor('destination'):
            raise serializers.ValidationError('Origem e destino devem ser diferentes.')
        fim = valor('ended_at')
        if fim is not None and fim <= valor('started_at'):
            raise serializers.ValidationError('O fim deve ser depois do início.')
        return dados
