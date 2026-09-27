import { Button } from "@/components/ui/button"

/**
 * Uma consulta que falhou deixa a tela sem dado nenhum. O que o operador
 * digitou nao se perde: o formulario nao e desmontado por causa de um refetch
 * que falhou, so a tela mostra o aviso e o botao.
 *
 * O `tentando` vem do `isFetching` de quem refaz e desabilita o botao enquanto
 * o pedido corre. Quem segura o aviso na tela durante o retry e o `retentando`
 * do chamador: o TanStack zera o `error` de uma consulta sem dado quando ela e
 * refeita, entao sem ele o aviso sairia da tela no clique. Sem o `retentando`,
 * o primeiro clique ja tira o botao da tela; com ele, quem barra o segundo
 * clique e o `disabled`.
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
