// Roda a suite inteira, incluindo os testes lentos (TESTE_LENTO=1), como a validade de 5 min do
// mfa_token. Funciona igual no PowerShell, no cmd e no Linux.
//   node scripts/completo.mjs
import { spawn } from "node:child_process";

const args = ["playwright", "test", "--project=api", "--project=tela", "--project=limite", ...process.argv.slice(2)];
const filho = spawn("npx", args, { stdio: "inherit", shell: true, env: { ...process.env, TESTE_LENTO: "1" } });
filho.on("exit", (codigo) => process.exit(codigo ?? 1));
