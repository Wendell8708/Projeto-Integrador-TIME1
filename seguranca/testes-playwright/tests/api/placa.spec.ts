import { expect, test } from "../../support/fixtures";
import { sessao } from "../../support/sessoes";

/*
 * Rotas da placa ESP32 (/iot/*): so aceitam a chave da propria placa no cabecalho X-Device-Key.
 * Sem chave, com chave falsa ou com o token de uma pessoa, a placa falsa nao manda leitura.
 */
const LOTE = {
  readings: [{ sequence: 1, recorded_at: new Date().toISOString(), temperature_c: 99, humidity_pct: 1 }],
  impacts: [],
};

const ROTAS: [string, string, unknown?][] = [
  ["GET", "/iot/config"],
  ["POST", "/iot/heartbeat", { network: "wifi" }],
  ["POST", "/iot/telemetry/batch", LOTE],
];

test.describe("Placa: só entra com a chave da placa", () => {
  test("sem o cabeçalho X-Device-Key", async ({ api }) => {
    for (const [metodo, rota, json] of ROTAS) {
      const resposta = await api.chamar(metodo, rota, { json });
      expect(resposta.status(), `${metodo} ${rota}`).toBe(401);
    }
  });

  test("com uma chave falsa", async ({ api }) => {
    for (const chave of ["chave-falsa", "0".repeat(64), "' OR '1'='1"]) {
      for (const [metodo, rota, json] of ROTAS) {
        const resposta = await api.chamar(metodo, rota, { json, headers: { "X-Device-Key": chave } });
        expect(resposta.status(), `${metodo} ${rota} com chave "${chave}"`).toBe(401);
      }
    }
  });

  test("com o token de login de uma pessoa (vendedor)", async ({ api }) => {
    const token = sessao("A").access;
    for (const [metodo, rota, json] of ROTAS) {
      const resposta = await api.chamar(metodo, rota, { json, token });
      expect([401, 403], `${metodo} ${rota} com JWT de pessoa`).toContain(resposta.status());
    }
  });
});
