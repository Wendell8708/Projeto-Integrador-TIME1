"""Router das rotas da API.

Fica num modulo separado de piADS04/api.py de proposito: o router importa as views
do DRF, que leem as configuracoes (inclusive o renderer de api.py). Juntos no mesmo
arquivo, isso vira import circular.
"""

from rest_framework.routers import SimpleRouter


class OptionalSlashRouter(SimpleRouter):
    """Aceita a rota com ou sem barra no final (/fruits e /fruits/). O plano usa sem barra."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trailing_slash = '/?'
