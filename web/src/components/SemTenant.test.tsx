import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { mockFetch, montarRota, type Resposta } from "@/teste/roteador"
import { Casca } from "@/app/casca"

const rotas = [
  { path: "/", element: <Casca />, children: [{ path: "peers", element: <p>lista de peers</p> }] },
]

/**
 * Segura a proxima leitura da chave ate o caso mandar soltar, e repassa o
 * resto ao arnes: e a janela em que a casca esta sem a lista e sem a falha
 * dela, que e justamente onde o estado vazio nao pode aparecer.
 */
function segurarProximaLeitura(chave: string) {
  const doArnes = globalThis.fetch
  let liberar: () => void = () => {}
  const espera = new Promise<void>((resolve) => { liberar = resolve })
  let jaSegurou = false
  vi.stubGlobal("fetch", async (entrada: Request, init?: RequestInit) => {
    if (!jaSegurou && `${entrada.method} ${String(entrada.url).split("?")[0]}` === chave) {
      jaSegurou = true
      await espera
    }
    return doArnes(entrada, init)
  })
  return () => liberar()
}

describe("a casca sem nenhum tenant", () => {
  beforeEach(() => window.sessionStorage.clear())

  it("explica a pasta vazia e oferece criar o primeiro", async () => {
    mockFetch({ "GET /api/asns": { corpo: [] } })
    montarRota(rotas, "/peers")

    expect(await screen.findByRole("heading", { name: /nenhuma rede cadastrada/i }))
      .toBeInTheDocument()
    // o caminho do checkout na tela: e a pasta de onde a lista sai, e quem
    // preferir resolver pelo terminal precisa dele
    expect(screen.getByText("peers/")).toBeInTheDocument()
    expect(screen.getByText("peers/64512.yaml")).toBeInTheDocument()
    // nao ha tela de peer neste estado: sem tenant nao ha o que listar
    expect(screen.queryByText("lista de peers")).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: /criar o primeiro ASN/i }))
    // o mesmo dialogo do seletor, com os dois campos que a recusa da API usa
    expect(await screen.findByLabelText(/AS da rede/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Namespace das standard/i)).toBeInTheDocument()
  })

  it("a lista fora do ar avisa com tentar de novo, e nao o estado vazio", async () => {
    // O nulo do `asn` e o mesmo nos dois casos, e a consulta de dados se
    // desabilita nos dois: sem separar, a queda da unica rota que sustenta as
    // outras ficava invisivel, com a cara de instalacao nova
    const respostas: Record<string, Resposta> = { "GET /api/asns": { status: 500, corpo: {} } }
    mockFetch(respostas)
    montarRota(rotas, "/peers")

    // o aviso so aparece depois de a consulta gastar o retry do cliente (um,
    // com o atraso padrao de 1s), que e o mesmo do app
    expect(await screen.findByText("não deu para falar com a API", {}, { timeout: 3000 }))
      .toBeInTheDocument()
    expect(screen.queryByText(/nenhuma rede cadastrada/i)).not.toBeInTheDocument()

    // a API volta, vazia: a resposta e segurada para o caso ver a janela do
    // refetch, que e onde o TanStack zera o `error` da consulta sem dado
    respostas["GET /api/asns"] = { corpo: [] }
    const soltar = segurarProximaLeitura("GET /api/asns")
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))

    // enquanto a resposta nao chega, o aviso fica de pe e o botao espera: o
    // estado vazio aqui seria a mesma mentira por outro caminho
    expect(screen.queryByText(/nenhuma rede cadastrada/i)).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: /tentar de novo/i })).toBeDisabled()

    soltar()
    expect(await screen.findByRole("heading", { name: /nenhuma rede cadastrada/i }))
      .toBeInTheDocument()
  })
})
