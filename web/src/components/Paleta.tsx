import { useNavigate } from "react-router-dom"
import {
  Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from "@/components/ui/command"
import { useTema } from "@/app/tema"
import type { GrupoResumo, PeerResumo } from "@/api/consultas"

const TIPOS = ["cliente", "parceiro", "upstream", "ix", "pni"]

type Props = {
  aberta: boolean
  aoFechar: () => void
  peers: PeerResumo[]
  grupos: GrupoResumo[]
  // as duas primeiras acoes so existem quando a tela aberta tem um registro ou
  // um bloco; o base e sempre oferecido
  aoDuplicar?: () => void
  aoCopiarBloco?: () => void
  aoBaixarBase?: () => void
}

export function Paleta({ aberta, aoFechar, peers, grupos, aoDuplicar, aoCopiarBloco, aoBaixarBase }: Props) {
  const [tema, trocarTema] = useTema()
  const navegar = useNavigate()

  // o atalho de tema muda com o que esta escolhido: com o sistema, a terceira
  // opcao e "usar o tema do sistema"
  //
  // O <Command> por dentro do dialogo e o que falta no CommandDialog destes
  // componentes: sem ele a lista e o campo de busca leem um contexto do cmdk
  // que nao existe e a paleta morre no primeiro render. Os componentes de ui/
  // sao gerados e nao se editam, entao a raiz entra aqui.
  return (
    <CommandDialog
      open={aberta}
      onOpenChange={(v) => !v && aoFechar()}
      title="Paleta de comandos"
      description="Pular para um peer ou um grupo, criar registro ou trocar o tema"
    >
      <Command>
        <CommandInput placeholder="buscar peer, grupo ou comando" />
        <CommandList>
          <CommandEmpty>nada com esse nome</CommandEmpty>

          {/* O CommandItem e do cmdk e nao aceita `asChild`: quem navega e o
              onSelect, com o navigate do roteador */}
          <CommandGroup heading="Peers">
            {peers.map((p) => (
              <CommandItem
                key={p.id}
                value={`${p.apelido} ${p.nome} ${p.asn} ${p.tipo}`}
                onSelect={() => { aoFechar(); navegar(`/peers/${p.id}`) }}
                className="flex w-full justify-between"
              >
                <span>{p.apelido || p.nome || p.token}</span>
                <span className="dado text-xs text-muted-foreground">AS{p.asn}</span>
              </CommandItem>
            ))}
          </CommandGroup>

          <CommandGroup heading="Grupos">
            {grupos.map((g) => (
              <CommandItem
                key={g.id}
                value={`${g.nome} ${g.tipo}`}
                onSelect={() => { aoFechar(); navegar(`/grupos/${g.id}`) }}
                className="flex w-full justify-between"
              >
                <span>{g.nome}</span>
                <span className="text-xs text-muted-foreground">{g.membros} membros</span>
              </CommandItem>
            ))}
          </CommandGroup>

          <CommandGroup heading="Criar">
            {TIPOS.map((t) => (
              <CommandItem key={t} value={`novo peer ${t}`} onSelect={() => { aoFechar(); navegar(`/peers/novo?tipo=${t}`) }}>
                novo peer {t}
              </CommandItem>
            ))}
            {TIPOS.map((t) => (
              <CommandItem key={`g-${t}`} value={`novo grupo ${t}`} onSelect={() => { aoFechar(); navegar(`/grupos/novo?tipo=${t}`) }}>
                novo grupo {t}
              </CommandItem>
            ))}
          </CommandGroup>

          {(aoDuplicar || aoCopiarBloco) && (
            <CommandGroup heading="A tela aberta">
              {aoDuplicar && (
                <CommandItem value="duplicar o registro aberto" onSelect={() => { aoFechar(); aoDuplicar() }}>
                  duplicar o registro aberto
                </CommandItem>
              )}
              {aoCopiarBloco && (
                <CommandItem value="copiar o bloco aberto" onSelect={() => { aoFechar(); aoCopiarBloco() }}>
                  copiar o bloco aberto
                </CommandItem>
              )}
            </CommandGroup>
          )}

          {aoBaixarBase && (
            <CommandGroup heading="Blocos">
              <CommandItem value="baixar o bloco base" onSelect={() => { aoFechar(); aoBaixarBase() }}>
                baixar o bloco base
              </CommandItem>
            </CommandGroup>
          )}

          <CommandGroup heading="Tema">
            {(["claro", "escuro", "sistema"] as const).map((t) => (
              <CommandItem
                key={t}
                value={`tema ${t}`}
                onSelect={() => trocarTema(t)}
              >
                tema {t}
                {tema === t ? " (atual)" : ""}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
