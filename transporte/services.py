"""
Regras de negocio do transporte (sem HTTP e sem JSON: so Python e banco).
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Avg, Max, Min
from django.utils import timezone

from dominio.models import ConfiguracaoLimite

from .models import Shipment


class CargaIncompativel(Exception):
    """As frutas da carga nao tem nenhuma faixa de temperatura/umidade em comum."""


@dataclass(frozen=True)
class FaixaIdeal:
    temperatura_minima: Decimal
    temperatura_maxima: Decimal
    margem_critica_temperatura: Decimal
    umidade_minima: Decimal
    umidade_maxima: Decimal
    margem_critica_umidade: Decimal

    def como_dict(self):
        return {campo: float(valor) for campo, valor in self.__dict__.items()}


def faixa_ideal_de_frutas(frutas_ids):
    """
    Calcula a faixa ideal para um conjunto de frutas no MESMO caminhao.

    Regra: INTERSECAO das faixas (maior minimo e menor maximo), porque o
    caminhao tem uma temperatura so e ela precisa servir para todas as frutas.
    A margem critica usada e a MENOR (a mais rigorosa).

    Devolve None se nao ha nenhuma fruta com limite ativo cadastrado.
    Levanta CargaIncompativel se a intersecao e vazia (ex.: uma fruta quer
    2 a 4 C e outra quer 12 a 14 C).
    """
    limites = list(ConfiguracaoLimite.objects.filter(fruta_id__in=set(frutas_ids), situacao=True))
    if not limites:
        return None

    faixa = FaixaIdeal(
        temperatura_minima=max(l.temperatura_minima for l in limites),
        temperatura_maxima=min(l.temperatura_maxima for l in limites),
        margem_critica_temperatura=min(l.margem_critica_temperatura for l in limites),
        umidade_minima=max(l.umidade_minima for l in limites),
        umidade_maxima=min(l.umidade_maxima for l in limites),
        margem_critica_umidade=min(l.margem_critica_umidade for l in limites),
    )
    if faixa.temperatura_minima >= faixa.temperatura_maxima or faixa.umidade_minima >= faixa.umidade_maxima:
        raise CargaIncompativel('As frutas desta carga não têm faixa de temperatura/umidade em comum.')
    return faixa


def faixa_ideal(transporte):
    """Faixa ideal do transporte, a partir das frutas das suas cargas."""
    frutas_ids = transporte.cargas.values_list('fruta_id', flat=True)
    return faixa_ideal_de_frutas(frutas_ids)


def transporte_ativo_para(dispositivo, instante):
    """
    Qual transporte estava EM ANDAMENTO com este dispositivo naquele instante?
    E assim que uma leitura "descobre" a que viagem pertence.
    """
    return (
        Shipment.objects
        .filter(dispositivo=dispositivo, status='em_andamento', data_hora_inicio__lte=instante)
        .order_by('-data_hora_inicio')
        .first()
    )


def _numero(valor):
    return None if valor is None else float(valor)


def resumo_do_transporte(transporte):
    """
    Dados prontos para o card do dashboard: estatisticas, ultima leitura,
    faixa ideal e status atual (sem_dados / normal / atencao / critico).
    """
    # Import aqui dentro: alertas.services importa transporte.services (evita ciclo).
    from alertas.services import classificar_leitura

    leituras = transporte.readings.all()
    estatisticas = leituras.aggregate(
        temperatura_media=Avg('temperature_c'), temperatura_minima=Min('temperature_c'), temperatura_maxima=Max('temperature_c'),
        umidade_media=Avg('humidity_pct'), umidade_minima=Min('humidity_pct'), umidade_maxima=Max('humidity_pct'),
    )
    ultima = leituras.first()  # ordering padrao: mais recente primeiro

    try:
        faixa = faixa_ideal(transporte)
        erro_faixa = None
    except CargaIncompativel as erro:
        faixa, erro_faixa = None, str(erro)

    status_atual = 'sem_dados'
    if ultima is not None:
        status_atual = 'normal'
        if faixa is not None:
            niveis = classificar_leitura(ultima, faixa)
            if 'critico' in (niveis['temperatura'][0], niveis['umidade'][0]):
                status_atual = 'critico'
            elif 'atencao' in (niveis['temperatura'][0], niveis['umidade'][0]):
                status_atual = 'atencao'

    return {
        'transporte': transporte.id,
        'status_transporte': transporte.status,
        'total_leituras': leituras.count(),
        'estatisticas': {chave: _numero(valor) for chave, valor in estatisticas.items()},
        'ultima_leitura': None if ultima is None else {
            'temperatura': float(ultima.temperature_c),
            'umidade': float(ultima.humidity_pct),
            'medido_em': ultima.recorded_at,
        },
        'faixa_ideal': None if faixa is None else faixa.como_dict(),
        'aviso_faixa': erro_faixa,
        'alertas_ativos': transporte.alertas.filter(status__in=['aberto', 'reconhecido']).count(),
        'status_atual': status_atual,
        'gerado_em': timezone.now(),
    }
