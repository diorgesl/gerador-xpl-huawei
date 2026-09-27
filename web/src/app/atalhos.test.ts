import { renderHook } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { useAtalhos } from "./atalhos"

const teclar = (tecla: string, extras: KeyboardEventInit = {}) => {
  const evento = new KeyboardEvent("keydown", { key: tecla, cancelable: true, ...extras })
  window.dispatchEvent(evento)
  return evento
}

describe("os atalhos do teclado", () => {
  it("Ctrl+S salva e nao deixa o navegador abrir o salvar da pagina", () => {
    const aoSalvar = vi.fn()
    renderHook(() => useAtalhos({ aoSalvar, aoAbrirPaleta: vi.fn() }))
    const evento = teclar("s", { ctrlKey: true })
    expect(aoSalvar).toHaveBeenCalled()
    expect(evento.defaultPrevented).toBe(true)
  })

  it("Cmd+S no Mac faz o mesmo", () => {
    const aoSalvar = vi.fn()
    renderHook(() => useAtalhos({ aoSalvar, aoAbrirPaleta: vi.fn() }))
    teclar("s", { metaKey: true })
    expect(aoSalvar).toHaveBeenCalled()
  })

  it("Ctrl+K e Cmd+K abrem a paleta", () => {
    const aoAbrirPaleta = vi.fn()
    renderHook(() => useAtalhos({ aoSalvar: vi.fn(), aoAbrirPaleta }))
    teclar("k", { ctrlKey: true })
    teclar("k", { metaKey: true })
    expect(aoAbrirPaleta).toHaveBeenCalledTimes(2)
  })

  it("a tecla sozinha nao faz nada", () => {
    const aoSalvar = vi.fn()
    const aoAbrirPaleta = vi.fn()
    renderHook(() => useAtalhos({ aoSalvar, aoAbrirPaleta }))
    teclar("s")
    teclar("k")
    expect(aoSalvar).not.toHaveBeenCalled()
    expect(aoAbrirPaleta).not.toHaveBeenCalled()
  })

  it("o atalho morre com o componente", () => {
    const aoSalvar = vi.fn()
    const { unmount } = renderHook(() => useAtalhos({ aoSalvar, aoAbrirPaleta: vi.fn() }))
    unmount()
    teclar("s", { ctrlKey: true })
    expect(aoSalvar).not.toHaveBeenCalled()
  })
})
