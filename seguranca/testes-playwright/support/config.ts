import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

/**
 * Tudo vem de variaveis de ambiente (ou do arquivo .env desta pasta), nada de senha no codigo.
 * As mesmas variaveis dos scripts Python de seguranca/testes/ (comum.py).
 */
const arquivoEnv = fileURLToPath(new URL("../.env", import.meta.url));
if (existsSync(arquivoEnv)) process.loadEnvFile(arquivoEnv);

const semBarra = (url: string) => url.replace(/\/+$/, "");

export const FRONT_URL = semBarra(process.env.FRONT_URL || "https://caminh-do-vale-front.vercel.app");
export const API_URL = semBarra(process.env.API_URL || "https://projeto-integrador-time1.onrender.com/api/v1");
export const SENHA = process.env.TESTE_SENHA ?? "";
export const SEGREDO_TOTP = (process.env.TESTE_TOTP_SEGREDO ?? "").replace(/\s/g, "").toUpperCase();
export const MISSAO = process.env.MISSAO || "TIME1";

/**
 * Usuarios sinteticos criados por: python manage.py preparar_teste_seguranca [--terceiro].
 * Podem ser trocados por contas reais no .env (TESTE_USUARIO_A/B/C).
 */
export const USUARIOS = {
  A: process.env.TESTE_USUARIO_A || "vendedor-a@teste.local",
  B: process.env.TESTE_USUARIO_B || "vendedor-b@teste.local",
  C: process.env.TESTE_USUARIO_C || "vendedor-c@teste.local",
};

/**
 * TESTE_CODIGO_MANUAL=1: sem o segredo do autenticador, os capitulos de 2FA do video param e
 * esperam a pessoa digitar o codigo que esta no aplicativo do celular naquele momento.
 */
export const CODIGO_MANUAL = process.env.TESTE_CODIGO_MANUAL === "1" && Boolean(SENHA) && !SEGREDO_TOTP;
export type Letra = keyof typeof USUARIOS;

/** Pasta (fora do Git) onde o setup guarda as sessoes e o ultimo passo TOTP usado. */
export const PASTA_AUTH = fileURLToPath(new URL("../.auth/", import.meta.url));

export const TEM_CREDENCIAIS = Boolean(SENHA && SEGREDO_TOTP);
export const AVISO_CREDENCIAIS =
  "Defina TESTE_SENHA e TESTE_TOTP_SEGREDO no .env (os mesmos do preparar_teste_seguranca).";
