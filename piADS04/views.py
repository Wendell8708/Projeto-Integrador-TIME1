"""Paginas gerais do backend: a raiz (status da API) e a resposta de rota inexistente."""

from django.http import JsonResponse
from django.utils import timezone


def home(request):
    """GET / -- mostra que a API esta no ar e onde ficam as rotas (serve de health check)."""
    return JsonResponse({
        'name': 'piADS04 - API de monitoramento de transporte de frutas',
        'status': 'online',
        'time': timezone.now().isoformat(),
        'api': '/api/v1/',
        'docs': '/api/docs/',
        'admin': '/admin/',
    })


def not_found(request, exception=None):
    """Qualquer rota inexistente responde JSON, em vez da pagina "Not Found" do Django."""
    return JsonResponse({'detail': 'Rota não encontrada.', 'path': request.path, 'docs': '/api/docs/'}, status=404)
