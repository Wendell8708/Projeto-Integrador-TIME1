"""Ensina o Swagger (drf-spectacular) a documentar a autenticacao da placa (cabecalho X-Device-Key)."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class DeviceKeyScheme(OpenApiAuthenticationExtension):
    target_class = 'iot.authentication.DeviceKeyAuthentication'
    name = 'DeviceKey'

    def get_security_definition(self, auto_schema):
        return {'type': 'apiKey', 'in': 'header', 'name': 'X-Device-Key'}
