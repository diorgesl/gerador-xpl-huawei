import type { ReactNode } from "react"
import { ContextoDefinirAcoes, type AcoesDaTela } from "./acoes-contexto"

/** Entrega as acoes da tela aberta a paleta e o jeito de troca-las a ela. */
export function ProvedorAcoes({ definir, children }: {
  definir: (acoes: AcoesDaTela) => void
  children: ReactNode
}) {
  return <ContextoDefinirAcoes.Provider value={definir}>{children}</ContextoDefinirAcoes.Provider>
}
