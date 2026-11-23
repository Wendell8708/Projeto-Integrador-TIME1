# Segurança — Caminho do Vale

## 1. Objetivo e escopo

Este diretório documenta dois controles implementados na API Django: **autenticação em dois fatores (2FA/TOTP)** e **autorização por recurso para mitigar IDOR**. O objetivo é permitir que outra pessoa identifique os controles, prepare dados sintéticos e reproduza os testes sem acessar dados reais. O modelo de ameaças está em [`modelo-ameacas.md`](modelo-ameacas.md) e o registro de IA em [`uso-de-ia.md`](uso-de-ia.md).

**Status (23/11/2026):** os dois controles estão na `main`, publicados no Render e na Azure, e foram testados em produção antes e depois da correção. As evidências estão em `seguranca/evidencias/` (seção 5) e os vídeos na seção 6.

**Código de missão:** o professor não disponibilizou um código de missão para a equipe. O sistema está preparado para recebê-lo: o servidor lê a variável `SECURITY_MISSION_CODE` e os scripts de teste leem `MISSAO`. Nas evidências foi usado o identificador da equipe, `TIME1`.

## 2. Controles implementados e localização

| Controle | Local do código | Funcionamento |
| --- | --- | --- |
| TOTP, cadastro de autenticador e QR Code | `usuarios/dois_fatores.py` | Cria o segredo e URI `otpauth://`, gera QR Code em SVG e valida o código no servidor. |
| 2FA no login | `usuarios/views.py`, `usuarios/urls.py` | O login usa uma etapa intermediária `mfa_token`; `POST /auth/2fa/setup` inicia o cadastro, `POST /auth/2fa/activate` ativa o fator e `POST /auth/2fa/verify` valida o segundo fator antes de emitir tokens de acesso. |
| Recuperação de acesso | `usuarios/dois_fatores.py`, `usuarios/views.py`, `usuarios/models.py` | Gera códigos de recuperação com hash persistido; cada código só pode ser usado uma vez. A rota `POST /auth/2fa/recovery-codes` substitui os códigos antigos após conferir TOTP. |
| Limites de tentativas | `usuarios/views.py`, `piADS04/settings.py` | O escopo `mfa` usa `ScopedRateThrottle`; `THROTTLE_MFA` tem padrão `10/min`. O escopo `login` também tem padrão `10/min`. Configurações de ambiente podem alterar esses valores. |
| Regra central de visibilidade e log IDOR | `usuarios/acesso.py` | `ProtecaoDonoMixin` filtra o queryset segundo `request.user`; recursos existentes mas não visíveis recebem 404, com tentativa registrada em log. |
| Viagens e itens de viagem | `transporte/views.py` | ViewSets aplicam filtro de autorização por viagem e seu relacionamento com o usuário. |
| Placas e leituras | `iot/views.py` | Filtragem de dispositivos por proprietário e de leituras por viagem permitida. |
| Alertas | `alertas/views.py` | Filtragem pelo acesso à viagem vinculada ao alerta. |
| Veículos e locais | `dominio/views.py` | Consulta permite itens próprios, compartilhados ou vinculados a viagens autorizadas; alteração/remoção exigem dono ou administrador da plataforma. |

A política **não** se resume a comparar `created_by`: viagens podem ser visíveis a quem criou, comprador, motorista e dono do dispositivo associado; superusuário ou grupo `Administrador` têm acesso de plataforma. Cadastros compartilhados sem dono são visíveis, mas só a plataforma os altera. As regras exatas estão em `usuarios/acesso.py`.

Os endpoints e contratos adicionais estão em `docs/API.md`.

## 3. Requisitos para reproduzir

1. Use Python, as dependências de `requirements.txt`, a configuração Django e um banco de dados **de teste**, conforme `.env.example` e o README principal. Nunca publique senhas, segredos, tokens ou conteúdo do `.env` no Git.
2. Execute os comandos a partir da **raiz** do projeto, onde fica `manage.py`.
3. Configure a API e as variáveis de teste no PowerShell, **substituindo os exemplos por valores privados**:

```powershell
$env:TESTE_SENHA = '<senha-privada-de-teste-com-10-ou-mais-caracteres>'
$env:TESTE_TOTP_SEGREDO = python -c "import pyotp; print(pyotp.random_base32())"
$env:MISSAO = '<codigo-da-equipe>'
$env:API_URL = 'http://127.0.0.1:8000/api/v1'
```

- `TESTE_SENHA`: senha dos usuários sintéticos; o comando exige pelo menos 10 caracteres.
- `TESTE_TOTP_SEGREDO`: mesmo segredo base32 para os usuários sintéticos com 2FA habilitado; é dado sensível, não registrar seu valor nos documentos nem nas evidências.
- `MISSAO`: identificador que aparece no cabeçalho dos resultados (o professor não enviou código de missão; usamos `TIME1`). No servidor, o equivalente é `SECURITY_MISSION_CODE`.
- `API_URL`: endereço-base da API **a ser testada**. O script `seguranca/testes/comum.py` possui um padrão apontando para Render, portanto **defina explicitamente a URL local/de homologação** para evitar alterar dados de produção.

**Preparação do banco de teste:**

```powershell
python manage.py migrate
python manage.py criar_grupos
python manage.py carregar_limites_iniciais
python manage.py preparar_teste_seguranca --terceiro
```

O último comando cria/reaproveita os vendedores sintéticos A, B e C; A e B recebem seus próprios dispositivos, veículos, locais e viagens, e C não recebe placa nem viagem. Os registros podem ser atualizados/reabertos em novas execuções. **Não execute esta preparação em uma base com dados reais**: o comando reutiliza identificadores de teste e redefine credenciais/estado das viagens sintéticas. Caso o servidor seja iniciado localmente, mantenha-o em outro terminal com `python manage.py runserver`.

## 4. Execução dos testes

**Primeiro os testes automáticos do Django:**

```powershell
python manage.py test
```

**Depois, com o ambiente de teste preparado e a API respondendo em `API_URL`:**

```powershell
python seguranca/testes/teste_otp.py
python seguranca/testes/teste_idor.py
python seguranca/testes/teste_terceiro_usuario.py
python seguranca/testes/teste_janela_otp.py
```

- `teste_otp.py`: valida ausência de token final só com senha, código inválido, código válido, prevenção de reutilização e recuperação de uso único.
- `teste_idor.py`: o usuário A tenta acessar recursos de B por ID e exercita cenários de contorno. **Pode fazer PATCH ou encerrar a viagem de teste de B**; execute exclusivamente sobre dados sintéticos autorizados. Em caso de repetição, rode novamente `preparar_teste_seguranca --terceiro`.
- `teste_terceiro_usuario.py`: verifica se o usuário C, sem placas e viagens, consegue ver registros alheios.
- `teste_janela_otp.py`: compara a aceitação de código do intervalo anterior; para demonstrar janela estrita, altere `OTP_VALID_WINDOW=0` na configuração **local** do servidor, reinicie-o e repita. O padrão do código é `1`.

**Teste interativo de revogação de códigos de recuperação:**

```powershell
python seguranca/testes/teste_invalidar_recuperacao.py
```

O script orienta uma ação entre duas etapas. Em outro terminal do **mesmo ambiente e banco** da API de teste, execute o comando informado pelo script, por exemplo:

```powershell
python manage.py invalidar_codigos_recuperacao vendedor-a@teste.local
```

Depois retorne ao primeiro terminal para comprovar que o código revogado é rejeitado. Execute apenas com usuários de teste. Alguns scripts imprimem valores de OTP ou recuperação no terminal: **remova ou oculte esses dados antes de compartilhar qualquer captura ou log**.

### 4.1 Postman

Importe `seguranca/testes/caminho-do-vale.postman_collection.json`. Configure `base_url` para o servidor autorizado de teste e preencha as variáveis de coleção necessárias. A coleção contém o fluxo em duas etapas e cenários de acesso. Nunca exporte a coleção com `senha`, `codigo`, `mfa_token`, `access` ou `refresh` preenchidos.

### 4.2 Critérios para interpretar

- **2FA:** a autenticação apenas por senha não deve fornecer o token JWT final quando o segundo fator estiver ativo; OTP inválido ou reutilizado deve ser recusado; recuperação deve funcionar uma única vez.
- **IDOR:** tentativa de acessar um objeto privado de outra conta por ID deve ser negada (normalmente 404; algumas alterações podem retornar 403), sem impedir que o usuário legítimo continue acessando seu próprio objeto.
- **Limites de requisição:** verificar o escopo `mfa` com testes próprios em ambiente de teste, respeitando que a taxa real depende da configuração e do cache da execução.

Todo resultado citado na seção 5 tem um arquivo de evidência correspondente.

## 5. Evidências

Os mesmos scripts foram rodados contra a API publicada (`https://projeto-integrador-time1.onrender.com/api/v1`) antes e depois dos controles, com os usuários sintéticos `vendedor-a@teste.local` e `vendedor-b@teste.local`.

| Controle | Antes | Depois |
| --- | --- | --- |
| 2FA no login | `evidencias/otp-antes.txt` (17/11/2026): a senha, sozinha, devolvia o token de acesso. **VULNERÁVEL** | `evidencias/otp-depois.txt` (22/11/2026): senha sozinha não recebe token; código errado (400), código válido (200), o mesmo `mfa_token` depois do login (401), código reutilizado (400), código de recuperação aceito uma vez e recusado na segunda (400), recadastro do autenticador só com a senha (400). **PROTEGIDO** |
| IDOR | `evidencias/idor-antes.txt` (17/11/2026): 6 de 6 tentativas do usuário A sobre dados do B foram aceitas. **VULNERÁVEL** | `evidencias/idor-depois.txt` (22/11/2026): 11 de 11 tentativas recusadas (404 nas leituras, alterações e comandos; 403 nos contornos com o ID do B no corpo; mesma resposta para viagem alheia e inexistente), e o dono continua usando normalmente (200). **PROTEGIDO** |
| Testes automatizados | — | `python manage.py test --noinput`: 178 testes passando, incluindo `usuarios/test_2fa.py`, `usuarios/test_idor.py`, `usuarios/test_idor_cadastros.py` e `usuarios/test_gestao_usuarios.py`. |
| Log do servidor | — | Cada tentativa bloqueada gera no log as linhas `IDOR bloqueado: usuario=... id=...` e `OTP recusado`, visíveis no painel de logs do Render. |

## 6. Vídeos de demonstração

Dois vídeos de até 90 segundos, um por controle, gravados no sistema publicado:

- **2FA com TOTP:** login pedindo o código, código errado recusado, código do app aceito e reutilização recusada.
- **Proteção contra IDOR:** cada usuário vendo só os próprios dados e a tentativa de acessar a viagem de outro usuário respondida com 404.

<!-- Para o player aparecer: edite este arquivo no GitHub e arraste cada .mp4 (até 10 MB) para a linha abaixo do título; o GitHub troca pela URL do vídeo. -->

### 2FA com TOTP

_(arraste aqui o vídeo do 2FA)_

### Proteção contra IDOR

_(arraste aqui o vídeo do IDOR)_

## 7. Limitações e riscos residuais

- O 2FA reduz o risco de uso indevido de **senha isoladamente vazada**, mas não elimina phishing em tempo real, roubo de sessão/JWT, comprometimento do dispositivo autenticador ou indisponibilidade do serviço.
- A proteção IDOR se aplica às rotas que realmente usam os filtros de acesso; novas rotas ou consultas criadas sem verificação apropriada podem reintroduzir a falha. Administradores possuem acesso mais amplo por regra de negócio.
- Ao publicar a API em mais de um provedor (Render e Azure), todos precisam usar a mesma `OTP_ENCRYPTION_KEY`; com chaves diferentes, o segredo gravado por um servidor não é decifrado pelo outro e o código é recusado. Isso aconteceu no deploy da Azure e foi corrigido definindo a mesma chave nos dois ambientes.
- A credencial `X-Device-Key` protege a ingestão por dispositivo, mas o acesso físico à placa pode expor a chave; essa mitigação é parcial.
- MQTT em broker público, sem autenticação/TLS conforme o modelo atual, continua com risco de leitura/publicação indevida; a API mantém o histórico oficial separadamente.
- O padrão `10/min` do escopo MFA e do login é mitigação parcial contra tentativas em massa, não proteção completa contra ataques distribuídos e negação de serviço; a configuração pode variar conforme ambiente.

## 8. Participação da equipe

| Integrante | Participação na entrega de segurança |
| --- | --- |
| Wendell Barboza | Implementação dos controles (2FA, IDOR, gestão de usuários), scripts de teste, evidências de antes e depois, vídeos |
| Lucas Mendes | `README.md`, `uso-de-ia.md` e atualização do `modelo-ameacas.md` desta pasta; deploy na Azure |
| Matheus Henrique | Telas de login em duas etapas, QR Code e gestão de usuários no front |
| Wendell Brasiliano | Banco de dados (PostgreSQL) |
| Lais Nayara | Placa ESP32 e organização da entrega no GitHub |
| Anderson Bem | Placa ESP32 (repositório do IoT) |

O histórico de commits e os pull requests no GitHub registram a autoria de cada alteração. O uso de IA está declarado em [`uso-de-ia.md`](uso-de-ia.md).
