from django_filters import rest_framework as filters
from rest_framework import viewsets

from .models import Device, Reading
from .serializers import DeviceSerializer, ReadingSerializer


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    filterset_fields = ['situacao']


class ReadingFilter(filters.FilterSet):
    # /leituras/?device=1&shipment=3&inicio=2026-10-01T00:00:00Z&fim=2026-10-02T00:00:00Z
    inicio = filters.IsoDateTimeFilter(field_name='recorded_at', lookup_expr='gte')
    fim = filters.IsoDateTimeFilter(field_name='recorded_at', lookup_expr='lte')

    class Meta:
        model = Reading
        fields = ['device', 'shipment']


class ReadingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Leituras do sensor: so consulta. Uma medicao historica nao se edita nem se
    apaga pela API, e quem grava e a placa (rota de telemetria).
    """

    queryset = Reading.objects.select_related('device')
    serializer_class = ReadingSerializer
    filterset_class = ReadingFilter
    ordering_fields = ['recorded_at']
