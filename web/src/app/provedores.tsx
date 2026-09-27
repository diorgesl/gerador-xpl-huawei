import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react"
import { Toaster } from "@/components/ui/sonner"
import { aplicarTema, gravarTema, lerTema, type Tema } from "./tema"

const consultas = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
})

const ContextoTema = createContext<[Tema, (tema: Tema) => void]>(["sistema", () => {}])

export function useTema() {
  return useContext(ContextoTema)
}

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

export function Provedores({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={consultas}>
      <ProvedorTema>
        {children}
        <Toaster position="bottom-right" />
      </ProvedorTema>
    </QueryClientProvider>
  )
}
