# Caminho do Vale

Sistema de monitoramento do transporte de frutas do Vale do São Francisco. Uma placa ESP32 viaja com a carga, mede temperatura, umidade e impactos e envia as leituras para esta API. Vendedor, comprador e motorista acompanham a viagem em tempo real e recebem alertas quando a carga sai dos limites ideais da fruta.

Projeto Integrador do curso de Análise e Desenvolvimento de Sistemas (ADS), Faculdade Senac.

## Equipe (Time 1)

| Integrante |
|---|
| Anderson Bem |
| Lais Nayara |
| Lucas Mendes |
| Matheus Henrique |
| Wendell Brasiliano |
| Wendell Barboza |

## Visão geral

| Parte | Tecnologia | Onde fica |
|---|---|---|
| **API (este repositório)** | Django + Django REST Framework, JWT | Render |
| Banco de dados | PostgreSQL | Neon |
| Front-end / PWA | React | Repositório próprio do front |
| Placa | ESP32-C3 com MicroPython | [AndersonBem/IOT-senac-temp-umidade](https://github.com/AndersonBem/IOT-senac-temp-umidade) |

API publicada: `https://projeto-integrador-time1.onrender.com/api/v1`

## Funcionalidades

- **Viagens:** o vendedor cria a viagem (origem, destino, veículo, placa, frutas e lotes) e vincula comprador e motorista. A viagem passa por `planejada → em andamento → entregue → concluída`.
- **Telemetria:** a placa envia leituras e impactos em lote; a API guarda o histórico e marca a placa como online.
- **Alertas:** temperatura, umidade ou impacto fora dos limites da fruta geram alertas, que podem ser reconhecidos e encerrados.
- **Dashboard:** resumo da viagem, histórico de leituras, impactos e alertas.
- **Assistente (chat):** perguntas sobre as viagens respondidas com a API do Gemini, usando só os dados que o usuário pode ver.
- **Gestão de usuários:** a equipe da plataforma cria usuários por convite (link para definir a senha), muda papéis e reseta o 2FA, sem precisar do `/admin`.

### Papéis

| Papel | O que faz |
|---|---|
| Plataforma (administrador) | A equipe fornecedora: gerencia usuários e cadastros compartilhados |
| Vendedor | Cria a carga e a viagem, vincula comprador e motorista |
| Comprador | Acompanha a compra e confirma a entrega |
| Motorista | Vê só a própria viagem, inicia e finaliza |

## Segurança

Dois controles implementados para a avaliação de cibersegurança:

- **Login em dois fatores (2FA com TOTP):** a senha sozinha não entra. O usuário cadastra um app autenticador por QR Code e informa o código de 6 dígitos a cada login. Há códigos de recuperação de uso único, códigos não podem ser reutilizados e as tentativas são limitadas.
- **Proteção contra IDOR:** cada usuário só vê e comanda o que é dele. Trocar o ID na URL ou no corpo da requisição devolve 404/403, e a tentativa é registrada no log.

Documentação, modelo de ameaças, testes e evidências (antes e depois): [`seguranca/`](seguranca/README.md).

## Estrutura do repositório

```
piADS04/      configurações do Django (settings, urls)
usuarios/     login, 2FA, papéis, gestão de usuários e regras de acesso (IDOR)
dominio/      frutas e seus limites, locais e veículos
transporte/   viagens, itens (fruta/lote), início, fim e confirmação
iot/          placas, credenciais, leituras e impactos
alertas/      geração e tratamento de alertas
assistente/   chat com o Gemini
docs/         guia da API, modelo de dados (DER) e teste da placa
seguranca/    documentação, testes e evidências de segurança
```

## Como rodar localmente

Pré-requisitos: Python 3.13 e um PostgreSQL (local ou Neon).

```powershell
git clone https://github.com/Wendell8708/Projeto-Integrador-TIME1.git
cd Projeto-Integrador-TIME1

python -m venv venv
.\venv\Scripts\Activate.ps1          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

Copy-Item .env.example .env          # Linux/macOS: cp .env.example .env
# preencha o .env com os dados do SEU banco e uma SECRET_KEY própria

python manage.py migrate
python manage.py criar_grupos
python manage.py carregar_limites_iniciais
python manage.py runserver
```

A API fica em `http://127.0.0.1:8000/api/v1`.

> Nunca publique o `.env`, senhas, chaves ou tokens no GitHub. O `.env.example` traz só os nomes das variáveis.

### Variáveis de ambiente principais

| Variável | Para quê |
|---|---|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Configuração básica do Django |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_SSLMODE` | Conexão com o PostgreSQL |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Endereço do front que pode chamar a API |
| `OTP_ENCRYPTION_KEY` | Chave que cifra os segredos do 2FA no banco |
| `SECURITY_MISSION_CODE` | Código de missão que aparece nos logs de segurança |
| `GEMINI_API_KEY` | Chat do assistente (sem ela, o chat responde 503) |
| `PASSWORD_RESET_URL`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Convites e recuperação de senha por e-mail |

## Testes

```powershell
python manage.py test --noinput
```

Os testes de segurança contra a API (IDOR e 2FA) estão em `seguranca/testes/`; o passo a passo está em [`seguranca/README.md`](seguranca/README.md).

## Deploy

No Render, o `build.sh` roda a cada deploy: instala as dependências, coleta os arquivos estáticos, aplica as migrations e cria os grupos de papéis. A aplicação sobe com `gunicorn piADS04.wsgi`.

## Documentação

- [Guia da API](docs/API.md): rotas, corpos e respostas, para o front e para a placa
- [Modelo de dados](docs/MODELO_DE_DADOS.md) e [DER](docs/DER.png)
- [Teste da placa](docs/TESTE_PLACA.md)
- [Relatório de alterações](docs/RELATORIO_ALTERACOES.md)
- [Segurança](seguranca/README.md)
