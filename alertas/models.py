from django.conf import settings
from django.db import models
from django.db.models import Q


class Alert(models.Model):
    TYPE_CHOICES = [
        ('temperature', 'Temperatura'),
        ('humidity', 'Umidade'),
        ('shock', 'Impacto'),
    ]
    SEVERITY_CHOICES = [
        ('warning', 'Atenção'),
        ('critical', 'Crítico'),
    ]
    STATUS_CHOICES = [
        ('open', 'Aberto'),
        ('acknowledged', 'Reconhecido'),
        ('resolved', 'Resolvido'),
    ]

    shipment = models.ForeignKey('transporte.Shipment', on_delete=models.PROTECT, related_name='alerts')
    # O que disparou o alerta: uma leitura (temperatura/umidade) OU um evento de impacto.
    reading = models.ForeignKey('iot.Reading', on_delete=models.PROTECT, null=True, blank=True, related_name='alerts')
    shock_event = models.ForeignKey('iot.ShockEvent', on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='alerts')

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='open')
    message = models.CharField(max_length=255, blank=True)

    # Guardamos os valores NA HORA do alerta: se a faixa da fruta mudar depois,
    # o historico do alerta continua fiel ao que aconteceu.
    measured_value = models.DecimalField(max_digits=6, decimal_places=2)
    violated_limit = models.DecimalField(max_digits=6, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='alerts_acknowledged',
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shipment', 'status'], name='alerts_shipment_status_idx'),
        ]
        constraints = [
            # No maximo UM alerta ativo (aberto ou reconhecido) por viagem e tipo:
            # evita 500 alertas iguais enquanto a temperatura continua fora da faixa.
            models.UniqueConstraint(
                fields=['shipment', 'type'], condition=Q(status__in=['open', 'acknowledged']),
                name='alerts_one_active_per_shipment_type',
            ),
            # Todo alerta tem origem: uma leitura ou um evento de impacto.
            models.CheckConstraint(
                condition=Q(reading__isnull=False) | Q(shock_event__isnull=False),
                name='alerts_has_source',
            ),
        ]

    def __str__(self):
        return f'Alerta {self.get_severity_display()} de {self.get_type_display()} (viagem #{self.shipment_id})'
