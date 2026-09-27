import { useQuery } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import { cliente } from "./cliente"
import type { GrupoForm, PeerForm, Previa } from "./consultas"

const ATRASO = 400

/**
 * A previa do formulario aberto, 400ms depois da ultima alteracao.
 *
 * O valor atrasado entra na chave da consulta: quando ele muda, o TanStack
 * cancela a requisicao anterior pelo AbortController e comeca outra. E a regra
 * da spec, e sai de graca do desenho da chave.
 *
 * O atrasado comeca nulo, e a consulta so liga depois da primeira janela: com
 * o valor inicial direto, a previa dispararia na montagem, com o formulario
 * em branco, e o painel mostraria o bloco de um peer vazio por um instante ate
 * o registro chegar e o reset mudar os valores.
 */
export function usePrevia({ tipo, id, valores, ligado }: {
  tipo: "peers" | "grupos"
  id: number | null
  valores: PeerForm | GrupoForm
  ligado: boolean
}) {
  const [atrasado, setAtrasado] = useState<PeerForm | GrupoForm | null>(null)

  useEffect(() => {
    const relogio = setTimeout(() => setAtrasado(valores), ATRASO)
    return () => clearTimeout(relogio)
  }, [valores])

  return useQuery({
    queryKey: ["previa", tipo, id, atrasado],
    enabled: ligado && atrasado !== null,
    queryFn: async ({ signal }) => {
      // O caminho vai literal, e nao numa variavel: o openapi-fetch tipa cada
      // rota pelo literal, e um `caminho as never` joga a chamada no overload
      // sem opcoes, onde o segundo argumento so pode ser `undefined` (o
      // `tsc -b` reprova com TS2345). Duas chamadas literais mantem o mesmo
      // pedido, com o init conferido contra o schema de cada uma.
      const params = { params: { query: { id: id ?? undefined } } }
      const { data, error } = tipo === "peers"
        ? await cliente.POST("/api/peers/previa", { ...params, body: atrasado as PeerForm, signal })
        : await cliente.POST("/api/grupos/previa", { ...params, body: atrasado as GrupoForm, signal })
      if (error) throw error
      return data as unknown as Previa
    },
  })
}
