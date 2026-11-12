
"""
Regras de negocio da viagem.

Este arquivo concentra as regras de:
- Limites ambientais das frutas.
- Compatibilidade de cargas mistas.
- Congelamento dos limites da viagem.
- Estatisticas do transporte.
- Resumo para o dashboard.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Avg, F, Max, Min
from django.utils import timezone

from dominio.models import FruitParameter


# =========================================================
# EXCEÇÕES
# =========================================================

class IncompatibleCargo(Exception):
    """
    As frutas da carga não possuem uma faixa ambiental
    de temperatura e umidade em comum.
    """


# =========================================================
# LIMITES AMBIENTAIS
# =========================================================

@dataclass(frozen=True)
class FruitRange:

    temperature_min_c: Decimal
    temperature_max_c: Decimal
    temperature_critical_margin_c: Decimal

    humidity_min_pct: Decimal
    humidity_max_pct: Decimal
    humidity_critical_margin_pct: Decimal

    impact_max_g: Decimal | None

    def as_dict(self):
        """
        Converte os limites para um dicionário
        que pode ser armazenado em JSON.
        """

        return {
            campo: (
                None if valor is None else float(valor)
            )
            for campo, valor in self.__dict__.items()
        }


# =========================================================
# CALCULAR LIMITES A PARTIR DAS FRUTAS
# =========================================================

def fruit_range_for(fruit_ids):
    """
    Calcula os limites ambientais para uma carga.

    Quando existem várias frutas, utiliza a interseção
    dos limites de temperatura e umidade.

    Para margens críticas e impacto máximo,
    utiliza o valor mais rigoroso.

    Retorna None quando não existem parâmetros ativos.

    Levanta IncompatibleCargo quando as faixas
    ambientais são incompatíveis.
    """

    params = list(
        FruitParameter.objects.filter(
            fruit_id__in=set(fruit_ids),
            is_active=True
        )
    )

    if not params:
        return None

    impactos = [
        parametro.impact_max_g
        for parametro in params
        if parametro.impact_max_g is not None
    ]

    faixa = FruitRange(

        temperature_min_c=max(
            parametro.temperature_min_c
            for parametro in params
        ),

        temperature_max_c=min(
            parametro.temperature_max_c
            for parametro in params
        ),

        temperature_critical_margin_c=min(
            parametro.temperature_critical_margin_c
            for parametro in params
        ),

        humidity_min_pct=max(
            parametro.humidity_min_pct
            for parametro in params
        ),

        humidity_max_pct=min(
            parametro.humidity_max_pct
            for parametro in params
        ),

        humidity_critical_margin_pct=min(
            parametro.humidity_critical_margin_pct
            for parametro in params
        ),

        impact_max_g=(
            min(impactos)
            if impactos
            else None
        ),
    )

    # Verifica a compatibilidade da carga.

    if (
        faixa.temperature_min_c >= faixa.temperature_max_c
        or
        faixa.humidity_min_pct >= faixa.humidity_max_pct
    ):

        raise IncompatibleCargo(
            'As frutas desta carga não possuem '
            'uma faixa de temperatura e umidade em comum.'
        )

    return faixa


# =========================================================
# LIMITES CONGELADOS DA VIAGEM
# =========================================================

def fruit_range(shipment):
    """
    Retorna os limites ambientais de uma viagem.

    REGRA PRINCIPAL:

    Se a viagem possui limites congelados,
    utiliza exclusivamente os valores armazenados
    em limits_snapshot.

    Dessa forma, alterações posteriores no cadastro
    das frutas não modificam os limites da viagem.

    COMPATIBILIDADE:

    Viagens antigas, sem limites congelados,
    continuam utilizando os parâmetros atuais
    das frutas cadastradas.
    """

    snapshot = shipment.limits_snapshot

    # -----------------------------------------------------
    # VIAGEM COM LIMITES CONGELADOS
    # -----------------------------------------------------

    if snapshot is not None:

        return FruitRange(

            temperature_min_c=Decimal(
                str(snapshot['temperature_min_c'])
            ),

            temperature_max_c=Decimal(
                str(snapshot['temperature_max_c'])
            ),

            temperature_critical_margin_c=Decimal(
                str(snapshot['temperature_critical_margin_c'])
            ),

            humidity_min_pct=Decimal(
                str(snapshot['humidity_min_pct'])
            ),

            humidity_max_pct=Decimal(
                str(snapshot['humidity_max_pct'])
            ),

            humidity_critical_margin_pct=Decimal(
                str(snapshot['humidity_critical_margin_pct'])
            ),

            impact_max_g=(
                Decimal(
                    str(snapshot['impact_max_g'])
                )
                if snapshot.get('impact_max_g') is not None
                else None
            ),
        )

    # -----------------------------------------------------
    # VIAGEM ANTIGA SEM LIMITES CONGELADOS
    # -----------------------------------------------------

    try:

        return fruit_range_for(
            shipment.items.values_list(
                'fruit_id',
                flat=True
            )
        )

    except IncompatibleCargo:

        return None


# =========================================================
# CONVERSÃO NUMÉRICA
# =========================================================

def _num(valor):
    """
    Converte Decimal para float.

    Mantém None quando não existe valor.
    """

    return (
        None
        if valor is None
        else float(valor)
    )


# =========================================================
# RESUMO DA VIAGEM PARA O DASHBOARD
# =========================================================

def shipment_summary(shipment):
    """
    Retorna os dados utilizados pelo dashboard.

    Inclui:
    - Informações da viagem.
    - Frutas transportadas.
    - Situação do dispositivo.
    - Última leitura.
    - Estatísticas de temperatura e umidade.
    - Eventos de impacto.
    - Leituras sincronizadas depois de falha de rede.
    - Limites ambientais congelados.
    - Quantidade de alertas abertos.
    - Estado atual do transporte.
    """

    # Importação local para evitar dependência circular.
    from alertas.services import classify_reading

    # -----------------------------------------------------
    # LEITURAS DA VIAGEM
    # -----------------------------------------------------

    leituras = shipment.readings.all()

    stats = leituras.aggregate(

        temperature_min_c=Min('temperature_c'),

        temperature_max_c=Max('temperature_c'),

        temperature_avg_c=Avg('temperature_c'),

        humidity_min_pct=Min('humidity_pct'),

        humidity_max_pct=Max('humidity_pct'),

        humidity_avg_pct=Avg('humidity_pct'),
    )

    # -----------------------------------------------------
    # EVENTOS DE IMPACTO
    # -----------------------------------------------------

    impactos = shipment.shock_events.aggregate(
        maior=Max('impact_peak_g')
    )

    # Última leitura registrada.
    ultima = leituras.first()

    # -----------------------------------------------------
    # LIMITES AMBIENTAIS DA VIAGEM
    # -----------------------------------------------------

    # CORREÇÃO IMPORTANTE:
    #
    # Agora utilizamos fruit_range(shipment),
    # que consulta primeiro os limites congelados.
    #
    # Antes o dashboard recalculava os limites
    # utilizando os parâmetros atuais das frutas.

    faixa = fruit_range(shipment)

    aviso_faixa = None

    if faixa is None:

        aviso_faixa = (
            'Não foi possível determinar os limites '
            'ambientais desta viagem.'
        )

    # -----------------------------------------------------
    # CLASSIFICAR A SITUAÇÃO ATUAL
    # -----------------------------------------------------

    situacao = 'no_data'

    if ultima is not None:

        situacao = 'normal'

        if faixa is not None:

            niveis = classify_reading(
                ultima,
                faixa
            )

            if 'critical' in (
                niveis['temperature'][0],
                niveis['humidity'][0]
            ):

                situacao = 'critical'

            elif 'warning' in (
                niveis['temperature'][0],
                niveis['humidity'][0]
            ):

                situacao = 'warning'

    # -----------------------------------------------------
    # LEITURAS RECEBIDAS APÓS FALHA DE REDE
    # -----------------------------------------------------

    atraso = timezone.timedelta(
        minutes=10
    )

    sincronizadas_depois = leituras.filter(
        received_at__gt=F('recorded_at') + atraso
    ).count()

    # -----------------------------------------------------
    # INFORMAÇÕES DO DISPOSITIVO
    # -----------------------------------------------------

    dispositivo = shipment.device

    # -----------------------------------------------------
    # RESPOSTA DO DASHBOARD
    # -----------------------------------------------------

    return {

        'shipment_id': shipment.id,

        'status': shipment.status,

        'fruits': [
            {
                'id': item.fruit_id,
                'name': item.fruit.name,
            }
            for item in shipment.items.select_related(
                'fruit'
            )
        ],

        'device': {

            'id': dispositivo.id,

            'uid': dispositivo.uid,

            'online': dispositivo.online,

            'connection': (
                dispositivo.last_connection_type
                or None
            ),

            'last_seen_at': dispositivo.last_seen_at,
        },

        'latest_reading': (

            None

            if ultima is None

            else {

                'recorded_at': ultima.recorded_at,

                'temperature_c': _num(
                    ultima.temperature_c
                ),

                'humidity_pct': _num(
                    ultima.humidity_pct
                ),

                'impact_peak_g': _num(
                    ultima.impact_peak_g
                ),
            }
        ),

        'metrics': {

            **{
                chave: _num(valor)
                for chave, valor in stats.items()
            },

            'readings': leituras.count(),

            'shock_events': (
                shipment.shock_events.count()
            ),

            'max_impact_g': _num(
                impactos['maior']
            ),

            'synced_after_offline': (
                sincronizadas_depois
            ),
        },

        # Limites congelados ou limites atuais
        # para viagens antigas.
        'limits': (
            None
            if faixa is None
            else faixa.as_dict()
        ),

        'limits_warning': aviso_faixa,

        'open_alerts': shipment.alerts.filter(
            status__in=[
                'open',
                'acknowledged'
            ]
        ).count(),

        'current_status': situacao,

        'generated_at': timezone.now(),
    }
