// Roda o Playwright no modo apresentacao (APRESENTACAO=1): passos mais lentos, legendas e painel
// com pausa para leitura. Funciona igual no PowerShell, no cmd e no Linux (sem cross-env).
//   node scripts/apresentar.mjs --ui
//   node scripts/apresentar.mjs --project=tela --headed
import { spawn } from "node:child_process";

const filho = spawn("npx", ["playwright", "test", ...process.argv.slice(2)], {
  stdio: "inherit",
  shell: true,
  env: { ...process.env, APRESENTACAO: "1" },
});
filho.on("exit", (codigo) => process.exit(codigo ?? 1));
