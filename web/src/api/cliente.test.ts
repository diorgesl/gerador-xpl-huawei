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
