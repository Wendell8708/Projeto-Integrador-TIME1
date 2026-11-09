from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from iot.services import register_reading
from piADS04.tests_utils import montar_cenario


class AuthTest(APITestCase):
    def setUp(self):
        cache.clear()  # zera o contador do limite de tentativas de login
        call_command('criar_grupos', verbosity=0)
        self.usuario = User.objects.create_user('ana', password='senha-forte-123', email='ana@exemplo.com',
                                                first_name='Ana', last_name='Lima')
        self.usuario.groups.add(Group.objects.get(name='Operador'))

    def logar(self, email='ana@exemplo.com', password='senha-forte-123'):
        return self.client.post('/api/v1/auth/login', {'email': email, 'password': password})

    def test_login_por_email_devolve_tokens_e_usuario_no_formato_do_plano(self):
        resposta = self.logar()
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()['data']
        self.assertIn('access', corpo)
        self.assertIn('refresh', corpo)
        self.assertEqual(corpo['user'], {'id': self.usuario.id, 'name': 'Ana Lima',
                                         'email': 'ana@exemplo.com', 'role': 'operator'})

    def test_email_nao_diferencia_maiusculas(self):
        self.assertEqual(self.logar(email='ANA@Exemplo.com').status_code, 200)

    def test_login_com_senha_errada_falha(self):
        self.assertEqual(self.logar(password='errada').status_code, 400)

    def test_refresh_gera_novo_access(self):
        refresh = self.logar().json()['data']['refresh']
        resposta = self.client.post('/api/v1/auth/refresh', {'refresh': refresh})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('access', resposta.json()['data'])

    def test_me_exige_login(self):
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code, 401)

    def test_me_mostra_papel_grupos_e_permissoes(self):
        token = self.logar().json()['data']['access']
        resposta = self.client.get('/api/v1/auth/me', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['role'], 'operator')
        self.assertIn('transporte.add_shipment', resposta.data['permissions'])
        self.assertNotIn('dominio.add_fruit', resposta.data['permissions'])

    def test_muitas_tentativas_de_login_sao_barradas(self):
        for _ in range(10):
            self.logar(password='errada')
        self.assertEqual(self.logar().status_code, 429)


class PermissionsByGroupTest(APITestCase):
    def setUp(self):
        call_command('criar_grupos', verbosity=0)
        self.c = montar_cenario(status='planned')

    def usuario_no_grupo(self, grupo):
        usuario = User.objects.create_user(f'u-{grupo}', password='x')
        usuario.groups.add(Group.objects.get(name=grupo))
        self.client.force_authenticate(usuario)

    def test_sem_login_nao_acessa_nada(self):
        self.assertEqual(self.client.get('/api/v1/locations').status_code, 401)

    def test_usuario_sem_grupo_nao_ve_nada(self):
        self.client.force_authenticate(User.objects.create_user('sem-grupo', password='x'))
        self.assertEqual(self.client.get('/api/v1/locations').status_code, 403)

    def test_visualizador_consulta_mas_nao_cria(self):
        self.usuario_no_grupo('Visualizador')
        self.assertEqual(self.client.get('/api/v1/locations').status_code, 200)
        self.assertEqual(self.client.post('/api/v1/locations', {'name': 'X', 'type': 'farm'}).status_code, 403)

    def test_operador_cria_local_mas_nao_cria_fruta(self):
        self.usuario_no_grupo('Operador')
        self.assertEqual(self.client.post('/api/v1/locations', {'name': 'X', 'type': 'farm'}).status_code, 201)
        self.assertEqual(self.client.post('/api/v1/fruits', {'name': 'Caju'}).status_code, 403)

    def test_administrador_cria_fruta(self):
        self.usuario_no_grupo('Administrador')
        self.assertEqual(self.client.post('/api/v1/fruits', {'name': 'Caju'}).status_code, 201)

    def test_visualizador_nao_inicia_viagem_mas_operador_inicia(self):
        url = f"/api/v1/shipments/{self.c['viagem'].id}/start"
        self.usuario_no_grupo('Visualizador')
        self.assertEqual(self.client.post(url).status_code, 403)
        self.usuario_no_grupo('Operador')
        self.assertEqual(self.client.post(url).status_code, 200)


class ApiFlowTest(APITestCase):
    """Do cadastro ao dashboard: leitura entra, alerta nasce, resumo reflete."""

    def setUp(self):
        call_command('criar_grupos', verbosity=0)
        self.c = montar_cenario(status='planned')
        admin = User.objects.create_user('admin', password='x', first_name='Ada')
        admin.groups.add(Group.objects.get(name='Administrador'))
        self.client.force_authenticate(admin)
        self.client.post(f"/api/v1/shipments/{self.c['viagem'].id}/start")
        self.url = f"/api/v1/shipments/{self.c['viagem'].id}"

    def enviar_leitura(self, temperatura, minutos, sequence=None):
        self.seq = getattr(self, 'seq', 0) + 1
        return register_reading(
            device=self.c['dispositivo'], shipment=self.c['viagem'],
            sequence=sequence if sequence is not None else self.seq,
            recorded_at=timezone.now() + timedelta(minutes=minutos),
            temperature_c=temperatura, humidity_pct='85',
        )

    def test_usuario_nao_grava_leitura_pela_api(self):
        self.assertEqual(self.client.post('/api/v1/readings', {}).status_code, 405)

    def test_leituras_fora_da_faixa_geram_alerta_e_status(self):
        self.enviar_leitura('14', 0)
        self.enviar_leitura('14', 1)
        self.assertEqual(len(self.client.get(f'{self.url}/alerts').data), 1)
        resumo = self.client.get(f'{self.url}/summary').data
        self.assertEqual(resumo['metrics']['readings'], 2)
        self.assertEqual(resumo['current_status'], 'warning')
        self.assertEqual(resumo['open_alerts'], 1)
        self.assertEqual(resumo['latest_reading']['temperature_c'], 14.0)
        self.assertEqual(resumo['device']['uid'], 'esp32-teste')

    def test_historico_paginado_no_formato_do_plano(self):
        self.enviar_leitura('10', 0)
        self.enviar_leitura('11', 1)
        corpo = self.client.get(f'{self.url}/readings').json()
        self.assertEqual(len(corpo['data']), 2)
        self.assertEqual(corpo['pagination'], {'next': None, 'previous': None, 'count': 2})

    def test_filtro_since_traz_so_as_novas(self):
        self.enviar_leitura('10', 0)
        leitura, _ = self.enviar_leitura('11', 1)
        antes = (leitura.recorded_at - timedelta(seconds=1)).isoformat()
        corpo = self.client.get(f'{self.url}/readings', {'since': antes}).json()
        self.assertEqual(len(corpo['data']), 1)

    def test_reconhecer_e_resolver_alerta(self):
        self.enviar_leitura('14', 0)
        self.enviar_leitura('14', 1)
        alerta = self.client.get('/api/v1/alerts').json()['data'][0]
        resposta = self.client.post(f"/api/v1/alerts/{alerta['id']}/ack")
        self.assertEqual((resposta.status_code, resposta.data['status']), (200, 'acknowledged'))
        self.assertEqual(resposta.data['acknowledged_by_name'], 'Ada')
        self.assertEqual(self.client.post(f"/api/v1/alerts/{alerta['id']}/resolve").data['status'], 'resolved')

    def test_carga_incompativel_e_recusada(self):
        from decimal import Decimal

        from dominio.models import Fruit, FruitParameter
        gelada = Fruit.objects.create(name='Fruta gelada')
        FruitParameter.objects.create(
            fruit=gelada, temperature_min_c=Decimal('0'), temperature_max_c=Decimal('4'),
            humidity_min_pct=Decimal('90'), humidity_max_pct=Decimal('95'),
        )
        resposta = self.client.post('/api/v1/shipment-items', {
            'shipment': self.c['viagem'].id, 'fruit': gelada.id, 'lot': 'X', 'quantity_kg': '10',
        })
        self.assertEqual(resposta.status_code, 400)

    def test_erro_nao_vem_embrulhado_em_data(self):
        corpo = self.client.post(f'{self.url}/start').json()  # ja esta ativa
        self.assertIn('detail', corpo)
        self.assertNotIn('data', corpo)

    def test_documentacao_swagger_so_para_staff_fora_do_debug(self):
        self.assertEqual(self.client.get('/api/schema/').status_code, 403)
        self.client.force_authenticate(User.objects.create_user('staff', password='x', is_staff=True))
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)


class SwaggerWithAdminSessionTest(APITestCase):
    """
    O Swagger (/api/docs/) abre no navegador, que so manda o cookie de sessao do /admin/
    (nao o cabecalho Bearer). Com DEBUG=False, so staff logado enxerga a documentacao.
    """

    def setUp(self):
        cache.clear()  # outro teste enche o contador do limite de login; sem isto o login aqui levaria 429

    def test_sem_login_responde_403_e_nao_401(self):
        # 403 (e nao 401) porque a sessao e o primeiro metodo de autenticacao da documentacao.
        self.assertEqual(self.client.get('/api/docs/').status_code, 403)
        self.assertEqual(self.client.get('/api/schema/').status_code, 403)

    def test_usuario_comum_logado_na_sessao_nao_ve_a_documentacao(self):
        User.objects.create_user('comum', password='senha-forte-123')
        self.client.login(username='comum', password='senha-forte-123')
        self.assertEqual(self.client.get('/api/docs/').status_code, 403)

    def test_staff_logado_pela_sessao_do_admin_ve_a_documentacao(self):
        User.objects.create_user('chefe', password='senha-forte-123', is_staff=True)
        self.assertTrue(self.client.login(username='chefe', password='senha-forte-123'))  # cookie de sessao
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)

    def test_staff_com_jwt_tambem_ve_a_documentacao(self):
        User.objects.create_user('chefe', password='senha-forte-123', is_staff=True, email='chefe@exemplo.com')
        token = self.client.post('/api/v1/auth/login', {'email': 'chefe@exemplo.com', 'password': 'senha-forte-123'}
                                 ).json()['data']['access']
        resposta = self.client.get('/api/schema/', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(resposta.status_code, 200)

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings

from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError


class LogoutETokensTest(APITestCase):

    def setUp(self):
        cache.clear()

        self.usuario = User.objects.create_user(
            username='usuario_logout_teste',
            email='logout@exemplo.com',
            password='SenhaForte123!'
        )

        self.refresh = RefreshToken.for_user(self.usuario)

        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.refresh.access_token}'
        )

    def test_logout_com_token_valido(self):
        resposta = self.client.post(
            '/api/v1/auth/logout',
            {'refresh': str(self.refresh)},
            format='json'
        )

        self.assertEqual(resposta.status_code, 200)

        with self.assertRaises(TokenError):
            RefreshToken(str(self.refresh))

    def test_logout_sem_refresh_token(self):
        resposta = self.client.post(
            '/api/v1/auth/logout',
            {},
            format='json'
        )

        self.assertEqual(resposta.status_code, 400)

    def test_logout_sem_autenticacao(self):
        self.client.credentials()

        resposta = self.client.post(
            '/api/v1/auth/logout',
            {'refresh': str(self.refresh)},
            format='json'
        )

        self.assertEqual(resposta.status_code, 401)

    def test_logout_com_refresh_de_outro_usuario(self):
        outro = User.objects.create_user(
            username='outro_usuario_logout',
            password='SenhaForte123!'
        )

        token_outro = RefreshToken.for_user(outro)

        resposta = self.client.post(
            '/api/v1/auth/logout',
            {'refresh': str(token_outro)},
            format='json'
        )

        self.assertEqual(resposta.status_code, 400)


class RecuperacaoDeSenhaTest(APITestCase):

    def setUp(self):
        cache.clear()

        self.usuario = User.objects.create_user(
            username='usuario_recuperacao',
            email='recuperacao@exemplo.com',
            password='SenhaAntiga123!'
        )

        self.url_solicitar = '/api/v1/auth/password-reset'
        self.url_confirmar = '/api/v1/auth/password-reset/confirm'

    @override_settings(PASSWORD_RESET_TIMEOUT=3600)
    @patch('usuarios.views.urlopen')
    @patch('usuarios.views.config')
    def test_solicitar_recuperacao(
        self,
        mock_config,
        mock_urlopen
    ):
        valores = {
            'PASSWORD_RESET_URL':
                'http://localhost:5173/redefinir-senha',
            'RESEND_API_KEY': 'chave-ficticia',
            'RESEND_FROM_EMAIL': 'teste@exemplo.com',
        }

        mock_config.side_effect = (
            lambda chave, default='':
            valores.get(chave, default)
        )

        resposta = self.client.post(
            self.url_solicitar,
            {'email': self.usuario.email},
            format='json'
        )

        self.assertEqual(resposta.status_code, 200)
        mock_urlopen.assert_called_once()

    def test_email_inexistente_nao_revela_usuario(self):
        resposta = self.client.post(
            self.url_solicitar,
            {'email': 'naoexiste@exemplo.com'},
            format='json'
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn('detail', resposta.data)

    def test_redefinir_senha_com_token_valido(self):
        from django.contrib.auth.tokens import (
            default_token_generator
        )
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(
            force_bytes(self.usuario.pk)
        )

        token = default_token_generator.make_token(
            self.usuario
        )

        resposta = self.client.post(
            self.url_confirmar,
            {
                'uid': uid,
                'token': token,
                'password': 'NovaSenhaForte123!',
            },
            format='json'
        )

        self.assertEqual(resposta.status_code, 200)

        self.usuario.refresh_from_db()

        self.assertTrue(
            self.usuario.check_password('NovaSenhaForte123!')
        )

    def test_redefinir_senha_com_token_invalido(self):
        resposta = self.client.post(
            self.url_confirmar,
            {
                'uid': 'invalido',
                'token': 'token-invalido',
                'password': 'NovaSenhaForte123!',
            },
            format='json'
        )

        self.assertEqual(resposta.status_code, 400)

    def test_redefinir_senha_fraca(self):
        from django.contrib.auth.tokens import (
            default_token_generator
        )
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(
            force_bytes(self.usuario.pk)
        )

        token = default_token_generator.make_token(
            self.usuario
        )

        resposta = self.client.post(
            self.url_confirmar,
            {
                'uid': uid,
                'token': token,
                'password': '123',
            },
            format='json'
        )

        self.assertEqual(resposta.status_code, 400)
