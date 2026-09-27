import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { usePrevia } from "./previa"

const BRANCO = { id: "7", nome: "ACME", tipo: "cliente" }

function montar(inicial: unknown) {
  const consultas = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const envolver = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={consultas}>{children}</QueryClientProvider>
  )
  return renderHook(
    ({ valores }: { valores: unknown }) =>
      usePrevia({ tipo: "peers", id: 7, valores: valores as never, ligado: true }),
    { wrapper: envolver, initialProps: { valores: inicial } },
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
    const pedidos: string[] = []
    comFetch(pedidos)
    const { rerender } = montar(BRANCO)
    rerender({ valores: { ...BRANCO, nome: "ACME 2" } })
    await act(async () => { await vi.advanceTimersByTimeAsync(200) })
    rerender({ valores: { ...BRANCO, nome: "ACME 3" } })
    await act(async () => { await vi.advanceTimersByTimeAsync(500) })
    expect(pedidos).toHaveLength(1)
  })
})
