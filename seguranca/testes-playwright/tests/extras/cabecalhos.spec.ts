import { API_URL, FRONT_URL } from "../../support/config";
import { expect, test } from "../../support/fixtures";

/*
 * Extra (fora do "npm test"): endurecimento que nao faz parte dos dois controles do trabalho,
 * mas que um avaliador pode perguntar. Uma falha aqui e uma recomendacao, nao uma quebra do 2FA
 * ou do IDOR. Rode com: npm run test:extras
 */
const ORIGEM_MALICIOSA = "https://site-malicioso.example";
const HTTPS = (url: string) => url.startsWith("https://");

test.describe("Front: cabeçalhos de segurança", () => {
  let cabecalhos: Record<string, string> = {};

  test.beforeEach(async ({ request }) => {
    cabecalhos = (await request.get(`${FRONT_URL}/login`)).headers();
  });

  test("HTTPS obrigatório (Strict-Transport-Security)", async () => {
    test.skip(!HTTPS(FRONT_URL), "front local em http");
    expect(cabecalhos["strict-transport-security"]).toContain("max-age=");
  });

  test("o navegador não adivinha o tipo do arquivo (X-Content-Type-Options)", async () => {
    expect(cabecalhos["x-content-type-options"]).toBe("nosniff");
  });

  test("não pode ser colocado em iframe de outro site (X-Frame-Options ou CSP frame-ancestors)", async () => {
    const xfo = cabecalhos["x-frame-options"] ?? "";
    const csp = cabecalhos["content-security-policy"] ?? "";
    expect(/deny|sameorigin/i.test(xfo) || /frame-ancestors/i.test(csp), `X-Frame-Options="${xfo}" CSP="${csp}"`).toBe(true);
  });

  test("tem Content-Security-Policy", async () => {
    expect(cabecalhos["content-security-policy"] ?? "").not.toBe("");
  });

  test("clickjacking na prática: o front não abre dentro de um iframe", async ({ page }) => {
    await page.setContent(`<h1 style="font-family:sans-serif">Site malicioso</h1>
      <iframe src="${FRONT_URL}/login" style="width:1000px;height:560px;border:4px solid red"></iframe>`);
    await page.waitForTimeout(8_000);
    const quadro = page.frames().find((f) => f.url().startsWith(FRONT_URL));
    const carregou = quadro ? await quadro.locator("#root > *").count().catch(() => 0) : 0;
    await test.info().attach("site malicioso com o front no iframe", { body: await page.screenshot(), contentType: "image/png" });
    expect(carregou, "o front abriu dentro do iframe de outro site").toBe(0);
  });
});

test.describe("API: cabeçalhos, CORS e modo debug", () => {
  test("cabeçalhos de segurança do Django", async ({ api }) => {
    const h = (await api.get("/auth/me")).headers();
    expect(h["x-frame-options"]).toBe("DENY");
    expect(h["x-content-type-options"]).toBe("nosniff");
    if (HTTPS(API_URL)) expect(h["strict-transport-security"]).toContain("max-age=");
  });

  test("CORS: um site qualquer não lê as respostas da API", async ({ api }) => {
    const simples = await api.get("/auth/me", { headers: { Origin: ORIGEM_MALICIOSA } });
    const acao = simples.headers()["access-control-allow-origin"];
    expect(acao === ORIGEM_MALICIOSA || acao === "*", `Access-Control-Allow-Origin: ${acao}`).toBe(false);

    const preflight = await api.chamar("OPTIONS", "/auth/login", {
      headers: { Origin: ORIGEM_MALICIOSA, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type" },
    });
    const acaoPre = preflight.headers()["access-control-allow-origin"];
    expect(acaoPre === ORIGEM_MALICIOSA || acaoPre === "*", `preflight: ${acaoPre}`).toBe(false);
  });

  test("modo debug desligado: erro não mostra código nem configuração", async ({ api }) => {
    const origem = new URL(API_URL).origin;
    for (const rota of [`${origem}/rota-que-nao-existe-${Date.now()}`, `${API_URL}/shipments/abc`]) {
      const texto = await (await api.get(rota)).text();
      expect(texto, rota).not.toMatch(/Traceback|DEBUG = True|URLconf|settings\.py|SECRET_KEY/);
    }
  });

  test("redireciona http para https", async ({ api }) => {
    test.skip(!HTTPS(API_URL), "API local em http");
    const http = API_URL.replace("https://", "http://");
    const resposta = await api.chamar("GET", `${http}/auth/me`, { headers: {} });
    // O fetch segue o redirecionamento; o que importa é terminar em https.
    expect(resposta.url()).toMatch(/^https:\/\//);
  });
});
