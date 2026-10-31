from rest_framework import serializers

from .models import Fruit, FruitParameter, Location, Vehicle


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'type', 'address', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'plate', 'model', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class FruitLimitsSerializer(serializers.ModelSerializer):
    """Os limites ATIVOS de uma fruta, no formato do JSON 2 do plano ("limits")."""

    class Meta:
        model = FruitParameter
        fields = [
            'temperature_min_c', 'temperature_max_c', 'temperature_critical_margin_c',
            'humidity_min_pct', 'humidity_max_pct', 'humidity_critical_margin_pct',
            'impact_max_g',
        ]


class FruitSerializer(serializers.ModelSerializer):
    limits = serializers.SerializerMethodField()

    class Meta:
        model = Fruit
        fields = ['id', 'name', 'description', 'is_active', 'limits', 'created_at']
        read_only_fields = ['id', 'limits', 'created_at']

    def get_limits(self, fruta) -> dict | None:
        ativo = next((p for p in fruta.parameters.all() if p.is_active), None)
        return None if ativo is None else FruitLimitsSerializer(ativo).data


class FruitParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = FruitParameter
        fields = [
            'id', 'fruit',
            'temperature_min_c', 'temperature_max_c', 'temperature_critical_margin_c',
            'humidity_min_pct', 'humidity_max_pct', 'humidity_critical_margin_pct',
            'impact_max_g', 'source', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, dados):
        # Em PATCH, campos ausentes vem da instancia atual.
        def valor(campo):
            return dados.get(campo, getattr(self.instance, campo, None))

        if valor('temperature_min_c') >= valor('temperature_max_c'):
            raise serializers.ValidationError('A temperatura mínima deve ser menor que a máxima.')
        if valor('humidity_min_pct') >= valor('humidity_max_pct'):
            raise serializers.ValidationError('A umidade mínima deve ser menor que a máxima.')

        # Mensagem clara em vez de erro 500 do banco (constraint "um ativo por fruta").
        if valor('is_active'):
            outros_ativos = FruitParameter.objects.filter(fruit=valor('fruit'), is_active=True)
            if self.instance is not None:
                outros_ativos = outros_ativos.exclude(pk=self.instance.pk)
            if outros_ativos.exists():
                raise serializers.ValidationError(
                    'Esta fruta já tem parâmetros ativos. Desative os anteriores primeiro.'
                )
        return dados
