import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { BarraLateral } from "./BarraLateral"
import { filtrarGrupos, filtrarPeers } from "@/lib/busca"
import { montarRota, mockFetch, peticoes } from "@/teste/roteador"

const PEERS = [
  { id: 1, token: "268127", tipo: "cliente", asn: 268127, apelido: "", nome: "Cliente ACME", grupo_id: null },
  { id: 2, token: "BRDIGITAL", tipo: "upstream", asn: 14840, apelido: "BRDIGITAL", nome: "BRDIGITAL-20G", grupo_id: null },
  { id: 3, token: "IX-SP", tipo: "ix", asn: 26162, apelido: "IX-SP", nome: "IX.br Sao Paulo", grupo_id: 9 },
]
const GRUPOS = [{ id: 9, nome: "PARCEIROS", tipo: "parceiro", tabela: "nenhuma", membros: 4 }]

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
  // Quem monta e o arnes, e nao mais um MemoryRouter cru: a barra passou a
  // levar o seletor de ASN, que le o tenant do provedor e so sabe qual e
  // depois da lista do /api/asns - o `mockFetch` vazio entrega o ambiente do
  // arnes, que ja traz essa lista. A rota e um coringa porque o que se monta
  // aqui e a barra, que responde a qualquer endereco: o caco que ela le e o
  // `pathname`, e nao a rota
  const montar = (props = {}) => {
    mockFetch({})
    return montarRota([
      { path: "*", element: <BarraLateral peers={PEERS} grupos={GRUPOS} aoNovo={vi.fn()} {...props} /> },
    ])
  }

  it("mostra as secoes, os links e o AS da rede", async () => {
    montar()
    // as duas listas sao titulo, nao link: o nome do link de um peer e o
    // apelido dele, e o de um grupo e o nome mais a contagem de membros
    for (const titulo of ["Peers", "Grupos", "Política"]) {
      expect(screen.getByRole("heading", { name: titulo })).toBeInTheDocument()
    }
    for (const rotulo of ["Prefixos próprios", "Bloco base", "Config completa",
                          "Configurações"]) {
      expect(screen.getByRole("link", { name: rotulo })).toBeInTheDocument()
    }
    // o AS vem do contexto, que so o sabe depois da lista de ASNs
    expect(await screen.findByText("AS64512")).toBeInTheDocument()
  })

  it("mostra o tipo em badge e a contagem de membros do grupo", () => {
    montar()
    expect(screen.getAllByText("cliente").length).toBeGreaterThan(0)
    expect(screen.getByText("4")).toBeInTheDocument()
  })

  it("o item aceso e o do registro aberto, e nao o do id que comeca igual", () => {
    // `startsWith(para)` acendia /peers/1 em /peers/12: dois itens acesos, e o
    // errado era o do registro que o operador nao abriu. O que compara e o
    // segmento inteiro, e nao o prefixo do texto
    mockFetch({})
    montarRota(
      [{
        path: "*",
        element: (
          <BarraLateral
            peers={[...PEERS, { id: 12, token: "268999", tipo: "cliente", asn: 268999, apelido: "NOVO", nome: "Cliente NOVO", grupo_id: null }]}
            grupos={GRUPOS}
            aoNovo={vi.fn()}
          />
        ),
      }],
      "/peers/12",
    )
    const item = (destino: string) => screen.getAllByRole("link").find((l) => l.getAttribute("href") === destino)
    expect(item("/peers/12")).toHaveAttribute("aria-current", "page")
    expect(item("/peers/1")).not.toHaveAttribute("aria-current")
    expect(item("/grupos/9")).not.toHaveAttribute("aria-current")
  })

  it("o menu novo chama o destino de cada item", async () => {
    // o Item do Base UI dispara o clique pelo onClick: com o onSelect do Radix
    // (que o Base UI nao tem) o clique fechava o menu e nao chamava ninguem, e
    // nada acusava, porque o onSelect e prop valida no div
    const aoNovo = vi.fn()
    montar({ aoNovo })
    await userEvent.click(screen.getByRole("button", { name: /novo/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: "peer cliente" }))
    expect(aoNovo).toHaveBeenCalledWith("/peers/novo?tipo=cliente")
    await userEvent.click(screen.getByRole("button", { name: /novo/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: "grupo upstream" }))
    expect(aoNovo).toHaveBeenCalledWith("/grupos/novo?tipo=upstream")
  })

  it("o item do PDF baixa o documento do cliente", async () => {
    // o /politica-cliente.pdf e fetch cru, como o /base.txt: a rota nao esta
    // no cliente tipado, e o `?asn=` entra na mao
    const baixados: HTMLAnchorElement[] = []
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      baixados.push(this)
    })
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:pdf"), revokeObjectURL: vi.fn() })
    mockFetch({ "GET /politica-cliente.pdf": { binario: "%PDF-1.4" } })
    montarRota([
      { path: "*", element: <BarraLateral peers={PEERS} grupos={GRUPOS} aoNovo={vi.fn()} /> },
    ])

    await userEvent.click(screen.getByRole("button", { name: /política do cliente/i }))

    const pedido = peticoes().find((p) => p.caminho === "/politica-cliente.pdf")
    expect(pedido?.query).toBe("asn=64512")
    expect(baixados[0]?.download).toBe("politica-bgp-64512.pdf")
    vi.unstubAllGlobals()
  })

  it("a sessao vencida no PDF nao baixa uma folha de erro", async () => {
    // o mesmo cuidado do bloco base: sem a conferencia o operador salvaria a
    // resposta do servidor com o nome do documento, e entregaria aquilo ao
    // cliente
    const baixados: HTMLAnchorElement[] = []
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      baixados.push(this)
    })
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:pdf"), revokeObjectURL: vi.fn() })
    mockFetch({
      "GET /politica-cliente.pdf": {
        status: 401,
        corpo: { erros: { _: "sessao expirada ou ausente" }, avisos: [] },
      },
    })
    montarRota([
      { path: "*", element: <BarraLateral peers={PEERS} grupos={GRUPOS} aoNovo={vi.fn()} /> },
    ])

    await userEvent.click(screen.getByRole("button", { name: /política do cliente/i }))

    await vi.waitFor(() => expect(peticoes().some((p) => p.caminho === "/politica-cliente.pdf")).toBe(true))
    expect(baixados).toHaveLength(0)
    vi.unstubAllGlobals()
  })

  it("a busca esconde o que nao casa", async () => {
    montar()
    await userEvent.type(screen.getByRole("searchbox"), "acme")
    expect(screen.getByRole("link", { name: /Cliente ACME/ })).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /BRDIGITAL-20G/ })).not.toBeInTheDocument()
  })

  it("sair chama o logout e volta para o login", async () => {
    // o montar dos outros casos usa o MemoryRouter cru, e o useSair precisa do
    // QueryClient: aqui quem monta e o arnes, com a rota de destino de verdade
    mockFetch({ "POST /api/logout": { corpo: { logado: false, usuario: null } } })
    montarRota([
      { path: "/peers", element: <BarraLateral peers={[]} grupos={[]} aoNovo={() => {}} /> },
      { path: "/login", element: <h1>entrou na tela de login</h1> },
    ], "/peers")

    await userEvent.click(screen.getByRole("button", { name: /sair/i }))

    await screen.findByText("entrou na tela de login")
    const pedido = peticoes().find((p) => p.caminho === "/api/logout")
    expect(pedido?.metodo).toBe("POST")
  })
})
