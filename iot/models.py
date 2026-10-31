import hashlib
import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Device(models.Model):
    """Placa ESP32 que acompanha a carga."""

    CONNECTION_CHOICES = [('wifi', 'Wi-Fi'), ('2g', 'Rede celular 2G')]

    uid = models.CharField(max_length=100, unique=True, help_text='Identificador gravado na placa (ex.: VSF-001).')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, help_text='Ultima comunicacao da placa com a API.')
    last_connection_type = models.CharField(max_length=10, choices=CONNECTION_CHOICES, blank=True)
    # Nome da rede Wi-Fi que a placa usou. A SENHA do Wi-Fi nunca fica no banco.
    wifi_ssid = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'devices'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.uid})'

    @property
    def online(self):
        """Comunicou dentro da tolerancia (DEVICE_ONLINE_TOLERANCE_MINUTES)?"""
        if self.last_seen_at is None:
            return False
        tolerancia = timezone.timedelta(minutes=settings.DEVICE_ONLINE_TOLERANCE_MINUTES)
        return timezone.now() - self.last_seen_at <= tolerancia


class DeviceCredential(models.Model):
    """
    Chave de acesso de UMA placa, separada do login das pessoas (plano, secao 3.4).

    O banco guarda so o SHA-256 da chave. A chave em si aparece uma unica vez,
    quando e criada (comando `criar_credencial_dispositivo`). Como ela e longa e
    aleatoria (256 bits), um hash rapido como o SHA-256 ja e seguro aqui.
    """

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='credentials')
    secret_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'device_credentials'

    def __str__(self):
        situacao = 'revogada' if self.revoked_at else 'ativa'
        return f'Credencial {situacao} de {self.device.uid}'

    @staticmethod
    def hash_da_chave(chave):
        return hashlib.sha256(chave.encode()).hexdigest()

    @classmethod
    def gerar(cls, device):
        """Revoga as chaves anteriores da placa, cria uma nova e devolve (credencial, chave_em_texto)."""
        cls.objects.filter(device=device, revoked_at__isnull=True).update(revoked_at=timezone.now())
        chave = secrets.token_urlsafe(32)
        credencial = cls.objects.create(device=device, secret_hash=cls.hash_da_chave(chave))
        return credencial, chave


class Reading(models.Model):
    """
    Uma medicao periodica do sensor durante uma viagem.

    - `recorded_at`: hora em que o SENSOR mediu (vale para o historico e os graficos).
    - `received_at`: hora em que o servidor recebeu (mostra o que chegou atrasado).
    - `sequence`: contador da placa. Com UNIQUE(device, sequence), reenviar a
      mesma leitura nunca duplica. A placa guarda o contador na flash e nunca volta a 1.
    - `shipment`: a viagem. E uma chave (e nao o horario) para que relogio errado
      nao tire a leitura da viagem e dado atrasado ainda entre nela.
    """

    NETWORK_CHOICES = Device.CONNECTION_CHOICES

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
        return (f'{self.device.uid} #{self.sequence} '
                f'{self.temperature_c}°C {self.humidity_pct}% @ {self.recorded_at:%d/%m %H:%M}')


class ShockEvent(models.Model):
    """
    Impacto detectado ENTRE as leituras (pico do acelerometro acima do limiar da placa).

    `event_id` e o identificador que a placa da ao evento. Com
    UNIQUE(device, event_id), reenviar o mesmo evento nunca duplica.
    """

    shipment = models.ForeignKey('transporte.Shipment', on_delete=models.PROTECT, related_name='shock_events')
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name='shock_events')
    event_id = models.CharField(max_length=64)
    recorded_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    impact_peak_g = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        db_table = 'shock_events'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['shipment', '-recorded_at'], name='shocks_shipment_recorded_idx'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['device', 'event_id'], name='shock_events_unique_device_event'),
            models.CheckConstraint(condition=Q(impact_peak_g__gte=0), name='shock_events_impact_not_negative'),
        ]

    def __str__(self):
        return f'{self.device.uid} {self.event_id} {self.impact_peak_g} g @ {self.recorded_at:%d/%m %H:%M}'
