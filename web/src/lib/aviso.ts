import { toast } from "sonner"

// A escrita que nao chegou ao servidor, em um lugar so. Duas coisas a tornam
// diferente das recusas de formulario, e nenhuma delas passa pelo `{error}` do
// openapi-fetch: a excecao de rede, que ele RE-LANCA (o `fetch` do navegador
// rejeita, e o cliente deixa a promessa rejeitada subir), e o 5xx, que e falha
// do servidor e nao do que o operador escreveu.
//
// A frase e a mesma das telas de `Falha` de proposito: a falha de escrita tem
// uma cara so, e o operador aprende uma vez o que ela quer dizer. O caminho de
// volta e o mesmo dos dois casos - repetir o pedido -, porque nada do que esta
// na tela se perdeu.

/** A mesma mensagem do componente `Falha` das telas. */
export const FALHA_DE_REDE = "não deu para falar com a API"

/**
 * O aviso de uma escrita que nao chegou, com o "tentar de novo" que repete o
 * pedido. O toast e nao um `Falha` no lugar do corpo porque o formulario fica:
 * o que o operador digitou continua na tela, e o aviso e o que ele ve em cima.
 *
 * As telas que esperam a escrita (o peer e o grupo, que precisam do id gravado)
 * chamam o `escrever` abaixo; as que so disparam a mutacao passam isto ao
 * `onError` dela. Os dois caminhos terminam aqui.
 */
export function avisarFalhaDeRede(tentarDeNovo: () => void) {
  toast.error(FALHA_DE_REDE, { action: { label: "tentar de novo", onClick: tentarDeNovo } })
}

/** Um 5xx e falha do servidor, e nao do formulario: o caminho e tentar de novo. */
export const falhaDoServidor = (status: number) => status >= 500

/**
 * Roda uma escrita e devolve o que ela devolveu, ou nulo quando a promessa foi
 * rejeitada - nesse caso o aviso com "tentar de novo" ja ficou na tela, e quem
 * chamou so precisa parar.
 */
export async function escrever<T>(
  pedido: () => Promise<T>,
  tentarDeNovo: () => void,
): Promise<T | null> {
  try {
    return await pedido()
  } catch {
    avisarFalhaDeRede(tentarDeNovo)
    return null
  }
}
