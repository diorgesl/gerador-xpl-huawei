import { useState } from "react"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { mockFetch, montarRota, peticoes, type Resposta } from "@/teste/roteador"
import { Casca } from "@/app/casca"
import { useTenant } from "@/app/tenant"

/** A tela com estado proprio, como um formulario de rascunho. */
function Rascunho() {
  const { asn } = useTenant()
  const [texto, setTexto] = useState("")
  return (
    <div>
      <p>tela da rede {asn}</p>
      <label>
        rascunho
        <input value={texto} onChange={(e) => setTexto(e.target.value)} />
      </label>
    </div>
  )
}

const rotas = [
  {
    path: "/",
    element: <Casca />,
    children: [
      { path: "peers", element: <p>lista de peers</p> },
      { path: "peers/:id", element: <p>peer aberto</p> },
      { path: "prefixos", element: <Rascunho /> },
    ],
  },
]

// O que a casca pergunta em toda rota: os grupos e os peers do tenant, e a
// lista que o seletor desenha
const mapa = (): Record<string, Resposta> => ({
  "GET /api/asns": { corpo: ["64512", "264130"] },
  "GET /api/peers": { corpo: [] },
  "GET /api/grupos": { corpo: [] },
})

describe("o seletor de ASN", () => {
  beforeEach(() => window.sessionStorage.clear())

  it("troca de tenant e leva para a lista", async () => {
    // /peers/1 e um registro do tenant antigo: do outro lado ele nao existe,
    // ou e outro peer, entao a troca tem que sair da tela dele
    mockFetch(mapa())
    montarRota(rotas, "/peers/1")
    expect(await screen.findByText("peer aberto")).toBeInTheDocument()

    await userEvent.click(await screen.findByRole("button", { name: "AS64512" }))
    await userEvent.click(await screen.findByRole("menuitem", { name: "AS264130" }))

    expect(await screen.findByText("lista de peers")).toBeInTheDocument()
    // o seletor passa a mostrar a rede nova, e nao so a rota mudou
    expect(await screen.findByText("AS264130")).toBeInTheDocument()
    // e a consulta de dados seguinte ja e a do tenant escolhido
    await waitFor(
      () => expect(peticoes().some(
        (p) => p.caminho === "/api/peers" && p.query.includes("asn=264130"))).toBe(true),
    )
  })

  it("a troca remonta a tela, e o rascunho da rede anterior nao a segue", async () => {
    // O estado dos formularios nao e indexado pelo ASN: sem a chave na
    // Outlet, quem estivesse com um rascunho aberto continuaria com ele na
    // tela nova, e o primeiro salvar mandaria o texto de uma rede com o
    // `?asn=` da outra
    mockFetch(mapa())
    montarRota(rotas, "/prefixos")
    expect(await screen.findByText("tela da rede 64512")).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText("rascunho"), "texto da rede A")

    await userEvent.click(screen.getByRole("button", { name: "AS64512" }))
    await userEvent.click(await screen.findByRole("menuitem", { name: "AS264130" }))

    expect(await screen.findByText("tela da rede 264130")).toBeInTheDocument()
    expect(screen.getByLabelText("rascunho")).toHaveValue("")
  })

  it("criar um ASN novo ja o seleciona", async () => {
    const respostas = mapa()
    respostas["GET /api/asns"] = { corpo: ["64512"] }
    respostas["POST /api/asns"] = { status: 201, corpo: ["64512", "64513"] }
    mockFetch(respostas)
    // O POST cria: a lista seguinte ja traz o ASN novo, que e o que o servidor
    // devolve. E por ela que o seletor troca, e nao pelo que foi digitado
    const doArnes = globalThis.fetch
    vi.stubGlobal("fetch", (entrada: Request, init?: RequestInit) => {
      if (entrada.method === "POST") respostas["GET /api/asns"] = { corpo: ["64512", "64513"] }
      return doArnes(entrada, init)
    })
    montarRota(rotas, "/peers")
    await screen.findByText("lista de peers")

    await userEvent.click(screen.getByRole("button", { name: "AS64512" }))
    await userEvent.click(await screen.findByRole("menuitem", { name: "novo ASN" }))
    await userEvent.type(await screen.findByLabelText(/AS da rede/i), "64513")
    await userEvent.click(screen.getByRole("button", { name: "criar" }))

    await waitFor(() => expect(peticoes().some(
      (p) => p.caminho === "/api/asns" && p.metodo === "POST")).toBe(true))
    // o par inteiro vai no corpo, com os nomes curtos que a rota espera
    expect(peticoes().find((p) => p.caminho === "/api/asns" && p.metodo === "POST")?.corpo)
      .toEqual({ asn: "64513", politica: "" })
    // e a tela ja esta na rede criada
    expect(await screen.findByText("AS64513")).toBeInTheDocument()
  })

  it("o ASN sem cadastro recusa e mostra o erro no campo", async () => {
    const respostas = mapa()
    respostas["GET /api/asns"] = { corpo: ["64512"] }
    respostas["POST /api/asns"] = {
      status: 422,
      corpo: { erros: { asn_rede: "o ASN 64512 ja tem cadastro" }, avisos: [] },
    }
    mockFetch(respostas)
    montarRota(rotas, "/peers")
    await screen.findByText("lista de peers")

    await userEvent.click(screen.getByRole("button", { name: "AS64512" }))
    await userEvent.click(await screen.findByRole("menuitem", { name: "novo ASN" }))
    await userEvent.type(await screen.findByLabelText(/AS da rede/i), "64512")
    await userEvent.click(screen.getByRole("button", { name: "criar" }))

    // o nome do campo e o que faz a recusa aparecer: com outro `nome`, o 422
    // voltava sem pintar nada e o operador clicava de novo no mesmo botao
    const campo = (await screen.findByLabelText(/AS da rede/i)).closest("[data-campo]")
    expect(await screen.findByText("o ASN 64512 ja tem cadastro")).toBeInTheDocument()
    expect(campo).toContainElement(screen.getByRole("alert"))
    // a recusa nao fecha o dialogo nem limpa o que foi digitado
    expect(await screen.findByLabelText(/AS da rede/i)).toHaveValue("64512")
  })
})
