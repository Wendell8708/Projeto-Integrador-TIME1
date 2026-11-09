
from django.db import transaction
from rest_framework import serializers
from .models import (
    Shipment,
    ShipmentItem,
    FinalInspection,
    InspectionPhoto,
)

from .services import IncompatibleCargo, fruit_range_for


class ShipmentItemSerializer(serializers.ModelSerializer):
    fruit_name = serializers.CharField(
        source='fruit.name',
        read_only=True
    )

    class Meta:
        model = ShipmentItem
        fields = [
            'id', 'shipment', 'fruit', 'fruit_name',
            'lot', 'quantity_kg', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, dados):
        viagem = dados.get(
            'shipment',
            getattr(self.instance, 'shipment', None)
        )
        fruta = dados.get(
            'fruit',
            getattr(self.instance, 'fruit', None)
        )

        if viagem.status in ('completed', 'cancelled'):
            raise serializers.ValidationError(
                'Não é possível alterar a carga de uma viagem concluída ou cancelada.'
            )

        frutas = set(
            viagem.items.values_list('fruit_id', flat=True)
        )

        if self.instance is not None:
            frutas.discard(self.instance.fruit_id)

        frutas.add(fruta.id)

        try:
            fruit_range_for(frutas)
        except IncompatibleCargo as erro:
            raise serializers.ValidationError(str(erro))

        return dados


class ShipmentNestedItemSerializer(serializers.ModelSerializer):
    """
    Permite cadastrar frutas dentro da criação de uma viagem.
    O campo shipment é preenchido automaticamente.
    """

    fruit_name = serializers.CharField(
        source='fruit.name',
        read_only=True
    )

    class Meta:
        model = ShipmentItem
        fields = [
            'id', 'shipment', 'fruit', 'fruit_name',
            'lot', 'quantity_kg', 'created_at'
        ]
        read_only_fields = [
            'id', 'shipment', 'fruit_name', 'created_at'
        ]


class ShipmentSerializer(serializers.ModelSerializer):
    items = ShipmentNestedItemSerializer(
        many=True,
        required=False
    )

    class Meta:
        model = Shipment
        fields = [
            'id',
            'origin',
            'destination',
            'vehicle',
            'device',
            'created_by',
            'status',
            'started_at',
            'ended_at',
            'items',
            'created_at',
            'updated_at',
        ]

        read_only_fields = [
            'id',
            'created_by',
            'status',
            'created_at',
            'updated_at',
        ]

    def validate(self, dados):

        def valor(campo):
            return dados.get(
                campo,
                getattr(self.instance, campo, None)
            )

        if valor('origin') == valor('destination'):
            raise serializers.ValidationError(
                'Origem e destino devem ser diferentes.'
            )

        fim = valor('ended_at')
        inicio = valor('started_at')

        if fim is not None and inicio is not None:
            if fim <= inicio:
                raise serializers.ValidationError(
                    'O fim deve ser depois do início.'
                )

        # Os itens só podem ser enviados junto com
        # a criação da viagem.
        if self.instance is not None and 'items' in dados:
            raise serializers.ValidationError({
                'items': 'Para alterar a carga, utilize a rota de itens da viagem.'
            })

        itens = dados.get('items')

        if itens is not None:
            lotes = set()
            frutas = set()

            for item in itens:
                chave = (item['fruit'].pk, item['lot'])

                if chave in lotes:
                    raise serializers.ValidationError({
                        'items': 'Não repita a mesma fruta e lote na viagem.'
                    })

                lotes.add(chave)
                frutas.add(item['fruit'].pk)

            if frutas:
                try:
                    fruit_range_for(frutas)
                except IncompatibleCargo as erro:
                    raise serializers.ValidationError({
                        'items': str(erro)
                    })

        return dados

    @transaction.atomic
    def create(self, validated_data):
        """
        Cria a viagem e os itens na mesma transação.
        Se alguma operação falhar, tudo é desfeito.
        """

        itens = validated_data.pop('items', [])

        viagem = Shipment.objects.create(**validated_data)

        for item in itens:
            ShipmentItem.objects.create(
                shipment=viagem,
                **item
            )

        return viagem

# ======================================================
# SERIALIZER DAS FOTOGRAFIAS DA AVALIAÇÃO FINAL
# ======================================================

class InspectionPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = InspectionPhoto

        fields = [
            'id',
            'file_path',
            'created_at',
        ]

        read_only_fields = [
            'id',
            'file_path',
            'created_at',
        ]


# ======================================================
# SERIALIZER DA AVALIAÇÃO FINAL DA VIAGEM
# ======================================================

class FinalInspectionSerializer(serializers.ModelSerializer):

    photos = InspectionPhotoSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = FinalInspection

        fields = [
            'id',
            'shipment',
            'user',
            'condition',
            'notes',
            'photos',
            'created_at',
        ]

        read_only_fields = [
            'id',
            'shipment',
            'user',
            'photos',
            'created_at',
        ]
