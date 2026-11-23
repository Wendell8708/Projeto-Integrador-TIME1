# Segurança — Caminho do Vale

Relatório dos dois controles obrigatórios do projeto final de segurança: **autenticação em dois fatores (2FA com TOTP)** e **proteção contra IDOR**. Os dois estão na `main`, publicados e testados antes e depois na API em produção.

## 1. Identificação

| Integrante | GitHub |
| --- | --- |
| Anderson Bem | [@AndersonBem](https://github.com/AndersonBem) |
| Lais Nayara | [@LNayaraSilva](https://github.com/LNayaraSilva) |
| Lucas Mendes | [@Luc4s22](https://github.com/Luc4s22) |
| Matheus Henrique | [@MatheusGoesSoares](https://github.com/MatheusGoesSoares) |
| Wendell Barboza | [@Wendell8708](https://github.com/Wendell8708) |
| Wendell Brasiliano | [@Wendel-Brasiliano](https://github.com/Wendel-Brasiliano) |

- **Projeto do PI:** Caminho do Vale, monitoramento do transporte de frutas do Vale do São Francisco.
- **Código de missão:** o professor não enviou o código de missão para a equipe. Usamos o identificador da equipe, **`TIME1`**, no lugar dele: ele aparece nas linhas de log dos dois controles, no cabeçalho dos resultados dos testes e no nome dos arquivos de evidência. O sistema está pronto para receber o código oficial: basta definir a variável `SECURITY_MISSION_CODE` no servidor (logs) e `MISSAO` nos scripts de teste.

## 2. O projeto

Uma placa **ESP32-C3** viaja no baú do caminhão e mede temperatura, umidade e impactos. As leituras vão para uma **API em Django REST Framework**, publicada no **Render** (e também na **Azure**), com banco **PostgreSQL no Neon**. A API compara cada leitura com a faixa ideal da fruta e gera alertas. Vendedor, comprador e motorista acompanham as viagens num **painel React/PWA** publicado na Vercel.

```
ESP32-C3 --(X-Device-Key)--> API Django REST (Render / Azure) --> PostgreSQL (Neon)
                                   ^
Painel React/PWA (Vercel) --(JWT)--+
```

Papéis: **plataforma** (a equipe, administra), **vendedor** (cria a viagem e a carga), **comprador** (acompanha e confirma a entrega) e **motorista** (inicia e finaliza a própria viagem).

## 3. Controle 1: autenticação em dois fatores (2FA com TOTP)

### 3.1 A ameaça

Sem o segundo fator, quem descobrir a senha de um vendedor (vazamento, phishing, senha repetida em outro site) entra no painel como ele. A partir daí vê cargas, clientes e rotas, altera viagens e encerra viagens dos outros. Para o projeto, o impacto é perder a confiança no histórico da carga, que é justamente o que o sistema vende. Detalhes no [modelo de ameaças](modelo-ameacas.md), ameaças 1 e 5.

### 3.2 O controle

A senha certa não libera o sistema. Ela devolve só um `mfa_token` temporário, e o acesso (JWT) sai apenas depois do código de 6 dígitos do aplicativo autenticador, conferido **no servidor**.

| O quê | Onde |
| --- | --- |
| Regras do 2FA (cifra do segredo, token temporário, QR Code, verificação, códigos de recuperação, log) | [`usuarios/dois_fatores.py`](../usuarios/dois_fatores.py) |
| Rotas `/auth/login`, `/auth/2fa/setup`, `/auth/2fa/activate`, `/auth/2fa/verify`, `/auth/2fa/recovery-codes` | [`usuarios/views.py`](../usuarios/views.py), [`usuarios/urls.py`](../usuarios/urls.py) |
| Modelos `SegundoFator` e `CodigoRecuperacao` | [`usuarios/models.py`](../usuarios/models.py) |
| Configurações (janela, validade do token, limites, chave de cifra) | [`piADS04/settings.py`](../piADS04/settings.py) |
| Testes automáticos (17) | [`usuarios/test_2fa.py`](../usuarios/test_2fa.py) |

Decisões tomadas:

- **TOTP padrão (RFC 6238)**, 6 dígitos e 30 s, compatível com Google Authenticator, Microsoft Authenticator e Authy. Cadastro por **QR Code**.
- **Segredo cifrado no banco** (Fernet). A chave vem de `OTP_ENCRYPTION_KEY` ou, se vazia, é derivada do `SECRET_KEY`; as duas ficam só no ambiente. Quem copiar o banco não gera códigos.
- **`mfa_token` de uso único e curto:** assinado com o `SECRET_KEY`, vale 300 s (`MFA_TOKEN_MAX_AGE`) e deixa de valer quando o login termina.
- **Código de uso único:** o servidor guarda o último intervalo usado e recusa um código igual ou anterior. A linha é travada (`select_for_update`) para duas requisições simultâneas não passarem.
- **Janela de ±1 intervalo** (`OTP_VALID_WINDOW = 1`), para tolerar uns 30 s de diferença de relógio.
- **10 códigos de recuperação de uso único**, guardados só como hash (HMAC-SHA256) e mostrados uma única vez.
- **Limite de 10 tentativas por minuto** no login e no código (`THROTTLE_LOGIN`, `THROTTLE_MFA`).
- **Recadastro bloqueado:** com o 2FA ativo, `/auth/2fa/setup` recusa. Quem tem só a senha não consegue cadastrar o próprio celular. Para trocar de celular, a plataforma reseta o 2FA.
- **Log de cada recusa:** `[TIME1] OTP recusado: usuario=... motivo=... ip=...`.

### 3.3 Como testar

Prepare o ambiente como na [seção 5](#5-preparação-do-ambiente-de-teste) e rode:

```powershell
python seguranca/testes/teste_otp.py
```

O script testa, em ordem: senha certa sem código, código errado, código válido, o mesmo `mfa_token` depois do login, código reutilizado, código de recuperação usado duas vezes e a tentativa de contorno (recadastrar o autenticador só com a senha).

Testes extras: `teste_janela_otp.py` (janela de validade) e `teste_invalidar_recuperacao.py` (invalidar os códigos de recuperação de um usuário).

### 3.4 Resultado

| | Evidência | Resultado |
| --- | --- | --- |
| **Antes** (17/11/2026) | [`TIME1-otp-antes.txt`](evidencias/TIME1-otp-antes.txt) | A senha sozinha devolvia o token de acesso. **VULNERÁVEL** |
| **Depois** (22/11/2026) | [`TIME1-otp-depois.txt`](evidencias/TIME1-otp-depois.txt) | Senha sozinha não recebe token; código errado 400; código válido 200; `mfa_token` reaproveitado 401; código reutilizado 400; recuperação aceita uma vez e recusada na segunda (400); recadastro só com senha 400. **PROTEGIDO** |
| **Vídeo** | [`TIME1-video-front.mp4`](evidencias/TIME1-video-front.mp4), [`TIME1-video-postman.mp4`](evidencias/TIME1-video-postman.mp4) | Login pedindo o código, código errado recusado, código do app aceito. Até 90 s cada |
| **Automático** | `python manage.py test usuarios.test_2fa --noinput` | 17 testes passando |

### 3.5 Limitações

- Não protege contra **phishing em tempo real** (alguém que captura senha e código na hora e usa em seguida) nem contra **roubo do JWT** já emitido. Próximo passo: WebAuthn/passkeys e tokens de acesso mais curtos.
- Se o **celular for comprometido**, o segredo vai junto. Mitigação: reset do 2FA pela plataforma.
- O limite de tentativas é contado por origem, então não segura um **ataque distribuído** (muitas máquinas ao mesmo tempo). Próximo passo: bloqueio temporário da conta após N falhas.
- **Todo servidor que usa o mesmo banco precisa da mesma `OTP_ENCRYPTION_KEY`.** Com chaves diferentes, o segredo gravado por um não é decifrado pelo outro e o código é recusado; isso aconteceu no deploy da Azure e foi corrigido definindo a mesma chave nos dois.
- Se `OTP_ENCRYPTION_KEY` estiver vazia, a chave vem do `SECRET_KEY`: trocar o `SECRET_KEY` invalida o 2FA de todos, que precisam cadastrar de novo.

## 4. Controle 2: proteção contra IDOR

### 4.1 A ameaça

As rotas recebem o ID do recurso na URL (`/shipments/13`, `/devices/4`). Sem checagem de dono, um vendedor logado troca o número e lê as leituras, altera a configuração ou encerra a viagem de outro vendedor. Também pode colocar a placa de outro na própria viagem, mandando o ID no corpo. Para o projeto, isso expõe dados comerciais (clientes, rotas, cargas) e permite sabotar o monitoramento de outra empresa. Detalhes no [modelo de ameaças](modelo-ameacas.md), ameaça 2.

### 4.2 O controle

Toda consulta passa por um **filtro de dono feito no servidor com o usuário do token**, nunca com um ID enviado pelo cliente.

| O quê | Onde |
| --- | --- |
| Regra central: quem é dono, `ProtecaoDonoMixin`, log de bloqueio | [`usuarios/acesso.py`](../usuarios/acesso.py) |
| Viagens e itens (fruta e lote); checagem de IDs no corpo | [`transporte/views.py`](../transporte/views.py) |
| Placas e leituras | [`iot/views.py`](../iot/views.py) |
| Alertas | [`alertas/views.py`](../alertas/views.py) |
| Locais e veículos | [`dominio/views.py`](../dominio/views.py) |
| Chat do assistente (contexto enviado ao Gemini) | [`assistente/contexto.py`](../assistente/contexto.py) |
| Autenticação da placa (`X-Device-Key`) | [`iot/authentication.py`](../iot/authentication.py) |
| Testes automáticos (20) | [`usuarios/test_idor.py`](../usuarios/test_idor.py), [`usuarios/test_idor_cadastros.py`](../usuarios/test_idor_cadastros.py) |

Decisões tomadas:

- **Um lugar só protege todas as rotas:** o `ProtecaoDonoMixin` filtra o `get_queryset()`. Toda rota de detalhe e toda ação (`/shipments/13/finish`) chama `get_object()`, que procura o ID dentro desse queryset filtrado. O ID de outro usuário "não existe" para quem pede.
- **404, não 403, para recurso alheio:** a resposta é a mesma de um ID que não existe, então não dá para descobrir quais IDs existem (enumeração).
- **Dono por papel:** a viagem é visível para quem criou, comprador, motorista e dono da placa. Placas, só o dono. Leituras, alertas e itens seguem a viagem. Plataforma vê tudo.
- **Ver não é poder alterar:** quem vê a viagem mas não pode agir (o comprador tentando iniciar, o motorista mudando a origem) recebe **403**.
- **IDs no corpo também são conferidos:** placa, veículo, origem e destino de uma viagem precisam ser do próprio usuário (ou cadastros compartilhados). Senão, 403.
- **Log de cada bloqueio:** `[TIME1] IDOR bloqueado: usuario=... recurso=... id=... rota=... ip=... motivo=...`. Só entra no log quando o recurso existe de verdade (tentativa real, não um ID inexistente).

### 4.3 Como testar

Prepare o ambiente como na [seção 5](#5-preparação-do-ambiente-de-teste) e rode:

```powershell
python seguranca/testes/teste_idor.py
python seguranca/testes/teste_terceiro_usuario.py
```

O `teste_idor.py` faz o vendedor A tentar ler, alterar e comandar a placa e a viagem do vendedor B. Também tenta dois contornos: o ID do B no corpo da requisição e a enumeração (comparar "existe mas não é seu" com "não existe"). No fim, confere que o B continua usando normalmente. O `teste_terceiro_usuario.py` usa o vendedor C, criado sem placa e sem viagem, e mostra que ele não enxerga nada dos outros.

### 4.4 Resultado

| | Evidência | Resultado |
| --- | --- | --- |
| **Antes** (17/11/2026) | [`TIME1-idor-antes.txt`](evidencias/TIME1-idor-antes.txt) | 6 de 6 tentativas do A sobre os dados do B foram aceitas. **VULNERÁVEL** |
| **Depois** (22/11/2026) | [`TIME1-idor-depois.txt`](evidencias/TIME1-idor-depois.txt) | 11 de 11 tentativas recusadas: 404 nas leituras, alterações e comandos; 403 nos contornos pelo corpo; mesma resposta para viagem alheia e inexistente. O dono continua usando (200). **PROTEGIDO** |
| **Vídeo** | [`TIME1-video-front.mp4`](evidencias/TIME1-video-front.mp4), [`TIME1-video-postman.mp4`](evidencias/TIME1-video-postman.mp4) | Cada usuário vê só o que é seu; a viagem do outro responde 404. Até 90 s cada |
| **Log** | Painel de logs do Render | Linhas `[TIME1] IDOR bloqueado` para cada tentativa |
| **Automático** | `python manage.py test usuarios.test_idor usuarios.test_idor_cadastros --noinput` | 20 testes passando |

### 4.5 Limitações

- Só protege as rotas que usam o mixin e os filtros de `usuarios/acesso.py`. **Uma rota nova criada sem eles reabre o IDOR.** Próximo passo: um teste automático que percorra todas as rotas com dois usuários.
- A **plataforma vê tudo** por regra de negócio. Uma conta de plataforma comprometida expõe todos os dados. Próximo passo: 2FA obrigatório e auditoria das ações da plataforma.
- A chave da placa (`X-Device-Key`) fica no próprio dispositivo: quem tiver **acesso físico** pode extraí-la. Mitigação: revogar a credencial.
- O **MQTT** ainda usa broker público, sem autenticação nem TLS. Próximo passo: broker privado com usuário por placa e TLS.

## 5. Preparação do ambiente de teste

1. Instale as dependências (`pip install -r requirements.txt`) e crie o `.env` a partir do `.env.example`. Nunca publique o `.env`.
2. Rode os comandos a partir da **raiz** do projeto, onde fica o `manage.py`.
3. Defina as variáveis de teste no PowerShell, com valores **seus**:

```powershell
$env:TESTE_SENHA = '<senha-de-teste-com-10-ou-mais-caracteres>'
$env:TESTE_TOTP_SEGREDO = python -c "import pyotp; print(pyotp.random_base32())"
$env:MISSAO = 'TIME1'
$env:API_URL = 'http://127.0.0.1:8000/api/v1'   # sem esta linha, os scripts usam a API do Render
```

4. Prepare os dados sintéticos e suba a API:

```powershell
python manage.py migrate
python manage.py criar_grupos
python manage.py carregar_limites_iniciais
python manage.py preparar_teste_seguranca --terceiro
python manage.py runserver        # em outro terminal
```

O `preparar_teste_seguranca` cria os vendedores sintéticos A, B e C (`vendedor-a@teste.local` etc.), com placa, veículo, locais e uma viagem em andamento para A e B. Ele redefine a senha e o 2FA desses usuários a cada execução, então **só rode num banco de teste**. Rode de novo antes de repetir o `teste_idor.py`, que encerra a viagem do B de propósito.

**Todos os testes automáticos** (178): `python manage.py test --noinput`.

**Postman:** importe [`testes/caminho-do-vale.postman_collection.json`](testes/caminho-do-vale.postman_collection.json). Nunca exporte a coleção com senha, código ou tokens preenchidos.

## 6. Outros documentos

- [Modelo de ameaças](modelo-ameacas.md)
- [Declaração de uso de IA](uso-de-ia.md)
- [Guia da API](../docs/API.md)
