import { useCallback, useEffect, useRef, useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { MoreHorizontal } from "lucide-react"
import { BadgeTipo } from "@/components/BadgeTipo"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { AvisoNaoSalvo } from "@/components/AvisoNaoSalvo"
import { Falha } from "@/components/Falha"
import { PainelSaida, type AbaSaida } from "@/components/PainelSaida"
import { NaoEncontrado } from "@/telas/NaoEncontrado"
import { chaves, lerRecusa, recusaComMarca, temRecusa, useGrupos, usePlano, type PeerForm } from "@/api/consultas"
import { camposDoErro } from "@/lib/campos"
import { avisarFalhaDeRede, escrever, falhaDoServidor } from "@/lib/aviso"
// o `consultas.ts` nao reexporta o cliente: ele e o dono do cliente e o importa
// para os hooks, mas o export fica no cliente.ts
import { cliente } from "@/api/cliente"
import { usePeerInicial } from "@/api/inicial"
import { usePrevia } from "@/api/previa"
import { copiarComAviso } from "@/lib/copiar"
import { cn } from "@/lib/utils"
import { usePublicarAcoes } from "@/app/acoes-contexto"
import { FormularioPeer } from "./FormularioPeer"
import { CAMPO_BRANCO } from "./camposPeer"

/**
 * A tela remonta quando o registro muda. O React Router reusa o elemento na
 * troca de `:id`, entao sem a chave o `useForm` sobrevive com os valores do
 * registro ANTERIOR, e o salvar grava eles no registro novo.
 */
export function TelaDoPeer() {
  const { id } = useParams()
  return <PeerTela key={id ?? "novo"} />
}

export function PeerTela() {
  const { id } = useParams()
  const [busca] = useSearchParams()
  const navegar = useNavigate()
  const consultas = useQueryClient()

  // `/peers/abc` casa na rota do `:id` sem ser um id: o Number virava NaN, o
  // GET respondia 422 (o inicial.ts so trata o 404) e o operador caia na falha
  // de rede, cujo "tentar de novo" nunca ia funcionar. Endereco que nao aponta
  // para registro nenhum e o mesmo caso do registro que nao existe
  const ident = id !== undefined && /^\d+$/.test(id) ? Number(id) : null
  const enderecoInvalido = id !== undefined && ident === null
  // O `de` so vale na tela do registro novo: com os dois na URL o id manda,
  // senao o cabecalho anuncia "copia de 3" com os valores do 3 na tela e o
  // salvar manda o id 8 do corpo no PUT do 7, que a API le como troca de
  // identidade - o peer 7 se perderia
  const de = ident === null ? busca.get("de") : null

  // A navegacao que a propria tela pede nao pode cair no aviso de alteracao nao
  // salva: o registro foi excluido, sumiu, ou acabou de ser gravado. A marca e um
  // ref porque o `useBlocker` le no momento da navegacao, e nao no render
  // seguinte: com um booleano, a navegacao deste instante veria o valor velho
  const saindoDeProposito = useRef(false)
  const local = useLocation()
  // A chave da localizacao muda a cada navegacao, inclusive quando o destino e
  // o MESMO caminho (o 404 de /peers redireciona para /peers). Com o pathname, a
  // marca ficaria presa em true no primeiro caso desses e o guarda ficaria
  // desligado pelo resto da vida da tela, em silencio
  useEffect(() => {
    saindoDeProposito.current = false
  }, [local.key])

  const irPara = useCallback(
    (destino: string, opcoes?: { replace?: boolean }) => {
      saindoDeProposito.current = true
      navegar(destino, opcoes)
    },
    [navegar],
  )
  const tipo = busca.get("tipo") ?? "cliente"
  const copiando = de !== null

  const plano = usePlano()
  const grupos = useGrupos()
  // Sem o `ligado` a consulta sairia com o ident nulo e traria o formulario em
  // branco de /peers/novo: e um pedido que a tela nem usa, para um endereco que
  // nao aponta para registro nenhum
  const inicial = usePeerInicial(ident, de ? Number(de) : null, tipo, !enderecoInvalido)

  const form = useForm<PeerForm>({ defaultValues: CAMPO_BRANCO })
  const valores = useWatch({ control: form.control }) as PeerForm
  const sujo = form.formState.isDirty

  // O que uma recusa escreveu na tela (a do salvar ou a da consulta ao IRR) e
  // ate quando ela vale. Sao os dois juntos porque uma previa nova derruba os
  // dois de uma vez, e porque o erro do IRR sai da mesma lista de erros.
  const [recusa, setRecusa] = useState<{ em: number; erros: Record<string, string>; irr: string | null } | null>(null)
  const [excluindo, setExcluindo] = useState(false)
  const [painel, setPainel] = useState<"formulario" | "saida">("formulario")
  const blocoRef = useRef<HTMLDivElement>(null)

  // O sujo entra por ref, e nao como dependencia do efeito: com ele na lista, o
  // salvamento bem-sucedido (que zera o `isDirty`) faz o efeito rodar de novo e
  // reaplicar o registro LIDO NA MONTAGEM, desfazendo na tela o que acabou de
  // ser gravado. A leitura aqui e so para nao sobrescrever o que o operador
  // esta digitando quando um refetch traz o registro.
  const sujoRef = useRef(sujo)
  useEffect(() => {
    sujoRef.current = sujo
  })

  useEffect(() => {
    if (inicial.data && !sujoRef.current) form.reset(inicial.data.formulario)
  }, [inicial.data, form])

  useEffect(() => {
    if (inicial.error?.message === "nao_encontrado") {
      toast.error("registro não encontrado")
      irPara("/peers", { replace: true })
    }
  }, [inicial.error, irPara])

  const previa = usePrevia({ tipo: "peers", id: ident, valores, ligado: Boolean(inicial.data) })

  // A remocao vem do registro salvo, e nao da previa: ela desfaz o que esta no
  // equipamento, e o que esta no equipamento e o que foi gravado
  const saida = useQuery({
    queryKey: ["saida", "peer", ident],
    enabled: ident !== null && inicial.data !== undefined,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/peers/{ident}/saida", {
        params: { path: { ident: ident as number } },
      })
      return error ? null : data
    },
  })

  // A recusa vale ate a proxima previa responder, que traz a lista de erros
  // dela. A validade sai no render, e nao de um efeito que zera o estado: o
  // `set-state-in-effect` do lint e erro nesta config, a mesma razao que levou
  // o rascunho do campo de lista para o render. O `em` e lido no proprio
  // evento, e nao do fechamento do handler: a previa refaz o pedido quando a
  // janela volta ao foco, e a marca do fechamento chegaria velha depois disso.
  const recusaVale = recusa !== null && previa.dataUpdatedAt <= recusa.em ? recusa : null
  const erros = recusaVale && Object.keys(recusaVale.erros).length > 0 ? recusaVale.erros : previa.data?.erros ?? {}
  const avisos = previa.data?.avisos ?? []
  // So as chaves que apontam para um campo do formulario contam. O bgpq4 fora
  // do ar nao diz nada sobre o que esta escrito nos campos, e contar o mapa
  // inteiro apagava o painel ("a previa volta quando os erros forem
  // corrigidos") por causa de uma consulta que falhou, sem nenhum campo para
  // corrigir. E o mesmo que a tela dos prefixos ja faz com as duas caixas
  const comErro = Object.entries(erros).some(
    ([chave, mensagem]) => Boolean(mensagem) && camposDoErro(chave, valores.tipo).length > 0,
  )
  const erroIrr = recusaVale?.irr ?? null

  const abas: AbaSaida[] = [
    {
      id: "bloco",
      rotulo: "bloco do peer",
      // a previa que nao veio nao e previa nenhuma: sem o `isError` o painel
      // ficaria em "gerando previa..." para sempre, esperando por um bloco que
      // nao vem
      conteudo: comErro || previa.isError ? null : previa.data?.bloco ?? null,
      arquivo: previa.data?.arquivo ?? null,
      salvo: previa.data?.salvo ?? null,
    },
  ]
  if (saida.data?.remover) {
    abas.push({
      id: "remover", rotulo: "remoção", conteudo: saida.data.remover,
      arquivo: saida.data.arquivo, salvo: saida.data.remover, soLeitura: true,
    })
  }
  if (previa.data?.criar_lista) {
    abas.push({
      id: "criar", rotulo: "ao criar o peer", conteudo: previa.data.criar_lista,
      arquivo: null, salvo: saida.data?.criar_lista ?? null,
    })
  }

  // O IRR substitui os prefixos do formulario sem gravar nada: e o mesmo
  // botao da tela antiga, que o operador aperta antes de salvar
  const irr = useMutation({
    mutationFn: (forcar: boolean) =>
      cliente.POST("/api/irr", {
        body: { asn: form.getValues("asn"), apelido: form.getValues("apelido"), forcar },
      }),
    onSuccess: (r, forcar) => {
      if (r.error) {
        const lida = lerRecusa(r.error)
        // o 502 do bgpq4 e falha do servidor: o aviso com o caminho de volta
        // entra junto da mensagem, que e a da consulta e nao a de um campo
        if (falhaDoServidor(r.response.status)) avisarFalhaDeRede(() => irr.mutate(forcar))
        setRecusa(recusaComMarca(r.error, lida.erros.bgpq4 ?? lida.erros.asn ?? "a consulta ao IRR falhou"))
        return
      }
      // so a mensagem do IRR sai: os erros que o salvar deixou na tela ficam
      // com a validade que ja tinham, como no efeito que este render trocou
      setRecusa((atual) => (atual ? { ...atual, irr: null } : null))
      form.setValue("prefixos_v4", r.data.v4, { shouldDirty: true })
      form.setValue("prefixos_v6", r.data.v6, { shouldDirty: true })
      toast("prefixos do IRR no formulário; nada foi gravado")
    },
    // a excecao de rede nao passa pelo ramo do `r.error`: o openapi-fetch a
    // re-lanca, e sem este caminho o clique na consulta nao deixava rastro
    onError: (_erro, forcar) => avisarFalhaDeRede(() => irr.mutate(forcar)),
  })

  const salvar = useMutation({
    mutationFn: async () => {
      const corpo = form.getValues()
      return ident === null
        ? cliente.POST("/api/peers", { body: corpo })
        : cliente.PUT("/api/peers/{ident}", { params: { path: { ident } }, body: corpo })
    },
  })

  /**
   * Grava e devolve o ID do registro gravado, ou nulo quando a API recusou ou
   * quando a escrita nem chegou.
   */
  async function gravar(): Promise<number | null> {
    // O `escrever` e quem apanha a excecao do fetch: sem ele o `mutateAsync`
    // rejeitava, a excecao subia por esta funcao e nao havia nem aviso na tela
    // nem quem a apanhasse depois (o "salvar e copiar" a levava ao painel, que
    // dizia "nada foi copiado: a operacao nao terminou")
    const r = await escrever(() => salvar.mutateAsync(), () => void gravar())
    if (r === null) return null
    if (r.error) {
      if (r.response.status === 404) {
        toast.error("registro não encontrado")
        irPara("/peers", { replace: true })
        return null
      }
      // O 5xx e falha do servidor, e nao do formulario: o aviso com o caminho
      // de volta entra junto. Sem corpo de recusa nao ha mensagem de campo a
      // mostrar, e o `_corpo` do lerRecusa seria ruido em cima do aviso
      if (falhaDoServidor(r.response.status)) {
        avisarFalhaDeRede(() => void gravar())
        if (!temRecusa(r.error)) return null
      }
      // Sem o refetch daqui: ele subiria o `dataUpdatedAt` da previa e a marca
      // da recusa chegaria vencida, apagando no mesmo instante a lista que ela
      // acabou de escrever. Os erros do salvar ficam ate a proxima previa
      // responder, que e quando a lista de la substitui a de ca
      setRecusa(recusaComMarca(r.error))
      return null
    }
    setRecusa(null)
    toast(`gravado em out/${r.data.arquivo}`)
    void consultas.invalidateQueries({ queryKey: chaves.peers })
    void consultas.invalidateQueries({ queryKey: chaves.plano })
    // A aba de remocao vem de GET /saida, e nao da previa: sem invalidar, ela
    // continuaria com o bloco de ANTES do salvar, e o copiar dela levaria para
    // o equipamento um bloco que nao vale mais
    void consultas.invalidateQueries({ queryKey: ["saida", "peer", ident] })
    form.reset(r.data.registro.formulario)
    // O ID do formulario move o registro no servidor (a API documenta isso):
    // se ele mudou, a URL tem que acompanhar, senao o proximo salvar bate no
    // 404 de um registro que existe com outro id
    if (String(r.data.registro.id) !== (id ?? "")) irPara(`/peers/${r.data.registro.id}`, { replace: true })
    return r.data.registro.id
  }

  // O booleano de volta e "chegou na area de transferencia", e nao "a funcao
  // rodou": salvar recusado e copia que caiu na selecao manual devolvem false,
  // e o painel so confirma o que copiou de fato
  async function salvarECopiar(aba: AbaSaida): Promise<boolean> {
    const gravado = await gravar()
    if (gravado === null) return false
    // O que vai para a area de transferencia e o bloco do registro gravado, e
    // nao o da previa: o que vale e o que foi para o out/ agora
    const { data } = await cliente.GET("/api/peers/{ident}/saida", {
      params: { path: { ident: gravado } },
    })
    const texto = aba.id === "criar" ? data?.criar_lista : aba.id === "remover" ? data?.remover : data?.bloco
    if (!texto) return false
    return (await copiarComAviso(texto, blocoRef.current)) === "copiado"
  }

  async function excluir() {
    const r = await escrever(
      () => cliente.DELETE("/api/peers/{ident}", { params: { path: { ident: ident as number } } }),
      () => void excluir(),
    )
    if (r === null) return
    if (r.error) {
      toast.error("não deu para excluir")
      // o 5xx tem o caminho de volta, e o 404 nao tem o que repetir
      if (falhaDoServidor(r.response.status)) avisarFalhaDeRede(() => void excluir())
      return
    }
    setExcluindo(false)
    void consultas.invalidateQueries({ queryKey: chaves.peers })
    toast("peer excluído")
    irPara("/peers", { replace: true })
  }

  // A paleta oferece o que a tela aberta sabe fazer, e o que ela nao publica
  // nao aparece la: sem esta chamada, o "duplicar o registro aberto" e o
  // "copiar o bloco aberto" ficam mortos, que foi o que aconteceu ate aqui
  //
  // A aba corrente vem do painel pelo `aoTrocarAba`: a copia da paleta tem que
  // ser a da aba que o operador esta vendo, e nao a primeira do painel
  //
  // O `?? abas[0]` e o mesmo fallback que o painel faz quando a aba corrente
  // sai da lista (o quadro "ao criar" some quando a previa deixa de mandar o
  // `criar_lista`): sem ele, a tela acharia que nao ha bloco nenhum enquanto o
  // painel mostra o da primeira aba, e a paleta ofereceria a copia de um bloco
  // que nao e o da tela - ou nenhuma
  //
  // O bloco aberto pode nao existir (a previa em erro chega com conteudo nulo):
  // ai o item nem aparece, em vez de aparecer e nao fazer nada
  const [abaAtiva, setAbaAtiva] = useState(abas[0]?.id ?? "")
  const blocoAberto = (abas.find((a) => a.id === abaAtiva) ?? abas[0])?.conteudo ?? null
  usePublicarAcoes({
    // Sem o dado na tela o formulario nem esta montado: o Ctrl+S mandaria um PUT
    // com o formulario em branco, e a recusa da API nao apareceria aqui, porque
    // quem mostra a recusa e o formulario
    aoSalvar: plano.data && inicial.data ? () => void gravar() : undefined,
    // O duplicar da paleta navega como o do cabecalho, com `navegar` e nao com
    // `irPara`: a copia vem do registro SALVO, entao a alteracao nao salva se
    // perde, e o operador tem que poder dizer nao. O mesmo comando nao pode
    // perguntar num lugar e nao no outro
    aoDuplicar: ident === null ? undefined : () => navegar(`/peers/novo?de=${ident}`),
    aoCopiarBloco: blocoAberto ? () => void copiarComAviso(blocoAberto, blocoRef.current) : undefined,
  })

  const grupo = (grupos.data ?? []).find((g) => String(g.id) === String(valores.grupo_id))

  // O endereco que nao aponta para registro nenhum tem a tela dele: nao ha o
  // que tentar de novo, e a tela de falha de rede mentiria sobre o problema
  if (enderecoInvalido) return <NaoEncontrado />

  // Uma falha de rede nao pode passar: sem o plano a tela fica vazia sem dizer
  // por que. O 404 e outro caminho, o do toast e da volta para /peers.
  //
  // O aviso sobrevive ao tentar de novo, e nao so ao erro: o TanStack zera o
  // `error` de uma consulta sem dado quando ela e refeita (o estado volta a
  // `pending`), entao sem o `retentando` o clique cairia no formulario em
  // branco ate a resposta chegar, e o botao que desabilita so existiria depois
  // disso. O `errorUpdateCount` e o que resta da falha depois do refetch, e o
  // `data === undefined` deixa de fora o refetch de fundo de quem ja tem dado
  const tentando = plano.isFetching || inicial.isFetching
  const retentando = (c: { isFetching: boolean; data: unknown; errorUpdateCount: number }) =>
    c.isFetching && c.data === undefined && c.errorUpdateCount > 0
  const falhou =
    (plano.isError || inicial.isError || retentando(plano) || retentando(inicial)) &&
    inicial.error?.message !== "nao_encontrado"
  if (falhou) {
    return (
      <Falha
        mensagem="não deu para falar com a API"
        tentando={tentando}
        aoTentar={() => { void plano.refetch(); void inicial.refetch() }}
      />
    )
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 p-3">
      <AvisoNaoSalvo sujo={sujo} permitir={() => saindoDeProposito.current} />

      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-base font-semibold">{valores.nome || "peer novo"}</h1>
        <BadgeTipo tipo={valores.tipo} />
        <span className="dado text-xs text-muted-foreground">{inicial.data?.token || "sem token"}</span>
        <span className="dado text-xs text-muted-foreground">AS{valores.asn || "—"}</span>
        {grupo && <span className="text-xs text-muted-foreground">grupo {grupo.nome}</span>}

        <div className="ml-auto flex items-center gap-2">
          {/* Sem o registro na mao o botao nao salva: a janela entre a montagem e
              a leitura e a unica em que o cabecalho existe sem o formulario, e o
              salvar ali mandaria o formulario em branco */}
          <Button size="sm" onClick={() => void gravar()} disabled={salvar.isPending || !inicial.data}>salvar</Button>
          {ident !== null && (
            <Button size="sm" variant="ghost" onClick={() => navegar(`/peers/novo?de=${ident}`)}>
              duplicar
            </Button>
          )}
          {ident !== null && (
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button size="sm" variant="ghost" aria-label="mais ações" />}>
                <MoreHorizontal className="size-4" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {/* o Item do Base UI nao tem onSelect (o do Radix tinha): o
                    clique e o onClick, e o onSelect nao dispara nunca */}
                <DropdownMenuItem onClick={() => setExcluindo(true)}>excluir</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </header>

      {copiando && (
        <p className="rounded border border-aviso-texto/30 bg-aviso-fundo p-2 text-xs text-aviso-texto">
          cópia de {inicial.data?.token}: troque ASN, IPs remotos e o que mais for único antes de salvar
        </p>
      )}

      {/* Abaixo de 1280px as duas colunas viram abas. O formulario e montado uma
          vez so: duplicar a arvore duplicaria os id dos campos */}
      <div className="flex gap-2 xl:hidden">
        {(["formulario", "saida"] as const).map((p) => (
          <Button key={p} size="sm" variant={painel === p ? "secondary" : "ghost"} onClick={() => setPainel(p)}>
            {p === "formulario" ? "formulário" : "saída"}
          </Button>
        ))}
      </div>

      <div className="grid min-h-0 flex-1 gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,42rem)]">
        <div className={cn("min-w-0 overflow-y-auto", painel === "saida" && "hidden xl:block")}>
          {plano.data && inicial.data && (
            <FormularioPeer
              form={form}
              plano={plano.data}
              grupos={(grupos.data ?? []).map((g) => ({ valor: String(g.id), rotulo: `${g.nome} (${g.tipo})` }))}
              erros={erros}
              avisos={avisos}
              erroIrr={erroIrr}
              aoConsultarIrr={(forcar) => irr.mutate(forcar)}
              aoIrPara={(campo, secao) => {
                if (!campo && !secao) return
                // Sem campo o alvo e a secao: e o caso do erro que cobre varios
                // campos, em que apontar um deles seria mentir sobre onde esta
                if (!campo) {
                  document.getElementById(`secao-${secao}`)?.scrollIntoView({ block: "start" })
                  return
                }
                const alvo = document.querySelector<HTMLElement>(`[data-campo="${campo}"] input, [data-campo="${campo}"] textarea, [data-campo="${campo}"] button`)
                alvo?.focus()
                alvo?.scrollIntoView({ block: "center" })
              }}
            />
          )}
        </div>

        <div ref={blocoRef} className={cn("min-w-0 xl:sticky xl:top-3 xl:self-start", painel === "formulario" && "hidden xl:block")}>
          <PainelSaida
            abas={abas}
            aoTrocarAba={setAbaAtiva}
            sujo={sujo}
            carregando={previa.isFetching}
            erro={comErro ? "com erro" : previa.isError ? "não deu para gerar a prévia" : null}
            onCopiar={async (aba) =>
              aba.conteudo ? (await copiarComAviso(aba.conteudo, blocoRef.current)) === "copiado" : false
            }
            onSalvarECopiar={salvarECopiar}
          />
        </div>
      </div>

      <Dialog open={excluindo} onOpenChange={setExcluindo}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Excluir o peer {inicial.data?.token}?</DialogTitle>
            <DialogDescription>
              O registro sai do peers.yaml e o arquivo {inicial.data?.token} sai de out/. Isto não desfaz nada no equipamento.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setExcluindo(false)}>cancelar</Button>
            <Button variant="destructive" onClick={() => void excluir()}>excluir</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
