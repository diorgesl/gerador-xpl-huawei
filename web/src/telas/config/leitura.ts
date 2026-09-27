/**
 * A altura da linha de leitura: o quanto o topo da secao precisa ter subido
 * para ela ser "a que esta sendo lida".
 *
 * A medida e presa de dois lados. De baixo, o `scroll-mt-24` das secoes (96px):
 * o salto de um link do sumario poe a secao aberta em 96, e a linha tem que
 * ficar abaixo disso, senao a secao que o operador acabou de abrir nao conta
 * como lida. De cima, a altura maxima do sumario grudado (80px, o `max-h-20`
 * dele), senao a marca andaria com a secao ainda escondida atras dele.
 */
export const LINHA_DE_LEITURA = 104

/**
 * A chave da ultima secao cujo topo ja passou a linha de leitura, ou null
 * quando nenhuma passou.
 *
 * E a secao que o operador tem na frente: as de baixo ainda nao chegaram, e as
 * de cima ja sairam.
 *
 * O `noFundo` cobre o fim da rolagem. La a ultima secao pode ser mais baixa que
 * a janela, e o topo dela fica abaixo da linha: sem esta regra a marca ficaria
 * na penultima, com a ultima ocupando a tela.
 *
 * A decisao sai daqui, e nao do componente, para ter teste: a medida que ela
 * consome vem do layout, que o jsdom nao calcula.
 */
export function secaoNaLinha(chaves: string[], topos: number[], linha: number,
                             noFundo = false) {
  if (noFundo) return chaves[chaves.length - 1] ?? null
  let achada: string | null = null
  chaves.forEach((chave, i) => {
    if ((topos[i] ?? Infinity) <= linha) achada = chave
  })
  return achada
}
