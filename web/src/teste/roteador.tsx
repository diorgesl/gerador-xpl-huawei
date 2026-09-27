import { render } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { RouterProvider, createMemoryRouter, type RouteObject } from "react-router-dom"
import { afterEach, beforeEach, vi } from "vitest"
import { Provedores } from "@/app/provedores"

/** Um pedido que o fetch de mentira atendeu, ja na forma que a prova le. */
export type Pedido = {
  metodo: string
  caminho: string
  query: string
  corpo: unknown
}

export type Resposta = { status?: number; corpo: unknown }

// O que o fetch de mentira viu fica no modulo, e nao no fechamento de cada
// `mockFetch`, porque quem limpa e quem acusa sao os dois ganchos abaixo,
// registrados uma vez por arquivo quando este modulo carrega
let vistos: Pedido[] = []
let semMapa: string[] = []

/** Os pedidos atendidos desde o comeco do caso, na ordem em que chegaram. */
export function peticoes(): Pedido[] {
  return [...vistos]
}

beforeEach(() => {
  vistos = []
  semMapa = []
})

afterEach(() => {
  vi.unstubAllGlobals()
  const faltando = semMapa
  semMapa = []
  // Uma rota fora do mapa devolvia 404 em silencio, e a tela lia aquilo como um
  // estado de verdade: a prova via a tela navegar embora e podia passar mesmo
  // assim. Agora ela acusa, e o nome da chave vem na mensagem
  if (faltando.length > 0) {
    throw new Error(`rota sem mapa no mockFetch: ${[...new Set(faltando)].join(", ")}`)
  }
})

/**
 * Monta o app com rotas de verdade: o AvisoNaoSalvo depende do data router.
 *
 * O QueryClient e de cada caso, e nao o do modulo: com um so, o caso seguinte
 * leria pela mesma chave o dado que o anterior deixou, e o `staleTime` de 5s
 * das consultas ainda estaria valendo.
 */
export function montarRota(rotas: RouteObject[], inicial = "/") {
  const consultas = new QueryClient({
    defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
  })
  const roteador = createMemoryRouter(rotas, { initialEntries: [inicial] })
  return render(
    <Provedores>
      <QueryClientProvider client={consultas}>
        <RouterProvider router={roteador} />
      </QueryClientProvider>
    </Provedores>,
  )
}

/**
 * Um fetch de mentira por metodo e caminho, com a query string fora da chave.
 * O openapi-fetch chama `fetch(request)`, com o pedido ja montado: o metodo e o
 * caminho vem do proprio Request, e nao de um segundo argumento. A casca pede
 * `/base.txt` com uma string, que e o outro formato que este duble entende.
 *
 * O que passou fica em `peticoes()`, com o corpo ja lido: e por ele que a prova
 * ve o que a tela mandou, e nao so quantos pedidos sairam.
 */
export function mockFetch(mapa: Record<string, Resposta>) {
  return vi.stubGlobal("fetch", (entrada: Request | string, init?: RequestInit) => {
    const pedido = lerPedido(entrada, init)
    vistos.push(pedido)
    const chave = `${pedido.metodo} ${pedido.caminho}`
    const achado = mapa[chave]
    if (!achado) {
      semMapa.push(chave)
      return Promise.resolve(new Response("{}", { status: 404 }))
    }
    const status = achado.status ?? 200
    // 204 e companhia nao podem ter corpo: o construtor do Response recusa
    // qualquer coisa ali, inclusive a string "null" de um corpo nulo
    const semCorpo = status === 204 || status === 205 || status === 304
    return Promise.resolve(
      new Response(semCorpo ? null : JSON.stringify(achado.corpo), {
        status,
        headers: { "content-type": "application/json" },
      }),
    )
  })
}

function lerPedido(entrada: Request | string, init?: RequestInit): Pedido {
  if (typeof entrada === "string") {
    const [caminho, query = ""] = entrada.split("?")
    return { metodo: init?.method ?? "GET", caminho, query, corpo: corpoLido(init?.body) }
  }
  const [caminho, query = ""] = String(entrada.url).split("?")
  // O tipo do DOM diz que o corpo do Request e um ReadableStream; o duble do
  // setup guarda o valor cru com que o pedido foi montado, e o cast e o que le
  // o que ele tem de verdade
  const bruto = (entrada as unknown as { body?: unknown }).body
  return { metodo: entrada.method, caminho, query, corpo: corpoLido(bruto) }
}

function corpoLido(bruto: unknown): unknown {
  if (typeof bruto !== "string") return bruto ?? null
  try {
    return JSON.parse(bruto)
  } catch {
    return bruto
  }
}
