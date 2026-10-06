# Relatório de alterações: base da API (piADS04)

Este relatório explica **o que foi feito, por que e como**, em ordem. Serve de guia para conferir o código junto com o time.

> Escopo: backend/API. Ficou **de fora** (para ser feito em conjunto): integração com o ThingSpeak e a comparação ThingSpeak × envio direto do ESP32.

---

## 0. Como rodar e conferir

```powershell
cd C:\Users\gs_cl\Documents\piAds04
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py criar_grupos
python manage.py carregar_limites_iniciais
python manage.py createsuperuser
python manage.py runserver
```

- Swagger (documentação interativa): http://127.0.0.1:8000/api/docs/ (aberta só com `DEBUG=True` no `.env`)
- Admin: http://127.0.0.1:8000/admin/
- Testes: `python manage.py test` (33 testes)

No `.env`, além das variáveis já existentes, acrescente `DEBUG=True` para desenvolvimento (veja o `.env.example`). Sem ela o sistema assume `DEBUG=False`, por segurança.

---

## 1. Problema encontrado: o banco ativo era SQLite

**O que era:** no `settings.py` o bloco do PostgreSQL estava comentado e o SQLite ativo. O `migrate` anterior criou tabelas no `db.sqlite3`, não no PostgreSQL.

**O que foi feito:** o PostgreSQL passou a ser o único banco, configurado por variáveis do `.env` (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`). O primeiro `migrate` real foi executado nele.

## 2. `piADS04/settings.py`

| Mudança | Por quê |
|---|---|
| `TIME_ZONE = 'America/Recife'` (era `'utf-8'`) | `'utf-8'` não é um fuso. O banco guarda em UTC; o fuso só afeta a exibição, mas precisa ser válido. |
| `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` lidos do `.env` | Valores que mudam entre máquinas ou ambientes não ficam fixos no código. `DEBUG` é `False` por padrão (seguro). |
| Removido `MAILERS` | Não é uma configuração do Django; não fazia nada. |
| `SIMPLE_JWT`: access 30 min, refresh 1 dia | Access curto limita o estrago se vazar; o refresh evita novo login a toda hora. |
| `REST_FRAMEWORK`: permissão padrão, filtros, paginação (50) | Todas as views herdam o mesmo comportamento seguro e consistente. |
| `django_filters` e `drf_spectacular` | Filtros por query string e documentação Swagger automática. |
| `DEFAULT_AUTO_FIELD = BigAutoField` | IDs de 64 bits: leituras de sensor crescem rápido. |

Arquivos novos: `.env.example` (modelo sem valores reais, vai para o Git) e `requirements.txt` (para o time reproduzir o ambiente).

## 3. App `usuarios`: autenticação e permissões

Decisão mantida: **só o sistema nativo do Django** (`User`, `Group`, `Permission`). O `UserProfile` foi **removido** (migração `0002_delete_userprofile`).

### Endpoints

| Rota | O que faz |
|---|---|
| `POST /api/v1/auth/token/` | Login: recebe `username` e `password`, devolve `access` e `refresh`. |
| `POST /api/v1/auth/token/refresh/` | Troca o `refresh` por um novo `access`. |
| `GET /api/v1/auth/me/` | Devolve o usuário logado, seus grupos e permissões (o React decide o que mostrar). |

O frontend envia o token em todas as chamadas: `Authorization: Bearer <access>`.

### `usuarios/permissions.py`

- **`PermissaoPorModelo`**: usa as permissões automáticas do Django (`add_`, `change_`, `delete_`, `view_`). O `DjangoModelPermissions` original deixa qualquer usuário logado fazer `GET`; aqui `GET` exige `view_<model>`. É a permissão **padrão** de todas as views.
- **`PodeAlterarModelo`**: para ações que mudam um registro existente via `POST` (iniciar/concluir transporte, reconhecer alerta). Exige `change_<model>` em vez de `add_`.

### Comando `criar_grupos` (idempotente)

| Grupo | Pode |
|---|---|
| **Administrador** | tudo (36 permissões) |
| **Operador** | ver tudo; criar/editar locais, veículos, transportes e cargas; reconhecer alertas (18) |
| **Visualizador** | só consultar (9) |

Rodar de novo deixa os grupos exatamente como definido no arquivo.

## 4. Modelagem

### `iot.Leitura` (novo): o coração do histórico
- `medido_em`: hora em que o **sensor** mediu (vale para o histórico). `recebido_em`: hora em que o servidor recebeu (acha atrasos).
- `origem_id`: o `entry_id` do ThingSpeak. Há uma regra única `(dispositivo, origem_id)`: sincronizar duas vezes a mesma leitura **não duplica**.
- Índice `(dispositivo, -medido_em)` para a consulta mais comum (histórico por período).
- Validação: umidade 0–100, temperatura −50 a 100.

### `alertas.Alerta` (novo)
- `tipo` (temperatura/umidade), `severidade` (atenção/crítico), `status` (aberto/reconhecido/resolvido).
- Guarda `valor_medido` e `limite_violado` **na hora do alerta**: se a faixa mudar depois, o histórico continua fiel.
- Regra no banco: **no máximo um alerta ativo por transporte e tipo** (evita 500 alertas iguais).

### `dominio.ConfiguracaoLimite` (alterado)
- Faixa ideal de temperatura e umidade por fruta, mais **margem crítica** de cada uma, e o campo `fonte` (de onde veio o dado).
- Como o status é decidido: dentro da faixa → **normal**; fora até a margem → **atenção**; além da margem → **crítico**. Exemplo: faixa 8–12 °C, margem 3: 7 °C é atenção; 4 °C é crítico.
- Removidos `data_inicio`/`data_fim` (o histórico fiel já fica no `Alerta`).
- Regras no banco: mínimo < máximo; **uma faixa ativa por fruta**.

### `transporte` (reforçado)
- Regras no banco: origem ≠ destino; fim > início; quantidade > 0; mesma fruta+lote não repete no transporte.
- `Transporte.leituras()`: o histórico do dispositivo **durante** a viagem (do início ao fim, ou até agora).

### Correção
- `_str_` → `__str__` em todos os models (com um underscore só, o Django ignorava).

## 5. Regras de negócio (`services.py`): onde fica a inteligência

A regra é: **a view não decide nada, só orquestra**. Isso permite trocar o ThingSpeak por envio direto do ESP32 sem mexer nas regras.

### `transporte/services.py`
- **`faixa_ideal_de_frutas(frutas_ids)`**: calcula a faixa para um caminhão. Com várias frutas usa a **interseção** (maior mínimo, menor máximo) e a **menor margem crítica** (a mais rigorosa). Devolve `None` se nenhuma fruta tem limite ativo; levanta `CargaIncompativel` se não há faixa em comum.
- **`faixa_ideal(transporte)`**: o mesmo, a partir das cargas do transporte.
- **`transporte_ativo_para(dispositivo, instante)`**: descobre a que viagem uma leitura pertence (dispositivo + transporte **em andamento** + horário).
- **`resumo_do_transporte(transporte)`**: monta o card do dashboard (estatísticas, última leitura, faixa ideal, alertas ativos e `status_atual`: sem_dados/normal/atenção/crítico).

### `alertas/services.py`
- **`classificar(valor, minimo, maximo, margem)`**: função pura que devolve `(nível, limite_violado)`.
- **`classificar_leitura(leitura, faixa)`**: aplica a classificação a temperatura e umidade.
- **`avaliar_leitura(leitura)`**: o fluxo completo:
  1. acha o transporte da leitura; se não há, nada a avaliar;
  2. obtém a faixa ideal;
  3. classifica cada medida;
  4. **só abre alerta se as últimas `LEITURAS_CONSECUTIVAS = 2` leituras estão fora da faixa** (o DHT11 erra ~±2 °C e ±5% de umidade; isso evita alarme falso);
  5. se já há alerta ativo do mesmo tipo, não duplica, e sobe para crítico se piorar;
  6. quando a medida volta ao normal, o alerta ativo é **resolvido** sozinho.

### `iot/services.py`
- **`registrar_leitura(...)`**: **porta única** de entrada de leituras (API manual hoje; sincronização do ThingSpeak ou ESP32 direto depois). Grava sem duplicar (por `origem_id`) e chama a avaliação de alertas.

## 6. API (`/api/v1/`)

Cada app segue as camadas: `models` → `serializers` (JSON e validação) → `views` (finas) → `urls` (rotas geradas por router).

| Recurso | Rotas | Observações |
|---|---|---|
| Locais, veículos, frutas, limites, dispositivos, cargas | CRUD em `/locais/`, `/veiculos/`, `/frutas/`, `/limites/`, `/dispositivos/`, `/cargas/` | Limites validam min < max e uma faixa ativa por fruta; carga recusa fruta **incompatível** com as outras do caminhão. |
| Transportes | CRUD em `/transportes/` | O `status` **não** é editável direto: só pelas ações abaixo. |
| `POST /transportes/{id}/iniciar/` | planejado → em andamento | Exige ≥ 1 carga e dispositivo livre. Registra o início real. |
| `POST /transportes/{id}/concluir/` | em andamento → concluído | Registra o fim real. |
| `GET /transportes/{id}/leituras/` | histórico, paginado | Filtros `?inicio=` e `?fim=` (ISO 8601). |
| `GET /transportes/{id}/resumo/` | dados do dashboard | Estatísticas, última leitura, faixa e status. |
| `GET /transportes/{id}/alertas/` | alertas do transporte | |
| `/leituras/` | listar, ver e criar | Sem editar/apagar: medição histórica não se altera. Filtros `dispositivo`, `inicio`, `fim`. |
| `/alertas/` | listar e ver; `POST /alertas/{id}/reconhecer/` | Alertas são criados só pelo sistema. |

Também: `/api/schema/` (OpenAPI) e `/api/docs/` (Swagger). O schema foi validado **sem avisos**.

## 7. Testes (33, todos passando)

- Classificação normal/atenção/crítico (inclusive limites exatos).
- Alertas: tolerância de leituras consecutivas, sem duplicar, escalar para crítico, resolver ao normalizar, umidade independente, dedupe por `origem_id`, leitura fora de viagem.
- Faixa ideal: uma fruta, carga mista (interseção), carga incompatível, sem limites.
- Login JWT, refresh, `/me`, e permissões de cada grupo.
- Fluxo completo: leitura → alerta → resumo → reconhecer.

## 8. Pesquisa de temperaturas (e limitações)

Comando `carregar_limites_iniciais` cria 5 frutas com faixas **inativas e marcadas "A CONFERIR"** (não geram alertas até serem validadas).

| Fruta | Temp. (°C) | Umid. (%) | Situação da fonte |
|---|---|---|---|
| Uva de mesa | 0 a 1 | 85 a 95 | Embrapa e USDA concordam. |
| Manga | 10 a 13 | 85 a 90 | Embrapa e USDA; varia com a maturação. |
| Melão amarelo | 10 a 12 | 85 a 90 | Embrapa (temp.); **umidade assumida**; CEAGESP cita 7–10 °C: divergência. |
| Goiaba | 7 a 10 | 85 a 95 | UF/USDA; faixa de umidade em torno de 90% assumida. |
| Banana | 13 a 15 | 85 a 95 | Embrapa (mín. 85%); máximo assumido. |

**Lacunas honestas:**
- Não consegui abrir os PDFs originais da Embrapa (servidor retornou erro 503); os valores vêm de **resumos de busca**. É preciso conferir na fonte antes de ativar.
- **Melancia** e **acerola**: sem dado confiável encontrado, então não foram incluídas.
- **DHT11**: mede 0 a 50 °C (±2 °C) e umidade 20–90% (±5%). Para **uva** (próxima de 0 °C) e umidades acima de 90%, o sensor **não é confiável**. Vale discutir um DHT22 ou SHT3x.

## 9. Pendências 

1. Conferir as faixas na fonte, ajustar e ativar.
2. Decidir se `LEITURAS_CONSECUTIVAS = 2` e as margens críticas (3 °C, 10 pontos) fazem sentido.
3. Revisar as permissões do **Operador** (hoje não edita limites nem dispositivos).
4. **Integração com o ThingSpeak** (sincronização periódica chamando `registrar_leitura`) e a comparação com envio direto do ESP32 (que precisaria de uma chave de API por dispositivo, e não de login de usuário).
5. Decidir o formato de deploy (PythonAnywhere) e variáveis de produção.
6. Os arquivos `db.sqlite3` e `.pyc` saíram do Git; avisar o time.
