"""
Rotas do projeto. Toda a API fica sob /api/v1/ (versionada: se um dia a API
mudar de forma incompativel, criamos /api/v2/ sem quebrar o frontend atual).

Documentacao interativa (Swagger):  /api/docs/   |   Esquema OpenAPI: /api/schema/
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication

from .views import home

# Em desenvolvimento a documentacao e aberta; fora dele, so administradores.
permissao_docs = [AllowAny] if settings.DEBUG else [IsAdminUser]

# Quem abre /api/docs/ no NAVEGADOR nao manda o cabecalho "Authorization: Bearer ...":
# o navegador so leva o cookie de sessao. Sem este ajuste, a pagina respondia 401 mesmo
# para o administrador logado. Agora vale a sessao do /admin/ (faca login la e volte)
# ou o JWT. As chamadas feitas DENTRO do Swagger continuam usando o JWT (botao Authorize).
autenticacao_docs = [SessionAuthentication, JWTAuthentication]

urlpatterns = [
    # A raiz mostra que a API esta no ar (em vez de 404).
    path('', home, name='home'),
    path('admin/', admin.site.urls),

    path('api/v1/auth/', include('usuarios.urls')),
    path('api/v1/', include('dominio.urls')),
    path('api/v1/', include('iot.urls')),
    path('api/v1/', include('transporte.urls')),
    path('api/v1/', include('alertas.urls')),

    path('api/schema/', SpectacularAPIView.as_view(
        permission_classes=permissao_docs, authentication_classes=autenticacao_docs), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(
        url_name='schema', permission_classes=permissao_docs, authentication_classes=autenticacao_docs), name='docs'),
]

# Rota inexistente responde JSON (vale com DEBUG=False, como no Render).
handler404 = 'piADS04.views.not_found'
