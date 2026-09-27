import { useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { PainelSaida, type AbaSaida } from "@/components/PainelSaida"
import { cliente } from "@/api/cliente"
import { chaves, lerRecusa } from "@/api/consultas"
import { copiarComAviso } from "@/lib/copiar"
import { usePublicarAcoes } from "@/app/acoes-contexto"

/** O texto dos dois editores, no formato que a API recebe e devolve. */
type Texto = { v4: string; v6: string }

export function PrefixosTela() {
  const consultas = useQueryClient()
  // O rascunho e o que o operador escreveu, e comeca nulo: enquanto ele for
  // nulo o texto dos editores e o do registro, derivado no proprio render. O
  // caminho obvio, um efeito copiando a resposta para o estado, e
  // `set-state-in-effect`, que e erro do lint nesta config, e ainda apagaria o
  // que esta escrito a cada refetch ao voltar o foco. Com o rascunho, o
  // registro manda ate a primeira tecla (ou a consulta ao IRR), e depois o
  // que esta na tela manda
  const [rascunho, setRascunho] = useState<Texto | null>(null)
  const [errosDoSalvar, setErrosDoSalvar] = useState<Record<string, string>>({})
  const blocoRef = useRef<HTMLDivElement>(null)

  const blocos = useQuery({
    queryKey: chaves.blocos,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/blocos")
      if (error) throw new Error("falha ao ler os blocos")
      return data
    },
  })

  const texto: Texto = rascunho ?? { v4: blocos.data?.texto.v4 ?? "", v6: blocos.data?.texto.v6 ?? "" }
  const { v4, v6 } = texto

  const previa = useQuery({
    queryKey: ["previa-blocos", v4, v6],
    // so depois de o registro chegar: antes disso a previa sairia com os dois
    // editores vazios, e o painel abriria com o bloco do texto em branco
    enabled: blocos.data !== undefined,
    queryFn: async () => {
      const { data, error } = await cliente.POST("/api/blocos/previa", { body: { v4, v6 } })
      if (error) throw error
      return data
    },
  })

  const salvar = useMutation({
    mutationFn: () => cliente.PUT("/api/blocos", { body: { v4, v6 } }),
    onSuccess: (r) => {
      if (r.error) {
        setErrosDoSalvar(lerRecusa(r.error).erros)
        return
      }
      setErrosDoSalvar({})
      toast("blocos gravados em out/blocos.txt")
      void consultas.invalidateQueries({ queryKey: chaves.blocos })
    },
  })

  const consultar = useMutation({
    mutationFn: (forcar: boolean) => cliente.POST("/api/blocos/irr", { body: { v4, v6, forcar } }),
    onSuccess: (r) => {
      if (r.error) {
        setErrosDoSalvar(lerRecusa(r.error).erros)
        return
      }
      setErrosDoSalvar({})
      if (r.data) setRascunho({ v4: r.data.v4, v6: r.data.v6 })
      toast("prefixos do IRR no formulário; nada foi gravado")
    },
  })

  // A previa tambem traz erros: com o prefixo torto ela responde 200 com o mapa
  // de erros e o bloco nulo. Sem olhar para eles, a tela nao mostraria a
  // mensagem e o painel cairia no bloco salvo, que nao e a previa do que esta
  // escrito. O erro do salvar tem precedencia porque e o mais recente
  const erros = Object.keys(errosDoSalvar).length > 0 ? errosDoSalvar : previa.data?.erros ?? {}
  const comErro = Object.keys(erros).length > 0

  const abas: AbaSaida[] = [
    {
      id: "originacao", rotulo: "originação",
      conteudo: comErro ? null : previa.data?.bloco ?? blocos.data?.originacao ?? null,
      arquivo: "blocos.txt", salvo: previa.data?.salvo ?? null,
    },
  ]
  if (blocos.data?.remover) {
    abas.push({
      id: "remover", rotulo: "remoção", conteudo: blocos.data.remover,
      arquivo: "blocos.txt", salvo: blocos.data.remover, soLeitura: true,
    })
  }

  // A tela publica o que ela sabe fazer para a paleta: gravar e copiar o bloco
  // aberto. Nao ha duplicar: os prefixos do AS sao um registro so, e nao uma
  // lista de registros como os peers e os grupos
  const blocoAberto = abas[0]?.conteudo ?? null
  usePublicarAcoes({
    aoSalvar: () => salvar.mutate(),
    aoCopiarBloco: blocoAberto ? () => void copiarComAviso(blocoAberto, blocoRef.current) : undefined,
  })

  return (
    <div className="flex min-h-0 flex-col gap-3 p-3">
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

      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => salvar.mutate()} disabled={salvar.isPending}>salvar</Button>
        <Button size="sm" variant="ghost" onClick={() => consultar.mutate(false)} disabled={consultar.isPending}>
          consultar IRR
        </Button>
        <Button size="sm" variant="ghost" onClick={() => consultar.mutate(true)} disabled={consultar.isPending}>
          reconsultar
        </Button>
      </div>

      <div ref={blocoRef} className="min-w-0">
        <PainelSaida
          abas={abas}
          sujo={false}
          carregando={previa.isFetching}
          erro={comErro ? "com erro" : null}
          onCopiar={async (aba) =>
            aba.conteudo ? (await copiarComAviso(aba.conteudo, blocoRef.current)) === "copiado" : false
          }
        />
      </div>
    </div>
  )
}
