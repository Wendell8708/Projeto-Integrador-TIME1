from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios.permissions import PodeAlterarModelo

from .models import Alerta
from .serializers import AlertaSerializer


class AlertaViewSet(viewsets.ReadOnlyModelViewSet):
    """Alertas gerados pelo sistema. So leitura, mais a acao de reconhecer."""

    queryset = Alerta.objects.select_related('transporte', 'reconhecido_por')
    serializer_class = AlertaSerializer
    filterset_fields = ['transporte', 'tipo', 'severidade', 'status']

    @action(detail=True, methods=['post'], permission_classes=[PodeAlterarModelo])
    def reconhecer(self, request, pk=None):
        """Marca o alerta como "visto" por quem esta logado (aberto -> reconhecido)."""
        alerta = self.get_object()
        if alerta.status != 'aberto':
            return Response({'detail': 'Só é possível reconhecer um alerta aberto.'}, status=status.HTTP_400_BAD_REQUEST)

        alerta.status = 'reconhecido'
        alerta.reconhecido_por = request.user
        alerta.reconhecido_em = timezone.now()
        alerta.save(update_fields=['status', 'reconhecido_por', 'reconhecido_em'])
        return Response(self.get_serializer(alerta).data)
