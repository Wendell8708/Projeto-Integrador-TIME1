# Declaração de uso de inteligência artificial

## 1. Objetivo

Registrar com transparência como a equipe do **Caminho do Vale** usou ferramentas de IA no desenvolvimento e na documentação dos controles de segurança (2FA com TOTP e proteção contra IDOR): em que partes a IA ajudou, o que a equipe decidiu e validou, e quais problemas foram encontrados e corrigidos durante a validação.

A IA foi usada como **auxílio**. As decisões de projeto, a execução dos testes, a revisão e a aprovação de cada alteração foram da equipe.

## 2. Ferramentas usadas

| Ferramenta | Quem usou | Para quê |
| --- | --- | --- |
| **Claude** (Anthropic) | Wendell Barboza | Geração e revisão de código, criação de testes, explicação do código, direcionamento das etapas, apoio no deploy e na documentação |
| **ChatGPT** (OpenAI) | Lucas Mendes | Estrutura e redação inicial de `README.md`, `modelo-ameacas.md` e deste arquivo (19/11/2026); apoio no deploy da Azure |
| **Gemini** (Google) | — | **Não** foi ferramenta de desenvolvimento: é a API usada pelo chat do próprio sistema, uma funcionalidade do produto. O contexto enviado a ele passa pelo mesmo filtro de IDOR |

## 3. Onde a IA ajudou

| Área | Como a IA ajudou | Artefatos |
| --- | --- | --- |
| **Geração de código** | Propôs a implementação do 2FA (segredo TOTP cifrado, QR Code, token temporário de uso único, códigos de recuperação com hash, limite de tentativas) e do controle de acesso por dono, revisada e ajustada pela equipe antes do commit | `usuarios/dois_fatores.py`, `usuarios/acesso.py`, `usuarios/views.py`, `usuarios/gestao.py`, `transporte/views.py`, `iot/views.py`, `alertas/views.py`, `dominio/views.py` |
| **Testes** | Sugeriu os cenários de ataque (troca de ID na URL e no corpo, enumeração, reuso de código e de token, recadastro do autenticador) e os testes automatizados | `usuarios/test_2fa.py`, `usuarios/test_idor.py`, `usuarios/test_idor_cadastros.py`, `seguranca/testes/` |
| **Consultas e explicação** | Explicou cada bloco de código e montou o mapa "controle → arquivo e linha", para a equipe conseguir explicar e alterar o código ao vivo na apresentação | Material de estudo pessoal (fora do repositório) |
| **Direcionamento** | Ajudou a planejar a ordem do trabalho: capturar a evidência do antes, implementar por fases (branches `seguranca/antes`, `seguranca/fase1`, `seguranca/fases234`), testar e capturar o depois | PRs #8, #9 e #10 |
| **Revisão** | Analisou os apontamentos de uma revisão de código: quais faziam sentido e quais não comprometiam a entrega. A equipe decidiu o que aplicar | PR #13 e PR #14 (`fix/revisao-de-codigo`) |
| **Deploy e ferramentas** | Orientou a configuração do Render e da Azure, a coleção do Postman e o diagnóstico de erros | `build.sh`, `seguranca/testes/caminho-do-vale.postman_collection.json` |
| **Documentação** | Ajudou a redigir `docs/API.md`, o `README.md` do projeto e os documentos desta pasta | `docs/`, `seguranca/` |

## 4. O que foi decidido e validado pela equipe

- **Regras de negócio:** os papéis (plataforma, vendedor, comprador e motorista) e quem pode ver e fazer o quê em cada viagem foram definidos pela equipe em 17/11/2026.
- **Execução dos testes:** os scripts foram rodados pelo Wendell contra a API publicada, antes e depois dos controles. Os resultados estão em `seguranca/evidencias/`, e não foram gerados pela IA.
- **Testes manuais:** o login em duas etapas e o IDOR também foram testados no Postman e no front, com contas diferentes (vendedor A e vendedor B).
- **Revisão e aprovação:** cada alteração entrou por pull request revisado e aprovado na `main`.
- **Segredos:** nenhuma senha, chave, segredo TOTP ou arquivo `.env` foi enviado às ferramentas de IA.

## 5. Problemas encontrados na validação e como foram corrigidos

Sugestões da IA não foram aceitas sem teste. Estes são exemplos reais de problemas que apareceram e foram corrigidos:

| Problema | Como foi percebido | Correção |
| --- | --- | --- |
| Algumas rotas checavam o estado da viagem antes do dono e respondiam 400 em vez de 403 para quem não era o dono | Testes automatizados | Reordenado: primeiro a verificação de dono, depois a de estado |
| Uma migration dependia de outra de outro app e quebrava o banco de teste | Execução dos testes | Dependência entre as migrations corrigida |
| O exemplo de segredo TOTP tinha 16 caracteres e foi recusado pela biblioteca `pyotp`, que exige 112 bits | Erro ao rodar o script de teste | Segredo gerado com `pyotp.random_base32()` (32 caracteres) |
| Testes falhavam com `DEBUG=False` por causa do redirecionamento para HTTPS (301) | Execução dos testes | Configuração própria para os testes |
| No deploy da Azure, o código do 2FA era sempre recusado para contas cadastradas no Render | Teste manual de login | O segredo é cifrado com uma chave do servidor, e os dois deploys usavam chaves diferentes. Corrigido definindo a mesma `OTP_ENCRYPTION_KEY` nos dois |
| A revisão de código apontou que o token temporário do login podia ser reaproveitado | Revisão de código | Token passou a valer uma vez só (teste 3b do `teste_otp.py`) |

## 6. Principais solicitações feitas à IA

Resumo fiel das principais solicitações (não é transcrição literal):

| Data | Solicitação | Objetivo |
| --- | --- | --- |
| 02/10/2026 | Montar a base da API: modelos, autenticação JWT, rotas e testes | Estrutura inicial do backend |
| 16 e 17/11/2026 | Guia pra implementar o 2FA com TOTP e a proteção contra IDOR | Controles exigidos pela atividade |
| 17/11/2026 | Criar scripts que testem os ataques antes e depois, com o código de missão no cabeçalho | Evidências |
| 19/11/2026 | Criar a gestão de usuários por convite, para não depender do `/admin` | Usabilidade e segurança |
| 19/11/2026 | Comparar o projeto com as tarefas de documentação e redigir os documentos faltantes (Lucas) | Documentação desta pasta |
| 22/11/2026 | Mapear cada controle para arquivo e linha e explicar como mostrar o antes | Preparação da apresentação |
| 23/11/2026 | Diagnosticar por que o 2FA não funcionava no deploy da Azure | Correção do deploy |

## 7. Commits com coautoria declarada da IA

Os commits de **02/10/2026** trazem no próprio Git a linha `Co-Authored-By: Claude`. Eles montaram a base da API, antes dos controles de segurança. O autor aparece como "Seu Nome" porque o Git ainda não estava configurado com o nome do autor.

| Commit | Mensagem | O que fez | Tamanho |
| --- | --- | --- | --- |
| `27676b0` | Adiciona models de domínio, iot e transporte com migrações | Primeiros modelos e migrations | 38 arquivos |
| `a76a055` | Fundação: PostgreSQL ativo, fuso correto, config via .env e permissões nativas | Configuração do banco e do ambiente | 6 arquivos |
| `8553623` | Modelagem: Leitura, Alerta e limites com faixa e margem crítica | Modelos de leitura, alerta e limites por fruta | 8 arquivos |
| `93f600b` | Autenticação JWT, endpoint /me e grupos de permissão | Login por token e grupos de permissão | 7 arquivos |
| `1e072d2` | API REST v1: services de negócio, serializers, views, rotas e admin | Primeira versão das rotas da API | 23 arquivos |
| `854f449` | Testes automatizados da API (33 testes) | Primeiros testes automatizados | 4 arquivos |

Os commits de segurança de novembro :

| Commit | Mensagem |
| --- | --- |
| `f2608a7` | Segurança: modelo de ameaças e testes do antes (IDOR e OTP) |
| `0eafeda` | Fase 1: papéis vendedor/comprador/motorista, donos da viagem e da placa |
| `b6c47c6` | Segurança: IDOR por dono, 2FA TOTP com códigos de recuperação e chat Gemini |
| `bf1af09` | Proteção IDOR em veículos e locais, rota de usuários, testes de alteração ao vivo |
| `11f1c17` | Gestão de usuários pela plataforma e docs da API |
| `0a651d4` | Correções da revisão: viagem e carga travadas após iniciar, alertas, integridade e token 2FA de uso único |

Os commits de documentação do Lucas (`86156a1` e `2302cec`, 19/11/2026) tiveram a redação inicial auxiliada pelo ChatGPT, conforme a seção 2.

## 8. Limitações e responsabilidade

Respostas de IA podem conter erros, sugestões incompletas ou suposições sobre os requisitos, como mostram os casos da seção 5. Por isso, todo código sugerido foi testado (178 testes automatizados, scripts de ataque e testes manuais) antes de entrar na `main`. A responsabilidade pelo código entregue e pelos resultados apresentados é da equipe.
