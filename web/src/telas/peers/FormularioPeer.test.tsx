import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useForm } from "react-hook-form"
import { describe, expect, it, vi } from "vitest"
import { Provedores } from "@/app/provedores"
import type { PeerForm, PeerResumo, Plano } from "@/api/consultas"
import { FormularioPeer } from "./FormularioPeer"

const PLANO = {
  rede: { asn: "64512", politica: "65532" },
  padroes: {
    tipos: {
      cliente: { lp_base: 300, route_limit: 50, timer_keepalive: null, timer_hold: null },
      upstream: { lp_base: 100, route_limit: 1500000, timer_keepalive: 10, timer_hold: 30 },
      ix: { lp_base: 190, route_limit: 500000, timer_keepalive: null, timer_hold: null },
      parceiro: { lp_base: 300, route_limit: 50, timer_keepalive: null, timer_hold: null },
      pni: { lp_base: 200, route_limit: 10000, timer_keepalive: null, timer_hold: null },
    },
    origem_tipo: { cliente: 1100, parceiro: 1100, upstream: 1400, ix: 1300, pni: 1500 },
    origem_classe: { transito: 1100, residencial: 1110 },
    downstream: ["cliente", "parceiro"],
    origens_por_tipo: { cliente: [1100, 1110], upstream: [1400, 1000, 1900] },
    origem_nome: { 1100: "cliente de transito", 1110: "cliente residencial", 1400: "upstream", 1300: "ix" },
  },
  tipos: ["cliente", "parceiro", "upstream", "ix", "pni"],
  tipos_com_criar_lista: ["cliente", "parceiro", "upstream"],
  classes_cliente: ["transito", "residencial", "corporativo", "cgnat"],
  lp_base: { cliente: 300, upstream: 100 },
  route_limit: { cliente: 50, upstream: 1500000 },
  route_limit_exemplo: { cliente: 100 },
  prepend_max: 6,
  prepend_implementado: 3,
  pop_min: 2001, pop_max: 2999, aprendizado_min: 3000, aprendizado_max: 3999,
  pop_usados: [2001, 2010], aprendizado_usados: [3100],
  campos_por_tipo: {
    classe: ["cliente", "parceiro"], pop: ["cliente", "parceiro"],
    default_route: ["cliente", "parceiro"], aprendizado: ["upstream", "ix"],
    prepend_base: ["upstream"], bh_upstream: ["upstream"], ap_block: ["upstream"],
    ap_te: ["upstream"], te_prefixos_v4: ["upstream"], te_prefixos_v6: ["upstream"],
    ix_id: ["ix"], ap_prefer: ["ix"], ap_allowed: ["pni"],
    communities: ["cliente", "parceiro", "upstream"],
    large_communities: ["cliente", "parceiro", "upstream"],
  },
  campos_por_tipo_grupo: {},
  // o catalogo da busca de communities. Vazio aqui de proposito: a lista
  // tem teste proprio no AdicionarCommunity.test.tsx, e o que estes casos
  // provam e o resto do formulario
  sugestoes: { communities: [], large_communities: [] },
} satisfies Plano

const BRANCO: PeerForm = {
  id: "7", apelido: "", nome: "Cliente ACME", tipo: "cliente", grupo_id: "", politica_de: "",
  asn: "268127", descricao: "", classe: "residencial", lp_base: "300", origem: "1110",
  pop: "2001", aprendizado: "", ix_id: "", route_limit: "50", prepend_base: "0",
  timer_keepalive: "", timer_hold: "", bfd: true, graceful_restart: true,
  default_route: false, bh_upstream: "", prefixos_v4: ["45.169.232.0/22"], prefixos_v6: [],
  te_prefixos_v4: [], te_prefixos_v6: [], ap_block: [], ap_te: [], ap_allowed: [],
  ap_prefer: [], communities: [], large_communities: [],
  sessao_v4_local: "198.51.100.1", sessao_v4_remoto: "198.51.100.2",
  sessao_v6_local: "", sessao_v6_remoto: "",
}

// O ACME-BKP existe para provar que quem reaproveita nao se oferece como
// origem, e o OUTRO e o Upstream para provar os filtros de tipo e de ASN
const PEERS: PeerResumo[] = [
  { id: 1, token: "268127", tipo: "cliente", asn: 268127, apelido: "ACME",
    nome: "Cliente ACME", grupo_id: null, politica_de: null },
  { id: 2, token: "268128", tipo: "cliente", asn: 268128, apelido: "OUTRO",
    nome: "Cliente OUTRO", grupo_id: null, politica_de: null },
  { id: 3, token: "14840", tipo: "upstream", asn: 14840, apelido: "",
    nome: "Upstream", grupo_id: null, politica_de: null },
  { id: 4, token: "ACME-BKP", tipo: "cliente", asn: 268127, apelido: "ACME-BKP",
    nome: "Cliente ACME BKP", grupo_id: null, politica_de: 1 },
]

function Montar({ iniciais = {}, erros = {}, avisos = [], plano = PLANO, peers = PEERS }: {
  iniciais?: Partial<PeerForm>
  erros?: Record<string, string>
  avisos?: { campo: string; mensagem: string }[]
  plano?: Plano
  peers?: PeerResumo[]
}) {
  const form = useForm<PeerForm>({ defaultValues: { ...BRANCO, ...iniciais } })
  return (
    <Provedores>
      <FormularioPeer form={form} plano={plano} grupos={[]} peers={peers} erros={erros} avisos={avisos} aoIrPara={vi.fn()} />
    </Provedores>
  )
}

describe("o formulario do peer", () => {
  it("o indice lista as secoes que a tela mostra, com o rotulo delas", () => {
    render(<Montar />)
    // as oito secoes da tabela, menos as duas que o peer de cliente nao tem
    // campo para mostrar: o indice e os fieldsets saem da mesma lista
    for (const rotulo of ["Identificação", "Política", "Limites e timers", "Prefixos anunciados", "CL-PEER", "Sessões"]) {
      expect(screen.getByRole("link", { name: new RegExp(rotulo, "i") })).toBeInTheDocument()
    }
  })

  it("nao lista a secao que ficou sem campo nenhum", () => {
    // um link para uma secao que nao esta na tela nao leva a lugar nenhum: o
    // cliente nao tem campo em "te" nem em "aspath", e os dois sairiam do
    // indice apontando para id que nao existe
    render(<Montar />)
    expect(screen.queryByRole("link", { name: /Exceção de TE/ })).not.toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /AS-path/ })).not.toBeInTheDocument()
  })

  it("a lista aceita uma linha por vez, com o Enter no meio", async () => {
    // digitar "a", Enter, "b" deixava o campo com "ab": o value saia do array
    // filtrado, e a quebra digitada sumia antes de o proximo caractere entrar
    render(<Montar iniciais={{ prefixos_v4: [] }} />)
    const campo = screen.getByLabelText(/IPv4 \(0\)/)
    await userEvent.type(campo, "45.169.232.0/22{enter}45.169.236.0/23")
    expect(campo).toHaveValue("45.169.232.0/22\n45.169.236.0/23")
    // e o array subiu com as duas, que e o que a contagem no rotulo mostra
    expect(screen.getByLabelText(/IPv4 \(2\)/)).toBeInTheDocument()
  })

  it("esconde o campo que nao pertence ao tipo", () => {
    render(<Montar />)
    expect(screen.queryByLabelText(/ASNs permitidos/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Membros com LP 195/)).not.toBeInTheDocument()
  })

  it("mostra o campo de outro tipo quando ele tem valor guardado, com a nota", () => {
    // o caso da copia: o valor veio do peer copiado e nao pode ficar invisivel
    render(<Montar iniciais={{ ap_allowed: ["15169"], tipo: "cliente" }} />)
    expect(screen.getByLabelText(/ASNs permitidos/)).toHaveValue("15169")
    // a nota e a mesma nos dois campos que o tipo nao usa e que tem valor
    // guardado (o prepend_base do BRANCO tambem e so do upstream, com o "0"
    // dele), entao a assercao ancora no campo, e nao na mensagem solta
    expect(document.querySelector('[data-campo="ap_allowed"]')).toHaveTextContent("o bloco de cliente não usa este campo")
  })

  it("mostra a mensagem do erro embaixo do campo", () => {
    // a mesma mensagem aparece duas vezes de proposito, no resumo do topo e
    // embaixo do campo: a assercao ancora no campo para nao pegar as duas
    render(<Montar erros={{ asn: "ASN ja usado pelo peer BRDIGITAL-20G" }} />)
    expect(document.querySelector('[data-campo="asn"]')).toHaveTextContent("ASN ja usado pelo peer BRDIGITAL-20G")
  })

  it("leva a mensagem da API para o campo da sessao", () => {
    // a chave do erro e a da API ("sessoes.v4.local") e o campo e o da tela
    // ("sessao_v4_local"): sem a traducao o campo apareceria, por causa do
    // erro, e ficaria sem a mensagem embaixo
    render(<Montar erros={{ "sessoes.v4.local": "endereco local obrigatorio" }} />)
    const campo = document.querySelector('[data-campo="sessao_v4_local"]')
    expect(campo).toHaveTextContent("endereco local obrigatorio")
  })

  it("mostra o aviso em ambar, sem tom de erro", () => {
    render(<Montar avisos={[{ campo: "route_limit", mensagem: "route-limit alto para o tipo" }]} />)
    expect(screen.getByText("route-limit alto para o tipo")).toBeInTheDocument()
  })

  it("o aviso aparece mesmo com erro no mesmo campo", () => {
    // a API devolve os dois (route-limit fora da tabela e abaixo do minimo, por
    // exemplo), e nenhum outro lugar da tela desenha aviso: engolir o aviso por
    // causa do erro perde a informacao que o operador precisa ver
    render(
      <Montar
        erros={{ route_limit: "route-limit abaixo do minimo" }}
        avisos={[{ campo: "route_limit", mensagem: "route-limit fora da tabela do tipo" }]}
      />,
    )
    const campo = document.querySelector('[data-campo="route_limit"]')
    expect(campo).toHaveTextContent("route-limit abaixo do minimo")
    expect(campo).toHaveTextContent("route-limit fora da tabela do tipo")
  })

  it("mostra todos os avisos do campo, e nao so o primeiro", () => {
    // As communities fora do plano geram um aviso por valor (o append do
    // _avisa_communities roda dentro do for), e o campo desenhava so o
    // primeiro: o operador corrigia um e o outro seguia escondido
    render(
      <Montar
        avisos={[
          { campo: "communities", mensagem: "community fora do namespace: 64512:50" },
          { campo: "communities", mensagem: "community fora da faixa do plano: 64512:51" },
        ]}
      />,
    )

    const campo = document.querySelector('[data-campo="communities"]')
    expect(campo).toHaveTextContent("community fora do namespace: 64512:50")
    expect(campo).toHaveTextContent("community fora da faixa do plano: 64512:51")
  })

  it("um mapa de campos vazio cai na tabela local", () => {
    // com `??` so, o mapa vazio da API passaria como verdadeiro e o
    // `pertenceAoTipo` responderia true para todo campo com tipo: a visibilidade
    // e a nota parariam de valer sem avisar. O ap_allowed de um cliente e o
    // campo que denuncia, porque so a nota explica a presenca dele
    render(<Montar plano={{ ...PLANO, campos_por_tipo: {} }} iniciais={{ ap_allowed: ["15169"] }} />)
    const campo = document.querySelector('[data-campo="ap_allowed"]')
    expect(campo).toHaveTextContent("o bloco de cliente não usa este campo")
  })

  it("uma entrada por linha, com a contagem no rotulo", () => {
    render(<Montar iniciais={{ prefixos_v4: ["45.169.232.0/22", "45.169.236.0/23"] }} />)
    expect(screen.getByLabelText(/IPv4 \(2\)/)).toHaveValue("45.169.232.0/22\n45.169.236.0/23")
  })

  it("conta os erros em cada secao do indice", () => {
    render(<Montar erros={{ asn: "ja usado", route_limit: "maior que zero" }} />)
    expect(screen.getByRole("link", { name: /Identificação \(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Limites e timers \(1\)/ })).toBeInTheDocument()
  })

  it("trocar a classe leva a origem junto, quando ela ainda e a da classe anterior", async () => {
    render(<Montar iniciais={{ classe: "residencial", origem: "1110" }} />)
    // o select do shadcn e um listbox, e nao um <select>: o clique no gatilho
    // abre a lista, e o valor escolhido aparece no gatilho pelo rotulo
    await userEvent.click(screen.getByLabelText("Classe"))
    await userEvent.click(await screen.findByRole("option", { name: /corporativo/ }))
    // corporativo nao esta na tabela do plano de teste, entao o esperado cai no
    // origem_tipo do cliente. Sem a classe nova dentro do retrato da cascata a
    // origem ficaria em 1110, a da classe que acabou de sair
    expect(screen.getByLabelText("Origem da rota")).toHaveTextContent("1100")
  })

  it("trocar o tipo aplica a cascata nos campos que ainda estao no default", async () => {
    render(<Montar iniciais={{ tipo: "upstream", lp_base: "100", route_limit: "1500000", timer_keepalive: "10", timer_hold: "30" }} />)
    // o select do shadcn e um listbox, e nao um <select>: abre no
    // clique do gatilho e a opcao entra no clique dela
    await userEvent.click(screen.getByLabelText("Tipo"))
    await userEvent.click(await screen.findByRole("option", { name: "cliente" }))
    expect(screen.getByLabelText("LP base")).toHaveValue("300")
    expect(screen.getByLabelText(/route-limit/)).toHaveValue("50")
    expect(screen.getByLabelText("keepalive")).toHaveValue("")
  })

  it("a lista de origem so traz peer do mesmo tipo e ASN, e dono da politica", async () => {
    render(<Montar iniciais={{ tipo: "cliente", asn: "268127" }} />)
    // a lista do listbox so existe aberta: o gatilho abre, e a opcao entra no
    // clique dela
    await userEvent.click(screen.getByLabelText(/reaproveitar/i))
    const opcoes = await screen.findAllByRole("option", { name: /ACME/ })
    // o OUTRO e de outro ASN, o Upstream e de outro tipo, e o ACME-BKP ja
    // reaproveita de alguem
    expect(opcoes.map((o) => o.textContent)).toEqual(["ACME"])
  })

  it("escolher a origem deixa a nota, e nao esconde campo", async () => {
    // a decisao da spec: o operador nao perde de vista o que esta cadastrado
    render(<Montar iniciais={{ tipo: "cliente", asn: "268127" }} />)
    await userEvent.click(screen.getByLabelText(/reaproveitar/i))
    await userEvent.click(await screen.findByRole("option", { name: "ACME" }))
    expect(screen.getByText(/a política vem do peer/i)).toBeInTheDocument()
    expect(screen.getByLabelText("LP base")).toBeInTheDocument()
    expect(screen.getByLabelText(/Origem da rota/)).toBeInTheDocument()
  })

  it("o peer que cede politica avisa que renomear mexe no bloco do outro", async () => {
    // o aviso mora no formulario da origem, que e onde a renomeacao acontece
    render(<Montar iniciais={{ id: "1", tipo: "cliente", asn: "268127" }} />)
    expect(await screen.findByText(/um peer reaproveita a política deste/i))
      .toBeInTheDocument()
  })

  it("a origem escolhida volta a ser nenhuma pela opcao vazia", async () => {
    // sem ela o reaproveitamento seria porta de mao unica na tela: voltar
    // atras so pela API, que e o caminho que esta tela existe para fechar
    render(<Montar iniciais={{ tipo: "cliente", asn: "268127", politica_de: "1" }} />)
    expect(screen.getByText(/a política vem do peer/i)).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText(/reaproveitar/i))
    await userEvent.click(await screen.findByRole("option", { name: /carrega a própria política/ }))
    expect(screen.queryByText(/a política vem do peer/i)).not.toBeInTheDocument()
    // o gatilho mostra a opcao vazia, e nao um numero solto: o valor do
    // formulario voltou para o vazio
    expect(screen.getByLabelText(/reaproveitar/i)).toHaveTextContent("— carrega a própria política —")
  })

  it("trocar o tipo limpa a origem que nao vale no par novo", async () => {
    // o id velho ficaria como opcao fora da lista - um numero solto no gatilho,
    // sem nota - e o operador so saberia no salvar
    render(<Montar iniciais={{ tipo: "cliente", asn: "268127", politica_de: "1" }} />)
    await userEvent.click(screen.getByLabelText("Tipo"))
    await userEvent.click(await screen.findByRole("option", { name: "upstream" }))
    expect(screen.getByLabelText(/reaproveitar/i)).toHaveTextContent("— carrega a própria política —")
  })

  it("trocar o ASN limpa a origem escolhida", async () => {
    render(<Montar iniciais={{ tipo: "cliente", asn: "268127", politica_de: "1" }} />)
    const campo = screen.getByLabelText("ASN")
    await userEvent.clear(campo)
    await userEvent.type(campo, "268128")
    // o par novo e outro (o OUTRO e do ASN novo, e nao o escolhido), entao a
    // escolha antiga saiu
    expect(screen.getByLabelText(/reaproveitar/i)).toHaveTextContent("— carrega a própria política —")
  })

  it("o erro do reaproveitamento conta na secao e aparece no campo", () => {
    // a chave da API e o nome do campo sao o mesmo, mas sem a entrada na
    // tabela de secoes nem o badge do indice nem o painel de saida viam a
    // recusa: o painel ficava mudo, porque a previa volta 200 e sem bloco
    render(<Montar erros={{ politica_de: "peer de origem nao encontrado" }} />)
    expect(screen.getByRole("link", { name: /Identificação \(1\)/ })).toBeInTheDocument()
    expect(document.querySelector('[data-campo="politica_de"]'))
      .toHaveTextContent("peer de origem nao encontrado")
  })

  it("o peer de id 0 e origem como as outras, e nao o formulario novo", async () => {
    // Number("") e 0, e o id 0 existe: sem a guarda do id vazio o formulario
    // novo se veria como o peer de id 0, o esconderia da lista e acharia que
    // ele reaproveita deste formulario
    const peers: PeerResumo[] = [
      { id: 0, token: "ZERO", tipo: "cliente", asn: 268127, apelido: "ZERO",
        nome: "Cliente ZERO", grupo_id: null, politica_de: null },
      { id: 5, token: "ZERO-BKP", tipo: "cliente", asn: 268127, apelido: "ZERO-BKP",
        nome: "Cliente ZERO BKP", grupo_id: null, politica_de: 0 },
    ]
    render(<Montar iniciais={{ id: "", tipo: "cliente", asn: "268127" }} peers={peers} />)
    await userEvent.click(screen.getByLabelText(/reaproveitar/i))
    const opcoes = await screen.findAllByRole("option", { name: /ZERO/ })
    // o ZERO-BKP ja reaproveita, entao so o ZERO se oferece
    expect(opcoes.map((o) => o.textContent)).toEqual(["ZERO"])
    expect(document.querySelector('[data-campo="apelido"]')).not.toHaveTextContent(/reaproveita/)
  })
})
