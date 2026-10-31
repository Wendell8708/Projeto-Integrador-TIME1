from piADS04.routers import OptionalSlashRouter

from .views import AlertViewSet

router = OptionalSlashRouter()
router.register('alerts', AlertViewSet)

urlpatterns = router.urls
