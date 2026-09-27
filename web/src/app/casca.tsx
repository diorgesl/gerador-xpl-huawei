import { Outlet, useNavigate } from "react-router-dom"
import { BarraLateral } from "@/components/BarraLateral"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Menu } from "lucide-react"
import { useGrupos, usePeers, usePlano } from "@/api/consultas"

export function Casca() {
  const plano = usePlano()
  const peers = usePeers()
  const grupos = useGrupos()
  const navegar = useNavigate()

  const barra = (
    <BarraLateral
      peers={peers.data ?? []}
      grupos={grupos.data ?? []}
      asn={plano.data?.rede.asn ?? ""}
      aoNovo={navegar}
    />
  )

  return (
    <div className="flex min-h-dvh">
      {/* a partir de 1024px a barra fica fixa; abaixo disso vira gaveta */}
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
        <div className="sticky top-0 h-dvh overflow-y-auto">{barra}</div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b bg-card p-2 lg:hidden">
          <Sheet>
            <SheetTrigger render={<Button variant="ghost" size="icon" aria-label="Abrir navegação" />}>
              <Menu className="size-5" />
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-0">
              {barra}
            </SheetContent>
          </Sheet>
          <span className="font-semibold">bgpgen</span>
        </header>
        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
