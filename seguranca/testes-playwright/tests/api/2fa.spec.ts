import { AVISO_CREDENCIAIS, SEGREDO_TOTP, TEM_CREDENCIAIS, USUARIOS } from "../../support/config";
import { dados, expect, test } from "../../support/fixtures";
import { codigoDoPasso, marcarPassoUsado, passoAtual, proximoPasso } from "../../support/totp";

/*
 * Controle 1: login em dois fatores (TOTP). Mesmos itens do teste_otp.py, mais tentativas de
 * contorno. Usa o usuario A. Os testes rodam em ordem: cada um aproveita o anterior.
 */
const A = USUARIOS.A;

test.skip(!TEM_CREDENCIAIS, AVISO_CREDENCIAIS);

let acesso = "";
let mfaUsado = "";
let codigoUsado = "";

test.describe("2FA na API", () => {
  test.describe.configure({ mode: "serial" });

  test("1. senha certa sem o código não entrega o token de acesso", async ({ api }) => {
    const resposta = await api.loginSenha(A);
    expect(resposta.status()).toBe(200);
    const corpo = await dados(resposta);
    expect(corpo, "o login só com a senha devolveu o token de acesso").not.toHaveProperty("access");
    expect(corpo).not.toHaveProperty("refresh");
    expect(corpo).toMatchObject({ mfa_required: true, mfa_setup_required: false });
    expect(typeof corpo.mfa_token).toBe("string");

    // O mfa_token não serve como token de acesso.
    const me = await api.get("/auth/me", { token: corpo.mfa_token });
    expect(me.status(), "o mfa_token abriu uma rota protegida").toBe(401);
  });

  test("2. código errado é recusado", async ({ api }) => {
    const mfa = await api.novoMfaToken(A);
    const resposta = await api.post("/auth/2fa/verify", { json: { mfa_token: mfa, code: "000000" } });
    expect(resposta.status()).toBe(400);
    expect(await resposta.text()).not.toContain("access");
  });

  test("3. código em formato inválido é recusado", async ({ api }) => {
    const mfa = await api.novoMfaToken(A);
    for (const code of ["abc123", "1234567", "12345", "", " 00 00 0"]) {
      const resposta = await api.post("/auth/2fa/verify", { json: { mfa_token: mfa, code } });
      expect(resposta.status(), `código "${code}"`).toBe(400);
    }
  });

  test("4. código válido do autenticador entra", async ({ api }) => {
    mfaUsado = await api.novoMfaToken(A);
    const { resposta, codigo } = await api.verificarComCodigo(A, mfaUsado);
    expect(resposta.status()).toBe(200);
    const tokens = await dados(resposta);
    expect(tokens).toHaveProperty("access");
    expect(tokens).toHaveProperty("refresh");
    acesso = tokens.access;
    codigoUsado = codigo;

    const me = await api.get("/auth/me", { token: acesso });
    expect(me.status()).toBe(200);
    expect((await dados(me)).email).toBe(A);
  });

  test("5. o mesmo mfa_token não vale depois que o login termina", async ({ api }) => {
    test.skip(!mfaUsado, "depende do teste 4");
    const resposta = await api.post("/auth/2fa/verify", { json: { mfa_token: mfaUsado, code: codigoUsado } });
    expect(resposta.status()).toBe(401);
  });

  test("6. o mesmo código não funciona duas vezes", async ({ api }) => {
    test.skip(!codigoUsado, "depende do teste 4");
    const mfa = await api.novoMfaToken(A);
    const resposta = await api.post("/auth/2fa/verify", { json: { mfa_token: mfa, code: codigoUsado } });
    expect(resposta.status()).toBe(400);
    // Dentro da janela de 30 s o servidor diz "já foi utilizado"; depois, "inválido ou vencido".
    // Nos dois casos o código foi recusado.
    await test.info().attach("mensagem do servidor", { body: await resposta.text(), contentType: "text/plain" });
  });

  test("7. mfa_token adulterado é recusado", async ({ api }) => {
    const mfa = await api.novoMfaToken(A);
    const [conteudo, , assinatura] = mfa.split(":");
    // Troca o ID do usuário dentro do token (sem a assinatura certa) e altera a assinatura.
    const forjados = [
      mfa.slice(0, -2) + (mfa.endsWith("AA") ? "BB" : "AA"),
      `${conteudo}:${Date.now().toString(36)}:${assinatura ?? "x"}`,
      "eyJ1IjoxLCJsIjoiIn0:1:assinatura-falsa",
    ];
    const passo = await proximoPasso(A);
    for (const token of forjados) {
      const resposta = await api.post("/auth/2fa/verify", { json: { mfa_token: token, code: codigoDoPasso(SEGREDO_TOTP, passo) } });
      expect(resposta.status(), `token forjado ${token.slice(0, 20)}...`).toBe(401);
    }
  });

  test("8. código de recuperação funciona uma vez só", async ({ api }) => {
    test.skip(!acesso, "depende do teste 4");
    // Gera códigos novos (pede um código atual do autenticador; os antigos deixam de valer).
    const passo = await proximoPasso(A);
    const gerados = await api.post("/auth/2fa/recovery-codes", { token: acesso, json: { code: codigoDoPasso(SEGREDO_TOTP, passo) } });
    expect(gerados.status()).toBe(200);
    marcarPassoUsado(A, passo);
    const codigos: string[] = (await dados(gerados)).recovery_codes;
    expect(codigos).toHaveLength(10);

    const primeira = await api.post("/auth/2fa/verify", { json: { mfa_token: await api.novoMfaToken(A), recovery_code: codigos[0] } });
    expect(primeira.status(), "código de recuperação válido").toBe(200);
    const segunda = await api.post("/auth/2fa/verify", { json: { mfa_token: await api.novoMfaToken(A), recovery_code: codigos[0] } });
    expect(segunda.status(), "o mesmo código de recuperação de novo").toBe(400);
  });

  test("9. contorno: com a senha, não dá para recadastrar o autenticador", async ({ api }) => {
    const mfa = await api.novoMfaToken(A);
    const resposta = await api.post("/auth/2fa/setup", { json: { mfa_token: mfa } });
    expect(resposta.status()).toBe(400);
    const corpo = await resposta.text();
    expect(corpo, "o servidor devolveu um QR Code novo").not.toContain("otpauth");
    expect(corpo).not.toContain("secret");
  });

  test("10. código vencido (1 min atrás) e código do futuro são recusados", async ({ api }) => {
    // A janela do servidor aceita o intervalo atual e um de cada lado (~30 s). Dois intervalos fora, não.
    const agora = passoAtual();
    for (const [nome, passo] of [["de 1 minuto atrás", agora - 2], ["de 1 minuto à frente", agora + 2]] as const) {
      const mfa = await api.novoMfaToken(A);
      const resposta = await api.post("/auth/2fa/verify", { json: { mfa_token: mfa, code: codigoDoPasso(SEGREDO_TOTP, passo as number) } });
      expect(resposta.status(), `código ${nome}`).toBe(400);
      expect(await resposta.text()).not.toContain("access");
    }
  });

  test("11. corrida: o mesmo código enviado duas vezes ao mesmo tempo entra uma vez só", async ({ api }) => {
    const [mfa1, mfa2] = [await api.novoMfaToken(A), await api.novoMfaToken(A)];
    const passo = await proximoPasso(A);
    const code = codigoDoPasso(SEGREDO_TOTP, passo);
    const respostas = await Promise.all([
      api.post("/auth/2fa/verify", { json: { mfa_token: mfa1, code } }),
      api.post("/auth/2fa/verify", { json: { mfa_token: mfa2, code } }),
    ]);
    marcarPassoUsado(A, passo);
    const status = respostas.map((r) => r.status()).sort();
    await test.info().attach("status das duas requisições", { body: status.join(", "), contentType: "text/plain" });
    expect(status.filter((s) => s === 200), "as duas requisições entraram com o mesmo código").toHaveLength(1);
    expect([400, 401]).toContain(status.find((s) => s !== 200));
  });

  test("12. códigos de recuperação antigos deixam de valer quando uma lista nova é gerada", async ({ api }) => {
    test.skip(!acesso, "depende do teste 4");
    const gerar = async () => {
      const passo = await proximoPasso(A);
      const r = await api.post("/auth/2fa/recovery-codes", { token: acesso, json: { code: codigoDoPasso(SEGREDO_TOTP, passo) } });
      expect(r.status()).toBe(200);
      marcarPassoUsado(A, passo);
      return (await dados(r)).recovery_codes as string[];
    };
    const antigos = await gerar();
    const novos = await gerar();
    expect(novos).not.toContain(antigos[0]);
    const comAntigo = await api.post("/auth/2fa/verify", { json: { mfa_token: await api.novoMfaToken(A), recovery_code: antigos[0] } });
    expect(comAntigo.status(), "um código da lista antiga ainda funcionou").toBe(400);
    const comNovo = await api.post("/auth/2fa/verify", { json: { mfa_token: await api.novoMfaToken(A), recovery_code: novos[0] } });
    expect(comNovo.status(), "o código da lista nova não funcionou").toBe(200);
  });

  test("13. corrida: o mesmo código de recuperação usado duas vezes ao mesmo tempo entra uma vez só", async ({ api }) => {
    test.skip(!acesso, "depende do teste 4");
    const passo = await proximoPasso(A);
    const gerados = await api.post("/auth/2fa/recovery-codes", { token: acesso, json: { code: codigoDoPasso(SEGREDO_TOTP, passo) } });
    marcarPassoUsado(A, passo);
    const codigo: string = (await dados(gerados)).recovery_codes[0];
    const [mfa1, mfa2] = [await api.novoMfaToken(A), await api.novoMfaToken(A)];
    const respostas = await Promise.all([
      api.post("/auth/2fa/verify", { json: { mfa_token: mfa1, recovery_code: codigo } }),
      api.post("/auth/2fa/verify", { json: { mfa_token: mfa2, recovery_code: codigo } }),
    ]);
    const status = respostas.map((r) => r.status()).sort();
    await test.info().attach("status das duas requisições", { body: status.join(", "), contentType: "text/plain" });
    expect(status.filter((s) => s === 200), "o mesmo código de recuperação entrou duas vezes").toHaveLength(1);
  });

  test("14. gerar códigos de recuperação exige login e o código atual do aplicativo", async ({ api }) => {
    test.skip(!acesso, "depende do teste 4");
    const semLogin = await api.post("/auth/2fa/recovery-codes", { json: { code: "123456" } });
    expect(semLogin.status(), "sem login").toBe(401);
    const codigoErrado = await api.post("/auth/2fa/recovery-codes", { token: acesso, json: { code: "000000" } });
    expect(codigoErrado.status(), "com login, mas código errado").toBe(400);
    expect(await codigoErrado.text()).not.toContain("recovery_codes");
  });
});

/*
 * Validade do mfa_token: depois de MFA_TOKEN_MAX_AGE segundos (300 = 5 min), nem o código certo
 * entra. Demora o prazo inteiro, por isso so roda com TESTE_LENTO=1 (npm run test:completo).
 * Se o servidor estiver com outro prazo (alteracao ao vivo), informe em TESTE_MFA_MAX_AGE.
 */
test.describe("2FA na API: validade do mfa_token", () => {
  test("15. o mfa_token vence: depois do prazo, nem o código certo entra", async ({ api }) => {
    test.skip(process.env.TESTE_LENTO !== "1", "Teste lento (espera o mfa_token vencer). Rode com: npm run test:completo");
    const prazo = Number(process.env.TESTE_MFA_MAX_AGE || 300);
    test.setTimeout((prazo + 180) * 1000);
    const mfa = await api.novoMfaToken(A);
    await new Promise((r) => setTimeout(r, (prazo + 5) * 1000));
    const passo = await proximoPasso(A);
    const resposta = await api.post("/auth/2fa/verify", { json: { mfa_token: mfa, code: codigoDoPasso(SEGREDO_TOTP, passo) } });
    expect(resposta.status(), `o mfa_token ainda valia depois de ${prazo} s`).toBe(401);
  });
});

/*
 * Primeiro acesso (cadastro do autenticador). Precisa de um usuario de teste SEM 2FA ativo, com a
 * mesma senha TESTE_SENHA: informe o e-mail em TESTE_USUARIO_SEM_2FA. Depois deste teste o
 * usuario fica com o 2FA ativo; para repetir, a plataforma reseta o 2FA dele.
 */
test.describe("2FA na API: primeiro acesso", () => {
  const email = process.env.TESTE_USUARIO_SEM_2FA ?? "";

  test("16. cadastro do autenticador: QR Code, ativação com o primeiro código e recuperação", async ({ api }) => {
    test.skip(!email, "Defina TESTE_USUARIO_SEM_2FA (e-mail de um usuário de teste sem o 2FA ativo).");
    const login = await dados(await api.loginSenha(email));
    expect(login, "o usuário já tem 2FA ativo").toMatchObject({ mfa_required: true, mfa_setup_required: true });
    expect(login).not.toHaveProperty("access");

    // Ativar sem ter pedido o QR Code, ou com código errado: recusado.
    expect((await api.post("/auth/2fa/activate", { json: { mfa_token: login.mfa_token, code: "000000" } })).status()).toBe(400);

    const setup = await dados(await api.post("/auth/2fa/setup", { json: { mfa_token: login.mfa_token } }));
    expect(setup.secret, "o servidor não devolveu o segredo").toMatch(/^[A-Z2-7]{16,}$/);
    expect(setup.otpauth_uri).toMatch(/^otpauth:\/\/totp\//);
    expect(String(setup.qr_code)).toMatch(/svg/i);

    const errado = await api.post("/auth/2fa/activate", { json: { mfa_token: login.mfa_token, code: "000000" } });
    expect(errado.status(), "ativou com código errado").toBe(400);

    const segredo: string = setup.secret;
    const ativado = await api.post("/auth/2fa/activate", { json: { mfa_token: login.mfa_token, code: codigoDoPasso(segredo, passoAtual()) } });
    expect(ativado.status()).toBe(200);
    const tokens = await dados(ativado);
    expect(tokens).toHaveProperty("access");
    expect(tokens.recovery_codes).toHaveLength(10);

    // Agora ativo: pedir outro QR Code é recusado, e o login seguinte já pede o código.
    const depois = await dados(await api.loginSenha(email));
    expect(depois.mfa_setup_required).toBe(false);
    expect((await api.post("/auth/2fa/setup", { json: { mfa_token: depois.mfa_token } })).status()).toBe(400);
    const entrou = await api.post("/auth/2fa/verify", { json: { mfa_token: depois.mfa_token, code: codigoDoPasso(segredo, passoAtual() + 1) } });
    expect(entrou.status(), "o código do autenticador recém-cadastrado não entrou").toBe(200);
  });
});
