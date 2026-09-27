import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { usePrevia } from "./previa"

const BRANCO = { id: "7", nome: "ACME", tipo: "cliente" }

function montar(inicial: unknown, ligado = true) {
  const consultas = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const envolver = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={consultas}>{children}</QueryClientProvider>
  )
  return renderHook(
    ({ valores, ligado: aberto }: { valores: unknown; ligado: boolean }) =>
      usePrevia({ tipo: "peers", id: 7, valores: valores as never, ligado: aberto }),
    { wrapper: envolver, initialProps: { valores: inicial, ligado } },
  )
}

function comFetch(pedidos: string[]) {
  vi.stubGlobal("fetch", (url: string) => {
    pedidos.push(String(url))
    return Promise.resolve(
      new Response(JSON.stringify({ bloco: "x", arquivo: "a.txt" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    )
  })
}

// A mesma coisa, guardando o corpo: o duble do Request do setup guarda o body,
// e e por ele que se ve QUAL formulario foi pedido, e nao so quantos pedidos
function comFetchCorpo(corpos: string[]) {
  vi.stubGlobal("fetch", (entrada: Request) => {
    corpos.push(String((entrada as unknown as { body: string }).body))
    return Promise.resolve(
      new Response(JSON.stringify({ bloco: "x", arquivo: "a.txt" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    )
  })
}

beforeEach(() => vi.useFakeTimers())
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("a previa ao vivo", () => {
  it("nao pede nada antes do atraso de 400ms", async () => {
    const pedidos: string[] = []
    comFetch(pedidos)
    montar(BRANCO)
    await act(async () => { await vi.advanceTimersByTimeAsync(200) })
    expect(pedidos).toHaveLength(0)
    await act(async () => { await vi.advanceTimersByTimeAsync(300) })
    expect(pedidos).toHaveLength(1)
  })

  it("duas alteracoes dentro da janela viram um pedido so", async () => {
    const corpos: string[] = []
    comFetchCorpo(corpos)
    const { rerender } = montar(BRANCO)
    rerender({ valores: { ...BRANCO, nome: "ACME 2" }, ligado: true })
    await act(async () => { await vi.advanceTimersByTimeAsync(200) })
    rerender({ valores: { ...BRANCO, nome: "ACME 3" }, ligado: true })
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(corpos).toHaveLength(1)
    // o corpo e quem diz que a janela foi REARMADA, e nao so que saiu um pedido:
    // com um relogio armado uma vez so, o pedido levaria o valor da primeira
    // alteracao ("ACME 2") no lugar do ultimo
    expect(JSON.parse(corpos[0])).toMatchObject({ nome: "ACME 3" })
  })

  it("nao comeca a janela antes de o registro chegar", async () => {
    // sem a guarda do ligado na janela, o relogio correria na montagem, com o
    // formulario em branco: um registro que demore mais que os 400ms faria a
    // primeira previa sair com o peer vazio, e o painel mostraria aquele bloco
    const corpos: string[] = []
    comFetchCorpo(corpos)
    const { rerender } = montar(BRANCO, false)
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(corpos).toHaveLength(0)
    // o registro chega e os valores dele entram: a janela corre a partir daqui
    rerender({ valores: { ...BRANCO, nome: "ACME CARREGADO" }, ligado: true })
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(corpos).toHaveLength(1)
    expect(JSON.parse(corpos[0])).toMatchObject({ nome: "ACME CARREGADO" })
  })
})
