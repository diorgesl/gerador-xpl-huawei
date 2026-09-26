import { readFileSync } from "node:fs"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"
import { contraste, lerTokens, type Oklch } from "./contraste"

// `new URL("./tokens.css", import.meta.url)` nao serve: o Vite reescreve o asset
// para uma URL http do jsdom (http://localhost:3000/src/estilo/tokens.css) e o
// fileURLToPath recusa. O import.meta.url cru aqui ja e um file:// do arquivo.
const CAMINHO = resolve(dirname(fileURLToPath(import.meta.url)), "tokens.css")
const TOKENS = lerTokens(readFileSync(CAMINHO, "utf8"))

// nome do fundo, nome do texto, minimo. Texto corrido exige 4,5:1; borda de
// campo e anel de foco exigem 3:1, que e o que a WCAG 1.4.11 pede de limite
// de componente.
const PARES: [string, string, number][] = [
  ["background", "foreground", 4.5],
  ["card", "foreground", 4.5],
  ["muted", "foreground", 4.5],
  ["background", "muted-foreground", 4.5],
  ["card", "muted-foreground", 4.5],
  ["muted", "muted-foreground", 4.5],
  ["primary", "primary-foreground", 4.5],
  ["card", "erro-texto", 4.5],
  ["card", "aviso-texto", 4.5],
  ["card", "sucesso-texto", 4.5],
  ["erro-fundo", "erro-texto", 4.5],
  ["aviso-fundo", "aviso-texto", 4.5],
  ["sucesso-fundo", "sucesso-texto", 4.5],
  ["card", "xpl-palavra", 4.5],
  ["card", "xpl-community", 4.5],
  ["card", "xpl-prefixo", 4.5],
  ["card", "xpl-objeto", 4.5],
  ["card", "xpl-numero", 4.5],
  ["card", "xpl-comentario", 4.5],
  ["background", "input", 3.0],
  ["card", "input", 3.0],
  ["muted", "input", 3.0],
  ["background", "ring", 3.0],
  ["card", "ring", 3.0],
  ["background", "border", 1.0],
]

const TIPOS = ["cliente", "parceiro", "upstream", "ix", "pni"]

describe("a matematica do contraste", () => {
  it("da 21:1 entre branco e preto", () => {
    const branco: Oklch = [1, 0, 0]
    const preto: Oklch = [0, 0, 0]
    expect(contraste(branco, preto)).toBeCloseTo(21, 1)
  })
})

describe.each(["claro", "escuro"])("o tema %s", (tema) => {
  const temaTokens = (nome: string) => {
    const t = TOKENS[tema === "claro" ? ":root" : ".dark"]?.[nome]
    if (!t) throw new Error(`token ${nome} falta no tema ${tema}`)
    return t
  }

  it.each(PARES)("%s com %s fica em pelo menos %s:1", (fundo, texto, minimo) => {
    const r = contraste(temaTokens(texto), temaTokens(fundo))
    expect(r, `${tema}: ${texto} sobre ${fundo} deu ${r.toFixed(2)}:1`).toBeGreaterThanOrEqual(minimo)
  })

  it.each(TIPOS)("o badge de %s passa", (tipo) => {
    const r = contraste(temaTokens(`badge-${tipo}-texto`), temaTokens(`badge-${tipo}-fundo`))
    expect(r, `${tema}: badge ${tipo} deu ${r.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5)
  })
})
