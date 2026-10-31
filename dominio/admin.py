from django.contrib import admin

from .models import Fruit, FruitParameter, Location, Vehicle


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'is_active']
    list_filter = ['type', 'is_active']
    search_fields = ['name']


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['plate', 'model', 'is_active']
    search_fields = ['plate']


@admin.register(Fruit)
class FruitAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    search_fields = ['name']


@admin.register(FruitParameter)
class FruitParameterAdmin(admin.ModelAdmin):
    list_display = ['fruit', 'temperature_min_c', 'temperature_max_c', 'humidity_min_pct',
                    'humidity_max_pct', 'impact_max_g', 'is_active']
    list_filter = ['is_active']
