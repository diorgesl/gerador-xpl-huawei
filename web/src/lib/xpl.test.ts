import { readdirSync, readFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"
import { PALAVRAS_CHAVE, tokenizar } from "./xpl"

// `new URL(p, import.meta.url)` nao serve: o Vite reescreve o caminho para uma
// URL http do jsdom e o fileURLToPath recusa. E o mesmo encanamento do
// contraste.test.ts, que ja tropecou nisso.
//
// Sem a barra no fim e com `join` em cada arquivo: o `resolve` normaliza
// `../../../tests/golden/` para `.../tests/golden`, e concatenar o nome direto
// daria `.../tests/goldenbase.txt`.
const raiz = (p: string) => resolve(dirname(fileURLToPath(import.meta.url)), p)
const GOLDEN = raiz("../../../tests/golden")
const TEMPLATES = raiz("../../../templates")

const arquivos = (dir: string, fim: string) =>
  readdirSync(dir).filter((n) => n.endsWith(fim))

describe("o round-trip sobre os golden", () => {
  it.each(arquivos(GOLDEN, ".txt"))("%s volta byte a byte", (nome) => {
    const original = readFileSync(join(GOLDEN, nome), "utf8")
    for (const linha of original.split("\n")) {
      const texto = tokenizar(linha).map((t) => t.texto).join("")
      expect(texto, `linha: ${JSON.stringify(linha)}`).toBe(linha)
    }
  })
})

describe("o contrato de cada classe", () => {
  // O filtro tira todo token de classe "texto": o que este teste afirma e a
  // lista de tokens CLASSIFICADOS de uma linha. Que nada se perca no caminho e
  // o round-trip acima que garante.
  const caso = (linha: string, esperado: [string, string][]) => {
    const t = tokenizar(linha).filter((x) => x.classe !== "texto")
    expect(t.map((x) => [x.classe, x.texto])).toEqual(esperado)
  }

  it("le a community de dois e de tres campos", () => {
    caso("apply community {64512:9666, 64512:200} additive", [
      ["palavra-chave", "apply"],
      ["community", "64512:9666"],
      ["community", "64512:200"],
    ])
    caso("apply large-community {64512:1000:268127} additive", [
      ["palavra-chave", "apply"],
      ["palavra-chave", "large-community"],
      ["community", "64512:1000:268127"],
    ])
  })

  it("le prefixo com mascara, IP puro e prefixo sem barra", () => {
    // `next-hop` nao esta na lista de palavras-chave, entao sai como texto e
    // nao aparece aqui
    caso("apply ip next-hop 192.0.2.1", [
      ["palavra-chave", "apply"],
      ["palavra-chave", "ip"],
      ["prefixo", "192.0.2.1"],
    ])
    // `le` tambem e texto; o prefixo sem barra e o numero ficam
    caso(" 45.169.232.0 22 le 24", [["prefixo", "45.169.232.0"], ["numero", "22"], ["numero", "24"]])
    caso("2001:db8::/32", [["prefixo", "2001:db8::/32"]])
  })

  it("le o IPv6 comprimido que comeca com dois pontos", () => {
    // as quatro primeiras linhas da lista de bogons do bloco base
    caso(" :: 0 le 0,", [["prefixo", "::"], ["numero", "0"], ["numero", "0"]])
    caso(" :: 128,", [["prefixo", "::"], ["numero", "128"]])
    caso(" ::1 128,", [["prefixo", "::1"], ["numero", "128"]])
    caso(" ::ffff:0:0 96 le 128,", [["prefixo", "::ffff:0:0"], ["numero", "96"], ["numero", "128"]])
  })

  it("nao le o comeco de um IPv6 como community", () => {
    // "2804:36b4::" tem dois grupos numericos no comeco, e sem a guarda de
    // fronteira o ramo da community o partia em "2804:36" mais o resto
    caso(" network 2804:36b4:: 32", [
      ["palavra-chave", "network"],
      ["prefixo", "2804:36b4::"],
      ["numero", "32"],
    ])
    // e a community de verdade continua saindo inteira
    caso("{2804:36} additive", [["community", "2804:36"]])
  })

  it("le os nomes de objeto que o proprio gerador escreve", () => {
    caso("xpl route-filter ORIGEM-2804-36b4_32", [
      ["palavra-chave", "xpl"],
      ["palavra-chave", "route-filter"],
      ["objeto", "ORIGEM-2804-36b4_32"],
    ])
    // `preference` e texto e nao aparece; o NULL0 e o nome da interface de
    // descarte, sem separador nenhum
    caso("ip route-static 2804:36b4:: 32 NULL0 preference 250", [
      ["palavra-chave", "ip"],
      ["palavra-chave", "route-static"],
      ["prefixo", "2804:36b4::"],
      ["numero", "32"],
      ["objeto", "NULL0"],
      ["numero", "250"],
    ])
  })

  it("le o nome de objeto e o numero solto", () => {
    caso(" call route-filter IMPORT-SANITY-V4", [
      ["palavra-chave", "call"],
      ["palavra-chave", "route-filter"],
      ["objeto", "IMPORT-SANITY-V4"],
    ])
    // a ordem e a da linha: o numero vem antes do `then`
    caso(" if tag eq 666 then", [["palavra-chave", "if"], ["numero", "666"], ["palavra-chave", "then"]])
  })

  it("nao casa palavra-chave no meio de outra palavra", () => {
    // a guarda de fronteira do regex: `description` e uma palavra-chave da
    // lista, e nao pode casar dentro de `descriptions` (`ip` tambem esta na
    // lista e aparece no meio dela)
    expect(tokenizar("descriptions").map((x) => x.classe)).toEqual(["texto"])
    // e casam quando a palavra e inteira
    expect(tokenizar("ip").map((x) => x.classe)).toEqual(["palavra-chave"])
    // o nome de objeto inteiro tambem e um token so, sem palavra-chave no meio.
    // O filtro e o mesmo do `caso`: sem ele o branco entre as palavras entra na
    // lista de classes, e a linha tem sete tokens, nao quatro
    expect(
      tokenizar("peer 198.51.100.2 description CLIENTE-AS268127")
        .filter((x) => x.classe !== "texto")
        .map((x) => x.classe),
    ).toEqual(["palavra-chave", "prefixo", "palavra-chave", "objeto"])
  })

  it("a linha de comentario e um token so, inteira", () => {
    for (const linha of ["# gerado por bgpgen - nao editar a mao", "  !- undo xpl community-list CL-PEER-1"]) {
      const t = tokenizar(linha)
      expect(t).toEqual([{ classe: "comentario", texto: linha }])
    }
  })

  it("toda linha de comentario do golden e so comentario", () => {
    for (const nome of arquivos(GOLDEN, ".txt")) {
      const original = readFileSync(join(GOLDEN, nome), "utf8")
      for (const linha of original.split("\n")) {
        const enxuto = linha.trimStart()
        if (!enxuto.startsWith("#") && !enxuto.startsWith("!-")) continue
        const fora = tokenizar(linha).filter((t) => t.classe !== "comentario")
        expect(fora, `${nome}: ${linha}`).toEqual([])
      }
    }
  })
})

describe("a lista de palavras-chave", () => {
  const templates = arquivos(TEMPLATES, ".j2")
    .map((n) => readFileSync(join(TEMPLATES, n), "utf8"))
    .join("\n")

  it.each(PALAVRAS_CHAVE)("%s aparece em algum template .j2 do projeto", (palavra) => {
    // a lista sai dos templates: palavra que nenhum deles escreve e palavra
    // inventada, e o tokenizador estaria pintando o que nao existe
    expect(templates).toContain(palavra)
  })
})
