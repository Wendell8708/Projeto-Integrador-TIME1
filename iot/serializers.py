from rest_framework import serializers

from .models import Dispositivo, Leitura
from .services import registrar_leitura


class DispositivoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispositivo
        fields = ['id', 'nome', 'identificador', 'thingspeak_channel_id', 'situacao', 'data_cadastro']
        read_only_fields = ['id', 'data_cadastro']


class LeituraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Leitura
        fields = ['id', 'dispositivo', 'temperatura', 'umidade', 'medido_em', 'recebido_em', 'origem_id']
        read_only_fields = ['id', 'recebido_em']
        # A unicidade (dispositivo + origem_id) e tratada no service, que devolve a
        # leitura existente em vez de dar erro. Por isso desligamos o validador automatico.
        validators = []

    def create(self, dados):
        # Toda leitura entra pelo service: grava sem duplicar e avalia alertas.
        leitura, _criada = registrar_leitura(**dados)
        return leitura
