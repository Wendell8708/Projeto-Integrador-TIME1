from django.contrib import admin

from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    # shipment_id (numero) em vez de shipment: evita buscar origem e destino a cada linha.
    list_display = ['id', 'shipment_id', 'type', 'severity', 'status', 'measured_value', 'created_at']
    list_filter = ['status', 'severity', 'type']
    search_fields = ['=shipment__id']
    raw_id_fields = ['shipment', 'reading', 'shock_event']
    list_per_page = 50
