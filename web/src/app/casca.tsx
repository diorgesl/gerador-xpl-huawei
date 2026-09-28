import { useCallback, useState } from "react"
import { Outlet, useNavigate } from "react-router-dom"
import { BarraLateral } from "@/components/BarraLateral"
import { Paleta } from "@/components/Paleta"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Menu } from "lucide-react"
import { sessaoVencida } from "@/api/cliente"
import { useAsns, useGrupos, usePeers } from "@/api/consultas"
import { baixar } from "@/lib/copiar"
import { Falha } from "@/components/Falha"
import { SemTenant } from "@/components/SemTenant"
import { ProvedorAcoes } from "./acoes"
import { useAtalhos } from "./atalhos"
import type { AcoesDaTela } from "./acoes-contexto"
import { ContextoDefinirRascunho, ContextoLerRascunho } from "./rascunho"
import { useTenant } from "./tenant"

export function Casca() {
  const peers = usePeers()
  const grupos = useGrupos()
  const navegar = useNavigate()
  const { asn, erro } = useTenant()
  // a mesma consulta do provedor do tenant, para o "tentar de novo" e para o
  // estado da lista: a chave e a mesma, entao o dado e um so
  const lista = useAsns()

  const [paletaAberta, setPaletaAberta] = useState(false)
  // o que a tela aberta publica: a paleta e o Ctrl+S leem daqui
  const [acoes, setAcoes] = useState<AcoesDaTela>({})
  // o estado, e nao um ref, porque o seletor de ASN precisa re-renderizar
  // quando ele muda: e no render seguinte que a pergunta pela troca aparece ou
  // nao. Ele mora na casca porque as duas pontas estao embaixo dela - a tela
  // que publica, no Outlet, e o seletor, na barra lateral
  const [sujo, setSujo] = useState(false)

  const abrirPaleta = useCallback(() => setPaletaAberta(true), [])
  useAtalhos({ aoSalvar: acoes.aoSalvar, aoAbrirPaleta: abrirPaleta })

  const duplicar = acoes.aoDuplicar
  const copiarBloco = acoes.aoCopiarBloco

  const baixarBase = useCallback(async () => {
    // O /base.txt nao esta em /api, mas e do tenant como as outras rotas: sem
    // o `?asn=` o download bate num 422 no meio de uma acao que nao tem nada a
    // ver com o ASN. O fetch cru nao passa pelo cliente tipado, entao o
    // parametro entra na mao, e e por isso que o `tsc` nao cobra esta linha
    const resposta = await fetch(`/base.txt?asn=${asn}`)
    // o fetch cru nao passa pelo cliente, entao o 401 de sessao vencida
    // precisa do aviso aqui: sem ele o clique nao faria nada, calado
    if (sessaoVencida(resposta)) return
    // sem a conferencia, um 500 do servidor salvaria a pagina de erro com o
    // nome do bloco base
    if (!resposta.ok) return
    baixar(await resposta.text(), "base.txt")
  }, [asn])

  // Dois estados diferentes que o mesmo `asn` nulo produziria:
  // - a lista nao chegou (rede fora, 500): e falha de comunicacao, e o
  //   aviso com tentar de novo e o mesmo das outras telas;
  // - a lista chegou e esta vazia: e a pasta `peers/` sem arquivo, e o que
  //   a tela tem a fazer e oferecer o primeiro ASN.
  // Sem a distincao, a queda da unica rota que sustenta todas as outras
  // ficava invisivel: as consultas nem saem com o ASN nulo, entao tela
  // nenhuma tem erro proprio para mostrar.
  if (asn === null) {
    // O `erro` do contexto e zerado pelo TanStack quando a consulta sem dado e
    // refeita (o estado volta a `pending`), e o `errorUpdateCount` e o que
    // resta da falha enquanto o pedido corre: sem ele o proprio "tentar de
    // novo" cairia no estado vazio, dizendo que a pasta esta vazia enquanto a
    // lista ainda nem respondeu.
    // O `data === undefined` e o que separa este retentar do refetch de fundo
    // de quem ja tem dado, como nas outras quatro telas: o contador e cumulativo
    // e nunca zera, entao sem ele uma pasta que ja falhou uma vez e voltou
    // vazia viraria "nao deu para falar com a API" a cada refetch de fundo
    // (o foco da janela, o staleTime), por um pedido que nem esta falhando
    const tentando = lista.isFetching
    const falhou = erro !== null ||
      (tentando && lista.data === undefined && lista.errorUpdateCount > 0)
    if (falhou) {
      return (
        <Falha
          mensagem="não deu para falar com a API"
          tentando={tentando}
          aoTentar={() => void lista.refetch()}
        />
      )
    }
    // nem falha nem pasta vazia: a lista ainda nao chegou, e afirmar qualquer
    // das duas coisas aqui seria adivinhar
    return lista.isSuccess ? <SemTenant /> : null
  }

  const barra = (
    <BarraLateral
      peers={peers.data ?? []}
      grupos={grupos.data ?? []}
      aoNovo={navegar}
    />
  )

  return (
    // os dois contextos do rascunho envolvem a arvore inteira, e nao so o
    // Outlet: a barra lateral (o seletor que pergunta) esta fora do main, e a
    // tela que publica esta dentro dele
    <ContextoDefinirRascunho.Provider value={setSujo}>
      <ContextoLerRascunho.Provider value={sujo}>
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
                {/* A chave no ASN remonta a tela na troca: o rascunho de uma
                    rede nao tem o que fazer na outra, e sem remontar o primeiro
                    salvar depois da troca mandaria o texto da rede anterior com
                    o ?asn= da nova. A perda do rascunho na troca e o que a
                    tarefa 8 pergunta antes de deixar acontecer. */}
                <Outlet key={asn} />
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
      </ContextoLerRascunho.Provider>
    </ContextoDefinirRascunho.Provider>
  )
}
