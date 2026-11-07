from django.contrib import admin

from .models import Device, DeviceCredential, Reading, ShockEvent


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'uid', 'is_active', 'last_seen_at', 'last_connection_type']
    search_fields = ['name', 'uid']


@admin.register(DeviceCredential)
class DeviceCredentialAdmin(admin.ModelAdmin):
    # A chave nao aparece em lugar nenhum: so o hash fica no banco.
    list_display = ['device', 'created_at', 'revoked_at']
    readonly_fields = ['device', 'secret_hash', 'created_at']


# Leituras crescem rapido (uma a cada 30 s por placa). Sem estes ajustes a lista fazia
# varias consultas POR LINHA (placa, viagem, origem e destino da viagem) e o filtro por
# viagem montava o nome de TODAS as viagens; com o banco remoto (Neon) a pagina passava
# do tempo limite do gunicorn no Render (WORKER TIMEOUT / 500).
# Para ver uma viagem: /admin/iot/reading/?shipment__id__exact=4
@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ['device', 'shipment_id', 'sequence', 'temperature_c', 'humidity_pct', 'impact_peak_g', 'recorded_at']
    list_select_related = ['device']
    list_filter = ['device', 'shipment__status']
    search_fields = ['=shipment__id', '=sequence']
    raw_id_fields = ['device', 'shipment']
    list_per_page = 50
    show_full_result_count = False
    ordering = ['-recorded_at']


@admin.register(ShockEvent)
class ShockEventAdmin(admin.ModelAdmin):
    list_display = ['device', 'shipment_id', 'event_id', 'impact_peak_g', 'recorded_at']
    list_select_related = ['device']
    list_filter = ['device', 'shipment__status']
    search_fields = ['=shipment__id', 'event_id']
    raw_id_fields = ['device', 'shipment']
    list_per_page = 50
    show_full_result_count = False
