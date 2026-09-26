// Contraste WCAG de cores escritas em oklch, sem dependencia: e o mesmo
// calculo que o navegador faz para pintar o token. So o teste usa.
export type Oklch = [number, number, number]

const RE = /^oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)$/

export function lerOklch(valor: string): Oklch | null {
  const m = RE.exec(valor.trim())
  if (!m) return null
  return [Number(m[1]), Number(m[2]), Number(m[3])]
}

/** Os tokens de um bloco, por seletor. Blocos aninhados nao existem aqui. */
export function lerTokens(css: string): Record<string, Record<string, Oklch>> {
  const blocos: Record<string, Record<string, Oklch>> = {}
  const semComentario = css
    .replace(/\/\*[\s\S]*?\*\//g, "")
    // os at-rules de statement (`@import`, `@custom-variant`) ficam no preludio
    // do primeiro bloco: sem tirar, eles entram no nome do seletor e o `:root`
    // deixa de existir no mapa
    .replace(/@[^{};]*;/g, "")
  for (const [, seletor, corpo] of semComentario.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const nome = seletor.trim()
    const tokens: Record<string, Oklch> = {}
    for (const [, chave, valor] of corpo.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
      const cor = lerOklch(valor)
      if (cor) tokens[chave.slice(2)] = cor
    }
    if (Object.keys(tokens).length) blocos[nome] = tokens
  }
  return blocos
}

function paraLinear(u: number): number {
  return u <= 0.04045 ? u / 12.92 : ((u + 0.055) / 1.055) ** 2.4
}

/** oklch para sRGB, com o ajuste do gamut por corte, como o CSS faz. */
function paraSrgb([L, C, H]: Oklch): [number, number, number] {
  const h = (H * Math.PI) / 180
  const a = C * Math.cos(h)
  const b = C * Math.sin(h)
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3
  const cru: [number, number, number] = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ]
  return cru.map((u) => {
    const v = Math.min(1, Math.max(0, u))
    return v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055
  }) as [number, number, number]
}

function luminancia(cor: Oklch): number {
  const [r, g, b] = paraSrgb(cor).map(paraLinear)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contraste(um: Oklch, outro: Oklch): number {
  const a = luminancia(um)
  const b = luminancia(outro)
  const [alto, baixo] = a > b ? [a, b] : [b, a]
  return (alto + 0.05) / (baixo + 0.05)
}
