from rest_framework.routers import SimpleRouter

from .views import ConfiguracaoLimiteViewSet, FrutaViewSet, LocalViewSet, VeiculoViewSet

# O router gera sozinho as rotas: /locais/ (lista/cria) e /locais/{id}/ (ver/edita/apaga).
router = SimpleRouter()
router.register('locais', LocalViewSet)
router.register('veiculos', VeiculoViewSet)
router.register('frutas', FrutaViewSet)
router.register('limites', ConfiguracaoLimiteViewSet)

urlpatterns = router.urls
