import { createContext, useContext } from "react"

const CHAVE = "bgpgen.asn"

/**
 * O ASN da aba, e nao do navegador.
 *
 * O sessionStorage e por aba e morre com ela: duas abas podem estar em
 * redes diferentes ao mesmo tempo, que e a propriedade que a API sem
 * estado com o ?asn= compra. O localStorage seria compartilhado entre as
 * abas da mesma origem e as duas brigariam pelo mesmo valor.
 *
 * Ler e gravar nunca pode derrubar a tela: em janela privada ou com o
 * storage bloqueado por politica, o acesso lanca. Sem ele a escolha vale
 * so enquanto a aba viver, e a tela segue no primeiro da lista.
 */
export function lerAsn(): string | null {
  try {
    return window.sessionStorage.getItem(CHAVE)
  } catch {
    return null
  }
}

export function gravarAsn(asn: string) {
  try {
    window.sessionStorage.setItem(CHAVE, asn)
  } catch {
    // sem storage a escolha nao sobrevive ao recarregamento, e so
  }
}

export type TenantAtual = {
  /** O ASN escolhido, ou null enquanto a lista nao chegou ou esta vazia. */
  asn: string | null
  asns: string[]
  /**
   * A falha da lista de ASNs, ou null. E o unico jeito de a casca dizer que o
   * app esta sem tenant por queda de rede, e nao por pasta vazia: com o asn
   * nulo as consultas de dados se desabilitam, e nenhuma tela chega a ter um
   * erro proprio para mostrar.
   */
  erro: Error | null
  trocar: (asn: string) => void
}

export const ContextoTenant = createContext<TenantAtual>({
  asn: null,
  asns: [],
  erro: null,
  trocar: () => {},
})

/** O ASN escolhido. Null antes de a lista chegar, e sem nenhum tenant. */
export function useAsn() {
  return useContext(ContextoTenant).asn
}

export function useTenant() {
  return useContext(ContextoTenant)
}
