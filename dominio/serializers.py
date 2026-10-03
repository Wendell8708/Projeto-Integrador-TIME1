from rest_framework import serializers

from .models import ConfiguracaoLimite, Fruta, Local, Veiculo


class LocalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Local
        fields = ['id', 'nome', 'tipo_local', 'endereco', 'situacao', 'data_cadastro']
        read_only_fields = ['id', 'data_cadastro']


class VeiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Veiculo
        fields = ['id', 'placa', 'modelo', 'situacao', 'data_cadastro']
        read_only_fields = ['id', 'data_cadastro']


class FrutaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fruta
        fields = ['id', 'nome', 'descricao', 'situacao', 'data_cadastro']
        read_only_fields = ['id', 'data_cadastro']


class ConfiguracaoLimiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracaoLimite
        fields = [
            'id', 'fruta',
            'temperatura_minima', 'temperatura_maxima', 'margem_critica_temperatura',
            'umidade_minima', 'umidade_maxima', 'margem_critica_umidade',
            'fonte', 'situacao',
        ]
        read_only_fields = ['id']

    def validate(self, dados):
        # Em PATCH, campos ausentes vem da instancia atual.
        def valor(campo):
            return dados.get(campo, getattr(self.instance, campo, None))

        if valor('temperatura_minima') >= valor('temperatura_maxima'):
            raise serializers.ValidationError('A temperatura mínima deve ser menor que a máxima.')
        if valor('umidade_minima') >= valor('umidade_maxima'):
            raise serializers.ValidationError('A umidade mínima deve ser menor que a máxima.')

        # Mensagem clara em vez de erro 500 do banco (constraint "um ativo por fruta").
        if valor('situacao'):
            outros_ativos = ConfiguracaoLimite.objects.filter(fruta=valor('fruta'), situacao=True)
            if self.instance is not None:
                outros_ativos = outros_ativos.exclude(pk=self.instance.pk)
            if outros_ativos.exists():
                raise serializers.ValidationError(
                    'Esta fruta já tem uma configuração de limites ativa. Desative a anterior primeiro.'
                )
        return dados
