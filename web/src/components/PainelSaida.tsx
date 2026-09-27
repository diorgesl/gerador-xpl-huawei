import { useEffect, useRef, useState } from "react"
import { Check, Copy, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { CodigoXpl } from "./CodigoXpl"
import { Diff } from "./Diff"
import { estadoDoBloco } from "@/lib/diff"
import { baixar } from "@/lib/copiar"

export type AbaSaida = {
  id: string
  rotulo: string
  conteudo: string | null
  arquivo: string | null
  salvo: string | null
  // a remocao vem do registro salvo, e nao da previa: o botao dela e sempre copiar
  soLeitura?: boolean
}

type Props = {
  abas: AbaSaida[]
  sujo: boolean
  carregando: boolean
  erro: string | null
  // A tela recebe a aba inteira, e nao so o texto, porque o "salvar e copiar"
  // precisa saber qual bloco copiar depois que o salvar confirmar
  onCopiar?: (aba: AbaSaida) => Promise<void> | void
  onSalvarECopiar?: (aba: AbaSaida) => Promise<void>
}

const plural = (n: number, um: string, muitos: string) => `${n} ${n === 1 ? um : muitos}`

function Estado({ previa, salvo, sujo }: { previa: string; salvo: string | null; sujo: boolean }) {
  const { estado, incluidas, removidas } = estadoDoBloco(previa, salvo, sujo)
  if (estado === "igual") return <>igual ao salvo</>
  if (estado === "novo") return <>arquivo novo</>
  if (estado === "desatualizado") return <>o arquivo em out/ está desatualizado</>
  return <>{plural(incluidas, "linha incluída", "linhas incluídas")}, {plural(removidas, "removida", "removidas")}</>
}

export function PainelSaida({ abas, sujo, carregando, erro, onCopiar, onSalvarECopiar }: Props) {
  const [copiado, setCopiado] = useState<string | null>(null)
  const [modoDiff, setModoDiff] = useState(false)
  const [abaAtual, setAbaAtual] = useState(abas[0]?.id ?? "")
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  const confirmar = (id: string) => {
    setCopiado(id)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setCopiado(null), 1500)
  }

  const aba = abas.find((a) => a.id === abaAtual) ?? abas[0]
  const semBloco = erro !== null || !aba || aba.conteudo === null
  // o sujo entra junto do estado: com o formulario mexido e a previa ainda
  // igual ao out/, quem esta para tras e o arquivo, e o salvar e o que o
  // atualiza. O cabecalho continua dizendo "igual ao salvo", porque ele fala
  // da previa contra o out/, e nao do formulario
  const precisaSalvar = Boolean(
    aba && !aba.soLeitura && !semBloco && (sujo || estadoDoBloco(aba.conteudo, aba.salvo, sujo).estado !== "igual"),
  )

  return (
    <section className="flex h-full flex-col gap-2 rounded border bg-card p-2">
      <Tabs value={aba?.id} onValueChange={setAbaAtual} className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <TabsList>
            {abas.map((a) => (
              <TabsTrigger key={a.id} value={a.id}>{a.rotulo}</TabsTrigger>
            ))}
          </TabsList>
          <p className="text-xs text-muted-foreground" aria-live="polite">
            {carregando ? "gerando prévia..." : semBloco ? "" : <Estado previa={aba.conteudo!} salvo={aba.salvo} sujo={sujo} />}
          </p>
        </div>

        {abas.map((a) => (
          <TabsContent key={a.id} value={a.id} className="min-h-0 flex-1">
            {a.conteudo === null ? (
              <p className="p-4 text-sm text-muted-foreground">
                {erro ? "a prévia volta quando os erros forem corrigidos" : "gerando prévia..."}
              </p>
            ) : modoDiff && a.salvo !== null ? (
              <Diff previa={a.conteudo} salvo={a.salvo} />
            ) : (
              <CodigoXpl texto={a.conteudo} />
            )}
          </TabsContent>
        ))}
      </Tabs>

      {!semBloco && (
        <div className="flex flex-wrap gap-2 border-t pt-2">
          <Button
            size="sm"
            onClick={async () => {
              // a tela e quem copia (ela sabe qual elemento selecionar no
              // ultimo degrau do fallback). O painel so cuida do rotulo.
              if (precisaSalvar && onSalvarECopiar) await onSalvarECopiar(aba)
              else await onCopiar?.(aba)
              confirmar(aba.id)
            }}
          >
            {copiado === aba.id ? <Check className="size-4" /> : <Copy className="size-4" />}
            {copiado === aba.id ? "copiado" : precisaSalvar ? "salvar e copiar" : "copiar"}
          </Button>

          <Button
            size="sm"
            variant="ghost"
            aria-pressed={modoDiff}
            disabled={aba.salvo === null}
            onClick={() => setModoDiff((v) => !v)}
          >
            diff
          </Button>

          <Button
            size="sm"
            variant="ghost"
            onClick={() => baixar(aba.conteudo!, aba.arquivo ?? "bloco.txt")}
          >
            <Download className="size-4" /> baixar
          </Button>
        </div>
      )}
    </section>
  )
}
