import { afterEach, describe, expect, it, vi } from "vitest"
import { lerRecusa } from "./consultas"

afterEach(() => vi.unstubAllGlobals())

// O jsdom nao implementa Request (so o Headers): quem responde por ele e o
// Request do Node, que recusa URL relativa com ERR_INVALID_URL. No browser a
// URL relativa resolve contra o documento e passa, e e esse comportamento que
// o teste do caminho precisa. O shim guarda a URL como veio, que e o unico
// pedaco que o teste le, e o toString a devolve para o stub do fetch.
class Requisicao {
  url: string

  constructor(url: string) {
    this.url = url
  }

  toString() {
    return this.url
  }
}

describe("o cliente fala com o mesmo caminho relativo em dev e em producao", () => {
  it("o GET do plano vai para /api/plano", async () => {
    const chamadas: string[] = []
    vi.stubGlobal("Request", Requisicao)
    vi.stubGlobal("fetch", (entrada: RequestInfo | URL) => {
      chamadas.push(String(entrada))
      return Promise.resolve(new Response("{}", { status: 200, headers: { "content-type": "application/json" } }))
    })
    // o createClient le globalThis.Request e globalThis.fetch na criacao, entao
    // o modulo tem que ser avaliado depois dos stubs: assim quem corre aqui e o
    // cliente de verdade, com o baseUrl vazio do cliente.ts
    vi.resetModules()
    const { cliente } = await import("./cliente")
    await cliente.GET("/api/plano")
    expect(chamadas).toEqual(["/api/plano"])
  })
})

describe("o cliente avisa quando a sessao caiu", () => {
  // o chamador escolhe a requisicao: e o caminho dela que decide se o 401
  // significa "sessao caiu" ou "senha errada"
  async function comResposta(
    status: number,
    chamada: (cliente: typeof import("./cliente").cliente) => Promise<unknown>,
  ) {
    vi.stubGlobal("Request", Requisicao)
    vi.stubGlobal("fetch", () =>
      Promise.resolve(new Response("{}", { status, headers: { "content-type": "application/json" } })),
    )
    vi.resetModules()
    const modulo = await import("./cliente")
    let avisos = 0
    modulo.quandoPerderSessao(() => { avisos += 1 })
    await chamada(modulo.cliente)
    return avisos
  }

  it("avisa no 401 de uma consulta qualquer", async () => {
    const avisos = await comResposta(401, (c) => c.GET("/api/plano"))

    expect(avisos).toBe(1)
  })

  it("nao avisa no 422 nem no 500", async () => {
    expect(await comResposta(422, (c) => c.GET("/api/plano"))).toBe(0)
    expect(await comResposta(500, (c) => c.GET("/api/plano"))).toBe(0)
  })

  it("nao avisa no 401 do login, que e senha errada", async () => {
    // se avisasse, a tela de login recarregaria a cada chute e apagaria a
    // mensagem de erro e a senha digitada
    const avisos = await comResposta(401, (c) =>
      c.POST("/api/login", { body: { usuario: "admin", senha: "chute" } }),
    )

    expect(avisos).toBe(0)
  })
})

describe("a resposta crua de um fetch fora do cliente", () => {
  // o /base.txt e texto puro e nao esta no schema: ele sai por fetch cru nas
  // duas telas, e por isso nao passa pelo middleware do cliente
  async function comStatus(status: number) {
    vi.stubGlobal("Request", Requisicao)
    vi.resetModules()
    const modulo = await import("./cliente")
    let avisos = 0
    modulo.quandoPerderSessao(() => { avisos += 1 })
    const parar = modulo.sessaoVencida(new Response("", { status }))
    return { parar, avisos }
  }

  it("o 401 manda parar e avisa", async () => {
    expect(await comStatus(401)).toEqual({ parar: true, avisos: 1 })
  })

  it("o 200 e o 500 nao avisam nem mandam parar", async () => {
    expect(await comStatus(200)).toEqual({ parar: false, avisos: 0 })
    expect(await comStatus(500)).toEqual({ parar: false, avisos: 0 })
  })
})

describe("a leitura da recusa", () => {
  it("le o corpo no formato da API", () => {
    expect(lerRecusa({ erros: { asn: "ASN ja usado" }, avisos: [] })).toEqual({
      erros: { asn: "ASN ja usado" }, avisos: [],
    })
  })

  it("corpo fora do formato vira erro de corpo", () => {
    const r = lerRecusa({ detail: "Not Found" })
    expect(Object.keys(r.erros)).toEqual(["_corpo"])
  })

  it("corpo nulo nao estoura", () => {
    expect(lerRecusa(null).erros._corpo).toBeDefined()
  })
})
