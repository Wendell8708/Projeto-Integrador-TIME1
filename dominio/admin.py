from django.contrib import admin

from .models import ConfiguracaoLimite, Fruta, Local, Veiculo


@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tipo_local', 'situacao']
    list_filter = ['tipo_local', 'situacao']
    search_fields = ['nome']


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ['placa', 'modelo', 'situacao']
    search_fields = ['placa']


@admin.register(Fruta)
class FrutaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'situacao']
    search_fields = ['nome']


@admin.register(ConfiguracaoLimite)
class ConfiguracaoLimiteAdmin(admin.ModelAdmin):
    list_display = ['fruta', 'temperatura_minima', 'temperatura_maxima', 'umidade_minima', 'umidade_maxima', 'situacao']
    list_filter = ['situacao']
