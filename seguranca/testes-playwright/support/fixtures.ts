import { test as base, expect } from "@playwright/test";
import { Api, dados } from "./api";
import { API_URL } from "./config";
import { abrirPainel, linhaNoPainel, notaNoPainel } from "./painel";

type Fixtures = {
  /** Cliente da API. Cada chamada aparece no painel, como passo no --ui e no console. */
  api: Api;
  /** Escreve uma frase explicativa no painel da API (e vira um passo no --ui). */
  nota: (texto: string) => Promise<void>;
};

/**
 * "test" com as fixtures da suite. A fixture "api" abre uma pagina de painel (no mesmo contexto
 * do teste) onde cada requisicao ao back aparece com o status; assim os testes so de API tambem
 * tem tela no --ui e no video. No fim, anexa ao relatorio a lista de requisicoes (evidencia).
 */
export const test = base.extend<Fixtures>({
  api: async ({ request, context }, use, testInfo) => {
    const painel = await context.newPage();
    const caminho = testInfo.titlePath.slice(1, -1).join(" > ");
    await abrirPainel(painel, testInfo.title, `${caminho}  ·  ${API_URL}`);
    const api = new Api(request, (linha) => linhaNoPainel(painel, linha));
    api.painel = painel;
    await use(api);
    if (api.registro.length) {
      await testInfo.attach("requisicoes", { body: api.registro.join("\n"), contentType: "text/plain" });
    }
  },
  nota: async ({ api }, use) => {
    await use(async (texto) => {
      console.log(`[nota] ${texto}`);
      await base.step(texto, () => notaNoPainel(api.painel!, texto));
    });
  },
});

export { expect, dados };

/** Recusado = 403 (proibido) ou 404 (nao encontrado). 2xx seria VULNERAVEL. */
export const RECUSADO = [403, 404];
