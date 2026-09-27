import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { mockFetch, montarRota, peticoes } from "@/teste/roteador"
import { PrefixosTela } from "./PrefixosTela"

const BASE = {
  "GET /api/blocos": {
    corpo: {
      texto: { v4: "38.252.64.0/22  64512:613", v6: "" },
      originacao: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list",
      remover: "undo xpl ip-prefix-list PL-ORIGEM-V4",
    },
  },
  "POST /api/blocos/previa": {
    corpo: { erros: {}, avisos: [], bloco: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list", arquivo: "blocos.txt", salvo: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list" },
  },
}

const rotas = [{ path: "/prefixos", element: <PrefixosTela /> }]

afterEach(() => vi.unstubAllGlobals())

describe("a tela dos prefixos proprios", () => {
  it("mostra os dois editores com o texto de hoje", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/prefixos")
    await waitFor(() => expect(screen.getByLabelText(/IPv4/)).toHaveValue("38.252.64.0/22  64512:613"))
    expect(screen.getByLabelText(/IPv6/)).toHaveValue("")
  })

  it("explica o formato acima dos editores", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/prefixos")
    expect(await screen.findByText(/uma linha por prefixo/i)).toBeInTheDocument()
    expect(screen.getByText(/fora de serviço/i)).toBeInTheDocument()
  })

  it("oferece as abas de originacao e de remocao", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/prefixos")
    expect(await screen.findByRole("tab", { name: /originação/i })).toBeInTheDocument()
    expect(await screen.findByRole("tab", { name: /remoção/i })).toBeInTheDocument()
  })

  it("a consulta ao IRR substitui o texto dos dois editores sem gravar", async () => {
    mockFetch({
      ...BASE,
      "POST /api/blocos/irr": { corpo: { v4: "45.169.232.0/22\n45.169.236.0/23", v6: "2001:db8::/32" } },
    })
    montarRota(rotas, "/prefixos")
    await userEvent.click(await screen.findByRole("button", { name: /consultar IRR/i }))
    await waitFor(() => expect(screen.getByLabelText(/IPv4/)).toHaveValue("45.169.232.0/22\n45.169.236.0/23"))
    expect(screen.getByLabelText(/IPv6/)).toHaveValue("2001:db8::/32")
    // "sem gravar" e a segunda metade do nome do caso: sem esta linha uma tela
    // que gravasse junto com a consulta passaria
    expect(peticoes().some((p) => p.metodo === "PUT")).toBe(false)
  })

  it("o erro do prefixo torto aparece no editor da familia dele", async () => {
    mockFetch({ ...BASE, "PUT /api/blocos": { status: 422, corpo: { erros: { blocos_v6: "prefixo invalido: 2001:db8::/129" }, avisos: [] } } })
    montarRota(rotas, "/prefixos")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar/i }))
    expect(await screen.findByText("prefixo invalido: 2001:db8::/129")).toBeInTheDocument()
  })

  it("o erro que vem da propria previa aparece e tira o bloco antigo do painel", async () => {
    // a previa responde 200 com o mapa de erros e o bloco nulo. Sem olhar para
    // esse mapa a tela ficaria muda, e o painel cairia no bloco salvo como se
    // ele fosse a previa do texto de agora
    mockFetch({
      ...BASE,
      "POST /api/blocos/previa": {
        corpo: {
          erros: { blocos_v6: "prefixo invalido: 2001:db8::/129" },
          avisos: [],
          bloco: null,
          arquivo: null,
          salvo: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list",
        },
      },
    })
    montarRota(rotas, "/prefixos")
    expect(await screen.findByText("prefixo invalido: 2001:db8::/129")).toBeInTheDocument()
    expect(await screen.findByText(/a prévia volta quando os erros forem corrigidos/)).toBeInTheDocument()
  })
})
