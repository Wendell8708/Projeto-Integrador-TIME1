from rest_framework import serializers

from .models import Device, Reading


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['id', 'nome', 'identificador', 'thingspeak_channel_id', 'situacao', 'data_cadastro']
        read_only_fields = ['id', 'data_cadastro']


class ReadingSerializer(serializers.ModelSerializer):
    """So leitura: quem grava leituras e a placa, pela rota de telemetria (nao um usuario)."""

    class Meta:
        model = Reading
        fields = [
            'id', 'shipment', 'device', 'sequence', 'recorded_at', 'received_at',
            'temperature_c', 'humidity_pct', 'impact_peak_g', 'network',
        ]
        read_only_fields = fields
