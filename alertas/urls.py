from rest_framework.routers import SimpleRouter

from .views import AlertaViewSet

router = SimpleRouter()
router.register('alertas', AlertaViewSet)

urlpatterns = router.urls
