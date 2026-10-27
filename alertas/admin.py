from django.contrib import admin

from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'transporte', 'tipo', 'severidade', 'status', 'valor_medido', 'criado_em']
    list_filter = ['status', 'severidade', 'tipo']
