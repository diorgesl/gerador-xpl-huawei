import { toast } from "sonner"
import { afterEach, describe, expect, it, vi } from "vitest"
import { baixar, copiar, copiarComAviso } from "./copiar"

vi.mock("sonner", () => ({ toast: vi.fn() }))

function comClipboard(fn: () => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(fn) },
  })
}

afterEach(() => {
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined })
  vi.restoreAllMocks()
})

describe("a copia do bloco", () => {
  it("usa o navigator.clipboard quando ele existe", async () => {
    const escrever = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: escrever } })
    await expect(copiar("64512:100")).resolves.toBe("copiado")
    expect(escrever).toHaveBeenCalledWith("64512:100")
  })

  it("cai no execCommand quando o clipboard existe e recusa", async () => {
    comClipboard(() => Promise.reject(new Error("sem permissao")))
    const exec = vi.spyOn(document, "execCommand").mockReturnValue(true)
    await expect(copiar("64512:100")).resolves.toBe("copiado")
    expect(exec).toHaveBeenCalledWith("copy")
  })

  it("sem clipboard nenhum, tenta o execCommand", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined })
    vi.spyOn(document, "execCommand").mockReturnValue(true)
    await expect(copiar("64512:100")).resolves.toBe("copiado")
  })

  it("com as duas recusando, deixa o bloco selecionado", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined })
    vi.spyOn(document, "execCommand").mockReturnValue(false)
    const alvo = document.createElement("pre")
    alvo.textContent = "xpl route-filter X"
    document.body.appendChild(alvo)

    await expect(copiar("xpl route-filter X", alvo)).resolves.toBe("selecionado")
    expect(document.getSelection()?.toString()).toBe("xpl route-filter X")
    alvo.remove()
  })

  it("avisa quando so deu para selecionar", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined })
    vi.spyOn(document, "execCommand").mockReturnValue(false)
    await expect(copiarComAviso("x")).resolves.toBe("selecionado")
    expect(toast).toHaveBeenCalledWith("o bloco ficou selecionado: use Ctrl+C para copiar")
  })

  it("seleciona o codigo dentro do painel, e nao o painel inteiro", async () => {
    // as telas passam o painel montado: o Ctrl+C manual nao pode levar junto o
    // rotulo das abas e dos botoes, e a numeracao fica fora do `code`
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined })
    vi.spyOn(document, "execCommand").mockReturnValue(false)
    const painel = document.createElement("div")
    painel.innerHTML =
      "<span>bloco do peer</span><pre><span>1</span><code>xpl route-filter X\nend-filter</code></pre><button>copiar</button>"
    document.body.appendChild(painel)

    await expect(copiar("xpl route-filter X\nend-filter", painel)).resolves.toBe("selecionado")
    expect(document.getSelection()?.toString()).toBe("xpl route-filter X\nend-filter")
    painel.remove()
  })
})

describe("o download do bloco", () => {
  it("cria um link com o nome do arquivo de out/ e clica nele", () => {
    const cliques: HTMLAnchorElement[] = []
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      cliques.push(this)
    })
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() })

    baixar("xpl route-filter X", "CLIENTE-268127.txt")

    expect(cliques).toHaveLength(1)
    expect(cliques[0].download).toBe("CLIENTE-268127.txt")
    expect(cliques[0].href).toContain("blob:x")
    vi.unstubAllGlobals()
  })

  it("salva um Blob como ele veio, sem virar texto no caminho", () => {
    // o PDF do cliente e bytes, e nao uma string: um `new Blob([blob])` sem
    // o tipo perde o application/pdf, e um texto(blob) no meio do caminho
    // corromperia o arquivo antes de o operador salvar
    const criados: Blob[] = []
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn((b: Blob) => {
        criados.push(b)
        return "blob:x"
      }),
      revokeObjectURL: vi.fn(),
    })
    const pdf = new Blob(["%PDF-1.4"], { type: "application/pdf" })

    baixar(pdf, "politica-bgp-64512.pdf")

    expect(criados[0]).toBe(pdf)
    expect(criados[0].type).toBe("application/pdf")
    vi.unstubAllGlobals()
  })
})
