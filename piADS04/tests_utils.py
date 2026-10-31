"""Funcoes auxiliares so para os testes: montam um cenario pronto no banco de testes."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from dominio.models import Fruit, FruitParameter, Location, Vehicle
from iot.models import Device, DeviceCredential
from transporte.models import Shipment, ShipmentItem


def montar_cenario(com_limites=True, status='active'):
    """
    Cria fazenda, centro de distribuicao, veiculo, placa (com chave), uma fruta com
    faixa de 8 a 12 C (margem 3), 80 a 90 % (margem 10), impacto maximo 2.5 g, e uma
    viagem que comecou ha 1 hora.
    """
    fazenda = Location.objects.create(name='Fazenda Teste', type='farm')
    centro = Location.objects.create(name='CD Teste', type='distribution_center')
    veiculo = Vehicle.objects.create(plate='ABC1D23')
    dispositivo = Device.objects.create(name='ESP32 teste', uid='esp32-teste')
    _, chave = DeviceCredential.gerar(dispositivo)
    fruta = Fruit.objects.create(name='Manga')
    if com_limites:
        FruitParameter.objects.create(
            fruit=fruta,
            temperature_min_c=Decimal('8'), temperature_max_c=Decimal('12'),
            humidity_min_pct=Decimal('80'), humidity_max_pct=Decimal('90'),
            impact_max_g=Decimal('2.5'),
        )
    inicio = timezone.now() - timedelta(hours=1)
    viagem = Shipment.objects.create(
        origin=fazenda, destination=centro, vehicle=veiculo, device=dispositivo,
        started_at=inicio, status=status,
    )
    ShipmentItem.objects.create(shipment=viagem, fruit=fruta, lot='L1', quantity_kg=Decimal('500'))
    return {
        'fazenda': fazenda, 'centro': centro, 'veiculo': veiculo, 'dispositivo': dispositivo,
        'chave': chave, 'fruta': fruta, 'viagem': viagem, 'inicio': inicio,
    }
