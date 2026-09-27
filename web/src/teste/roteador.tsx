import { render } from "@testing-library/react"
import { RouterProvider, createMemoryRouter, type RouteObject } from "react-router-dom"
import { vi } from "vitest"
import { Provedores } from "@/app/provedores"

/** Monta o app com rotas de verdade: o AvisoNaoSalvo depende do data router. */
export function montarRota(rotas: RouteObject[], inicial = "/") {
  const roteador = createMemoryRouter(rotas, { initialEntries: [inicial] })
  return render(
    <Provedores>
      <RouterProvider router={roteador} />
    </Provedores>,
  )
}

export type Resposta = { status?: number; corpo: unknown }

/**
 * Um fetch de mentira por metodo e caminho, com a query string fora da chave.
 * O openapi-fetch chama `fetch(request)`, com o pedido ja montado: o metodo e o
 * caminho vem do proprio Request, e nao de um segundo argumento.
 */
export function mockFetch(mapa: Record<string, Resposta>) {
  return vi.stubGlobal("fetch", (entrada: Request) => {
    const chave = `${entrada.method} ${String(entrada.url).split("?")[0]}`
    const achado = mapa[chave]
    if (!achado) return Promise.resolve(new Response("{}", { status: 404 }))
    return Promise.resolve(
      new Response(JSON.stringify(achado.corpo), {
        status: achado.status ?? 200,
        headers: { "content-type": "application/json" },
      }),
    )
  })
}
