from django.contrib import admin

from .models import Alerta


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ['id', 'transporte', 'tipo', 'severidade', 'status', 'valor_medido', 'criado_em']
    list_filter = ['status', 'severidade', 'tipo']
