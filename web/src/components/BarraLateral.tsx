import { Link, useLocation } from "react-router-dom"
import { ChevronDown, Plus, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { BadgeTipo } from "@/components/BadgeTipo"
import { filtrarGrupos, filtrarPeers } from "@/lib/busca"
import type { GrupoResumo, PeerResumo } from "@/api/consultas"
import { useState } from "react"

const TIPOS = ["cliente", "parceiro", "upstream", "ix", "pni"]

// O seletor de tema nao mora aqui: ele fica nas configuracoes (Task 15) e na
// paleta de comandos (Task 8), que sao os dois lugares que a spec pede.
type Props = {
  peers: PeerResumo[]
  grupos: GrupoResumo[]
  asn: string
  aoNovo: (destino: string) => void
}

export function BarraLateral({ peers, grupos, asn, aoNovo }: Props) {
  const [busca, setBusca] = useState("")
  const { pathname } = useLocation()
  const peersVisiveis = filtrarPeers(peers, busca)
  const gruposVisiveis = filtrarGrupos(grupos, busca)

  const item = (para: string, rotulo: string, extra?: React.ReactNode) => (
    <Link
      to={para}
      aria-current={pathname.startsWith(para) ? "page" : undefined}
      className="flex items-center justify-between gap-2 rounded px-2 py-1 text-sm hover:bg-accent aria-[current=page]:bg-accent"
    >
      <span className="truncate">{rotulo}</span>
      {extra}
    </Link>
  )

  return (
    <nav aria-label="Navegação" className="flex h-full flex-col gap-3 p-3">
      <div className="flex items-baseline justify-between">
        <span className="font-semibold">bgpgen</span>
        <Link to="/configuracoes" className="dado text-xs text-muted-foreground hover:underline">
          AS{asn}
        </Link>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-2 top-2 size-4 text-muted-foreground" />
        <Input
          type="search"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="buscar por ASN, apelido, nome ou tipo"
          aria-label="Buscar peers e grupos"
          className="pl-8"
        />
      </div>

      <DropdownMenu>
        {/* a composicao e por `render`, e nao por `asChild`: os componentes
            que o CLI escreveu sao do Base UI */}
        <DropdownMenuTrigger render={<Button size="sm" className="justify-between" />}>
          <span className="flex items-center gap-1">
            <Plus className="size-4" /> novo
          </span>
          <ChevronDown className="size-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {TIPOS.map((t) => (
            <DropdownMenuItem key={t} onSelect={() => aoNovo(`/peers/novo?tipo=${t}`)}>
              peer {t}
            </DropdownMenuItem>
          ))}
          {TIPOS.map((t) => (
            <DropdownMenuItem key={`g-${t}`} onSelect={() => aoNovo(`/grupos/novo?tipo=${t}`)}>
              grupo {t}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
        <section>
          <h2 className="px-2 py-1 text-[11px] uppercase tracking-wide text-muted-foreground">
            Peers
          </h2>
          {peersVisiveis.length === 0 ? (
            <p className="px-2 text-sm text-muted-foreground">nenhum peer</p>
          ) : (
            peersVisiveis.map((p) => item(`/peers/${p.id}`, p.apelido || p.nome || p.token, <BadgeTipo tipo={p.tipo} />))
          )}
        </section>

        <section>
          <h2 className="px-2 py-1 text-[11px] uppercase tracking-wide text-muted-foreground">
            Grupos
          </h2>
          {gruposVisiveis.length === 0 ? (
            <p className="px-2 text-sm text-muted-foreground">nenhum grupo</p>
          ) : (
            gruposVisiveis.map((g) =>
              item(`/grupos/${g.id}`, g.nome, <span className="dado text-xs text-muted-foreground">{g.membros}</span>),
            )
          )}
        </section>

        <section>
          <h2 className="px-2 py-1 text-[11px] uppercase tracking-wide text-muted-foreground">
            Política
          </h2>
          {item("/prefixos", "Prefixos próprios")}
          {item("/base", "Bloco base")}
          {item("/configuracoes", "Configurações")}
        </section>
      </div>

    </nav>
  )
}
