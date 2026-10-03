from rest_framework.routers import SimpleRouter

from .views import CargaViewSet, TransporteViewSet

router = SimpleRouter()
router.register('transportes', TransporteViewSet)
router.register('cargas', CargaViewSet)

urlpatterns = router.urls
