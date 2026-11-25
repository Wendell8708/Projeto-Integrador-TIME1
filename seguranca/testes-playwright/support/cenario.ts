import type { Api } from "./api";
import { dados } from "./api";
import type { Sessao } from "./api";

/**
 * Recursos de teste de um usuario: a viagem do lote TESTE-IDOR-<letra> (criada pelo
 * preparar_teste_seguranca), com a placa, o veiculo e a fazenda dela. Mesma busca do teste_idor.py.
 */
export type Recursos = { viagem: number; placa: number; veiculo: number; fazenda: number; destino: number };

export async function recursosDe(api: Api, s: Sessao, letra: "A" | "B"): Promise<Recursos> {
  const resposta = await api.get("/shipments?page_size=200", { token: s.access });
  const viagens: any[] = (await dados(resposta)) ?? [];
  const viagem = viagens.find(
    (v) => v.created_by === s.user.id && (v.items ?? []).some((i: any) => i.lot === `TESTE-IDOR-${letra}`),
  );
  if (!viagem) {
    throw new Error(`Viagem de teste do ${letra} nao encontrada. Rode: python manage.py preparar_teste_seguranca`);
  }
  return { viagem: viagem.id, placa: viagem.device, veiculo: viagem.vehicle, fazenda: viagem.origin, destino: viagem.destination };
}

export const ids = (lista: unknown) => (Array.isArray(lista) ? lista.map((x: any) => x.id) : []);
