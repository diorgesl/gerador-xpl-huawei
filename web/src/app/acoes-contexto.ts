import { createContext, useContext, useEffect, useMemo, useRef } from "react"

/** O que a tela aberta sabe fazer, para a paleta e o Ctrl+S alcancarem. */
export type AcoesDaTela = {
  aoSalvar?: () => void
  aoDuplicar?: () => void
  aoCopiarBloco?: () => void
}

// Dois contextos de proposito: a casca LE as acoes da tela aberta e a tela
// ESCREVE as dela. Com um so, a tela escreveria no mesmo contexto que le.
export const ContextoAcoes = createContext<AcoesDaTela>({})
export const ContextoDefinirAcoes = createContext<(a: AcoesDaTela) => void>(() => {})

export function useAcoesDaTela() {
  return useContext(ContextoAcoes)
}

export function useDefinirAcoes() {
  return useContext(ContextoDefinirAcoes)
}

/**
 * Publica as acoes da tela aberta com um objeto ESTAVEL, cujos campos chamam um
 * ref atualizado a cada render. O caminho ingenuo, que e publicar dentro de um
 * efeito que depende dos handlers, vira laco: handler novo a cada render, entao
 * objeto novo publicado, entao re-render, entao handler novo. As telas chamam
 * isto uma vez e nao precisam memoizar nada.
 *
 * O ref se atualiza num efeito sem dependencias, e nao no corpo do render: o
 * lint proibe escrever em ref durante o render, e o efeito roda depois do
 * commit e antes de qualquer handler de evento, entao quem chama as acoes
 * sempre le a versao do ultimo render.
 */
export function usePublicarAcoes(acoes: AcoesDaTela) {
  const atual = useRef(acoes)
  useEffect(() => {
    atual.current = acoes
  })
  const definir = useDefinirAcoes()
  const estavel = useMemo<AcoesDaTela>(
    () => ({
      aoSalvar: () => atual.current.aoSalvar?.(),
      aoDuplicar: () => atual.current.aoDuplicar?.(),
      aoCopiarBloco: () => atual.current.aoCopiarBloco?.(),
    }),
    [],
  )
  useEffect(() => definir(estavel), [definir, estavel])
}
