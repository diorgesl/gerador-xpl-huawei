import { useContext, useEffect, useRef, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useTenant } from "@/app/tenant"
import { ContextoLerRascunho } from "@/app/rascunho"
import { DialogoNovoAsn } from "./DialogoNovoAsn"

/**
 * A rede da aba, no cabecalho da barra lateral: e o unico lugar visivel em
 * toda rota, e a escolha vale para a tela inteira.
 *
 * Cada opcao do menu e um cadastro, e nao uma preferencia de exibicao: os
 * peers, os grupos e os blocos sao os do tenant escolhido. Por isso a lista
 * sai do /api/asns, que e o que a pasta do checkout tem agora, e nao de uma
 * constante na tela.
 *
 * A troca com rascunho sujo pergunta antes de acontecer, e e o unico lugar do
 * app que pergunta por ela: a chave no ASN remonta a tela, entao o rascunho de
 * uma rede nao sobrevive a outra, e quem decide se ele se perde e quem o
 * escreveu.
 */
export function SeletorAsn() {
  const { asn, asns, trocar } = useTenant()
  const sujo = useContext(ContextoLerRascunho)
  const [novoAberto, setNovoAberto] = useState(false)
  // a rede que espera resposta: enquanto ela estiver aqui, a pergunta esta de
  // pe e nada trocou ainda
  const [pendente, setPendente] = useState<string | null>(null)
  // a troca que tem que terminar na lista: o registro aberto e do tenant
  // antigo, e /peers/3 nao existe do outro lado, ou e outro peer
  const irParaLista = useRef(false)
  const navegar = useNavigate()
  const { pathname } = useLocation()

  // A navegacao sai depois da troca, e nao junto com ela: no clique, o
  // useBlocker da tela que sai ainda esta de pe, com o `sujo` do ultimo render
  // dela, barraria o pedido - e o pedido morreria junto com a tela, porque a
  // chave no ASN remonta o Outlet e leva o blocker embora sem satisfazer a
  // navegacao que ele engoliu. Aqui a tela antiga ja saiu (e o blocker dela com
  // ela) e a nova montou limpa, entao nao ha o que barrar
  useEffect(() => {
    if (!irParaLista.current) return
    irParaLista.current = false
    navegar("/peers")
  }, [asn, navegar])

  const aplicar = (novo: string) => {
    irParaLista.current = /^\/(peers|grupos)\//.test(pathname)
    trocar(novo)
  }

  const escolher = (novo: string) => {
    if (novo === asn) return
    // A pergunta vem antes da troca, e nao da navegacao: o useBlocker do
    // AvisoNaoSalvo barraria a rota depois de o ASN ja ter mudado, e a tela
    // do peer antigo ficaria de pe consultando o tenant novo
    if (sujo) {
      setPendente(novo)
      return
    }
    aplicar(novo)
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

      {/* O mesmo aviso do AvisoNaoSalvo, e nao o proprio: la ele barra uma
          navegacao que ja saiu, aqui ele pergunta por uma troca que ainda nao
          aconteceu. O texto e o mesmo porque a perda e a mesma - o rascunho
          que nao foi para o peers.yaml */}
      {pendente !== null && (
        <div role="alertdialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4">
          <div className="w-full max-w-sm rounded border bg-card p-4">
            <h2 className="text-sm font-semibold">Trocar de rede sem salvar?</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Há alterações que ainda não foram para o peers.yaml.
            </p>
            <div className="mt-3 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setPendente(null)}>
                continuar editando
              </Button>
              <Button size="sm" onClick={() => { aplicar(pendente); setPendente(null) }}>
                trocar sem salvar
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
