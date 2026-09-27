import { useQuery } from "@tanstack/react-query"
import { Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { CodigoXpl } from "@/components/CodigoXpl"
import { baixar, copiarComAviso } from "@/lib/copiar"
import { usePublicarAcoes } from "@/app/acoes-contexto"

export function BaseTela() {
  // O /base.txt e montado no momento do download, e nao guardado em out/:
  // ele reflete o plan.py e os templates de agora
  const base = useQuery({
    queryKey: ["base"],
    queryFn: async () => {
      const r = await fetch("/base.txt")
      if (!r.ok) throw new Error("falha ao ler o base.txt")
      return r.text()
    },
  })

  // A tela publica o que ela sabe fazer: copiar o bloco base. Nao ha duplicar
  // (nao e um registro) nem salvar (o /base.txt e montado na hora do download)
  const texto = base.data ?? null
  usePublicarAcoes({
    aoCopiarBloco: texto ? () => void copiarComAviso(texto, document.querySelector("code")) : undefined,
  })

  return (
    <div className="flex min-h-0 flex-col gap-3 p-3">
      <h1 className="text-base font-semibold">Bloco base</h1>

      <p className="max-w-3xl text-xs text-muted-foreground">
        O bloco base primeiro: é ele que define os sets e os filtros compartilhados que os
        blocos de peer chamam. Depois dele, o bloco de cada peer e, por último, o dos
        prefixos próprios. A ordem de colagem completa está no README, na seção
        "Ordem de colagem no F1A".
      </p>

      {/* Os dois botoes esperam o texto: sem ele a copia levaria nada, e o
          download salvaria um base.txt vazio com o nome do bloco. A guarda e
          a mesma que a Casca ja tem no "baixar o bloco base" da paleta */}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={!base.data}
          onClick={() => void copiarComAviso(base.data ?? "", document.querySelector("code"))}
        >
          copiar
        </Button>
        <Button size="sm" variant="ghost" disabled={!base.data} onClick={() => baixar(base.data ?? "", "base.txt")}>
          <Download className="size-4" /> baixar
        </Button>
      </div>

      {base.isLoading && <p className="text-sm text-muted-foreground">gerando...</p>}
      {base.data && <CodigoXpl texto={base.data} />}
    </div>
  )
}
