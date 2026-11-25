import { createHmac } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { PASTA_AUTH } from "./config";

/**
 * TOTP (RFC 6238) igual ao do Google Authenticator e ao do servidor (pyotp):
 * HMAC-SHA1(segredo, numero do intervalo de 30 s), reduzido a 6 digitos.
 */
export const PASSO_S = 30;

function base32(segredo: string): Buffer {
  const alfabeto = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const bytes: number[] = [];
  let bits = 0;
  let valor = 0;
  for (const letra of segredo.replace(/=+$/, "")) {
    const indice = alfabeto.indexOf(letra);
    if (indice < 0) throw new Error("TESTE_TOTP_SEGREDO nao e base32 valido.");
    valor = ((valor << 5) | indice) & 0xfff;
    bits += 5;
    if (bits >= 8) {
      bytes.push((valor >>> (bits - 8)) & 0xff);
      bits -= 8;
    }
  }
  return Buffer.from(bytes);
}

export const passoAtual = () => Math.floor(Date.now() / 1000 / PASSO_S);

export function codigoDoPasso(segredo: string, passo: number): string {
  const mensagem = Buffer.alloc(8);
  mensagem.writeBigUInt64BE(BigInt(passo));
  const hash = createHmac("sha1", base32(segredo)).update(mensagem).digest();
  const deslocamento = hash[hash.length - 1] & 0x0f;
  const numero = (hash.readUInt32BE(deslocamento) & 0x7fffffff) % 1_000_000;
  return String(numero).padStart(6, "0");
}

/*
 * O servidor recusa um codigo de intervalo igual ou anterior ao ultimo usado (ultimo_passo).
 * Guardamos, por usuario, o ultimo intervalo que estes testes usaram. Fica num arquivo porque
 * o setup e os testes rodam em processos diferentes.
 */
const arquivo = join(PASTA_AUTH, "totp.json");

function lerEstado(): Record<string, number> {
  try {
    return existsSync(arquivo) ? JSON.parse(readFileSync(arquivo, "utf8")) : {};
  } catch {
    return {};
  }
}

export function marcarPassoUsado(email: string, passo: number) {
  const estado = lerEstado();
  estado[email] = Math.max(estado[email] ?? 0, passo);
  mkdirSync(PASTA_AUTH, { recursive: true });
  writeFileSync(arquivo, JSON.stringify(estado, null, 2));
}

const dormir = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Proximo intervalo que este usuario ainda nao usou. A janela do servidor (OTP_VALID_WINDOW=1)
 * aceita o intervalo atual e o seguinte; se os dois ja foram usados, espera o proximo.
 */
export async function proximoPasso(email: string): Promise<number> {
  for (;;) {
    const atual = passoAtual();
    const passo = Math.max(atual, (lerEstado()[email] ?? 0) + 1);
    if (passo <= atual + 1) return passo;
    const espera = (PASSO_S - (Date.now() / 1000) % PASSO_S) * 1000 + 500;
    await dormir(espera);
  }
}

/** Espera o relogio chegar no intervalo informado (usado quando a janela do servidor e 0). */
export async function esperarPasso(passo: number) {
  while (passoAtual() < passo) await dormir(500);
}
