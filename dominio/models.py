from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Location(models.Model):
    """Local de origem ou destino de uma viagem (fazenda, centro de distribuicao, armazem)."""

    TYPE_CHOICES = [
        ('farm', 'Fazenda'),
        ('distribution_center', 'Centro de Distribuição'),
        ('warehouse', 'Armazém'),
    ]

    name = models.CharField(max_length=150)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'locations'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_type_display()})'


class Vehicle(models.Model):
    plate = models.CharField(max_length=10, unique=True)
    model = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicles'
        ordering = ['plate']

    def __str__(self):
        return self.plate


class Fruit(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fruits'
        ordering = ['name']

    def __str__(self):
        return self.name


class FruitParameter(models.Model):
    """
    Faixa IDEAL de temperatura, umidade e impacto para transportar uma fruta.

    Como o nivel do alerta e calculado (ver alertas/services.py):
      - dentro de [min, max]                         -> normal
      - fora da faixa, ate a margem critica          -> warning (atencao)
      - alem da margem critica                       -> critical (critico)

    Exemplo: faixa 8 a 12 C com margem 3 -> 14 C e warning; 16 C e critical.
    """

    fruit = models.ForeignKey(Fruit, on_delete=models.CASCADE, related_name='parameters')

    temperature_min_c = models.DecimalField(max_digits=5, decimal_places=2)
    temperature_max_c = models.DecimalField(max_digits=5, decimal_places=2)
    temperature_critical_margin_c = models.DecimalField(
        max_digits=5, decimal_places=2, default=3,
        help_text='Distancia (em graus C) alem da faixa a partir da qual o alerta e critico.',
    )

    humidity_min_pct = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_max_pct = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_critical_margin_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=10,
        help_text='Distancia (em pontos percentuais) alem da faixa a partir da qual o alerta e critico.',
    )

    # Maior aceleracao dinamica (sem a gravidade) aceitavel num impacto, em g.
    impact_max_g = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    source = models.CharField(
        max_length=255, blank=True, default='',
        help_text='De onde veio a faixa (Embrapa, CEAGESP, artigo...). Importante para rastrear o dado.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fruit_parameters'
        constraints = [
            models.CheckConstraint(
                condition=Q(temperature_min_c__lt=F('temperature_max_c')),
                name='fruit_parameters_temperature_min_lt_max',
            ),
            models.CheckConstraint(
                condition=Q(humidity_min_pct__lt=F('humidity_max_pct')),
                name='fruit_parameters_humidity_min_lt_max',
            ),
            models.CheckConstraint(
                condition=Q(humidity_min_pct__gte=0, humidity_max_pct__lte=100),
                name='fruit_parameters_humidity_0_100',
            ),
            models.CheckConstraint(
                condition=Q(impact_max_g__isnull=True) | Q(impact_max_g__gt=0),
                name='fruit_parameters_impact_positive',
            ),
            # So pode existir UM parametro ativo por fruta; e ele que vale para os alertas.
            models.UniqueConstraint(
                fields=['fruit'], condition=Q(is_active=True),
                name='fruit_parameters_one_active_per_fruit',
            ),
        ]

    def clean(self):
        # Mensagem amigavel no admin (as constraints protegem o banco).
        if self.temperature_min_c is not None and self.temperature_max_c is not None:
            if self.temperature_min_c >= self.temperature_max_c:
                raise ValidationError('A temperatura mínima deve ser menor que a máxima.')
        if self.humidity_min_pct is not None and self.humidity_max_pct is not None:
            if self.humidity_min_pct >= self.humidity_max_pct:
                raise ValidationError('A umidade mínima deve ser menor que a máxima.')

    def __str__(self):
        return f'Parâmetros de {self.fruit.name}'
