import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { BarraLateral } from "./BarraLateral"
import { filtrarGrupos, filtrarPeers } from "@/lib/busca"

const PEERS = [
  { id: 1, token: "268127", tipo: "cliente", asn: 268127, apelido: "", nome: "Cliente ACME", grupo_id: null },
  { id: 2, token: "BRDIGITAL", tipo: "upstream", asn: 14840, apelido: "BRDIGITAL", nome: "BRDIGITAL-20G", grupo_id: null },
  { id: 3, token: "IX-SP", tipo: "ix", asn: 26162, apelido: "IX-SP", nome: "IX.br Sao Paulo", grupo_id: 9 },
]
const GRUPOS = [{ id: 9, nome: "PARCEIROS", tipo: "parceiro", membros: 4 }]

describe("o filtro da busca", () => {
  it("sem termo, devolve tudo", () => {
    expect(filtrarPeers(PEERS, "  ")).toHaveLength(3)
  })

  it("casa por ASN, apelido, nome e tipo", () => {
    expect(filtrarPeers(PEERS, "14840").map((p) => p.id)).toEqual([2])
    expect(filtrarPeers(PEERS, "brdigital").map((p) => p.id)).toEqual([2])
    expect(filtrarPeers(PEERS, "acme").map((p) => p.id)).toEqual([1])
    expect(filtrarPeers(PEERS, "ix").map((p) => p.id)).toEqual([3])
  })

  it("sem resultado devolve vazio, e nao tudo", () => {
    expect(filtrarPeers(PEERS, "nao existe")).toEqual([])
  })

  it("vale para o grupo pelo nome e pelo tipo", () => {
    expect(filtrarGrupos(GRUPOS, "parceiros")).toHaveLength(1)
    expect(filtrarGrupos(GRUPOS, "upstream")).toHaveLength(0)
  })
})

describe("a barra lateral", () => {
  const montar = (props = {}) =>
    render(
      <MemoryRouter>
        <BarraLateral peers={PEERS} grupos={GRUPOS} asn="64512" aoNovo={vi.fn()} {...props} />
      </MemoryRouter>,
    )

  it("mostra as secoes, os links e o AS da rede", () => {
    montar()
    // as duas listas sao titulo, nao link: o nome do link de um peer e o
    // apelido dele, e o de um grupo e o nome mais a contagem de membros
    for (const titulo of ["Peers", "Grupos", "Política"]) {
      expect(screen.getByRole("heading", { name: titulo })).toBeInTheDocument()
    }
    for (const rotulo of ["Prefixos próprios", "Bloco base", "Configurações"]) {
      expect(screen.getByRole("link", { name: rotulo })).toBeInTheDocument()
    }
    expect(screen.getByText("AS64512")).toBeInTheDocument()
  })

  it("mostra o tipo em badge e a contagem de membros do grupo", () => {
    montar()
    expect(screen.getAllByText("cliente").length).toBeGreaterThan(0)
    expect(screen.getByText("4")).toBeInTheDocument()
  })

  it("a busca esconde o que nao casa", async () => {
    montar()
    await userEvent.type(screen.getByRole("searchbox"), "acme")
    expect(screen.getByRole("link", { name: /Cliente ACME/ })).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /BRDIGITAL-20G/ })).not.toBeInTheDocument()
  })
})
