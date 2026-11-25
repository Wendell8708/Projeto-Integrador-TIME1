import { AVISO_CREDENCIAIS, TEM_CREDENCIAIS, USUARIOS } from "../../support/config";
import { dados, expect, RECUSADO, test } from "../../support/fixtures";
import { sessao } from "../../support/sessoes";

/*
 * Quem e o usuario vem SEMPRE do token JWT assinado. Estes testes tentam entrar sem token, com
 * token forjado ou com o token errado, e subir de papel (vendedor fazendo coisa da plataforma).
 */
const ROTAS_PROTEGIDAS = [
  "/auth/me", "/auth/users?role=buyer", "/shipments", "/shipments/current", "/shipment-items",
  "/devices", "/readings", "/alerts", "/locations", "/vehicles", "/fruits", "/fruit-parameters",
];

const b64url = (valor: object | string) =>
  Buffer.from(typeof valor === "string" ? valor : JSON.stringify(valor)).toString("base64url");
const lerParte = (token: string, indice: number) => JSON.parse(Buffer.from(token.split(".")[indice], "base64url").toString());

test.describe("Token: sem token ou com token inválido não entra", () => {
  test("rotas protegidas sem token respondem 401", async ({ api }) => {
    for (const rota of ROTAS_PROTEGIDAS) {
      const resposta = await api.get(rota);
      expect(resposta.status(), `GET ${rota} sem token`).toBe(401);
    }
  });

  test("token com lixo ou no formato errado responde 401", async ({ api }) => {
    for (const token of ["abc", "Bearer", "a.b.c", "eyJhbGciOiJIUzI1NiJ9.e30.assinatura"]) {
      const resposta = await api.get("/auth/me", { token });
      expect(resposta.status(), `token "${token}"`).toBe(401);
    }
  });

  test("JWT adulterado: trocar o user_id para o do B sem a chave", async ({ api }) => {
    const a = sessao("A");
    const b = sessao("B");
    const [cabecalho, , assinatura] = a.access.split(".");
    const conteudo = { ...lerParte(a.access, 1), user_id: b.user.id };
    const forjado = `${cabecalho}.${b64url(conteudo)}.${assinatura}`;
    const resposta = await api.get("/auth/me", { token: forjado });
    expect(resposta.status(), "o servidor aceitou um token alterado").toBe(401);
  });

  test('JWT com "alg: none" (sem assinatura) responde 401', async ({ api }) => {
    const a = sessao("A");
    const conteudo = lerParte(a.access, 1);
    for (const alg of ["none", "None", "NONE"]) {
      const forjado = `${b64url({ alg, typ: "JWT" })}.${b64url(conteudo)}.`;
      const resposta = await api.get("/auth/me", { token: forjado });
      expect(resposta.status(), `alg ${alg}`).toBe(401);
    }
  });

  test("o refresh token não serve como token de acesso", async ({ api }) => {
    const resposta = await api.get("/auth/me", { token: sessao("A").refresh });
    expect(resposta.status()).toBe(401);
  });

  test("o token de acesso vence (exp no token)", async () => {
    const conteudo = lerParte(sessao("A").access, 1);
    const minutos = (conteudo.exp - conteudo.iat) / 60;
    await test.info().attach("validade do access", { body: `${minutos} minutos`, contentType: "text/plain" });
    expect(minutos, "validade do token de acesso").toBeLessThanOrEqual(60);
  });
});

test.describe("Logout", () => {
  test("depois do logout, o refresh token deixa de valer", async ({ api }) => {
    test.skip(!TEM_CREDENCIAIS, AVISO_CREDENCIAIS);
    const nova = await api.entrar(USUARIOS.A); // sessão só deste teste, para não derrubar as outras
    const saiu = await api.post("/auth/logout", { token: nova.access, json: { refresh: nova.refresh } });
    expect(saiu.status()).toBe(200);
    const renovar = await api.post("/auth/refresh", { json: { refresh: nova.refresh } });
    expect(renovar.status(), "o refresh continuou valendo depois do logout").toBe(401);

    // Limitação conhecida (JWT): o access já emitido vale até vencer. Fica registrado no relatório.
    const me = await api.get("/auth/me", { token: nova.access });
    test.info().annotations.push({
      type: "limitação conhecida",
      description: `access depois do logout: ${me.status()} (JWT sem estado vale até expirar)`,
    });
  });

  test("o A não consegue fazer logout da sessão do B", async ({ api }) => {
    const a = sessao("A");
    const b = sessao("B");
    const resposta = await api.post("/auth/logout", { token: a.access, json: { refresh: b.refresh } });
    expect(resposta.status()).toBe(400);
    const renovar = await api.post("/auth/refresh", { json: { refresh: b.refresh } });
    expect(renovar.status(), "a sessão do B foi derrubada pelo A").toBe(200);
  });
});

test.describe("Papéis: vendedor não faz o que é da plataforma", () => {
  test("não lista todos os usuários (com e-mail)", async ({ api }) => {
    const resposta = await api.get("/auth/users", { token: sessao("A").access });
    expect(resposta.status()).not.toBe(200);
    expect(await resposta.text(), "a resposta trouxe e-mails de usuários").not.toContain("@teste.local");
  });

  test("a lista de compradores não traz e-mail", async ({ api }) => {
    const resposta = await api.get("/auth/users?role=buyer", { token: sessao("A").access });
    expect(resposta.status()).toBe(200);
    expect(await resposta.text()).not.toMatch(/"email"/);
  });

  test("não abre nem altera o cadastro do B", async ({ api }) => {
    const token = sessao("A").access;
    const idB = sessao("B").user.id;
    expect(RECUSADO).toContain((await api.get(`/auth/users/${idB}`, { token })).status());
    expect(RECUSADO).toContain((await api.patch(`/auth/users/${idB}`, { token, json: { is_active: false } })).status());
  });

  test("não reseta o 2FA do B", async ({ api }) => {
    const resposta = await api.post(`/auth/users/${sessao("B").user.id}/reset-2fa`, { token: sessao("A").access });
    expect(RECUSADO, "um vendedor conseguiu apagar o 2FA de outra pessoa").toContain(resposta.status());
  });

  test("não se promove a administrador", async ({ api }) => {
    const a = sessao("A");
    const resposta = await api.patch(`/auth/users/${a.user.id}`, { token: a.access, json: { role: "admin" } });
    expect(RECUSADO).toContain(resposta.status());
    const me = await dados(await api.get("/auth/me", { token: a.access }));
    expect(me.role ?? me.groups ?? "").not.toMatch(/admin/i);
  });

  test("não cria usuário", async ({ api }) => {
    const resposta = await api.post("/auth/users", {
      token: sessao("A").access,
      json: { name: "Invasor", email: `invasor-${Date.now()}@teste.local`, role: "admin" },
    });
    expect(RECUSADO).toContain(resposta.status());
  });
});
