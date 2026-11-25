import type { Browser, Page, TestInfo } from "@playwright/test";
import { recursosDe } from "../../support/cenario";
import { expect, test } from "../../support/fixtures";
import { legenda, mostrarApiNoFront } from "../../support/painel";
import { estadoDoFront, sessao } from "../../support/sessoes";

/*
 * O IDOR visto pela tela, do jeito do guia ("cole a URL na janela do A"): o vendedor B abre a
 * propria viagem, copia a URL, e o vendedor A abre a mesma URL na janela dele. Duas janelas ao
 * mesmo tempo, cada uma gravada em video, com as respostas da API no canto da tela.
 */
async function janela(browser: Browser, letra: "A" | "B", testInfo: TestInfo, registro: string[]) {
  const contexto = await browser.newContext({
    storageState: estadoDoFront(letra),
    serviceWorkers: "block",
    viewport: { width: 1280, height: 720 },
    recordVideo: { dir: testInfo.outputPath(`video-${letra}`), size: { width: 1280, height: 720 } },
  });
  const page = await contexto.newPage();
  mostrarApiNoFront(page, letra, registro);
  return page;
}

async function anexarVideo(page: Page, nome: string, testInfo: TestInfo) {
  const video = page.video();
  await page.context().close();
  if (video) await testInfo.attach(nome, { path: await video.path(), contentType: "video/webm" });
}

const respostaDaViagem = (page: Page, id: number) =>
  page.waitForResponse((r) => new RegExp(`/shipments/${id}/?$`).test(new URL(r.url()).pathname), { timeout: 120_000 });

test.describe("IDOR na tela do front", () => {
  test("o A cola a URL da viagem do B e não vê nada", async ({ api, browser }, testInfo) => {
    const b = await recursosDe(api, sessao("B"), "B");
    const url = `/cargas/VG-${b.viagem}`;
    const registro: string[] = [];

    const telaB = await janela(browser, "B", testInfo, registro);
    await test.step(`B abre a própria viagem: ${url}`, async () => {
      const resposta = respostaDaViagem(telaB, b.viagem);
      await telaB.goto(url);
      expect((await resposta).status()).toBe(200);
      await legenda(telaB, `Vendedor B abre a própria viagem (${url}) e copia a URL`);
      await expect(telaB.getByText("Viagem não encontrada")).toHaveCount(0);
      await testInfo.attach("tela do B", { body: await telaB.screenshot(), contentType: "image/png" });
    });

    const telaA = await janela(browser, "A", testInfo, registro);
    await test.step(`A cola a mesma URL: ${url}`, async () => {
      const resposta = respostaDaViagem(telaA, b.viagem);
      await telaA.goto(url);
      const status = (await resposta).status();
      await legenda(telaA, `Vendedor A cola a URL da viagem do B: a API responde ${status}`);
      expect(status, "a API entregou a viagem do B para o A").toBe(404);
      await expect(telaA.getByText("Viagem não encontrada")).toBeVisible();
      await expect(telaA.getByText("TESTE-IDOR-B")).toHaveCount(0);
      await testInfo.attach("tela do A", { body: await telaA.screenshot(), contentType: "image/png" });
    });

    await test.step("A não vê a viagem do B na lista de cargas", async () => {
      await telaA.goto("/cargas");
      await legenda(telaA, "Na lista de cargas do A também não aparece nada do B");
      await expect(telaA.getByText("TESTE-IDOR-B")).toHaveCount(0);
    });

    await testInfo.attach("requisicoes", { body: registro.join("\n"), contentType: "text/plain" });
    await anexarVideo(telaB, "video da janela do B", testInfo);
    await anexarVideo(telaA, "video da janela do A", testInfo);
  });
});
