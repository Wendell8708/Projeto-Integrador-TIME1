from django.db import models
from django.db.models import F, Q

from dominio.models import Fruta, Local, Veiculo
from iot.models import Device


class Shipment(models.Model):
    """
    A viagem: unidade central do monitoramento.

    Leituras e impactos pertencem a uma viagem (`shipment.readings`).
    """

    STATUS_CHOICES = [
        ('planejado', 'Planejado'),
        ('em_andamento', 'Em Andamento'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado'),
    ]

    origem = models.ForeignKey(Local, on_delete=models.PROTECT, related_name='transportes_origem')
    destino = models.ForeignKey(Local, on_delete=models.PROTECT, related_name='transportes_destino')
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT, related_name='transportes')
    dispositivo = models.ForeignKey(Device, on_delete=models.PROTECT, related_name='transportes')

    data_hora_inicio = models.DateTimeField()
    data_hora_fim = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planejado')

    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shipments'
        ordering = ['-data_hora_inicio']
        constraints = [
            models.CheckConstraint(
                condition=~Q(origem=F('destino')),
                name='transporte_origem_diferente_destino',
            ),
            models.CheckConstraint(
                condition=Q(data_hora_fim__isnull=True) | Q(data_hora_fim__gt=F('data_hora_inicio')),
                name='transporte_fim_depois_do_inicio',
            ),
        ]

    def __str__(self):
        return f'Transporte #{self.id} - {self.origem} → {self.destino}'


class Carga(models.Model):
    transporte = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='cargas')
    fruta = models.ForeignKey(Fruta, on_delete=models.PROTECT, related_name='cargas')

    lote = models.CharField(max_length=50)
    quantidade_kg = models.DecimalField(max_digits=10, decimal_places=2)

    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['transporte', 'fruta', 'lote'],
                name='carga_unica_por_transporte_fruta_lote',
            ),
            models.CheckConstraint(
                condition=Q(quantidade_kg__gt=0),
                name='carga_quantidade_positiva',
            ),
        ]

    def __str__(self):
        return f'{self.fruta.nome} - Lote {self.lote} ({self.quantidade_kg}kg)'
