from django_filters import rest_framework as filters
from rest_framework import mixins, viewsets

from .models import Dispositivo, Leitura
from .serializers import DispositivoSerializer, LeituraSerializer


class DispositivoViewSet(viewsets.ModelViewSet):
    queryset = Dispositivo.objects.all()
    serializer_class = DispositivoSerializer
    filterset_fields = ['situacao']


class LeituraFilter(filters.FilterSet):
    # /leituras/?dispositivo=1&inicio=2026-10-01T00:00:00Z&fim=2026-10-02T00:00:00Z
    inicio = filters.IsoDateTimeFilter(field_name='medido_em', lookup_expr='gte')
    fim = filters.IsoDateTimeFilter(field_name='medido_em', lookup_expr='lte')

    class Meta:
        model = Leitura
        fields = ['dispositivo']


class LeituraViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Leituras do sensor. So listar, ver e criar: uma medicao historica nao deve
    ser editada nem apagada pela API.
    """

    queryset = Leitura.objects.select_related('dispositivo')
    serializer_class = LeituraSerializer
    filterset_class = LeituraFilter
    ordering_fields = ['medido_em']
