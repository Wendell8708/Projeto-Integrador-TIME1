import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { FullResult, Reporter, TestCase, TestResult } from "@playwright/test/reporter";
import { API_URL, FRONT_URL, MISSAO } from "./config";

/**
 * Resumo no mesmo formato das evidencias de seguranca/evidencias/: cabecalho com o codigo de
 * missao, uma linha por teste (PROTEGIDO / VULNERAVEL / PULADO) e as requisicoes de cada um.
 * Grava em evidencias/<MISSAO>-playwright-<data>.txt (pasta fora do Git).
 */
// eslint-disable-next-line no-control-regex
const semCores = (texto: string) => texto.replace(/\u001b\[[0-9;]*m/g, "");

export default class ResumoReporter implements Reporter {
  private readonly linhas: string[] = [];
  private contagem = { protegido: 0, vulneravel: 0, erro: 0, pulado: 0 };
  private readonly inicio = new Date();

  onTestEnd(test: TestCase, result: TestResult) {
    const projeto = test.parent.project()?.name ?? "";
    if (projeto === "setup" && result.status === "passed") return;
    const titulo = test.titlePath().slice(3).filter(Boolean).join(" > ");
    let situacao: string;
    if (result.status === "passed") {
      situacao = "PROTEGIDO";
      this.contagem.protegido++;
    } else if (result.status === "skipped") {
      situacao = "PULADO";
      this.contagem.pulado++;
    } else {
      // Falha de uma checagem (expect) = o controle nao segurou. Outra excecao = o teste nem
      // conseguiu atacar (login falhou, servidor fora do ar...), entao e ERRO, nao VULNERAVEL.
      const mensagem = semCores(result.error?.message ?? "");
      situacao = /expect\(/.test(mensagem) ? "VULNERAVEL" : "ERRO";
      this.contagem[situacao === "ERRO" ? "erro" : "vulneravel"]++;
    }
    this.linhas.push(`${situacao.padEnd(11)} [${projeto}] ${titulo}`);
    for (const nota of test.annotations.filter((a) => a.type !== "skip")) {
      this.linhas.push(`            ${nota.type}: ${nota.description ?? ""}`);
    }
    const motivo = test.annotations.find((a) => a.type === "skip")?.description;
    if (situacao === "PULADO" && motivo) this.linhas.push(`            motivo: ${motivo}`);
    if ((situacao === "VULNERAVEL" || situacao === "ERRO") && result.error?.message) {
      const linhas = semCores(result.error.message).split("\n").filter((l) => l.trim()).slice(0, 4);
      this.linhas.push(...linhas.map((l) => `            ${l.trim()}`));
    }
    for (const anexo of result.attachments) {
      if (anexo.name === "requisicoes" && anexo.body) {
        this.linhas.push(...anexo.body.toString().split("\n").map((l) => `            ${l}`));
      }
    }
  }

  onEnd(result: FullResult) {
    if (!this.linhas.length) return; // --list ou nenhum teste rodou
    const data = this.inicio.toLocaleString("pt-BR", { timeZone: "America/Recife" });
    const { protegido, vulneravel, erro, pulado } = this.contagem;
    const texto = [
      "=".repeat(78),
      `[${MISSAO}] Testes de seguranca com Playwright (2FA, IDOR, sessao, placa)`,
      `Front: ${FRONT_URL}`,
      `API:   ${API_URL}`,
      `Data:  ${data}`,
      "=".repeat(78),
      ...this.linhas,
      "-".repeat(78),
      vulneravel
        ? `RESULTADO: VULNERAVEL - ${vulneravel} checagem(ns) falharam; ${protegido} protegido(s), ${erro} erro(s), ${pulado} pulado(s).`
        : erro
          ? `RESULTADO: INCOMPLETO - ${erro} teste(s) nao rodaram por erro; ${protegido} protegido(s), ${pulado} pulado(s).`
          : `RESULTADO: PROTEGIDO - ${protegido} teste(s) passaram; ${pulado} pulado(s). (${result.status})`,
    ].join("\n");

    const pasta = fileURLToPath(new URL("../evidencias/", import.meta.url));
    mkdirSync(pasta, { recursive: true });
    const carimbo = this.inicio.toISOString().slice(0, 16).replace(/[-:T]/g, "");
    const arquivo = `${pasta}${MISSAO}-playwright-${carimbo}.txt`;
    writeFileSync(arquivo, texto + "\n");
    console.log(`\n${texto}\n\nResumo salvo em ${arquivo}`);
  }

  printsToStdio() {
    return false;
  }
}
