import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { montarRota, mockFetch, peticoes } from "@/teste/roteador"
import { LoginTela } from "./LoginTela"

const ROTAS = [
  { path: "/login", element: <LoginTela /> },
  { path: "/peers", element: <h1>a casca</h1> },
]

describe("a tela de login", () => {
  it("com a senha errada mostra a mensagem e nao sai da tela", async () => {
    mockFetch({
      "POST /api/login": {
        status: 401,
        corpo: { erros: { _: "usuario ou senha invalidos" }, avisos: [] },
      },
    })
    montarRota(ROTAS, "/login")

    await userEvent.type(screen.getByLabelText("Senha"), "chute")
    await userEvent.click(screen.getByRole("button", { name: /^entrar$/ }))

    expect(await screen.findByRole("alert")).toHaveTextContent("usuario ou senha invalidos")
    // a senha digitada fica: quem errou uma tecla nao digita tudo de novo
    expect(screen.getByLabelText("Senha")).toHaveValue("chute")
  })

  it("com a senha certa vai para os peers", async () => {
    mockFetch({
      "POST /api/login": { corpo: { logado: true, usuario: "admin" } },
      "GET /api/sessao": { corpo: { logado: true, usuario: "admin" } },
    })
    montarRota(ROTAS, "/login")

    await userEvent.type(screen.getByLabelText("Senha"), "certa")
    await userEvent.click(screen.getByRole("button", { name: /^entrar$/ }))

    await screen.findByText("a casca")
    const pedido = peticoes().find((p) => p.caminho === "/api/login")
    expect(pedido?.corpo).toEqual({ usuario: "admin", senha: "certa" })
  })
})
