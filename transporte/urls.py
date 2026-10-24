from rest_framework.routers import SimpleRouter

from .views import CargaViewSet, ShipmentViewSet

router = SimpleRouter()
router.register('transportes', ShipmentViewSet)
router.register('cargas', CargaViewSet)

urlpatterns = router.urls
