from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from iot.services import registrar_leitura
from piADS04.tests_utils import montar_cenario

from .models import Alerta
from .services import classificar


class ClassificarTest(SimpleTestCase):
    """Funcao pura: faixa 8 a 12, margem critica 3."""

    def chamar(self, valor):
        return classificar(Decimal(valor), Decimal('8'), Decimal('12'), Decimal('3'))

    def test_dentro_da_faixa_e_normal(self):
        self.assertEqual(self.chamar('10'), ('normal', None))
        self.assertEqual(self.chamar('8'), ('normal', None))   # limite inclusivo
        self.assertEqual(self.chamar('12'), ('normal', None))

    def test_pouco_fora_e_atencao(self):
        self.assertEqual(self.chamar('7'), ('atencao', Decimal('8')))
        self.assertEqual(self.chamar('14'), ('atencao', Decimal('12')))
        self.assertEqual(self.chamar('15'), ('atencao', Decimal('12')))  # exatamente a margem ainda e atencao

    def test_muito_fora_e_critico(self):
        self.assertEqual(self.chamar('4'), ('critico', Decimal('8')))
        self.assertEqual(self.chamar('15.01'), ('critico', Decimal('12')))


class AvaliarLeituraTest(TestCase):
    def setUp(self):
        self.c = montar_cenario()
        self.agora = self.c['inicio'] + timedelta(minutes=10)

    def enviar(self, minutos, temperatura, umidade='85', origem_id=None):
        return registrar_leitura(
            self.c['dispositivo'], Decimal(temperatura), Decimal(umidade),
            self.agora + timedelta(minutes=minutos), origem_id,
        )

    def test_leitura_normal_nao_gera_alerta(self):
        self.enviar(0, '10')
        self.assertEqual(Alerta.objects.count(), 0)

    def test_uma_leitura_fora_nao_alerta_por_causa_da_tolerancia_do_sensor(self):
        self.enviar(0, '10')
        self.enviar(1, '14')  # so UMA fora da faixa
        self.assertEqual(Alerta.objects.count(), 0)

    def test_duas_leituras_fora_abrem_um_alerta(self):
        self.enviar(0, '14')
        self.enviar(1, '14')
        alerta = Alerta.objects.get()
        self.assertEqual((alerta.tipo, alerta.severidade, alerta.status), ('temperatura', 'atencao', 'aberto'))
        self.assertEqual(alerta.limite_violado, Decimal('12'))

    def test_nao_duplica_alerta_enquanto_continua_fora(self):
        for minuto in range(5):
            self.enviar(minuto, '14')
        self.assertEqual(Alerta.objects.count(), 1)

    def test_alerta_sobe_para_critico_se_piorar(self):
        self.enviar(0, '14')
        self.enviar(1, '14')
        self.enviar(2, '20')
        alerta = Alerta.objects.get()
        self.assertEqual(alerta.severidade, 'critico')

    def test_alerta_e_resolvido_quando_volta_ao_normal(self):
        self.enviar(0, '14')
        self.enviar(1, '14')
        self.enviar(2, '10')
        alerta = Alerta.objects.get()
        self.assertEqual(alerta.status, 'resolvido')
        self.assertIsNotNone(alerta.resolvido_em)

    def test_umidade_gera_alerta_independente_da_temperatura(self):
        self.enviar(0, '10', umidade='50')
        self.enviar(1, '10', umidade='50')
        alerta = Alerta.objects.get()
        self.assertEqual((alerta.tipo, alerta.severidade), ('umidade', 'critico'))

    def test_leitura_repetida_pelo_origem_id_nao_duplica(self):
        _, criada1 = self.enviar(0, '10', origem_id=123)
        _, criada2 = self.enviar(0, '10', origem_id=123)
        self.assertTrue(criada1)
        self.assertFalse(criada2)

    def test_leitura_sem_transporte_em_andamento_e_gravada_mas_nao_avaliada(self):
        self.c['transporte'].status = 'concluido'
        self.c['transporte'].save()
        self.enviar(0, '30')
        self.enviar(1, '30')
        self.assertEqual(Alerta.objects.count(), 0)
