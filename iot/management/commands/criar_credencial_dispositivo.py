"""
Gera a chave de acesso de uma placa (e revoga a anterior, se houver).

Uso:  python manage.py criar_credencial_dispositivo VSF-001
      python manage.py criar_credencial_dispositivo VSF-001 --nome "Placa do caminhao 1"

A chave aparece UMA vez. Copie para a configuracao da placa (cabecalho X-Device-Key).
O banco guarda so o hash: se perder a chave, gere outra.
"""

from django.core.management.base import BaseCommand

from iot.models import Device, DeviceCredential


class Command(BaseCommand):
    help = 'Gera (ou troca) a chave X-Device-Key de uma placa.'

    def add_arguments(self, parser):
        parser.add_argument('uid', help='Identificador da placa (ex.: VSF-001). Cria a placa se nao existir.')
        parser.add_argument('--nome', default='', help='Nome da placa, usado so se ela for criada agora.')

    def handle(self, *args, **options):
        dispositivo, criado = Device.objects.get_or_create(
            uid=options['uid'], defaults={'name': options['nome'] or options['uid']},
        )
        _, chave = DeviceCredential.gerar(dispositivo)
        if criado:
            self.stdout.write(f'Placa {dispositivo.uid} criada.')
        self.stdout.write(self.style.SUCCESS(f'Chave da placa {dispositivo.uid} (guarde agora, nao aparece de novo):'))
        self.stdout.write(chave)
