"""
Formato padrao das respostas da API (contrato do plano tecnico, secao 2.2).

- Toda resposta de SUCESSO vem dentro da chave "data":   {"data": {...}}
- Listas paginadas trazem tambem "pagination":           {"data": [...], "pagination": {"next": ...}}
- Erros (4xx/5xx) continuam no formato padrao do DRF:    {"detail": "..."} ou {"campo": ["..."]}
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response


class EnvelopeRenderer(JSONRenderer):
    """Embrulha as respostas de sucesso em {"data": ...}."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get('response')
        ja_embrulhada = getattr(response, 'envelope_pronto', False)
        if response is not None and response.status_code < 400 and data is not None and not ja_embrulhada:
            data = {'data': data}
        return super().render(data, accepted_media_type, renderer_context)


class StandardPagination(PageNumberPagination):
    """Paginacao no formato do plano: {"data": [...], "pagination": {"next": ..., "previous": ..., "count": ...}}."""

    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500

    def get_paginated_response(self, data):
        response = Response({
            'data': data,
            'pagination': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'count': self.page.paginator.count,
            },
        })
        response.envelope_pronto = True  # o renderer nao embrulha de novo
        return response

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'data': schema,
                'pagination': {
                    'type': 'object',
                    'properties': {
                        'next': {'type': 'string', 'nullable': True},
                        'previous': {'type': 'string', 'nullable': True},
                        'count': {'type': 'integer'},
                    },
                },
            },
        }

