import { useQuery } from "@tanstack/react-query"
import { Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { CodigoXpl } from "@/components/CodigoXpl"
import { Falha } from "@/components/Falha"
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

  // O aviso sobrevive ao tentar de novo, e nao so ao erro: o TanStack zera o
  // `error` de uma consulta sem dado quando ela e refeita (o estado volta a
  // `pending`), entao sem o `retentando` o botao que desabilita so existiria
  // depois da resposta. O `errorUpdateCount` e o que resta da falha depois do
  // refetch, e o `data === undefined` deixa de fora o refetch de fundo de quem
  // ja tem o bloco
  const tentando = base.isFetching
  const retentando = tentando && base.data === undefined && base.errorUpdateCount > 0
  const falhou = base.isError || retentando

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

      {/* O aviso entra acima do painel, e nao no lugar do corpo como o peer e o
          grupo fazem: la nao ha formulario sem o registro, e aqui o titulo e o
          paragrafo da ordem servem mesmo com o /base.txt fora do ar. A mensagem
          e a do Falha das outras telas, para a falha ter uma cara so */}
      {falhou && (
        <Falha mensagem="não deu para falar com a API" tentando={tentando} aoTentar={() => void base.refetch()} />
      )}

      {base.isLoading && <p className="text-sm text-muted-foreground">gerando...</p>}
      {base.data && <CodigoXpl texto={base.data} />}
    </div>
  )
}
