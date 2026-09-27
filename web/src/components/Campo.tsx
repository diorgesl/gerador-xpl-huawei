import type { ReactNode } from "react"
import { CircleAlert, TriangleAlert } from "lucide-react"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

type Props = {
  nome: string
  rotulo: string
  ajuda?: string
  erro?: string
  aviso?: string
  // "o bloco de <tipo> nao usa este campo": o campo esta a vista porque tem
  // valor guardado ou erro, e nao porque pertence ao tipo aberto
  nota?: string
  largo?: boolean
  children: ReactNode
}

export function Campo({ nome, rotulo, ajuda, erro, aviso, nota, largo, children }: Props) {
  return (
    <div
      data-campo={nome}
      className={cn("flex flex-col gap-1", largo && "sm:col-span-2")}
    >
      <Label htmlFor={nome} className="text-[13px]">
        {rotulo}
      </Label>
      {children}
      {ajuda && !erro && <p className="text-xs text-muted-foreground">{ajuda}</p>}
      {nota && <p className="text-xs text-muted-foreground">{nota}</p>}
      {erro && (
        <p role="alert" className="flex items-start gap-1 text-xs text-erro-texto">
          <CircleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
          {erro}
        </p>
      )}
      {aviso && !erro && (
        <p className="flex items-start gap-1 text-xs text-aviso-texto">
          <TriangleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
          {aviso}
        </p>
      )}
    </div>
  )
}
