import { useEffect } from "react"
import { useBlocker } from "react-router-dom"
import { Button } from "@/components/ui/button"

/**
 * Pede confirmacao ao sair com alteracao nao salva, pelos dois caminhos: a
 * navegacao da SPA (useBlocker, que so existe em data router) e o fechamento
 * da aba ou o recarregamento (beforeunload).
 */
export function AvisoNaoSalvo({ sujo, aoSair }: { sujo: boolean; aoSair?: () => void }) {
  const bloqueio = useBlocker(sujo)

  useEffect(() => {
    if (!sujo) return
    const aoFechar = (evento: BeforeUnloadEvent) => {
      // o returnValue e o que o Chrome le; o preventDefault cobre o resto
      evento.preventDefault()
      evento.returnValue = ""
      return ""
    }
    window.addEventListener("beforeunload", aoFechar)
    return () => window.removeEventListener("beforeunload", aoFechar)
  }, [sujo])

  if (bloqueio.state !== "blocked") return null

  return (
    <div role="alertdialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4">
      <div className="w-full max-w-sm rounded border bg-card p-4">
        <h2 className="text-sm font-semibold">Sair sem salvar?</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Há alterações que ainda não foram para o peers.yaml.
        </p>
        <div className="mt-3 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => bloqueio.reset?.()}>
            continuar editando
          </Button>
          <Button size="sm" onClick={() => { aoSair?.(); bloqueio.proceed?.() }}>
            sair sem salvar
          </Button>
        </div>
      </div>
    </div>
  )
}
