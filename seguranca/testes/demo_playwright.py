"""
Demonstracao automatica dos dois controles pelo FRONT, com Playwright.

Abre duas janelas lado a lado (vendedor A e vendedor B) e mostra, devagar e
com legenda na tela:
    1. 2FA:  senha certa -> pede o codigo; codigo errado -> recusado;
             codigo do app -> entra.
    2. IDOR: o B abre a propria viagem; o A cola a URL da viagem do B
             -> a API responde 404 e a tela mostra "Viagem nao encontrada".

O codigo do 2FA e calculado com o segredo dos usuarios de TESTE
(TESTE_TOTP_SEGREDO), o mesmo que o aplicativo autenticador usaria.

Instalar (uma vez):
    pip install playwright pyotp requests
    python -m playwright install chromium

Rodar (PowerShell, na raiz do projeto, mesmas variaveis dos outros testes):
    $env:TESTE_SENHA = "..."; $env:TESTE_TOTP_SEGREDO = "..."; $env:MISSAO = "TIME1"
    python seguranca/testes/demo_playwright.py              # so a demonstracao
    python seguranca/testes/demo_playwright.py --gravar     # grava um video de cada janela

Opcional: $env:FRONT_URL (padrao: o front publicado na Vercel).
Antes de repetir, rode: python manage.py preparar_teste_seguranca
"""

import os
import re
import sys
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from comum import (
    MISSAO, SENHA, USUARIO_A, USUARIO_B, cabecalho, codigo_novo, exigir_senha, token_de,
)
from teste_idor import recursos_de

FRONT_URL = os.environ.get('FRONT_URL', 'https://caminh-do-vale-front.vercel.app').rstrip('/')
GRAVAR = '--gravar' in sys.argv
PASTA_VIDEOS = os.path.join('seguranca', 'evidencias', 'videos-playwright')

LENTO_MS = 350        # atraso entre cada acao do navegador (para dar para acompanhar)
PAUSA_S = 2.5         # tempo de leitura de cada legenda
LARGURA, ALTURA = 940, 980

CAMPO_CODIGO = 'input[aria-label="Código de 6 dígitos do aplicativo autenticador"]'


def legenda(pagina, texto, cor='#123A24'):
    """Faixa fixa no rodape da pagina explicando o passo (some quando a pagina navega)."""
    pagina.evaluate(
        """([texto, cor, missao]) => {
            let el = document.getElementById('demo-legenda');
            if (!el) {
                el = document.createElement('div');
                el.id = 'demo-legenda';
                el.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:99999;padding:14px 18px;'
                    + 'font:600 20px system-ui,sans-serif;color:#fff;text-align:center;'
                    + 'box-shadow:0 -4px 14px rgba(0,0,0,.25)';
                document.body.appendChild(el);
            }
            el.style.background = cor;
            el.textContent = '[' + missao + '] ' + texto;
        }""",
        [texto, cor, MISSAO],
    )
    print(f'  > {texto}')
    time.sleep(PAUSA_S)


def abrir_janela(pw, x, titulo):
    navegador = pw.chromium.launch(
        headless=os.environ.get('DEMO_HEADLESS') == '1', slow_mo=LENTO_MS,
        args=[f'--window-position={x},0', f'--window-size={LARGURA},{ALTURA}'],
    )
    opcoes = {'viewport': {'width': LARGURA - 20, 'height': ALTURA - 140}}
    if GRAVAR:
        os.makedirs(PASTA_VIDEOS, exist_ok=True)
        opcoes['record_video_dir'] = PASTA_VIDEOS
        opcoes['record_video_size'] = opcoes['viewport']
    contexto = navegador.new_context(**opcoes)
    pagina = contexto.new_page()
    print(f'Janela {titulo} aberta.')
    return navegador, contexto, pagina


def preencher_login(pagina, email):
    pagina.goto(f'{FRONT_URL}/login', wait_until='domcontentloaded')
    pagina.get_by_label('E-mail').fill(email)
    pagina.get_by_label('Senha').fill(SENHA)
    pagina.get_by_role('button', name='Entrar').click()
    pagina.locator(CAMPO_CODIGO).wait_for(timeout=90_000)  # o Render gratuito pode demorar a acordar


def entrar_com_codigo(pagina, email):
    campo = pagina.locator(CAMPO_CODIGO)
    campo.fill('')
    campo.fill(codigo_novo(email))  # 6 digitos: o front envia sozinho
    pagina.wait_for_url(lambda url: '/login' not in url, timeout=30_000)
    pagina.wait_for_load_state('networkidle')


def demo_2fa(pagina):
    print('\n--- 1. AUTENTICACAO EM DOIS FATORES ---')
    preencher_login(pagina, USUARIO_A)
    legenda(pagina, '2FA: senha certa, mas o sistema NAO entra: pede o código do app')

    pagina.locator(CAMPO_CODIGO).fill('000000')
    try:
        pagina.get_by_text(re.compile('inválido|vencido', re.I)).first.wait_for(timeout=15_000)
    except PlaywrightTimeout:
        pass
    legenda(pagina, '2FA: código errado (000000) -> RECUSADO pelo servidor', '#B23A2E')

    entrar_com_codigo(pagina, USUARIO_A)
    legenda(pagina, '2FA: código do autenticador -> acesso liberado', '#1A7A44')


def demo_idor(pagina_a, pagina_b, viagem_b):
    print('\n--- 2. PROTECAO CONTRA IDOR ---')
    url_viagem = f'{FRONT_URL}/cargas/VG-{viagem_b}'

    preencher_login(pagina_b, USUARIO_B)
    entrar_com_codigo(pagina_b, USUARIO_B)
    pagina_b.goto(url_viagem, wait_until='networkidle')
    legenda(pagina_b, f'Vendedor B abre a PRÓPRIA viagem (VG-{viagem_b}): funciona', '#1A7A44')

    legenda(pagina_a, f'IDOR: o vendedor A cola a URL da viagem do B (VG-{viagem_b})')
    padrao = re.compile(rf'/shipments/{viagem_b}/?(\?.*)?$')
    status = None
    try:
        with pagina_a.expect_response(lambda r: bool(padrao.search(r.url)), timeout=30_000) as resposta:
            pagina_a.goto(url_viagem, wait_until='domcontentloaded')
        status = resposta.value.status
    except PlaywrightTimeout:
        pagina_a.goto(url_viagem, wait_until='domcontentloaded')
    try:
        pagina_a.get_by_text('Viagem não encontrada').first.wait_for(timeout=20_000)
    except PlaywrightTimeout:
        pass
    pagina_a.wait_for_load_state('networkidle')
    if status is not None:
        legenda(pagina_a, f'IDOR: a API respondeu {status} -> o A não vê a viagem do B', '#B23A2E')
    else:
        legenda(pagina_a, 'IDOR: viagem não encontrada -> o A não vê a viagem do B', '#B23A2E')
    return status


def main():
    exigir_senha()
    cabecalho('Demonstracao pelo front (Playwright): 2FA e IDOR')
    print(f'Front: {FRONT_URL}')

    # O ID da viagem do B vem da API, logado como o proprio B.
    viagem_b, *_ = recursos_de(token_de(USUARIO_B), 'B')
    print(f'Viagem de teste do vendedor B: VG-{viagem_b}')

    with sync_playwright() as pw:
        nav_a, ctx_a, pagina_a = abrir_janela(pw, 0, 'do vendedor A (esquerda)')
        nav_b, ctx_b, pagina_b = abrir_janela(pw, LARGURA, 'do vendedor B (direita)')
        try:
            demo_2fa(pagina_a)
            status = demo_idor(pagina_a, pagina_b, viagem_b)
            print('\n' + '-' * 72)
            print('RESULTADO: senha sozinha nao entra; codigo errado recusado; codigo valido entra.')
            print(f'           A tentou abrir a viagem do B: {status or "tela de viagem nao encontrada"}.')
            input('\nEnter para fechar as janelas...')
        finally:
            ctx_a.close()
            ctx_b.close()
            nav_a.close()
            nav_b.close()
    if GRAVAR:
        print(f'Videos salvos em {PASTA_VIDEOS}')


if __name__ == '__main__':
    main()
