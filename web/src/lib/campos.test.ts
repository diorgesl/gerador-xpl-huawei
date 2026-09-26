import { describe, expect, it } from "vitest"
import {
  CAMPOS_POR_TIPO, camposDoErro, cascata, origemEsperada, secoesComErro, visivel,
} from "./campos"

const PADROES = {
  tipos: {
    cliente: { lp_base: 300, route_limit: 50, timer_keepalive: null, timer_hold: null },
    upstream: { lp_base: 100, route_limit: 1500000, timer_keepalive: 10, timer_hold: 30 },
    ix: { lp_base: 190, route_limit: 500000, timer_keepalive: null, timer_hold: null },
  },
  origem_tipo: { cliente: 1100, upstream: 1400, ix: 1300 },
  origem_classe: { transito: 1100, residencial: 1110 },
  downstream: ["cliente", "parceiro"],
  origens_por_tipo: {},
  origem_nome: {},
}

describe("a visibilidade de um campo", () => {
  const vazio = { asn: "", prefixos_v4: [] as string[], bfd: true }

  it("aparece quando pertence ao tipo", () => {
    expect(visivel("ap_allowed", vazio, {}, CAMPOS_POR_TIPO, "pni")).toBe(true)
    expect(visivel("ap_allowed", vazio, {}, CAMPOS_POR_TIPO, "cliente")).toBe(false)
  })

  it("aparece quando tem erro, mesmo fora do tipo", () => {
    expect(visivel("ap_allowed", vazio, { ap_allowed: "PNI sem allowlist" }, CAMPOS_POR_TIPO, "cliente")).toBe(true)
  })

  it("aparece quando tem valor, senao o dado gravado fica invisivel", () => {
    const comValor = { ap_allowed: ["15169"], prefixos_v4: [], bfd: false }
    expect(visivel("ap_allowed", comValor, {}, CAMPOS_POR_TIPO, "cliente")).toBe(true)
  })

  it("campo fora da tabela pertence a todos os tipos", () => {
    for (const tipo of ["cliente", "parceiro", "upstream", "ix", "pni"]) {
      expect(visivel("apelido", vazio, {}, CAMPOS_POR_TIPO, tipo)).toBe(true)
      expect(visivel("nome", vazio, {}, CAMPOS_POR_TIPO, tipo)).toBe(true)
    }
  })
})

describe("o mapeamento do erro para o campo", () => {
  it("traduz a sessao composta para o campo plano do formulario", () => {
    expect(camposDoErro("sessoes.v4.local", "cliente")).toEqual(["sessao_v4_local"])
    expect(camposDoErro("sessoes.v6.remoto", "cliente")).toEqual(["sessao_v6_remoto"])
  })

  it("o erro de sessao sem familia marca os quatro", () => {
    expect(camposDoErro("sessoes", "cliente")).toEqual([
      "sessao_v4_local", "sessao_v4_remoto", "sessao_v6_local", "sessao_v6_remoto",
    ])
  })

  it("o erro de prefixos marca as duas familias", () => {
    expect(camposDoErro("prefixos", "cliente")).toEqual(["prefixos_v4", "prefixos_v6"])
    expect(camposDoErro("te_prefixos", "upstream")).toEqual(["te_prefixos_v4", "te_prefixos_v6"])
  })

  it("no grupo do tipo ix o aprendizado e o do bloco do IX", () => {
    expect(camposDoErro("aprendizado", "ix", true)).toEqual(["aprendizado_ix"])
    expect(camposDoErro("aprendizado", "upstream", true)).toEqual(["aprendizado"])
    expect(camposDoErro("aprendizado", "ix", false)).toEqual(["aprendizado"])
  })

  it("erro sem campo nenhum nao aponta para lugar nenhum", () => {
    for (const chave of ["bgpq4", "_corpo", "_", "membros"]) {
      expect(camposDoErro(chave, "cliente")).toEqual([])
    }
  })

  it("campo simples do formulario mapeia nele mesmo", () => {
    expect(camposDoErro("asn", "cliente")).toEqual(["asn"])
    expect(camposDoErro("route_limit", "cliente")).toEqual(["route_limit"])
  })
})

describe("o indice de secoes", () => {
  it("conta o erro na secao do campo", () => {
    const contagem = secoesComErro({ asn: "ja usado", route_limit: "maior que zero" }, "cliente", false)
    expect(contagem.identificacao).toBe(1)
    expect(contagem.limites).toBe(1)
    expect(contagem.politica).toBe(0)
  })

  it("erro sem campo nao conta em secao nenhuma", () => {
    const contagem = secoesComErro({ bgpq4: "sem rede", prefixos: "prefixo invalido" }, "cliente", false)
    expect(Object.values(contagem).reduce((a, b) => a + b, 0)).toBe(1)
    expect(contagem.prefixos).toBe(1)
  })
})

describe("a cascata de defaults ao trocar o tipo", () => {
  const base = { lp_base: "100", route_limit: "1500000", timer_keepalive: "10", timer_hold: "30", origem: "1400" }

  it("reescreve o que ainda esta no default do tipo anterior", () => {
    const novo = cascata("upstream", "cliente", base, PADROES, ["lp_base", "route_limit", "timer_keepalive", "timer_hold"])
    expect(novo.lp_base).toBe("300")
    expect(novo.route_limit).toBe("50")
    expect(novo.timer_keepalive).toBe("")
    expect(novo.timer_hold).toBe("")
  })

  it("nao toca no que o operador digitou por cima", () => {
    const proprio = { ...base, lp_base: "150", timer_hold: "45" }
    const novo = cascata("upstream", "cliente", proprio, PADROES, ["lp_base", "route_limit", "timer_keepalive", "timer_hold"])
    expect(novo.lp_base).toBe("150")
    expect(novo.timer_hold).toBe("45")
    expect(novo.route_limit).toBe("50")
  })

  it("troca de tipo redesenha a origem", () => {
    const novo = cascata("upstream", "ix", base, PADROES, ["lp_base"])
    expect(novo.origem).toBe("1300")
  })

  it("a classe nao mexida deixa a origem onde esta", () => {
    const doCliente = { ...base, classe: "transito", origem: "1100" }
    const igual = cascata("cliente", "cliente", doCliente, PADROES, [], "transito")
    expect(igual.origem).toBe("1100")
  })

  it("troca de classe mexe na origem do downstream quando ela ainda era a da classe antiga", () => {
    const doCliente = { ...base, classe: "residencial", origem: "1100" }
    expect(cascata("cliente", "cliente", doCliente, PADROES, [], "transito").origem).toBe("1110")
  })

  it("troca de classe respeita a origem que o operador escolheu na mao", () => {
    const doCliente = { ...base, classe: "residencial", origem: "1900" }
    expect(cascata("cliente", "cliente", doCliente, PADROES, [], "transito").origem).toBe("1900")
  })

  it("nao mexe na origem quando o tipo nao e downstream", () => {
    const up = { classe: "transito", origem: "1400" }
    expect(cascata("upstream", "upstream", up, PADROES, [], "residencial").origem).toBe("1400")
  })

  it("nao reescreve nada quando o tipo nao mudou", () => {
    const novo = cascata("upstream", "upstream", base, PADROES, ["lp_base", "route_limit"])
    expect(novo).toEqual(base)
  })

  it("a origem esperada da classe vence no downstream", () => {
    expect(origemEsperada("cliente", "residencial", PADROES)).toBe(1110)
    expect(origemEsperada("cliente", "", PADROES)).toBe(1100)
    expect(origemEsperada("upstream", "residencial", PADROES)).toBe(1400)
  })
})
