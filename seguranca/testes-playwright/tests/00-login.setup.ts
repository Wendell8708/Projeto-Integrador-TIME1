import { rmSync } from "node:fs";
import { join } from "node:path";
import type { Sessao } from "../support/api";
import { AVISO_CREDENCIAIS, PASTA_AUTH, TEM_CREDENCIAIS, USUARIOS, type Letra } from "../support/config";
import { test } from "../support/fixtures";
import { salvarSessoes } from "../support/sessoes";

/*
 * Entra com os usuarios de teste (senha + codigo do autenticador) e guarda os tokens para os
 * outros testes. Sem credenciais, os testes que precisam de login sao pulados; os que nao
 * precisam (rotas sem token, chave da placa) rodam assim mesmo.
 */
test("entra com os usuarios de teste A, B e C", async ({ api }) => {
  rmSync(join(PASTA_AUTH, "sessoes.json"), { force: true });
  test.skip(!TEM_CREDENCIAIS, AVISO_CREDENCIAIS);

  const sessoes: Partial<Record<Letra, Sessao>> = {};
  sessoes.A = await api.entrar(USUARIOS.A);
  sessoes.B = await api.entrar(USUARIOS.B);
  // O C so existe depois de "preparar_teste_seguranca --terceiro"; sem ele, os testes do C sao pulados.
  const loginC = await api.loginSenha(USUARIOS.C);
  if (loginC.ok()) sessoes.C = await api.entrar(USUARIOS.C);
  salvarSessoes(sessoes);
});
