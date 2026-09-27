import { useCallback, useState } from "react"
import { Outlet, useNavigate } from "react-router-dom"
import { BarraLateral } from "@/components/BarraLateral"
import { Paleta } from "@/components/Paleta"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Menu } from "lucide-react"
import { sessaoVencida } from "@/api/cliente"
import { useGrupos, usePeers, usePlano } from "@/api/consultas"
import { baixar } from "@/lib/copiar"
import { ProvedorAcoes } from "./acoes"
import { useAtalhos } from "./atalhos"
import type { AcoesDaTela } from "./acoes-contexto"

export function Casca() {
  const plano = usePlano()
  const peers = usePeers()
  const grupos = useGrupos()
  const navegar = useNavigate()

  const [paletaAberta, setPaletaAberta] = useState(false)
  // o que a tela aberta publica: a paleta e o Ctrl+S leem daqui
  const [acoes, setAcoes] = useState<AcoesDaTela>({})

  const abrirPaleta = useCallback(() => setPaletaAberta(true), [])
  useAtalhos({ aoSalvar: acoes.aoSalvar, aoAbrirPaleta: abrirPaleta })

  const duplicar = acoes.aoDuplicar
  const copiarBloco = acoes.aoCopiarBloco

  const baixarBase = useCallback(async () => {
    const resposta = await fetch("/base.txt")
    // o fetch cru nao passa pelo cliente, entao o 401 de sessao vencida
    // precisa do aviso aqui: sem ele o clique nao faria nada, calado
    if (sessaoVencida(resposta)) return
    // sem a conferencia, um 500 do servidor salvaria a pagina de erro com o
    // nome do bloco base
    if (!resposta.ok) return
    baixar(await resposta.text(), "base.txt")
  }, [])

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
          <ProvedorAcoes definir={setAcoes}>
            <Outlet />
          </ProvedorAcoes>
        </main>
      </div>

      <Paleta
        aberta={paletaAberta}
        aoFechar={() => setPaletaAberta(false)}
        peers={peers.data ?? []}
        grupos={grupos.data ?? []}
        aoDuplicar={duplicar}
        aoCopiarBloco={copiarBloco}
        aoBaixarBase={baixarBase}
      />
    </div>
  )
}
