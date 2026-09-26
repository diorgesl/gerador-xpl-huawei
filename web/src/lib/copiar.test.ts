import { afterEach, describe, expect, it, vi } from "vitest"
import { copiar } from "./copiar"

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
})
