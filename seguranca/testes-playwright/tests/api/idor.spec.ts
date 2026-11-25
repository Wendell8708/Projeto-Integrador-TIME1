import { Api } from "../../support/api";
import { ids, recursosDe, type Recursos } from "../../support/cenario";
import { dados, expect, RECUSADO, test } from "../../support/fixtures";
import { sessao } from "../../support/sessoes";

/*
 * Controle 2: protecao contra IDOR. O vendedor A, logado com a conta DELE, tenta ler, alterar e
 * comandar o que e do vendedor B so trocando o ID (na URL ou no corpo). Esperado: 404 para ID
 * na URL (o mesmo de "nao existe"), 403 para ID no corpo, e o B continua usando normalmente.
 */
test.describe.configure({ mode: "serial" });

let b: Recursos;
let a: Recursos;

test.beforeAll(async ({ request }) => {
  const api = new Api(request);
  b = await recursosDe(api, sessao("B"), "B");
  a = await recursosDe(api, sessao("A"), "A");
});

test.describe("IDOR: o A tenta usar o que é do B (ID na URL)", () => {
  const casos: [string, string, string, Record<string, unknown>?][] = [
    ["ler a viagem do B", "GET", "/shipments/{viagem}"],
    ["ler o resumo da viagem do B", "GET", "/shipments/{viagem}/summary"],
    ["ler as leituras da viagem do B", "GET", "/shipments/{viagem}/readings"],
    ["ler a placa do B", "GET", "/devices/{placa}"],
    ["ler o veículo do B", "GET", "/vehicles/{veiculo}"],
    ["ler a fazenda do B", "GET", "/locations/{fazenda}"],
    ["alterar a fazenda do B", "PATCH", "/locations/{fazenda}", { name: "invadida" }],
    ["alterar a placa do B", "PATCH", "/devices/{placa}", { name: "invadida" }],
    ["alterar a viagem do B", "PATCH", "/shipments/{viagem}", {}],
    ["iniciar a viagem do B", "POST", "/shipments/{viagem}/start"],
    ["encerrar a viagem do B", "POST", "/shipments/{viagem}/finish"],
    ["confirmar a entrega da viagem do B", "POST", "/shipments/{viagem}/confirm"],
  ];

  for (const [descricao, metodo, molde, corpo] of casos) {
    test(`${descricao}: ${metodo} ${molde}`, async ({ api }) => {
      const rota = molde.replace(/\{(\w+)\}/, (_, campo) => String(b[campo as keyof Recursos]));
      const opcoes = metodo === "POST" && !corpo ? { form: { condition: "good" } } : { json: corpo };
      const resposta = await api.chamar(metodo, rota, { token: sessao("A").access, ...opcoes });
      expect(RECUSADO, `${metodo} ${rota} respondeu ${resposta.status()}`).toContain(resposta.status());
    });
  }

  test("ler uma leitura, um item e um alerta do B pelo ID", async ({ api }) => {
    const tokenB = sessao("B").access;
    const leituras = ids(await dados(await api.get(`/shipments/${b.viagem}/readings`, { token: tokenB })));
    const itens = ids((await dados(await api.get(`/shipments/${b.viagem}`, { token: tokenB })))?.items);
    const todosAlertas: any[] = (await dados(await api.get("/alerts?page_size=200", { token: tokenB }))) ?? [];
    const alertas = ids(todosAlertas.filter((x) => x.shipment === b.viagem));
    const alvos = [
      ...leituras.slice(0, 1).map((id) => `/readings/${id}`),
      ...itens.slice(0, 1).map((id) => `/shipment-items/${id}`),
      ...alertas.slice(0, 1).map((id) => `/alerts/${id}`),
    ];
    test.skip(!alvos.length, "o B não tem leituras, itens nem alertas para testar");
    for (const rota of alvos) {
      const resposta = await api.get(rota, { token: sessao("A").access });
      expect(RECUSADO, `GET ${rota} respondeu ${resposta.status()}`).toContain(resposta.status());
    }
    for (const id of alertas.slice(0, 1)) {
      const resposta = await api.post(`/alerts/${id}/ack`, { token: sessao("A").access });
      expect(RECUSADO, `POST /alerts/${id}/ack respondeu ${resposta.status()}`).toContain(resposta.status());
    }
  });
});

test.describe("IDOR: as listas do A não trazem nada do B", () => {
  test("viagens, placas e leituras", async ({ api }) => {
    const token = sessao("A").access;
    expect(ids(await dados(await api.get("/shipments?page_size=200", { token })))).not.toContain(b.viagem);
    expect(ids(await dados(await api.get("/devices?page_size=200", { token })))).not.toContain(b.placa);
    const leituras: any[] = (await dados(await api.get("/readings?page_size=200", { token }))) ?? [];
    expect(leituras.filter((l) => l.shipment === b.viagem), "leituras da viagem do B na lista do A").toHaveLength(0);
    const alertas: any[] = (await dados(await api.get("/alerts?page_size=200", { token }))) ?? [];
    expect(alertas.filter((x) => x.shipment === b.viagem), "alertas da viagem do B na lista do A").toHaveLength(0);
  });

  test("filtro pela viagem ou placa do B na query string", async ({ api }) => {
    const token = sessao("A").access;
    const doB = (x: any) => x.shipment === b.viagem || x.id === b.viagem || x.device === b.placa;
    for (const rota of [`/readings?shipment=${b.viagem}`, `/alerts?shipment=${b.viagem}`, `/shipments?device=${b.placa}&page_size=200`]) {
      const lista = await dados(await api.get(rota, { token }));
      expect((Array.isArray(lista) ? lista : []).filter(doB), `GET ${rota} trouxe dados do B`).toHaveLength(0);
    }
  });
});

test.describe("IDOR: contorno pelo corpo da requisição", () => {
  test("placa do B na viagem do A", async ({ api }) => {
    const resposta = await api.patch(`/shipments/${a.viagem}`, { token: sessao("A").access, json: { device: b.placa } });
    expect(RECUSADO).toContain(resposta.status());
  });

  test("veículo do B na viagem do A", async ({ api }) => {
    const resposta = await api.patch(`/shipments/${a.viagem}`, { token: sessao("A").access, json: { vehicle: b.veiculo } });
    expect(RECUSADO).toContain(resposta.status());
  });

  test("fazenda do B como origem da viagem do A", async ({ api }) => {
    const fazenda = await dados(await api.get(`/locations/${b.fazenda}`, { token: sessao("B").access }));
    test.skip(fazenda?.owner == null, "a fazenda do B é um cadastro compartilhado (sem dono)");
    const resposta = await api.patch(`/shipments/${a.viagem}`, { token: sessao("A").access, json: { origin: b.fazenda } });
    expect(RECUSADO).toContain(resposta.status());
  });

  test("criar uma viagem nova com a placa do B", async ({ api }) => {
    const token = sessao("A").access;
    const fruta = ids(await dados(await api.get("/fruits", { token })))[0] ?? 1;
    const resposta = await api.post("/shipments", {
      token,
      json: {
        origin: a.fazenda, destination: a.destino, vehicle: a.veiculo, device: b.placa,
        started_at: new Date(Date.now() + 86_400_000).toISOString(),
        items: [{ fruit: fruta, lot: "TESTE-IDOR-CONTORNO", quantity_kg: "1.00" }],
      },
    });
    await test.info().attach("resposta", { body: await resposta.text(), contentType: "application/json" });
    expect(resposta.status(), "a viagem foi criada com a placa de outro usuário").not.toBe(201);
    // 403 (placa não é sua) ou 400 (a placa nem aparece como opção para o A).
    expect([400, 403, 404]).toContain(resposta.status());
  });
});

test.describe("IDOR: enumeração de IDs", () => {
  test("viagem do B e viagem inexistente dão a mesma resposta", async ({ api }) => {
    const token = sessao("A").access;
    const alheia = await api.get(`/shipments/${b.viagem}`, { token });
    const inexistente = await api.get("/shipments/999999999", { token });
    expect(alheia.status()).toBe(inexistente.status());
    expect(await alheia.text()).toBe(await inexistente.text());
  });

  test("placa do B e placa inexistente dão a mesma resposta", async ({ api }) => {
    const token = sessao("A").access;
    const alheia = await api.get(`/devices/${b.placa}`, { token });
    const inexistente = await api.get("/devices/999999999", { token });
    expect(alheia.status()).toBe(inexistente.status());
    expect(await alheia.text()).toBe(await inexistente.text());
  });
});

test.describe("IDOR: o dono continua usando", () => {
  test("o B lê a própria viagem, a placa e as leituras", async ({ api }) => {
    const token = sessao("B").access;
    expect((await api.get(`/shipments/${b.viagem}`, { token })).status()).toBe(200);
    expect((await api.get(`/devices/${b.placa}`, { token })).status()).toBe(200);
    expect((await api.get(`/shipments/${b.viagem}/readings`, { token })).status()).toBe(200);
  });
});

test.describe("IDOR: usuário novo (C) não vê nada dos outros", () => {
  test("listas vazias e 404 nos IDs do A e do B", async ({ api }) => {
    const token = sessao("C").access;
    expect(await dados(await api.get("/devices", { token }))).toEqual([]);
    expect(await dados(await api.get("/shipments", { token }))).toEqual([]);
    for (const rota of [`/shipments/${a.viagem}`, `/shipments/${b.viagem}`, `/devices/${a.placa}`, `/devices/${b.placa}`]) {
      const resposta = await api.get(rota, { token });
      expect(RECUSADO, `GET ${rota} respondeu ${resposta.status()}`).toContain(resposta.status());
    }
  });
});
