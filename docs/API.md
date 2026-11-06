# API — guia rápido para o front e para a placa

Base: `https://projeto-integrador-time1.onrender.com/api/v1` · Swagger: `/api/docs/`
(em produção: faça login em `/admin/` com um usuário **staff** e volte para `/api/docs/`).

- Sucesso vem em `{"data": ...}`. Listas: `{"data": [...], "pagination": {"next", "previous", "count"}}`.
- Erro vem como `{"detail": "..."}` ou `{"campo": ["..."]}`.
- Rotas aceitam com ou sem barra no final.
- Pessoas: `Authorization: Bearer <access>`. Placa: `X-Device-Key: <chave>`.

## Autenticação

| Método | Rota | Corpo | Resposta (`data`) |
|---|---|---|---|
| POST | `/auth/login` | `{"email", "password"}` | `{"access", "refresh", "user": {"id", "name", "email", "role"}}` |
| POST | `/auth/refresh` | `{"refresh"}` | `{"access"}` |
| GET | `/auth/me` | — | usuário, `role`, grupos e permissões |

`role`: `admin`, `operator` ou `viewer`. O access vale 30 min; o refresh, 1 dia.

## Cadastros e viagens

| Método | Rota | O que faz |
|---|---|---|
| GET/POST | `/fruits` | Frutas com os limites ativos em `limits` |
| GET/POST | `/fruit-parameters` | Limites por fruta (só admin cria) |
| GET/POST | `/locations`, `/vehicles`, `/devices` | Cadastros |
| GET/POST | `/shipments` | Viagens (filtros: `status`, `device`, `origin`, `destination`) |
| POST | `/shipment-items` | Fruta e lote numa viagem |
| POST | `/shipments/{id}/start` | `planned` → `active` |
| POST | `/shipments/{id}/finish` | `active` → `completed` |
| GET | `/shipments/{id}/summary` | Card do dashboard |
| GET | `/shipments/{id}/readings` | Histórico (`?start=`, `?end=`, `?since=`) |
| GET | `/shipments/{id}/shocks` | Impactos |
| GET | `/shipments/{id}/alerts` | Alertas |
| GET | `/alerts` | Todos os alertas (filtros: `shipment`, `type`, `severity`, `status`) |
| POST | `/alerts/{id}/ack` · `/alerts/{id}/resolve` | Reconhecer · encerrar |

Tempo real: chame `/summary` e `/readings?since=<recorded_at da última leitura>` a cada 5–10 s.

## Placa (ESP32)

| Método | Rota | Para quê |
|---|---|---|
| GET | `/iot/config` | Viagem ativa (`shipment_id`) e limites da placa |
| POST | `/iot/telemetry/batch` | Envia leituras e impactos em lote |
| POST | `/iot/heartbeat` | `{"network": "wifi", "wifi_ssid": "..."}`: marca a placa como online |

Lote (até 200 itens):

```json
{
  "device_uid": "VSF-001",
  "shipment_id": 3,
  "network": "wifi",
  "readings": [
    {"sequence": 1001, "recorded_at": "2026-10-31T10:00:00Z", "temperature_c": 7.8, "humidity_pct": 88.2, "impact_peak_g": 1.6}
  ],
  "shocks": [
    {"event_id": "evt-001", "recorded_at": "2026-10-31T10:02:00Z", "impact_peak_g": 3.1}
  ]
}
```

Resposta: `{"data": {"accepted_reading_sequences": [1001], "accepted_shock_ids": ["evt-001"]}}`.
A placa apaga da fila local só o que vier nessas listas. Reenviar não duplica.

Regras para a placa: `recorded_at` em UTC; `sequence` salvo na flash e nunca reiniciado;
a viagem precisa estar `active` (ou `completed`, para dado atrasado).
A chave sai do comando `python manage.py criar_credencial_dispositivo <uid>` ou da seed.

Passo a passo do teste com a placa real: [`TESTE_PLACA.md`](TESTE_PLACA.md).
