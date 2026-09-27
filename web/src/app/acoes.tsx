import type { ReactNode } from "react"
import { ContextoAcoes, ContextoDefinirAcoes, type AcoesDaTela } from "./acoes-contexto"

/** Entrega as acoes da tela aberta a paleta e o jeito de troca-las a ela. */
export function ProvedorAcoes({ acoes, definir, children }: {
  acoes: AcoesDaTela
  definir: (acoes: AcoesDaTela) => void
  children: ReactNode
}) {
  return (
    <ContextoDefinirAcoes.Provider value={definir}>
      <ContextoAcoes.Provider value={acoes}>{children}</ContextoAcoes.Provider>
    </ContextoDefinirAcoes.Provider>
  )
}
