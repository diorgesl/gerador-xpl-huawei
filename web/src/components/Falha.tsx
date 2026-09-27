import { Button } from "@/components/ui/button"

/**
 * Uma consulta que falhou deixa a tela sem dado nenhum. O que o operador
 * digitou nao se perde: o formulario nao e desmontado por causa de um refetch
 * que falhou, so a tela mostra o aviso e o botao.
 */
export function Falha({ mensagem, aoTentar }: { mensagem: string; aoTentar: () => void }) {
  return (
    <div role="alert" className="m-3 rounded border border-erro-texto/30 bg-erro-fundo p-3 text-erro-texto">
      <p className="text-sm">{mensagem}</p>
      <Button size="sm" variant="ghost" className="mt-2" onClick={aoTentar}>
        tentar de novo
      </Button>
    </div>
  )
}
