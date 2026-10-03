from django.db import models
from dominio.models import Local, Veiculo, Fruta
from iot.models import Dispositivo


class Transporte(models.Model):
    STATUS_CHOICES = [
        ('planejado', 'Planejado'),
        ('em_andamento', 'Em Andamento'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado'),
    ]

    origem = models.ForeignKey(Local, on_delete=models.PROTECT, related_name='transportes_origem')
    destino = models.ForeignKey(Local, on_delete=models.PROTECT, related_name='transportes_destino')
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT, related_name='transportes')
    dispositivo = models.ForeignKey(Dispositivo, on_delete=models.PROTECT, related_name='transportes')

    data_hora_inicio = models.DateTimeField()
    data_hora_fim = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planejado')

    data_cadastro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Transporte #{self.id} - {self.origem} → {self.destino}'


class Carga(models.Model):
    transporte = models.ForeignKey(Transporte, on_delete=models.CASCADE, related_name='cargas')
    fruta = models.ForeignKey(Fruta, on_delete=models.PROTECT, related_name='cargas')

    lote = models.CharField(max_length=50)
    quantidade_kg = models.DecimalField(max_digits=10, decimal_places=2)

    data_cadastro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.fruta.nome} - Lote {self.lote} ({self.quantidade_kg}kg)'