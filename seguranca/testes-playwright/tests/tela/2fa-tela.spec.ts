import type { Page } from "@playwright/test";
import { AVISO_CREDENCIAIS, SEGREDO_TOTP, SENHA, TEM_CREDENCIAIS, USUARIOS } from "../../support/config";
import { expect, test } from "../../support/fixtures";
import { APRESENTACAO, legenda, mostrarApiNoFront } from "../../support/painel";
import { codigoDoPasso, marcarPassoUsado, proximoPasso } from "../../support/totp";

/*
 * O 2FA visto pela tela do front publicado, com o back de verdade. A faixa no topo diz o passo
 * e o quadro no canto mostra o que a API respondeu.
 */
const A = USUARIOS.A;
const campoCodigo = (page: Page) => page.getByLabel("Código de 6 dígitos do aplicativo autenticador");

async function digitar(page: Page, rotulo: string, texto: string) {
  const campo = page.getByLabel(rotulo, { exact: true });
  if (APRESENTACAO) await campo.pressSequentially(texto, { delay: 60 });
  else await campo.fill(texto);
}

async function abrirLogin(page: Page, registro: string[]) {
  mostrarApiNoFront(page, "A", registro);
  await page.goto("/login");
  // O Render gratuito pode levar ~1 min para acordar; a tela de login mostra o splash enquanto isso.
  await expect(page.getByRole("heading", { name: "Entrar no painel" })).toBeVisible({ timeout: 120_000 });
}

test.describe("2FA na tela do front", () => {
  test("senha sozinha não entra; código errado é recusado; código certo entra", async ({ page }, testInfo) => {
    test.skip(!TEM_CREDENCIAIS, AVISO_CREDENCIAIS);
    const registro: string[] = [];
    await abrirLogin(page, registro);

    await test.step("1. entra só com e-mail e senha", async () => {
      await legenda(page, "1. O vendedor A entra só com e-mail e senha");
      await digitar(page, "E-mail", A);
      await digitar(page, "Senha", SENHA);
      const login = page.waitForResponse((r) => r.url().includes("/auth/login") && r.request().method() === "POST");
      await page.getByRole("button", { name: "Entrar", exact: true }).click();
      const resposta = await login;
      expect(resposta.status()).toBe(200);
      expect(await resposta.text(), "a senha sozinha devolveu o token de acesso").not.toMatch(/"access"/);
    });

    await test.step("2. o painel não abre: pede o código do autenticador", async () => {
      await legenda(page, "2. A senha certa NÃO abre o painel: o sistema pede o código do autenticador");
      await expect(page.getByRole("heading", { name: "Digite o código" })).toBeVisible();
      const sessao = await page.evaluate(() => localStorage.getItem("cdv.session"));
      expect(sessao, "o front guardou uma sessão antes do código").toBeNull();
    });

    await test.step("3. código errado é recusado", async () => {
      await legenda(page, "3. Um código errado (000000) é recusado pelo servidor");
      const verificar = page.waitForResponse((r) => r.url().includes("/auth/2fa/verify"));
      await campoCodigo(page).fill("000000");
      expect((await verificar).status()).toBe(400);
      await expect(page.getByRole("alert")).toHaveText("Código inválido ou vencido.");
    });

    await test.step("4. código certo do autenticador entra", async () => {
      await legenda(page, "4. O código certo do autenticador (TOTP de 30 s) libera o acesso");
      const passo = await proximoPasso(A);
      const verificar = page.waitForResponse((r) => r.url().includes("/auth/2fa/verify"));
      await campoCodigo(page).fill(codigoDoPasso(SEGREDO_TOTP, passo));
      const resposta = await verificar;
      marcarPassoUsado(A, passo);
      expect(resposta.status()).toBe(200);
      await expect(page.getByRole("button", { name: "Menu do usuário" })).toBeVisible();
      const sessao = await page.evaluate(() => JSON.parse(localStorage.getItem("cdv.session") ?? "null"));
      expect(sessao).toMatchObject({ twoFactor: true, user: { email: A } });
      await testInfo.attach("painel depois do 2FA", { body: await page.screenshot(), contentType: "image/png" });
    });

    await test.step("5. sair encerra a sessão", async () => {
      await legenda(page, "5. Ao sair, a sessão é apagada do navegador");
      await page.getByRole("button", { name: "Menu do usuário" }).click();
      await page.getByRole("button", { name: "Sair" }).click();
      await expect(page).toHaveURL(/\/login$/);
      expect(await page.evaluate(() => localStorage.getItem("cdv.session"))).toBeNull();
      await legenda(page, "Resultado: só senha não entra; só o código do autenticador libera o painel");
    });

    await testInfo.attach("requisicoes", { body: registro.join("\n"), contentType: "text/plain" });
  });

  test("sem sessão, as telas internas voltam para o login", async ({ page }) => {
    const registro: string[] = [];
    mostrarApiNoFront(page, "anônimo", registro);
    for (const rota of ["/", "/cargas", "/cargas/VG-1", "/configuracoes", "/alertas"]) {
      await test.step(`abre ${rota} sem estar logado`, async () => {
        await page.goto(rota);
        await legenda(page, `Sem login, ${rota} volta para a tela de login`);
        await expect(page).toHaveURL(/\/login$/);
      });
    }
    // Nenhuma chamada de dados saiu sem login (a tela de login só "acorda" o servidor).
    expect(registro.filter((l) => /shipments|devices|alerts|readings/.test(l))).toEqual([]);
  });
});
