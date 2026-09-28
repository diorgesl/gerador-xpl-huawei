import { useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { AvisoNaoSalvo } from "@/components/AvisoNaoSalvo"
import { Falha } from "@/components/Falha"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { PainelSaida, type AbaSaida } from "@/components/PainelSaida"
import { cliente } from "@/api/cliente"
import { chaves, lerRecusa, recusaComMarca, temRecusa, useBlocos } from "@/api/consultas"
import { avisarFalhaDeRede, falhaDoServidor } from "@/lib/aviso"
import { copiarComAviso } from "@/lib/copiar"
import { usePublicarAcoes } from "@/app/acoes-contexto"
import { useAsn } from "@/app/tenant"

/** O texto dos dois editores, no formato que a API recebe e devolve. */
type Texto = { v4: string; v6: string }

/** O arquivo da originacao, o mesmo que o salvar escreve em out/. */
const ARQUIVO = "blocos.txt"

/** O nome proprio do bloco de remocao: o de origem ja e o `blocos.txt`. */
const ARQUIVO_REMOVER = "remover-blocos.txt"

/** Os erros que cabem nas duas caixas. O resto e recado, e nao erro de campo. */
const CAMPOS = ["blocos_v4", "blocos_v6"] as const

export function PrefixosTela() {
  const consultas = useQueryClient()
  // as tres chamadas diretas desta tela sao rotas de dados como as dos hooks:
  // vao com o tenant da aba
  const asn = useAsn()
  // O rascunho e o que o operador escreveu, e comeca nulo: enquanto ele for
  // nulo o texto dos editores e o do registro, derivado no proprio render. O
  // caminho obvio, um efeito copiando a resposta para o estado, e
  // `set-state-in-effect`, que e erro do lint nesta config, e ainda apagaria o
  // que esta escrito a cada refetch ao voltar o foco. Com o rascunho, o
  // registro manda ate a primeira tecla (ou a consulta ao IRR), e depois o
  // que esta na tela manda
  const [rascunho, setRascunho] = useState<Texto | null>(null)
  // O que uma recusa escreveu na tela (a do salvar ou a da consulta ao IRR) e
  // ate quando ela vale. As duas dividem o mesmo estado porque uma previa nova
  // derruba as duas de uma vez, e porque o recado do IRR sai do mesmo mapa de
  // erros que a recusa do salvar. O `irr` e o que nao pertence a nenhum campo
  const [recusa, setRecusa] = useState<{ em: number; erros: Record<string, string>; irr: string | null } | null>(null)
  const blocoRef = useRef<HTMLDivElement>(null)

  const blocos = useBlocos()

  const texto: Texto = rascunho ?? { v4: blocos.data?.texto.v4 ?? "", v6: blocos.data?.texto.v6 ?? "" }
  const { v4, v6 } = texto

  // O sujo e o rascunho contra o que o servidor tem, e nao um `false` fixo: e
  // ele que faz o cabecalho contar as linhas em vez de culpar o arquivo em
  // out/, e e ele que arma o aviso de saida. Antes de o registro chegar nao ha
  // com o que comparar, e ai qualquer rascunho e texto que so existe na tela
  const sujo = rascunho !== null && (
    blocos.data === undefined || rascunho.v4 !== blocos.data.texto.v4 || rascunho.v6 !== blocos.data.texto.v6
  )

  const previa = useQuery({
    // o ASN entra na chave como nas dos hooks: o bloco previsto e da rede
    // escolhida, e nao so do texto que esta nas caixas
    queryKey: ["previa-blocos", v4, v6, asn],
    // so depois de o registro chegar: antes disso a previa sairia com os dois
    // editores vazios, e o painel abriria com o bloco do texto em branco
    enabled: blocos.data !== undefined,
    queryFn: async () => {
      const { data, error } = await cliente.POST("/api/blocos/previa", {
        params: { query: { asn: Number(asn) } }, body: { v4, v6 },
      })
      if (error) throw error
      return data
    },
  })

  const salvar = useMutation({
    mutationFn: () => cliente.PUT("/api/blocos", {
      params: { query: { asn: Number(asn) } }, body: { v4, v6 },
    }),
    onSuccess: (r) => {
      if (r.error) {
        // o 5xx e falha do servidor, e nao do texto: o aviso com o caminho de
        // volta entra junto, e o "tentar de novo" repete o mesmo PUT
        if (falhaDoServidor(r.response.status)) {
          avisarFalhaDeRede(() => salvar.mutate())
          // Sem corpo de recusa nao ha o que mostrar no painel, e o `_corpo`
          // do lerRecusa ("resposta inesperada da API") seria ruido em cima do
          // aviso: e o mesmo caminho do peer e do grupo
          if (!temRecusa(r.error)) return
        }
        // Sem o refetch da previa daqui: ele subiria o `dataUpdatedAt` dela e a
        // marca da recusa chegaria vencida, apagando no mesmo instante a lista
        // que ela acabou de escrever. Os erros do salvar ficam ate a proxima
        // previa responder, que e quando a lista de la substitui a de ca
        setRecusa(recusaComMarca(r.error))
        return
      }
      setRecusa(null)
      toast("blocos gravados em out/blocos.txt")
      void consultas.invalidateQueries({ queryKey: chaves.blocos })
      // A previa tem chave propria, com o texto: invalidar o registro nao a
      // toca, e o `salvo` dela continuaria sendo o arquivo de ANTES do salvar.
      // Sem esta linha o cabecalho diz que o out/ esta atrasado no segundo
      // seguinte ao toast que disse que ele acabou de ser escrito
      void consultas.invalidateQueries({ queryKey: ["previa-blocos"] })
    },
    onError: () => avisarFalhaDeRede(() => salvar.mutate()),
  })

  const consultar = useMutation({
    mutationFn: (forcar: boolean) => cliente.POST("/api/blocos/irr", {
      params: { query: { asn: Number(asn) } }, body: { v4, v6, forcar },
    }),
    onSuccess: (r, forcar) => {
      if (r.error) {
        const lida = lerRecusa(r.error)
        // o 502 do bgpq4 e falha do servidor: o aviso com o caminho de volta
        // entra junto do recado, que sai ao lado dos botoes
        if (falhaDoServidor(r.response.status)) avisarFalhaDeRede(() => consultar.mutate(forcar))
        // a mensagem do bgpq4 nao e de um campo: ela sai ao lado dos botoes, e
        // nao no editor nem no painel
        //
        // O `_corpo` do lerRecusa fica fora desta corrente: ele e o texto de
        // quando o corpo nao tem forma de recusa, e nao diz nada sobre a
        // consulta. O recado proprio e a mensagem que sobra
        setRecusa(recusaComMarca(r.error, lida.erros.bgpq4 ?? lida.erros._ ?? "a consulta ao IRR falhou"))
        return
      }
      // so o recado do IRR sai: os erros que o salvar deixou na tela ficam com
      // a validade que ja tinham
      setRecusa((atual) => (atual ? { ...atual, irr: null } : null))
      if (r.data) setRascunho({ v4: r.data.v4, v6: r.data.v6 })
      toast("prefixos do IRR no formulário; nada foi gravado")
    },
    // a excecao de rede nao passa pelo ramo do `r.error`, e a consulta ao bgpq4
    // e a operacao mais lenta da tela: sem o aviso, o clique que nem saiu era
    // indistinguivel da consulta em andamento
    onError: (_erro, forcar) => avisarFalhaDeRede(() => consultar.mutate(forcar)),
  })

  // A recusa vale ate a proxima previa responder, que traz a lista de erros
  // dela. A validade sai no render, e nao de um efeito que zera o estado: o
  // `set-state-in-effect` do lint e erro nesta config, a mesma razao que levou
  // o rascunho para o render. O `em` e lido no proprio evento, e nao do
  // fechamento do handler: a previa refaz o pedido quando a janela volta ao
  // foco, e a marca do fechamento chegaria velha depois disso
  const recusaVale = recusa !== null && previa.dataUpdatedAt <= recusa.em ? recusa : null
  // A previa tambem traz erros: com o prefixo torto ela responde 200 com o mapa
  // de erros e o bloco nulo. Sem olhar para eles, a tela nao mostraria a
  // mensagem e o painel cairia no bloco salvo, que nao e a previa do que esta
  // escrito. Os do salvar vem antes porque sao os mais recentes
  const erros = recusaVale && Object.keys(recusaVale.erros).length > 0 ? recusaVale.erros : previa.data?.erros ?? {}
  // So os dois campos contam como erro do bloco: o bgpq4 fora do ar e o corpo
  // fora do modelo nao dizem nada sobre o que esta escrito nas caixas, e contar
  // o mapa inteiro apagaria o painel por causa de uma consulta que falhou
  const comErro = CAMPOS.some((campo) => Boolean(erros[campo]))
  const foraDosCampos = Object.entries(erros)
    .filter(([campo]) => !(CAMPOS as readonly string[]).includes(campo))
    .map(([, mensagem]) => mensagem)
  const erroIrr = recusaVale?.irr ?? (foraDosCampos.length > 0 ? foraDosCampos.join("; ") : null)

  const abas: AbaSaida[] = [
    {
      id: "originacao", rotulo: "originação",
      // a previa que nao veio nao e o bloco salvo: sem o `isError` daqui o
      // painel mostraria o texto de antes como se fosse a previa de agora, com
      // o botao de copiar vivo, e o operador levaria para o equipamento um
      // bloco que nao e o do que esta escrito
      conteudo: comErro || previa.isError ? null : previa.data?.bloco ?? blocos.data?.originacao ?? null,
      arquivo: ARQUIVO, salvo: previa.data?.salvo ?? null,
    },
  ]
  if (blocos.data?.remover) {
    abas.push({
      id: "remover", rotulo: "remoção", conteudo: blocos.data.remover,
      // o nome proprio da remocao: com o `blocos.txt` das duas, o arquivo de
      // undo cairia em cima do de origem na pasta de downloads
      arquivo: ARQUIVO_REMOVER, salvo: blocos.data.remover, soLeitura: true,
    })
  }

  // A tela publica o que ela sabe fazer para a paleta: gravar e copiar o bloco
  // aberto. Nao ha duplicar: os prefixos do AS sao um registro so, e nao uma
  // lista de registros como os peers e os grupos
  //
  // O bloco aberto e o da aba que o painel avisa pelo `aoTrocarAba`: com a aba
  // de remocao aberta, a copia da paleta tem que ser a dela, e nao a da
  // originacao, que e a primeira
  //
  // O `?? abas[0]` e o fallback do proprio painel para quando a aba corrente
  // sai da lista (a de remocao sai se o registro deixar de ter o bloco de
  // undo), e e ele que impede a paleta de oferecer a copia de um bloco que nao
  // e o da tela
  const [abaAtiva, setAbaAtiva] = useState(abas[0]?.id ?? "")
  const blocoAberto = (abas.find((a) => a.id === abaAtiva) ?? abas[0])?.conteudo ?? null
  // O salvamento exige o texto conhecido: enquanto o GET /api/blocos nao
  // responde, os dois editores estao vazios e o backend ACEITA esse vazio
  // (`validar_blocos` nao tem o que apontar), gravando um out/blocos.txt sem
  // nenhuma originacao. Nas telas do peer e do grupo o vazio e recusado pela
  // API, entao la a guarda e so a do Ctrl+S
  usePublicarAcoes({
    aoSalvar: blocos.data ? () => salvar.mutate() : undefined,
    aoCopiarBloco: blocoAberto ? () => void copiarComAviso(blocoAberto, blocoRef.current) : undefined,
  })

  // Uma falha de rede nao pode passar: sem o registro a tela fica com os dois
  // editores vazios, o painel dizendo que esta gerando uma previa que nao vem,
  // e os botoes do IRR levariam a um rascunho que o salvar nao aceita
  //
  // O aviso sobrevive ao tentar de novo, e nao so ao erro: o TanStack zera o
  // `error` de uma consulta sem dado quando ela e refeita (o estado volta a
  // `pending`), entao sem o `retentando` o clique cairia no formulario dos dois
  // editores vazios - como se o registro tivesse sumido - ate a resposta
  // chegar, e o botao que desabilita so existiria depois disso. O
  // `errorUpdateCount` e o que resta da falha depois do refetch, e o
  // `data === undefined` deixa de fora o refetch de fundo de quem ja tem dado
  const tentando = blocos.isFetching
  const retentando = tentando && blocos.data === undefined && blocos.errorUpdateCount > 0
  if (blocos.isError || retentando) {
    return (
      <Falha
        mensagem="não deu para falar com a API"
        tentando={tentando}
        aoTentar={() => void blocos.refetch()}
      />
    )
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 p-3">
      <AvisoNaoSalvo sujo={sujo} />

      <h1 className="text-base font-semibold">Prefixos próprios do AS</h1>

      <p className="max-w-3xl text-xs text-muted-foreground">
        Uma linha por prefixo, no formato <code className="dado">cidr community community</code>, com um
        espaço entre cada um. A linha começada por <code className="dado">!-</code> é prefixo fora de
        serviço: ele não entra na configuração, mas continua no bloco de remoção. O{" "}
        <code className="dado">!-</code> no fim da linha marca o prefixo que sumiu da consulta ao IRR.
      </p>

      <div className="grid gap-3 lg:grid-cols-2">
        {(["v4", "v6"] as const).map((familia) => (
          <div key={familia} className="flex flex-col gap-1" data-campo={`blocos_${familia}`}>
            <Label htmlFor={`blocos_${familia}`}>{familia === "v4" ? "IPv4" : "IPv6"}</Label>
            <Textarea
              id={`blocos_${familia}`}
              rows={8}
              spellCheck={false}
              className="dado"
              value={texto[familia]}
              onChange={(e) => setRascunho({ ...texto, [familia]: e.target.value })}
            />
            {erros[`blocos_${familia}`] && (
              <p role="alert" className="text-xs text-erro-texto">{erros[`blocos_${familia}`]}</p>
            )}
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={() => salvar.mutate()} disabled={salvar.isPending || !blocos.data}>salvar</Button>
        {/* Sem o registro na mao a consulta enche as caixas com um texto que o
            salvar nao aceita, porque e ele que a guarda do salvar espera */}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => consultar.mutate(false)}
          disabled={consultar.isPending || !blocos.data}
        >
          consultar IRR
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => consultar.mutate(true)}
          disabled={consultar.isPending || !blocos.data}
        >
          reconsultar
        </Button>
        {consultar.isPending && (
          <span className="text-xs text-muted-foreground">consultando o IRR...</span>
        )}
        {erroIrr && <p role="alert" className="text-xs text-erro-texto">{erroIrr}</p>}
      </div>

      <div ref={blocoRef} className="min-w-0">
        <PainelSaida
          abas={abas}
          aoTrocarAba={setAbaAtiva}
          sujo={sujo}
          carregando={previa.isFetching}
          erro={comErro ? "com erro" : previa.isError ? "não deu para gerar a prévia" : null}
          onCopiar={async (aba) =>
            aba.conteudo ? (await copiarComAviso(aba.conteudo, blocoRef.current)) === "copiado" : false
          }
        />
      </div>
    </div>
  )
}
