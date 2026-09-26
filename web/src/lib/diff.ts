import { diffLines } from "diff"

export type Estado = "igual" | "novo" | "desatualizado" | "diferente"
export type Linha = { texto: string; estado: "igual" | "incluida" | "removida" }

const linhas = (valor: string) => valor.split("\n")

export function contar(previa: string, salvo: string) {
  let incluidas = 0
  let removidas = 0
  for (const parte of diffLines(salvo, previa)) {
    if (parte.added) incluidas += parte.count ?? 0
    else if (parte.removed) removidas += parte.count ?? 0
  }
  return { incluidas, removidas }
}

/**
 * O estado do bloco em relacao ao arquivo de out/.
 *
 * A diferenca sem edicao nao salva nao e edicao do operador: e o arquivo em
 * out/ que ficou para tras, porque o plan.py ou um template mudaram depois do
 * ultimo salvar. O cabecalho diz isso, e nao "N linhas incluidas".
 */
export function estadoDoBloco(previa: string | null, salvo: string | null, sujo: boolean) {
  if (previa === null || salvo === null) {
    return { estado: "novo" as Estado, incluidas: 0, removidas: 0 }
  }
  if (previa === salvo) return { estado: "igual" as Estado, incluidas: 0, removidas: 0 }
  const c = contar(previa, salvo)
  return { estado: (sujo ? "diferente" : "desatualizado") as Estado, ...c }
}

export function marcarLinhas(previa: string, salvo: string): Linha[] {
  const saida: Linha[] = []
  for (const parte of diffLines(salvo, previa)) {
    const estado: Linha["estado"] = parte.added ? "incluida" : parte.removed ? "removida" : "igual"
    // diffLines fecha cada parte com o \n final: removendo o ultimo vazio, a
    // volta das linhas nao cria uma linha fantasma no fim
    for (const texto of linhas(parte.value.endsWith("\n") ? parte.value.slice(0, -1) : parte.value)) {
      saida.push({ texto, estado })
    }
  }
  return saida
}
