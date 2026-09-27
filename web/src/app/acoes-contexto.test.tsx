import { renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it, vi } from "vitest"
import { ContextoDefinirAcoes, usePublicarAcoes, type AcoesDaTela } from "./acoes-contexto"

// o que a casca ve: cada objeto que a tela publicou, na ordem em que chegou
function montar(inicial: AcoesDaTela) {
  const publicadas: AcoesDaTela[] = []
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ContextoDefinirAcoes.Provider value={(a) => { publicadas.push(a) }}>
      {children}
    </ContextoDefinirAcoes.Provider>
  )
  const { rerender, unmount } = renderHook((props: AcoesDaTela) => usePublicarAcoes(props), {
    wrapper,
    initialProps: inicial,
  })
  return { publicadas, rerender, unmount }
}

describe("as acoes que a tela publica", () => {
  it("so os campos que a tela declarou, porque a paleta decide pela presenca", () => {
    const { publicadas } = montar({ aoSalvar: vi.fn() })
    expect(Object.keys(publicadas[0])).toEqual(["aoSalvar"])
  })

  it("tela sem acao nenhuma publica um objeto vazio", () => {
    const { publicadas } = montar({})
    expect(Object.keys(publicadas[0])).toEqual([])
  })

  it("publica o mesmo objeto a cada render, que e o que impede o laco", () => {
    const { publicadas, rerender } = montar({ aoSalvar: vi.fn() })
    rerender({ aoSalvar: vi.fn() })
    expect(publicadas[publicadas.length - 1]).toBe(publicadas[0])
  })

  it("o campo publicado chama o handler do ultimo render", () => {
    const primeiro = vi.fn()
    const ultimo = vi.fn()
    const { publicadas, rerender } = montar({ aoSalvar: primeiro })
    rerender({ aoSalvar: ultimo })
    publicadas[0].aoSalvar?.()
    expect(primeiro).not.toHaveBeenCalled()
    expect(ultimo).toHaveBeenCalled()
  })

  it("sair da tela limpa as acoes dela", () => {
    const { publicadas, unmount } = montar({ aoSalvar: vi.fn(), aoDuplicar: vi.fn() })
    unmount()
    expect(publicadas[publicadas.length - 1]).toEqual({})
  })

  it("republica quando a tela passa a declarar uma acao", () => {
    const { publicadas, rerender } = montar({ aoSalvar: vi.fn() })
    rerender({ aoSalvar: vi.fn(), aoDuplicar: vi.fn() })
    expect(Object.keys(publicadas[publicadas.length - 1])).toEqual(["aoSalvar", "aoDuplicar"])
  })

  it("tira a acao que a tela deixou de declarar", () => {
    const { publicadas, rerender } = montar({ aoSalvar: vi.fn(), aoDuplicar: vi.fn() })
    rerender({ aoSalvar: vi.fn() })
    expect(Object.keys(publicadas[publicadas.length - 1])).toEqual(["aoSalvar"])
  })
})
