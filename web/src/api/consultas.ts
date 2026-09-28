import { useQuery } from "@tanstack/react-query"
import { useAsn } from "@/app/tenant"
import type { components } from "./schema"
import { cliente } from "./cliente"

export type Plano = components["schemas"]["Plano"]
export type PeerForm = components["schemas"]["PeerForm"]
export type GrupoForm = components["schemas"]["GrupoForm"]
export type PeerRegistro = components["schemas"]["PeerRegistro"]
export type GrupoRegistro = components["schemas"]["GrupoRegistro"]
export type PeerResumo = components["schemas"]["PeerResumo"]
export type GrupoResumo = components["schemas"]["GrupoResumo"]
export type Previa = components["schemas"]["Previa"]
export type Saida = components["schemas"]["Saida"]
export type Blocos = components["schemas"]["Blocos"]
export type Config = components["schemas"]["Config"]
export type SecaoConfig = components["schemas"]["SecaoConfig"]
export type RedeAtual = components["schemas"]["RedeAtual"]
export type Sessao = components["schemas"]["SessaoResposta"]
export type Recusa = { erros: Record<string, string>; avisos: { campo: string; mensagem: string }[] }

/**
 * O corpo que o `lerRecusa` entende. Quem nao for isto e resposta fora do
 * modelo, e nela a mensagem e o aviso da escrita (`_corpo` seria o texto de um
 * campo que nao existe).
 */
export function temRecusa(corpo: unknown): boolean {
  return Boolean(corpo) && typeof corpo === "object" && "erros" in (corpo as object)
}

export function lerRecusa(corpo: unknown): Recusa {
  if (temRecusa(corpo)) return corpo as Recusa
  return { erros: { _corpo: "resposta inesperada da API" }, avisos: [] }
}

/**
 * A recusa da escrita com a marca do evento, que e o que decide ate quando ela
 * vale: a proxima previa que responder substitui a lista de erros dela.
 *
 * A marca sai daqui, e nao do corpo do callback da mutacao, por duas razoes: o
 * literal era o mesmo em quatro lugares, e a regra `react-hooks/purity` do lint
 * le o callback do `onSuccess` como codigo de render quando ele chama um helper
 * de outro modulo, e ai o `Date.now()` vira erro.
 */
export function recusaComMarca(corpoErro: unknown, irr: string | null = null) {
  return { em: Date.now(), erros: lerRecusa(corpoErro).erros, irr }
}

export const chaves = {
  asns: ["asns"] as const,
  plano: ["plano"] as const,
  peers: ["peers"] as const,
  peer: (id: number) => ["peer", id] as const,
  grupos: ["grupos"] as const,
  grupo: (id: number) => ["grupo", id] as const,
  blocos: ["blocos"] as const,
  config: ["config"] as const,
  sessao: ["sessao"] as const,
}

// As listas recarregam quando a janela volta ao foco: uma edicao manual no
// peers.yaml aparece sem F5
const comum = { refetchOnWindowFocus: true, staleTime: 5_000 }

/** A lista de ASNs, a unica consulta que nao e de um tenant: e ela quem diz quais existem. */
export function useAsns() {
  return useQuery({
    queryKey: chaves.asns,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/asns")
      if (error) throw new Error("falha ao listar os ASNs")
      return data
    },
    ...comum,
  })
}

export function usePlano() {
  const asn = useAsn()
  return useQuery({
    // o ASN entra na chave: sem ele, o react-query serviria a lista de um
    // tenant enquanto o outro esta selecionado, e a troca mostraria o
    // cadastro da rede errada ate o refetch chegar
    queryKey: [...chaves.plano, asn],
    // sem ASN nao ha o que perguntar: a janela entre a montagem e a lista
    // de ASNs chegando e curta, e uma consulta sem asn seria um 422
    enabled: asn !== null,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/plano", {
        // O `asn` da query e `int` na API, e a lista e o sessionStorage o
        // guardam como texto: o `Number` e a travessia entre os dois, e o
        // `enabled` acima garante que ela so acontece com o ASN na mao (o
        // `Number(null)` seria o 0, um tenant que nao existe)
        params: { query: { asn: Number(asn) } },
      })
      if (error) throw new Error("falha ao ler o plano")
      return data
    },
    ...comum,
  })
}

export function usePeers() {
  const asn = useAsn()
  return useQuery({
    queryKey: [...chaves.peers, asn],
    enabled: asn !== null,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/peers", {
        params: { query: { asn: Number(asn) } },
      })
      if (error) throw new Error("falha ao listar os peers")
      return data
    },
    ...comum,
  })
}

export function usePeer(id: number | null) {
  const asn = useAsn()
  return useQuery({
    queryKey: [...chaves.peer(id ?? -1), asn],
    enabled: id !== null && asn !== null,
    queryFn: async () => {
      const { data, error, response } = await cliente.GET("/api/peers/{ident}", {
        params: { path: { ident: id as number }, query: { asn: Number(asn) } },
      })
      if (response.status === 404) throw new Error("nao_encontrado")
      if (error) throw new Error("falha ao ler o peer")
      return data
    },
    ...comum,
  })
}

export function useGrupos() {
  const asn = useAsn()
  return useQuery({
    queryKey: [...chaves.grupos, asn],
    enabled: asn !== null,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/grupos", {
        params: { query: { asn: Number(asn) } },
      })
      if (error) throw new Error("falha ao listar os grupos")
      return data
    },
    ...comum,
  })
}

export function useGrupo(id: number | null) {
  const asn = useAsn()
  return useQuery({
    queryKey: [...chaves.grupo(id ?? -1), asn],
    enabled: id !== null && asn !== null,
    queryFn: async () => {
      const { data, error, response } = await cliente.GET("/api/grupos/{ident}", {
        params: { path: { ident: id as number }, query: { asn: Number(asn) } },
      })
      if (response.status === 404) throw new Error("nao_encontrado")
      if (error) throw new Error("falha ao ler o grupo")
      return data
    },
    ...comum,
  })
}

export function useBlocos() {
  const asn = useAsn()
  return useQuery({
    queryKey: [...chaves.blocos, asn],
    enabled: asn !== null,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/blocos", {
        params: { query: { asn: Number(asn) } },
      })
      if (error) throw new Error("falha ao ler os blocos")
      return data
    },
    ...comum,
  })
}

export function useConfig() {
  const asn = useAsn()
  return useQuery({
    queryKey: [...chaves.config, asn],
    enabled: asn !== null,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/config", {
        params: { query: { asn: Number(asn) } },
      })
      if (error) throw new Error("falha ao ler a config")
      return data
    },
    ...comum,
  })
}
