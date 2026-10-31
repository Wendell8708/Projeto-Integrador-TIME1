from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from alertas.models import Alert
from piADS04.tests_utils import montar_cenario
from transporte.models import Shipment

from .models import Device, DeviceCredential, Reading, ShockEvent

URL = '/api/v1/iot/telemetry/batch'


def leitura(seq, minuto, temperatura='10.5', umidade='85'):
    return {'sequence': seq, 'recorded_at': f'2026-10-31T10:{minuto:02d}:00Z',
            'temperature_c': temperatura, 'humidity_pct': umidade, 'impact_peak_g': '0.4'}


class TelemetryBatchTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.c = montar_cenario()
        self.client.credentials(HTTP_X_DEVICE_KEY=self.c['chave'])

    def lote(self, readings=(), shocks=(), **extra):
        corpo = {'device_uid': 'esp32-teste', 'shipment_id': self.c['viagem'].id, 'network': 'wifi',
                 'readings': list(readings), 'shocks': list(shocks), **extra}
        return self.client.post(URL, corpo, format='json')

    def test_lote_valido_grava_e_confirma_no_formato_do_plano(self):
        resposta = self.lote([leitura(1001, 0), leitura(1002, 5)],
                             [{'event_id': 'evt-001', 'recorded_at': '2026-10-31T10:02:00Z', 'impact_peak_g': '1.1'}])
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'data': {'accepted_reading_sequences': [1001, 1002],
                                                    'accepted_shock_ids': ['evt-001']}})
        self.assertEqual(Reading.objects.count(), 2)
        self.assertEqual(ShockEvent.objects.count(), 1)

    def test_reenvio_nao_duplica_e_confirma_de_novo(self):
        self.lote([leitura(1, 0)])
        resposta = self.lote([leitura(1, 0), leitura(2, 5)])
        self.assertEqual(resposta.data['accepted_reading_sequences'], [1, 2])
        self.assertEqual(Reading.objects.count(), 2)

    def test_lote_fora_de_ordem_gera_o_mesmo_alerta(self):
        self.lote([leitura(3, 10, '14'), leitura(1, 0, '10'), leitura(2, 5, '14')])
        self.assertEqual(Alert.objects.filter(type='temperature').count(), 1)

    def test_impacto_acima_do_limite_gera_alerta(self):
        self.lote(shocks=[{'event_id': 'e1', 'recorded_at': '2026-10-31T10:02:00Z', 'impact_peak_g': '3.1'}])
        self.assertEqual(Alert.objects.get().type, 'shock')

    def test_sem_chave_401(self):
        self.client.credentials()
        self.assertEqual(self.lote([leitura(1, 0)]).status_code, 401)

    def test_chave_errada_ou_revogada_401(self):
        self.client.credentials(HTTP_X_DEVICE_KEY='chave-inventada')
        self.assertEqual(self.lote([leitura(1, 0)]).status_code, 401)
        DeviceCredential.gerar(self.c['dispositivo'])  # gera nova: a antiga fica revogada
        self.client.credentials(HTTP_X_DEVICE_KEY=self.c['chave'])
        self.assertEqual(self.lote([leitura(1, 0)]).status_code, 401)

    def test_jwt_de_usuario_nao_serve_para_a_rota_da_placa(self):
        from django.contrib.auth.models import User
        from rest_framework_simplejwt.tokens import RefreshToken
        token = RefreshToken.for_user(User.objects.create_superuser('root', 'r@example.com', 'x')).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.lote([leitura(1, 0)]).status_code, 401)

    def test_placa_nao_grava_na_viagem_de_outra_placa(self):
        outra = Device.objects.create(uid='outra', name='Outra')
        _, chave_outra = DeviceCredential.gerar(outra)
        self.client.credentials(HTTP_X_DEVICE_KEY=chave_outra)
        resposta = self.lote([leitura(1, 0)], device_uid='outra')
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Reading.objects.count(), 0)

    def test_device_uid_diferente_da_chave_e_recusado(self):
        self.assertEqual(self.lote([leitura(1, 0)], device_uid='impostor').status_code, 400)

    def test_viagem_planejada_nao_recebe(self):
        Shipment.objects.filter(pk=self.c['viagem'].pk).update(status='planned')
        self.assertEqual(self.lote([leitura(1, 0)]).status_code, 400)

    def test_viagem_encerrada_ainda_recebe_dado_atrasado(self):
        Shipment.objects.filter(pk=self.c['viagem'].pk).update(status='completed')
        self.assertEqual(self.lote([leitura(1, 0)]).status_code, 200)

    def test_valor_impossivel_e_recusado_com_400(self):
        self.assertEqual(self.lote([leitura(1, 0, umidade='120')]).status_code, 400)
        self.assertEqual(Reading.objects.count(), 0)

    def test_lote_vazio_e_recusado(self):
        self.assertEqual(self.lote().status_code, 400)

    @override_settings(IOT_MAX_BATCH_ITEMS=3)
    def test_lote_grande_demais_e_recusado(self):
        self.assertEqual(self.lote([leitura(i, i) for i in range(4)]).status_code, 400)

    def test_lote_atualiza_ultima_comunicacao(self):
        self.lote([leitura(1, 0)])
        dispositivo = Device.objects.get(pk=self.c['dispositivo'].pk)
        self.assertTrue(dispositivo.online)
        self.assertEqual(dispositivo.last_connection_type, 'wifi')


class HeartbeatAndConfigTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.c = montar_cenario()
        self.client.credentials(HTTP_X_DEVICE_KEY=self.c['chave'])

    def test_heartbeat_marca_online_e_guarda_ssid(self):
        resposta = self.client.post('/api/v1/iot/heartbeat', {'network': 'wifi', 'wifi_ssid': 'Caminhao-1'})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.data['online'])
        self.assertEqual(resposta.data['wifi_ssid'], 'Caminhao-1')

    def test_config_devolve_viagem_ativa_e_limites(self):
        corpo = self.client.get('/api/v1/iot/config').json()['data']
        self.assertEqual(corpo['shipment_id'], self.c['viagem'].id)
        self.assertEqual(corpo['limits']['temperature_max_c'], 12.0)

    def test_config_sem_viagem_ativa(self):
        Shipment.objects.update(status='planned')
        self.assertIsNone(self.client.get('/api/v1/iot/config').data['shipment_id'])


class DeviceCredentialTest(TestCase):
    def test_banco_guarda_so_o_hash(self):
        dispositivo = Device.objects.create(uid='x', name='x')
        credencial, chave = DeviceCredential.gerar(dispositivo)
        self.assertNotEqual(credencial.secret_hash, chave)
        self.assertEqual(credencial.secret_hash, DeviceCredential.hash_da_chave(chave))
