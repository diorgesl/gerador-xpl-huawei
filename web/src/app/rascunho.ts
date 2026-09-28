import { createContext, useContext, useEffect } from "react"

/**
 * O rascunho da tela aberta, dos dois lados: a tela de formulario publica se
 * ela tem alteracao que ainda nao foi para o arquivo, e o seletor de ASN le.
 *
 * Sao dois contextos, e nao um objeto com uma funcao dentro, como o das acoes:
 * o que atravessa aqui e um booleano de render, e quem le precisa re-renderizar
 * quando ele muda - um valor estavel lido de um ref nao faria isso, e o seletor
 * decidiria a pergunta pelo rascunho do commit anterior.
 */
export const ContextoDefinirRascunho = createContext<(sujo: boolean) => void>(() => {})

/** Se a tela aberta tem alteracao nao salva. Quem le e o seletor de ASN. */
export const ContextoLerRascunho = createContext<boolean>(false)

/**
 * Publica se a tela aberta tem alteracao nao salva. Quem chama sao as telas de
 * formulario, no mesmo lugar em que ja publicam o `aoSalvar`.
 *
 * A limpeza devolve `false` na saida para a tela que sai nao deixar o rascunho
 * dela valendo para a proxima: a troca de tenant remonta a tela, e sem ela o
 * seletor perguntaria por causa de um formulario que ja nao esta em lugar
 * nenhum. Ela roda tambem quando o proprio `sujo` muda, e o efeito seguinte
 * republica o valor novo no mesmo lote, entao a tela nao chega a ficar sem
 * rascunho no meio.
 */
export function usePublicarRascunho(sujo: boolean) {
  const definir = useContext(ContextoDefinirRascunho)
  useEffect(() => {
    definir(sujo)
    return () => definir(false)
  }, [definir, sujo])
}
