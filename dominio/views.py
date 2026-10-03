from rest_framework import viewsets

from .models import ConfiguracaoLimite, Fruta, Local, Veiculo
from .serializers import (
    ConfiguracaoLimiteSerializer, FrutaSerializer, LocalSerializer, VeiculoSerializer,
)

# As views sao "finas": o ModelViewSet ja entrega listar, criar, ver, editar e
# apagar. A permissao vem do padrao do projeto (grupos + permissoes do Django).


class LocalViewSet(viewsets.ModelViewSet):
    queryset = Local.objects.all()
    serializer_class = LocalSerializer
    filterset_fields = ['tipo_local', 'situacao']
    search_fields = ['nome']


class VeiculoViewSet(viewsets.ModelViewSet):
    queryset = Veiculo.objects.all()
    serializer_class = VeiculoSerializer
    filterset_fields = ['situacao']


class FrutaViewSet(viewsets.ModelViewSet):
    queryset = Fruta.objects.all()
    serializer_class = FrutaSerializer
    filterset_fields = ['situacao']


class ConfiguracaoLimiteViewSet(viewsets.ModelViewSet):
    queryset = ConfiguracaoLimite.objects.select_related('fruta')
    serializer_class = ConfiguracaoLimiteSerializer
    filterset_fields = ['fruta', 'situacao']
