import { namespace, opcoesPorTipo, opcoesUsadas, type Opcao } from "@/lib/campos"
import type { PeerForm, Plano } from "@/api/consultas"

// O `Opcao` sai daqui junto dos tipos de campo: o `Formulario` e o
// `FormularioPeer` o importam deste arquivo, e o campos.ts e anterior a ele.
export type { Opcao }

export type TipoCampo = "texto" | "select" | "combo" | "area" | "caixa"

// A forma de um campo: o que ele e, como se desenha e de que secao faz parte.
// Os quatro tipos moram aqui, e nao no lib/campos.ts, porque dependem do Plano
// da API: este arquivo nasce depois dele, e o campos.ts nasce antes.
export type Contexto = {
  plano: Plano
  tipo: string
  grupos: Opcao[]
  // as origens possiveis do reaproveitamento. Sai da lista de peers e nao do
  // /api/plano: o filtro depende do tipo e do ASN que o formulario tem agora,
  // e quem tem os dois e a tela
  origens: Opcao[]
}

export type Campo = {
  nome: string
  rotulo: string
  tipo: TipoCampo
  secao: string
  ajuda?: string
  mono?: boolean
  largo?: boolean
  linhas?: number
  // a funcao existe porque a tabela e um modulo, e o POP_MIN so e conhecido
  // quando o /api/plano chega
  placeholder?: string | ((ctx: Contexto) => string)
  opcoes?: (ctx: Contexto) => Opcao[]
  // a lista de origens candidatas sai dos peers ja cadastrados, e nao do
  // /api/plano: o filtro depende do tipo e do ASN que o formulario tem
  // agora, e so a tela tem a lista
  origens?: boolean
  // sufixo da opcao que representa um valor guardado fora da lista do tipo, o
  // que a tela antiga escrevia na origem: "1900 - fora da tabela do tipo"
  rotuloForaDaLista?: string
  // a chave do /api/plano de onde sai a busca de communities. O campo
  // declara de onde le, e nao so que le: sem isso o formulario teria que
  // adivinhar que `large_communities` le a lista `large_communities`
  sugestoes?: "communities" | "large_communities"
}

// As opcoes de cada select saem do /api/plano, e nao de uma tabela escrita a
// mao aqui: e a mesma fonte que a tela antiga lia.

// A ordem aqui e a ordem na tela, secao por secao. O que decide se o campo
// aparece e o /api/plano (campos_por_tipo) mais a regra do visivel; esta
// tabela so diz como cada um se desenha. ASN, IP, prefixo e community vao em
// fonte mono, como manda a regra de tipografia.
export const CAMPOS_PEER: Campo[] = [
  { nome: "apelido", rotulo: "Apelido", tipo: "texto", secao: "identificacao", mono: true,
    ajuda: "entra no lugar do ASN no nome dos objetos" },
  { nome: "id", rotulo: "ID", tipo: "texto", secao: "identificacao", mono: true,
    ajuda: "0 a 99, e o mesmo espaço dos grupos" },
  { nome: "nome", rotulo: "Nome", tipo: "texto", secao: "identificacao",
    ajuda: "vai no campo description da sessão" },
  { nome: "tipo", rotulo: "Tipo", tipo: "select", secao: "identificacao",
    opcoes: (ctx) => ctx.plano.tipos.map((t) => ({ valor: t, rotulo: t })) },
  { nome: "grupo_id", rotulo: "Grupo", tipo: "select", secao: "identificacao",
    ajuda: "sem grupo, o peer declara a própria política",
    opcoes: (ctx) => [{ valor: "", rotulo: "— sem grupo —" }, ...ctx.grupos] },
  { nome: "asn", rotulo: "ASN", tipo: "texto", secao: "identificacao", mono: true },
  { nome: "descricao", rotulo: "Descrição", tipo: "texto", secao: "identificacao", largo: true },

  { nome: "politica_de", rotulo: "Reaproveitar a política de", tipo: "select", secao: "identificacao",
    origens: true,
    ajuda: "o segundo link de um cliente usa a política do primeiro: nenhum filtro é gerado de novo" },
  { nome: "classe", rotulo: "Classe", tipo: "select", secao: "politica",
    opcoes: (ctx) => [
      { valor: "", rotulo: "—" },
      ...ctx.plano.classes_cliente.map((c) => ({
        valor: c,
        rotulo: `${c} - ${namespace(ctx.plano.rede)}:${ctx.plano.padroes.origem_classe[c]}`,
      })),
    ] },
  { nome: "lp_base", rotulo: "LP base", tipo: "combo", secao: "politica", mono: true,
    opcoes: (ctx) => opcoesPorTipo(ctx.plano.lp_base) },
  { nome: "origem", rotulo: "Origem da rota", tipo: "select", secao: "politica",
    rotuloForaDaLista: " - fora da tabela do tipo",
    opcoes: (ctx) => {
      // a lista muda com o tipo: e a mesma cascata de hoje, lida do /api/plano
      const codigos = ctx.plano.padroes.origens_por_tipo[ctx.tipo]
        ?? Object.keys(ctx.plano.padroes.origem_nome).map(Number)
      return codigos.map((c) => ({
        valor: String(c),
        rotulo: `${c} - ${ctx.plano.padroes.origem_nome[String(c)] ?? "fora da tabela do tipo"}`,
      }))
    } },
  { nome: "pop", rotulo: "POP", tipo: "combo", secao: "politica", mono: true,
    placeholder: (ctx) => String(ctx.plano.pop_min), opcoes: (ctx) => opcoesUsadas(ctx.plano.pop_usados) },
  { nome: "aprendizado", rotulo: "Ponto de aprendizado", tipo: "combo", secao: "politica", mono: true,
    opcoes: (ctx) => opcoesUsadas(ctx.plano.aprendizado_usados) },
  { nome: "ix_id", rotulo: "ID do IX no PeeringDB", tipo: "texto", secao: "politica", mono: true },

  { nome: "route_limit", rotulo: "route-limit", tipo: "combo", secao: "limites", mono: true,
    opcoes: (ctx) => opcoesPorTipo(ctx.plano.route_limit) },
  { nome: "prepend_base", rotulo: "Prepend base", tipo: "select", secao: "limites",
    opcoes: (ctx) => {
      // 0 a PREPEND_MAX; acima do implementado o rotulo avisa que o ramo nao existe
      return Array.from({ length: ctx.plano.prepend_max + 1 }, (_, n) => ({
        valor: String(n),
        rotulo: n === 0
          ? "0 - sem prepend (P1)"
          : `${n} - ${n} prepend(s) (P${n + 1})` +
            (n > ctx.plano.prepend_implementado ? " - reservado, sem ramo nos filtros" : ""),
      }))
    } },
  { nome: "timer_keepalive", rotulo: "keepalive", tipo: "texto", secao: "limites", mono: true },
  { nome: "timer_hold", rotulo: "hold", tipo: "texto", secao: "limites", mono: true,
    ajuda: "em branco, o equipamento usa o default dele" },
  { nome: "bfd", rotulo: "BFD", tipo: "caixa", secao: "limites" },
  { nome: "graceful_restart", rotulo: "Graceful restart", tipo: "caixa", secao: "limites" },
  { nome: "default_route", rotulo: "Anuncia default route", tipo: "caixa", secao: "limites" },
  { nome: "bh_upstream", rotulo: "Blackhole do upstream", tipo: "texto", secao: "limites", mono: true, largo: true },

  { nome: "prefixos_v4", rotulo: "IPv4", tipo: "area", secao: "prefixos", mono: true, linhas: 5,
    ajuda: "uma linha por prefixo: cidr, intervalo opcional (-24) e as communities. sem intervalo, só o prefixo exato; começada por !-, a linha fica fora do anúncio" },
  { nome: "prefixos_v6", rotulo: "IPv6", tipo: "area", secao: "prefixos", mono: true, linhas: 5,
    ajuda: "uma linha por prefixo: cidr, intervalo opcional (-48) e as communities. sem intervalo, só o prefixo exato; começada por !-, a linha fica fora do anúncio" },

  { nome: "te_prefixos_v4", rotulo: "Exceção de TE IPv4", tipo: "area", secao: "te", mono: true, linhas: 3 },
  { nome: "te_prefixos_v6", rotulo: "Exceção de TE IPv6", tipo: "area", secao: "te", mono: true, linhas: 3 },

  { nome: "ap_block", rotulo: "ASNs bloqueados", tipo: "area", secao: "aspath", mono: true, linhas: 3 },
  { nome: "ap_te", rotulo: "ASNs com TE preferencial", tipo: "area", secao: "aspath", mono: true, linhas: 3 },
  { nome: "ap_allowed", rotulo: "ASNs permitidos", tipo: "area", secao: "aspath", mono: true, linhas: 3 },
  { nome: "ap_prefer", rotulo: "Membros com LP 195", tipo: "area", secao: "aspath", mono: true, linhas: 3 },

  { nome: "communities", rotulo: "communities", tipo: "area", secao: "clpeer", mono: true, linhas: 3,
    sugestoes: "communities",
    ajuda: "a community que este peer recebe além do que o plano já manda" },
  { nome: "large_communities", rotulo: "large-communities", tipo: "area", secao: "clpeer", mono: true, linhas: 3,
    sugestoes: "large_communities",
    ajuda: "RFC 8195, três campos: namespace, função e ASN" },

  { nome: "sessao_v4_local", rotulo: "IPv4 local", tipo: "texto", secao: "sessoes", mono: true },
  { nome: "sessao_v4_remoto", rotulo: "IPv4 remoto", tipo: "texto", secao: "sessoes", mono: true },
  { nome: "sessao_v6_local", rotulo: "IPv6 local", tipo: "texto", secao: "sessoes", mono: true },
  { nome: "sessao_v6_remoto", rotulo: "IPv6 remoto", tipo: "texto", secao: "sessoes", mono: true },
]

/** O formulario vazio, com os defaults que a API tambem usa. */
export const CAMPO_BRANCO: PeerForm = {
  id: "", apelido: "", nome: "", tipo: "cliente", grupo_id: "", politica_de: "", asn: "", descricao: "",
  classe: "", lp_base: "300", origem: "1100", pop: "", aprendizado: "", ix_id: "",
  route_limit: "50", prepend_base: "0", timer_keepalive: "", timer_hold: "",
  bfd: true, graceful_restart: true, default_route: false, bh_upstream: "",
  prefixos_v4: [], prefixos_v6: [], te_prefixos_v4: [], te_prefixos_v6: [],
  ap_block: [], ap_te: [], ap_allowed: [], ap_prefer: [],
  communities: [], large_communities: [],
  sessao_v4_local: "", sessao_v4_remoto: "", sessao_v6_local: "", sessao_v6_remoto: "",
}
