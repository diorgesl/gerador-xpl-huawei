import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { montarRota } from "@/teste/roteador"
import { Inicio } from "./Inicio"

// A tela nao pede nada a API: ela so diz o que fazer. O `montarRota` entra aqui
// porque o que a prova fixa e a rota que a monta, e nao o componente solto.
describe("a tela de chegada", () => {
  it("convida a escolher um peer quando nada esta aberto", () => {
    montarRota([{ path: "/peers", element: <Inicio oQue="peer" /> }], "/peers")
    expect(screen.getByText(/escolha um peer ou crie um/)).toBeInTheDocument()
  })

  it("fala de grupo na rota dos grupos", () => {
    montarRota([{ path: "/grupos", element: <Inicio oQue="grupo" /> }], "/grupos")
    expect(screen.getByText(/escolha um grupo ou crie um/)).toBeInTheDocument()
  })

  it("nao oferece um segundo botao de criar", () => {
    // o "+ novo" da barra e o unico: um botao aqui deixaria ambigua a busca do
    // e2e por "novo", que roda contra a tela inteira
    montarRota([{ path: "/peers", element: <Inicio oQue="peer" /> }], "/peers")
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })
})
