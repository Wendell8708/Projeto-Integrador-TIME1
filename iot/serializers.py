from django.conf import settings
from rest_framework import serializers

from .models import Device, Reading, ShockEvent


class DeviceSerializer(serializers.ModelSerializer):
    online = serializers.BooleanField(read_only=True)

    class Meta:
        model = Device
        fields = ['id', 'uid', 'name', 'is_active', 'online', 'last_seen_at',
                  'last_connection_type', 'wifi_ssid', 'created_at']
        read_only_fields = ['id', 'online', 'last_seen_at', 'last_connection_type', 'wifi_ssid', 'created_at']


class ReadingSerializer(serializers.ModelSerializer):
    """So consulta: quem grava leituras e a placa, pela rota de telemetria."""

    class Meta:
        model = Reading
        fields = ['id', 'shipment', 'device', 'sequence', 'recorded_at', 'received_at',
                  'temperature_c', 'humidity_pct', 'impact_peak_g', 'network']
        read_only_fields = fields


class ShockEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShockEvent
        fields = ['id', 'shipment', 'device', 'event_id', 'recorded_at', 'received_at', 'impact_peak_g']
        read_only_fields = fields


# --- Entrada da placa (contrato do plano, secao 3.2) -------------------------

class TelemetryReadingInput(serializers.Serializer):
    sequence = serializers.IntegerField(min_value=0)
    recorded_at = serializers.DateTimeField()
    temperature_c = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=-40, max_value=80)
    humidity_pct = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)
    impact_peak_g = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0,
                                             required=False, allow_null=True)


class TelemetryShockInput(serializers.Serializer):
    event_id = serializers.CharField(max_length=64)
    recorded_at = serializers.DateTimeField()
    impact_peak_g = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0)


class TelemetryBatchInput(serializers.Serializer):
    device_uid = serializers.CharField(max_length=100)
    shipment_id = serializers.IntegerField()
    network = serializers.ChoiceField(choices=Device.CONNECTION_CHOICES, required=False, allow_blank=True, default='')
    readings = TelemetryReadingInput(many=True, required=False, default=list)
    shocks = TelemetryShockInput(many=True, required=False, default=list)

    def validate(self, dados):
        total = len(dados['readings']) + len(dados['shocks'])
        if total == 0:
            raise serializers.ValidationError('O lote está vazio.')
        if total > settings.IOT_MAX_BATCH_ITEMS:
            raise serializers.ValidationError(
                f'Lote com {total} itens: o máximo é {settings.IOT_MAX_BATCH_ITEMS}. Divida em lotes menores.'
            )
        return dados


class TelemetryBatchResult(serializers.Serializer):
    """So para a documentacao (Swagger): a resposta do lote."""

    accepted_reading_sequences = serializers.ListField(child=serializers.IntegerField())
    accepted_shock_ids = serializers.ListField(child=serializers.CharField())


class HeartbeatInput(serializers.Serializer):
    network = serializers.ChoiceField(choices=Device.CONNECTION_CHOICES, required=False, allow_blank=True, default='')
    wifi_ssid = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
