from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UsuarioLogadoSerializer


class MeView(APIView):
    """GET /api/v1/auth/me/ -> dados, grupos e permissoes de quem esta logado."""

    # Qualquer usuario autenticado pode ver os proprios dados.
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UsuarioLogadoSerializer)  # so para a documentacao Swagger
    def get(self, request):
        return Response(UsuarioLogadoSerializer(request.user).data)
