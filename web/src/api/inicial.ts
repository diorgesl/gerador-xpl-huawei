import { useQuery } from "@tanstack/react-query"
import { useAsn } from "@/app/tenant"
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
 *
 * O `asn !== null` e a janela entre a montagem da tela e a lista de ASNs
 * chegando: o `ligado` dela e verdadeiro desde o primeiro render, e sem esta
 * guarda o pedido sairia sem o `?asn=` e a tela mostraria a falha de rede por
 * um instante em cima de um pedido que a propria tela recusaria.
 */
export function usePeerInicial(ident: number | null, de: number | null, tipo: string, ligado = true) {
  const asn = useAsn()
  return useQuery({
    queryKey: ["peer-inicial", ident, de, tipo, asn],
    enabled: ligado && asn !== null,
    queryFn: async (): Promise<PeerRegistro> => {
      const resposta = de !== null
        ? await cliente.GET("/api/peers/{ident}/copia", {
            params: { path: { ident: de }, query: { asn: Number(asn) } } })
        : ident !== null
          ? await cliente.GET("/api/peers/{ident}", {
              params: { path: { ident }, query: { asn: Number(asn) } } })
          : await cliente.GET("/api/peers/novo", {
              params: { query: { tipo, asn: Number(asn) } } })
      if (resposta.response.status === 404) throw new Error("nao_encontrado")
      if (resposta.error) throw new Error("falha ao ler o peer")
      return resposta.data
    },
  })
}

export function useGrupoInicial(ident: number | null, de: number | null, tipo: string, ligado = true) {
  const asn = useAsn()
  return useQuery({
    queryKey: ["grupo-inicial", ident, de, tipo, asn],
    enabled: ligado && asn !== null,
    queryFn: async (): Promise<GrupoRegistro> => {
      const resposta = de !== null
        ? await cliente.GET("/api/grupos/{ident}/copia", {
            params: { path: { ident: de }, query: { asn: Number(asn) } } })
        : ident !== null
          ? await cliente.GET("/api/grupos/{ident}", {
              params: { path: { ident }, query: { asn: Number(asn) } } })
          : await cliente.GET("/api/grupos/novo", {
              params: { query: { tipo, asn: Number(asn) } } })
      if (resposta.response.status === 404) throw new Error("nao_encontrado")
      if (resposta.error) throw new Error("falha ao ler o grupo")
      return resposta.data
    },
  })
}
