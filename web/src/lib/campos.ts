// O que o formulario mostra e o que cada erro aponta. A tabela de campos por
// tipo vem da API (/api/plano, servida de form.CAMPOS_POR_TIPO), e e ELA que a
// tela usa: o formulario so monta depois que o plano chegou. A copia abaixo
// existe para o teste deste modulo rodar sem servidor, e nao chega ao
// operador. Se a tabela do Python mudar, quem sente primeiro e a tela (que le
// a da API) e nao este arquivo.
//
// A copia do grupo e montada por espalhamento, entao a ORDEM das chaves e
// diferente da do dicionario do Python; o conteudo e o mesmo.
export type Valor = string | string[] | boolean
export type Valores = Record<string, Valor>
export type Erros = Record<string, string>
export type Padroes = {
  tipos: Record<string, { lp_base: number | null; route_limit: number | null;
                          timer_keepalive: number | null; timer_hold: number | null }>
  origem_tipo: Record<string, number>
  origem_classe: Record<string, number>
  downstream: string[]
  origens_por_tipo: Record<string, number[]>
  origem_nome: Record<string, string>
}

export const CAMPOS_POR_TIPO: Record<string, string[]> = {
  classe: ["cliente", "parceiro"],
  pop: ["cliente", "parceiro"],
  default_route: ["cliente", "parceiro"],
  aprendizado: ["upstream", "ix"],
  prepend_base: ["upstream"],
  bh_upstream: ["upstream"],
  ap_block: ["upstream"],
  ap_te: ["upstream"],
  te_prefixos_v4: ["upstream"],
  te_prefixos_v6: ["upstream"],
  ix_id: ["ix"],
  ap_prefer: ["ix"],
  ap_allowed: ["pni"],
  communities: ["cliente", "parceiro", "upstream"],
  large_communities: ["cliente", "parceiro", "upstream"],
}

export const CAMPOS_POR_TIPO_GRUPO: Record<string, string[]> = {
  ...CAMPOS_POR_TIPO,
  aprendizado: ["upstream"],
  aprendizado_ix: ["ix"],
  communities: ["upstream"],
  large_communities: ["upstream"],
}

export const CASCATA_PEER = ["lp_base", "route_limit", "timer_keepalive", "timer_hold"]
export const CASCATA_GRUPO = ["lp_base", "timer_keepalive", "timer_hold"]

// As opcoes de varios selects saem da tabela do plano e do que ja esta
// cadastrado. Ficam aqui, e nao em cada tabela de tela, porque o peer e o
// grupo montam as mesmas listas.
export const opcoesPorTipo = (mapa: Record<string, number>): Opcao[] =>
  Object.entries(mapa).map(([tipo, valor]) => ({ valor: String(valor), rotulo: tipo }))

export const opcoesUsadas = (valores: number[]): Opcao[] =>
  valores.map((v) => ({ valor: String(v), rotulo: "já cadastrado" }))

/**
 * O namespace das standard: o `politica` quando ha um, senao o proprio ASN.
 * Recebe o `rede` e nao o plano inteiro de proposito: este arquivo nasce na
 * Task 5, antes do tipo Plano, e o formato de que ele precisa e so este.
 */
export const namespace = (rede: { asn: string; politica: string }): string =>
  rede.politica || rede.asn

export type Secao = { id: string; rotulo: string; campos: string[] }

// A forma de um campo da tela mora no camposPeer.ts (Task 10), junto da
// tabela: ela depende do tipo Plano, que nasce na Task 6, e este arquivo
// nasce na Task 5.

// Duas formas de lista de select que o peer e o grupo montam igual.
export type Opcao = { valor: string; rotulo: string }

export const SECOES_PEER: Secao[] = [
  { id: "identificacao", rotulo: "Identificação", campos: ["id", "apelido", "nome", "tipo", "grupo_id", "asn", "descricao"] },
  { id: "politica", rotulo: "Política", campos: ["classe", "lp_base", "origem", "pop", "aprendizado", "ix_id"] },
  { id: "limites", rotulo: "Limites e timers", campos: ["route_limit", "prepend_base", "timer_keepalive", "timer_hold", "bfd", "graceful_restart", "default_route", "bh_upstream"] },
  { id: "prefixos", rotulo: "Prefixos anunciados", campos: ["prefixos_v4", "prefixos_v6"] },
  { id: "te", rotulo: "Exceção de TE", campos: ["te_prefixos_v4", "te_prefixos_v6"] },
  { id: "aspath", rotulo: "AS-path", campos: ["ap_block", "ap_te", "ap_allowed", "ap_prefer"] },
  { id: "clpeer", rotulo: "CL-PEER", campos: ["communities", "large_communities"] },
  { id: "sessoes", rotulo: "Sessões", campos: ["sessao_v4_local", "sessao_v4_remoto", "sessao_v6_local", "sessao_v6_remoto"] },
]

export const SECOES_GRUPO: Secao[] = [
  { id: "identificacao", rotulo: "Identificação", campos: ["nome", "tipo", "asn"] },
  { id: "downstream", rotulo: "Downstream", campos: ["classe", "pop"] },
  { id: "politica", rotulo: "Política", campos: ["origem", "lp_base", "default_route"] },
  { id: "limites", rotulo: "Limites e timers", campos: ["timer_keepalive", "timer_hold", "bfd", "graceful_restart"] },
  { id: "upstream", rotulo: "Upstream", campos: ["aprendizado", "bh_upstream", "prepend_base", "ap_block", "ap_te", "te_prefixos_v4", "te_prefixos_v6", "communities", "large_communities"] },
  { id: "ix", rotulo: "IX", campos: ["aprendizado_ix", "ix_id", "ap_prefer"] },
  { id: "pni", rotulo: "PNI", campos: ["ap_allowed"] },
  { id: "prefixos", rotulo: "Prefixos do grupo", campos: ["prefixos_v4", "prefixos_v6"] },
]

// A chave do erro da API para os campos do formulario. A API fala a lingua do
// validate.py ("sessoes.v4.local"), e o formulario fala a lingua da tela
// ("sessao_v4_local"): este mapa e a unica traducao entre as duas.
const ERRO_PARA_CAMPO: Record<string, string[]> = {
  "sessoes.v4.local": ["sessao_v4_local"],
  "sessoes.v4.remoto": ["sessao_v4_remoto"],
  "sessoes.v6.local": ["sessao_v6_local"],
  "sessoes.v6.remoto": ["sessao_v6_remoto"],
  sessoes: ["sessao_v4_local", "sessao_v4_remoto", "sessao_v6_local", "sessao_v6_remoto"],
  prefixos: ["prefixos_v4", "prefixos_v6"],
  te_prefixos: ["te_prefixos_v4", "te_prefixos_v6"],
}

// Sem campo nenhum: o resumo mostra, nenhum input marca. As quatro primeiras
// sao chaves que a API realmente emite (a falha do bgpq4, o corpo malformado,
// o 404 e o 409 do grupo com membros).
//
// `confirmado` esta aqui por decisao: a tela antiga tinha uma caixa com esse
// nome e o erro embaixo dela, e a API nova nao pede mais nada disso (a
// confirmacao virou dialogo e o DELETE nao le campo nenhum). A chave fica
// mapeada por precaucao, porque o custo e zero e o efeito de nao estar e o
// resumo mandar o operador clicar num campo que nao existe.
const SEM_CAMPO = ["bgpq4", "_corpo", "_", "membros", "confirmado"]

export function camposDoErro(chave: string, tipo: string, deGrupo = false): string[] {
  if (SEM_CAMPO.includes(chave)) return []
  const daTela = (deGrupo ? SECOES_GRUPO : SECOES_PEER).flatMap((s) => s.campos)
  const eCampo = (campo: string) => daTela.includes(campo)
  if (ERRO_PARA_CAMPO[chave]) return ERRO_PARA_CAMPO[chave].filter(eCampo)
  // no grupo do IX o aprendizado mora no campo do bloco do IX: a tela antiga
  // tinha a mesma volta, com a ancora trocando pelo tipo
  if (deGrupo && chave === "aprendizado" && tipo === "ix") return ["aprendizado_ix"]
  // Chave que nao e campo DESTE formulario nao vira campo: o `id` existe no
  // peer e nao no grupo, e uma chave nova do backend nao existe em nenhum.
  // Sem esta guarda o resumo prometia um link que nao levava a lugar nenhum e
  // o painel de saida fechava sem desenhar campo
  return eCampo(chave) ? [chave] : []
}

export function campoDoErro(chave: string, tipo: string, deGrupo = false): string | null {
  return camposDoErro(chave, tipo, deGrupo)[0] ?? null
}

export function temValor(valor: Valor | undefined): boolean {
  if (valor === undefined || valor === null) return false
  if (typeof valor === "string") return valor.trim() !== ""
  if (Array.isArray(valor)) return valor.some((v) => v.trim() !== "")
  return valor
}

export function pertenceAoTipo(nome: string, camposPorTipo: Record<string, string[]>, tipo: string): boolean {
  const tipos = camposPorTipo[nome]
  return tipos === undefined || tipos.includes(tipo)
}

/**
 * Um campo aparece quando pertence ao tipo, quando tem erro ou quando tem
 * valor. A ultima condicao e o que impede um dado gravado de ficar guardado e
 * invisivel, numa copia ou depois de trocar o tipo.
 */
export function visivel(nome: string, valores: Valores, erros: Erros,
                        camposPorTipo: Record<string, string[]>, tipo: string,
                        deGrupo = false): boolean {
  if (pertenceAoTipo(nome, camposPorTipo, tipo)) return true
  for (const chave of Object.keys(erros)) {
    if (erros[chave] && camposDoErro(chave, tipo, deGrupo).includes(nome)) return true
  }
  return temValor(valores[nome])
}

/**
 * A mensagem que aparece embaixo do campo. A chave do erro e a da API
 * ("sessoes.v4.local") e o campo e o da tela ("sessao_v4_local"), entao a
 * chave direta so vale quando as duas coincidem ("asn") e o resto sai do mapa
 * de campos, o mesmo que o resumo e o `visivel` ja usam. Sem isto o campo da
 * sessao aparece por causa do erro e fica sem a mensagem embaixo.
 */
export function erroDoCampo(nome: string, erros: Erros, tipo: string,
                            deGrupo = false): string | undefined {
  if (erros[nome]) return erros[nome]
  for (const [chave, mensagem] of Object.entries(erros)) {
    if (mensagem && camposDoErro(chave, tipo, deGrupo).includes(nome)) return mensagem
  }
  return undefined
}

export function secoesComErro(erros: Erros, tipo: string, deGrupo: boolean, secoes = deGrupo ? SECOES_GRUPO : SECOES_PEER) {
  const contagem: Record<string, number> = {}
  for (const s of secoes) contagem[s.id] = 0
  for (const [chave, mensagem] of Object.entries(erros)) {
    if (!mensagem) continue
    for (const campo of camposDoErro(chave, tipo, deGrupo)) {
      const secao = secoes.find((s) => s.campos.includes(campo))
      if (secao) {
        contagem[secao.id] += 1
        break
      }
    }
  }
  return contagem
}

const texto = (v: unknown) => (v === null || v === undefined ? "" : String(v))

export function origemEsperada(tipo: string, classe: string, padroes: Padroes): number {
  if (padroes.downstream.includes(tipo) && padroes.origem_classe[classe] !== undefined) {
    return padroes.origem_classe[classe]
  }
  return padroes.origem_tipo[tipo] ?? padroes.origem_tipo.cliente ?? 1100
}

/**
 * A regra da cascata da tela antiga, nas duas partes dela: (1) ao trocar o
 * tipo, o campo que ainda estiver no default do tipo anterior passa para o
 * default do novo, e o que o operador digitou por cima fica; (2) a origem
 * segue a mesma ideia ao contrario: ela so e trocada se nao valer no tipo
 * novo, porque a lista de origens validas muda com o tipo e as listas se
 * sobrepoem.
 *
 * Devolve uma copia do formulario inteiro, com os campos que a cascata tocou
 * ja com o valor novo, e nao so as chaves que mudaram, porque quem chama
 * escreve de volta o objeto todo no formulario.
 */
export function cascata(tipoAntes: string, tipo: string, valores: Valores,
                        padroes: Padroes, campos: string[], classeAntes?: string): Valores {
  const novo: Valores = { ...valores }
  const antes = padroes.tipos[tipoAntes]
  const agora = padroes.tipos[tipo]

  if (tipo !== tipoAntes && antes && agora) {
    for (const campo of campos) {
      const velho = (antes as Record<string, unknown>)[campo]
      const novoValor = (agora as Record<string, unknown>)[campo]
      if (velho === undefined || novoValor === undefined) continue
      if (texto(valores[campo]) === texto(velho)) novo[campo] = texto(novoValor)
    }
  }

  if (tipo !== tipoAntes) {
    // A origem nao e reescrita de cara: o tipo novo pode aceitar a que esta la.
    // As listas se sobrepoem (1000, 1200 e 1900 valem em dois ou tres tipos), e
    // a tela antiga mantinha a escolha do operador quando ela ainda valia:
    // `lista.indexOf(manter) >= 0 ? manter : origemEsperada(...)`. Sobrescrever
    // aqui trocaria uma origem de politica escolhida a mao por um default.
    const atual = Number(valores.origem)
    const lista = padroes.origens_por_tipo[tipo]
    novo.origem = lista && lista.includes(atual)
      ? String(valores.origem)
      : String(origemEsperada(tipo, String(valores.classe ?? ""), padroes))
  } else if (classeAntes !== undefined && padroes.downstream.includes(tipo) && String(valores.classe ?? "") !== classeAntes) {
    // a classe do downstream carrega a origem junto, mas so quando a origem
    // ainda e a da classe anterior
    if (texto(valores.origem) === texto(padroes.origem_classe[classeAntes])) {
      novo.origem = String(origemEsperada(tipo, String(valores.classe ?? ""), padroes))
    }
  }
  return novo
}
