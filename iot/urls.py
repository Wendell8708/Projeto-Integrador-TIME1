from rest_framework.routers import SimpleRouter

from .views import DeviceViewSet, ReadingViewSet

router = SimpleRouter()
router.register('dispositivos', DeviceViewSet)
router.register('leituras', ReadingViewSet)

urlpatterns = router.urls
