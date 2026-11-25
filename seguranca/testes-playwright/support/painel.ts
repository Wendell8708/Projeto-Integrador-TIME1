import type { Page } from "@playwright/test";

/**
 * Parte visual dos testes, para o modo --ui e para o video da apresentacao.
 *
 * - Painel da API: uma pagina que mostra cada requisicao feita ao back (quem chamou, rota,
 *   status). Os testes so de API nao tem tela; com o painel, o --ui e o video mostram o ataque.
 * - Legenda e mini-log no front: nos testes de tela, uma faixa no topo diz o que o teste esta
 *   fazendo e um quadro no canto mostra as respostas da API, junto com a tela do front.
 *
 * APRESENTACAO=1 (npm run ui / npm run apresentacao) deixa tudo mais lento para dar tempo de ler.
 */
export const APRESENTACAO = process.env.APRESENTACAO === "1";
const PAUSA_MS = APRESENTACAO ? 450 : 0;

export type LinhaApi = { quem: string; metodo: string; rota: string; status: number };

export function rotuloStatus(status: number) {
  if (status >= 200 && status < 300) return { texto: "aceito", classe: "ok" };
  if (status === 429) return { texto: "limite", classe: "limite" };
  if (status >= 500) return { texto: "erro", classe: "erro" };
  return { texto: "recusado", classe: "recusado" };
}

export function textoDaLinha(l: LinhaApi) {
  return `${l.quem.padEnd(8)} ${l.metodo.padEnd(6)} ${l.rota}  ->  ${l.status} ${rotuloStatus(l.status).texto}`;
}

const ESTILO = `
  :root { color-scheme: dark; }
  body { margin: 0; background: #0f1a14; color: #e7f3ea; font: 15px/1.45 Consolas, "Cascadia Mono", monospace; }
  header { padding: 18px 24px; background: #16643a; display: flex; flex-direction: column; gap: 4px; }
  header b { font: 600 20px "Segoe UI", system-ui, sans-serif; }
  header span { font: 15px "Segoe UI", system-ui, sans-serif; opacity: .9; }
  main { padding: 12px 24px; }
  .linha { display: grid; grid-template-columns: 150px 70px 1fr 150px; gap: 12px; padding: 7px 10px; border-bottom: 1px solid #22382b; animation: entra .25s ease-out; }
  .quem { color: #9fd3b0; } .metodo { color: #f0c674; }
  .st { text-align: right; font-weight: 700; }
  .ok .st { color: #7ab8ff; } .recusado .st { color: #5fd38a; } .limite .st { color: #f0c674; } .erro .st { color: #ff7a7a; }
  .nota { padding: 10px; margin: 8px 0; border-left: 4px solid #5fd38a; background: #16261c; font-family: "Segoe UI", system-ui, sans-serif; }
  @keyframes entra { from { opacity: 0; transform: translateY(-4px); } }
`;

/** Abre o painel da API numa pagina em branco. */
export async function abrirPainel(page: Page, titulo: string, subtitulo: string) {
  await page.setContent(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>API - ${titulo}</title>
    <style>${ESTILO}</style></head><body><header><b></b><span></span></header><main id="linhas"></main></body></html>`);
  await page.evaluate(([t, s]) => {
    document.querySelector("header b")!.textContent = t;
    document.querySelector("header span")!.textContent = s;
  }, [titulo, subtitulo]);
}

/** Acrescenta uma requisicao ao painel. */
export async function linhaNoPainel(page: Page, l: LinhaApi) {
  const { texto, classe } = rotuloStatus(l.status);
  await page.evaluate(({ l, texto, classe }) => {
    const div = document.createElement("div");
    div.className = `linha ${classe}`;
    for (const [cls, valor] of [["quem", l.quem], ["metodo", l.metodo], ["rota", l.rota], ["st", `${l.status} ${texto}`]]) {
      const span = document.createElement("span");
      span.className = cls;
      span.textContent = valor;
      div.append(span);
    }
    document.getElementById("linhas")!.append(div);
    div.scrollIntoView({ block: "end" });
  }, { l, texto, classe });
  if (PAUSA_MS) await page.waitForTimeout(PAUSA_MS);
}

/** Uma frase explicando o que vem a seguir (aparece no painel). */
export async function notaNoPainel(page: Page, texto: string) {
  await page.evaluate((t) => {
    const div = document.createElement("div");
    div.className = "nota";
    div.textContent = t;
    document.getElementById("linhas")!.append(div);
    div.scrollIntoView({ block: "end" });
  }, texto);
  if (PAUSA_MS) await page.waitForTimeout(PAUSA_MS * 2);
}

/*
 * ----- Front: legenda no topo e mini-log da API no canto -----
 * Os elementos tem pointer-events: none, entao nao atrapalham os cliques do teste. Sao criados de
 * novo se a pagina navegar (cada navegacao apaga o DOM).
 */
const CRIAR_SOBREPOSICAO = () => {
  if (document.getElementById("pw-legenda")) return;
  const css = document.createElement("style");
  css.textContent = `
    #pw-legenda { position: fixed; top: 12px; left: 50%; transform: translateX(-50%); z-index: 2147483647; pointer-events: none;
      max-width: 80vw; padding: 10px 18px; border-radius: 10px; background: rgba(15,26,20,.92); color: #fff;
      font: 600 16px "Segoe UI", system-ui, sans-serif; box-shadow: 0 6px 24px rgba(0,0,0,.25); }
    #pw-legenda:empty { display: none; }
    #pw-api { position: fixed; right: 12px; bottom: 12px; width: 470px; z-index: 2147483647; pointer-events: none;
      border-radius: 10px; overflow: hidden; background: rgba(15,26,20,.94); color: #e7f3ea;
      font: 12.5px/1.5 Consolas, "Cascadia Mono", monospace; box-shadow: 0 6px 24px rgba(0,0,0,.3); }
    #pw-api b { display: block; padding: 6px 10px; background: #16643a; font: 600 12.5px "Segoe UI", system-ui, sans-serif; }
    #pw-api div { padding: 3px 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    #pw-api .ok { color: #7ab8ff; } #pw-api .recusado { color: #5fd38a; } #pw-api .limite { color: #f0c674; } #pw-api .erro { color: #ff7a7a; }`;
  const legenda = document.createElement("div");
  legenda.id = "pw-legenda";
  const api = document.createElement("div");
  api.id = "pw-api";
  api.innerHTML = "<b>Back-end (API) - respostas</b>";
  document.documentElement.append(css, legenda, api);
};

/** Mostra uma frase no topo da tela do front (e registra como passo no --ui). */
export async function legenda(page: Page, texto: string) {
  await page.evaluate(CRIAR_SOBREPOSICAO).catch(() => {});
  await page.evaluate((t) => { document.getElementById("pw-legenda")!.textContent = t; }, texto).catch(() => {});
  if (PAUSA_MS) await page.waitForTimeout(PAUSA_MS * 2);
}

/**
 * Liga a tela do front ao mini-log: cada resposta de /api/v1 que o front recebe aparece no canto
 * da tela, no console do --ui e na lista de evidencias do teste.
 */
export function mostrarApiNoFront(page: Page, quem: string, registro: string[]) {
  page.on("response", async (resposta) => {
    const url = new URL(resposta.url());
    if (!url.pathname.includes("/api/v1") || resposta.request().method() === "OPTIONS") return;
    const l: LinhaApi = {
      quem,
      metodo: resposta.request().method(),
      rota: url.pathname.replace(/^.*\/api\/v1/, "") + url.search,
      status: resposta.status(),
    };
    const texto = textoDaLinha(l);
    registro.push(`${String(l.status).padStart(4)}  ${l.metodo.padEnd(6)} ${l.rota}   (tela do ${quem})`);
    console.log(`[front ${quem}] ${texto}`);
    const { classe } = rotuloStatus(l.status);
    await page.evaluate(CRIAR_SOBREPOSICAO).catch(() => {});
    await page.evaluate(({ texto, classe }) => {
      const caixa = document.getElementById("pw-api");
      if (!caixa) return;
      const div = document.createElement("div");
      div.className = classe;
      div.textContent = texto;
      caixa.append(div);
      while (caixa.children.length > 9) caixa.children[1].remove();
    }, { texto: `${l.metodo} ${l.rota} -> ${l.status}`, classe }).catch(() => {});
  });
}
