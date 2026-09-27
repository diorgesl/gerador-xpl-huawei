import { afterEach, describe, expect, it, vi } from "vitest"
import { aplicarTema, gravarTema, lerTema } from "./tema"

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
  document.documentElement.classList.remove("dark")
})

describe("a escolha de tema guardada", () => {
  it("sem escolha nenhuma, vale o sistema", () => {
    expect(lerTema()).toBe("sistema")
  })

  it("le o que foi gravado", () => {
    gravarTema("escuro")
    expect(lerTema()).toBe("escuro")
    gravarTema("claro")
    expect(lerTema()).toBe("claro")
  })

  it("voltar para o sistema apaga a escolha", () => {
    gravarTema("escuro")
    gravarTema("sistema")
    expect(localStorage.getItem("tema")).toBeNull()
    expect(lerTema()).toBe("sistema")
  })
})

describe("storage bloqueado", () => {
  it("ler com o storage lancando cai no sistema", () => {
    // janela privada e storage bloqueado por politica lancam aqui
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage bloqueado")
    })
    expect(lerTema()).toBe("sistema")
  })

  it("gravar com o storage lancando nao estoura", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("storage bloqueado")
    })
    expect(() => gravarTema("escuro")).not.toThrow()
  })
})

describe("a aplicacao do tema", () => {
  it("o escuro poe a classe no html", () => {
    aplicarTema("escuro")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    aplicarTema("claro")
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })

  it("o sistema segue o matchMedia", () => {
    vi.spyOn(window, "matchMedia").mockReturnValue({ matches: true } as MediaQueryList)
    aplicarTema("sistema")
    expect(document.documentElement.classList.contains("dark")).toBe(true)
  })
})
