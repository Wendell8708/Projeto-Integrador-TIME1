from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from alertas.serializers import AlertSerializer
from iot.serializers import ReadingSerializer, ShockEventSerializer
from iot.views import ReadingFilter
from usuarios.permissions import PodeAlterarModelo

from .models import Shipment, ShipmentItem
from .serializers import ShipmentItemSerializer, ShipmentSerializer
from .services import shipment_summary


class ShipmentViewSet(viewsets.ModelViewSet):
    queryset = (
        Shipment.objects
        .select_related('origin', 'destination', 'vehicle', 'device')
        .prefetch_related('items__fruit')
    )
    serializer_class = ShipmentSerializer
    filterset_fields = ['status', 'vehicle', 'device', 'origin', 'destination']
    ordering_fields = ['started_at', 'created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # --- Ciclo de vida --------------------------------------------------

    @action(detail=True, methods=['post'], permission_classes=[PodeAlterarModelo])
    def start(self, request, pk=None):
        """planned -> active. A partir daqui a placa pode enviar leituras para esta viagem."""
        viagem = self.get_object()
        if viagem.status != 'planned':
            return Response({'detail': 'Só é possível iniciar uma viagem planejada.'}, status=status.HTTP_400_BAD_REQUEST)
        if not viagem.items.exists():
            return Response({'detail': 'Cadastre ao menos uma fruta na carga antes de iniciar.'},
                            status=status.HTTP_400_BAD_REQUEST)

        viagem.status = 'active'
        viagem.started_at = timezone.now()  # vira o inicio REAL da viagem
        try:
            with transaction.atomic():
                viagem.save(update_fields=['status', 'started_at', 'updated_at'])
        except IntegrityError:
            # Indice unico parcial: o dispositivo ja esta em outra viagem ativa.
            return Response({'detail': 'Este dispositivo já está em outra viagem em andamento.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(viagem).data)

    @action(detail=True, methods=['post'], permission_classes=[PodeAlterarModelo])
    def finish(self, request, pk=None):
        """active -> completed, registrando o fim real."""
        viagem = self.get_object()
        if viagem.status != 'active':
            return Response({'detail': 'Só é possível encerrar uma viagem em andamento.'},
                            status=status.HTTP_400_BAD_REQUEST)
        viagem.status = 'completed'
        viagem.ended_at = timezone.now()
        viagem.save(update_fields=['status', 'ended_at', 'updated_at'])
        return Response(self.get_serializer(viagem).data)

    # --- Dados para o dashboard -----------------------------------------

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Indicadores do dashboard: ultima leitura, metricas, dispositivo, limites e alertas abertos."""
        return Response(shipment_summary(self.get_object()))

    @action(detail=True, methods=['get'])
    def readings(self, request, pk=None):
        """Historico de temperatura e umidade (paginado; filtros ?start=, ?end=, ?since=)."""
        viagem = self.get_object()
        leituras = ReadingFilter(request.query_params, queryset=viagem.readings.all()).qs
        pagina = self.paginate_queryset(leituras)
        return self.get_paginated_response(ReadingSerializer(pagina, many=True).data)

    @action(detail=True, methods=['get'])
    def shocks(self, request, pk=None):
        """Eventos de impacto da viagem (paginado)."""
        pagina = self.paginate_queryset(self.get_object().shock_events.all())
        return self.get_paginated_response(ShockEventSerializer(pagina, many=True).data)

    @action(detail=True, methods=['get'])
    def alerts(self, request, pk=None):
        """Alertas da viagem."""
        alertas = self.get_object().alerts.select_related('acknowledged_by')
        return Response(AlertSerializer(alertas, many=True).data)


class ShipmentItemViewSet(viewsets.ModelViewSet):
    queryset = ShipmentItem.objects.select_related('fruit', 'shipment')
    serializer_class = ShipmentItemSerializer
    filterset_fields = ['shipment', 'fruit']
