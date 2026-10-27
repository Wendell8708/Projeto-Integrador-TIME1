from django.contrib import admin

from .models import Carga, Shipment


class CargaInline(admin.TabularInline):
    model = Carga
    extra = 0


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'origem', 'destino', 'veiculo', 'dispositivo', 'status', 'data_hora_inicio']
    list_filter = ['status']
    inlines = [CargaInline]
