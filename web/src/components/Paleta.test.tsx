import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import { Provedores } from "@/app/provedores"
import { Paleta } from "./Paleta"

const PEERS = [
  { id: 1, token: "268127", tipo: "cliente", asn: 268127, apelido: "", nome: "Cliente ACME", grupo_id: null },
  { id: 2, token: "BRDIGITAL", tipo: "upstream", asn: 14840, apelido: "BRDIGITAL", nome: "BRDIGITAL-20G", grupo_id: null },
]
const GRUPOS = [{ id: 9, nome: "PARCEIROS", tipo: "parceiro", membros: 4 }]

// A paleta navega pelo `navigate`, e nao por <Link>: o CommandItem e do cmdk e
// nao tem composicao. As rotas de destino existem aqui para o teste provar que
// a navegacao acontece, e nao so que o item foi clicado.
function montar(extras = {}) {
  const props = {
    aberta: true, aoFechar: vi.fn(), peers: PEERS, grupos: GRUPOS,
    aoDuplicar: undefined, aoCopiarBloco: undefined, ...extras,
  }
  return render(
    <MemoryRouter initialEntries={["/peers"]}>
      <Provedores>
        <Routes>
          <Route path="/peers" element={<Paleta {...props} />} />
          <Route path="/peers/novo" element={<p>peer novo</p>} />
          <Route path="/peers/:id" element={<p>peer aberto</p>} />
          <Route path="/grupos/novo" element={<p>grupo novo</p>} />
          <Route path="/grupos/:id" element={<p>grupo aberto</p>} />
        </Routes>
      </Provedores>
    </MemoryRouter>,
  )
}

describe("a paleta de comandos", () => {
  it("leva a qualquer peer e a qualquer grupo", async () => {
    montar()
    await userEvent.click(screen.getByText("Cliente ACME"))
    expect(await screen.findByText("peer aberto")).toBeInTheDocument()
  })

  it("lista as acoes de criar", async () => {
    montar()
    expect(screen.getByText(/novo peer cliente/)).toBeInTheDocument()
    // um item por tipo de grupo: `getByText(/novo grupo/)` casaria os cinco e
    // estouraria com "found multiple elements"
    expect(screen.getByText(/novo grupo upstream/)).toBeInTheDocument()
    expect(screen.getAllByText(/novo grupo/)).toHaveLength(5)
  })

  it("filtra pelo que o operador digita", async () => {
    montar()
    await userEvent.type(screen.getByPlaceholderText(/buscar/i), "brdigital")
    // o rotulo do item e o apelido, como na barra lateral; o nome do cadastro
    // entra no `value`, que e o que a busca le
    expect(screen.getByText("BRDIGITAL")).toBeInTheDocument()
    expect(screen.queryByText("Cliente ACME")).not.toBeInTheDocument()
  })

  it("so oferece duplicar e copiar quando a tela aberta tem o que duplicar", async () => {
    montar({ aoDuplicar: vi.fn(), aoCopiarBloco: vi.fn() })
    expect(screen.getByText(/duplicar/)).toBeInTheDocument()
    expect(screen.getByText(/copiar o bloco/)).toBeInTheDocument()
  })

  it("sem registro aberto, as duas acoes nao aparecem", () => {
    montar()
    expect(screen.queryByText(/duplicar/)).not.toBeInTheDocument()
  })

  it("a acao de baixar o bloco base chega na casca", async () => {
    // quem busca o /base.txt e o baixa e a Casca; a paleta so dispara a acao
    const baixar = vi.fn()
    montar({ aoBaixarBase: baixar })
    await userEvent.click(screen.getByText(/baixar o bloco base/))
    expect(baixar).toHaveBeenCalled()
  })

  it("o tema se troca pela paleta", async () => {
    montar()
    await userEvent.click(screen.getByText(/tema escuro/i))
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })

  it("Esc fecha", async () => {
    const aoFechar = vi.fn()
    montar({ aoFechar })
    await userEvent.keyboard("{Escape}")
    expect(aoFechar).toHaveBeenCalled()
  })
})
