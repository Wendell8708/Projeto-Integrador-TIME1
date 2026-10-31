from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios.permissions import PodeAlterarModelo

from .models import Alert
from .serializers import AlertSerializer


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    """Alertas gerados pelo sistema. So leitura, mais as acoes de reconhecer e resolver."""

    queryset = Alert.objects.select_related('shipment', 'acknowledged_by')
    serializer_class = AlertSerializer
    filterset_fields = ['shipment', 'type', 'severity', 'status']

    @action(detail=True, methods=['post'], permission_classes=[PodeAlterarModelo])
    def ack(self, request, pk=None):
        """Marca o alerta como visto por quem esta logado (open -> acknowledged)."""
        alerta = self.get_object()
        if alerta.status != 'open':
            return Response({'detail': 'Só é possível reconhecer um alerta aberto.'}, status=status.HTTP_400_BAD_REQUEST)
        alerta.status = 'acknowledged'
        alerta.acknowledged_by = request.user
        alerta.acknowledged_at = timezone.now()
        alerta.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at'])
        return Response(self.get_serializer(alerta).data)

    @action(detail=True, methods=['post'], permission_classes=[PodeAlterarModelo])
    def resolve(self, request, pk=None):
        """Encerra o alerta a mao. Necessario para impacto, que nao 'volta ao normal' sozinho."""
        alerta = self.get_object()
        if alerta.status == 'resolved':
            return Response({'detail': 'Este alerta já está resolvido.'}, status=status.HTTP_400_BAD_REQUEST)
        alerta.status = 'resolved'
        alerta.resolved_at = timezone.now()
        alerta.save(update_fields=['status', 'resolved_at'])
        return Response(self.get_serializer(alerta).data)
