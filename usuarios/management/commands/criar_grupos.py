"""
Cria (ou atualiza) os grupos do sistema e as permissoes de cada um.

Uso:  python manage.py criar_grupos

Pode rodar quantas vezes quiser: o comando e idempotente (sempre deixa os
grupos exatamente como definido aqui). Usa so User/Group/Permission nativos.
"""

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

APPS_DO_PROJETO = ['dominio', 'iot', 'transporte', 'alertas']


def permissoes_do_projeto():
    """
    Permissoes dos models que EXISTEM hoje nos apps do projeto.

    O Django nao apaga as permissoes de um model removido ou renomeado (elas ficam
    "orfas" no banco). Filtrar pelos models atuais evita dar permissao a um model
    que nao existe mais.
    """
    tipos = [
        ContentType.objects.get_for_model(modelo)
        for modelo in apps.get_models()
        if modelo._meta.app_label in APPS_DO_PROJETO
    ]
    return Permission.objects.filter(content_type__in=tipos)

# Operador: cadastra/edita o que e do dia a dia; nao mexe em limites nem dispositivos.
# Os nomes sao os do model em minusculas (shipment, alert...): e assim que o Django
# batiza as permissoes (add_shipment, change_alert...).
OPERADOR_PODE_ADICIONAR_E_EDITAR = [
    'local', 'veiculo', 'shipment', 'carga',
]
OPERADOR_PODE_EDITAR = ['alert']  # reconhecer alertas


def permissoes_do_administrador():
    """Administrador: todas as permissoes de todos os models do projeto."""
    return permissoes_do_projeto()


def permissoes_do_operador():
    permissoes = permissoes_do_projeto()
    codenames = {p.codename for p in permissoes if p.codename.startswith('view_')}
    for modelo in OPERADOR_PODE_ADICIONAR_E_EDITAR:
        codenames |= {f'add_{modelo}', f'change_{modelo}'}
    for modelo in OPERADOR_PODE_EDITAR:
        codenames.add(f'change_{modelo}')
    return permissoes.filter(codename__in=codenames)


def permissoes_do_visualizador():
    """Visualizador: so consulta (view_) tudo."""
    return permissoes_do_projeto().filter(codename__startswith='view_')


GRUPOS = {
    'Administrador': permissoes_do_administrador,
    'Operador': permissoes_do_operador,
    'Visualizador': permissoes_do_visualizador,
}


class Command(BaseCommand):
    help = 'Cria os grupos Administrador, Operador e Visualizador com suas permissoes.'

    def handle(self, *args, **options):
        for nome, obter_permissoes in GRUPOS.items():
            grupo, criado = Group.objects.get_or_create(name=nome)
            permissoes = list(obter_permissoes())
            grupo.permissions.set(permissoes)  # "set" substitui: mantem o grupo sempre igual a este arquivo
            situacao = 'criado' if criado else 'atualizado'
            if options['verbosity'] > 0:
                self.stdout.write(self.style.SUCCESS(f'Grupo {nome} {situacao} com {len(permissoes)} permissoes.'))
