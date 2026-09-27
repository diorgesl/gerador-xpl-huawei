import { Button } from "@/components/ui/button"

/**
 * Uma consulta que falhou deixa a tela sem dado nenhum. O que o operador
 * digitou nao se perde: o formulario nao e desmontado por causa de um refetch
 * que falhou, so a tela mostra o aviso e o botao.
 *
 * O `tentando` vem do `isFetching` de quem refaz: sem ele o botao segue
 * clicavel durante o pedido, e o refetch do TanStack reinicia o que esta em
 * voo, entao o clique duplo vira dois pedidos.
 */
export function Falha({ mensagem, tentando = false, aoTentar }: {
  mensagem: string
  tentando?: boolean
  aoTentar: () => void
}) {
  return (
    <div role="alert" className="m-3 rounded border border-erro-texto/30 bg-erro-fundo p-3 text-erro-texto">
      <p className="text-sm">{mensagem}</p>
      <Button size="sm" variant="ghost" className="mt-2" disabled={tentando} onClick={aoTentar}>
        tentar de novo
      </Button>
    </div>
  )
}
