from django.utils import timezone
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from transporte.models import Shipment
from transporte.services import fruit_range

from .authentication import DeviceKeyAuthentication, DeviceRateThrottle, IsDevice, registrar_contato
from .models import Device, Reading
from .serializers import (
    DeviceSerializer, HeartbeatInput, ReadingSerializer, TelemetryBatchInput, TelemetryBatchResult,
)
from .services import process_batch


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    filterset_fields = ['is_active']


class ReadingFilter(filters.FilterSet):
    # /readings?shipment=3&start=2026-10-01T00:00:00Z&end=2026-10-02T00:00:00Z
    start = filters.IsoDateTimeFilter(field_name='recorded_at', lookup_expr='gte')
    end = filters.IsoDateTimeFilter(field_name='recorded_at', lookup_expr='lte')
    # So o que chegou depois de um instante: o front busca so as novas a cada atualizacao.
    since = filters.IsoDateTimeFilter(field_name='recorded_at', lookup_expr='gt')

    class Meta:
        model = Reading
        fields = ['device', 'shipment']


class ReadingViewSet(viewsets.ReadOnlyModelViewSet):
    """Leituras: so consulta. Medicao historica nao se edita nem se apaga, e quem grava e a placa."""

    queryset = Reading.objects.select_related('device')
    serializer_class = ReadingSerializer
    filterset_class = ReadingFilter
    ordering_fields = ['recorded_at']


# --- Rotas da PLACA (autenticadas pela chave do dispositivo, nao por JWT) -----

class DeviceAPIView(APIView):
    authentication_classes = [DeviceKeyAuthentication]
    permission_classes = [IsDevice]
    throttle_classes = [DeviceRateThrottle]


class TelemetryBatchView(DeviceAPIView):
    """
    POST /api/v1/iot/telemetry/batch

    Recebe leituras e impactos em lote e devolve so os identificadores gravados.
    A placa apaga da fila local apenas o que vier na resposta.
    """

    @extend_schema(request=TelemetryBatchInput, responses=TelemetryBatchResult)
    def post(self, request):
        entrada = TelemetryBatchInput(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data
        dispositivo = request.auth

        if dados['device_uid'] != dispositivo.uid:
            return Response({'detail': 'device_uid não corresponde à chave enviada.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # A viagem tem que ser DESTA placa. Aceita viagem ativa ou ja concluida
        # (dado que ficou na fila offline e chegou depois do fim da viagem).
        viagem = Shipment.objects.filter(
            pk=dados['shipment_id'], device=dispositivo, status__in=['active', 'completed'],
        ).first()
        if viagem is None:
            return Response({'detail': 'Viagem inexistente, de outro dispositivo ou ainda não iniciada.'},
                            status=status.HTTP_400_BAD_REQUEST)

        registrar_contato(dispositivo, rede=dados['network'])
        resultado = process_batch(
            device=dispositivo, shipment=viagem, network=dados['network'],
            readings=dados['readings'], shocks=dados['shocks'],
        )
        return Response(resultado)


class HeartbeatView(DeviceAPIView):
    """POST /api/v1/iot/heartbeat -- 'estou viva': atualiza a ultima comunicacao da placa."""

    @extend_schema(request=HeartbeatInput, responses=DeviceSerializer)
    def post(self, request):
        entrada = HeartbeatInput(data=request.data)
        entrada.is_valid(raise_exception=True)
        registrar_contato(request.auth, rede=entrada.validated_data['network'],
                          ssid=entrada.validated_data['wifi_ssid'])
        request.auth.refresh_from_db()
        return Response(DeviceSerializer(request.auth).data)


class DeviceConfigView(DeviceAPIView):
    """
    GET /api/v1/iot/config -- a placa pergunta "qual e minha viagem ativa e meus limites?".

    Responde shipment_id = null quando a placa nao esta em nenhuma viagem ativa.
    """

    @extend_schema(responses=inline_serializer('DeviceConfig', {
        'device_uid': serializers.CharField(),
        'shipment_id': serializers.IntegerField(allow_null=True),
        'limits': serializers.DictField(allow_null=True),
        'server_time': serializers.DateTimeField(),
    }))
    def get(self, request):
        dispositivo = request.auth
        registrar_contato(dispositivo)
        viagem = Shipment.objects.filter(device=dispositivo, status='active').first()
        limites = None
        if viagem is not None:
            faixa = fruit_range(viagem)
            limites = None if faixa is None else faixa.as_dict()
        return Response({
            'device_uid': dispositivo.uid,
            'shipment_id': None if viagem is None else viagem.id,
            'limits': limites,
            'server_time': timezone.now(),  # a placa pode acertar o relogio por aqui se nao tiver NTP
        })
