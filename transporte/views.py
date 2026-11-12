
"""
Views do sistema de monitoramento de transporte de frutas.

Funcionalidades:
- Criar e gerenciar viagens.
- Iniciar viagens com limites ambientais congelados.
- Finalizar viagens com avaliação e fotografias.
- Consultar indicadores do dashboard.
- Consultar leituras de temperatura e umidade.
- Consultar eventos de impacto.
- Consultar alertas.
- Gerenciar itens das viagens.
"""

import logging

import cloudinary
import cloudinary.uploader

from decouple import config

from django.db import IntegrityError, transaction
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
    JSONParser,
)
from rest_framework.response import Response

from alertas.serializers import AlertSerializer

from iot.serializers import (
    ReadingSerializer,
    ShockEventSerializer,
)
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


logger = logging.getLogger(__name__)


# =========================================================
# FUNÇÕES AUXILIARES PARA FOTOGRAFIAS
# =========================================================

def validar_fotografia(foto):
    """
    Valida tamanho, tipo declarado e assinatura
    inicial de imagens JPEG e PNG.
    """

    tipos = {
        'image/jpeg': b'\xff\xd8\xff',
        'image/png': b'\x89PNG\r\n\x1a\n',
    }

    if foto.size == 0:
        return 'A fotografia está vazia.'

    if foto.size > 5 * 1024 * 1024:
        return 'Cada fotografia deve ter no máximo 5 MB.'

    tipo = getattr(foto, 'content_type', '')

    if tipo not in tipos:
        return 'São permitidas somente imagens JPEG ou PNG.'

    posicao = foto.tell()

    try:
        foto.seek(0)
        assinatura = foto.read(8)

    finally:
        foto.seek(posicao)

    if not assinatura.startswith(tipos[tipo]):
        return 'O conteúdo da fotografia não corresponde ao tipo informado.'

    return None


def configurar_cloudinary():
    """
    Configura o Cloudinary a partir das variáveis
    de ambiente, sem expor credenciais.
    """

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

    if not all([cloud_name, api_key, api_secret]):
        return False

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )

    return True


def excluir_uploads_cloudinary(public_ids):
    """
    Tenta excluir fotografias enviadas caso
    uma operação posterior falhe.
    """

    for public_id in public_ids:
        try:
            cloudinary.uploader.destroy(
                public_id,
                resource_type='image'
            )

        except Exception:
            logger.exception(
                'Falha ao remover upload do Cloudinary: %s',
                public_id
            )


# =========================================================
# VIEWSET DAS VIAGENS
# =========================================================

class ShipmentViewSet(viewsets.ModelViewSet):

    queryset = (
        Shipment.objects
        .select_related(
            'origin',
            'destination',
            'vehicle',
            'device',
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
        """
        Registra o usuário responsável pela criação.
        """

        serializer.save(
            created_by=self.request.user
        )

    # =====================================================
    # INICIAR VIAGEM
    # =====================================================

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[PodeAlterarModelo],
    )
    def start(self, request, pk=None):
        """
        Inicia uma viagem planejada.

        Regras:
        - A viagem precisa estar planejada.
        - Precisa possuir ao menos uma fruta.
        - A carga deve ter limites compatíveis.
        - Os limites são congelados na viagem.
        - Um dispositivo não pode ter duas
          viagens ativas simultaneamente.
        """

        viagem_atual = self.get_object()

        try:
            with transaction.atomic():

                viagem = (
                    Shipment.objects
                    .select_for_update()
                    .get(pk=viagem_atual.pk)
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
                            'Cadastre ao menos uma fruta na carga antes de iniciar.'
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
                            'As frutas não possuem limites ambientais configurados.'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Congela os limites ambientais.
                viagem.limits_snapshot = faixa.as_dict()

                # Inicia efetivamente a viagem.
                viagem.status = 'active'
                viagem.started_at = timezone.now()

                viagem.save(
                    update_fields=[
                        'status',
                        'started_at',
                        'limits_snapshot',
                        'updated_at',
                    ]
                )

        except IntegrityError:
            # A transação já foi revertida neste ponto.
            return Response(
                {
                    'detail':
                    'Não foi possível iniciar a viagem. '
                    'O dispositivo pode estar vinculado '
                    'a outra viagem ativa.'
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
        ],
    )
    def finish(self, request, pk=None):
        """
        Finaliza uma viagem em andamento.

        Recebe:
        - condition: good, damaged ou critical.
        - notes: observações da chegada.
        - photos: arquivos JPEG/PNG opcionais.

        As fotografias são armazenadas no Cloudinary.
        """

        viagem_atual = self.get_object()

        if viagem_atual.status != 'active':
            return Response(
                {
                    'detail':
                    'Só é possível finalizar uma viagem em andamento.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------------------------------
        # VALIDAR AVALIAÇÃO
        # -------------------------------------------------

        condition = request.data.get('condition')
        notes = request.data.get('notes', '')

        condicoes_validas = {
            'good',
            'damaged',
            'critical',
        }

        if condition not in condicoes_validas:
            return Response(
                {
                    'detail':
                    'Informe uma condição válida: '
                    'good, damaged ou critical.'
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

        if len(notes) > 10000:
            return Response(
                {
                    'detail':
                    'As observações devem ter no máximo 10000 caracteres.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------------------------------
        # VALIDAR FOTOGRAFIAS
        # -------------------------------------------------

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
            erro = validar_fotografia(foto)

            if erro:
                return Response(
                    {'detail': erro},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # -------------------------------------------------
        # VERIFICAR CLOUDINARY
        # -------------------------------------------------

        if fotos and not configurar_cloudinary():
            return Response(
                {
                    'detail':
                    'O armazenamento de fotografias '
                    'não está configurado.'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        urls_fotos = []
        ids_uploads = []

        # -------------------------------------------------
        # ENVIAR FOTOS PARA CLOUDINARY
        # -------------------------------------------------

        try:
            for foto in fotos:

                foto.seek(0)

                resultado = cloudinary.uploader.upload(
                    foto,
                    folder=(
                        f'piads04/viagens/'
                        f'{viagem_atual.pk}'
                    ),
                    resource_type='image',
                )

                ids_uploads.append(
                    resultado['public_id']
                )

                urls_fotos.append(
                    resultado['secure_url']
                )

        except Exception:
            logger.exception(
                'Falha ao enviar fotografias da viagem %s',
                viagem_atual.pk
            )

            excluir_uploads_cloudinary(ids_uploads)

            return Response(
                {
                    'detail':
                    'Não foi possível armazenar as fotografias.'
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        # -------------------------------------------------
        # SALVAR A AVALIAÇÃO EM UMA TRANSAÇÃO
        # -------------------------------------------------

        viagem_ja_encerrada = False

        try:
            with transaction.atomic():

                viagem = (
                    Shipment.objects
                    .select_for_update()
                    .get(pk=viagem_atual.pk)
                )

                if viagem.status != 'active':
                    viagem_ja_encerrada = True

                else:
                    avaliacao = FinalInspection.objects.create(
                        shipment=viagem,
                        user=request.user,
                        condition=condition,
                        notes=notes,
                    )

                    InspectionPhoto.objects.bulk_create([
                        InspectionPhoto(
                            inspection=avaliacao,
                            file_path=url,
                        )
                        for url in urls_fotos
                    ])

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
            excluir_uploads_cloudinary(ids_uploads)
            raise

        if viagem_ja_encerrada:
            excluir_uploads_cloudinary(ids_uploads)

            return Response(
                {
                    'detail':
                    'Esta viagem já foi encerrada.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            resultado,
            status=status.HTTP_200_OK
        )

    # =====================================================
    # RESUMO DO DASHBOARD
    # =====================================================

    @action(
        detail=True,
        methods=['get'],
    )
    def summary(self, request, pk=None):
        """
        Retorna os indicadores da viagem.
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
        methods=['get'],
    )
    def readings(self, request, pk=None):
        """
        Lista leituras de temperatura e umidade.

        Aceita os filtros de período já existentes.
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
        methods=['get'],
    )
    def shocks(self, request, pk=None):
        """
        Retorna os eventos de impacto da viagem.
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
    # ALERTAS
    # =====================================================

    @action(
        detail=True,
        methods=['get'],
    )
    def alerts(self, request, pk=None):
        """
        Retorna os alertas da viagem.
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
# VIEWSET DOS ITENS DAS VIAGENS
# =========================================================

class ShipmentItemViewSet(viewsets.ModelViewSet):
    """
    Gerencia as frutas e os lotes transportados.
    """

    queryset = (
        ShipmentItem.objects
        .select_related(
            'fruit',
            'shipment',
        )
    )

    serializer_class = ShipmentItemSerializer

    filterset_fields = [
        'shipment',
        'fruit',
    ]
