"""
Permissoes da API baseadas no sistema NATIVO do Django.

Cada model tem 4 permissoes automaticas: add_, change_, delete_ e view_.
Os grupos (Administrador, Operador, Visualizador) recebem essas permissoes
pelo comando `python manage.py criar_grupos`. Aqui so dizemos ao DRF
qual permissao cada metodo HTTP exige.
"""

from rest_framework.permissions import DjangoModelPermissions


class PermissaoPorModelo(DjangoModelPermissions):
    """
    Permissao padrao de todas as views.

    O DjangoModelPermissions original deixa qualquer usuario logado fazer GET.
    Aqui exigimos tambem a permissao `view_`, para que so quem pode ver veja.

        GET    -> view_<model>
        POST   -> add_<model>
        PUT    -> change_<model>
        DELETE -> delete_<model>
    """

    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': ['%(app_label)s.view_%(model_name)s'],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }


class PodeAlterarModelo(PermissaoPorModelo):
    """
    Para acoes que MUDAM um registro existente via POST (ex.: iniciar um
    transporte, reconhecer um alerta). Nesses casos o POST nao e "criar",
    e sim "alterar", entao exigimos `change_<model>`.
    """

    perms_map = {
        **PermissaoPorModelo.perms_map,
        'POST': ['%(app_label)s.change_%(model_name)s'],
    }
