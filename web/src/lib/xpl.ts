// Tokenizador do XPL do plano. Nenhuma biblioteca conhece a linguagem: uma
// gramatica TextMate no Shiki pesaria mais que o lexer inteiro. A regra que
// manda aqui e o round-trip: juntar o texto de todos os tokens tem que
// devolver a linha original, byte a byte.
export type Classe =
  | "comentario"
  | "palavra-chave"
  | "community"
  | "prefixo"
  | "objeto"
  | "numero"
  | "texto"

export type Token = { classe: Classe; texto: string }

export const PALAVRAS_CHAVE = [
  "xpl", "route-filter", "end-filter", "community-list", "large-community-list",
  "as-path-list", "ip-prefix-list", "end-list", "large-community", "if", "elseif", "else", "endif",
  "then", "and", "or", "call", "apply", "approve", "refuse", "finish", "pass",
  "break", "undo", "peer", "bgp", "group", "network", "ip", "route-static",
  "description",
] as const

// A ordem importa: a community tem que ser tentada antes do prefixo, senao o
// "64512:1500" cairia no ramo do IPv6, e o nome de objeto antes do numero.
const PADROES: [Classe, string][] = [
  ["community", String.raw`\d{1,10}:\d{1,10}(?::\d{1,10})?`],
  ["prefixo", String.raw`\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,3})?`],
  ["prefixo", String.raw`(?:[0-9a-fA-F]{1,4}:){1,}(?::[0-9a-fA-F]{0,4})*(?:/\d{1,3})?`],
  ["objeto", String.raw`[A-Z][A-Z0-9]*(?:[-_][A-Z0-9]+)+`],
  ["palavra-chave", `(?<![A-Za-z0-9_-])(?:${[...PALAVRAS_CHAVE].sort((a, b) => b.length - a.length).join("|")})(?![A-Za-z0-9_-])`],
  ["numero", String.raw`\d+`],
]

const RE = new RegExp(
  PADROES.map(([, p]) => `(${p})`).join("|") + String.raw`|([\s\S])`,
  "g",
)

function juntar(cru: Token[]): Token[] {
  const saida: Token[] = []
  for (const t of cru) {
    const ultimo = saida[saida.length - 1]
    if (t.classe === "texto" && ultimo?.classe === "texto") ultimo.texto += t.texto
    else saida.push({ ...t })
  }
  return saida
}

export function tokenizar(linha: string): Token[] {
  const enxuto = linha.trimStart()
  // comentario e a linha inteira: o XPL do plano comenta com # no topo e com
  // !- nas linhas de undo, e nada disso tem outra classe dentro
  if (enxuto.startsWith("#") || enxuto.startsWith("!-")) {
    return [{ classe: "comentario", texto: linha }]
  }
  const cru: Token[] = []
  for (const m of linha.matchAll(RE)) {
    const i = m.slice(1).findIndex((v) => v !== undefined)
    cru.push({ classe: PADROES[i]?.[0] ?? "texto", texto: m[0] })
  }
  return juntar(cru)
}
