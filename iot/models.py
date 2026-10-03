from django.db import models


class Dispositivo(models.Model):
    nome = models.CharField(max_length=100)
    identificador = models.CharField(max_length=100, unique=True)
    thingspeak_channel_id = models.CharField(max_length=20, blank=True)
    situacao = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.nome} ({self.identificador})'
