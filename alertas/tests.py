from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from iot.models import Reading
from iot.services import register_reading, register_shock
from piADS04.tests_utils import montar_cenario

from .models import Alert
from .services import classify


class ClassifyTest(SimpleTestCase):
    """Funcao pura: faixa 8 a 12, margem critica 3."""

    def chamar(self, valor):
        return classify(Decimal(valor), Decimal('8'), Decimal('12'), Decimal('3'))

    def test_dentro_da_faixa_e_normal(self):
        self.assertEqual(self.chamar('10'), ('normal', None))
        self.assertEqual(self.chamar('8'), ('normal', None))   # limite inclusivo
        self.assertEqual(self.chamar('12'), ('normal', None))

    def test_pouco_fora_e_warning(self):
        self.assertEqual(self.chamar('7'), ('warning', Decimal('8')))
        self.assertEqual(self.chamar('14'), ('warning', Decimal('12')))
        self.assertEqual(self.chamar('15'), ('warning', Decimal('12')))  # exatamente a margem ainda e warning

    def test_muito_fora_e_critical(self):
        self.assertEqual(self.chamar('4'), ('critical', Decimal('8')))
        self.assertEqual(self.chamar('15.01'), ('critical', Decimal('12')))


class EvaluateReadingTest(TestCase):
    def setUp(self):
        self.c = montar_cenario()
        self.agora = self.c['inicio'] + timedelta(minutes=10)
        self.seq = 0

    def enviar(self, minutos, temperatura, umidade='85', sequence=None):
        """Simula o que a placa faz: cada leitura tem um sequence novo (ou repetido, num reenvio)."""
        self.seq += 1
        return register_reading(
            device=self.c['dispositivo'], shipment=self.c['viagem'],
            sequence=sequence if sequence is not None else self.seq,
            recorded_at=self.agora + timedelta(minutes=minutos),
            temperature_c=Decimal(temperatura), humidity_pct=Decimal(umidade),
        )

    def test_leitura_normal_nao_gera_alerta(self):
        self.enviar(0, '10')
        self.assertEqual(Alert.objects.count(), 0)

    def test_uma_leitura_fora_nao_alerta_por_causa_da_tolerancia_do_sensor(self):
        self.enviar(0, '10')
        self.enviar(1, '14')
        self.assertEqual(Alert.objects.count(), 0)

    def test_duas_leituras_fora_abrem_um_alerta(self):
        self.enviar(0, '14')
        self.enviar(1, '14')
        alerta = Alert.objects.get()
        self.assertEqual((alerta.type, alerta.severity, alerta.status), ('temperature', 'warning', 'open'))
        self.assertEqual(alerta.violated_limit, Decimal('12'))
        self.assertIn('acima do limite', alerta.message)

    def test_nao_duplica_alerta_enquanto_continua_fora(self):
        for minuto in range(5):
            self.enviar(minuto, '14')
        self.assertEqual(Alert.objects.count(), 1)

    def test_alerta_sobe_para_critico_se_piorar(self):
        self.enviar(0, '14')
        self.enviar(1, '14')
        self.enviar(2, '20')
        self.assertEqual(Alert.objects.get().severity, 'critical')

    def test_alerta_e_resolvido_quando_volta_ao_normal(self):
        self.enviar(0, '14')
        self.enviar(1, '14')
        self.enviar(2, '10')
        alerta = Alert.objects.get()
        self.assertEqual(alerta.status, 'resolved')
        self.assertIsNotNone(alerta.resolved_at)

    def test_umidade_gera_alerta_independente_da_temperatura(self):
        self.enviar(0, '10', umidade='50')
        self.enviar(1, '10', umidade='50')
        alerta = Alert.objects.get()
        self.assertEqual((alerta.type, alerta.severity), ('humidity', 'critical'))

    def test_reenvio_com_o_mesmo_sequence_nao_duplica(self):
        leitura1, criada1 = self.enviar(0, '10', sequence=500)
        leitura2, criada2 = self.enviar(0, '10', sequence=500)
        self.assertTrue(criada1)
        self.assertFalse(criada2)
        self.assertEqual(leitura1.pk, leitura2.pk)
        self.assertEqual(Reading.objects.count(), 1)

    def test_reenvio_nao_reavalia_nem_duplica_alerta(self):
        self.enviar(0, '14', sequence=1)
        self.enviar(1, '14', sequence=2)
        self.enviar(1, '14', sequence=2)
        self.assertEqual(Alert.objects.count(), 1)

    def test_umidade_impossivel_e_recusada_pelo_banco(self):
        with self.assertRaises(IntegrityError):
            self.enviar(0, '10', umidade='120')
        self.assertEqual(Reading.objects.count(), 0)

    def test_leitura_com_relogio_errado_continua_na_viagem_certa(self):
        leitura, _ = self.enviar(-60 * 24 * 365, '10')  # relogio um ano atrasado
        self.assertEqual(leitura.shipment, self.c['viagem'])

    def test_dado_atrasado_depois_de_encerrar_ainda_gera_alerta(self):
        self.c['viagem'].status = 'completed'
        self.c['viagem'].save()
        self.enviar(0, '30')
        self.enviar(1, '30')
        self.assertEqual(Alert.objects.count(), 1)


class EvaluateShockTest(TestCase):
    def setUp(self):
        self.c = montar_cenario()  # impacto maximo da manga: 2.5 g

    def impacto(self, event_id, pico):
        return register_shock(device=self.c['dispositivo'], shipment=self.c['viagem'], event_id=event_id,
                              recorded_at=self.c['inicio'] + timedelta(minutes=5), impact_peak_g=Decimal(pico))

    def test_impacto_dentro_do_limite_nao_alerta(self):
        self.impacto('e1', '2.0')
        self.assertEqual(Alert.objects.count(), 0)

    def test_impacto_acima_do_limite_alerta_na_hora(self):
        self.impacto('e1', '3.1')
        alerta = Alert.objects.get()
        self.assertEqual((alerta.type, alerta.severity, alerta.measured_value), ('shock', 'warning', Decimal('3.1')))

    def test_impacto_muito_forte_e_critico(self):
        self.impacto('e1', '4.0')  # acima de 1.5 x 2.5
        self.assertEqual(Alert.objects.get().severity, 'critical')

    def test_varios_impactos_atualizam_o_mesmo_alerta_com_o_maior_pico(self):
        self.impacto('e1', '3.0')
        self.impacto('e2', '4.2')
        self.impacto('e3', '2.8')
        alerta = Alert.objects.get()
        self.assertEqual((alerta.measured_value, alerta.severity), (Decimal('4.2'), 'critical'))

    def test_mesmo_event_id_nao_duplica(self):
        _, criado1 = self.impacto('e1', '3.0')
        _, criado2 = self.impacto('e1', '3.0')
        self.assertEqual((criado1, criado2), (True, False))
