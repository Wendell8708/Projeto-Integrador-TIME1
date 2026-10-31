from django.urls import re_path
from piADS04.routers import OptionalSlashRouter

from .views import DeviceConfigView, DeviceViewSet, HeartbeatView, ReadingViewSet, TelemetryBatchView

router = OptionalSlashRouter()
router.register('devices', DeviceViewSet)
router.register('readings', ReadingViewSet)

urlpatterns = [
    # Rotas da placa (chave X-Device-Key)
    re_path(r'^iot/telemetry/batch/?$', TelemetryBatchView.as_view(), name='iot-telemetry-batch'),
    re_path(r'^iot/heartbeat/?$', HeartbeatView.as_view(), name='iot-heartbeat'),
    re_path(r'^iot/config/?$', DeviceConfigView.as_view(), name='iot-config'),
] + router.urls
