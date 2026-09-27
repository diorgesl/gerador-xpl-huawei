import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useSessao } from "@/api/sessao"

/**
 * O que separa a casca da tela de login.
 *
 * Enquanto a consulta esta em voo nao desenha nada: meia casca piscando
 * antes do redirecionamento e pior do que meio segundo parado, e a casca
 * ja dispara tres consultas proprias que voltariam 401.
 */
export function ExigeLogin({ children }: { children: ReactNode }) {
  const sessao = useSessao()

  if (sessao.isPending) return null
  if (!sessao.data?.logado) return <Navigate to="/login" replace />
  return <>{children}</>
}
