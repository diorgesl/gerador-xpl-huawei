import { createContext, useContext } from "react"

export type Tema = "claro" | "escuro" | "sistema"

const CHAVE = "tema"

/**
 * Ler e gravar o tema nunca pode derrubar a tela: em janela privada ou com o
 * storage bloqueado por politica, o localStorage lanca. A escolha vale so
 * nesta aba e a tela segue no tema do sistema.
 */
export function lerTema(): Tema {
  try {
    const guardado = localStorage.getItem(CHAVE)
    return guardado === "claro" || guardado === "escuro" ? guardado : "sistema"
  } catch {
    return "sistema"
  }
}

export function gravarTema(tema: Tema) {
  try {
    if (tema === "sistema") localStorage.removeItem(CHAVE)
    else localStorage.setItem(CHAVE, tema)
  } catch {
    // sem storage a escolha nao sobrevive ao recarregamento, e so
  }
}

export function aplicarTema(tema: Tema) {
  const escuro =
    tema === "escuro" ||
    (tema === "sistema" && window.matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.toggle("dark", escuro)
}

// O contexto mora aqui, e nao no provedores.tsx, porque o arquivo de la exporta
// o componente que o publica: componente e coisa que nao e componente no mesmo
// arquivo quebra o fast refresh e a regra do react-refresh reclama. A paleta e
// as configuracoes trocam o tema por este hook.
export const ContextoTema = createContext<[Tema, (tema: Tema) => void]>(["sistema", () => {}])

export function useTema() {
  return useContext(ContextoTema)
}
