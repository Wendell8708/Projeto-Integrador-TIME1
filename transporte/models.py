from django.conf import settings
from django.db import models
from django.db.models import F, Q

from dominio.models import Fruit, Location, Vehicle
from iot.models import Device


class Shipment(models.Model):
    """
    A viagem: unidade central do monitoramento.

    Leituras, impactos e alertas pertencem a uma viagem (shipment.readings,
    shipment.shock_events, shipment.alerts).
    """

    STATUS_CHOICES = [
        ('planned', 'Planejada'),
        ('active', 'Em andamento'),
        ('completed', 'Concluída'),
        ('cancelled', 'Cancelada'),
    ]

    origin = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='shipments_from')
    destination = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='shipments_to')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='shipments')
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name='shipments')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='shipments_created',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    started_at = models.DateTimeField(help_text='Inicio previsto; vira o inicio REAL quando a viagem e iniciada.')
    ended_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shipments'
        ordering = ['-started_at']
        constraints = [
            models.CheckConstraint(condition=~Q(origin=F('destination')),
                                   name='shipments_origin_differs_destination'),
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F('started_at')),
                                   name='shipments_end_after_start'),
            # Um dispositivo so pode estar em UMA viagem ativa por vez; senao nao se
            # sabe a quem a leitura pertence. O banco garante, mesmo com dois cliques ao mesmo tempo.
            models.UniqueConstraint(fields=['device'], condition=Q(status='active'),
                                    name='shipments_one_active_per_device'),
        ]

    def __str__(self):
        return f'Viagem #{self.id} - {self.origin} → {self.destination}'


class ShipmentItem(models.Model):
    """Uma fruta (lote) dentro da viagem. Uma viagem pode levar varias frutas (carga mista)."""

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='items')
    fruit = models.ForeignKey(Fruit, on_delete=models.PROTECT, related_name='shipment_items')
    lot = models.CharField(max_length=50)
    quantity_kg = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shipment_items'
        constraints = [
            models.UniqueConstraint(fields=['shipment', 'fruit', 'lot'], name='shipment_items_unique_lot'),
            models.CheckConstraint(condition=Q(quantity_kg__gt=0), name='shipment_items_quantity_positive'),
        ]

    def __str__(self):
        return f'{self.fruit.name} - lote {self.lot} ({self.quantity_kg} kg)'
