import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { mockFetch, montarRota, peticoes, type Resposta } from "@/teste/roteador"
import { Casca } from "@/app/casca"
import { ConfiguracoesTela } from "./ConfiguracoesTela"

const PLANO = {
  rede: { asn: "64512", politica: "65532" },
  padroes: { tipos: {}, origem_tipo: {}, origem_classe: {}, downstream: [], origens_por_tipo: {}, origem_nome: {} },
  tipos: [], tipos_com_criar_lista: [], classes_cliente: [], lp_base: {}, route_limit: {},
  route_limit_exemplo: {}, prepend_max: 6, prepend_implementado: 3,
  pop_min: 2001, pop_max: 2999, aprendizado_min: 3000, aprendizado_max: 3999,
  pop_usados: [], aprendizado_usados: [], campos_por_tipo: {}, campos_por_tipo_grupo: {},
}

const BASE = {
  "GET /api/plano": { corpo: PLANO },
  "GET /api/peers": { corpo: [] },
  "GET /api/grupos": { corpo: [] },
}

const rotas = [{ path: "/configuracoes", element: <ConfiguracoesTela /> }]

// A casca monta a tela por rota, como no app: e por ela que o Ctrl+S chega
const casca = [
  {
    path: "/",
    element: <Casca />,
    children: [{ path: "configuracoes", element: <ConfiguracoesTela /> }],
  },
]

/**
 * Segura uma leitura ate o caso mandar soltar, e repassa o resto ao arnes: e a
 * janela em que a tela esta montada sem dado nenhum.
 */
function segurarLeitura(chave: string) {
  const doArnes = globalThis.fetch
  let liberar: () => void = () => {}
  const espera = new Promise<void>((resolve) => { liberar = resolve })
  vi.stubGlobal("fetch", async (entrada: Request) => {
    if (`${entrada.method} ${String(entrada.url).split("?")[0]}` === chave) await espera
    return doArnes(entrada)
  })
  return () => liberar()
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe("a tela das configuracoes", () => {
  it("mostra o AS da rede e o namespace", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/configuracoes")
    // o campo existe desde a montagem e o valor so chega com a leitura: o
    // `findByLabelText` espera o campo, nao o valor dele
    await waitFor(() => expect(screen.getByLabelText(/AS da rede/i)).toHaveValue("64512"))
    expect(screen.getByLabelText(/namespace/i)).toHaveValue("65532")
  })

  it("explica que o namespace so e necessario com ASN de 32 bits", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/configuracoes")
    expect(await screen.findByText(/32 bits/i)).toBeInTheDocument()
  })

  it("o erro da faixa aparece no campo do AS", async () => {
    mockFetch({ ...BASE, "PUT /api/rede": { status: 422, corpo: { erros: { asn_rede: "AS da rede fora da faixa valida" }, avisos: [] } } })
    montarRota(rotas, "/configuracoes")
    const gravar = await screen.findByRole("button", { name: /gravar AS/i })
    // o botao so oferece o salvar depois de o plano chegar
    await waitFor(() => expect(gravar).toBeEnabled())
    await userEvent.click(gravar)
    expect(await screen.findByText("AS da rede fora da faixa valida")).toBeInTheDocument()
  })

  it("troca o tema e guarda a escolha", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/configuracoes")
    await userEvent.click(await screen.findByRole("button", { name: /^escuro$/i }))
    expect(localStorage.getItem("tema")).toBe("escuro")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })

  it("o tema escolhido se anuncia como pressionado", async () => {
    // a marca era so a cor (variant + ring): quem usa leitor de tela nao sabia
    // qual dos tres estava valendo. O tema padrao e "sistema", entao o clique
    // em "claro" muda o estado de verdade, e a marca tem que SAIR do sistema
    mockFetch(BASE)
    montarRota(rotas, "/configuracoes")
    await screen.findByRole("button", { name: "claro" })
    expect(screen.getByRole("button", { name: "sistema" })).toHaveAttribute("aria-pressed", "true")

    await userEvent.click(screen.getByRole("button", { name: "claro" }))

    expect(screen.getByRole("button", { name: "claro" })).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("button", { name: "escuro" })).toHaveAttribute("aria-pressed", "false")
    // esta terceira e a que pega a marca presa no padrao: medida na execucao,
    // um `aria-pressed={tema === t || t === "sistema"}` passa nas duas de cima
    // e falha so aqui, porque o "pressionado" ficaria nos dois botoes
    expect(screen.getByRole("button", { name: "sistema" })).toHaveAttribute("aria-pressed", "false")
  })

  it("o gravar AS espera o plano chegar, e depois grava o que esta na tela", async () => {
    // a janela entre a montagem e a leitura e a unica em que a tela existe sem
    // dado: sem a guarda, o botao mandava o formulario em branco, e a recusa da
    // API pintava um campo que o operador nunca tocou
    mockFetch({ ...BASE, "PUT /api/rede": { corpo: { asn: "64512", politica: "65532" } } })
    const soltar = segurarLeitura("GET /api/plano")
    montarRota(rotas, "/configuracoes")
    const gravar = await screen.findByRole("button", { name: /gravar AS/i })
    await waitFor(() => expect(gravar).toBeDisabled())
    await userEvent.click(gravar)
    expect(peticoes().filter((p) => p.metodo !== "GET")).toEqual([])
    // e a direcao que mostra: com o plano na mao o botao volta, e o que sai e o
    // que esta escrito na tela, e nao o branco
    soltar()
    await waitFor(() => expect(screen.getByLabelText(/AS da rede/i)).toHaveValue("64512"))
    await userEvent.click(screen.getByRole("button", { name: /gravar AS/i }))
    expect(peticoes().filter((p) => p.metodo === "PUT")).toEqual([
      { metodo: "PUT", caminho: "/api/rede", query: "", corpo: { asn: "64512", politica: "65532" } },
    ])
  })

  it("o que o operador digita nao e apagado pelo dado que chega depois", async () => {
    // o formulario monta antes de a leitura responder, e o mesmo caminho vale
    // para o refetch do foco e para a invalidacao depois do salvar: o dado que
    // chega nao pode passar por cima do campo que esta sendo digitado. O outro
    // campo, que ninguem tocou, entra com o valor do plano
    mockFetch(BASE)
    const soltar = segurarLeitura("GET /api/plano")
    montarRota(rotas, "/configuracoes")
    await userEvent.type(await screen.findByLabelText(/AS da rede/i), "64500")
    soltar()
    await waitFor(() => expect(screen.getByLabelText(/namespace/i)).toHaveValue("65532"))
    expect(screen.getByLabelText(/AS da rede/i)).toHaveValue("64500")
  })

  it("diz que nao deu para falar com a API, e o tentar de novo traz o dado", async () => {
    // Sem o aviso a tela fica com os campos vazios e o gravar morto sem dizer
    // por que. O aviso entra acima dos campos, e nao no lugar do corpo: o tema
    // e a explicacao do namespace valem mesmo com o plano fora do ar
    const mapa: Record<string, Resposta> = { ...BASE, "GET /api/plano": { status: 500, corpo: {} } }
    mockFetch(mapa)
    montarRota(rotas, "/configuracoes")
    // o aviso so aparece depois de a consulta gastar o retry do cliente (um,
    // com o atraso padrao de 1s), que e o mesmo do app
    expect(await screen.findByText("não deu para falar com a API", {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /gravar AS/i })).toBeDisabled()
    // a API volta: o tentar de novo e o unico caminho de volta, e sem ele a tela
    // ficaria presa na falha ate um F5
    mapa["GET /api/plano"] = BASE["GET /api/plano"]
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    await waitFor(() => expect(screen.getByLabelText(/AS da rede/i)).toHaveValue("64512"))
    await waitFor(() => expect(screen.getByRole("button", { name: /gravar AS/i })).toBeEnabled())
  })

  it("a rede fora no gravar avisa com tentar de novo, e o campo nao se perde", async () => {
    // O openapi-fetch RE-LANCA a excecao de rede: o onSuccess do gravar nao
    // rodava, e o clique em "gravar AS" nao deixava rastro nenhum na tela
    const mapa: Record<string, Resposta> = { ...BASE, "PUT /api/rede": { rede: true } }
    mockFetch(mapa)
    montarRota(rotas, "/configuracoes")
    const campo = await screen.findByLabelText(/AS da rede/i)
    await waitFor(() => expect(campo).toHaveValue("64512"))
    await userEvent.clear(campo)
    await userEvent.type(campo, "64500")
    await userEvent.click(screen.getByRole("button", { name: /gravar AS/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    expect(screen.getByLabelText(/AS da rede/i)).toHaveValue("64500")
    mapa["PUT /api/rede"] = { corpo: { asn: "64500", politica: "65532" } }
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    await waitFor(() => expect(peticoes().filter((p) => p.metodo === "PUT")).toHaveLength(2))
  })

  it("o 500 no gravar avisa com tentar de novo", async () => {
    // o 500 e o outro caso da mesma linha da spec ("500 ou rede fora"), e ele
    // chega pelo ramo do `r.error`, e nao pela excecao
    const mapa: Record<string, Resposta> = { ...BASE, "PUT /api/rede": { status: 500, corpo: { detail: "falhou" } } }
    mockFetch(mapa)
    montarRota(rotas, "/configuracoes")
    const gravar = await screen.findByRole("button", { name: /gravar AS/i })
    await waitFor(() => expect(gravar).toBeEnabled())
    await userEvent.click(gravar)
    expect(await screen.findByRole("button", { name: /tentar de novo/i })).toBeInTheDocument()
    mapa["PUT /api/rede"] = { corpo: { asn: "64512", politica: "65532" } }
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    await waitFor(() => expect(peticoes().filter((p) => p.metodo === "PUT")).toHaveLength(2))
  })

  it("o Ctrl+S grava o AS com o plano na mao", async () => {
    // a tela publica o `aoSalvar` para a paleta e o Ctrl+S, como as outras
    // quatro: sem a publicacao o atalho fica morto aqui
    mockFetch({ ...BASE, "PUT /api/rede": { corpo: { asn: "64512", politica: "65532" } } })
    montarRota(casca, "/configuracoes")
    await waitFor(() => expect(screen.getByLabelText(/AS da rede/i)).toHaveValue("64512"))
    await userEvent.keyboard("{Control>}s{/Control}")
    expect(peticoes().filter((p) => p.metodo === "PUT")).toEqual([
      { metodo: "PUT", caminho: "/api/rede", query: "", corpo: { asn: "64512", politica: "65532" } },
    ])
  })

  it("o Ctrl+S nao grava com a leitura do plano fora do ar", async () => {
    // a guarda vale depois da falha, e nao so durante a carga: com o plano fora
    // do ar o namespace nao chegou, e um PUT daqui o apagaria
    mockFetch({
      ...BASE,
      "GET /api/plano": { status: 500, corpo: {} },
      "PUT /api/rede": { corpo: { asn: "64512", politica: "65532" } },
    })
    montarRota(casca, "/configuracoes")
    // a segunda leitura e o retry do cliente (um, com o atraso padrao de 1s):
    // depois dela a consulta parou de tentar e a tela continua sem o dado
    await waitFor(
      () => expect(peticoes().filter((p) => p.caminho === "/api/plano").length).toBe(2),
      { timeout: 3000 },
    )
    await userEvent.keyboard("{Control>}s{/Control}")
    expect(peticoes().filter((p) => p.metodo !== "GET")).toEqual([])
  })
})
