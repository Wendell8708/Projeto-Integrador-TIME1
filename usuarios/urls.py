from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import MeView

urlpatterns = [
    # Login: recebe {"username", "password"} e devolve {"access", "refresh"}.
    path('token/', TokenObtainPairView.as_view(), name='token_obtain'),
    # Renova o access token usando o refresh token.
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
]
