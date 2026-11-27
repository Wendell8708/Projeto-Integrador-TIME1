"""
Testes automatizados do 2FA (TOTP). Cobrem exatamente o "como provar" do trabalho:
senha sem codigo -> recusado; codigo errado ou vencido -> recusado; codigo valido
-> aceito; codigo ja usado -> recusado; codigo de recuperacao -> uma vez so.
"""

import time
from unittest.mock import patch

import pyotp
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APITestCase

from usuarios import dois_fatores
from usuarios.models import SegundoFator

SENHA = 'senha-forte-123'


@override_settings(SECURITY_MISSION_CODE='TST123')
class DoisFatoresTest(APITestCase):

    def setUp(self):
        cache.clear()  # zera os limites de tentativas entre os testes
        self.usuario = User.objects.create_user('ana', 'ana@teste.local', SENHA)

    # --- helpers ---------------------------------------------------------------

    def login(self):
        return self.client.post('/api/v1/auth/login', {'email': 'ana@teste.local', 'password': SENHA}).json()['data']

    def cadastrar(self):
        """Login + setup + activate. Devolve (segredo, codigos de recuperacao)."""
        token = self.login()['mfa_token']
        segredo = self.client.post('/api/v1/auth/2fa/setup', {'mfa_token': token}).json()['data']['secret']
        corpo = self.client.post('/api/v1/auth/2fa/activate',
                                 {'mfa_token': token, 'code': pyotp.TOTP(segredo).now()}).json()['data']
        return segredo, corpo['recovery_codes']

    def verificar(self, **campos):
        token = self.login()['mfa_token']
        return self.client.post('/api/v1/auth/2fa/verify', {'mfa_token': token, **campos})

    # --- cadastro ----------------------------------------------------------------

    def test_senha_certa_sem_codigo_nao_entrega_token(self):
        corpo = self.login()
        self.assertNotIn('access', corpo)
        self.assertTrue(corpo['mfa_required'])
        self.assertTrue(corpo['mfa_setup_required'])

    def test_setup_devolve_qr_code_e_segredo_fica_cifrado(self):
        token = self.login()['mfa_token']
        dados = self.client.post('/api/v1/auth/2fa/setup', {'mfa_token': token}).json()['data']
        self.assertTrue(dados['qr_code'].startswith('data:image/svg+xml;base64,'))
        self.assertTrue(dados['otpauth_uri'].startswith('otpauth://totp/'))
        guardado = SegundoFator.objects.get(usuario=self.usuario).segredo_cifrado
        self.assertNotIn(dados['secret'], guardado)  # no banco nao fica o segredo em texto

    def test_ativacao_entrega_tokens_e_dez_codigos_de_recuperacao(self):
        _, codigos = self.cadastrar()
        self.assertEqual(len(codigos), 10)
        self.assertFalse(self.login()['mfa_setup_required'])

    def test_nao_recadastra_com_2fa_ativo(self):
        """Contorno: quem so tem a senha tenta cadastrar o PROPRIO celular na conta."""
        self.cadastrar()
        token = self.login()['mfa_token']
        self.assertEqual(self.client.post('/api/v1/auth/2fa/setup', {'mfa_token': token}).status_code, 400)

    # --- verificacao -------------------------------------------------------------

    def test_codigo_valido_entra(self):
        segredo, _ = self.cadastrar()
        proximo = pyotp.TOTP(segredo).at(time.time() + 30)  # o codigo de agora ja foi usado na ativacao
        resposta = self.verificar(code=proximo)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        self.assertIn('access', resposta.json()['data'])

    def test_codigo_errado_e_recusado_e_vai_para_o_log(self):
        self.cadastrar()
        with self.assertLogs('seguranca', level='WARNING') as log:
            resposta = self.verificar(code='000000')
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('[TST123] OTP recusado', log.output[0])

    def test_codigo_vencido_e_recusado(self):
        segredo, _ = self.cadastrar()
        antigo = pyotp.TOTP(segredo).at(time.time() - 300)  # de 5 minutos atras
        self.assertEqual(self.verificar(code=antigo).status_code, 400)

    def test_codigo_ja_usado_nao_funciona_de_novo(self):
        segredo, _ = self.cadastrar()
        proximo = pyotp.TOTP(segredo).at(time.time() + 30)
        self.assertEqual(self.verificar(code=proximo).status_code, 200)
        resposta = self.verificar(code=proximo)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('já foi utilizado', resposta.json()['detail'])

    @override_settings(OTP_VALID_WINDOW=0)
    def test_janela_zero_so_aceita_o_codigo_do_intervalo_atual(self):
        """Alteracao ao vivo: OTP_VALID_WINDOW=0 recusa o codigo do intervalo seguinte."""
        segredo, _ = self.cadastrar()
        self.assertEqual(self.verificar(code=pyotp.TOTP(segredo).at(time.time() + 30)).status_code, 400)

    def test_codigo_de_recuperacao_funciona_uma_vez_so(self):
        _, codigos = self.cadastrar()
        self.assertEqual(self.verificar(recovery_code=codigos[0]).status_code, 200)
        self.assertEqual(self.verificar(recovery_code=codigos[0]).status_code, 400)
        self.assertEqual(self.verificar(recovery_code=codigos[1].lower()).status_code, 200)

    def test_codigos_de_recuperacao_invalidados_param_de_valer(self):
        _, codigos = self.cadastrar()
        dois_fatores.invalidar_codigos_recuperacao(self.usuario)
        self.assertEqual(self.verificar(recovery_code=codigos[2]).status_code, 400)

    def test_token_temporario_expirado_e_recusado(self):
        segredo, _ = self.cadastrar()
        token = self.login()['mfa_token']
        with override_settings(MFA_TOKEN_MAX_AGE=0), patch('django.core.signing.time.time', return_value=time.time() + 10):
            resposta = self.client.post('/api/v1/auth/2fa/verify',
                                        {'mfa_token': token, 'code': pyotp.TOTP(segredo).at(time.time() + 30)})
        self.assertEqual(resposta.status_code, 401)

    def test_token_temporario_forjado_e_recusado(self):
        self.cadastrar()
        resposta = self.client.post('/api/v1/auth/2fa/verify', {'mfa_token': 'eyJ1Ijo5OX0:forjado', 'code': '123456'})
        self.assertEqual(resposta.status_code, 401)

    def test_muitas_tentativas_de_codigo_sao_barradas(self):
        self.cadastrar()
        token = self.login()['mfa_token']
        for _ in range(10):
            self.client.post('/api/v1/auth/2fa/verify', {'mfa_token': token, 'code': '000000'})
        resposta = self.client.post('/api/v1/auth/2fa/verify', {'mfa_token': token, 'code': '000000'})
        self.assertEqual(resposta.status_code, 429)

    # --- admin do Django ---------------------------------------------------------

    def test_admin_exige_codigo(self):
        """Contorno: entrar pelo /admin/ so com a senha."""
        self.usuario.is_staff = self.usuario.is_superuser = True
        self.usuario.save()
        segredo, _ = self.cadastrar()
        sem_codigo = self.client.post('/admin/login/', {'username': 'ana', 'password': SENHA, 'codigo': ''})
        self.assertEqual(sem_codigo.status_code, 200)  # volta para o formulario: nao entrou
        self.assertNotIn('_auth_user_id', self.client.session)
        com_codigo = self.client.post('/admin/login/', {
            'username': 'ana', 'password': SENHA, 'codigo': pyotp.TOTP(segredo).at(time.time() + 30),
        })
        self.assertEqual(com_codigo.status_code, 302)  # redireciona para o painel: entrou


class RevisaoDoTokenTemporarioTest(APITestCase):
    """mfa_token de uso unico e papel deterministico."""

    def setUp(self):
        cache.clear()
        call_command('criar_grupos', verbosity=0)
        self.usuario = User.objects.create_user('uso-unico', 'uso.unico@teste.local', 'senha-de-teste-123')

    def test_mfa_token_nao_vale_depois_que_o_login_termina(self):
        login = self.client.post('/api/v1/auth/login',
                                 {'email': 'uso.unico@teste.local', 'password': 'senha-de-teste-123'}).json()['data']
        token = login['mfa_token']
        segredo = self.client.post('/api/v1/auth/2fa/setup', {'mfa_token': token}).json()['data']['secret']
        ativado = self.client.post('/api/v1/auth/2fa/activate',
                                   {'mfa_token': token, 'code': pyotp.TOTP(segredo).now()})
        self.assertEqual(ativado.status_code, 200)
        # O mesmo token de novo (ex.: alguem que o copiou): ja nao vale.
        de_novo = self.client.post('/api/v1/auth/2fa/verify',
                                   {'mfa_token': token, 'recovery_code': ativado.json()['data']['recovery_codes'][0]})
        self.assertEqual(de_novo.status_code, 401)

    def test_papel_com_varios_grupos_e_sempre_o_de_mais_poder(self):
        from django.contrib.auth.models import Group
        from usuarios.serializers import role_do_usuario
        self.usuario.groups.add(Group.objects.get(name='Motorista'), Group.objects.get(name='Vendedor'))
        self.assertEqual(role_do_usuario(self.usuario), 'seller')


@override_settings(SECURITY_MISSION_CODE='TST123', MFA_CONTAS_DEMONSTRACAO=['demo@teste.local'])
class ContaDemonstracaoTest(APITestCase):
    """Conta listada em MFA_CONTAS_DEMONSTRACAO entra so com a senha; as outras continuam com 2FA."""

    def setUp(self):
        cache.clear()
        User.objects.create_user('demo', 'demo@teste.local', SENHA)
        User.objects.create_user('ana', 'ana@teste.local', SENHA)

    def login(self, email):
        return self.client.post('/api/v1/auth/login', {'email': email, 'password': SENHA})

    def test_conta_de_demonstracao_entra_sem_2fa_e_vai_para_o_log(self):
        with self.assertLogs('seguranca', level='WARNING') as log:
            corpo = self.login('demo@teste.local').json()['data']
        self.assertIn('access', corpo)
        self.assertNotIn('mfa_token', corpo)
        self.assertIn('[TST123] 2FA dispensado', log.output[0])

    def test_outras_contas_continuam_com_2fa(self):
        corpo = self.login('ana@teste.local').json()['data']
        self.assertNotIn('access', corpo)
        self.assertTrue(corpo['mfa_required'])

    def test_senha_errada_continua_recusada(self):
        resposta = self.client.post('/api/v1/auth/login', {'email': 'demo@teste.local', 'password': 'errada'})
        self.assertEqual(resposta.status_code, 400)

    def test_plataforma_nunca_e_dispensada(self):
        User.objects.filter(email='demo@teste.local').update(is_superuser=True)
        corpo = self.login('demo@teste.local').json()['data']
        self.assertNotIn('access', corpo)

    @override_settings(MFA_CONTAS_DEMONSTRACAO=[])
    def test_sem_a_variavel_ninguem_e_dispensado(self):
        corpo = self.login('demo@teste.local').json()['data']
        self.assertNotIn('access', corpo)
