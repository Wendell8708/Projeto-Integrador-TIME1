from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from alertas.serializers import AlertSerializer
from iot.serializers import ReadingSerializer
from iot.views import ReadingFilter
from usuarios.permissions import PodeAlterarModelo

from .models import Carga, Shipment
from .serializers import CargaSerializer, ShipmentSerializer
from .services import resumo_do_transporte


class ShipmentViewSet(viewsets.ModelViewSet):
    queryset = (
        Shipment.objects
        .select_related('origem', 'destino', 'veiculo', 'dispositivo')
        .prefetch_related('cargas__fruta')
    )
    serializer_class = ShipmentSerializer
    filterset_fields = ['status', 'veiculo', 'dispositivo', 'origem', 'destino']
    ordering_fields = ['data_hora_inicio', 'data_cadastro']

    # --- Ciclo de vida --------------------------------------------------

    @action(detail=True, methods=['post'], permission_classes=[PodeAlterarModelo])
    def iniciar(self, request, pk=None):
        """planejado -> em_andamento. A partir daqui as leituras do dispositivo contam para este transporte."""
        transporte = self.get_object()
        if transporte.status != 'planejado':
            return Response({'detail': 'Só é possível iniciar um transporte planejado.'}, status=status.HTTP_400_BAD_REQUEST)
        if not transporte.cargas.exists():
            return Response({'detail': 'Cadastre ao menos uma carga antes de iniciar.'}, status=status.HTTP_400_BAD_REQUEST)

        # Um dispositivo so pode estar em UMA viagem por vez; senao nao sabemos a quem a leitura pertence.
        ocupado = Shipment.objects.filter(dispositivo=transporte.dispositivo, status='em_andamento').exists()
        if ocupado:
            return Response({'detail': 'Este dispositivo já está em outro transporte em andamento.'}, status=status.HTTP_400_BAD_REQUEST)

        transporte.status = 'em_andamento'
        transporte.data_hora_inicio = timezone.now()  # vira o inicio REAL da viagem
        transporte.save(update_fields=['status', 'data_hora_inicio'])
        return Response(self.get_serializer(transporte).data)

    @action(detail=True, methods=['post'], permission_classes=[PodeAlterarModelo])
    def concluir(self, request, pk=None):
        """em_andamento -> concluido, registrando o fim real."""
        transporte = self.get_object()
        if transporte.status != 'em_andamento':
            return Response({'detail': 'Só é possível concluir um transporte em andamento.'}, status=status.HTTP_400_BAD_REQUEST)

        transporte.status = 'concluido'
        transporte.data_hora_fim = timezone.now()
        transporte.save(update_fields=['status', 'data_hora_fim'])
        return Response(self.get_serializer(transporte).data)

    # --- Dados para o dashboard -----------------------------------------

    @action(detail=True, methods=['get'])
    def leituras(self, request, pk=None):
        """Historico de temperatura e umidade durante o transporte (paginado e filtravel por inicio/fim)."""
        transporte = self.get_object()
        leituras = ReadingFilter(request.query_params, queryset=transporte.readings.select_related('device')).qs
        pagina = self.paginate_queryset(leituras)
        serializer = ReadingSerializer(pagina, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'])
    def resumo(self, request, pk=None):
        """Estatisticas, ultima leitura, faixa ideal e status atual (normal/atencao/critico)."""
        return Response(resumo_do_transporte(self.get_object()))

    @action(detail=True, methods=['get'])
    def alertas(self, request, pk=None):
        """Alertas deste transporte."""
        transporte = self.get_object()
        serializer = AlertSerializer(transporte.alertas.select_related('transporte'), many=True)
        return Response(serializer.data)


class CargaViewSet(viewsets.ModelViewSet):
    queryset = Carga.objects.select_related('fruta', 'transporte')
    serializer_class = CargaSerializer
    filterset_fields = ['transporte', 'fruta']
