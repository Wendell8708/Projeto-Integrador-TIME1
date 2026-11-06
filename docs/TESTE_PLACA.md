# Teste da placa real com a API

Passo a passo para ligar a ESP32-C3 na API e conferir que as leituras chegam, que reenviar não duplica,
que a queda de rede não perde dados e que o alerta aparece.

> **Regra de ouro:** chaves e senhas ficam **só** no `wifi_config.py` da placa (que não vai para o Git),
> no `.env` e nas variáveis do Render. Nunca no chat, no código, num PDF ou num print.

## Como funciona

```
DHT11 ──> ESP32-C3 ──(a cada 30 s)──> fila.jsonl (memória da placa)
                                          │
                  (a cada 30 s, com Wi-Fi) ▼
                      POST /iot/telemetry/batch   ──> API (Render) ──> PostgreSQL (Neon)
                      cabeçalho X-Device-Key              │
                                                          └─ responde só o que gravou
```

- A placa guarda cada leitura num **arquivo** antes de enviar. Só **apaga** da fila o que a API confirmar
  (`accepted_reading_sequences`). Sem rede, a fila cresce (até 3000 leituras) e esvazia quando a rede volta.
- Cada leitura tem um número `sequence` que **nunca se repete**, nem depois de reiniciar a placa.
  Se a API recebe o mesmo número de novo, **não grava em dobro** e confirma mesmo assim.
- A placa pergunta a cada 60 s `GET /iot/config`: "qual é a minha viagem ativa e quais os limites?".
  Sem viagem ativa, ela **não registra** leituras.
- O horário é acertado por NTP (ou pelo `server_time` da API) e enviado em UTC.

## 1. No backend (uma vez)

O backend já está pronto: **não precisa mudar código**. Faltam só dados no banco de produção (Neon).

| # | O quê | Como |
|---|---|---|
| 1 | Frutas e limites | `python manage.py carregar_limites_iniciais` (se a seed ainda não rodou). Os limites precisam estar **ativos**, senão não há alerta. |
| 2 | Cadastrar a placa | `uid` **igual** ao `DEVICE_UID` da placa (`VSF-001`). A seed já cria. |
| 3 | Gerar a chave da placa | `python manage.py criar_credencial_dispositivo VSF-001` |
| 4 | Criar a viagem | `POST /shipments` com `device`, `origin`, `destination`, `vehicle` |
| 5 | Colocar uma fruta na viagem | `POST /shipment-items` com `shipment`, `fruit`, `lot`, `quantity_kg` |
| 6 | Iniciar a viagem | `POST /shipments/{id}/start` |

Atenção ao passo 3:

- A chave aparece **uma única vez**. O banco guarda só o hash.
- Gerar uma nova **revoga a anterior**. Se a seed já gerou uma chave e a placa usa essa, a placa passa a receber 401.
- Rode com o `.env` apontando para o Neon (é o banco que a API no Render usa). Copie a chave direto para o
  `wifi_config.py` da placa e não a cole em lugar nenhum.

Confirme no Swagger (`/api/docs/`, depois de logar em `/admin/` com um usuário **staff**):
`GET /shipments/{id}` mostra `status: "active"`.

## 2. Na placa

Arquivos que vão para a placa:

| Arquivo | Para quê |
|---|---|
| `main.py` | Programa principal |
| `api_client.py` | Fila, `sequence`, lote e chamadas à API |
| `api_config.py` | URL da API, `DEVICE_UID` e intervalos |
| `mqtt_config.py` | Broker MQTT (continua funcionando) |
| `wifi_config.py` | **Segredos**: Wi-Fi e `DEVICE_KEY` (modelo em `wifi_config.example.py`) |

`wifi_config.py` precisa ter a chave:

```python
WIFI_SSID = "NOME_DA_REDE"
WIFI_PASSWORD = "SENHA_DA_REDE"
THINGSPEAK_WRITE_API_KEY = "..."
DEVICE_KEY = "a-chave-que-o-backend-mostrou-uma-vez"
```

Envio (troque `COM3` pela porta da sua placa):

```powershell
python -m mpremote connect COM3 fs cp .\src\api_config.py :api_config.py
python -m mpremote connect COM3 fs cp .\src\api_client.py :api_client.py
python -m mpremote connect COM3 fs cp .\src\main.py :main.py
python -m mpremote connect COM3 fs cp .\src\wifi_config.py :wifi_config.py
python -m mpremote connect COM3 reset
python -m mpremote connect COM3
```

## 3. O que você deve ver no terminal da placa

| Mensagem | Significa |
|---|---|
| `[Relogio] Acertado (UTC): 2026-...Z` | NTP funcionou |
| `[API] Pronta. Pendentes na fila: 0 \| viagem: 3` | Fila e chave carregadas |
| `[API] Viagem ativa: None -> 3` | A API disse qual é a viagem |
| `[API] Leitura 1 guardada. Pendentes: 1` | Leitura entrou na fila (a cada 30 s) |
| `[API] Envio: ok \| pendentes: 0` | A API gravou e confirmou |

Na API, confira em `GET /shipments/{id}/summary` (`metrics.readings`, `latest_reading`, `device.online`)
e em `GET /shipments/{id}/readings`.

## 4. Roteiro de testes

| # | Teste | Como | Esperado |
|---|---|---|---|
| 1 | Leitura chega | Deixe ligada 2 min | `readings` cresce; `device.online = true` |
| 2 | Horário certo | Compare `recorded_at` com o relógio do PC (UTC) | Diferença de segundos |
| 3 | Alerta | Aqueça o sensor com a mão até passar do limite | `open_alerts` sobe **depois de 2 leituras seguidas** (~1 min) e some sozinho quando volta |
| 4 | Sem rede | Desligue o Wi-Fi por 5 min | A placa segue guardando (`Pendentes` sobe); LED azul pisca |
| 5 | Rede volta | Religue o Wi-Fi | `Envio: ok` e `pendentes` volta a 0; `metrics.synced_after_offline` > 0; **sem duplicar** |
| 6 | Reinício | Desligue e ligue no meio da viagem | `sequence` continua de onde parou (não volta a 1); nada se perde |
| 7 | Chave errada | Troque 1 letra da `DEVICE_KEY` | `[API] Chave recusada (401)`; **a fila é mantida**; corrigindo a chave, tudo é enviado |
| 8 | Sem viagem | `POST /shipments/{id}/finish` | `Viagem ativa: 3 -> None`; leituras novas não são registradas |
| 9 | Dado atrasado | Encerre a viagem com leituras ainda na fila | A API **aceita** leituras de viagem `completed` |

## 5. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `Chave recusada (401)` | Chave errada ou **revogada** (alguém gerou outra) | Gere uma nova e atualize o `wifi_config.py` |
| `Config: sem resposta` na primeira vez | O Render gratuito dorme e leva ~1 min para acordar | Espere: a fila guarda e tenta de novo |
| `Sem viagem ativa: leitura nao registrada` | Nenhuma viagem `active` para esse dispositivo | Faça `start` na viagem; confira `device` = `VSF-001` |
| `Relogio sem acerto` | NTP bloqueado na rede | O horário da API (`server_time`) acerta sozinho na próxima consulta de configuração |
| `Envio: recusado` | A API rejeitou o lote (`400`) | Veja o `detail`; a leitura é descartada após 10 recusas, para não travar a fila |
| Não aparece alerta | Parâmetro da fruta **inativo** ou 1 só leitura fora da faixa | Ative o `fruit-parameter`; espere 2 leituras seguidas |
| Leituras com `recorded_at` de 2000/1970 | Relógio nunca foi acertado | Não acontece com o código novo: ele só registra com horário válido |

## 6. Limitações conhecidas

- O **ADXL345** ainda não está ligado: a leitura vai sem `impact_peak_g` (a API aceita) e não há eventos de impacto.
- O **MQTT** continua ativo num broker público, sem senha: serve de espelho para teste, **não** para dado real.
- O DHT11 mede só de 0 a 50 °C (±2 °C) e umidade de 20 a 90%: não serve para frutas que pedem perto de 0 °C (ex.: uva).
- A chamada HTTP bloqueia o laço da placa por até 30 s (tempo limite). Nesse intervalo o sensor e os LEDs param;
  nada se perde, a leitura seguinte entra na fila.
