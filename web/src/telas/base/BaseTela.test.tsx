import { fireEvent, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { quandoPerderSessao } from "@/api/cliente"
import { montarRota } from "@/teste/roteador"
import { BaseTela } from "./BaseTela"

const BASE_TXT = "# bloco base: sets e filtros compartilhados\nxpl community-list CL-NOADV\nerror: 10.0.0.0/8 le 32\nend-list"

afterEach(() => vi.unstubAllGlobals())

// o /base.txt e texto puro, e nao JSON: o mockFetch do arnes nao serve aqui.
//
// O provedor de tenant pergunta a lista de ASNs em toda montagem, e pelo mesmo
// fetch global: quem responde por ela e este duble, com a mesma lista ambiente
// do arnes. Na conta entram so as chamadas do /base.txt - sem essa separacao o
// retry do provedor apareceria no meio dela e o caso mediria o pedido errado
function comFetch(resposta: () => Response) {
  const chamadas: string[] = []
  vi.stubGlobal("fetch", (entrada: Request | string) => {
    const url = typeof entrada === "string" ? entrada : entrada.url
    if (url.startsWith("/api/asns")) {
      return Promise.resolve(
        new Response(JSON.stringify(["64512"]), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      )
    }
    chamadas.push(url)
    return Promise.resolve(resposta())
  })
  return chamadas
}

function comBaseTxt() {
  return comFetch(() =>
    new Response(BASE_TXT, { status: 200, headers: { "content-type": "text/plain" } }))
}

describe("a tela do bloco base", () => {
  it("mostra o texto do /base.txt com destaque", async () => {
    comBaseTxt()
    montarRota([{ path: "/base", element: <BaseTela /> }], "/base")
    expect(await screen.findByText(/CL-NOADV/)).toBeInTheDocument()
    expect(document.querySelector(".tk-comentario")).toBeTruthy()
    expect(document.querySelector(".tk-objeto")).toBeTruthy()
  })

  it("explica a ordem de colagem", async () => {
    comBaseTxt()
    montarRota([{ path: "/base", element: <BaseTela /> }], "/base")
    expect(await screen.findByText(/bloco base primeiro/i)).toBeInTheDocument()
  })

  it("nao oferece copiar nem baixar antes de o texto chegar", async () => {
    // com o /base.txt fora do ar nao ha o que copiar nem o que baixar, e o
    // botao sem guarda salvaria um base.txt vazio com o nome do bloco (a Casca
    // ja evita isso no "baixar o bloco base" da paleta)
    const chamadas = comFetch(() => new Response("falhou", { status: 500 }))
    montarRota([{ path: "/base", element: <BaseTela /> }], "/base")
    // A espera e a segunda chamada, o retry do cliente (um, com o atraso padrao
    // de 1s), e nao o padrao de 1s do waitFor: sem ela o caso mediria o
    // carregando, em que o botao ja esta desabilitado pela mesma guarda
    await waitFor(() => expect(chamadas).toHaveLength(2), { timeout: 3000 })
    expect(screen.getByRole("button", { name: /^copiar$/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /^baixar$/i })).toBeDisabled()
  })

  it("a falha do /base.txt sai acima do painel, com o tentar de novo", async () => {
    // a tela nao troca o corpo pelo aviso como o peer e o grupo fazem: o titulo
    // e o paragrafo da ordem servem mesmo com o /base.txt fora do ar, entao o
    // aviso entra acima do painel e o resto da tela fica
    const chamadas = comFetch(() => new Response("falhou", { status: 500 }))
    montarRota([{ path: "/base", element: <BaseTela /> }], "/base")
    // a espera e a segunda chamada, o retry do cliente: sem ela o caso mediria
    // o carregando, em que nao ha falha nenhuma para mostrar
    await waitFor(() => expect(chamadas).toHaveLength(2), { timeout: 3000 })
    expect(screen.getByText("não deu para falar com a API")).toBeInTheDocument()
    expect(screen.getByText(/bloco base primeiro/i)).toBeInTheDocument()
    const tentar = screen.getByRole("button", { name: /tentar de novo/i })
    fireEvent.click(tentar)
    await waitFor(() => expect(chamadas.length).toBeGreaterThan(2), { timeout: 3000 })
  })

  it("o 401 no /base.txt avisa que a sessao caiu", async () => {
    // sem o aviso, a sessao vencida viraria "nao deu para falar com a API" e
    // um tentar de novo que nunca passa, sem caminho para a tela de login
    comFetch(() => new Response("", { status: 401 }))
    let avisos = 0
    quandoPerderSessao(() => { avisos += 1 })
    montarRota([{ path: "/base", element: <BaseTela /> }], "/base")

    await waitFor(() => expect(avisos).toBe(1))
  })
})
