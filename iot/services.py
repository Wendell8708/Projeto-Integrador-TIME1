"""
Servico de entrada de leituras.

Qualquer caminho que traga dados do sensor (POST manual na API, sincronizacao
com o ThingSpeak, ou o ESP32 enviando direto) deve passar por AQUI. Assim a
regra e uma so: gravar sem duplicar e avaliar alertas.
"""

from django.db import transaction

from alertas.services import avaliar_leitura

from .models import Leitura


@transaction.atomic
def registrar_leitura(dispositivo, temperatura, umidade, medido_em, origem_id=None):
    """
    Grava uma leitura e avalia se ela gera alerta.

    Devolve (leitura, criada). Se `origem_id` ja existe para o dispositivo
    (ex.: o mesmo entry_id do ThingSpeak sincronizado duas vezes), devolve a
    leitura existente com criada=False e NAO reavalia alertas.
    """
    if origem_id is not None:
        existente = Leitura.objects.filter(dispositivo=dispositivo, origem_id=origem_id).first()
        if existente is not None:
            return existente, False

    leitura = Leitura.objects.create(
        dispositivo=dispositivo, temperatura=temperatura, umidade=umidade,
        medido_em=medido_em, origem_id=origem_id,
    )
    avaliar_leitura(leitura)
    return leitura, True
