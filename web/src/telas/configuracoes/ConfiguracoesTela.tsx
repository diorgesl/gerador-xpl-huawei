import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Campo } from "@/components/Campo"
import { Falha } from "@/components/Falha"
import { usePublicarAcoes } from "@/app/acoes-contexto"
import { useTema } from "@/app/tema"
import { useAsn } from "@/app/tenant"
import { cliente } from "@/api/cliente"
import { chaves, lerRecusa, usePlano, type RedeAtual } from "@/api/consultas"
import { avisarFalhaDeRede, falhaDoServidor } from "@/lib/aviso"
import { cn } from "@/lib/utils"

export function ConfiguracoesTela() {
  const consultas = useQueryClient()
  const plano = usePlano()
  const [tema, trocarTema] = useTema()
  // o PUT e uma rota de dados como as outras: o tenant vai no `?asn=`, e nao
  // no corpo, que so carrega o que a tela edita
  const asn = useAsn()
  const [erros, setErros] = useState<Record<string, string>>({})

  // O que o operador escreveu, campo a campo, e so ele: a tela mostra este
  // rascunho por cima do que o /api/plano trouxe. Nao e um efeito que copia o
  // dado para dentro do estado, por duas razoes: o `set-state-in-effect` do
  // lint e erro nesta config (foi o que tirou o rascunho dos prefixos do
  // efeito), e o copiar passaria por cima do que esta sendo digitado, porque o
  // refetch do foco e a invalidacao depois do salvar chegam pelo mesmo caminho
  // de um `plano.data` novo. O `??` e por campo de proposito: o campo que
  // ninguem tocou acompanha o plano, e nao fica congelado no que estava na
  // tela quando o outro foi editado
  const [rascunho, setRascunho] = useState<Partial<RedeAtual>>({})
  const carregado: RedeAtual = plano.data?.rede ?? { asn: "", politica: "" }
  const rede: RedeAtual = {
    asn: rascunho.asn ?? carregado.asn,
    politica: rascunho.politica ?? carregado.politica,
  }

  const gravar = useMutation({
    mutationFn: () => cliente.PUT("/api/rede", {
      params: { query: { asn: Number(asn) } },
      body: { politica: rede.politica },
    }),
    onSuccess: (r) => {
      if (r.error) {
        // o 5xx e falha do servidor, e nao do AS digitado: o aviso com o
        // caminho de volta entra junto da recusa, se houver uma
        if (falhaDoServidor(r.response.status)) avisarFalhaDeRede(() => gravar.mutate())
        setErros(lerRecusa(r.error).erros)
        return
      }
      setErros({})
      toast("AS da rede gravado")
      // o AS entra no cabecalho da barra lateral e no nome de toda community:
      // tudo que estava na tela fica velho de uma vez
      void consultas.invalidateQueries({ queryKey: chaves.plano })
      void consultas.invalidateQueries({ queryKey: chaves.peers })
      void consultas.invalidateQueries({ queryKey: chaves.grupos })
      void consultas.invalidateQueries({ queryKey: chaves.blocos })
    },
    // a excecao de rede nao passa pelo ramo do `r.error`: o openapi-fetch a
    // re-lanca, e sem este caminho o clique em gravar nao deixava rastro
    onError: () => avisarFalhaDeRede(() => gravar.mutate()),
  })

  // Sem o dado na tela o Ctrl+S nao grava: o namespace ainda nao chegou, e um
  // PUT daqui o apagaria, porque o branco e o estado "nao declarado" do
  // formulario. O `aoSalvar` e a unica acao que esta tela publica: nao ha
  // registro para duplicar nem bloco para copiar
  usePublicarAcoes({
    aoSalvar: plano.data ? () => gravar.mutate() : undefined,
  })

  // O aviso sobrevive ao tentar de novo, e nao so ao erro: o TanStack zera o
  // `error` de uma consulta sem dado quando ela e refeita (o estado volta a
  // `pending`), entao sem o `retentando` o botao que desabilita so existiria
  // depois da resposta. O `errorUpdateCount` e o que resta da falha depois do
  // refetch, e o `data === undefined` deixa de fora o refetch de fundo de quem
  // ja tem o plano
  const tentando = plano.isFetching
  const retentando = tentando && plano.data === undefined && plano.errorUpdateCount > 0
  const falhou = plano.isError || retentando

  return (
    <div className="flex max-w-xl flex-col gap-4 p-3">
      <h1 className="text-base font-semibold">Configurações</h1>

      {/* O aviso entra acima dos campos, e nao no lugar do corpo como o peer, o
          grupo e os prefixos fazem: la nao ha formulario sem o registro, e aqui
          o tema e a explicacao do namespace valem mesmo com o plano fora do ar.
          Sem ele a tela ficava com os campos vazios e o gravar morto sem dizer
          por que. A mensagem e a mesma das outras telas, para a falha ter uma
          cara so */}
      {falhou && (
        <Falha mensagem="não deu para falar com a API" tentando={tentando} aoTentar={() => void plano.refetch()} />
      )}

      <fieldset className="rounded border p-3">
        <legend className="px-1 text-[11px] uppercase tracking-wide text-muted-foreground">
          AS da rede
        </legend>
        <div className="flex flex-col gap-3">
          <Campo nome="asn_rede" rotulo="AS da rede" erro={erros.asn_rede}>
            <Input
              id="asn_rede"
              className="dado"
              inputMode="numeric"
              value={rede.asn}
              onChange={(e) => setRascunho((atual) => ({ ...atual, asn: e.target.value }))}
            />
          </Campo>

          <Campo
            nome="asn_politica"
            rotulo="Namespace das standard"
            erro={erros.asn_politica}
            ajuda="em branco, o namespace é o próprio AS da rede"
            nota="só é necessário com ASN de 32 bits: a RFC 1997 escreve o valor em 16 bits"
          >
            <Input
              id="asn_politica"
              className="dado"
              inputMode="numeric"
              placeholder={`= ${rede.asn}`}
              value={rede.politica}
              onChange={(e) => setRascunho((atual) => ({ ...atual, politica: e.target.value }))}
            />
          </Campo>

          <p className="text-xs text-muted-foreground">
            Trocar o AS muda o nome de toda community e o nome dos arquivos em out/.
          </p>

          <div>
            {/* Sem o plano na mao o botao nao grava: a janela entre a montagem
                e a leitura e a unica em que a tela existe sem dado, e o salvar
                ali mandaria o AS em branco, com a recusa da API pintando um
                campo que o operador nunca tocou */}
            <Button
              size="sm"
              onClick={() => gravar.mutate()}
              disabled={gravar.isPending || !plano.data}
            >
              gravar AS
            </Button>
          </div>
        </div>
      </fieldset>

      <fieldset className="rounded border p-3">
        <legend className="px-1 text-[11px] uppercase tracking-wide text-muted-foreground">
          Tema
        </legend>
        <div className="flex gap-2">
          {(["claro", "escuro", "sistema"] as const).map((t) => (
            <Button
              key={t}
              size="sm"
              variant={tema === t ? "secondary" : "ghost"}
              className={cn(tema === t && "ring-1")}
              // a cor sozinha nao diz nada a quem usa leitor de tela: o
              // aria-pressed e o que anuncia qual dos tres esta valendo
              aria-pressed={tema === t}
              onClick={() => trocarTema(t)}
            >
              {t}
            </Button>
          ))}
        </div>
      </fieldset>
    </div>
  )
}
