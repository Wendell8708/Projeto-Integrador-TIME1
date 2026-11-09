
from django.conf import settings
from django.db import models
from django.db.models import F, Q

from dominio.models import Fruit, Location, Vehicle
from iot.models import Device


class Shipment(models.Model):
    """
    A viagem: unidade central do monitoramento.

    Leituras, impactos e alertas pertencem a uma viagem.
    """

    STATUS_CHOICES = [
        ('planned', 'Planejada'),
        ('active', 'Em andamento'),
        ('completed', 'Concluída'),
        ('cancelled', 'Cancelada'),
    ]

    origin = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='shipments_from'
    )

    destination = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name='shipments_to'
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name='shipments'
    )

    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        related_name='shipments'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shipments_created'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planned'
    )

    started_at = models.DateTimeField(
        help_text=(
            'Início previsto; vira o início REAL '
            'quando a viagem é iniciada.'
        )
    )

    ended_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # NOVO: limites congelados no início da viagem.
    limits_snapshot = models.JSONField(
        null=True,
        blank=True,
        default=None
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = 'shipments'

        ordering = ['-started_at']

        constraints = [
            models.CheckConstraint(
                condition=~Q(origin=F('destination')),
                name='shipments_origin_differs_destination'
            ),

            models.CheckConstraint(
                condition=(
                    Q(ended_at__isnull=True)
                    | Q(ended_at__gt=F('started_at'))
                ),
                name='shipments_end_after_start'
            ),

            models.UniqueConstraint(
                fields=['device'],
                condition=Q(status='active'),
                name='shipments_one_active_per_device'
            ),
        ]

    def __str__(self):
        return (
            f'Viagem #{self.id} - '
            f'{self.origin} → {self.destination}'
        )


class ShipmentItem(models.Model):
    """
    Uma fruta ou lote dentro da viagem.
    Uma viagem pode transportar várias frutas.
    """

    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name='items'
    )

    fruit = models.ForeignKey(
        Fruit,
        on_delete=models.PROTECT,
        related_name='shipment_items'
    )

    lot = models.CharField(
        max_length=50
    )

    quantity_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = 'shipment_items'

        constraints = [
            models.UniqueConstraint(
                fields=['shipment', 'fruit', 'lot'],
                name='shipment_items_unique_lot'
            ),

            models.CheckConstraint(
                condition=Q(quantity_kg__gt=0),
                name='shipment_items_quantity_positive'
            ),
        ]

    def __str__(self):
        return (
            f'{self.fruit.name} - '
            f'lote {self.lot} ({self.quantity_kg} kg)'
        )


# ======================================================
# NOVO: AVALIAÇÃO FINAL DA VIAGEM
# ======================================================

class FinalInspection(models.Model):
    """
    Avaliação realizada ao final do transporte.
    Cada viagem pode possuir uma avaliação final.
    """

    CONDITION_CHOICES = [
        ('good', 'Bom estado'),
        ('damaged', 'Com avarias'),
        ('critical', 'Estado crítico'),
    ]

    shipment = models.OneToOneField(
        Shipment,
        on_delete=models.CASCADE,
        related_name='final_inspection'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='final_inspections'
    )

    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES
    )

    notes = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = 'final_inspections'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'Avaliação final da viagem '
            f'#{self.shipment_id}'
        )


# ======================================================
# NOVO: FOTOGRAFIAS DA AVALIAÇÃO
# ======================================================

class InspectionPhoto(models.Model):
    """
    Fotografia vinculada à avaliação final.

    O arquivo fica armazenado externamente.
    O banco registra apenas a URL.
    """

    inspection = models.ForeignKey(
        FinalInspection,
        on_delete=models.CASCADE,
        related_name='photos'
    )

    file_path = models.URLField(
        max_length=1000
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        db_table = 'inspection_photos'
        ordering = ['created_at']

    def __str__(self):
        return (
            f'Foto da avaliação '
            f'#{self.inspection_id}'
        )
