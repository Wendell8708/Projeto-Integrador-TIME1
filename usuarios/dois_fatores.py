"""
AUTENTICACAO EM DOIS FATORES (2FA) COM TOTP.

Como o TOTP funciona (RFC 6238), em poucas palavras:
    1. No cadastro, servidor e aplicativo (Google Authenticator) passam a
       conhecer o MESMO segredo (via QR Code).
    2. O tempo e dividido em intervalos ("passos") de 30 s, numerados desde 1970.
    3. Codigo = HMAC(segredo, numero do passo), reduzido a 6 digitos.
       Celular e servidor calculam sozinhos, sem conversar: se o relogio dos dois
       bate, o codigo bate. Quem so tem a senha nao tem o segredo -> nao gera o codigo.

O que este arquivo garante (o que o professor pede para provar):
    - codigo errado ou vencido -> recusado (so vale o passo atual +/- OTP_VALID_WINDOW);
    - codigo ja usado -> recusado (guardamos o ultimo passo usado);
    - codigo de recuperacao -> funciona uma vez so;
    - segredo cifrado no banco e chave fora do codigo.
"""

import base64
import hashlib
import hmac
import io
import logging
import secrets
import time

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone

from .models import CodigoRecuperacao, SegundoFator

logger = logging.getLogger('seguranca')

PASSO_S = 30  # duracao de cada codigo (padrao dos aplicativos autenticadores)
SALT_TOKEN = 'login-2fa'  # separa este token de outros usos do signing do Django


# ---------------------------------------------------------------------------
# Segredo cifrado no banco
# ---------------------------------------------------------------------------

def _fernet():
    """
    Cifra simetrica (Fernet = AES + HMAC) para guardar o segredo TOTP.

    A chave vem de OTP_ENCRYPTION_KEY (variavel de ambiente). Se estiver vazia,
    derivamos uma da SECRET_KEY do Django, que tambem so existe no ambiente.
    Assim, quem copiar o banco nao consegue gerar os codigos de ninguem.
    """
    chave = settings.OTP_ENCRYPTION_KEY
    if not chave:
        chave = base64.urlsafe_b64encode(hashlib.sha256(b'otp:' + settings.SECRET_KEY.encode()).digest())
    return Fernet(chave)


def _cifrar(segredo):
    return _fernet().encrypt(segredo.encode()).decode()


def _decifrar(cifrado):
    return _fernet().decrypt(cifrado.encode()).decode()


# ---------------------------------------------------------------------------
# Token temporario entre a senha e o codigo
# ---------------------------------------------------------------------------

def criar_token_temporario(usuario):
    """
    Depois da senha certa, o login NAO devolve o JWT: devolve este token, que so
    serve para a etapa do codigo. Ele e assinado com a SECRET_KEY (nao da para
    forjar nem trocar o ID de usuario) e expira em MFA_TOKEN_MAX_AGE segundos.
    """
    return signing.dumps({'u': usuario.pk, 'l': _marca_login(usuario)}, salt=SALT_TOKEN)


def _marca_login(usuario):
    return usuario.last_login.isoformat() if usuario.last_login else ''


def usuario_do_token(token, modelo_usuario):
    """
    Devolve o usuario do token temporario, ou None se for invalido/expirado.

    Uso unico: o token guarda o last_login do momento em que foi criado. Quando
    o login termina (emitir_tokens grava um last_login novo), o token deixa de
    valer, mesmo dentro dos 5 minutos.
    """
    try:
        dados = signing.loads(token, salt=SALT_TOKEN, max_age=settings.MFA_TOKEN_MAX_AGE)
    except signing.BadSignature:  # inclui SignatureExpired
        return None
    usuario = modelo_usuario.objects.filter(pk=dados.get('u'), is_active=True).first()
    if usuario is None or dados.get('l', '') != _marca_login(usuario):
        return None
    return usuario


# ---------------------------------------------------------------------------
# Cadastro (QR Code) e ativacao
# ---------------------------------------------------------------------------

def tem_2fa_ativo(usuario):
    return SegundoFator.objects.filter(usuario=usuario, ativo=True).exists()


def iniciar_cadastro(usuario):
    """
    Gera um segredo NOVO (pendente) e devolve o que a tela de cadastro precisa:
    o link otpauth://, o QR Code em SVG (data URI) e o segredo para digitar a mao.
    """
    segredo = pyotp.random_base32()  # 160 bits aleatorios
    SegundoFator.objects.update_or_create(
        usuario=usuario,
        defaults={'segredo_cifrado': _cifrar(segredo), 'ativo': False, 'ultimo_passo': None, 'ativado_em': None},
    )
    nome_conta = usuario.email or usuario.username
    uri = pyotp.TOTP(segredo).provisioning_uri(name=nome_conta, issuer_name=settings.OTP_ISSUER)

    imagem = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    imagem.save(buffer)
    qr = 'data:image/svg+xml;base64,' + base64.b64encode(buffer.getvalue()).decode()
    return {'otpauth_uri': uri, 'qr_code': qr, 'secret': segredo}


def ativar(usuario, codigo):
    """Confere o primeiro codigo do aplicativo; se bater, ativa o 2FA e gera os codigos de recuperacao."""
    if not SegundoFator.objects.filter(usuario=usuario, ativo=False).exists():
        return None
    if verificar_codigo(usuario, codigo, exigir_ativo=False) != 'ok':
        return None
    SegundoFator.objects.filter(usuario=usuario).update(ativo=True, ativado_em=timezone.now())
    return gerar_codigos_recuperacao(usuario)


# ---------------------------------------------------------------------------
# Verificacao do codigo TOTP (com protecao contra reuso)
# ---------------------------------------------------------------------------

def verificar_codigo(usuario, codigo, exigir_ativo=True):
    """
    Devolve 'ok', 'invalido' ou 'reutilizado'.

    select_for_update trava a linha do usuario: duas requisicoes com o MESMO
    codigo ao mesmo tempo nao passam as duas (a segunda ve o passo ja gravado).
    """
    codigo = (codigo or '').strip().replace(' ', '')
    if len(codigo) != 6 or not codigo.isdigit():
        return 'invalido'

    with transaction.atomic():
        fator = SegundoFator.objects.select_for_update().filter(usuario=usuario).first()
        if fator is None or (exigir_ativo and not fator.ativo):
            return 'invalido'
        try:
            totp = pyotp.TOTP(_decifrar(fator.segredo_cifrado))
        except InvalidToken:
            return 'invalido'  # chave de cifra trocada: segredo ilegivel

        passo_atual = int(time.time()) // PASSO_S
        janela = settings.OTP_VALID_WINDOW
        for desvio in range(-janela, janela + 1):
            passo = passo_atual + desvio
            # compare_digest compara em tempo constante (nao vaza por tempo de resposta).
            if hmac.compare_digest(totp.at(passo * PASSO_S), codigo):
                if fator.ultimo_passo is not None and passo <= fator.ultimo_passo:
                    return 'reutilizado'
                fator.ultimo_passo = passo
                fator.save(update_fields=['ultimo_passo'])
                return 'ok'
    return 'invalido'


# ---------------------------------------------------------------------------
# Codigos de recuperacao (uso unico)
# ---------------------------------------------------------------------------

ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # sem 0/O e 1/I, que confundem


def _hash_recuperacao(codigo):
    """
    HMAC-SHA256 com chave derivada da SECRET_KEY. O codigo tem 40 bits aleatorios,
    entao um hash rapido com chave secreta basta (e permite achar pelo hash direto).
    """
    chave = hashlib.sha256(b'recuperacao:' + settings.SECRET_KEY.encode()).digest()
    normalizado = codigo.strip().upper().replace('-', '').replace(' ', '')
    return hmac.new(chave, normalizado.encode(), hashlib.sha256).hexdigest()


def gerar_codigos_recuperacao(usuario, quantidade=10):
    """Apaga os antigos e cria novos. Os codigos em texto so sao mostrados AGORA, uma vez."""
    codigos = []
    with transaction.atomic():
        CodigoRecuperacao.objects.filter(usuario=usuario).delete()
        for _ in range(quantidade):
            bruto = ''.join(secrets.choice(ALFABETO) for _ in range(8))
            codigo = f'{bruto[:4]}-{bruto[4:]}'
            CodigoRecuperacao.objects.create(usuario=usuario, codigo_hash=_hash_recuperacao(codigo))
            codigos.append(codigo)
    return codigos


def usar_codigo_recuperacao(usuario, codigo):
    """
    Marca o codigo como usado e devolve True. O UPDATE so altera a linha se
    usado_em ainda for NULL: mesmo com duas requisicoes simultaneas, so uma ganha.
    """
    alterados = CodigoRecuperacao.objects.filter(
        usuario=usuario, codigo_hash=_hash_recuperacao(codigo or ''), usado_em__isnull=True,
    ).update(usado_em=timezone.now())
    return alterados == 1


def invalidar_codigos_recuperacao(usuario):
    """Gasta todos os codigos de recuperacao ainda nao usados. Devolve quantos."""
    return CodigoRecuperacao.objects.filter(usuario=usuario, usado_em__isnull=True).update(usado_em=timezone.now())


# ---------------------------------------------------------------------------
# Log com codigo de missao
# ---------------------------------------------------------------------------

def registrar_recusa(request, usuario, motivo):
    logger.warning(
        '[%s] OTP recusado: usuario=%s motivo=%s ip=%s',
        settings.SECURITY_MISSION_CODE,
        getattr(usuario, 'email', None) or getattr(usuario, 'username', '?'),
        motivo, request.META.get('REMOTE_ADDR', '?') if request is not None else '-',
    )


def registrar_dispensa(request, usuario):
    """Login sem 2FA de uma conta de demonstracao: fica registrado, como as recusas."""
    logger.warning(
        '[%s] 2FA dispensado (conta de demonstracao): usuario=%s ip=%s',
        settings.SECURITY_MISSION_CODE,
        getattr(usuario, 'email', None) or getattr(usuario, 'username', '?'),
        request.META.get('REMOTE_ADDR', '?') if request is not None else '-',
    )
