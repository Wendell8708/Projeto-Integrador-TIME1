"""
Autenticacao das PLACAS, separada do login das pessoas (plano, secao 3.4).

A placa manda a chave no cabecalho:   X-Device-Key: <chave>
Se a chave existe, nao foi revogada e a placa esta ativa, `request.auth` vira o
Device. Rotas de pessoas continuam usando JWT normalmente.
"""

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.throttling import SimpleRateThrottle

from .models import Device, DeviceCredential


class DeviceKeyAuthentication(BaseAuthentication):
    header = 'HTTP_X_DEVICE_KEY'

    def authenticate(self, request):
        chave = request.META.get(self.header)
        if not chave:
            return None  # sem cabecalho: a permissao IsDevice devolve 401
        credencial = (
            DeviceCredential.objects.select_related('device')
            .filter(secret_hash=DeviceCredential.hash_da_chave(chave), revoked_at__isnull=True)
            .first()
        )
        if credencial is None or not credencial.device.is_active:
            raise exceptions.AuthenticationFailed('Chave de dispositivo inválida ou revogada.')
        return AnonymousUser(), credencial.device

    def authenticate_header(self, request):
        return 'X-Device-Key'  # faz o DRF responder 401 (e nao 403) quando falta a chave


class IsDevice(BasePermission):
    message = 'Envie a chave do dispositivo no cabeçalho X-Device-Key.'

    def has_permission(self, request, view):
        return isinstance(request.auth, Device)


class DeviceRateThrottle(SimpleRateThrottle):
    """Limite de requisicoes POR PLACA (escopo 'iot' em DEFAULT_THROTTLE_RATES)."""

    scope = 'iot'

    def get_cache_key(self, request, view):
        if isinstance(request.auth, Device):
            return self.cache_format % {'scope': self.scope, 'ident': request.auth.pk}
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


def registrar_contato(device, rede='', ssid=''):
    """Atualiza a ultima comunicacao da placa (vale para lote e heartbeat)."""
    campos = {'last_seen_at': timezone.now()}
    if rede:
        campos['last_connection_type'] = rede
    if ssid:
        campos['wifi_ssid'] = ssid
    Device.objects.filter(pk=device.pk).update(**campos)
