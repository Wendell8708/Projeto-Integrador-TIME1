# Testes de segurança com Playwright

Ataques automatizados contra o **front publicado (Vercel)** e a **API de verdade (Render)**, sem backend simulado. Cobrem os dois controles do trabalho (2FA e IDOR) e o que está em volta deles: token, sessão, papéis, chave da placa e limite de tentativas.

Os scripts Python de [`../testes/`](../testes/) continuam valendo. Esta pasta faz os mesmos ataques e mais alguns, gera vídeo e prints de cada teste e mostra tudo passo a passo no modo `--ui`.

## Preparar (uma vez)

```powershell
cd seguranca/testes-playwright
npm install
copy .env.example .env      # preencha TESTE_SENHA e TESTE_TOTP_SEGREDO (peça ao Wendell Barboza)
```

- Os usuários de teste (`vendedor-a/b/c@teste.local`) e as viagens `TESTE-IDOR-A/B` vêm de `python manage.py preparar_teste_seguranca --terceiro`, rodado no banco que a API usa.
- O navegador padrão é o Google Chrome instalado. Para usar o Chromium do Playwright, deixe `PW_CHANNEL=` vazio no `.env` e rode `npx playwright install chromium`.
- Sem `TESTE_SENHA`, os testes que precisam de login são **pulados** (com o motivo). Os que não precisam rodam assim mesmo: rotas sem token, chave falsa da placa e telas sem login.

## Rodar

| Comando | O que faz |
| --- | --- |
| `npm test` | Tudo: API, tela e, por último, o limite de tentativas |
| `npm run test:completo` | O mesmo, incluindo os testes lentos (validade de 5 min do `mfa_token`) |
| `npm run video` | Grava um vídeo por capítulo para a apresentação (pasta em `VIDEO_DESTINO`) |
| `npm run test:api` | Só os ataques direto na API |
| `npm run test:tela` | Só os testes pela tela do front |
| `npm run test:limite` | Força bruta (deixa o IP bloqueado por ~1 min) |
| `npm run test:extras` | Cabeçalhos do front e da API, CORS, iframe e modo debug |
| `npm run ui` | **Modo visual** (`--ui`) em câmera lenta, para gravar a apresentação |
| `npm run apresentacao` | Roda API + tela com o navegador aberto, em câmera lenta |
| `npm run relatorio` | Abre o relatório HTML com vídeos, prints e trace de cada teste |

Para testar local: `FRONT_URL=http://localhost:5173` e `API_URL=http://127.0.0.1:8000/api/v1` no `.env`.

## O que é testado

| Arquivo | Ataques | Esperado |
| --- | --- | --- |
| `tests/api/2fa.spec.ts` | senha sem código; código errado, malformado, vencido (1 min atrás) e "do futuro"; código válido; `mfa_token` reaproveitado e adulterado; código reutilizado; **corrida** (mesmo código e mesmo código de recuperação enviados 2× ao mesmo tempo); recuperação usada duas vezes; lista antiga de recuperação anulada ao gerar outra; rota de novos códigos exige login e código atual; recadastrar o autenticador só com a senha; **validade de 5 min do `mfa_token`** (lento, `npm run test:completo`); **primeiro acesso** com QR Code e ativação (precisa de `TESTE_USUARIO_SEM_2FA`) | só o código certo entra, uma vez; o resto 400/401 |
| `tests/api/idor.spec.ts` | A lê, altera, inicia, encerra e confirma a viagem, a placa, o veículo, a fazenda, as leituras, os itens e os alertas do B pelo ID; listas e filtros; ID do B no corpo (placa, veículo, origem, viagem nova); enumeração; usuário C | 404 no ID da URL, 403 no ID do corpo, mesma resposta para "é do outro" e "não existe"; o B continua usando |
| `tests/api/sessao.spec.ts` | sem token, token com lixo, JWT com `user_id` trocado, `alg: none`, refresh usado como access, logout (refresh deixa de valer), logout da sessão de outro, vendedor tentando listar/alterar usuários, resetar o 2FA do B, virar admin, criar usuário | 401 / 403 |
| `tests/api/placa.spec.ts` | rotas `/iot/*` sem `X-Device-Key`, com chave falsa e com o JWT de uma pessoa | 401 |
| `tests/tela/2fa-tela.spec.ts` | login pela tela: senha não abre o painel, código errado, código certo, sair; telas internas sem login | igual à API, visto no front |
| `tests/tela/idor-tela.spec.ts` | o B abre a própria viagem; o A cola a mesma URL na janela dele | "Viagem não encontrada" e 404 da API |
| `tests/limite.spec.ts` | chutes seguidos de código e de senha | 429 antes da 11ª tentativa |
| `tests/extras/cabecalhos.spec.ts` | HSTS, nosniff, X-Frame-Options/CSP, front dentro de iframe, CORS de site qualquer, página de erro do Django | recomendações (fora do `npm test`) |

## Para a apresentação (vídeo e modo `--ui`)

`npm run ui` abre o Playwright em modo visual, com `APRESENTACAO=1` (passos mais lentos e pausas para leitura):

- **Lista da esquerda:** os testes. Ao clicar em um, cada requisição aparece como um passo com o resultado no nome, por exemplo `A  GET /shipments/13  ->  404 recusado`.
- **Tela da direita:** o que o navegador mostrava naquele passo.
  - Nos testes de **API**, é o **painel da API**: cada ataque entra numa linha com quem chamou, a rota e o status (verde = recusado, azul = aceito).
  - Nos testes de **tela**, é o **front**, com uma legenda no topo explicando o passo e um quadro no canto com as respostas da API. Front e back aparecem juntos.
- **Abas de baixo:** *Console* (o log de todas as requisições), *Network* e *Attachments* (vídeo, prints e lista de requisições).

Todo teste grava **vídeo**, **trace** e **print**. Ficam no relatório HTML (`npm run relatorio`) e em `test-results/`. O IDOR pela tela grava um vídeo por janela (A e B).

## Evidências

Cada execução grava `evidencias/<MISSAO>-playwright-<data>.txt`, no formato dos arquivos de [`../evidencias/`](../evidencias/): uma linha por teste (PROTEGIDO, VULNERÁVEL, ERRO ou PULADO) e as requisições feitas, com o status de cada uma. Senhas e tokens nunca entram nesse arquivo.

## Cuidados

- Por padrão os testes batem na **API de produção**. Eles só leem e tentam ações que devem ser recusadas. Se algum controle falhar, a ação passa de verdade (por exemplo, renomear a fazenda do B). Nesse caso, rode `preparar_teste_seguranca` de novo.
- O teste de recuperação **gera códigos de recuperação novos** para o vendedor A.
- O `limite` deixa o IP sem conseguir logar por cerca de 1 minuto. Por isso ele roda por último.
- `.env`, `.auth/` (tokens das sessões), `relatorio/`, `test-results/` e `evidencias/` estão no `.gitignore`.
