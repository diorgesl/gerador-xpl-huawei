import { screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { montarRota } from "@/teste/roteador"
import { BaseTela } from "./BaseTela"

const BASE_TXT = "# bloco base: sets e filtros compartilhados\nxpl community-list CL-NOADV\nerror: 10.0.0.0/8 le 32\nend-list"

afterEach(() => vi.unstubAllGlobals())

// o /base.txt e texto puro, e nao JSON: o mockFetch do arnes nao serve aqui
function comBaseTxt() {
  vi.stubGlobal("fetch", () =>
    Promise.resolve(new Response(BASE_TXT, { status: 200, headers: { "content-type": "text/plain" } })),
  )
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
    const chamadas = vi.fn(() => Promise.resolve(new Response("falhou", { status: 500 })))
    vi.stubGlobal("fetch", chamadas)
    montarRota([{ path: "/base", element: <BaseTela /> }], "/base")
    // A espera e a segunda chamada, o retry do cliente (um, com o atraso padrao
    // de 1s), e nao o padrao de 1s do waitFor: sem ela o caso mediria o
    // carregando, em que o botao ja esta desabilitado pela mesma guarda
    await waitFor(() => expect(chamadas).toHaveBeenCalledTimes(2), { timeout: 3000 })
    expect(screen.getByRole("button", { name: /^copiar$/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /^baixar$/i })).toBeDisabled()
  })
})
