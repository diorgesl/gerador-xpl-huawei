import { opcoesPorTipo, opcoesUsadas } from "@/lib/campos"
import type { Campo } from "@/telas/peers/camposPeer"
import type { GrupoForm } from "@/api/consultas"

// O grupo nao tem route_limit nem sessoes: o membro e quem tem os dois. O
// prepend_base e texto livre aqui, e nao o select do peer, como na tela antiga.
// Na classe o rotulo e so o nome, sem a community: tambem como a tela antiga.
export const CAMPOS_GRUPO: Campo[] = [
  { nome: "nome", rotulo: "Nome", tipo: "texto", secao: "identificacao", mono: true,
    ajuda: "vira o nome do group no equipamento" },
  { nome: "tipo", rotulo: "Tipo", tipo: "select", secao: "identificacao",
    opcoes: (ctx) => ctx.plano.tipos.map((t) => ({ valor: t, rotulo: t })) },
  { nome: "asn", rotulo: "ASN", tipo: "texto", secao: "identificacao", mono: true,
    ajuda: "em branco, cada membro declara o próprio" },

  { nome: "classe", rotulo: "Classe", tipo: "select", secao: "downstream",
    opcoes: (ctx) => [
      { valor: "", rotulo: "— sem classe —" },
      ...ctx.plano.classes_cliente.map((c) => ({ valor: c, rotulo: c })),
    ] },
  { nome: "pop", rotulo: "POP", tipo: "combo", secao: "downstream", mono: true,
    placeholder: (ctx) => String(ctx.plano.pop_min), opcoes: (ctx) => opcoesUsadas(ctx.plano.pop_usados) },

  { nome: "origem", rotulo: "Origem da rota", tipo: "select", secao: "politica",
    ajuda: "a lista muda com o tipo", rotuloForaDaLista: " - fora da tabela do tipo",
    opcoes: (ctx) => {
      const codigos = ctx.plano.padroes.origens_por_tipo[ctx.tipo]
        ?? Object.keys(ctx.plano.padroes.origem_nome).map(Number)
      return codigos.map((c) => ({
        valor: String(c),
        rotulo: `${c} - ${ctx.plano.padroes.origem_nome[String(c)] ?? "fora da tabela do tipo"}`,
      }))
    } },
  { nome: "lp_base", rotulo: "LP base", tipo: "combo", secao: "politica", mono: true,
    ajuda: "o membro sem LP próprio usa este", opcoes: (ctx) => opcoesPorTipo(ctx.plano.lp_base) },
  { nome: "default_route", rotulo: "Anuncia default route", tipo: "caixa", secao: "politica" },

  { nome: "timer_keepalive", rotulo: "keepalive", tipo: "texto", secao: "limites", mono: true },
  { nome: "timer_hold", rotulo: "hold", tipo: "texto", secao: "limites", mono: true,
    ajuda: "em branco, o equipamento usa o default dele" },
  { nome: "bfd", rotulo: "BFD", tipo: "caixa", secao: "limites" },
  { nome: "graceful_restart", rotulo: "Graceful restart", tipo: "caixa", secao: "limites" },

  { nome: "aprendizado", rotulo: "Ponto de aprendizado", tipo: "combo", secao: "upstream", mono: true,
    opcoes: (ctx) => opcoesUsadas(ctx.plano.aprendizado_usados) },
  { nome: "bh_upstream", rotulo: "Blackhole do upstream", tipo: "texto", secao: "upstream", mono: true },
  { nome: "prepend_base", rotulo: "Prepend base", tipo: "texto", secao: "upstream", mono: true },
  { nome: "ap_block", rotulo: "ASNs bloqueados", tipo: "area", secao: "upstream", mono: true, linhas: 3 },
  { nome: "ap_te", rotulo: "ASNs com TE preferencial", tipo: "area", secao: "upstream", mono: true, linhas: 3 },
  { nome: "te_prefixos_v4", rotulo: "PL-TE-PREFER v4", tipo: "area", secao: "upstream", mono: true, linhas: 3 },
  { nome: "te_prefixos_v6", rotulo: "PL-TE-PREFER v6", tipo: "area", secao: "upstream", mono: true, linhas: 3 },
  { nome: "communities", rotulo: "communities", tipo: "area", secao: "upstream", mono: true, linhas: 3 },
  { nome: "large_communities", rotulo: "large-communities", tipo: "area", secao: "upstream", mono: true, linhas: 3 },

  { nome: "aprendizado_ix", rotulo: "Ponto de aprendizado do IX", tipo: "combo", secao: "ix", mono: true,
    opcoes: (ctx) => opcoesUsadas(ctx.plano.aprendizado_usados) },
  { nome: "ix_id", rotulo: "ID do IX no PeeringDB", tipo: "texto", secao: "ix", mono: true },
  { nome: "ap_prefer", rotulo: "Membros com LP 195", tipo: "area", secao: "ix", mono: true, linhas: 3 },

  { nome: "ap_allowed", rotulo: "ASNs permitidos", tipo: "area", secao: "pni", mono: true, linhas: 3 },

  { nome: "prefixos_v4", rotulo: "IPv4", tipo: "area", secao: "prefixos", mono: true, linhas: 5 },
  { nome: "prefixos_v6", rotulo: "IPv6", tipo: "area", secao: "prefixos", mono: true, linhas: 5 },
]

export const CAMPO_BRANCO_GRUPO: GrupoForm = {
  id: "", nome: "", tipo: "parceiro", asn: "", classe: "", lp_base: "300",
  origem: "1100", pop: "", aprendizado: "", aprendizado_ix: "", ix_id: "",
  prepend_base: "0", timer_keepalive: "", timer_hold: "", bfd: true,
  graceful_restart: true, default_route: false, bh_upstream: "",
  prefixos_v4: [], prefixos_v6: [], te_prefixos_v4: [], te_prefixos_v6: [],
  ap_block: [], ap_te: [], ap_allowed: [], ap_prefer: [],
  communities: [], large_communities: [],
}
