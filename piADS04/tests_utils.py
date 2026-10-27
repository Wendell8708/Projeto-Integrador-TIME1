"""Funcoes auxiliares so para os testes: montam um cenario pronto no banco de testes."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from dominio.models import ConfiguracaoLimite, Fruta, Local, Veiculo
from iot.models import Device
from transporte.models import Carga, Shipment


def montar_cenario(com_limites=True, status='em_andamento'):
    """
    Cria fazenda, centro de distribuicao, veiculo, dispositivo, uma fruta com
    faixa de 8 a 12 C (margem 3) e 80 a 90 % (margem 10) e uma viagem.
    A viagem comecou ha 1 hora.
    """
    fazenda = Local.objects.create(nome='Fazenda Teste', tipo_local='fazenda')
    centro = Local.objects.create(nome='CD Teste', tipo_local='centro_distribuicao')
    veiculo = Veiculo.objects.create(placa='ABC1D23')
    dispositivo = Device.objects.create(nome='ESP32 teste', identificador='esp32-teste')
    fruta = Fruta.objects.create(nome='Manga')
    if com_limites:
        ConfiguracaoLimite.objects.create(
            fruta=fruta,
            temperatura_minima=Decimal('8'), temperatura_maxima=Decimal('12'),
            umidade_minima=Decimal('80'), umidade_maxima=Decimal('90'),
        )
    inicio = timezone.now() - timedelta(hours=1)
    transporte = Shipment.objects.create(
        origem=fazenda, destino=centro, veiculo=veiculo, dispositivo=dispositivo,
        data_hora_inicio=inicio, status=status,
    )
    Carga.objects.create(transporte=transporte, fruta=fruta, lote='L1', quantidade_kg=Decimal('500'))
    return {
        'fazenda': fazenda, 'centro': centro, 'veiculo': veiculo, 'dispositivo': dispositivo,
        'fruta': fruta, 'transporte': transporte, 'inicio': inicio,
    }
