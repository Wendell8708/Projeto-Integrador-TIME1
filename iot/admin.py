from django.contrib import admin

from .models import Device, Reading


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['nome', 'identificador', 'thingspeak_channel_id', 'situacao']
    search_fields = ['nome', 'identificador']


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ['device', 'shipment', 'sequence', 'temperature_c', 'humidity_pct', 'recorded_at']
    list_filter = ['device', 'shipment']
    date_hierarchy = 'recorded_at'
