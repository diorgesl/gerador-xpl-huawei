import { useEffect, useRef, useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"
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
import { chaves, lerRecusa, useGrupos, usePlano, type PeerForm } from "@/api/consultas"
// o `consultas.ts` nao reexporta o cliente: ele e o dono do cliente e o importa
// para os hooks, mas o export fica no cliente.ts
import { cliente } from "@/api/cliente"
import { usePeerInicial } from "@/api/inicial"
import { usePrevia } from "@/api/previa"
import { copiarComAviso } from "@/lib/copiar"
import { cn } from "@/lib/utils"
import { FormularioPeer } from "./FormularioPeer"
import { CAMPO_BRANCO } from "./camposPeer"

export function PeerTela() {
  const { id } = useParams()
  const [busca] = useSearchParams()
  const navegar = useNavigate()
  const consultas = useQueryClient()

  const ident = id ? Number(id) : null
  const de = busca.get("de")
  const tipo = busca.get("tipo") ?? "cliente"
  const copiando = de !== null

  const plano = usePlano()
  const grupos = useGrupos()
  const inicial = usePeerInicial(ident, de ? Number(de) : null, tipo)

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
      navegar("/peers", { replace: true })
    }
  }, [inicial.error, navegar])

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
  const comErro = Object.keys(erros).length > 0
  const erroIrr = recusaVale?.irr ?? null

  const abas: AbaSaida[] = [
    {
      id: "bloco",
      rotulo: "bloco do peer",
      conteudo: comErro ? null : previa.data?.bloco ?? null,
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
    onSuccess: (r) => {
      if (r.error) {
        const lida = lerRecusa(r.error)
        setRecusa({
          em: Date.now(),
          erros: lida.erros,
          irr: lida.erros.bgpq4 ?? lida.erros.asn ?? "a consulta ao IRR falhou",
        })
        return
      }
      // so a mensagem do IRR sai: os erros que o salvar deixou na tela ficam
      // com a validade que ja tinham, como no efeito que este render trocou
      setRecusa((atual) => (atual ? { ...atual, irr: null } : null))
      form.setValue("prefixos_v4", r.data.v4, { shouldDirty: true })
      form.setValue("prefixos_v6", r.data.v6, { shouldDirty: true })
      toast("prefixos do IRR no formulário; nada foi gravado")
    },
  })

  const salvar = useMutation({
    mutationFn: async () => {
      const corpo = form.getValues()
      return ident === null
        ? cliente.POST("/api/peers", { body: corpo })
        : cliente.PUT("/api/peers/{ident}", { params: { path: { ident } }, body: corpo })
    },
  })

  /** Grava e devolve o ID do registro gravado, ou nulo quando a API recusou. */
  async function gravar(): Promise<number | null> {
    const r = await salvar.mutateAsync()
    if (r.error) {
      if (r.response.status === 404) {
        toast.error("registro não encontrado")
        navegar("/peers", { replace: true })
        return null
      }
      // Sem o refetch daqui: ele subiria o `dataUpdatedAt` da previa e a marca
      // da recusa chegaria vencida, apagando no mesmo instante a lista que ela
      // acabou de escrever. Os erros do salvar ficam ate a proxima previa
      // responder, que e quando a lista de la substitui a de ca
      setRecusa({ em: Date.now(), erros: lerRecusa(r.error).erros, irr: null })
      return null
    }
    setRecusa(null)
    toast(`gravado em out/${r.data.arquivo}`)
    void consultas.invalidateQueries({ queryKey: chaves.peers })
    void consultas.invalidateQueries({ queryKey: chaves.plano })
    form.reset(r.data.registro.formulario)
    if (ident === null) navegar(`/peers/${r.data.registro.id}`, { replace: true })
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
    const r = await cliente.DELETE("/api/peers/{ident}", { params: { path: { ident: ident as number } } })
    if (r.error) {
      toast.error("não deu para excluir")
      return
    }
    setExcluindo(false)
    void consultas.invalidateQueries({ queryKey: chaves.peers })
    toast("peer excluído")
    navegar("/peers", { replace: true })
  }

  const grupo = (grupos.data ?? []).find((g) => String(g.id) === String(valores.grupo_id))

  // Uma falha de rede nao pode passar: sem o plano a tela fica vazia sem dizer
  // por que. O 404 e outro caminho, o do toast e da volta para /peers.
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
      <AvisoNaoSalvo sujo={sujo} />

      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-base font-semibold">{valores.nome || "peer novo"}</h1>
        <BadgeTipo tipo={valores.tipo} />
        <span className="dado text-xs text-muted-foreground">{inicial.data?.token || "sem token"}</span>
        <span className="dado text-xs text-muted-foreground">AS{valores.asn || "—"}</span>
        {grupo && <span className="text-xs text-muted-foreground">grupo {grupo.nome}</span>}

        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" onClick={() => void gravar()} disabled={salvar.isPending}>salvar</Button>
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
            sujo={sujo}
            carregando={previa.isFetching}
            erro={comErro ? "com erro" : null}
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
