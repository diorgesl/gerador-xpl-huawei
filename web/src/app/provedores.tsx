import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { Toaster } from "@/components/ui/sonner"
import { useAsns } from "@/api/consultas"
import { ContextoTenant, gravarAsn, lerAsn } from "./tenant"
import { aplicarTema, ContextoTema, gravarTema, lerTema, type Tema } from "./tema"

const consultas = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
})

function ProvedorTema({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>(lerTema)

  useEffect(() => {
    aplicarTema(tema)
    if (tema !== "sistema") return
    // com o sistema escolhido, a troca de tema do SO vale na hora
    const consulta = window.matchMedia("(prefers-color-scheme: dark)")
    const aoTrocar = () => aplicarTema("sistema")
    consulta.addEventListener("change", aoTrocar)
    return () => consulta.removeEventListener("change", aoTrocar)
  }, [tema])

  const trocar = useCallback((novo: Tema) => {
    gravarTema(novo)
    setTema(novo)
  }, [])

  return <ContextoTema.Provider value={[tema, trocar]}>{children}</ContextoTema.Provider>
}

/**
 * A lista enquanto a consulta nao responde. E uma constante, e nao um `[]` no
 * `??`, porque o `valor` do contexto e memoizado: com um array novo a cada
 * render, o memo nao serviria para nada e todo consumidor do tenant
 * re-renderizaria a cada resposta da consulta.
 */
const SEM_TENANTS: string[] = []

function ProvedorTenant({ children }: { children: ReactNode }) {
  const lista = useAsns()
  const asns = lista.data ?? SEM_TENANTS
  const [escolhido, setEscolhido] = useState<string | null>(lerAsn)

  // O guardado vale enquanto estiver na lista, e o `?? asns[0]` e o
  // primeiro boot, a aba nova e o tenant apagado a mao: nos tres a escolha
  // anterior nao existe mais, e cair no primeiro e melhor que ficar sem
  // nenhuma. Nao ha efeito que copie a lista para o estado: o que manda e
  // a lista que chegou, e nao a que estava na tela quando o operador
  // escolheu.
  const asn = escolhido !== null && asns.includes(escolhido)
    ? escolhido
    : (asns[0] ?? null)

  const trocar = useCallback((novo: string) => {
    gravarAsn(novo)
    setEscolhido(novo)
  }, [])

  // a falha da lista vai junto: e ela que separa, na casca, a rede fora do ar
  // da pasta sem arquivo, e o `asn` nulo e o mesmo nos dois casos
  const erro = lista.error
  const valor = useMemo(() => ({ asn, asns, erro, trocar }), [asn, asns, erro, trocar])
  return <ContextoTenant.Provider value={valor}>{children}</ContextoTenant.Provider>
}

/**
 * O `client` e do teste: o arnes monta um QueryClient por caso (as consultas
 * tem `staleTime` de 5s, e o caso seguinte leria o dado do anterior pela
 * mesma chave), e o provedor do tenant mora aqui dentro - o cliente do caso
 * so alcanca a lista de ASNs entrando por aqui. Em producao e o do modulo.
 */
export function Provedores({ children, client = consultas }: { children: ReactNode; client?: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <ProvedorTenant>
        <ProvedorTema>
          {children}
          <Toaster position="bottom-right" />
        </ProvedorTema>
      </ProvedorTenant>
    </QueryClientProvider>
  )
}
