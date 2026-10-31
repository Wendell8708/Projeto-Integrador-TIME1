from django.db.models import Prefetch
from rest_framework import viewsets

from .models import Fruit, FruitParameter, Location, Vehicle
from .serializers import (
    FruitParameterSerializer, FruitSerializer, LocationSerializer, VehicleSerializer,
)

# As views sao "finas": o ModelViewSet ja entrega listar, criar, ver, editar e
# apagar. A permissao vem do padrao do projeto (grupos + permissoes do Django).


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    filterset_fields = ['type', 'is_active']


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filterset_fields = ['is_active']


class FruitViewSet(viewsets.ModelViewSet):
    # Busca os parametros junto (1 consulta a mais no total, nao 1 por fruta).
    queryset = Fruit.objects.prefetch_related(Prefetch('parameters', queryset=FruitParameter.objects.all()))
    serializer_class = FruitSerializer
    filterset_fields = ['is_active']


class FruitParameterViewSet(viewsets.ModelViewSet):
    queryset = FruitParameter.objects.select_related('fruit')
    serializer_class = FruitParameterSerializer
    filterset_fields = ['fruit', 'is_active']
