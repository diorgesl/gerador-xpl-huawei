import createClient from "openapi-fetch"
import type { paths } from "./schema"

// baseUrl vazio de proposito: o caminho do schema ja comeca com /api, e a
// mesma build roda pelo proxy do Vite (5173) e pelo uvicorn (8000). Com host
// no codigo, um dos dois quebra.
// O `createClient` guarda o `globalThis.fetch` de quando o modulo carrega, e o
// teste troca o fetch depois disso. Este indireto le o global na hora da
// chamada, que e o que deixa o `mockFetch` do arnes valer para as telas: em
// producao e o mesmo fetch do browser.
export const cliente = createClient<paths>({
  baseUrl: "",
  fetch: (entrada: Request, init?: RequestInit) => (globalThis.fetch as typeof fetch)(entrada, init),
})
