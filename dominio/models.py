from django.db import models


class Local(models.Model):
    TIPO_CHOICES = [
        ('fazenda', 'Fazenda'),
        ('centro_distribuicao', 'Centro de Distribuição'),
        ('armazem', 'Armazém'),
    ]

    nome = models.CharField(max_length=150)
    tipo_local = models.CharField(max_length=30, choices=TIPO_CHOICES)
    endereco = models.CharField(max_length=255, blank=True)
    situacao = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    def _str_(self):
        return f'{self.nome} ({self.get_tipo_local_display()})'


class Veiculo(models.Model):
    placa = models.CharField(max_length=10, unique=True)
    modelo = models.CharField(max_length=100, blank=True)
    situacao = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    def _str_(self):
        return self.placa


class Fruta(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    situacao = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    def _str_(self):
        return self.nome


class ConfiguracaoLimite(models.Model):
    fruta = models.ForeignKey(Fruta, on_delete=models.CASCADE, related_name='limites')
    temperatura_minima = models.DecimalField(max_digits=5, decimal_places=2)
    temperatura_maxima = models.DecimalField(max_digits=5, decimal_places=2)
    umidade_minima = models.DecimalField(max_digits=5, decimal_places=2)
    umidade_maxima = models.DecimalField(max_digits=5, decimal_places=2)
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    situacao = models.BooleanField(default=True)

    def _str_(self):
        return f'Limites de {self.fruta.nome}'