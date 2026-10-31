"""
Regras de negocio da viagem (sem HTTP e sem JSON: so Python e banco).
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Avg, F, Max, Min
from django.utils import timezone

from dominio.models import FruitParameter


class IncompatibleCargo(Exception):
    """As frutas da carga nao tem nenhuma faixa de temperatura/umidade em comum."""


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
        return {campo: None if valor is None else float(valor) for campo, valor in self.__dict__.items()}


def fruit_range_for(fruit_ids):
    """
    Faixa ideal para um conjunto de frutas no MESMO caminhao.

    Regra: INTERSECAO das faixas (maior minimo e menor maximo), porque o caminhao
    tem uma temperatura so e ela precisa servir para todas as frutas. Margens e
    impacto maximo: o MENOR valor (o mais rigoroso).

    Devolve None se nenhuma fruta tem parametro ativo. Levanta IncompatibleCargo
    se a intersecao e vazia (ex.: uma fruta quer 2 a 4 C e outra 12 a 14 C).
    """
    params = list(FruitParameter.objects.filter(fruit_id__in=set(fruit_ids), is_active=True))
    if not params:
        return None

    impactos = [p.impact_max_g for p in params if p.impact_max_g is not None]
    faixa = FruitRange(
        temperature_min_c=max(p.temperature_min_c for p in params),
        temperature_max_c=min(p.temperature_max_c for p in params),
        temperature_critical_margin_c=min(p.temperature_critical_margin_c for p in params),
        humidity_min_pct=max(p.humidity_min_pct for p in params),
        humidity_max_pct=min(p.humidity_max_pct for p in params),
        humidity_critical_margin_pct=min(p.humidity_critical_margin_pct for p in params),
        impact_max_g=min(impactos) if impactos else None,
    )
    if faixa.temperature_min_c >= faixa.temperature_max_c or faixa.humidity_min_pct >= faixa.humidity_max_pct:
        raise IncompatibleCargo('As frutas desta carga não têm faixa de temperatura/umidade em comum.')
    return faixa


def fruit_range(shipment):
    """Faixa ideal da viagem, a partir das frutas da carga. None se nao ha faixa ou a carga e incompativel."""
    try:
        return fruit_range_for(shipment.items.values_list('fruit_id', flat=True))
    except IncompatibleCargo:
        return None


def _num(valor):
    return None if valor is None else float(valor)


def shipment_summary(shipment):
    """
    Dados prontos para o card do dashboard (JSON 4 do plano tecnico, ampliado).
    """
    # Import aqui dentro: alertas.services importa este modulo (evita import circular).
    from alertas.services import classify_reading

    leituras = shipment.readings.all()
    stats = leituras.aggregate(
        temperature_min_c=Min('temperature_c'), temperature_max_c=Max('temperature_c'),
        temperature_avg_c=Avg('temperature_c'),
        humidity_min_pct=Min('humidity_pct'), humidity_max_pct=Max('humidity_pct'),
        humidity_avg_pct=Avg('humidity_pct'),
    )
    impactos = shipment.shock_events.aggregate(maior=Max('impact_peak_g'))
    ultima = leituras.first()  # ordering padrao: mais recente primeiro

    try:
        faixa = fruit_range_for(shipment.items.values_list('fruit_id', flat=True))
        aviso_faixa = None
    except IncompatibleCargo as erro:
        faixa, aviso_faixa = None, str(erro)

    situacao = 'no_data'
    if ultima is not None:
        situacao = 'normal'
        if faixa is not None:
            niveis = classify_reading(ultima, faixa)
            if 'critical' in (niveis['temperature'][0], niveis['humidity'][0]):
                situacao = 'critical'
            elif 'warning' in (niveis['temperature'][0], niveis['humidity'][0]):
                situacao = 'warning'

    # Leitura que chegou mais de 10 min depois de medida = ficou na fila offline da placa.
    atraso = timezone.timedelta(minutes=10)
    sincronizadas_depois = leituras.filter(received_at__gt=F('recorded_at') + atraso).count()

    dispositivo = shipment.device
    return {
        'shipment_id': shipment.id,
        'status': shipment.status,
        'fruits': [{'id': i.fruit_id, 'name': i.fruit.name} for i in shipment.items.select_related('fruit')],
        'device': {
            'id': dispositivo.id,
            'uid': dispositivo.uid,
            'online': dispositivo.online,
            'connection': dispositivo.last_connection_type or None,
            'last_seen_at': dispositivo.last_seen_at,
        },
        'latest_reading': None if ultima is None else {
            'recorded_at': ultima.recorded_at,
            'temperature_c': _num(ultima.temperature_c),
            'humidity_pct': _num(ultima.humidity_pct),
            'impact_peak_g': _num(ultima.impact_peak_g),
        },
        'metrics': {
            **{chave: _num(valor) for chave, valor in stats.items()},
            'readings': leituras.count(),
            'shock_events': shipment.shock_events.count(),
            'max_impact_g': _num(impactos['maior']),
            'synced_after_offline': sincronizadas_depois,
        },
        'limits': None if faixa is None else faixa.as_dict(),
        'limits_warning': aviso_faixa,
        'open_alerts': shipment.alerts.filter(status__in=['open', 'acknowledged']).count(),
        'current_status': situacao,  # no_data / normal / warning / critical
        'generated_at': timezone.now(),
    }
