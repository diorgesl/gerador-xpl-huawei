import { useCallback, useEffect, useRef, useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom"
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
import { cliente } from "@/api/cliente"
import { chaves, lerRecusa, recusaComMarca, temRecusa, usePlano, type GrupoForm } from "@/api/consultas"
import { camposDoErro } from "@/lib/campos"
import { avisarFalhaDeRede, escrever, falhaDoServidor } from "@/lib/aviso"
import { useGrupoInicial } from "@/api/inicial"
import { usePrevia } from "@/api/previa"
import { copiarComAviso } from "@/lib/copiar"
import { cn } from "@/lib/utils"
import { usePublicarAcoes } from "@/app/acoes-contexto"
import { FormularioGrupo } from "./FormularioGrupo"
import { CAMPO_BRANCO_GRUPO } from "./camposGrupo"

export function GrupoTela() {
  const { id } = useParams()
  const [busca] = useSearchParams()
  const navegar = useNavigate()
  const consultas = useQueryClient()

  // `/grupos/abc` e o mesmo caso do peer: um endereco que nao aponta para
  // registro nenhum, e nao uma API fora do ar
  const ident = id !== undefined && /^\d+$/.test(id) ? Number(id) : null
  const enderecoInvalido = id !== undefined && ident === null
  // O `de` so vale na tela do registro novo, como no peer: com os dois na URL
  // o id manda, senao o cabecalho anuncia "copia de 3" com os valores do 3 na
  // tela e o salvar grava no id da URL com o corpo da copia
  const de = ident === null ? busca.get("de") : null

  // A navegacao que a propria tela pede nao pode cair no aviso de alteracao nao
  // salva: o registro foi excluido, sumiu, ou acabou de ser gravado. A marca e um
  // ref porque o `useBlocker` le no momento da navegacao, e nao no render
  // seguinte: com um booleano, a navegacao deste instante veria o valor velho
  const saindoDeProposito = useRef(false)
  const local = useLocation()
  // A chave da localizacao muda a cada navegacao, inclusive quando o destino e
  // o MESMO caminho (o 404 de /grupos redireciona para /grupos). Com o pathname, a
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
  const tipo = busca.get("tipo") ?? "parceiro"
  const copiando = de !== null

  const plano = usePlano()
  // sem o `ligado` a consulta sairia com o ident nulo e traria o grupo em
  // branco de /grupos/novo, que e um pedido que a tela nem vai usar
  const inicial = useGrupoInicial(ident, de ? Number(de) : null, tipo, !enderecoInvalido)

  const form = useForm<GrupoForm>({ defaultValues: CAMPO_BRANCO_GRUPO })
  const valores = useWatch({ control: form.control }) as GrupoForm
  const sujo = form.formState.isDirty

  // A recusa guarda a marca do evento junto dos erros: e com ela que a
  // validade dos dois e decidida no render
  const [recusa, setRecusa] = useState<{ em: number; erros: Record<string, string>; irr: string | null } | null>(null)
  const [errosDoGrupo, setErrosDoGrupo] = useState<Record<string, string>>({})
  const [excluindo, setExcluindo] = useState(false)
  const [painel, setPainel] = useState<"formulario" | "saida">("formulario")
  const blocoRef = useRef<HTMLDivElement>(null)

  // O sujo entra por ref, e nao como dependencia do efeito, como na PeerTela:
  // com ele na lista, o salvamento bem-sucedido (que zera o `isDirty`) faz o
  // efeito rodar de novo e reaplicar o registro LIDO NA MONTAGEM, desfazendo na
  // tela o que acabou de ser gravado. A leitura aqui e so para nao sobrescrever
  // o que o operador esta digitando quando um refetch traz o registro.
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
      irPara("/grupos", { replace: true })
    }
  }, [inicial.error, irPara])

  const previa = usePrevia({ tipo: "grupos", id: ident, valores, ligado: Boolean(inicial.data) })

  // O grupo nao tem bloco de remocao: o do membro e que desfaz a sessao
  const saida = useQuery({
    queryKey: ["saida", "grupo", ident],
    enabled: ident !== null && inicial.data !== undefined,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/grupos/{ident}/saida", {
        params: { path: { ident: ident as number } },
      })
      return error ? null : data
    },
  })

  // A recusa vale ate a proxima previa responder, como na tela do peer, e a
  // validade sai no render pelo mesmo motivo (o `set-state-in-effect` e erro do
  // lint nesta config)
  const recusaVale = recusa !== null && previa.dataUpdatedAt <= recusa.em ? recusa : null
  const erros = recusaVale && Object.keys(recusaVale.erros).length > 0 ? recusaVale.erros : previa.data?.erros ?? {}
  // So as chaves que apontam para um campo do formulario contam, como no peer e
  // na tela dos prefixos: a chave do bgpq4 nao tem campo, e contar o mapa
  // inteiro apagava o painel por causa de uma consulta que falhou
  const comErro = Object.entries(erros).some(
    ([chave, mensagem]) => Boolean(mensagem) && camposDoErro(chave, valores.tipo, true).length > 0,
  )
  const erroIrr = recusaVale?.irr ?? null

  const abas: AbaSaida[] = [
    {
      id: "bloco", rotulo: "bloco do grupo",
      // a previa que nao veio nao e previa nenhuma: sem o `isError` o painel
      // ficaria em "gerando previa..." para sempre
      conteudo: comErro || previa.isError ? null : previa.data?.bloco ?? null,
      arquivo: previa.data?.arquivo ?? null, salvo: previa.data?.salvo ?? null,
    },
  ]
  if (previa.data?.criar_lista) {
    abas.push({
      id: "criar", rotulo: "ao criar o grupo", conteudo: previa.data.criar_lista,
      arquivo: null, salvo: saida.data?.criar_lista ?? null,
    })
  }

  const irr = useMutation({
    mutationFn: (forcar: boolean) =>
      cliente.POST("/api/irr", {
        body: { asn: form.getValues("asn"), apelido: form.getValues("nome"), forcar },
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
      // com a validade que ja tinham
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
        ? cliente.POST("/api/grupos", { body: corpo })
        : cliente.PUT("/api/grupos/{ident}", { params: { path: { ident } }, body: corpo })
    },
  })

  async function gravar(): Promise<number | null> {
    // O `escrever` e quem apanha a excecao do fetch: sem ele o `mutateAsync`
    // rejeitava, a excecao subia por esta funcao sem aviso nenhum na tela
    const r = await escrever(() => salvar.mutateAsync(), () => void gravar())
    if (r === null) return null
    if (r.error) {
      if (r.response.status === 404) {
        toast.error("registro não encontrado")
        irPara("/grupos", { replace: true })
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
      // A recusa por `id` acontece quando o formulario em branco foi aberto
      // com um id que outro registro tomou no meio do caminho. O formulario do
      // grupo nao tem esse campo, entao sem esta linha a unica saida era
      // recarregar a tela e perder o que foi digitado: a tela rebusca o
      // proximo livre e o operador so clica em salvar de novo
      if (recusaComMarca(r.error).erros.id && ident === null) {
        const livre = await cliente.GET("/api/grupos/novo", { params: { query: { tipo } } })
        // o id do formulario e texto (o `GrupoForm.id`) e o do registro e
        // numero: sem o String o `tsc -b` reprova a linha, e a tela ja
        // converte assim no `String(r.data.registro.id)` do salvamento
        if (livre.data) form.setValue("id", String(livre.data.id), { shouldDirty: true })
      }
      return null
    }
    setRecusa(null)
    toast(`gravado em out/${r.data.arquivo}`)
    void consultas.invalidateQueries({ queryKey: chaves.grupos })
    void consultas.invalidateQueries({ queryKey: chaves.peers })
    // o /api/plano monta as listas de "ja cadastrado" (o POP e o aprendizado)
    // de peers MAIS grupos: sem invalidar, o grupo recem-gravado nao entra nas
    // sugestoes ate a janela voltar ao foco
    void consultas.invalidateQueries({ queryKey: chaves.plano })
    // o criar_lista e o salvo da aba "ao criar" vem de GET /saida, e nao da
    // previa: sem invalidar, a aba continuaria com o de antes do salvar
    void consultas.invalidateQueries({ queryKey: ["saida", "grupo", ident] })
    form.reset(r.data.registro.formulario)
    // o mesmo do peer: o id do formulario move o registro, e a URL acompanha
    if (String(r.data.registro.id) !== (id ?? "")) irPara(`/grupos/${r.data.registro.id}`, { replace: true })
    return r.data.registro.id
  }

  // O booleano de volta e "chegou na area de transferencia": o painel so
  // confirma o que copiou de fato, e um salvar recusado devolve false
  async function salvarECopiar(aba: AbaSaida): Promise<boolean> {
    const gravado = await gravar()
    if (gravado === null) return false
    const { data } = await cliente.GET("/api/grupos/{ident}/saida", { params: { path: { ident: gravado } } })
    const texto = aba.id === "criar" ? data?.criar_lista : data?.bloco
    if (!texto) return false
    return (await copiarComAviso(texto, blocoRef.current)) === "copiado"
  }

  async function excluir() {
    const r = await escrever(
      () => cliente.DELETE("/api/grupos/{ident}", { params: { path: { ident: ident as number } } }),
      () => void excluir(),
    )
    if (r === null) return
    if (r.error) {
      // o 5xx tem o caminho de volta, e sem corpo de recusa nao ha mensagem
      // para o dialogo: o `_corpo` do lerRecusa seria ruido em cima do aviso
      if (falhaDoServidor(r.response.status)) {
        avisarFalhaDeRede(() => void excluir())
        if (!temRecusa(r.error)) return
      }
      // o 409 traz os membros na mesma mensagem do POST /grupo/{nome}/excluir
      setErrosDoGrupo(lerRecusa(r.error).erros)
      return
    }
    setExcluindo(false)
    void consultas.invalidateQueries({ queryKey: chaves.grupos })
    toast("grupo excluído")
    irPara("/grupos", { replace: true })
  }

  // A paleta oferece o que a tela aberta sabe fazer: sem esta publicacao, o
  // "duplicar o registro aberto" e o "copiar o bloco aberto" nao aparecem. O
  // duplicar navega como o do cabecalho (com `navegar`), e o copiar so aparece
  // quando ha bloco, pelas mesmas razoes que valem na tela do peer
  //
  // O bloco aberto e o da aba que o painel avisa pelo `aoTrocarAba`, e nao o da
  // primeira aba: com o quadro "ao criar" na tela, a copia da paleta tem que
  // levar o que o operador esta vendo
  //
  // O `?? abas[0]` e o fallback do proprio painel para quando a aba corrente
  // sai da lista, e e ele que impede a paleta de oferecer a copia de um bloco
  // que nao e o da tela
  const [abaAtiva, setAbaAtiva] = useState(abas[0]?.id ?? "")
  const blocoAberto = (abas.find((a) => a.id === abaAtiva) ?? abas[0])?.conteudo ?? null
  usePublicarAcoes({
    // O Ctrl+S nao pode gravar numa tela que ainda nao tem o registro: enquanto
    // o plano ou o registro nao chegaram, o formulario esta em branco e o PUT
    // sairia com ele, sem que a recusa apareca na tela. E a mesma guarda do
    // formulario, e sem ela o atalho vale tambem na tela de falha de rede
    aoSalvar: plano.data && inicial.data ? () => void gravar() : undefined,
    aoDuplicar: ident === null ? undefined : () => navegar(`/grupos/novo?de=${ident}`),
    aoCopiarBloco: blocoAberto ? () => void copiarComAviso(blocoAberto, blocoRef.current) : undefined,
  })

  // O endereco que nao aponta para registro nenhum tem a tela dele, como no peer
  if (enderecoInvalido) return <NaoEncontrado />

  const falhou = (plano.isError || inicial.isError) && inicial.error?.message !== "nao_encontrado"
  if (falhou) {
    return (
      <Falha
        mensagem="não deu para falar com a API"
        aoTentar={() => { void plano.refetch(); void inicial.refetch() }}
      />
    )
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 p-3">
      <AvisoNaoSalvo sujo={sujo} permitir={() => saindoDeProposito.current} />

      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-base font-semibold">{valores.nome || "grupo novo"}</h1>
        <BadgeTipo tipo={valores.tipo} />
        {inicial.data?.membros.map((m) => (
          <Link key={m.id} to={`/peers/${m.id}`} className="dado text-xs underline">
            {m.token}
          </Link>
        ))}

        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" onClick={() => void gravar()} disabled={salvar.isPending || !inicial.data}>salvar</Button>
          {ident !== null && (
            <Button size="sm" variant="ghost" onClick={() => navegar(`/grupos/novo?de=${ident}`)}>duplicar</Button>
          )}
          {ident !== null && (
            <DropdownMenu>
              <DropdownMenuTrigger render={<Button size="sm" variant="ghost" aria-label="mais ações" />}>
                <MoreHorizontal className="size-4" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {/* o Menu.Item do Base UI dispara o onClick; o `onSelect` que a
                    versao antiga do shadcn usava nao existe e nao dispara */}
                <DropdownMenuItem onClick={() => setExcluindo(true)}>excluir</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </header>

      {copiando && (
        <p className="rounded border border-aviso-texto/30 bg-aviso-fundo p-2 text-xs text-aviso-texto">
          cópia de {inicial.data?.nome}: o nome do grupo é o que o salvar recusa quando repetido
        </p>
      )}

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
            <FormularioGrupo
              form={form}
              plano={plano.data}
              erros={erros}
              avisos={previa.data?.avisos ?? []}
              erroIrr={erroIrr}
              aoConsultarIrr={(forcar) => irr.mutate(forcar)}
              aoIrPara={(campo) => {
                if (!campo) return
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

      <Dialog open={excluindo} onOpenChange={(v) => { setExcluindo(v); if (!v) setErrosDoGrupo({}) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Excluir o grupo {inicial.data?.nome}?</DialogTitle>
            <DialogDescription>
              O grupo sai do peers.yaml. Isto não desfaz nada no equipamento.
            </DialogDescription>
          </DialogHeader>

          {/* Toda mensagem da recusa sai, e nao so a dos membros: um 404 traz a
              chave `_` e um corpo que o lerRecusa nao entende traz `_corpo`, e
              nos dois o dialogo ficava aberto, mudo, com o operador clicando */}
          {Object.entries(errosDoGrupo).filter(([, mensagem]) => mensagem).map(([chave, mensagem]) => (
            <p key={chave} role="alert" className="rounded border border-erro-texto/30 bg-erro-fundo p-2 text-xs text-erro-texto">
              {mensagem}
            </p>
          ))}

          <DialogFooter>
            {/* o onOpenChange limpa a recusa, e este caminho fechava por fora
                dele: o texto de antes voltava na abertura seguinte */}
            <Button variant="ghost" onClick={() => { setExcluindo(false); setErrosDoGrupo({}) }}>cancelar</Button>
            <Button variant="destructive" onClick={() => void excluir()}>excluir</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

/**
 * A tela remonta quando o registro muda, como no peer: sem a chave, os campos
 * ficam com os valores do registro ANTERIOR e o salvar grava eles no novo.
 */
export function TelaDoGrupo() {
  const { id } = useParams()
  return <GrupoTela key={id ?? "novo"} />
}
