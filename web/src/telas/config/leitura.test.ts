import { describe, expect, it } from "vitest"
import { LINHA_DE_LEITURA, secaoNaLinha } from "./leitura"

// Os topos sao o que o getBoundingClientRect devolveria, com a janela ja
// rolada: negativo e o que passou por cima
const LINHA = LINHA_DE_LEITURA

describe("a secao da linha de leitura", () => {
  it("e a ultima cujo topo ja passou a linha", () => {
    expect(secaoNaLinha(["a", "b", "c"], [-500, 40, 300], LINHA)).toBe("b")
  })

  it("conta a secao que parou exatamente na linha", () => {
    expect(secaoNaLinha(["a", "b"], [-500, LINHA], LINHA)).toBe("b")
    expect(secaoNaLinha(["a", "b"], [-500, LINHA + 1], LINHA)).toBe("a")
  })

  it("a secao que o link do sumario acabou de abrir conta como lida", () => {
    // e o unico caso em que a conta depende do numero: o `scroll-mt-24` das
    // secoes poe a secao aberta em 96, e uma linha menor que isso deixaria a
    // marca presa na secao de cima, com a de baixo aberta na frente
    expect(secaoNaLinha(["a", "b"], [-500, 96], LINHA)).toBe("b")
  })

  it("antes de a primeira chegar nao ha secao nenhuma", () => {
    expect(secaoNaLinha(["a", "b"], [LINHA + 1, 400], LINHA)).toBe(null)
  })

  it("no fim da pagina a ultima continua sendo a lida", () => {
    // A janela enche e o topo passa a linha: a marca tem que ficar na ultima,
    // e nao voltar para a de cima nem sumir
    expect(secaoNaLinha(["a", "b", "c"], [-2000, -900, -120], LINHA)).toBe("c")
  })

  it("com a rolagem no fim, a marca e a ultima mesmo com o topo abaixo da linha", () => {
    // A ultima secao mais baixa que a janela: no fim da rolagem o topo dela
    // fica abaixo da linha, e a conta sozinha devolveria a penultima, que e
    // quem o operador NAO esta vendo
    expect(secaoNaLinha(["a", "b", "c"], [-2000, -900, 300], LINHA)).toBe("b")
    expect(secaoNaLinha(["a", "b", "c"], [-2000, -900, 300], LINHA, true)).toBe("c")
  })

  it("no fim de uma pagina sem secao nenhuma nao ha o que marcar", () => {
    expect(secaoNaLinha([], [], LINHA, true)).toBe(null)
  })

  it("sem secao nenhuma nao ha o que marcar", () => {
    expect(secaoNaLinha([], [], LINHA)).toBe(null)
  })

  it("a secao que sumiu do documento nao rouba a marca", () => {
    // o documento sem a secao conta como infinito, e nao como zero: com zero
    // toda secao ausente passaria a linha e a marca iria para a ultima
    expect(secaoNaLinha(["a", "b"], [Infinity, -500], LINHA)).toBe("b")
  })
})
