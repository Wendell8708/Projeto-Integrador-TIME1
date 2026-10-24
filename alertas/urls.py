from rest_framework.routers import SimpleRouter

from .views import AlertViewSet

router = SimpleRouter()
router.register('alertas', AlertViewSet)

urlpatterns = router.urls
