import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { mockFetch, montarRota, type Resposta } from "@/teste/roteador"
import { ConfigTela } from "./ConfigTela"

// Um token por bloco, e nao frases: o CodigoXpl quebra a linha em spans por
// token, e o getByText so le os nos de texto diretos do elemento. Uma frase
// viraria varios spans e nenhum deles teria a frase inteira
// Na ordem do "Ordem de colagem no F1A" do README, que e a do /api/config: o
// base, os grupos, os peers e a originacao
const CONFIG = {
  secoes: [
    { chave: "base", titulo: "Bloco base", texto: "BASE-XPL", arquivo: null, salvo: null },
    { chave: "grupo-3", titulo: "PARCEIROS_CDN (parceiro)", texto: "GRUPO-XPL", arquivo: "grupo-PARCEIROS_CDN.txt", salvo: true },
    { chave: "peer-0", titulo: "Cliente ACME (cliente, AS268127)", texto: "PEER-XPL", arquivo: "ACME-AS268127-cliente.txt", salvo: false },
    { chave: "originacao", titulo: "Originacao dos prefixos proprios", texto: "ORIGEM-XPL", arquivo: "blocos.txt", salvo: true },
  ],
}

// O arquivo do "baixar tudo": os mesmos objetos, agrupados por tipo. Ele nao
// tem arquivo em out/ nem `salvo` - o grupo nao e um registro
const ORGANIZADA = {
  secoes: [
    { chave: "sets", titulo: "Sets e listas", texto: "SETS-XPL", arquivo: null, salvo: null },
    { chave: "filtros", titulo: "Route-filters", texto: "FILTROS-XPL", arquivo: null, salvo: null },
    { chave: "bgp", titulo: "bgp 64512", texto: "BGP-XPL", arquivo: null, salvo: null },
  ],
}

const rotas = [{ path: "/config-completa", element: <ConfigTela /> }]

const MAPA: Record<string, Resposta> = {
  "GET /api/config": { corpo: CONFIG },
  "GET /api/config/organizada": { corpo: ORGANIZADA },
}

function secao(nome: string) {
  return screen.getByRole("region", { name: nome })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("a tela da config completa", () => {
  it("mostra cada secao com o titulo e o bloco, na ordem que a API mandou", async () => {
    mockFetch(MAPA)
    montarRota(rotas, "/config-completa")

    // a ordem sai dos titulos, e nao de getAllByRole("region"): o sonner monta
    // um `section` proprio com aria-label na mesma arvore, e ele entraria na
    // lista. Que o id de cada secao e a chave esta no teste do sumario, que
    // compara os hrefs, e no do observador, que casa o id com a chave
    expect(await screen.findByRole("region", { name: "Bloco base" })).toBeInTheDocument()
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "Bloco base", "PARCEIROS_CDN (parceiro)",
      "Cliente ACME (cliente, AS268127)", "Originacao dos prefixos proprios",
    ])
    expect(within(secao("Bloco base")).getByText(/BASE-XPL/)).toBeInTheDocument()
    expect(within(secao("Cliente ACME (cliente, AS268127)")).getByText(/PEER-XPL/)).toBeInTheDocument()
  })

  it("marca o bloco que ainda nao foi gravado em out/", async () => {
    // O `salvo` e o mais perto de "isso esta no equipamento" que o app sabe:
    // sem a marca, o operador le a pagina inteira como se fosse a config que
    // ja esta la
    mockFetch(MAPA)
    montarRota(rotas, "/config-completa")

    const semArquivo = await screen.findByRole("region", { name: /Cliente ACME/ })
    expect(within(semArquivo).getByText(/sem arquivo em out\//)).toBeInTheDocument()
    // o base nao tem arquivo proprio e nem por isso esta pendente
    expect(within(secao("Bloco base")).queryByText(/sem arquivo em out\//)).not.toBeInTheDocument()
    expect(screen.getByText(/1 sem arquivo em out\//)).toBeInTheDocument()
  })

  it("recolhe uma secao e o topo recolhe e expande todas", async () => {
    mockFetch(MAPA)
    montarRota(rotas, "/config-completa")

    const alternar = await screen.findByRole("button", { name: /Bloco base/ })
    expect(alternar).toHaveAttribute("aria-expanded", "true")
    await userEvent.click(alternar)
    expect(screen.queryByText(/BASE-XPL/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: /expandir todas/i }))
    expect(screen.getByText(/BASE-XPL/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: /recolher todas/i }))
    expect(screen.queryByText(/BASE-XPL/)).not.toBeInTheDocument()
    expect(screen.queryByText(/PEER-XPL/)).not.toBeInTheDocument()
  })

  it("o sumario leva a cada secao", async () => {
    mockFetch(MAPA)
    montarRota(rotas, "/config-completa")

    const sumario = await screen.findByRole("navigation", { name: /sumário/i })
    expect(within(sumario).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
      "#base", "#grupo-3", "#peer-0", "#originacao",
    ])
  })

  // A marca da secao lida nao tem caso aqui: ela sai do topo de cada secao, que
  // o jsdom mede como zero para todas. Quem decide qual secao e a lida esta em
  // leitura.test.ts, com as medidas na mao, e quem prova a ligacao com a
  // rolagem de verdade e o e2e

  it("copiar tudo leva a config inteira, na ordem", async () => {
    const escrever = vi.fn()
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText: escrever } })
    mockFetch(MAPA)
    montarRota(rotas, "/config-completa")

    await userEvent.click(await screen.findByRole("button", { name: /copiar tudo/i }))

    await waitFor(() =>
      expect(escrever).toHaveBeenCalledWith([
        "BASE-XPL", "GRUPO-XPL", "PEER-XPL", "ORIGEM-XPL",
      ].join("\n\n")),
    )
  })

  it("baixar tudo leva o arquivo por tipo, e nao a ordem da tela", async () => {
    // o download nao e o `copiar tudo` num arquivo: quem baixa leva a config
    // agrupada por tipo, que vem do /config/organizada, buscada no clique
    const cliques: HTMLAnchorElement[] = []
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      cliques.push(this)
    })
    let baixado: Blob | undefined
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn((b: Blob) => {
        baixado = b
        return "blob:x"
      }),
      revokeObjectURL: vi.fn(),
    })
    mockFetch(MAPA)
    montarRota(rotas, "/config-completa")

    await userEvent.click(await screen.findByRole("button", { name: /baixar tudo/i }))

    await waitFor(() => expect(cliques).toHaveLength(1))
    // o ASN no nome: o mesmo operador baixa a config de mais de uma rede, e o
    // navegador renomeia o segundo `config.txt` para "config (1).txt"
    expect(cliques[0].download).toBe("config-64512.txt")
    expect(await baixado!.text()).toBe("SETS-XPL\n\nFILTROS-XPL\n\nBGP-XPL")
  })

  it("diz que nao deu para falar com a API, e o tentar de novo traz o dado", async () => {
    const mapa: Record<string, Resposta> = { "GET /api/config": { status: 500, corpo: {} } }
    mockFetch(mapa)
    montarRota(rotas, "/config-completa")

    expect(await screen.findByText("não deu para falar com a API", {}, { timeout: 3000 })).toBeInTheDocument()
    // sem dado nao ha o que copiar: o botao que levaria nada fica morto
    expect(screen.queryByRole("button", { name: /copiar tudo/i })).not.toBeInTheDocument()

    mapa["GET /api/config"] = MAPA["GET /api/config"]
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    expect(await screen.findByRole("region", { name: "Bloco base" })).toBeInTheDocument()
  })
})
