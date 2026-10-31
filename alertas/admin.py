from django.contrib import admin

from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'shipment', 'type', 'severity', 'status', 'measured_value', 'created_at']
    list_filter = ['status', 'severity', 'type']
