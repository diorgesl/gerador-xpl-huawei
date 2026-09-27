import { useQuery } from "@tanstack/react-query"
import { cliente } from "./cliente"
import type { GrupoRegistro, PeerRegistro } from "./consultas"

/**
 * O registro que abre a tela: o salvo, a copia ou o em branco. Sao os tres GET
 * da spec, e a tela precisa de um deles por vez. O 404 vira o erro
 * "nao_encontrado", que a tela distingue de uma falha qualquer.
 *
 * O `ligado` e da tela de endereco invalido (`/peers/abc`): sem ele a consulta
 * sairia com o ident nulo e traria o formulario em branco de `/peers/novo`,
 * que e um registro que a tela nem vai mostrar.
 */
export function usePeerInicial(ident: number | null, de: number | null, tipo: string, ligado = true) {
  return useQuery({
    queryKey: ["peer-inicial", ident, de, tipo],
    enabled: ligado,
    queryFn: async (): Promise<PeerRegistro> => {
      const resposta = de !== null
        ? await cliente.GET("/api/peers/{ident}/copia", { params: { path: { ident: de } } })
        : ident !== null
          ? await cliente.GET("/api/peers/{ident}", { params: { path: { ident } } })
          : await cliente.GET("/api/peers/novo", { params: { query: { tipo } } })
      if (resposta.response.status === 404) throw new Error("nao_encontrado")
      if (resposta.error) throw new Error("falha ao ler o peer")
      return resposta.data
    },
  })
}

export function useGrupoInicial(ident: number | null, de: number | null, tipo: string, ligado = true) {
  return useQuery({
    queryKey: ["grupo-inicial", ident, de, tipo],
    enabled: ligado,
    queryFn: async (): Promise<GrupoRegistro> => {
      const resposta = de !== null
        ? await cliente.GET("/api/grupos/{ident}/copia", { params: { path: { ident: de } } })
        : ident !== null
          ? await cliente.GET("/api/grupos/{ident}", { params: { path: { ident } } })
          : await cliente.GET("/api/grupos/novo", { params: { query: { tipo } } })
      if (resposta.response.status === 404) throw new Error("nao_encontrado")
      if (resposta.error) throw new Error("falha ao ler o grupo")
      return resposta.data
    },
  })
}
