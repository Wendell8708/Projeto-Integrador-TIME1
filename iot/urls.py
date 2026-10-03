from rest_framework.routers import SimpleRouter

from .views import DispositivoViewSet, LeituraViewSet

router = SimpleRouter()
router.register('dispositivos', DispositivoViewSet)
router.register('leituras', LeituraViewSet)

urlpatterns = router.urls
