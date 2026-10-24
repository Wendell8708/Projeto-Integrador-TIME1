from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Device(models.Model):
    nome = models.CharField(max_length=100)
    identificador = models.CharField(max_length=100, unique=True)
    thingspeak_channel_id = models.CharField(max_length=20, blank=True)
    situacao = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'devices'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.identificador})'


class Reading(models.Model):
    """
    Uma medicao periodica do sensor (temperatura e umidade) durante uma viagem.

    - `recorded_at`: hora em que o SENSOR mediu (vale para o historico).
    - `received_at`: hora em que o servidor recebeu (util para achar atrasos).
    - `sequence`: contador da placa. Com UNIQUE(device, sequence), reenviar a
      mesma leitura nunca duplica. A placa precisa guardar o contador na flash
      e nunca reiniciar em 1.
    - `shipment`: a viagem a que a leitura pertence. E uma chave (e nao o horario)
      para que relogio errado nao tire a leitura da viagem e para que dado
      atrasado, chegando depois de a viagem terminar, ainda entre nela.
    """

    NETWORK_CHOICES = [('wifi', 'Wi-Fi'), ('2g', 'Rede celular 2G')]

    shipment = models.ForeignKey('transporte.Shipment', on_delete=models.PROTECT, related_name='readings')
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name='readings')
    sequence = models.PositiveBigIntegerField()
    recorded_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    temperature_c = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(-40), MaxValueValidator(80)],
    )
    humidity_pct = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    # Maior pico de aceleracao DINAMICA (sem a gravidade) no intervalo desta leitura.
    impact_peak_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    network = models.CharField(max_length=10, choices=NETWORK_CHOICES, blank=True)

    class Meta:
        db_table = 'readings'
        ordering = ['-recorded_at']
        indexes = [
            # Consulta mais comum do dashboard: historico de uma viagem por periodo.
            models.Index(fields=['shipment', '-recorded_at'], name='readings_shipment_recorded_idx'),
            models.Index(fields=['device', '-recorded_at'], name='readings_device_recorded_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['device', 'sequence'], name='readings_unique_device_sequence'),
            # CHECKs no banco: valem para QUALQUER caminho de gravacao (API, MQTT, shell),
            # inclusive o objects.create() da ingestao, que nao passa pelos validators.
            models.CheckConstraint(condition=Q(humidity_pct__gte=0, humidity_pct__lte=100),
                                   name='readings_humidity_0_100'),
            models.CheckConstraint(condition=Q(temperature_c__gte=-40, temperature_c__lte=80),
                                   name='readings_temperature_range'),
            models.CheckConstraint(condition=Q(impact_peak_g__isnull=True) | Q(impact_peak_g__gte=0),
                                   name='readings_impact_not_negative'),
        ]

    def __str__(self):
        return (f'{self.device.identificador} #{self.sequence} '
                f'{self.temperature_c}°C {self.humidity_pct}% @ {self.recorded_at:%d/%m %H:%M}')
