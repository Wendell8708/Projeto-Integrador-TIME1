from django.contrib import admin

from .models import Dispositivo, Leitura


@admin.register(Dispositivo)
class DispositivoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'identificador', 'thingspeak_channel_id', 'situacao']
    search_fields = ['nome', 'identificador']


@admin.register(Leitura)
class LeituraAdmin(admin.ModelAdmin):
    list_display = ['dispositivo', 'temperatura', 'umidade', 'medido_em', 'origem_id']
    list_filter = ['dispositivo']
    date_hierarchy = 'medido_em'
