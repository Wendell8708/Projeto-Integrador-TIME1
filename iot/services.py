"""
Servico de entrada de dados da placa.

Qualquer caminho que traga dados do sensor (a rota de telemetria, um futuro
consumidor MQTT, a seed, um teste) passa por AQUI. Assim a regra e uma so:
gravar sem duplicar e avaliar alertas.
"""

from decimal import Decimal

from django.db import IntegrityError, transaction

from alertas.services import evaluate_reading, evaluate_shock

from .models import Reading, ShockEvent


def _para_decimal(campos, nomes):
    # O objeto recem-criado guarda em memoria exatamente o que recebeu (ex.: o texto
    # "14"); a avaliacao compara com a faixa em Decimal, entao normalizamos antes.
    for nome in nomes:
        if campos.get(nome) is not None:
            campos[nome] = Decimal(str(campos[nome]))


@transaction.atomic
def register_reading(*, device, shipment, sequence, **campos):
    """
    Grava uma leitura e avalia se ela gera alerta. Devolve (leitura, criada).

    Reenvio (mesmo device + sequence) devolve a leitura que ja existe, com
    criada=False, e NAO reavalia alertas. Quem decide o que e duplicado e o
    banco (UNIQUE): dois envios iguais ao mesmo tempo nao estouram em erro 500.
    Valor impossivel (CHECK do banco) levanta IntegrityError.

    `campos`: recorded_at, temperature_c, humidity_pct e, opcionais, impact_peak_g e network.
    """
    _para_decimal(campos, ('temperature_c', 'humidity_pct', 'impact_peak_g'))
    try:
        with transaction.atomic():  # savepoint: se o INSERT falhar, a transacao de fora continua usavel
            leitura = Reading.objects.create(device=device, shipment=shipment, sequence=sequence, **campos)
    except IntegrityError:
        existente = Reading.objects.filter(device=device, sequence=sequence).first()
        if existente is None:
            raise  # nao era duplicado: foi um CHECK (valor impossivel)
        return existente, False

    evaluate_reading(leitura)
    return leitura, True


@transaction.atomic
def register_shock(*, device, shipment, event_id, **campos):
    """Mesma ideia de register_reading, para eventos de impacto. Devolve (evento, criado)."""
    _para_decimal(campos, ('impact_peak_g',))
    try:
        with transaction.atomic():
            evento = ShockEvent.objects.create(device=device, shipment=shipment, event_id=event_id, **campos)
    except IntegrityError:
        existente = ShockEvent.objects.filter(device=device, event_id=event_id).first()
        if existente is None:
            raise
        return existente, False

    evaluate_shock(evento)
    return evento, True


def process_batch(*, device, shipment, readings, shocks, network=''):
    """
    Grava um lote vindo da placa e devolve o que pode ser apagado da fila dela.

    - Ordena por `recorded_at`: a regra de "2 leituras seguidas fora da faixa"
      precisa da ordem certa mesmo quando o lote chega atrasado ou embaralhado.
    - Cada item e gravado separadamente: um item invalido nao derruba os outros.
    - Confirma o que foi gravado agora E o que ja existia (reenvio): os dois ja
      estao no banco, entao a placa pode apagar. Item recusado NAO e confirmado.
    """
    aceitas, eventos_aceitos = [], []

    for item in sorted(readings, key=lambda r: r['recorded_at']):
        try:
            register_reading(device=device, shipment=shipment, network=network, **item)
            aceitas.append(item['sequence'])
        except IntegrityError:
            pass

    for item in sorted(shocks, key=lambda s: s['recorded_at']):
        try:
            register_shock(device=device, shipment=shipment, **item)
            eventos_aceitos.append(item['event_id'])
        except IntegrityError:
            pass

    return {'accepted_reading_sequences': aceitas, 'accepted_shock_ids': eventos_aceitos}
