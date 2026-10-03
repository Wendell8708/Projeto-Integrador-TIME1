from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Local(models.Model):
    TIPO_CHOICES = [
        ('fazenda', 'Fazenda'),
        ('centro_distribuicao', 'Centro de Distribuição'),
        ('armazem', 'Armazém'),
    ]

    nome = models.CharField(max_length=150)
    tipo_local = models.CharField(max_length=30, choices=TIPO_CHOICES)
    endereco = models.CharField(max_length=255, blank=True)
    situacao = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.get_tipo_local_display()})'


class Veiculo(models.Model):
    placa = models.CharField(max_length=10, unique=True)
    modelo = models.CharField(max_length=100, blank=True)
    situacao = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['placa']

    def __str__(self):
        return self.placa


class Fruta(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    situacao = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ConfiguracaoLimite(models.Model):
    """
    Faixa IDEAL de temperatura e umidade para transportar uma fruta.

    Como o status e calculado (ver alertas/services.py):
      - dentro de [minimo, maximo]                       -> normal
      - fora da faixa, ate `margem_critica` de distancia -> atencao
      - alem de `margem_critica` da faixa                -> critico

    Exemplo: faixa 8 a 12 C com margem 3 -> 7 C e atencao; 4 C e critico.
    """

    fruta = models.ForeignKey(Fruta, on_delete=models.CASCADE, related_name='limites')

    temperatura_minima = models.DecimalField(max_digits=5, decimal_places=2)
    temperatura_maxima = models.DecimalField(max_digits=5, decimal_places=2)
    margem_critica_temperatura = models.DecimalField(
        max_digits=5, decimal_places=2, default=3,
        help_text='Distancia (em graus C) alem da faixa ideal a partir da qual o alerta e critico.',
    )

    umidade_minima = models.DecimalField(max_digits=5, decimal_places=2)
    umidade_maxima = models.DecimalField(max_digits=5, decimal_places=2)
    margem_critica_umidade = models.DecimalField(
        max_digits=5, decimal_places=2, default=10,
        help_text='Distancia (em pontos percentuais) alem da faixa ideal a partir da qual o alerta e critico.',
    )

    fonte = models.CharField(
        max_length=255, blank=True, default='',
        help_text='De onde veio a faixa (Embrapa, CEAGESP, artigo...). Importante para rastrear o dado.',
    )
    situacao = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(temperatura_minima__lt=F('temperatura_maxima')),
                name='limite_temperatura_min_menor_que_max',
            ),
            models.CheckConstraint(
                condition=Q(umidade_minima__lt=F('umidade_maxima')),
                name='limite_umidade_min_menor_que_max',
            ),
            # So pode existir UMA configuracao ativa por fruta; ela e a usada nos alertas.
            models.UniqueConstraint(
                fields=['fruta'],
                condition=Q(situacao=True),
                name='um_limite_ativo_por_fruta',
            ),
        ]

    def clean(self):
        # Mensagem amigavel no admin/formularios (a constraint protege o banco).
        if self.temperatura_minima is not None and self.temperatura_maxima is not None:
            if self.temperatura_minima >= self.temperatura_maxima:
                raise ValidationError('A temperatura mínima deve ser menor que a máxima.')
        if self.umidade_minima is not None and self.umidade_maxima is not None:
            if self.umidade_minima >= self.umidade_maxima:
                raise ValidationError('A umidade mínima deve ser menor que a máxima.')

    def __str__(self):
        return f'Limites de {self.fruta.nome}'
