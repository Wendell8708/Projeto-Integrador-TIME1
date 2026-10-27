"""
Regras de negocio dos alertas: classificar uma leitura e abrir/atualizar/resolver alertas.

Ideia central (didatica):
  1. Pegamos a faixa ideal do transporte (transporte.services.faixa_ideal).
  2. Classificamos cada medida: normal, atencao ou critico.
  3. Para nao dar alarme falso (o DHT11 erra ~2 C e ~5% de umidade), so abrimos
     alerta se as ULTIMAS `LEITURAS_CONSECUTIVAS` leituras estao fora da faixa.
  4. Nunca existem dois alertas ativos do mesmo tipo no mesmo transporte
     (o banco garante). Se piorar, o alerta existente sobe para critico.
  5. Quando a medida volta ao normal, o alerta ativo e resolvido sozinho.
"""

from django.db import transaction
from django.utils import timezone

from iot.models import Reading
from transporte.services import CargaIncompativel, faixa_ideal

from .models import Alert

# Quantas leituras seguidas fora da faixa sao necessarias para abrir um alerta.
LEITURAS_CONSECUTIVAS = 2

ESTADOS_ATIVOS = ['aberto', 'reconhecido']


def classificar(valor, minimo, maximo, margem_critica):
    """
    Classifica UMA medida. Devolve (nivel, limite_violado).

        dentro de [minimo, maximo]          -> ('normal', None)
        fora, ate `margem_critica` de dist. -> ('atencao', limite)
        alem da margem                      -> ('critico', limite)

    Funcao pura (sem banco): facil de testar e de entender.
    """
    if valor < minimo:
        distancia, limite = minimo - valor, minimo
    elif valor > maximo:
        distancia, limite = valor - maximo, maximo
    else:
        return 'normal', None

    nivel = 'critico' if distancia > margem_critica else 'atencao'
    return nivel, limite


def classificar_leitura(leitura, faixa):
    """Classifica temperatura e umidade de uma leitura contra uma FaixaIdeal."""
    return {
        'temperatura': classificar(
            leitura.temperature_c, faixa.temperatura_minima, faixa.temperatura_maxima,
            faixa.margem_critica_temperatura,
        ),
        'umidade': classificar(
            leitura.humidity_pct, faixa.umidade_minima, faixa.umidade_maxima,
            faixa.margem_critica_umidade,
        ),
    }


def _anteriores_tambem_fora(leitura, transporte, tipo, faixa):
    """As (N-1) leituras anteriores deste transporte tambem estavam fora da faixa neste `tipo`?"""
    necessarias = LEITURAS_CONSECUTIVAS - 1
    if necessarias == 0:
        return True

    # As anteriores sao as da MESMA viagem (pela chave), nao as do dispositivo em geral.
    anteriores = list(
        Reading.objects
        .filter(shipment=transporte, recorded_at__lt=leitura.recorded_at)
        .order_by('-recorded_at')[:necessarias]
    )
    if len(anteriores) < necessarias:
        return False  # ainda nao ha historico suficiente para confirmar
    return all(classificar_leitura(l, faixa)[tipo][0] != 'normal' for l in anteriores)


@transaction.atomic
def avaliar_leitura(leitura):
    """
    Avalia uma leitura recem-registrada e abre, atualiza ou resolve alertas.
    Devolve a lista de alertas criados ou alterados por ela.
    """
    # A viagem vem da propria leitura. Vale mesmo se a viagem ja terminou:
    # dado atrasado que chega depois do "concluir" tambem gera alerta.
    transporte = leitura.shipment

    try:
        faixa = faixa_ideal(transporte)
    except CargaIncompativel:
        return []
    if faixa is None:
        return []  # sem limites cadastrados para as frutas: nao ha como avaliar

    mudancas = []
    niveis = classificar_leitura(leitura, faixa)
    valores = {'temperatura': leitura.temperature_c, 'umidade': leitura.humidity_pct}

    for tipo, (nivel, limite) in niveis.items():
        ativo = Alert.objects.filter(transporte=transporte, tipo=tipo, status__in=ESTADOS_ATIVOS).first()
        valor = valores[tipo]

        if nivel == 'normal':
            if ativo is not None:
                ativo.status = 'resolvido'
                ativo.resolvido_em = timezone.now()
                ativo.save(update_fields=['status', 'resolvido_em'])
                mudancas.append(ativo)
            continue

        if ativo is not None:
            if nivel == 'critico' and ativo.severidade != 'critico':
                ativo.severidade = 'critico'
                ativo.save(update_fields=['severidade'])
                mudancas.append(ativo)
            continue

        if _anteriores_tambem_fora(leitura, transporte, tipo, faixa):
            mudancas.append(Alert.objects.create(
                transporte=transporte, leitura=leitura, tipo=tipo, severidade=nivel,
                valor_medido=valor, limite_violado=limite,
            ))

    return mudancas
