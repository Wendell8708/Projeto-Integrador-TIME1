"""
Carrega frutas e faixas ideais INICIAIS de temperatura e umidade para transporte.

Uso:  python manage.py carregar_limites_iniciais

ATENCAO: os valores abaixo sao uma PROPOSTA inicial, tirada de resumos de
fontes tecnicas (Embrapa, CEAGESP, USDA Handbook 66 e artigos). Nao foi possivel
abrir os PDFs originais da Embrapa (servidor fora do ar na pesquisa), entao
TODA faixa e carregada INATIVA (situacao=False) e marcada "A CONFERIR" no campo
`fonte`. Inativa significa que ela NAO gera alertas ainda.

Fluxo: conferir cada faixa na fonte -> ajustar valores -> ativar (situacao=True)
pelo admin ou por PATCH /api/v1/limites/{id}/.

O comando e idempotente: rodar de novo atualiza as mesmas frutas, sem duplicar,
e NAO reativa nem sobrescreve faixas que voce ja ativou.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from dominio.models import ConfiguracaoLimite, Fruta

# nome, temp_min, temp_max, margem_temp, umid_min, umid_max, margem_umid, fonte
FAIXAS = [
    ('Uva de mesa', '0', '1', '2', '85', '95', '10',
     'A CONFERIR. Embrapa (0-1 C; 0 C e 90% UR) e USDA Handbook 66 (-1 a 0 C; 85-95% UR). '
     'ATENCAO: o DHT11 mede de 0 a 50 C e UR ate 90%, entao nao e confiavel para uva.'),
    ('Manga', '10', '13', '3', '85', '90', '10',
     'A CONFERIR. Embrapa (10-14 C para frutas tropicais; Tommy Atkins a 12 C e 85-90% UR) '
     'e USDA/UF (10-13 C, 85-90% UR). Depende do estadio de maturacao.'),
    ('Melão amarelo', '10', '12', '3', '85', '90', '10',
     'A CONFERIR. Embrapa (melao amarelo conservado a 10-12 C). Umidade NAO confirmada na fonte: '
     '85-90% e valor tipico de melao. CEAGESP cita 7-10 C para melao/melancia: divergencia a resolver.'),
    ('Goiaba', '7', '10', '3', '85', '95', '10',
     'A CONFERIR. UF/USDA: goiaba verde-madura a 8-10 C por 2-3 semanas, 90-95% UR; '
     'faixa de umidade assumida em torno de 90%.'),
    ('Banana', '13', '15', '3', '85', '95', '10',
     'A CONFERIR. Embrapa: 13-15 C com umidade minima de 85% (ate ~3 semanas). '
     'Limite maximo de umidade assumido.'),
]


class Command(BaseCommand):
    help = 'Carrega frutas e faixas ideais iniciais (INATIVAS, a conferir).'

    @transaction.atomic
    def handle(self, *args, **options):
        for nome, tmin, tmax, tmargem, umin, umax, umargem, fonte in FAIXAS:
            fruta, _ = Fruta.objects.get_or_create(nome=nome)

            # Nao mexe numa faixa que alguem ja conferiu e ativou.
            if ConfiguracaoLimite.objects.filter(fruta=fruta, situacao=True).exists():
                self.stdout.write(f'{nome}: ja tem faixa ativa, mantida.')
                continue

            ConfiguracaoLimite.objects.update_or_create(
                fruta=fruta, situacao=False,
                defaults={
                    'temperatura_minima': Decimal(tmin), 'temperatura_maxima': Decimal(tmax),
                    'margem_critica_temperatura': Decimal(tmargem),
                    'umidade_minima': Decimal(umin), 'umidade_maxima': Decimal(umax),
                    'margem_critica_umidade': Decimal(umargem),
                    'fonte': fonte,
                },
            )
            self.stdout.write(self.style.SUCCESS(f'{nome}: faixa carregada (INATIVA, a conferir).'))

        self.stdout.write(self.style.WARNING(
            'Lembrete: confira cada faixa na fonte e ative (situacao=True) so depois.'
        ))
