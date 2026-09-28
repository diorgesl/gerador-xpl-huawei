import { useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useTenant } from "@/app/tenant"
import { DialogoNovoAsn } from "./DialogoNovoAsn"

/**
 * A rede da aba, no cabecalho da barra lateral: e o unico lugar visivel em
 * toda rota, e a escolha vale para a tela inteira.
 *
 * Cada opcao do menu e um cadastro, e nao uma preferencia de exibicao: os
 * peers, os grupos e os blocos sao os do tenant escolhido. Por isso a lista
 * sai do /api/asns, que e o que a pasta do checkout tem agora, e nao de uma
 * constante na tela.
 */
export function SeletorAsn() {
  const { asn, asns, trocar } = useTenant()
  const [novoAberto, setNovoAberto] = useState(false)
  const navegar = useNavigate()
  const { pathname } = useLocation()

  const escolher = (novo: string) => {
    if (novo === asn) return
    trocar(novo)
    // o registro aberto e do tenant antigo: /peers/3 nao existe do outro
    // lado, ou e outro peer. A lista da rede nova e o destino
    if (/^\/(peers|grupos)\//.test(pathname)) navegar("/peers")
  }

  return (
    <>
      <DropdownMenu>
        {/* a composicao e por `render`, e nao por `asChild`: os componentes
            que o CLI escreveu sao do Base UI */}
        <DropdownMenuTrigger render={<Button variant="ghost" size="sm" className="dado px-1" />}>
          <span className="flex items-center gap-1">
            AS{asn ?? "..."}
            <ChevronDown className="size-3" />
          </span>
        </DropdownMenuTrigger>
        {/* o Item do Base UI nao tem onSelect (o do Radix tinha): o clique e o
            onClick, e o onSelect nao dispara nunca */}
        <DropdownMenuContent align="start">
          {asns.map((outro) => (
            <DropdownMenuItem key={outro} onClick={() => escolher(outro)}
                              aria-current={outro === asn ? "true" : undefined}>
              AS{outro}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setNovoAberto(true)}>novo ASN</DropdownMenuItem>
          <DropdownMenuItem onClick={() => navegar("/configuracoes")}>
            configurações
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {/* o ASN criado ja entra selecionado: quem acabou de criar um tenant quer
          trabalhar nele, e nao voltar para a rede que estava aberta */}
      <DialogoNovoAsn aberto={novoAberto} aoFechar={() => setNovoAberto(false)}
                      aoCriar={(novo) => { setNovoAberto(false); escolher(novo) }} />
    </>
  )
}
