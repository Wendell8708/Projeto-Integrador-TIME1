from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q

from iot.models import Leitura
from transporte.models import Transporte


class Alerta(models.Model):
    TIPO_CHOICES = [
        ('temperatura', 'Temperatura'),
        ('umidade', 'Umidade'),
    ]
    SEVERIDADE_CHOICES = [
        ('atencao', 'Atenção'),
        ('critico', 'Crítico'),
    ]
    STATUS_CHOICES = [
        ('aberto', 'Aberto'),
        ('reconhecido', 'Reconhecido'),
        ('resolvido', 'Resolvido'),
    ]

    transporte = models.ForeignKey(Transporte, on_delete=models.PROTECT, related_name='alertas')
    leitura = models.ForeignKey(
        Leitura, on_delete=models.PROTECT, related_name='alertas',
        help_text='Leitura que disparou o alerta.',
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    severidade = models.CharField(max_length=10, choices=SEVERIDADE_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='aberto')

    # Guardamos os valores NA HORA do alerta: se a faixa da fruta mudar depois,
    # o historico do alerta continua fiel ao que aconteceu.
    valor_medido = models.DecimalField(max_digits=5, decimal_places=2)
    limite_violado = models.DecimalField(max_digits=5, decimal_places=2)

    criado_em = models.DateTimeField(auto_now_add=True)
    reconhecido_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='alertas_reconhecidos',
    )
    reconhecido_em = models.DateTimeField(null=True, blank=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['transporte', 'status'], name='alerta_transporte_status_idx'),
        ]
        constraints = [
            # No maximo UM alerta "ativo" (aberto ou reconhecido) por transporte e tipo.
            # Evita 500 alertas iguais enquanto a temperatura continua fora da faixa.
            models.UniqueConstraint(
                fields=['transporte', 'tipo'],
                condition=Q(status__in=['aberto', 'reconhecido']),
                name='um_alerta_ativo_por_transporte_e_tipo',
            ),
        ]

    def __str__(self):
        return f'Alerta {self.get_severidade_display()} de {self.get_tipo_display()} (transporte #{self.transporte_id})'
