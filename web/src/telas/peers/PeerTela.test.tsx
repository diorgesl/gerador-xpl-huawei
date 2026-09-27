import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { mockFetch, montarRota } from "@/teste/roteador"
import { PeerTela } from "./PeerTela"

const PLANO = {
  rede: { asn: "64512", politica: "65532" },
  padroes: {
    tipos: { cliente: { lp_base: 300, route_limit: 50, timer_keepalive: null, timer_hold: null } },
    origem_tipo: { cliente: 1100 }, origem_classe: { transito: 1100 },
    downstream: ["cliente", "parceiro"], origens_por_tipo: {}, origem_nome: {},
  },
  tipos: ["cliente"], tipos_com_criar_lista: ["cliente"], classes_cliente: [],
  lp_base: {}, route_limit: {}, route_limit_exemplo: {}, prepend_max: 6, prepend_implementado: 3,
  pop_min: 2001, pop_max: 2999, aprendizado_min: 3000, aprendizado_max: 3999,
  pop_usados: [], aprendizado_usados: [], campos_por_tipo: {}, campos_por_tipo_grupo: {},
}

const FORMULARIO = {
  id: "7", apelido: "", nome: "Cliente ACME", tipo: "cliente", grupo_id: "",
  asn: "268127", descricao: "", classe: "transito", lp_base: "300", origem: "1100",
  pop: "2001", aprendizado: "", ix_id: "", route_limit: "50", prepend_base: "0",
  timer_keepalive: "", timer_hold: "", bfd: true, graceful_restart: true,
  default_route: false, bh_upstream: "", prefixos_v4: ["45.169.232.0/22"], prefixos_v6: [],
  te_prefixos_v4: [], te_prefixos_v6: [], ap_block: [], ap_te: [], ap_allowed: [],
  ap_prefer: [], communities: [], large_communities: [],
  sessao_v4_local: "198.51.100.1", sessao_v4_remoto: "198.51.100.2",
  sessao_v6_local: "", sessao_v6_remoto: "",
}

const BASE = {
  "GET /api/plano": { corpo: PLANO },
  "GET /api/peers": { corpo: [{ id: 7, token: "268127", tipo: "cliente", asn: 268127, apelido: "", nome: "Cliente ACME", grupo_id: null }] },
  "GET /api/grupos": { corpo: [] },
  "GET /api/peers/7": { corpo: { id: 7, token: "268127", formulario: FORMULARIO } },
  "POST /api/peers/previa": {
    corpo: {
      erros: {}, avisos: [], criar_lista: null,
      bloco: "xpl route-filter CUST-268127-IMPORT-V4\nend-filter",
      arquivo: "268127-cliente.txt", salvo: null,
    },
  },
  "GET /api/peers/7/saida": { corpo: { bloco: "salvo", remover: "remover", criar_lista: null, arquivo: "268127-cliente.txt" } },
}

const rotas = [
  { path: "/peers", element: <div>lista de peers</div> },
  { path: "/peers/novo", element: <PeerTela /> },
  { path: "/peers/:id", element: <PeerTela /> },
]

afterEach(() => vi.unstubAllGlobals())

describe("a tela do peer", () => {
  it("abre com o token e o ASN no cabecalho", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    expect(await screen.findByText("268127")).toBeInTheDocument()
    expect(screen.getByText(/AS268127/)).toBeInTheDocument()
  })

  it("mostra a previa ao vivo, e o cabecalho diz que o arquivo e novo", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    expect(await screen.findByText(/CUST-268127-IMPORT-V4/)).toBeInTheDocument()
    expect(screen.getByText(/arquivo novo/)).toBeInTheDocument()
  })

  it("avisa que e copia e de onde ela veio", async () => {
    mockFetch({ ...BASE, "GET /api/peers/7/copia": { corpo: { id: 8, token: "268127", formulario: { ...FORMULARIO, id: "8" } } } })
    montarRota(rotas, "/peers/novo?de=7")
    expect(await screen.findByText(/cópia de 268127/)).toBeInTheDocument()
  })

  it("mostra os erros do salvar recusado", async () => {
    mockFetch({ ...BASE, "PUT /api/peers/7": { status: 422, corpo: { erros: { asn: "ASN ja usado pelo peer BRDIGITAL-20G" }, avisos: [] } } })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    // a mensagem aparece duas vezes de proposito: no resumo do topo, que leva
    // ao campo, e embaixo do campo. Por isso a busca e por papel, e nao por
    // texto, que acharia as duas
    expect(await screen.findByRole("button", { name: "ASN ja usado pelo peer BRDIGITAL-20G" })).toBeInTheDocument()
    expect(document.querySelector('[data-campo="asn"]')).toHaveTextContent("ASN ja usado pelo peer BRDIGITAL-20G")
  })

  it("o excluir pede confirmacao com o token no texto", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    expect(await screen.findByRole("dialog")).toHaveTextContent("268127")
  })

  it("duplicar leva para o peer novo preenchido com a copia", async () => {
    mockFetch({ ...BASE, "GET /api/peers/7/copia": { corpo: { id: 8, token: "268127", formulario: { ...FORMULARIO, id: "8" } } } })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /duplicar/i }))
    expect(await screen.findByText(/cópia de 268127/)).toBeInTheDocument()
  })

  it("a recusa do salvar sai quando a previa responde de novo", async () => {
    // a recusa vale ate a proxima previa responder: a edicao rearma o atraso de
    // 400ms, a previa volta com a lista dela (vazia na fixture) e a mensagem do
    // salvar some junto
    mockFetch({ ...BASE, "PUT /api/peers/7": { status: 422, corpo: { erros: { asn: "ASN ja usado pelo peer BRDIGITAL-20G" }, avisos: [] } } })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByRole("button", { name: "ASN ja usado pelo peer BRDIGITAL-20G" })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText("Nome"), " 2")
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "ASN ja usado pelo peer BRDIGITAL-20G" })).not.toBeInTheDocument(),
    )
  })

  it("o campo de lista abre com o que o registro tem", async () => {
    // o rascunho do AreaTexto comeca vazio e quem o enche e o reset do registro
    // lido: sem este teste, um campo que so mostrasse o rascunho abriria em
    // branco num peer que tem prefixos
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    expect(await screen.findByLabelText(/^IPv4 \(1\)/)).toHaveValue("45.169.232.0/22")
  })

  it("o salvar bem-sucedido nao desfaz o que foi gravado", async () => {
    // o efeito do registro lido tem o sujo por ref, e nao por dependencia: com
    // ele na lista, o salvamento (que zera o isDirty) reaplicaria o registro da
    // montagem, e a tela voltaria ao valor de antes do salvar. Um salvamento
    // seguinte gravaria os valores revertidos
    const salvo = { ...FORMULARIO, prefixos_v4: ["45.169.232.0/22", "45.169.236.0/23"] }
    mockFetch({
      ...BASE,
      "PUT /api/peers/7": { corpo: { registro: { id: 7, token: "268127", formulario: salvo }, arquivo: "268127-cliente.txt", avisos: [] } },
    })
    montarRota(rotas, "/peers/7")
    const campo = await screen.findByLabelText(/^IPv4 \(/)
    await userEvent.clear(campo)
    await userEvent.type(campo, "45.169.232.0/22{enter}45.169.236.0/23")
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    await waitFor(() =>
      expect(screen.getByLabelText(/^IPv4 \(2\)/)).toHaveValue("45.169.232.0/22\n45.169.236.0/23"),
    )
  })

  it("a consulta ao IRR escreve os prefixos no formulario", async () => {
    // e o caminho em que o formulario muda por baixo do campo de lista, que e
    // onde o rascunho do AreaTexto tem que dar lugar ao valor de fora
    mockFetch({ ...BASE, "POST /api/irr": { corpo: { v4: ["45.169.244.0/22"], v6: [] } } })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /consultar IRR/i }))
    // a ancora evita o "IPv4 local" das sessoes, que e outro campo
    await waitFor(() => expect(screen.getByLabelText(/^IPv4 \(/)).toHaveValue("45.169.244.0/22"))
  })
})
