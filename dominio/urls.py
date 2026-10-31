from piADS04.routers import OptionalSlashRouter

from .views import FruitParameterViewSet, FruitViewSet, LocationViewSet, VehicleViewSet

# OptionalSlashRouter: aceita /fruits e /fruits/ (o plano usa sem barra no final).
router = OptionalSlashRouter()
router.register('locations', LocationViewSet)
router.register('vehicles', VehicleViewSet)
router.register('fruits', FruitViewSet)
router.register('fruit-parameters', FruitParameterViewSet)

urlpatterns = router.urls
