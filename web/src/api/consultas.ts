import { useQuery } from "@tanstack/react-query"
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
export type Recusa = { erros: Record<string, string>; avisos: { campo: string; mensagem: string }[] }

export function lerRecusa(corpo: unknown): Recusa {
  if (corpo && typeof corpo === "object" && "erros" in corpo) return corpo as Recusa
  return { erros: { _corpo: "resposta inesperada da API" }, avisos: [] }
}

export const chaves = {
  plano: ["plano"] as const,
  peers: ["peers"] as const,
  peer: (id: number) => ["peer", id] as const,
  grupos: ["grupos"] as const,
  grupo: (id: number) => ["grupo", id] as const,
  blocos: ["blocos"] as const,
}

// As listas recarregam quando a janela volta ao foco: uma edicao manual no
// peers.yaml aparece sem F5
const comum = { refetchOnWindowFocus: true, staleTime: 5_000 }

export function usePlano() {
  return useQuery({
    queryKey: chaves.plano,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/plano")
      if (error) throw new Error("falha ao ler o plano")
      return data
    },
    ...comum,
  })
}

export function usePeers() {
  return useQuery({
    queryKey: chaves.peers,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/peers")
      if (error) throw new Error("falha ao listar os peers")
      return data
    },
    ...comum,
  })
}

export function usePeer(id: number | null) {
  return useQuery({
    queryKey: chaves.peer(id ?? -1),
    queryFn: async () => {
      const { data, error, response } = await cliente.GET("/api/peers/{ident}", {
        params: { path: { ident: id as number } },
      })
      if (response.status === 404) throw new Error("nao_encontrado")
      if (error) throw new Error("falha ao ler o peer")
      return data
    },
    enabled: id !== null,
    ...comum,
  })
}

export function useGrupos() {
  return useQuery({
    queryKey: chaves.grupos,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/grupos")
      if (error) throw new Error("falha ao listar os grupos")
      return data
    },
    ...comum,
  })
}

export function useGrupo(id: number | null) {
  return useQuery({
    queryKey: chaves.grupo(id ?? -1),
    queryFn: async () => {
      const { data, error, response } = await cliente.GET("/api/grupos/{ident}", {
        params: { path: { ident: id as number } },
      })
      if (response.status === 404) throw new Error("nao_encontrado")
      if (error) throw new Error("falha ao ler o grupo")
      return data
    },
    enabled: id !== null,
    ...comum,
  })
}

export function useBlocos() {
  return useQuery({
    queryKey: chaves.blocos,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/blocos")
      if (error) throw new Error("falha ao ler os blocos")
      return data
    },
    ...comum,
  })
}
