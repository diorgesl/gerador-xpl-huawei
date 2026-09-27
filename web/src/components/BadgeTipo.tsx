import { cn } from "@/lib/utils"

// Um so lugar monta o nome dos tokens de badge: o matiz vem por tipo, e o
// texto tem o mesmo peso nos cinco
export function BadgeTipo({ tipo, className }: { tipo: string; className?: string }) {
  return (
    <span
      data-tipo={tipo}
      className={cn("rounded px-1.5 py-0.5 text-[11px] font-medium", className)}
      style={{
        background: `var(--badge-${tipo}-fundo)`,
        color: `var(--badge-${tipo}-texto)`,
      }}
    >
      {tipo}
    </span>
  )
}
