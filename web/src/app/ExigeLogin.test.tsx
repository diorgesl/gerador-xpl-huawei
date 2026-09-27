import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { ExigeLogin } from "./ExigeLogin"
import { montarRota, mockFetch } from "@/teste/roteador"

const ROTAS = [
  { path: "/login", element: <h1>a tela de login</h1> },
  {
    path: "/peers",
    element: (
      <ExigeLogin>
        <h1>a casca</h1>
      </ExigeLogin>
    ),
  },
]

describe("a guarda", () => {
  it("sem sessao leva para o login", async () => {
    mockFetch({ "GET /api/sessao": { corpo: { logado: false, usuario: null } } })
    montarRota(ROTAS, "/peers")

    await screen.findByText("a tela de login")
    // a casca nem chegou a montar: ela dispararia as consultas dela e
    // desenharia a barra lateral antes de o redirecionamento acontecer
    expect(screen.queryByText("a casca")).not.toBeInTheDocument()
  })

  it("com sessao desenha a casca", async () => {
    mockFetch({ "GET /api/sessao": { corpo: { logado: true, usuario: "admin" } } })
    montarRota(ROTAS, "/peers")

    await screen.findByText("a casca")
    expect(screen.queryByText("a tela de login")).not.toBeInTheDocument()
  })
})
