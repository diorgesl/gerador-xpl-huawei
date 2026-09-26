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
  "as-path-list", "ip-prefix-list", "ipv6-prefix-list", "ipv6-family", "ipv6",
  "end-list", "large-community", "if", "elseif", "else", "endif",
  "then", "and", "or", "call", "apply", "approve", "refuse", "finish", "pass",
  "break", "undo", "peer", "bgp", "group", "network", "ip", "route-static",
  "description",
] as const

// A ordem importa dos dois lados, e cada lado tem a sua prova:
// - a community vem antes do prefixo porque "64512:1500" tem "6451" (que e
//   hex) seguido de dois pontos, e o ramo do IPv6 comecaria a casar ali;
// - e a community tem guarda de fronteira no fim porque o contrario tambem
//   acontece: "2804:36b4::", que e um prefixo dos blocos proprios, tem dois
//   grupos numericos no comeco e casaria como a community "2804:36".
// O nome de objeto vem antes do numero pelo mesmo motivo de sempre.
const PADROES: [Classe, string][] = [
  ["community", String.raw`\d{1,10}:\d{1,10}(?::\d{1,10})?(?![0-9A-Za-z:])`],
  ["prefixo", String.raw`\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,3})?`],
  // IPv6 em duas formas: com grupos antes dos dois pontos, e a comprimida que
  // COMECA com "::": a lista de bogons do bloco base tem ::/0, :: 128,
  // ::1 128 e ::ffff:0:0 96, e sem a segunda forma nenhuma delas casa
  ["prefixo", String.raw`(?:[0-9a-fA-F]{1,4}:){1,}(?::[0-9a-fA-F]{0,4})*(?:/\d{1,3})?|::(?:[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{0,4})*)?(?:/\d{1,3})?`],
  // Duas formas de nome de objeto, as duas tiradas da saida do projeto:
  // "ORIGEM-2804-36b4_32" tem hex minusculo no meio do nome, e "NULL0" da rota
  // estatica nao tem separador nenhum. A segunda forma exige tres caracteres
  // para nao pegar sigla de duas letras.
  ["objeto", String.raw`[A-Z][A-Z0-9]*(?:[-_][A-Za-z0-9]+)+|[A-Z][A-Z0-9]{2,}`],
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
