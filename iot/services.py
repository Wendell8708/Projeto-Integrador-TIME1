"""
Servico de entrada de leituras.

Qualquer caminho que traga dados do sensor (a rota de telemetria da placa, o
consumidor MQTT, um comando de teste) deve passar por AQUI. Assim a regra e uma
so: gravar sem duplicar e avaliar alertas.
"""

from decimal import Decimal

from django.db import IntegrityError, transaction

from alertas.services import avaliar_leitura

from .models import Reading


@transaction.atomic
def registrar_leitura(*, device, shipment, sequence, **campos):
    """
    Grava uma leitura e avalia se ela gera alerta. Devolve (leitura, criada).

    Reenvio (mesmo device + sequence) devolve a leitura que ja existe, com
    criada=False, e NAO reavalia alertas. Quem decide quem e duplicado e o
    proprio banco (UNIQUE), por isso dois envios iguais ao mesmo tempo nao
    estouram em erro 500.

    `campos`: recorded_at, temperature_c, humidity_pct e, opcionais,
    impact_peak_g e network.
    """
    # Normaliza para Decimal: o objeto recem-criado guarda em memoria exatamente o que
    # recebeu (ex.: o texto "14"), e a avaliacao compara com a faixa em Decimal.
    for nome in ('temperature_c', 'humidity_pct', 'impact_peak_g'):
        if campos.get(nome) is not None:
            campos[nome] = Decimal(str(campos[nome]))

    try:
        # Savepoint: se o INSERT falhar, a transacao externa continua utilizavel.
        with transaction.atomic():
            leitura = Reading.objects.create(device=device, shipment=shipment, sequence=sequence, **campos)
    except IntegrityError:
        existente = Reading.objects.filter(device=device, sequence=sequence).first()
        if existente is None:
            raise  # nao era duplicado: foi um CHECK (valor impossivel). Propaga o erro.
        return existente, False

    avaliar_leitura(leitura)
    return leitura, True
