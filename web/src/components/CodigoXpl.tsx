import { useState } from "react"
import { WrapText } from "lucide-react"
import { Button } from "@/components/ui/button"
import { tokenizar } from "@/lib/xpl"
import { cn } from "@/lib/utils"

export type LinhaCodigo = { texto: string; estado?: "igual" | "incluida" | "removida" }

type Props = {
  texto?: string
  linhas?: LinhaCodigo[]
  numerar?: boolean
  quebrar?: boolean
}

const CORES: Record<string, { background: string; color: string }> = {
  incluida: { background: "var(--sucesso-fundo)", color: "var(--sucesso-texto)" },
  removida: { background: "var(--erro-fundo)", color: "var(--erro-texto)" },
}

export function CodigoXpl({ texto, linhas, numerar = true, quebrar }: Props) {
  const [embrulhar, setEmbrulhar] = useState(quebrar ?? false)
  const conteudo = linhas ?? (texto ?? "").split("\n").map((t) => ({ texto: t, estado: undefined }))

  return (
    <div className="relative">
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="absolute right-1 top-1 z-10"
        aria-label={embrulhar ? "desligar a quebra de linhas" : "quebrar linhas"}
        aria-pressed={embrulhar}
        onClick={() => setEmbrulhar((v) => !v)}
      >
        <WrapText className="size-4" />
      </Button>
      <pre
        className={cn(
          "flex overflow-auto rounded border bg-card p-2 text-[12.5px] leading-[1.45]",
          "max-h-[46vh] tab-size-2",
        )}
      >
        {/* a numeracao fica fora do <code>: dentro dele, ela entraria no
            textContent e um Ctrl+A do operador levaria numero junto */}
        {numerar && (
          <span aria-hidden="true" className="mr-3 shrink-0 select-none text-right text-muted-foreground">
            {conteudo.map((_, i) => (
              <span key={i} className="block">{i + 1}</span>
            ))}
          </span>
        )}
        <code className={cn("min-w-0", embrulhar ? "whitespace-pre-wrap break-all" : "whitespace-pre")}>
          {conteudo.map((linha, i) => {
            const marcada = linha.estado !== undefined && linha.estado !== "igual"
            return (
              <span
                key={i}
                className={cn("block", marcada && `ln-${linha.estado}`)}
                style={marcada ? CORES[linha.estado!] : undefined}
              >
                {marcada
                  ? linha.texto
                  : tokenizar(linha.texto).map((t, j) => (
                      <span key={j} className={`tk-${t.classe}`}>{t.texto}</span>
                    ))}
              </span>
            )
          })}
        </code>
      </pre>
    </div>
  )
}
