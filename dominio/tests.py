from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from alertas.models import Alert
from iot.models import Device, Reading
from transporte.models import Shipment

from .models import Fruit, FruitParameter


class FruitsApiTest(APITestCase):
    def setUp(self):
        self.client.force_authenticate(User.objects.create_superuser('root', 'root@example.com', 'x'))

    def test_fruta_traz_os_limites_ativos_no_formato_do_plano(self):
        call_command('carregar_limites_iniciais', stdout=StringIO())
        FruitParameter.objects.filter(fruit__name='Manga').update(is_active=True)
        frutas = {f['name']: f for f in self.client.get('/api/v1/fruits').json()['data']}
        self.assertEqual(frutas['Manga']['limits']['temperature_max_c'], '13.00')
        self.assertEqual(frutas['Manga']['limits']['impact_max_g'], '2.50')
        self.assertIsNone(frutas['Uva de mesa']['limits'])  # ainda inativa

    def test_dois_parametros_ativos_para_a_mesma_fruta_sao_recusados(self):
        fruta = Fruit.objects.create(name='Caju')
        dados = {'fruit': fruta.id, 'temperature_min_c': '5', 'temperature_max_c': '10',
                 'humidity_min_pct': '80', 'humidity_max_pct': '90', 'is_active': True}
        self.assertEqual(self.client.post('/api/v1/fruit-parameters', dados).status_code, 201)
        self.assertEqual(self.client.post('/api/v1/fruit-parameters', dados).status_code, 400)


class SeedTest(TestCase):
    def test_seed_cria_o_cenario_completo(self):
        saida = StringIO()
        call_command('seed', senha='Senha-Demo-123', stdout=saida)
        self.assertEqual(User.objects.filter(email__endswith='@example.com').count(), 3)
        self.assertEqual(Device.objects.count(), 2)
        self.assertEqual(set(Shipment.objects.values_list('status', flat=True)), {'completed', 'active', 'planned'})
        ativa = Shipment.objects.get(status='active')
        self.assertEqual(set(ativa.alerts.values_list('type', flat=True)), {'temperature', 'shock'})
        self.assertGreater(Reading.objects.count(), 90)
        self.assertIn('VSF-001:', saida.getvalue())

    def test_seed_nao_roda_duas_vezes_sem_reset(self):
        call_command('seed', senha='x', stdout=StringIO())
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('seed', senha='x', stdout=StringIO())
        call_command('seed', senha='x', reset=True, sim=True, stdout=StringIO())
        self.assertEqual(Alert.objects.filter(shipment__status='active').count(), 2)
