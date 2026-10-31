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


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ['device', 'shipment', 'sequence', 'temperature_c', 'humidity_pct', 'impact_peak_g', 'recorded_at']
    list_filter = ['device', 'shipment']
    date_hierarchy = 'recorded_at'


@admin.register(ShockEvent)
class ShockEventAdmin(admin.ModelAdmin):
    list_display = ['device', 'shipment', 'event_id', 'impact_peak_g', 'recorded_at']
    list_filter = ['device', 'shipment']
