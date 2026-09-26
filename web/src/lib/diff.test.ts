import { describe, expect, it } from "vitest"
import { contar, estadoDoBloco, marcarLinhas } from "./diff"

const A = "linha 1\nlinha 2\nlinha 3"
const B = "linha 1\nlinha 2 mudada\nlinha 3"

describe("o estado do bloco em relacao ao out/", () => {
  it("sem arquivo salvo e arquivo novo, com sujo ou sem", () => {
    expect(estadoDoBloco(B, null, true)).toEqual({ estado: "novo", incluidas: 0, removidas: 0 })
    expect(estadoDoBloco(null, A, true).estado).toBe("novo")
  })

  it("previa igual ao salvo e igual", () => {
    expect(estadoDoBloco(A, A, false)).toEqual({ estado: "igual", incluidas: 0, removidas: 0 })
    // com alteracao nao salva o formulario esta sujo mas o bloco nao mudou:
    // o cabecalho continua dizendo igual ao salvo
    expect(estadoDoBloco(A, A, true).estado).toBe("igual")
  })

  it("diferenca com edicao nao salva conta as linhas", () => {
    expect(estadoDoBloco(B, A, true)).toEqual({ estado: "diferente", incluidas: 1, removidas: 1 })
  })

  it("diferenca sem edicao nenhuma e arquivo desatualizado", () => {
    // o plan.py ou um template mudou depois do ultimo salvar
    expect(estadoDoBloco(B, A, false)).toEqual({ estado: "desatualizado", incluidas: 1, removidas: 1 })
  })
})

describe("a contagem de linhas", () => {
  it("conta a linha incluida e a removida", () => {
    expect(contar(B, A)).toEqual({ incluidas: 1, removidas: 1 })
  })

  it("conta o bloco inteiro que entrou", () => {
    // as duas pontas com quebra no fim, que e como o template escreve
    expect(contar("a\nb\nc\n", "a\n")).toEqual({ incluidas: 2, removidas: 0 })
  })

  it("sem quebra no fim, a linha da ponta conta dos dois lados", () => {
    // o diffLines compara por linha: "a" sem quebra contra "a\nb\nc" nao forma
    // prefixo comum, e a contagem sai maior nos dois lados. So acontece com
    // arquivo mexido a mao, porque o gerador sempre fecha a ultima linha
    expect(contar("a\nb\nc", "a")).toEqual({ incluidas: 3, removidas: 1 })
  })
})

describe("a marcacao das linhas", () => {
  it("marca incluida e removida, e o resto fica igual", () => {
    expect(marcarLinhas(B, A)).toEqual([
      { texto: "linha 1", estado: "igual" },
      { texto: "linha 2", estado: "removida" },
      { texto: "linha 2 mudada", estado: "incluida" },
      { texto: "linha 3", estado: "igual" },
    ])
  })

  it("tirando as removidas sobra a previa, linha por linha", () => {
    for (const [previa, salvo] of [[B, A], [A, A], ["a\nb\nc\nd", "a\nd"]] as const) {
      const texto = marcarLinhas(previa, salvo)
        .filter((l) => l.estado !== "removida")
        .map((l) => l.texto)
        .join("\n")
      expect(texto).toBe(previa)
    }
  })
})
