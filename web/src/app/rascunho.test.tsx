import { useState } from "react"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it } from "vitest"
import { mockFetch, montarRota, peticoes, type Resposta } from "@/teste/roteador"
import { AvisoNaoSalvo } from "@/components/AvisoNaoSalvo"
import { Casca } from "@/app/casca"
import { PrefixosTela } from "@/telas/prefixos/PrefixosTela"
import { TelaDoPeer } from "@/telas/peers/PeerTela"
import { TelaDoGrupo } from "@/telas/grupos/GrupoTela"
import { useTenant } from "@/app/tenant"
import { usePublicarRascunho } from "./rascunho"

/**
 * A tela de formulario em miniatura, para os casos que nao precisam da tela de
 * verdade: ela publica o rascunho e arma o AvisoNaoSalvo, que sao as duas
 * coisas que a troca poe em jogo. O aviso entra junto porque o useBlocker dele
 * e a armadilha da troca: a tela que acabou de sair ainda esta de pe quando o
 * seletor pede a navegacao para a lista.
 *
 * Quem mede a fiacao das telas de verdade - o `usePublicarRascunho` de cada
 * uma, com o `sujo` do formulario real - e o par do fim deste arquivo, que
 * monta a tela do peer e a do grupo na casca de verdade.
 */
function Formulario() {
  const { asn } = useTenant()
  const [texto, setTexto] = useState("")
  const sujo = texto !== ""
  usePublicarRascunho(sujo)
  return (
    <div>
      <p>tela da rede {asn}</p>
      <label>
        campo
        <input value={texto} onChange={(e) => setTexto(e.target.value)} />
      </label>
      <AvisoNaoSalvo sujo={sujo} />
    </div>
  )
}

const rotas = [
  {
    path: "/",
    element: <Casca />,
    children: [
      { path: "peers", element: <p>lista de peers</p> },
      { path: "peers/:id", element: <Formulario /> },
      // a tela de verdade, e nao um duble: e ela que mede a fiacao da tela
      // dos prefixos, que publica o rascunho por si. As do peer e do grupo
      // ficam no par logo abaixo, nas rotas de verdade
      { path: "prefixos", element: <PrefixosTela /> },
    ],
  },
]

// o que a casca e o seletor perguntam em toda rota: a lista de redes, os
// registros da rede aberta e o bloco de prefixos que a tela de /prefixos edita
const mapa = (): Record<string, Resposta> => ({
  "GET /api/asns": { corpo: ["64512", "264130"] },
  "GET /api/peers": { corpo: [] },
  "GET /api/grupos": { corpo: [] },
  "GET /api/blocos": {
    corpo: { texto: { v4: "38.252.64.0/22 64512:613", v6: "" }, originacao: "", remover: "" },
  },
  "POST /api/blocos/previa": {
    corpo: { erros: {}, avisos: [], bloco: "", arquivo: "blocos.txt", salvo: "" },
  },
})

// As rotas da casca com as duas telas de formulario de verdade dentro: a do
// peer e a do grupo pelo TelaDoPeer e pelo TelaDoGrupo, como no roteador. E o
// par do fim do arquivo que monta por aqui
const rotasDeVerdade = [
  {
    path: "/",
    element: <Casca />,
    children: [
      { path: "peers", element: <p>lista de peers</p> },
      { path: "peers/:id", element: <TelaDoPeer /> },
      { path: "grupos", element: <p>lista de grupos</p> },
      { path: "grupos/:id", element: <TelaDoGrupo /> },
    ],
  },
]

// O plano e os dois registros sao as fixtures que os arquivos das telas ja
// mockam (PeerTela.test.tsx e GrupoTela.test.tsx), com o plano unico porque um
// mapa so serve aos dois casos do par. O que ele mede e a fiacao das telas, e
// nao a forma da fixture
const PLANO = {
  rede: { asn: "64512", politica: "65532" },
  padroes: {
    tipos: {
      cliente: { lp_base: 300, route_limit: 50, timer_keepalive: null, timer_hold: null },
      upstream: { lp_base: 100, route_limit: 1500000, timer_keepalive: 10, timer_hold: 30 },
    },
    origem_tipo: { cliente: 1100, upstream: 1400 },
    origem_classe: { transito: 1100 },
    downstream: ["cliente", "parceiro"], origens_por_tipo: {}, origem_nome: {},
  },
  tipos: ["cliente", "parceiro", "upstream", "ix", "pni"],
  tipos_com_criar_lista: ["cliente", "parceiro", "upstream"],
  classes_cliente: [], tabelas: ["nenhuma", "parcial", "parcial_ix", "full"], lp_base: {}, route_limit: {}, route_limit_exemplo: {},
  prepend_max: 6, prepend_implementado: 3, pop_min: 2001, pop_max: 2999,
  aprendizado_min: 3000, aprendizado_max: 3999, pop_usados: [], aprendizado_usados: [],
  campos_por_tipo: {}, campos_por_tipo_grupo: {},
  // o catalogo da busca de communities: vazio aqui, porque o que
  // estes casos provam nao e a lista, e o AdicionarCommunity tem teste
  // proprio. O `satisfies` e o que faz a proxima chave do Plano
  // aparecer aqui como erro de tipo, e nao como tela quebrada
  sugestoes: { communities: [], large_communities: [] },
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

const GRUPO = {
  id: "2", nome: "OPERADORA", tipo: "upstream", asn: "14840", classe: "", lp_base: "100",
  origem: "1400", pop: "", aprendizado: "3100", aprendizado_ix: "", ix_id: "",
  prepend_base: "0", timer_keepalive: "10", timer_hold: "30", bfd: true,
  graceful_restart: true, default_route: false, bh_upstream: "",
  prefixos_v4: [], prefixos_v6: [], te_prefixos_v4: [], te_prefixos_v6: [],
  ap_block: [], ap_te: [], ap_allowed: [], ap_prefer: [], communities: [], large_communities: [],
}

// O mapa dos casos das telas de verdade: o de cima mais as duas telas
const DADOS = (): Record<string, Resposta> => ({
  ...mapa(),
  "GET /api/plano": { corpo: PLANO },
  "GET /api/peers/7": { corpo: { id: 7, token: "268127", formulario: FORMULARIO } },
  "GET /api/peers/7/saida": {
    corpo: { bloco: "salvo", remover: null, criar_lista: null, arquivo: "268127-cliente.txt" },
  },
  "POST /api/peers/previa": {
    corpo: {
      erros: {}, avisos: [], criar_lista: null, salvo: null, arquivo: "268127-cliente.txt",
      bloco: "xpl route-filter CUST-268127-IMPORT-V4\nend-filter",
    },
  },
  "GET /api/grupos/2": {
    corpo: { id: 2, nome: "OPERADORA", formulario: GRUPO, membros: [{ id: 3, token: "BRDIGITAL" }] },
  },
  "GET /api/grupos/2/saida": {
    corpo: { bloco: "xpl route-filter UP-OPERADORA-EXPORT-V4", criar_lista: null, arquivo: "grupo-OPERADORA.txt" },
  },
  "POST /api/grupos/previa": {
    corpo: {
      erros: {}, avisos: [], criar_lista: null, salvo: null, arquivo: "grupo-OPERADORA.txt",
      bloco: "xpl route-filter UP-OPERADORA-EXPORT-V4",
    },
  },
})

const PERGUNTA = /Há alterações que ainda não foram para o/

/** Abre o menu do seletor e pede a outra rede. */
async function escolherOutraRede() {
  await userEvent.click(screen.getByRole("button", { name: "AS64512" }))
  await userEvent.click(await screen.findByRole("menuitem", { name: "AS264130" }))
}

describe("a troca de tenant com rascunho sujo", () => {
  beforeEach(() => window.sessionStorage.clear())

  it("trocar de tenant com rascunho sujo pergunta antes", async () => {
    mockFetch(mapa())
    // /prefixos e a tela em que a troca nao navega: o rascunho e o unico
    // estrago em jogo, e por isso o caso isola a pergunta
    montarRota(rotas, "/prefixos")
    const v4 = await screen.findByLabelText("IPv4")
    await userEvent.type(v4, "  38.252.68.0/22 64512:613")

    await escolherOutraRede()

    expect(await screen.findByText(PERGUNTA)).toBeInTheDocument()
    // a pergunta vem ANTES da troca, e nao depois: com o ASN ja trocado a tela
    // de uma rede ficaria de pe consultando a outra, que e o buraco que este
    // aviso existe para fechar
    expect(screen.getByRole("button", { name: "AS64512" })).toBeInTheDocument()
    expect(peticoes().some((p) => p.query.includes("asn=264130"))).toBe(false)
  })

  it("cancelar mantem o tenant e o rascunho", async () => {
    mockFetch(mapa())
    montarRota(rotas, "/prefixos")
    const v4 = await screen.findByLabelText("IPv4")
    await userEvent.type(v4, "  38.252.68.0/22 64512:613")
    await escolherOutraRede()

    await userEvent.click(await screen.findByRole("button", { name: "continuar editando" }))

    // a pergunta some sem trocar nada: nem o tenant, nem a tela (que perde o
    // rascunho na remontagem), nem o que ja foi digitado
    expect(screen.queryByText(PERGUNTA)).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "AS64512" })).toBeInTheDocument()
    expect(screen.getByLabelText("IPv4")).toHaveValue("38.252.64.0/22 64512:613  38.252.68.0/22 64512:613")
    expect(peticoes().some((p) => p.query.includes("asn=264130"))).toBe(false)
  })

  it("confirmar troca o tenant e sai para /peers", async () => {
    mockFetch(mapa())
    // o registro aberto e do tenant antigo: /peers/1 nao existe do outro lado,
    // ou e outro peer, entao confirmar tem que sair da tela dele
    montarRota(rotas, "/peers/1")
    expect(await screen.findByText("tela da rede 64512")).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText("campo"), "rascunho da rede A")
    await escolherOutraRede()

    await userEvent.click(await screen.findByRole("button", { name: "trocar sem salvar" }))

    // saiu da tela do registro e esta na lista da rede nova
    expect(await screen.findByText("lista de peers")).toBeInTheDocument()
    expect(await screen.findByText("AS264130")).toBeInTheDocument()
    // a consulta seguinte ja e a da rede escolhida
    await waitFor(() => expect(peticoes().some(
      (p) => p.caminho === "/api/peers" && p.query.includes("asn=264130"))).toBe(true))
  })

  // O par que faltava: o duble la de cima nao prova a fiacao da tela do peer
  // nem a da tela do grupo, e era por ele que o `usePublicarRascunho(sujo)`
  // das duas podia sair sem a suite reprovar. Aqui a tela e a de verdade, com
  // as fixtures dela, e o campo digitado e um de verdade: o `sujo` que o
  // seletor le e o `isDirty` do formulario que esta em pe
  it.each([
    ["peer", "/peers/7"],
    ["grupo", "/grupos/2"],
  ])("a troca com o rascunho da tela do %s pergunta antes", async (_tela, rota) => {
    mockFetch(DADOS())
    montarRota(rotasDeVerdade, rota)
    await userEvent.type(await screen.findByLabelText("Nome"), " editado")

    await escolherOutraRede()

    expect(await screen.findByText(PERGUNTA)).toBeInTheDocument()
    // a pergunta vem ANTES da troca, como no caso dos prefixos: com o ASN ja
    // trocado a tela de uma rede ficaria de pe consultando a outra
    expect(screen.getByRole("button", { name: "AS64512" })).toBeInTheDocument()
    expect(peticoes().some((p) => p.query.includes("asn=264130"))).toBe(false)
  })
})
