"""
Popula o banco com um cenario de demonstracao completo.

Uso:
    python manage.py seed                          # senha dos usuarios gerada e mostrada no final
    python manage.py seed --senha "Minha-Senha-1"  # senha escolhida
    python manage.py seed --reset                  # APAGA os dados do projeto e recria do zero

O que cria:
  - grupos (criar_grupos) e 3 usuarios: admin, operador e visualizador
  - 4 locais, 2 veiculos, 5 frutas com parametros ATIVOS (valores "A CONFERIR")
  - 2 placas com chave de acesso: VSF-001 (a placa real) e VSF-002 (simulador)
  - 3 viagens:
      * concluida ontem (VSF-002), leituras normais
      * EM ANDAMENTO (VSF-002), com aquecimento no fim -> alerta de temperatura,
        um impacto acima do limite -> alerta de impacto, e leituras que chegaram
        atrasadas (simulando a fila offline da placa)
      * PLANEJADA com a placa real VSF-001: inicie pela API (/shipments/{id}/start)
        e a placa passa a enviar dados para ela

As leituras passam pelas mesmas regras da placa (iot.services), entao os alertas
nascem de verdade, pelo motor de alertas.
"""

import random
import secrets
from io import StringIO
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from alertas.models import Alert
from dominio.models import Fruit, FruitParameter, Location, Vehicle
from iot.models import Device, DeviceCredential, Reading, ShockEvent
from iot.services import register_reading, register_shock
from transporte.models import Shipment, ShipmentItem

USUARIOS = [
    # e-mail, nome, sobrenome, grupo, superusuario
    ('admin@example.com', 'Administrador', 'Demo', 'Administrador', True),
    ('operador@example.com', 'Operador', 'Demo', 'Operador', False),
    ('visualizador@example.com', 'Visualizador', 'Demo', 'Visualizador', False),
]


class Command(BaseCommand):
    help = 'Popula o banco com dados de demonstracao (usuarios, frutas, placas, viagens, leituras e alertas).'

    def add_arguments(self, parser):
        parser.add_argument('--senha', help='Senha dos 3 usuarios. Sem ela, uma senha aleatoria e gerada.')
        parser.add_argument('--reset', action='store_true',
                            help='Apaga TODOS os dados do projeto (viagens, leituras, frutas, placas...) antes.')
        parser.add_argument('--sim', action='store_true', help='Confirma o --reset sem perguntar.')

    def handle(self, *args, **options):
        if options['reset']:
            if not options['sim']:
                resposta = input('Isso APAGA todos os dados do projeto neste banco. Digite "apagar" para seguir: ')
                if resposta.strip().lower() != 'apagar':
                    raise CommandError('Cancelado.')
            self.apagar_tudo()
        elif Device.objects.filter(uid='VSF-001').exists():
            raise CommandError('A seed ja foi aplicada neste banco. Use --reset para apagar e recriar.')

        senha = options['senha'] or secrets.token_urlsafe(9)
        self.rng = random.Random(42)  # mesmos "sorteios" a cada execucao

        with transaction.atomic():
            call_command('criar_grupos', verbosity=0)
            self.criar_usuarios(senha)
            self.criar_cadastros()
            chaves = self.criar_placas()
            viagens = self.criar_viagens()

        self.resumo(senha, options['senha'] is None, chaves, viagens)

    # --- Limpeza ---------------------------------------------------------

    def apagar_tudo(self):
        # Ordem importa: os models usam PROTECT, entao filhos saem antes dos pais.
        for modelo in (Alert, ShockEvent, Reading, ShipmentItem, Shipment, DeviceCredential, Device,
                       FruitParameter, Fruit, Vehicle, Location):
            modelo.objects.all().delete()
        User.objects.filter(email__in=[u[0] for u in USUARIOS]).delete()
        self.stdout.write(self.style.WARNING('Dados do projeto apagados.'))

    # --- Cadastros -------------------------------------------------------

    def criar_usuarios(self, senha):
        self.usuarios = {}
        for email, nome, sobrenome, grupo, super_usuario in USUARIOS:
            usuario = User.objects.create_user(
                username=email, email=email, password=senha, first_name=nome, last_name=sobrenome,
                is_staff=super_usuario, is_superuser=super_usuario,
            )
            usuario.groups.add(Group.objects.get(name=grupo))
            self.usuarios[grupo] = usuario

    def criar_cadastros(self):
        L = Location.objects.create
        self.fazenda = L(name='Fazenda Vale Verde', type='farm', address='Petrolina - PE')
        self.packing = L(name='Packing House Juazeiro', type='warehouse', address='Juazeiro - BA')
        self.cd_recife = L(name='CD Recife', type='distribution_center', address='Recife - PE')
        self.ceagesp = L(name='CEAGESP', type='distribution_center', address='São Paulo - SP')

        self.caminhao1 = Vehicle.objects.create(plate='QWE1A23', model='Baú refrigerado 3/4')
        self.caminhao2 = Vehicle.objects.create(plate='RTY2B34', model='Carreta refrigerada')

        # Frutas e faixas do comando oficial; aqui ativamos todas para a demonstracao.
        call_command('carregar_limites_iniciais', stdout=StringIO())  # silencia a saida do comando
        FruitParameter.objects.update(is_active=True)
        self.manga = Fruit.objects.get(name='Manga')
        self.banana = Fruit.objects.get(name='Banana')

    def criar_placas(self):
        chaves = {}
        self.placa_real = Device.objects.create(uid='VSF-001', name='Placa ESP32-C3 (real)')
        self.simulador = Device.objects.create(uid='VSF-002', name='Simulador 02')
        for placa in (self.placa_real, self.simulador):
            _, chaves[placa.uid] = DeviceCredential.gerar(placa)
        return chaves

    # --- Viagens, leituras e impactos ------------------------------------

    def leituras(self, viagem, inicio, quantidade, intervalo_min, temperaturas, seq_inicial, rede='wifi'):
        """Grava leituras pelo mesmo servico que a placa usa (avalia alertas de verdade)."""
        for i in range(quantidade):
            register_reading(
                device=viagem.device, shipment=viagem, sequence=seq_inicial + i,
                recorded_at=inicio + timedelta(minutes=intervalo_min * i),
                temperature_c=Decimal(str(round(temperaturas(i), 2))),
                humidity_pct=Decimal(str(round(self.rng.uniform(86, 89), 2))),
                impact_peak_g=Decimal(str(round(self.rng.uniform(0.1, 1.2), 2))),
                network=rede,
            )
        return seq_inicial + quantidade

    def criar_viagens(self):
        agora = timezone.now()
        operador = self.usuarios['Operador']
        rng = self.rng

        # 1) Concluida ontem: 12 h, leituras a cada 10 min, tudo dentro da faixa.
        inicio1 = agora - timedelta(days=1, hours=14)
        concluida = Shipment.objects.create(
            origin=self.fazenda, destination=self.cd_recife, vehicle=self.caminhao2, device=self.simulador,
            created_by=operador, status='completed', started_at=inicio1, ended_at=inicio1 + timedelta(hours=12),
        )
        ShipmentItem.objects.create(shipment=concluida, fruit=self.manga, lot='MG-2610-01', quantity_kg=Decimal('8000'))
        seq = self.leituras(concluida, inicio1, 72, 10, lambda i: rng.uniform(11, 12.5), seq_inicial=1)
        register_shock(device=self.simulador, shipment=concluida, event_id='evt-0001',
                       recorded_at=inicio1 + timedelta(hours=5), impact_peak_g=Decimal('1.8'))

        # 2) Em andamento: comecou ha 2 h, leitura a cada 5 min. Nas ultimas 4, a carga
        #    esquenta (14 C > maximo de 13 C da manga) -> alerta de temperatura.
        inicio2 = agora - timedelta(hours=2)
        ativa = Shipment.objects.create(
            origin=self.packing, destination=self.ceagesp, vehicle=self.caminhao1, device=self.simulador,
            created_by=operador, status='active', started_at=inicio2,
        )
        ShipmentItem.objects.create(shipment=ativa, fruit=self.manga, lot='MG-2810-07', quantity_kg=Decimal('4500'))
        total = 24
        seq = self.leituras(ativa, inicio2, total, 5,
                            lambda i: rng.uniform(14.0, 14.6) if i >= total - 4 else rng.uniform(11, 12.5),
                            seq_inicial=seq)
        register_shock(device=self.simulador, shipment=ativa, event_id='evt-0002',
                       recorded_at=inicio2 + timedelta(minutes=47), impact_peak_g=Decimal('3.1'))

        # Leituras entre 30 e 60 min atras "chegaram" 35 min depois: simula a placa
        # sem rede, guardando na fila, e sincronizando quando a rede voltou.
        janela = ativa.readings.filter(recorded_at__gte=agora - timedelta(minutes=60),
                                       recorded_at__lt=agora - timedelta(minutes=30))
        for leitura in janela:
            Reading.objects.filter(pk=leitura.pk).update(received_at=leitura.recorded_at + timedelta(minutes=35))

        self.simulador.last_seen_at = agora
        self.simulador.last_connection_type = 'wifi'
        self.simulador.wifi_ssid = 'Caminhao-QWE1A23'
        self.simulador.save(update_fields=['last_seen_at', 'last_connection_type', 'wifi_ssid'])

        # 3) Planejada com a placa REAL: e so iniciar e ligar a placa.
        planejada = Shipment.objects.create(
            origin=self.fazenda, destination=self.cd_recife, vehicle=self.caminhao2, device=self.placa_real,
            created_by=operador, status='planned', started_at=agora + timedelta(hours=1),
        )
        ShipmentItem.objects.create(shipment=planejada, fruit=self.banana, lot='BN-3110-02', quantity_kg=Decimal('6000'))

        return {'concluida': concluida, 'ativa': ativa, 'planejada': planejada}

    # --- Saida -----------------------------------------------------------

    def resumo(self, senha, senha_gerada, chaves, viagens):
        ok, aviso, w = self.style.SUCCESS, self.style.WARNING, self.stdout.write
        w(ok('\nSeed aplicada.'))
        w(f'  Usuarios (senha: {senha}){" -- gerada agora, anote" if senha_gerada else ""}:')
        for email, *_ in USUARIOS:
            w(f'    {email}')
        w('  Chaves das placas (X-Device-Key) -- aparecem so agora, anote:')
        for uid, chave in chaves.items():
            w(f'    {uid}: {chave}')
        ativa = viagens['ativa']
        w(f'  Viagens: concluida #{viagens["concluida"].id} | em andamento #{ativa.id} '
          f'({ativa.readings.count()} leituras, {ativa.alerts.count()} alertas) | '
          f'planejada #{viagens["planejada"].id} (placa real VSF-001)')
        w(aviso('  Atencao: os parametros das frutas estao ATIVOS so para a demonstracao; '
                'os valores ainda estao "A CONFERIR" na fonte.'))
