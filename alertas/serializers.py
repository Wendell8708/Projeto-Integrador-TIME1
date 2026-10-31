from rest_framework import serializers

from .models import Alert


class AlertSerializer(serializers.ModelSerializer):
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = Alert
        fields = [
            'id', 'shipment', 'reading', 'shock_event', 'type', 'severity', 'status', 'message',
            'measured_value', 'violated_limit', 'created_at',
            'acknowledged_by', 'acknowledged_by_name', 'acknowledged_at', 'resolved_at',
        ]
        read_only_fields = fields  # alertas sao criados pelo sistema, nunca pela API
