from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Dispositivo(models.Model):
    nome = models.CharField(max_length=100)
    identificador = models.CharField(max_length=100, unique=True)
    thingspeak_channel_id = models.CharField(max_length=20, blank=True)
    situacao = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.identificador})'


class Leitura(models.Model):
    """
    Uma medicao do sensor (temperatura e umidade) em um instante.

    - `medido_em`: hora em que o SENSOR mediu (e a que vale para o historico).
    - `recebido_em`: hora em que o servidor recebeu (util para achar atrasos).
    - `origem_id`: identificador da leitura na origem (o `entry_id` do ThingSpeak).
      Com ele, sincronizar duas vezes a mesma leitura nao duplica nada.
    """

    dispositivo = models.ForeignKey(Dispositivo, on_delete=models.PROTECT, related_name='leituras')
    temperatura = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(-50), MaxValueValidator(100)],
    )
    umidade = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    medido_em = models.DateTimeField()
    recebido_em = models.DateTimeField(auto_now_add=True)
    origem_id = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-medido_em']
        indexes = [
            # Consulta mais comum: historico de um dispositivo por periodo.
            models.Index(fields=['dispositivo', '-medido_em'], name='leitura_disp_medido_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['dispositivo', 'origem_id'],
                condition=Q(origem_id__isnull=False),
                name='leitura_unica_por_origem',
            ),
        ]

    def __str__(self):
        return f'{self.dispositivo.identificador} {self.temperatura}°C {self.umidade}% @ {self.medido_em:%d/%m %H:%M}'
