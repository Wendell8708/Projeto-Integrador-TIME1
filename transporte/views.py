
from django.db import IntegrityError, transaction
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
    JSONParser,
)

from decouple import config

import cloudinary
import cloudinary.uploader

from alertas.serializers import AlertSerializer
from iot.serializers import ReadingSerializer, ShockEventSerializer
from iot.views import ReadingFilter
from usuarios.permissions import PodeAlterarModelo

from .models import (
    Shipment,
    ShipmentItem,
    FinalInspection,
    InspectionPhoto,
)

from .serializers import (
    ShipmentSerializer,
    ShipmentItemSerializer,
    FinalInspectionSerializer,
)

from .services import (
    shipment_summary,
    fruit_range_for,
    IncompatibleCargo,
)


class ShipmentViewSet(viewsets.ModelViewSet):

    queryset = (
        Shipment.objects
        .select_related(
            'origin',
            'destination',
            'vehicle',
            'device'
        )
        .prefetch_related('items__fruit')
    )

    serializer_class = ShipmentSerializer

    filterset_fields = [
        'status',
        'vehicle',
        'device',
        'origin',
        'destination',
    ]

    ordering_fields = [
        'started_at',
        'created_at',
    ]

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user
        )

    # =====================================================
    # INICIAR VIAGEM
    # =====================================================

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[PodeAlterarModelo]
    )
    def start(self, request, pk=None):

        """
        Inicia a viagem e congela os limites ambientais.
        """

        with transaction.atomic():

            viagem = Shipment.objects.select_for_update().get(
                pk=self.get_object().pk
            )

            if viagem.status != 'planned':
                return Response(
                    {
                        'detail':
                        'Só é possível iniciar uma viagem planejada.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not viagem.items.exists():
                return Response(
                    {
                        'detail':
                        'Cadastre ao menos uma fruta antes de iniciar.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            frutas = viagem.items.values_list(
                'fruit_id',
                flat=True
            )

            try:
                faixa = fruit_range_for(frutas)

            except IncompatibleCargo as erro:
                return Response(
                    {'detail': str(erro)},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if faixa is None:
                return Response(
                    {
                        'detail':
                        'As frutas não possuem limites configurados.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            viagem.limits_snapshot = faixa.as_dict()

            viagem.status = 'active'
            viagem.started_at = timezone.now()

            try:
                viagem.save(
                    update_fields=[
                        'status',
                        'started_at',
                        'limits_snapshot',
                        'updated_at',
                    ]
                )

            except IntegrityError:
                return Response(
                    {
                        'detail':
                        'Este dispositivo já possui outra viagem ativa.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            self.get_serializer(viagem).data,
            status=status.HTTP_200_OK
        )

    # =====================================================
    # FINALIZAR VIAGEM COM AVALIAÇÃO E FOTOS
    # =====================================================

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[PodeAlterarModelo],
        parser_classes=[
            MultiPartParser,
            FormParser,
            JSONParser,
        ]
    )
    def finish(self, request, pk=None):

        """
        Finaliza uma viagem com avaliação, observações
        e fotografias armazenadas no Cloudinary.
        """

        viagem = self.get_object()

        if viagem.status != 'active':
            return Response(
                {
                    'detail':
                    'Só é possível finalizar uma viagem em andamento.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # --------------------------------------------
        # DADOS DA AVALIAÇÃO
        # --------------------------------------------

        condition = request.data.get('condition')
        notes = request.data.get('notes', '')

        condicoes_validas = [
            'good',
            'damaged',
            'critical',
        ]

        if condition not in condicoes_validas:
            return Response(
                {
                    'detail':
                    'Informe uma condição válida: good, damaged ou critical.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(notes, str):
            return Response(
                {
                    'detail':
                    'As observações devem ser um texto.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # --------------------------------------------
        # VALIDAR FOTOGRAFIAS
        # --------------------------------------------

        fotos = request.FILES.getlist('photos')

        if len(fotos) > 10:
            return Response(
                {
                    'detail':
                    'Envie no máximo 10 fotografias.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        for foto in fotos:

            if foto.content_type not in [
                'image/jpeg',
                'image/png',
            ]:
                return Response(
                    {
                        'detail':
                        'São permitidas somente imagens JPEG ou PNG.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if foto.size > 5 * 1024 * 1024:
                return Response(
                    {
                        'detail':
                        'Cada fotografia deve ter no máximo 5 MB.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # --------------------------------------------
        # CONFIGURAR CLOUDINARY
        # --------------------------------------------

        urls_fotos = []
        ids_uploads = []

        if fotos:

            cloud_name = config(
                'CLOUDINARY_CLOUD_NAME',
                default=''
            )

            api_key = config(
                'CLOUDINARY_API_KEY',
                default=''
            )

            api_secret = config(
                'CLOUDINARY_API_SECRET',
                default=''
            )

            if not all([
                cloud_name,
                api_key,
                api_secret,
            ]):
                return Response(
                    {
                        'detail':
                        'Cloudinary não está configurado.'
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )

            try:

                for foto in fotos:

                    resultado = cloudinary.uploader.upload(
                        foto,
                        folder=f'piads04/viagens/{viagem.id}',
                        resource_type='image'
                    )

                    urls_fotos.append(
                        resultado['secure_url']
                    )

                    ids_uploads.append(
                        resultado['public_id']
                    )

            except Exception:

                for public_id in ids_uploads:
                    try:
                        cloudinary.uploader.destroy(public_id)
                    except Exception:
                        pass

                return Response(
                    {
                        'detail':
                        'Erro ao enviar fotografias.'
                    },
                    status=status.HTTP_502_BAD_GATEWAY
                )

        # --------------------------------------------
        # GRAVAR AVALIAÇÃO E FINALIZAR
        # --------------------------------------------

        erro = None
        resultado = None

        try:
            with transaction.atomic():

                viagem = Shipment.objects.select_for_update().get(
                    pk=viagem.pk
                )

                if viagem.status != 'active':
                    erro = 'A viagem já foi encerrada.'

                else:

                    avaliacao = FinalInspection.objects.create(
                        shipment=viagem,
                        user=request.user,
                        condition=condition,
                        notes=notes
                    )

                    for url in urls_fotos:

                        InspectionPhoto.objects.create(
                            inspection=avaliacao,
                            file_path=url
                        )

                    viagem.status = 'completed'
                    viagem.ended_at = timezone.now()

                    viagem.save(
                        update_fields=[
                            'status',
                            'ended_at',
                            'updated_at',
                        ]
                    )

                    resultado = FinalInspectionSerializer(
                        avaliacao
                    ).data

        except Exception:

            for public_id in ids_uploads:
                try:
                    cloudinary.uploader.destroy(public_id)
                except Exception:
                    pass

            raise

        if erro:

            for public_id in ids_uploads:
                try:
                    cloudinary.uploader.destroy(public_id)
                except Exception:
                    pass

            return Response(
                {'detail': erro},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            resultado,
            status=status.HTTP_200_OK
        )

    # =====================================================
    # DASHBOARD
    # =====================================================

    @action(
        detail=True,
        methods=['get']
    )
    def summary(self, request, pk=None):

        """
        Retorna os indicadores do dashboard.
        """

        viagem = self.get_object()

        return Response(
            shipment_summary(viagem)
        )

    # =====================================================
    # HISTÓRICO DE LEITURAS
    # =====================================================

    @action(
        detail=True,
        methods=['get']
    )
    def readings(self, request, pk=None):

        """
        Histórico de temperatura e umidade.
        """

        viagem = self.get_object()

        leituras = ReadingFilter(
            request.query_params,
            queryset=viagem.readings.all()
        ).qs

        pagina = self.paginate_queryset(leituras)

        return self.get_paginated_response(
            ReadingSerializer(
                pagina,
                many=True
            ).data
        )

    # =====================================================
    # EVENTOS DE IMPACTO
    # =====================================================

    @action(
        detail=True,
        methods=['get']
    )
    def shocks(self, request, pk=None):

        """
        Eventos de impacto durante o transporte.
        """

        viagem = self.get_object()

        pagina = self.paginate_queryset(
            viagem.shock_events.all()
        )

        return self.get_paginated_response(
            ShockEventSerializer(
                pagina,
                many=True
            ).data
        )

    # =====================================================
    # ALERTAS DA VIAGEM
    # =====================================================

    @action(
        detail=True,
        methods=['get']
    )
    def alerts(self, request, pk=None):

        """
        Lista os alertas associados à viagem.
        """

        viagem = self.get_object()

        alertas = viagem.alerts.select_related(
            'acknowledged_by'
        )

        return Response(
            AlertSerializer(
                alertas,
                many=True
            ).data
        )


# =========================================================
# ITENS DA VIAGEM
# =========================================================

class ShipmentItemViewSet(viewsets.ModelViewSet):

    queryset = (
        ShipmentItem.objects
        .select_related(
            'fruit',
            'shipment'
        )
    )

    serializer_class = ShipmentItemSerializer

    filterset_fields = [
        'shipment',
        'fruit',
    ]
