import { copyFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { Api, dados, type Opcoes, type Sessao } from "../../support/api";
import { recursosDe } from "../../support/cenario";
import { API_URL, FRONT_URL, SEGREDO_TOTP, SENHA, TEM_CREDENCIAIS, USUARIOS, AVISO_CREDENCIAIS } from "../../support/config";
import { abrirPainel, legenda, linhaNoPainel, mostrarApiNoFront, notaNoPainel } from "../../support/painel";
import { sessaoOpcional } from "../../support/sessoes";
import { codigoDoPasso, marcarPassoUsado, passoAtual, proximoPasso } from "../../support/totp";

/*
 * npm run video: grava um video por capitulo (cada frente de ataque) para a apresentacao.
 * Os videos e o indice capitulos.js vao para evidencias/videos/ e, se VIDEO_DESTINO estiver
 * definido, sao copiados para la (a pasta "videos" ao lado da apresentacao).
 * Os capitulos que precisam de login so rodam com TESTE_SENHA e TESTE_TOTP_SEGREDO no .env.
 */
const CAPITULOS = [
  { arquivo: "01-front-sem-login.webm", titulo: "Front: quem não entrou fica no login" },
  { arquivo: "02-2fa-tela.webm", titulo: "Login com 2FA pela tela" },
  { arquivo: "03-2fa-api.webm", titulo: "2FA atacado direto na API" },
  { arquivo: "04-idor-tela.webm", titulo: "IDOR pela tela: A abre a viagem do B" },
  { arquivo: "05-idor-api.webm", titulo: "IDOR na API: A contra os dados do B" },
  { arquivo: "06-token-papeis.webm", titulo: "Token forjado, logout e papéis" },
  { arquivo: "07-placa.webm", titulo: "Placa ESP32: só com a chave dela" },
  { arquivo: "08-cabecalhos-cors.webm", titulo: "Cabeçalhos e CORS da API" },
  { arquivo: "09-forca-bruta.webm", titulo: "Força bruta: limite de tentativas" },
] as const;
type Arquivo = (typeof CAPITULOS)[number]["arquivo"];

const PASTA = fileURLToPath(new URL("../../evidencias/videos/", import.meta.url));
const DESTINO = process.env.VIDEO_DESTINO;
const ROTAS = ["/auth/me", "/shipments", "/devices", "/readings", "/alerts", "/locations", "/vehicles", "/auth/users?role=buyer"];
const RECUSA = [400, 401, 403, 404];
const b64url = (v: object) => Buffer.from(JSON.stringify(v)).toString("base64url");
const lerParte = (token: string, i: number) => JSON.parse(Buffer.from(token.split(".")[i], "base64url").toString());

/** Estado de um capitulo: a pagina gravada, o cliente da API ligado ao painel e a contagem. */
class Cena {
  recusadas = 0;
  legitimas = 0;
  readonly api: Api;
  readonly preparo: Api; // chamadas de bastidor, fora do painel

  constructor(readonly page: Page) {
    this.api = new Api(page.request, (linha) => linhaNoPainel(page, linha));
    this.api.aoEsperar = (s) => notaNoPainel(page, `O servidor aplicou o limite de tentativas: aguardando ${s} s para continuar.`);
    this.preparo = new Api(page.request);
  }

  async cartao(titulo: string, subtitulo: string, rodape = "Caminho do Vale · Playwright", ms = 4000) {
    await this.page.setContent(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>
      body { margin: 0; height: 100vh; display: flex; align-items: center; justify-content: center; text-align: center;
        background: linear-gradient(145deg, #1a7a44, #16643a 70%, #124e2e); color: #fff; font-family: "Segoe UI", system-ui, sans-serif; }
      h1 { font-size: 52px; margin: 0 50px; } p { font-size: 25px; line-height: 1.45; color: #bfe3c8; margin: 18px 90px 0; }
      small { display: block; margin-top: 34px; font-size: 18px; letter-spacing: .14em; text-transform: uppercase; color: #f2c94c; }
    </style></head><body><div><h1></h1><p></p><small></small></div></body></html>`);
    await this.page.evaluate(([t, s, r]) => {
      document.querySelector("h1")!.textContent = t;
      document.querySelector("p")!.textContent = s;
      document.querySelector("small")!.textContent = r;
    }, [titulo, subtitulo, rodape]);
    await this.page.waitForTimeout(ms);
  }

  painel = (titulo: string, subtitulo = `Ataques direto na API · ${API_URL}`) => abrirPainel(this.page, titulo, subtitulo);
  nota = (texto: string) => notaNoPainel(this.page, texto);

  /** Um ataque: o servidor tem que recusar (400/401/403/404, ou a lista informada). */
  async ataque(metodo: string, rota: string, opcoes: Opcoes = {}, esperado: number[] = RECUSA) {
    const resposta = await this.api.chamar(metodo, rota, opcoes);
    expect(esperado, `${metodo} ${rota} respondeu ${resposta.status()}`).toContain(resposta.status());
    this.recusadas++;
    return resposta;
  }

  /** Uso legitimo (o dono com a credencial certa): tem que funcionar. */
  async legitimo(metodo: string, rota: string, opcoes: Opcoes = {}) {
    const resposta = await this.api.chamar(metodo, rota, opcoes);
    expect(resposta.ok(), `${metodo} ${rota} respondeu ${resposta.status()}`).toBe(true);
    this.legitimas++;
    return resposta;
  }

  /** Cartao final com a contagem real, salva o video e atualiza o indice dos capitulos. */
  async encerrar(arquivo: Arquivo, conclusao: string) {
    const dono = this.legitimas ? ` O uso legítimo continuou funcionando (${this.legitimas}).` : "";
    if (this.recusadas) await this.cartao(`${this.recusadas} ataques, todos recusados`, `${conclusao}${dono}`, "Resultado: PROTEGIDO");
    else await this.cartao("Resultado: PROTEGIDO", `${conclusao}${dono}`);
    const video = this.page.video();
    await this.page.close();
    if (!video) return;
    mkdirSync(PASTA, { recursive: true });
    await video.saveAs(join(PASTA, arquivo));
    salvarIndice(arquivo);
  }
}

function salvarIndice(novo: Arquivo) {
  const lista = CAPITULOS.filter((c) => existsSync(join(PASTA, c.arquivo)));
  const conteudo = `// Gerado por "npm run video". Lista dos capitulos que o slide toca em sequencia.\nwindow.CAPITULOS = ${JSON.stringify(lista, null, 2)};\n`;
  writeFileSync(join(PASTA, "capitulos.js"), conteudo);
  if (DESTINO) {
    mkdirSync(DESTINO, { recursive: true });
    copyFileSync(join(PASTA, novo), join(DESTINO, novo));
    writeFileSync(join(DESTINO, "capitulos.js"), conteudo);
  }
  console.log(`Capitulo gravado: ${novo}`);
}

/** Abre o front e espera a tela de abertura sumir. */
async function abrirFront(page: Page, rota: string) {
  await page.goto(`${FRONT_URL}${rota}`);
  await expect(page.getByRole("heading", { name: "Entrar no painel" }).or(page.getByRole("button", { name: "Menu do usuário" })))
    .toBeVisible({ timeout: 120_000 });
  await expect(page.getByLabel("Carregando aplicativo")).toBeHidden({ timeout: 30_000 });
}

async function sessaoNoNavegador(page: Page, s: Sessao) {
  await page.evaluate((sessao) => {
    localStorage.setItem("cdv.session", JSON.stringify(sessao));
    localStorage.setItem("cdv.assistant.seen", "1");
  }, { ...s, twoFactor: true });
}

const precisaLogin = () => test.skip(!TEM_CREDENCIAIS, AVISO_CREDENCIAIS);
const sessaoObrigatoria = (letra: "A" | "B") => {
  const s = sessaoOpcional(letra);
  test.skip(!s, `Sem sessao do usuario ${letra}. ${AVISO_CREDENCIAIS}`);
  return s!;
};

test.describe("Video da automacao (capitulos)", () => {
  test.beforeEach(() => test.setTimeout(900_000));

  test("01 front sem login", async ({ page }) => {
    const cena = new Cena(page);
    await cena.cartao("O front sem login", "Um visitante tenta abrir as telas internas do painel direto pela URL, sem ter entrado.");
    mostrarApiNoFront(page, "tela", []);
    for (const rota of ["/", "/cargas", "/cargas/VG-1", "/configuracoes", "/alertas"]) {
      await abrirFront(page, rota);
      await expect(page).toHaveURL(/\/login$/);
      cena.recusadas++;
      await legenda(page, `Sem login, ${rota} volta para a tela de login`);
      await page.waitForTimeout(2200);
    }
    await cena.encerrar("01-front-sem-login.webm", "Nenhuma tela interna abriu sem login, e nenhum dado foi pedido à API.");
  });

  test("02 login com 2FA pela tela", async ({ page }) => {
    precisaLogin();
    const cena = new Cena(page);
    await cena.cartao("Login com 2FA pela tela", "O vendedor A entra no painel publicado. A senha sozinha não basta: o servidor exige o código do aplicativo autenticador.");
    mostrarApiNoFront(page, "tela", []);
    await abrirFront(page, "/login");
    const campo = (rotulo: string) => page.getByLabel(rotulo, { exact: true });
    const codigo = page.getByLabel("Código de 6 dígitos do aplicativo autenticador");

    await legenda(page, "1. O vendedor A digita só e-mail e senha");
    await campo("E-mail").pressSequentially(USUARIOS.A, { delay: 40 });
    await campo("Senha").pressSequentially(SENHA, { delay: 40 });
    const login = page.waitForResponse((r) => r.url().includes("/auth/login") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Entrar", exact: true }).click();
    expect(await (await login).text(), "a senha sozinha devolveu o token de acesso").not.toMatch(/"access"/);
    await expect(page.getByRole("heading", { name: "Digite o código" })).toBeVisible();
    cena.recusadas++;
    await legenda(page, "2. A senha certa NÃO abre o painel: o servidor pede o código do autenticador");
    await page.waitForTimeout(3000);

    await legenda(page, "3. Um código errado (000000) é recusado pelo servidor");
    await codigo.pressSequentially("000000", { delay: 120 });
    await expect(page.getByRole("alert")).toHaveText("Código inválido ou vencido.");
    cena.recusadas++;
    await page.waitForTimeout(3000);

    await legenda(page, "4. O código certo do autenticador (muda a cada 30 s) libera o painel");
    const passo = await proximoPasso(USUARIOS.A);
    await codigo.pressSequentially(codigoDoPasso(SEGREDO_TOTP, passo), { delay: 120 });
    await expect(page.getByRole("button", { name: "Menu do usuário" })).toBeVisible();
    marcarPassoUsado(USUARIOS.A, passo);
    cena.legitimas++;
    await page.waitForTimeout(3500);

    await legenda(page, "5. Ao sair, a sessão é apagada do navegador");
    await page.getByRole("button", { name: "Menu do usuário" }).click();
    await page.getByRole("button", { name: "Sair" }).click();
    await expect(page).toHaveURL(/\/login$/);
    expect(await page.evaluate(() => localStorage.getItem("cdv.session"))).toBeNull();
    await page.waitForTimeout(2500);
    await cena.encerrar("02-2fa-tela.webm", "Só senha não entra; só o código do autenticador libera o painel.");
  });

  test("03 2FA atacado na API", async ({ page }) => {
    precisaLogin();
    const cena = new Cena(page);
    const A = USUARIOS.A;
    await cena.cartao("O 2FA atacado direto na API", "Sem o front: o atacante tem a senha do vendedor A e tenta entrar pela API de todos os jeitos.");
    await cena.painel("2FA atacado direto na API");

    await cena.nota("1. Senha certa, sem o código: o servidor devolve só um token temporário (mfa_token), sem acesso.");
    const corpo = await dados(await cena.api.loginSenha(A));
    expect(corpo, "o login só com senha entregou o token de acesso").not.toHaveProperty("access");
    cena.recusadas++;
    await cena.ataque("GET", "/auth/me", { token: corpo.mfa_token, quem: "mfa_token" });

    await cena.nota("2. Código errado e códigos em formato inválido.");
    for (const code of ["000000", "abc123", "1234567"]) {
      await cena.ataque("POST", "/auth/2fa/verify", { json: { mfa_token: corpo.mfa_token, code }, quem: `código ${code}` });
    }

    await cena.nota("3. O dono, com o código certo do aplicativo, entra (azul = aceito).");
    const mfa = await cena.preparo.novoMfaToken(A);
    const passo = await proximoPasso(A);
    const codigo = codigoDoPasso(SEGREDO_TOTP, passo);
    const entrou = await cena.legitimo("POST", "/auth/2fa/verify", { json: { mfa_token: mfa, code: codigo }, quem: "A (dono)" });
    marcarPassoUsado(A, passo);
    const acesso = (await dados(entrou)).access;

    await cena.nota("4. Reaproveitar o mesmo mfa_token, o mesmo código e um mfa_token forjado.");
    await cena.ataque("POST", "/auth/2fa/verify", { json: { mfa_token: mfa, code: codigo }, quem: "token usado" });
    await cena.ataque("POST", "/auth/2fa/verify", { json: { mfa_token: await cena.preparo.novoMfaToken(A), code: codigo }, quem: "código usado" });
    await cena.ataque("POST", "/auth/2fa/verify", { json: { mfa_token: "eyJ1IjoxLCJsIjoiIn0:1:assinatura-falsa", code: codigo }, quem: "token forjado" });

    await cena.nota("5. Código vencido (gerado 1 minuto atrás) e código \"do futuro\" (1 minuto à frente).");
    const agora = passoAtual();
    await cena.ataque("POST", "/auth/2fa/verify", { json: { mfa_token: await cena.preparo.novoMfaToken(A), code: codigoDoPasso(SEGREDO_TOTP, agora - 2) }, quem: "vencido" });
    await cena.ataque("POST", "/auth/2fa/verify", { json: { mfa_token: await cena.preparo.novoMfaToken(A), code: codigoDoPasso(SEGREDO_TOTP, agora + 2) }, quem: "do futuro" });

    await cena.nota("6. Corrida: o mesmo código certo enviado duas vezes AO MESMO TEMPO. Só uma pode entrar.");
    const [m1, m2] = [await cena.preparo.novoMfaToken(A), await cena.preparo.novoMfaToken(A)];
    const passoCorrida = await proximoPasso(A);
    const codigoCorrida = codigoDoPasso(SEGREDO_TOTP, passoCorrida);
    const corrida = await Promise.all([
      cena.api.post("/auth/2fa/verify", { json: { mfa_token: m1, code: codigoCorrida }, quem: "pedido 1" }),
      cena.api.post("/auth/2fa/verify", { json: { mfa_token: m2, code: codigoCorrida }, quem: "pedido 2" }),
    ]);
    marcarPassoUsado(A, passoCorrida);
    expect(corrida.filter((r) => r.status() === 200), "as duas requisições entraram com o mesmo código").toHaveLength(1);
    cena.legitimas++;
    cena.recusadas++;
    await cena.nota("Uma entrou e a outra foi recusada: o servidor trava o código enquanto confere.");

    await cena.nota("7. Código de recuperação: vale uma vez só.");
    const passo2 = await proximoPasso(A);
    const gerados = await cena.preparo.post("/auth/2fa/recovery-codes", { token: acesso, json: { code: codigoDoPasso(SEGREDO_TOTP, passo2) } });
    marcarPassoUsado(A, passo2);
    const recuperacao: string = (await dados(gerados)).recovery_codes[0];
    await cena.legitimo("POST", "/auth/2fa/verify", { json: { mfa_token: await cena.preparo.novoMfaToken(A), recovery_code: recuperacao }, quem: "A (dono)" });
    await cena.ataque("POST", "/auth/2fa/verify", { json: { mfa_token: await cena.preparo.novoMfaToken(A), recovery_code: recuperacao }, quem: "repetido" });

    await cena.nota("8. Com a senha, tentar cadastrar o próprio celular no lugar do autenticador do A.");
    await cena.ataque("POST", "/auth/2fa/setup", { json: { mfa_token: await cena.preparo.novoMfaToken(A) }, quem: "atacante" });
    await page.waitForTimeout(2500);
    await cena.encerrar("03-2fa-api.webm", "Sem o código do autenticador não sai token de acesso, e nenhum código ou token vale duas vezes.");
  });

  test("04 IDOR pela tela", async ({ page }) => {
    precisaLogin();
    const sA = sessaoObrigatoria("A");
    const sB = sessaoObrigatoria("B");
    const cena = new Cena(page);
    const b = await recursosDe(cena.preparo, sB, "B");
    const url = `/cargas/VG-${b.viagem}`;
    const daViagem = () => page.waitForResponse((r) => new RegExp(`/shipments/${b.viagem}/?$`).test(new URL(r.url()).pathname), { timeout: 120_000 });
    await cena.cartao("IDOR pela tela", "O vendedor B abre a própria viagem e copia a URL. O vendedor A, logado com a conta dele, cola a mesma URL.");
    mostrarApiNoFront(page, "tela", []);

    await abrirFront(page, "/login");
    await sessaoNoNavegador(page, sB);
    let resposta = daViagem();
    await abrirFront(page, url);
    expect((await resposta).status()).toBe(200);
    cena.legitimas++;
    await legenda(page, `Vendedor B abre a própria viagem (${url}): a API responde 200`);
    await page.waitForTimeout(4500);

    await sessaoNoNavegador(page, sA);
    resposta = daViagem();
    await abrirFront(page, url);
    const status = (await resposta).status();
    expect(status, "a API entregou a viagem do B para o A").toBe(404);
    await expect(page.getByText("Viagem não encontrada")).toBeVisible();
    cena.recusadas++;
    await legenda(page, `Vendedor A cola a mesma URL: a API responde ${status} e nada do B aparece`);
    await page.waitForTimeout(4500);

    await abrirFront(page, "/cargas");
    await expect(page.getByText("TESTE-IDOR-B")).toHaveCount(0);
    cena.recusadas++;
    await legenda(page, "Na lista de cargas do A também não aparece nada do B");
    await page.waitForTimeout(3500);
    await cena.encerrar("04-idor-tela.webm", "Trocar o ID na URL não mostra os dados de outra pessoa: a resposta é a mesma de uma viagem que não existe.");
  });

  test("05 IDOR na API", async ({ page }) => {
    precisaLogin();
    const sA = sessaoObrigatoria("A");
    const sB = sessaoObrigatoria("B");
    const cena = new Cena(page);
    const b = await recursosDe(cena.preparo, sB, "B");
    const a = await recursosDe(cena.preparo, sA, "A");
    const tokenA = sA.access;
    await cena.cartao("IDOR direto na API", `O vendedor A, logado com a conta dele, troca os IDs para mexer na viagem ${b.viagem}, na placa ${b.placa} e nos cadastros do vendedor B.`);
    await cena.painel("IDOR: o vendedor A contra os dados do B");

    await cena.nota("1. Ler o que é do B, trocando o ID na URL.");
    for (const rota of [`/shipments/${b.viagem}`, `/shipments/${b.viagem}/summary`, `/shipments/${b.viagem}/readings`, `/devices/${b.placa}`, `/vehicles/${b.veiculo}`, `/locations/${b.fazenda}`]) {
      await cena.ataque("GET", rota, { token: tokenA });
    }
    await cena.nota("2. Alterar e comandar a viagem e os cadastros do B.");
    await cena.ataque("PATCH", `/locations/${b.fazenda}`, { token: tokenA, json: { name: "invadida" } });
    await cena.ataque("PATCH", `/devices/${b.placa}`, { token: tokenA, json: { name: "invadida" } });
    await cena.ataque("PATCH", `/shipments/${b.viagem}`, { token: tokenA, json: {} });
    for (const acao of ["start", "finish", "confirm"]) {
      await cena.ataque("POST", `/shipments/${b.viagem}/${acao}`, { token: tokenA, form: { condition: "good" } });
    }
    await cena.nota("3. Contorno: o ID do B no corpo, dentro da viagem do próprio A.");
    await cena.ataque("PATCH", `/shipments/${a.viagem}`, { token: tokenA, json: { device: b.placa } });
    await cena.ataque("PATCH", `/shipments/${a.viagem}`, { token: tokenA, json: { vehicle: b.veiculo } });

    await cena.nota("4. Enumeração: a viagem do B e uma que não existe recebem exatamente a mesma resposta.");
    const alheia = await cena.ataque("GET", `/shipments/${b.viagem}`, { token: tokenA });
    const inexistente = await cena.ataque("GET", "/shipments/999999999", { token: tokenA });
    expect(await alheia.text()).toBe(await inexistente.text());

    await cena.nota("5. O dono (B) continua usando a própria viagem normalmente.");
    await cena.legitimo("GET", `/shipments/${b.viagem}`, { token: sB.access });
    await cena.legitimo("GET", `/devices/${b.placa}`, { token: sB.access });

    const sC = sessaoOpcional("C");
    if (sC) {
      await cena.nota("6. Um usuário novo (C), sem nada cadastrado, tenta abrir o que é do A e do B.");
      for (const rota of [`/shipments/${a.viagem}`, `/shipments/${b.viagem}`, `/devices/${a.placa}`, `/devices/${b.placa}`]) {
        await cena.ataque("GET", rota, { token: sC.access });
      }
    }
    await page.waitForTimeout(2500);
    await cena.encerrar("05-idor-api.webm", "Quem não é dono recebe 404 (ID na URL) ou 403 (ID no corpo), e o 404 não revela se o ID existe.");
  });

  test("06 token, logout e papeis", async ({ page }) => {
    const cena = new Cena(page);
    await cena.cartao("Token, logout e papéis", "Quem é o usuário vem só do token assinado pelo servidor. Aqui tentamos entrar sem token, com token forjado e subir de papel.");
    await cena.painel("Token forjado, logout e papéis");

    await cena.nota("1. Sem token nenhum, cada rota de dados da API.");
    for (const rota of ROTAS) await cena.ataque("GET", rota, {}, [401]);
    await cena.nota("2. Tokens inventados, inclusive um JWT sem assinatura (alg: none) se passando pelo usuário 1.");
    const semAssinatura = `${b64url({ alg: "none", typ: "JWT" })}.${b64url({ token_type: "access", user_id: 1, exp: 4102444800 })}.`;
    for (const token of ["abc", "eyJhbGciOiJIUzI1NiJ9.e30.assinatura-falsa", semAssinatura]) {
      await cena.ataque("GET", "/auth/me", { token }, [401]);
    }

    const sA = sessaoOpcional("A");
    const sB = sessaoOpcional("B");
    if (TEM_CREDENCIAIS && sA && sB) {
      await cena.nota("3. O token do A com o user_id trocado para o do B (sem a chave do servidor) e o refresh usado como acesso.");
      const [cab, , assinatura] = sA.access.split(".");
      const forjado = `${cab}.${b64url({ ...lerParte(sA.access, 1), user_id: sB.user.id })}.${assinatura}`;
      await cena.ataque("GET", "/auth/me", { token: forjado, quem: "A → B" }, [401]);
      await cena.ataque("GET", "/auth/me", { token: sA.refresh }, [401]);

      await cena.nota("4. Logout: depois de sair, o refresh token deixa de valer. E o A não consegue derrubar a sessão do B.");
      const nova = await cena.preparo.entrar(USUARIOS.A);
      await cena.legitimo("POST", "/auth/logout", { token: nova.access, json: { refresh: nova.refresh }, quem: "A (sair)" });
      await cena.ataque("POST", "/auth/refresh", { json: { refresh: nova.refresh }, quem: "refresh velho" }, [401]);
      await cena.ataque("POST", "/auth/logout", { token: sA.access, json: { refresh: sB.refresh } }, [400]);

      await cena.nota("5. Papéis: o vendedor A tenta fazer o que só a plataforma pode.");
      await cena.ataque("GET", `/auth/users/${sB.user.id}`, { token: sA.access });
      await cena.ataque("POST", `/auth/users/${sB.user.id}/reset-2fa`, { token: sA.access });
      await cena.ataque("PATCH", `/auth/users/${sA.user.id}`, { token: sA.access, json: { role: "admin" } });
      await cena.ataque("POST", "/auth/users", { token: sA.access, json: { name: "Invasor", email: `invasor-${Date.now()}@teste.local`, role: "admin" } });
    }
    await page.waitForTimeout(2500);
    await cena.encerrar("06-token-papeis.webm", "Sem token válido, assinado pelo servidor, a API não responde; e vendedor não vira plataforma.");
  });

  test("07 placa ESP32", async ({ page }) => {
    const cena = new Cena(page);
    await cena.cartao("A placa ESP32", "As rotas da placa só aceitam a chave da própria placa, no cabeçalho X-Device-Key. Uma placa falsa tenta mandar leituras.");
    await cena.painel("Placa: só entra com a chave da placa");
    const lote = { readings: [{ sequence: 1, recorded_at: new Date().toISOString(), temperature_c: 99, humidity_pct: 1 }], impacts: [] };
    const rotas: [string, string, unknown?][] = [["GET", "/iot/config"], ["POST", "/iot/heartbeat", { network: "wifi" }], ["POST", "/iot/telemetry/batch", lote]];

    await cena.nota("1. Sem o cabeçalho X-Device-Key.");
    for (const [m, r, json] of rotas) await cena.ataque(m, r, { json, quem: "sem chave" }, [401]);
    await cena.nota("2. Com chaves falsas, inclusive uma tentativa de injeção de SQL.");
    for (const chave of ["chave-falsa", "' OR '1'='1"]) {
      for (const [m, r, json] of rotas) await cena.ataque(m, r, { json, headers: { "X-Device-Key": chave }, quem: "chave falsa" }, [401]);
    }
    const sA = sessaoOpcional("A");
    if (sA) {
      await cena.nota("3. Com o login de uma pessoa (o vendedor A) no lugar da chave da placa.");
      for (const [m, r, json] of rotas) await cena.ataque(m, r, { json, token: sA.access }, [401, 403]);
    }
    await page.waitForTimeout(2500);
    await cena.encerrar("07-placa.webm", "Nenhuma leitura falsa entrou: sem a chave da placa, 401.");
  });

  test("08 cabecalhos e CORS", async ({ page }) => {
    const cena = new Cena(page);
    await cena.cartao("Cabeçalhos e CORS da API", "Proteções do navegador: a API não pode ser aberta dentro de outro site, e um site qualquer não lê as respostas dela.");
    await cena.painel("Cabeçalhos de segurança e CORS");
    const h = (await cena.api.get("/auth/me")).headers();
    await cena.nota(`X-Frame-Options: ${h["x-frame-options"] ?? "ausente"} · X-Content-Type-Options: ${h["x-content-type-options"] ?? "ausente"} · HSTS: ${h["strict-transport-security"] ? "ativo" : "ausente"}`);
    expect(h["x-frame-options"]).toBe("DENY");
    expect(h["x-content-type-options"]).toBe("nosniff");
    cena.recusadas += 2;

    await cena.nota("Um site malicioso (site-malicioso.example) tenta usar a API pelo navegador da vítima.");
    const origem = "https://site-malicioso.example";
    const pre = await cena.api.chamar("OPTIONS", "/auth/login", { headers: { Origin: origem, "Access-Control-Request-Method": "POST" }, quem: "site falso" });
    const permitido = pre.headers()["access-control-allow-origin"];
    expect(permitido === origem || permitido === "*").toBe(false);
    cena.recusadas++;
    await cena.nota(`Resposta: ${permitido ? `Access-Control-Allow-Origin: ${permitido}` : "sem Access-Control-Allow-Origin"}. O navegador bloqueia o site falso.`);

    await cena.nota("Uma rota que não existe: a página de erro não mostra código nem configuração do servidor.");
    const erro = await cena.ataque("GET", `${new URL(API_URL).origin}/rota-que-nao-existe`, { quem: "curioso" }, [404]);
    expect(await erro.text()).not.toMatch(/Traceback|DEBUG = True|SECRET_KEY/);
    await page.waitForTimeout(3000);
    await cena.encerrar("08-cabecalhos-cors.webm", "A API manda os cabeçalhos de proteção, recusa origens desconhecidas e não vaza detalhes nos erros.");
  });

  test("09 forca bruta", async ({ page }) => {
    const cena = new Cena(page);
    await cena.cartao("Força bruta", "O atacante tenta adivinhar a senha (e o código de 6 dígitos) na base da repetição. O servidor aceita no máximo 10 tentativas por minuto.");
    await cena.painel("Força bruta: limite de tentativas");

    if (TEM_CREDENCIAIS) {
      await cena.nota("1. Chutando o código de 6 dígitos, um atrás do outro.");
      const mfa = await cena.preparo.novoMfaToken(USUARIOS.A);
      let barrado = 0;
      for (let i = 1; i <= 15 && !barrado; i++) {
        const r = await cena.ataque("POST", "/auth/2fa/verify", { json: { mfa_token: mfa, code: String(100000 + i) }, esperarLimite: false, quem: `chute ${i}` }, [400, 429]);
        if (r.status() === 429) barrado = i;
      }
      expect(barrado, "nenhum chute de código foi barrado").toBeGreaterThan(0);
      await cena.nota(`Barrado com 429 no chute ${barrado}. Com 1 milhão de códigos, 10 por minuto e um código novo a cada 30 s, chutar não compensa.`);
    }

    await cena.nota(`${TEM_CREDENCIAIS ? "2" : "1"}. Chutando a senha do vendedor A, uma atrás da outra.`);
    let barrado = 0;
    for (let i = 1; i <= 15 && !barrado; i++) {
      const r = await cena.ataque("POST", "/auth/login", { json: { email: USUARIOS.A, password: `senha-errada-${i}` }, esperarLimite: false, quem: `chute ${i}` }, [400, 429]);
      if (r.status() === 429) barrado = i;
    }
    expect(barrado, "nenhuma tentativa de senha foi barrada").toBeGreaterThan(0);
    await cena.nota(`Barrado com 429 na tentativa ${barrado}: o servidor manda esperar antes de aceitar novas tentativas.`);
    await page.waitForTimeout(3000);
    await cena.encerrar("09-forca-bruta.webm", "Depois de 10 tentativas no mesmo minuto, o servidor para de responder às tentativas (429).");
  });
});
