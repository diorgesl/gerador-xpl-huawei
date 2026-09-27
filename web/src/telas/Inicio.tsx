/**
 * A tela de chegada de /peers e /grupos.
 *
 * A casca ja lista os registros na barra a esquerda, com busca e badge de tipo,
 * entao o corpo nao repete a lista. Ele tambem nao oferece botao de criar: o
 * "+ novo" da barra ja e esse caminho, e um segundo botao com o mesmo rotulo
 * deixaria ambigua a busca do e2e por "novo", que enxerga a tela inteira.
 */
export function Inicio({ oQue }: { oQue: "peer" | "grupo" }) {
  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold">escolha um {oQue} ou crie um</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        a lista está na barra à esquerda: clique num registro para abrir, ou use
        o "+ novo" para criar.
      </p>
    </div>
  )
}
