import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "@playwright/test";
import type { Sessao } from "./api";
import { AVISO_CREDENCIAIS, FRONT_URL, PASTA_AUTH, type Letra } from "./config";

/*
 * O setup (tests/00-login.setup.ts) entra uma vez com cada usuario de teste e guarda aqui os
 * tokens. Assim os testes nao gastam um codigo TOTP (e o limite de 10 logins por minuto) cada um.
 */
const arquivo = join(PASTA_AUTH, "sessoes.json");

export function salvarSessoes(sessoes: Partial<Record<Letra, Sessao>>) {
  mkdirSync(PASTA_AUTH, { recursive: true });
  writeFileSync(arquivo, JSON.stringify(sessoes, null, 2));
}

function lerSessoes(): Partial<Record<Letra, Sessao>> {
  try {
    return existsSync(arquivo) ? JSON.parse(readFileSync(arquivo, "utf8")) : {};
  } catch {
    return {};
  }
}

/** Nome curto do dono de um token, para o painel e o log: "A", "B (refresh)", "token forjado"... */
export function quemEh(token: string): string {
  for (const [letra, s] of Object.entries(lerSessoes())) {
    if (s?.access === token) return letra;
    if (s?.refresh === token) return `${letra} (refresh)`;
  }
  return token.split(".").length === 3 ? "token forjado" : "token inválido";
}

/** Sessao do usuario, ou undefined se o setup nao conseguiu entrar (sem pular o teste). */
export function sessaoOpcional(letra: Letra): Sessao | undefined {
  return lerSessoes()[letra];
}

/** Sessao do usuario A, B ou C. Sem ela, o teste e pulado com o motivo. */
export function sessao(letra: Letra): Sessao {
  const encontrada = lerSessoes()[letra];
  if (!encontrada) {
    const motivo = letra === "C"
      ? "Usuario C nao existe. Rode: python manage.py preparar_teste_seguranca --terceiro"
      : `Sem sessao do usuario ${letra}. ${AVISO_CREDENCIAIS}`;
    test.skip(true, motivo);
  }
  return encontrada!;
}

/**
 * Arquivo de "storage state" do Playwright que abre o front ja logado como o usuario: a mesma
 * chave "cdv.session" que o front grava no localStorage depois do codigo do autenticador.
 */
export function estadoDoFront(letra: Letra): string {
  const s = sessao(letra);
  const caminho = join(PASTA_AUTH, `front-${letra}.json`);
  const estado = {
    cookies: [],
    origins: [{
      origin: FRONT_URL,
      localStorage: [
        { name: "cdv.session", value: JSON.stringify({ ...s, twoFactor: true }) },
        { name: "cdv.assistant.seen", value: "1" },
      ],
    }],
  };
  writeFileSync(caminho, JSON.stringify(estado));
  return caminho;
}
