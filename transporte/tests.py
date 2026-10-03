from decimal import Decimal

from django.test import TestCase

from dominio.models import ConfiguracaoLimite, Fruta
from piADS04.tests_utils import montar_cenario

from .services import CargaIncompativel, faixa_ideal, faixa_ideal_de_frutas


class FaixaIdealTest(TestCase):
    def setUp(self):
        self.c = montar_cenario()

    def test_uma_fruta_usa_a_propria_faixa(self):
        faixa = faixa_ideal(self.c['transporte'])
        self.assertEqual((faixa.temperatura_minima, faixa.temperatura_maxima), (Decimal('8'), Decimal('12')))

    def test_carga_mista_usa_a_intersecao(self):
        uva = Fruta.objects.create(nome='Uva')
        ConfiguracaoLimite.objects.create(
            fruta=uva, temperatura_minima=Decimal('10'), temperatura_maxima=Decimal('14'),
            umidade_minima=Decimal('85'), umidade_maxima=Decimal('95'),
            margem_critica_temperatura=Decimal('2'),
        )
        faixa = faixa_ideal_de_frutas([self.c['fruta'].id, uva.id])
        self.assertEqual((faixa.temperatura_minima, faixa.temperatura_maxima), (Decimal('10'), Decimal('12')))
        self.assertEqual((faixa.umidade_minima, faixa.umidade_maxima), (Decimal('85'), Decimal('90')))
        self.assertEqual(faixa.margem_critica_temperatura, Decimal('2'))  # a mais rigorosa

    def test_frutas_sem_faixa_em_comum_levantam_erro(self):
        gelada = Fruta.objects.create(nome='Fruta gelada')
        ConfiguracaoLimite.objects.create(
            fruta=gelada, temperatura_minima=Decimal('0'), temperatura_maxima=Decimal('4'),
            umidade_minima=Decimal('90'), umidade_maxima=Decimal('95'),
        )
        with self.assertRaises(CargaIncompativel):
            faixa_ideal_de_frutas([self.c['fruta'].id, gelada.id])

    def test_sem_limites_cadastrados_devolve_none(self):
        outra = Fruta.objects.create(nome='Sem limite')
        self.assertIsNone(faixa_ideal_de_frutas([outra.id]))
