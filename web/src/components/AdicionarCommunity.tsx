import { useState } from "react"
import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@/components/ui/command"

/** O mesmo formato que o /api/plano devolve em `sugestoes`. */
export type Sugestao = { valor: string; rotulo: string; grupo: string }

type Props = {
  sugestoes: Sugestao[]
  /** O que ja esta no textarea: o que ja foi usado nao se oferece de novo. */
  jaUsadas: string[]
  aoAdicionar: (valor: string) => void
  /**
   * O nome do campo, que entra no rotulo do botao. Sao dois campos com
   * lista na mesma tela, e sem isto os dois botoes teriam o mesmo nome
   * acessivel: quem le a tela por leitor de tela ouviria "adicionar
   * community" duas vezes, sem saber qual e qual.
   */
  rotulo?: string
}

/**
 * A busca de communities do CL-PEER.
 *
 * O campo e um textarea livre, e continua sendo: quem sabe o numero digita.
 * Esta lista existe para quem sabe o efeito e nao o numero, que e o caso
 * comum — "prepend para os upstreams" e uma frase, `64512:613` nao e.
 *
 * A lista vem do /api/plano, montada do plan.py no namespace da rede, e o
 * filtro e o do cmdk: casa no texto do item, entao o rotulo carrega as
 * palavras que o operador procura.
 */
export function AdicionarCommunity({ sugestoes, jaUsadas, aoAdicionar, rotulo }: Props) {
  const [aberto, setAberto] = useState(false)
  const usadas = new Set(jaUsadas)
  // o grupo e o cabecalho da lista, e a ordem e a do catalogo: o
  // Map preserva a de insercao
  const porGrupo = new Map<string, Sugestao[]>()
  for (const s of sugestoes) {
    if (usadas.has(s.valor)) continue
    porGrupo.set(s.grupo, [...(porGrupo.get(s.grupo) ?? []), s])
  }

  const escolher = (valor: string) => {
    aoAdicionar(valor)
    setAberto(false)
  }

  return (
    <>
      <Button type="button" variant="outline" size="sm" onClick={() => setAberto(true)}
              aria-label={rotulo ? `adicionar ${rotulo}` : "adicionar community"}
              disabled={sugestoes.length === 0}>
        <Plus className="size-4" /> adicionar community
      </Button>
      <CommandDialog open={aberto} onOpenChange={setAberto}
                     title="Adicionar community"
                     description="Busque pelo efeito ou pelo numero">
        {/* o CommandDialog do ui nao traz a raiz do cmdk (o upstream do
            shadcn traz): sem este <Command> em volta, a lista morre no
            render. A paleta de comandos tem a mesma linha pelo mesmo motivo */}
        <Command>
          <CommandInput placeholder="buscar por efeito ou numero (prepend, no anunciar, 14840)" />
          <CommandList>
            <CommandEmpty>nenhuma community com esse nome</CommandEmpty>
            {[...porGrupo].map(([grupo, itens]) => (
              <CommandGroup key={grupo} heading={grupo}>
                {itens.map((s) => (
                  // o value e o que o cmdk filtra: com o rotulo so, quem
                  // digita o numero nao acha nada
                  <CommandItem key={s.valor} value={`${s.rotulo} ${s.valor}`}
                               onSelect={() => escolher(s.valor)}>
                    <span className="dado text-xs text-muted-foreground">{s.valor}</span>
                    <span className="truncate">{s.rotulo}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  )
}
