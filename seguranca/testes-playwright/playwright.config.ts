import { defineConfig } from "@playwright/test";
import { FRONT_URL } from "./support/config";
import { APRESENTACAO } from "./support/painel";

/*
 * Testes de seguranca contra a API e o front DE VERDADE (sem backend simulado).
 * Por padrao: front na Vercel e API no Render. Para testar local, defina FRONT_URL e API_URL.
 *
 * Os testes rodam um de cada vez (workers: 1): o servidor limita logins e codigos a 10 por
 * minuto e recusa um codigo TOTP ja usado, entao testes em paralelo atrapalhariam uns aos outros.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: "relatorio", open: "never" }],
    ["./support/resumo.ts"],
  ],
  use: {
    baseURL: FRONT_URL,
    channel: process.env.PW_CHANNEL ?? "chrome",
    locale: "pt-BR",
    timezoneId: "America/Recife",
    viewport: { width: 1280, height: 720 },
    // O service worker do PWA esconderia as chamadas da API do Playwright.
    serviceWorkers: "block",
    // Evidencia de todo teste: trace (passo a passo com a tela, rede e console, o que o --ui
    // mostra), video de cada pagina (front e painel da API) e print no fim.
    trace: "on",
    video: { mode: "on", size: { width: 1280, height: 720 } },
    screenshot: "on",
    // npm run ui / npm run apresentacao: mais lento para o video dar para acompanhar.
    launchOptions: { slowMo: APRESENTACAO ? 250 : 0 },
    actionTimeout: 30_000,
    navigationTimeout: 90_000,
  },
  projects: [
    // 1) Entra uma vez com A, B e C (senha + codigo do autenticador) e guarda os tokens.
    { name: "setup", testMatch: /00-login\.setup\.ts/ },
    // 2) Ataques direto na API: 2FA, IDOR, sessao/token, papeis e chave da placa.
    { name: "api", testMatch: /[\\/]api[\\/].*\.spec\.ts$/, dependencies: ["setup"] },
    // 3) Os mesmos controles vistos pela tela do front, com prints como evidencia.
    { name: "tela", testMatch: /[\\/]tela[\\/].*\.spec\.ts$/, dependencies: ["setup"] },
    // 4) Por ultimo: estoura o limite de tentativas (o IP fica bloqueado por ~1 minuto).
    { name: "limite", testMatch: /limite\.spec\.ts/, dependencies: ["api", "tela"] },
    // Extra (fora do "npm test"): cabecalhos de seguranca do front e da API, CORS e iframe.
    { name: "extras", testMatch: /[\\/]extras[\\/].*\.spec\.ts$/ },
    // npm run video: grava um video continuo da automacao para a apresentacao.
    { name: "video", testMatch: /[\\/]video[\\/].*\.spec\.ts$/, dependencies: ["setup"] },
  ],
});
