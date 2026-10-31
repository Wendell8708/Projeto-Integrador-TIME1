from django.contrib import admin

from .models import Shipment, ShipmentItem


class ShipmentItemInline(admin.TabularInline):
    model = ShipmentItem
    extra = 0


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'origin', 'destination', 'vehicle', 'device', 'status', 'started_at']
    list_filter = ['status']
    inlines = [ShipmentItemInline]
