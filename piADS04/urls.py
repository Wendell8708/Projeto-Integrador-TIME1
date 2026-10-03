"""
Rotas do projeto. Toda a API fica sob /api/v1/ (versionada: se um dia a API
mudar de forma incompativel, criamos /api/v2/ sem quebrar o frontend atual).

Documentacao interativa (Swagger):  /api/docs/   |   Esquema OpenAPI: /api/schema/
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny, IsAdminUser

# Em desenvolvimento a documentacao e aberta; fora dele, so administradores.
permissao_docs = [AllowAny] if settings.DEBUG else [IsAdminUser]

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/v1/auth/', include('usuarios.urls')),
    path('api/v1/', include('dominio.urls')),
    path('api/v1/', include('iot.urls')),
    path('api/v1/', include('transporte.urls')),
    path('api/v1/', include('alertas.urls')),

    path('api/schema/', SpectacularAPIView.as_view(permission_classes=permissao_docs), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema', permission_classes=permissao_docs), name='docs'),
]
