import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

type Opcao = { valor: string; rotulo: string }

// Sugere e aceita valor novo, como o datalist da tela antiga: a tabela do
// plano por um lado e o que ja esta cadastrado por outro. Nao e um select,
// porque o operador precisa poder digitar um POP ou um aprendizado que ainda
// nao existe.
export function CampoCombo({
  nome, valor, opcoes, aoMudar, placeholder, mono, id,
}: {
  nome: string
  valor: string
  opcoes: Opcao[]
  aoMudar: (valor: string) => void
  placeholder?: string
  mono?: boolean
  id?: string
}) {
  const lista = `${nome}-sugestoes`
  return (
    <>
      <Input
        id={id ?? nome}
        name={nome}
        list={lista}
        value={valor}
        placeholder={placeholder}
        inputMode={placeholder && /^\d+$/.test(placeholder) ? "numeric" : undefined}
        onChange={(e) => aoMudar(e.target.value)}
        className={cn(mono && "dado")}
      />
      <datalist id={lista}>
        {opcoes.map((o) => (
          <option key={o.valor} value={o.valor}>{o.rotulo}</option>
        ))}
      </datalist>
    </>
  )
}
