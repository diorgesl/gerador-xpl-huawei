import { useEffect } from "react"

type Acoes = {
  aoSalvar?: () => void
  aoAbrirPaleta: () => void
}

/**
 * Ctrl+S e Ctrl+K, com o Cmd do Mac valendo igual. O Ctrl+S precisa do
 * preventDefault: sem ele o navegador abre o dialogo de salvar a pagina por
 * cima da tela.
 */
export function useAtalhos({ aoSalvar, aoAbrirPaleta }: Acoes) {
  useEffect(() => {
    const aoTeclar = (evento: KeyboardEvent) => {
      if (!evento.ctrlKey && !evento.metaKey) return
      const tecla = evento.key.toLowerCase()
      if (tecla === "s" && aoSalvar) {
        evento.preventDefault()
        aoSalvar()
      } else if (tecla === "k") {
        evento.preventDefault()
        aoAbrirPaleta()
      }
    }
    window.addEventListener("keydown", aoTeclar)
    return () => window.removeEventListener("keydown", aoTeclar)
  }, [aoSalvar, aoAbrirPaleta])
}
