import createClient from "openapi-fetch"
import type { paths } from "./schema"

/** O que fazer quando o servidor recusa a sessao. */
let aoPerderSessao: (() => void) | null = null

/**
 * Registra quem trata a sessao perdida. Quem chama e o main.tsx, e o
 * callback leva para a tela de login.
 *
 * O aviso e um callback, e nao um `navigate` daqui, porque este modulo
 * nao esta dentro do router: quem sabe navegar e quem monta a arvore.
 */
export function quandoPerderSessao(fn: () => void) {
  aoPerderSessao = fn
}

/** Chama o aviso registrado, se houver. */
export function avisarPerdaDeSessao() {
  aoPerderSessao?.()
}

/**
 * A leitura de uma resposta que saiu por fetch cru, fora deste cliente.
 *
 * O /base.txt e texto puro e nao esta no schema, entao as duas telas que o
 * buscam (a Casca, no "baixar o bloco base" da paleta, e a tela do bloco
 * base) leem a resposta na mao. Sem esta conferencia, o 401 de uma sessao
 * vencida nao teria o mesmo destino das consultas: viraria uma falha de
 * servidor com um tentar de novo que nunca passa.
 *
 * Devolve true quando a sessao caiu, e quem chamou para por ali.
 */
export function sessaoVencida(resposta: Response): boolean {
  if (resposta.status !== 401) return false
  avisarPerdaDeSessao()
  return true
}

// baseUrl vazio de proposito: o caminho do schema ja comeca com /api, e a
// mesma build roda pelo proxy do Vite (5173) e pelo uvicorn (8000). Com host
// no codigo, um dos dois quebra.
// O `createClient` guarda o `globalThis.fetch` de quando o modulo carrega, e o
// teste troca o fetch depois disso. Este indireto le o global na hora da
// chamada, que e o que deixa o `mockFetch` do arnes valer para as telas: em
// producao e o mesmo fetch do browser.
// O `credentials` e o padrao do fetch para o mesmo host, e esta escrito aqui
// para que a intencao nao dependa da lembranca de ninguem.
export const cliente = createClient<paths>({
  baseUrl: "",
  credentials: "same-origin",
  fetch: (entrada: Request, init?: RequestInit) => (globalThis.fetch as typeof fetch)(entrada, init),
})

// O 401 do /api/login fica de fora: ali ele quer dizer "senha errada", e
// nao "sessao caiu". Quem trata e a tela de login, que mostra a mensagem e
// mantem o que foi digitado.
cliente.use({
  onResponse({ request, response }) {
    if (response.status !== 401) return
    const caminho = new URL(request.url, "http://localhost").pathname
    if (caminho === "/api/login") return
    avisarPerdaDeSessao()
  },
})
