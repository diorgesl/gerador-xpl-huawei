import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useForm } from "react-hook-form"
import { describe, expect, it, vi } from "vitest"
import { Provedores } from "@/app/provedores"
import type { PeerForm, Plano } from "@/api/consultas"
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
} as unknown as Plano

const BRANCO: PeerForm = {
  id: "7", apelido: "", nome: "Cliente ACME", tipo: "cliente", grupo_id: "",
  asn: "268127", descricao: "", classe: "residencial", lp_base: "300", origem: "1110",
  pop: "2001", aprendizado: "", ix_id: "", route_limit: "50", prepend_base: "0",
  timer_keepalive: "", timer_hold: "", bfd: true, graceful_restart: true,
  default_route: false, bh_upstream: "", prefixos_v4: ["45.169.232.0/22"], prefixos_v6: [],
  te_prefixos_v4: [], te_prefixos_v6: [], ap_block: [], ap_te: [], ap_allowed: [],
  ap_prefer: [], communities: [], large_communities: [],
  sessao_v4_local: "198.51.100.1", sessao_v4_remoto: "198.51.100.2",
  sessao_v6_local: "", sessao_v6_remoto: "",
}

function Montar({ iniciais = {}, erros = {}, avisos = [] }: {
  iniciais?: Partial<PeerForm>
  erros?: Record<string, string>
  avisos?: { campo: string; mensagem: string }[]
}) {
  const form = useForm<PeerForm>({ defaultValues: { ...BRANCO, ...iniciais } })
  return (
    <Provedores>
      <FormularioPeer form={form} plano={PLANO} grupos={[]} erros={erros} avisos={avisos} aoIrPara={vi.fn()} />
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
})
