"""
Rotas do projeto. Toda a API fica sob /api/v1/ (versionada: se um dia a API
mudar de forma incompativel, criamos /api/v2/ sem quebrar o frontend atual).
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('usuarios.urls')),
]
