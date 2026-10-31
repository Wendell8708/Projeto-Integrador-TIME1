from piADS04.routers import OptionalSlashRouter

from .views import ShipmentItemViewSet, ShipmentViewSet

router = OptionalSlashRouter()
router.register('shipments', ShipmentViewSet)
router.register('shipment-items', ShipmentItemViewSet)

urlpatterns = router.urls
