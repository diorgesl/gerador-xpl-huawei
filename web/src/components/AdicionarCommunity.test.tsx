import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { AdicionarCommunity } from "./AdicionarCommunity"

const SUGESTOES = [
  { valor: "64512:204", rotulo: "Não anunciar para os nossos outros clientes", grupo: "Anúncio" },
  { valor: "64512:613", rotulo: "Prepend 2x para os nossos upstreams", grupo: "Prepend" },
  { valor: "64512:5023", rotulo: "Prepend 2x (AS53062, identificador 02)", grupo: "Por upstream" },
]

function montar(props: Partial<Parameters<typeof AdicionarCommunity>[0]> = {}) {
  return render(
    <AdicionarCommunity sugestoes={SUGESTOES} jaUsadas={[]} aoAdicionar={vi.fn()} {...props} />,
  )
}

async function abrirEEscrever(texto: string) {
  await userEvent.click(screen.getByRole("button", { name: /adicionar/i }))
  await userEvent.type(screen.getByPlaceholderText(/buscar/i), texto)
}

describe("a busca de communities", () => {
  it("filtra pelo rotulo e o clique insere o valor", async () => {
    // o caso de uso que motivou a tela: o operador sabe que quer um
    // prepend e nao sabe de cor qual digito e qual classe
    const aoAdicionar = vi.fn()
    montar({ aoAdicionar })

    await abrirEEscrever("prepend")

    await userEvent.click(await screen.findByRole("option", { name: /identificador 02/ }))
    expect(aoAdicionar).toHaveBeenCalledWith("64512:5023")
  })

  it("acha pelo numero, e nao so pelo texto", async () => {
    const aoAdicionar = vi.fn()
    montar({ aoAdicionar })

    await abrirEEscrever("64512:204")

    await userEvent.click(await screen.findByRole("option", { name: /outros clientes/ }))
    expect(aoAdicionar).toHaveBeenCalledWith("64512:204")
  })

  it("esconde o que ja esta no campo", async () => {
    // oferecer de novo o que ja esta la convida a duplicar a linha, e a
    // lista do campo vira uma repeticao que o operador nao pediu
    montar({ jaUsadas: ["64512:613"] })

    await abrirEEscrever("prepend")

    expect(await screen.findByRole("option", { name: /identificador 02/ })).toBeInTheDocument()
    expect(screen.queryByRole("option", { name: /nossos upstreams/ })).not.toBeInTheDocument()
  })

  it("nomeia o botao com o campo, para os dois nao ficarem iguais", async () => {
    // a tela do peer tem duas listas, uma por campo: sem o nome do campo no
    // rotulo, os dois botoes chegam ao leitor de tela como "adicionar
    // community", sem dizer qual e qual
    montar({ rotulo: "large-communities" })
    expect(screen.getByRole("button", { name: "adicionar large-communities" })).toBeInTheDocument()
  })

  it("sem resultado, diz que nao achou", async () => {
    montar()

    await abrirEEscrever("nao existe isso")

    expect(await screen.findByText(/nenhuma community/i)).toBeInTheDocument()
  })
})
