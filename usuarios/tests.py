from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from iot.services import registrar_leitura
from piADS04.tests_utils import montar_cenario


class AutenticacaoTest(APITestCase):
    def setUp(self):
        call_command('criar_grupos', verbosity=0)
        self.usuario = User.objects.create_user('ana', password='senha-forte-123', email='ana@exemplo.com')
        self.usuario.groups.add(Group.objects.get(name='Visualizador'))

    def logar(self, username='ana', password='senha-forte-123'):
        return self.client.post('/api/v1/auth/token/', {'username': username, 'password': password})

    def test_login_devolve_access_e_refresh(self):
        resposta = self.logar()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('access', resposta.data)
        self.assertIn('refresh', resposta.data)

    def test_login_com_senha_errada_falha(self):
        self.assertEqual(self.logar(password='errada').status_code, 401)

    def test_refresh_gera_novo_access(self):
        refresh = self.logar().data['refresh']
        resposta = self.client.post('/api/v1/auth/token/refresh/', {'refresh': refresh})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('access', resposta.data)

    def test_me_exige_login(self):
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 401)

    def test_me_mostra_grupos_e_permissoes(self):
        token = self.logar().data['access']
        resposta = self.client.get('/api/v1/auth/me/', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['grupos'], ['Visualizador'])
        self.assertIn('transporte.view_shipment', resposta.data['permissoes'])
        self.assertNotIn('transporte.add_shipment', resposta.data['permissoes'])


class PermissoesPorGrupoTest(APITestCase):
    def setUp(self):
        call_command('criar_grupos', verbosity=0)
        self.c = montar_cenario(status='planejado')

    def usuario_no_grupo(self, grupo):
        usuario = User.objects.create_user(f'u-{grupo}', password='x')
        usuario.groups.add(Group.objects.get(name=grupo))
        self.client.force_authenticate(usuario)

    def test_sem_login_nao_acessa_nada(self):
        self.assertEqual(self.client.get('/api/v1/locais/').status_code, 401)

    def test_usuario_sem_grupo_nao_ve_nada(self):
        self.client.force_authenticate(User.objects.create_user('sem-grupo', password='x'))
        self.assertEqual(self.client.get('/api/v1/locais/').status_code, 403)

    def test_visualizador_consulta_mas_nao_cria(self):
        self.usuario_no_grupo('Visualizador')
        self.assertEqual(self.client.get('/api/v1/locais/').status_code, 200)
        resposta = self.client.post('/api/v1/locais/', {'nome': 'Novo', 'tipo_local': 'armazem'})
        self.assertEqual(resposta.status_code, 403)

    def test_operador_cria_local_mas_nao_cria_fruta(self):
        self.usuario_no_grupo('Operador')
        resposta = self.client.post('/api/v1/locais/', {'nome': 'Novo', 'tipo_local': 'armazem'})
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(self.client.post('/api/v1/frutas/', {'nome': 'Uva'}).status_code, 403)

    def test_administrador_cria_fruta(self):
        self.usuario_no_grupo('Administrador')
        self.assertEqual(self.client.post('/api/v1/frutas/', {'nome': 'Uva'}).status_code, 201)

    def test_visualizador_nao_inicia_transporte_mas_operador_inicia(self):
        url = f"/api/v1/transportes/{self.c['transporte'].id}/iniciar/"
        self.usuario_no_grupo('Visualizador')
        self.assertEqual(self.client.post(url).status_code, 403)
        self.usuario_no_grupo('Operador')
        resposta = self.client.post(url)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['status'], 'em_andamento')


class FluxoDaApiTest(APITestCase):
    """Do cadastro ate o dashboard: leitura entra, alerta nasce, resumo reflete."""

    def setUp(self):
        call_command('criar_grupos', verbosity=0)
        self.c = montar_cenario(status='planejado')
        admin = User.objects.create_user('admin', password='x')
        admin.groups.add(Group.objects.get(name='Administrador'))
        self.client.force_authenticate(admin)
        self.client.post(f"/api/v1/transportes/{self.c['transporte'].id}/iniciar/")

    def enviar_leitura(self, temperatura, minutos, sequence=None):
        """Quem grava leituras e a placa (service), nao um usuario pela API."""
        self.seq = getattr(self, 'seq', 0) + 1
        return registrar_leitura(
            device=self.c['dispositivo'], shipment=self.c['transporte'],
            sequence=sequence if sequence is not None else self.seq,
            recorded_at=timezone.now() + timedelta(minutes=minutos),
            temperature_c=temperatura, humidity_pct='85',
        )

    def test_usuario_nao_grava_leitura_pela_api(self):
        """POST em /leituras/ nao existe mais: leitura so entra pela placa."""
        resposta = self.client.post('/api/v1/leituras/', {})
        self.assertEqual(resposta.status_code, 405)

    def test_leituras_fora_da_faixa_geram_alerta_e_status(self):
        self.enviar_leitura('14', 0)
        self.enviar_leitura('14', 1)

        alertas = self.client.get(f"/api/v1/transportes/{self.c['transporte'].id}/alertas/").data
        self.assertEqual(len(alertas), 1)

        resumo = self.client.get(f"/api/v1/transportes/{self.c['transporte'].id}/resumo/").data
        self.assertEqual(resumo['total_leituras'], 2)
        self.assertEqual(resumo['status_atual'], 'atencao')
        self.assertEqual(resumo['alertas_ativos'], 1)

    def test_historico_do_transporte_e_paginado(self):
        self.enviar_leitura('10', 0)
        self.enviar_leitura('11', 1)
        historico = self.client.get(f"/api/v1/transportes/{self.c['transporte'].id}/leituras/").data
        self.assertEqual(historico['count'], 2)

    def test_leitura_reenviada_com_o_mesmo_sequence_nao_cria_outra(self):
        self.enviar_leitura('10', 0, sequence=77)
        self.enviar_leitura('10', 0, sequence=77)
        historico = self.client.get(f"/api/v1/transportes/{self.c['transporte'].id}/leituras/").data
        self.assertEqual(historico['count'], 1)

    def test_reconhecer_alerta(self):
        self.enviar_leitura('14', 0)
        self.enviar_leitura('14', 1)
        alerta = self.client.get('/api/v1/alertas/').data['results'][0]
        resposta = self.client.post(f"/api/v1/alertas/{alerta['id']}/reconhecer/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['status'], 'reconhecido')
        self.assertEqual(resposta.data['reconhecido_por_nome'], 'admin')

    def test_carga_incompativel_e_recusada(self):
        from decimal import Decimal
        from dominio.models import ConfiguracaoLimite, Fruta
        gelada = Fruta.objects.create(nome='Fruta gelada')
        ConfiguracaoLimite.objects.create(
            fruta=gelada, temperatura_minima=Decimal('0'), temperatura_maxima=Decimal('4'),
            umidade_minima=Decimal('90'), umidade_maxima=Decimal('95'),
        )
        resposta = self.client.post('/api/v1/cargas/', {
            'transporte': self.c['transporte'].id, 'fruta': gelada.id, 'lote': 'X', 'quantidade_kg': '10',
        })
        self.assertEqual(resposta.status_code, 400)

    def test_documentacao_swagger_so_para_staff_fora_do_debug(self):
        # Nos testes DEBUG=False: a documentacao exige usuario staff.
        self.assertEqual(self.client.get('/api/schema/').status_code, 403)
        self.client.force_authenticate(User.objects.create_user('staff', password='x', is_staff=True))
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
