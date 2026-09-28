import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Campo } from "@/components/Campo"
import { cliente } from "@/api/cliente"
import { chaves, lerRecusa } from "@/api/consultas"
import { avisarFalhaDeRede, falhaDoServidor } from "@/lib/aviso"

/**
 * O ASN novo, com os mesmos dois campos do formulario das Configuracoes.
 *
 * Os dois nascem juntos de proposito: um ASN de 32 bits sem o namespace
 * escreveria um arquivo que estoura na primeira leitura, e nao haveria como
 * consertar depois, porque o plano do tenant e justamente o que falha.
 *
 * Os nomes dos campos sao os do formulario do servidor, e nao uma escolha
 * desta tela: o POST /api/asns devolve a recusa nas chaves `asn_rede` e
 * `asn_politica`, e um `nome` diferente faria o 422 voltar sem pintar campo
 * nenhum - o operador veria o clique nao fazer nada.
 */
export function DialogoNovoAsn({ aberto, aoFechar, aoCriar }: {
  aberto: boolean
  aoFechar: () => void
  aoCriar: (asn: string) => void
}) {
  const [asn, setAsn] = useState("")
  const [politica, setPolitica] = useState("")
  const [erros, setErros] = useState<Record<string, string>>({})
  const consultas = useQueryClient()

  const criar = useMutation({
    mutationFn: () => cliente.POST("/api/asns", {
      body: { asn, politica },
    }),
    onSuccess: (r) => {
      if (r.error) {
        // o 5xx e falha do servidor, e nao do que foi digitado: o aviso com o
        // caminho de volta entra junto da recusa, se houver uma
        if (falhaDoServidor(r.response.status)) avisarFalhaDeRede(() => criar.mutate())
        setErros(lerRecusa(r.error).erros)
        return
      }
      setErros({})
      setAsn("")
      setPolitica("")
      // a lista e a unica fonte das opcoes do seletor: sem a invalidacao o
      // ASN novo existiria no servidor e nao no menu que o escolhe
      void consultas.invalidateQueries({ queryKey: chaves.asns })
      // O texto sem os espacos das pontas: o servidor apara antes de gravar, e
      // a lista que o seletor compara vem aparada tambem. Com o espaco, o ASN
      // recem-criado nao seria achado na lista e a escolha cairia no primeiro
      // tenant, que e o cadastro errado aberto sem aviso
      aoCriar(asn.trim())
    },
    // a excecao de rede nao passa pelo ramo do `r.error`: o openapi-fetch a
    // re-lanca, e sem este caminho o clique em criar nao deixaria rastro
    onError: () => avisarFalhaDeRede(() => criar.mutate()),
  })

  return (
    // so o fechamento interessa: nao ha gatilho que abra por aqui, e o `true`
    // que chegasse nao pode mexer no que quem chamou controla
    <Dialog open={aberto} onOpenChange={(v) => { if (!v) aoFechar() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Novo ASN</DialogTitle>
          <DialogDescription>
            Cria o arquivo {"peers/<ASN>.yaml"} do tenant e passa a tela para
            essa rede. O cadastro novo nasce sem peer, sem grupo e sem bloco.
          </DialogDescription>
        </DialogHeader>

        <Campo nome="asn_rede" rotulo="AS da rede" erro={erros.asn_rede}>
          <Input
            id="asn_rede"
            className="dado"
            inputMode="numeric"
            value={asn}
            onChange={(e) => setAsn(e.target.value)}
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
            placeholder={asn ? `= ${asn}` : undefined}
            value={politica}
            onChange={(e) => setPolitica(e.target.value)}
          />
        </Campo>

        <DialogFooter>
          <Button variant="ghost" onClick={aoFechar}>cancelar</Button>
          <Button onClick={() => criar.mutate()} disabled={criar.isPending}>criar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
