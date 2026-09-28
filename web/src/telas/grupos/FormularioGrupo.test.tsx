import { render, screen } from "@testing-library/react"
import { useForm } from "react-hook-form"
import { describe, expect, it, vi } from "vitest"
import { Provedores } from "@/app/provedores"
import type { GrupoForm, Plano } from "@/api/consultas"
import { FormularioGrupo } from "./FormularioGrupo"
import { CAMPO_BRANCO_GRUPO } from "./camposGrupo"

const PLANO = {
  rede: { asn: "64512", politica: "65532" },
  padroes: {
    tipos: {
      parceiro: { lp_base: 300, route_limit: 50, timer_keepalive: null, timer_hold: null },
      upstream: { lp_base: 100, route_limit: 1500000, timer_keepalive: 10, timer_hold: 30 },
      ix: { lp_base: 190, route_limit: 500000, timer_keepalive: null, timer_hold: null },
    },
    origem_tipo: { parceiro: 1100, upstream: 1400, ix: 1300 },
    origem_classe: { transito: 1100, residencial: 1110 },
    downstream: ["cliente", "parceiro"],
    origens_por_tipo: {}, origem_nome: { 1100: "cliente de transito" },
  },
  tipos: ["cliente", "parceiro", "upstream", "ix", "pni"],
  tipos_com_criar_lista: ["cliente", "parceiro", "upstream"],
  classes_cliente: ["transito", "residencial"],
  lp_base: { upstream: 100, ix: 190 }, route_limit: {}, route_limit_exemplo: {},
  prepend_max: 6, prepend_implementado: 3,
  pop_min: 2001, pop_max: 2999, aprendizado_min: 3000, aprendizado_max: 3999,
  pop_usados: [], aprendizado_usados: [],
  campos_por_tipo: {},
  campos_por_tipo_grupo: {
    classe: ["cliente", "parceiro"], pop: ["cliente", "parceiro"],
    default_route: ["cliente", "parceiro"], aprendizado: ["upstream"],
    aprendizado_ix: ["ix"], prepend_base: ["upstream"], bh_upstream: ["upstream"],
    ap_block: ["upstream"], ap_te: ["upstream"], te_prefixos_v4: ["upstream"],
    te_prefixos_v6: ["upstream"], communities: ["upstream"], large_communities: ["upstream"],
    ix_id: ["ix"], ap_prefer: ["ix"], ap_allowed: ["pni"],
  },
  sugestoes: { communities: [], large_communities: [] },
} satisfies Plano

function Montar({ iniciais = {}, erros = {} }: { iniciais?: Partial<GrupoForm>; erros?: Record<string, string> }) {
  const form = useForm<GrupoForm>({ defaultValues: { ...CAMPO_BRANCO_GRUPO, ...iniciais } })
  return (
    <Provedores>
      <FormularioGrupo form={form} plano={PLANO} erros={erros} avisos={[]} aoIrPara={vi.fn()} />
    </Provedores>
  )
}

describe("o formulario do grupo", () => {
  it("no tipo IX o aprendizado e o do bloco do IX, e o comum nao aparece", () => {
    render(<Montar iniciais={{ tipo: "ix" }} />)
    expect(screen.getByLabelText(/^Ponto de aprendizado do IX/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/^Ponto de aprendizado$/)).not.toBeInTheDocument()
  })

  it("no tipo upstream e o contrario", () => {
    render(<Montar iniciais={{ tipo: "upstream" }} />)
    expect(screen.getByLabelText(/^Ponto de aprendizado$/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/Ponto de aprendizado do IX/)).not.toBeInTheDocument()
  })

  it("o erro do aprendizado marca o campo do bloco certo", () => {
    render(<Montar iniciais={{ tipo: "ix" }} erros={{ aprendizado: "ponto de aprendizado 3xxx obrigatorio" }} />)
    const campo = screen.getByLabelText(/^Ponto de aprendizado do IX/).closest("[data-campo]")
    expect(campo).toHaveTextContent("ponto de aprendizado 3xxx obrigatorio")
  })

  it("nao tem campo de route-limit nem de sessao: o grupo nao tem nenhum dos dois", () => {
    render(<Montar iniciais={{ tipo: "upstream" }} />)
    expect(screen.queryByLabelText(/route-limit/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/IPv4 local/)).not.toBeInTheDocument()
  })

  it("nao mostra as secoes de outro tipo", () => {
    render(<Montar iniciais={{ tipo: "pni" }} />)
    expect(screen.getByLabelText(/ASNs permitidos/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/Membros com LP 195/)).not.toBeInTheDocument()
  })
})
