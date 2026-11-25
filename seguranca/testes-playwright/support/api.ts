import { test, type APIRequestContext, type APIResponse, type Page } from "@playwright/test";
import { API_URL, SEGREDO_TOTP, SENHA, USUARIOS } from "./config";
import { textoDaLinha, type LinhaApi, type Rotulo } from "./painel";
import { quemEh } from "./sessoes";
import { codigoDoPasso, esperarPasso, marcarPassoUsado, passoAtual, proximoPasso } from "./totp";

export type Sessao = {
  access: string;
  refresh: string;
  user: { id: number; name: string; email: string; role: string | null };
};

export type Opcoes = {
  token?: string;
  json?: unknown;
  form?: Record<string, string>;
  headers?: Record<string, string>;
  /** false: devolve o 429 em vez de esperar o Retry-After (so o teste de limite usa). */
  esperarLimite?: boolean;
  /** Quem aparece no painel/log. Sem isso, descobre pelo token (A, B, C) ou pelo e-mail do corpo. */
  quem?: string;
  /** Rótulo do painel calculado pela resposta, quando o status sozinho engana (ex.: preflight de CORS). */
  avaliar?: (resposta: APIResponse) => Rotulo;
};

function quemChamou(opcoes: Opcoes): string {
  if (opcoes.quem) return opcoes.quem;
  if (opcoes.token) return quemEh(opcoes.token);
  const email = (opcoes.json as { email?: string } | undefined)?.email;
  const letra = Object.entries(USUARIOS).find(([, e]) => e === email)?.[0];
  return letra ? `${letra} (login)` : "anônimo";
}

const dormir = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Corpo da resposta sem o envelope {"data": ...} da API. */
export async function dados(resposta: APIResponse): Promise<any> {
  const corpo = await resposta.json().catch(() => null);
  return corpo && typeof corpo === "object" && "data" in corpo ? corpo.data : corpo;
}

/**
 * Cliente da API para os testes. Nunca levanta erro em 4xx/5xx (o teste olha o status) e
 * registra "status METODO rota" de cada chamada, que vai para o relatorio como evidencia
 * (sem tokens nem senhas).
 */
export class Api {
  readonly registro: string[] = [];
  /** Pagina do painel visual (so quando criado pela fixture "api"). */
  painel?: Page;
  /** Avisa (no painel do video) que o servidor pediu para esperar o limite de tentativas. */
  aoEsperar?: (segundos: number) => Promise<void>;

  /** aoRegistrar: mostra a chamada no painel visual (fixtures.ts). */
  constructor(
    private readonly ctx: APIRequestContext,
    private readonly aoRegistrar?: (linha: LinhaApi) => Promise<void>,
  ) {}

  async chamar(metodo: string, rota: string, opcoes: Opcoes = {}): Promise<APIResponse> {
    const url = rota.startsWith("http") ? rota : API_URL + rota;
    for (let tentativa = 0; ; tentativa++) {
      const resposta = await this.ctx.fetch(url, {
        method: metodo,
        headers: {
          Accept: "application/json",
          ...(opcoes.token ? { Authorization: `Bearer ${opcoes.token}` } : {}),
          ...opcoes.headers,
        },
        data: opcoes.json,
        form: opcoes.form,
        failOnStatusCode: false,
        timeout: 90_000, // o Render gratuito leva ~1 min para acordar
      });
      const linha: LinhaApi = { quem: quemChamou(opcoes), metodo, rota, status: resposta.status(), rotulo: opcoes.avaliar?.(resposta) };
      this.registro.push(`${String(linha.status).padStart(4)}  ${metodo.padEnd(6)} ${rota}   (${linha.quem})`);
      console.log(`[api] ${textoDaLinha(linha)}`);
      // Cada chamada vira um passo com nome no --ui (o "log" ao lado da tela) e uma linha no painel.
      await test.step(textoDaLinha(linha), async () => {
        await this.aoRegistrar?.(linha);
      });
      // Outros testes rodados no mesmo minuto podem ter gastado o limite (10/min). Espera e repete.
      if (resposta.status() !== 429 || opcoes.esperarLimite === false || tentativa >= 2) return resposta;
      const espera = Math.min(Number(resposta.headers()["retry-after"]) || 60, 70);
      this.registro.push(`      (limite de tentativas: aguardando ${espera} s)`);
      await this.aoEsperar?.(espera);
      await dormir((espera + 1) * 1000);
    }
  }

  get = (rota: string, opcoes?: Opcoes) => this.chamar("GET", rota, opcoes);
  post = (rota: string, opcoes?: Opcoes) => this.chamar("POST", rota, opcoes);
  patch = (rota: string, opcoes?: Opcoes) => this.chamar("PATCH", rota, opcoes);

  /** Etapa 1: e-mail e senha. Com o 2FA, devolve so o mfa_token. */
  loginSenha(email: string, senha = SENHA) {
    return this.post("/auth/login", { json: { email, password: senha } });
  }

  async novoMfaToken(email: string): Promise<string> {
    const corpo = await dados(await this.loginSenha(email));
    if (!corpo?.mfa_token) throw new Error(`O login de ${email} nao devolveu mfa_token: ${JSON.stringify(corpo)?.slice(0, 200)}`);
    return corpo.mfa_token;
  }

  /**
   * Etapa 2: manda um codigo TOTP que este usuario ainda nao usou. Se o servidor disser que o
   * intervalo ja foi usado (por outro teste ou pelos scripts Python), passa para o seguinte.
   */
  async verificarComCodigo(email: string, mfaToken: string) {
    let passo = await proximoPasso(email);
    let resposta!: APIResponse;
    let codigo = "";
    for (let tentativa = 0; tentativa < 4; tentativa++) {
      codigo = codigoDoPasso(SEGREDO_TOTP, passo);
      resposta = await this.post("/auth/2fa/verify", { json: { mfa_token: mfaToken, code: codigo } });
      if (resposta.ok()) {
        marcarPassoUsado(email, passo);
        break;
      }
      if (resposta.status() !== 400) break;
      const texto = await resposta.text();
      if (texto.includes("utilizado") || passo < passoAtual() - 1) {
        marcarPassoUsado(email, passo);
        passo = await proximoPasso(email);
      } else if (passo > passoAtual()) {
        await esperarPasso(passo); // servidor com janela 0: so aceita o intervalo exato
      } else {
        break; // codigo do intervalo certo e mesmo assim recusado: segredo errado
      }
    }
    return { resposta, codigo, passo };
  }

  /** Login completo (senha + codigo). Devolve os tokens e o usuario. */
  async entrar(email: string): Promise<Sessao> {
    const login = await this.loginSenha(email);
    if (login.status() !== 200) {
      throw new Error(`Login de ${email} falhou: ${login.status()} ${(await login.text()).slice(0, 200)}`);
    }
    const corpo = await dados(login);
    if (corpo.access) return { access: corpo.access, refresh: corpo.refresh, user: corpo.user };
    if (corpo.mfa_setup_required) {
      throw new Error(`${email} ainda nao tem o 2FA ativo. Rode: python manage.py preparar_teste_seguranca`);
    }
    const { resposta } = await this.verificarComCodigo(email, corpo.mfa_token);
    if (!resposta.ok()) {
      throw new Error(`2FA de ${email} falhou: ${resposta.status()} ${(await resposta.text()).slice(0, 200)}. Confira TESTE_TOTP_SEGREDO.`);
    }
    const tokens = await dados(resposta);
    return { access: tokens.access, refresh: tokens.refresh, user: tokens.user };
  }
}
