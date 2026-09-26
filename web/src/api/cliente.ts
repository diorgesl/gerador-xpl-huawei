import createClient from "openapi-fetch"
import type { paths } from "./schema"

// baseUrl vazio de proposito: o caminho do schema ja comeca com /api, e a
// mesma build roda pelo proxy do Vite (5173) e pelo uvicorn (8000). Com host
// no codigo, um dos dois quebra.
export const cliente = createClient<paths>({ baseUrl: "" })
