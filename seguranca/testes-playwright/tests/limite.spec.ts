import { AVISO_CREDENCIAIS, TEM_CREDENCIAIS, USUARIOS } from "../support/config";
import { expect, test } from "../support/fixtures";

/*
 * Forca bruta: o servidor aceita no maximo 10 tentativas de codigo e 10 de senha por minuto
 * (THROTTLE_MFA e THROTTLE_LOGIN). Roda por ultimo: depois dele, este IP fica ~1 minuto bloqueado.
 */
const MAXIMO = 15;

test.describe("Limite de tentativas (força bruta)", () => {
  test.describe.configure({ mode: "serial" });

  test("chutar o código de 6 dígitos: o servidor barra com 429", async ({ api, nota }) => {
    test.skip(!TEM_CREDENCIAIS, AVISO_CREDENCIAIS);
    const mfa = await api.novoMfaToken(USUARIOS.A);
    await nota(`Chutando códigos seguidos (até ${MAXIMO}). Esperado: 429 antes da 11ª tentativa.`);
    let barrado = 0;
    for (let i = 1; i <= MAXIMO; i++) {
      const chute = String(100000 + i).padStart(6, "0");
      const resposta = await api.post("/auth/2fa/verify", { json: { mfa_token: mfa, code: chute }, esperarLimite: false });
      if (resposta.status() === 429) {
        barrado = i;
        expect(Number(resposta.headers()["retry-after"]), "o 429 diz quanto tempo esperar").toBeGreaterThan(0);
        break;
      }
      expect(resposta.status()).toBe(400);
    }
    expect(barrado, "nenhum chute foi barrado").toBeGreaterThan(0);
    expect(barrado).toBeLessThanOrEqual(11);
    await nota(`Barrado na tentativa ${barrado}. Com 1 milhão de códigos e 10 por minuto, chutar não compensa.`);
  });

  test("chutar a senha: o servidor barra com 429", async ({ api, nota }) => {
    await nota(`Tentando senhas erradas seguidas (até ${MAXIMO}). Esperado: 429 antes da 11ª tentativa.`);
    let barrado = 0;
    for (let i = 1; i <= MAXIMO; i++) {
      const resposta = await api.post("/auth/login", {
        json: { email: USUARIOS.A, password: `senha-errada-${i}` },
        esperarLimite: false,
      });
      if (resposta.status() === 429) {
        barrado = i;
        break;
      }
      expect(resposta.status()).toBe(400);
    }
    expect(barrado, "nenhuma tentativa de senha foi barrada").toBeGreaterThan(0);
    expect(barrado).toBeLessThanOrEqual(11);
    await nota(`Barrado na tentativa ${barrado}. Este IP fica bloqueado por cerca de 1 minuto.`);
  });
});
