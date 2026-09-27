import { CodigoXpl } from "./CodigoXpl"
import { contar, marcarLinhas } from "@/lib/diff"

export function Diff({ previa, salvo }: { previa: string; salvo: string }) {
  const { incluidas, removidas } = contar(previa, salvo)
  return (
    <div>
      <p className="mb-1 text-xs text-muted-foreground" aria-live="polite">
        <span className="mr-2 inline-block size-2 rounded-full bg-sucesso-fundo" aria-hidden="true" />
        {incluidas} linhas incluídas
        <span className="mx-2 inline-block size-2 rounded-full bg-erro-fundo" aria-hidden="true" />
        {removidas} removidas
      </p>
      <CodigoXpl linhas={marcarLinhas(previa, salvo)} />
    </div>
  )
}
