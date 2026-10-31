from django.urls import re_path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, MeView

# As rotas aceitam com ou sem barra no final (/auth/login e /auth/login/).
urlpatterns = [
    # Login: recebe {"email", "password"}; devolve {"access", "refresh", "user"}.
    re_path(r'^login/?$', LoginView.as_view(), name='auth-login'),
    # Renova o access token: recebe {"refresh"}; devolve {"access"}.
    re_path(r'^refresh/?$', TokenRefreshView.as_view(), name='auth-refresh'),
    re_path(r'^me/?$', MeView.as_view(), name='auth-me'),
]
