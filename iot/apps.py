from django.apps import AppConfig


class IotConfig(AppConfig):
    name = 'iot'

    def ready(self):
        from . import schema  # noqa: F401  registra a autenticacao da placa no Swagger
