import { render } from "@testing-library/react"
import { RouterProvider, createMemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { AvisoNaoSalvo } from "./AvisoNaoSalvo"

function montar(sujo: boolean) {
  const roteador = createMemoryRouter(
    [{ path: "/", element: <AvisoNaoSalvo sujo={sujo} /> }],
    { initialEntries: ["/"] },
  )
  return render(<RouterProvider router={roteador} />)
}

describe("o aviso de alteracao nao salva", () => {
  it("segura o fechamento da aba quando ha alteracao", () => {
    montar(true)
    const evento = new Event("beforeunload", { cancelable: true })
    window.dispatchEvent(evento)
    expect(evento.defaultPrevented).toBe(true)
  })

  it("nao segura nada quando esta tudo salvo", () => {
    montar(false)
    const evento = new Event("beforeunload", { cancelable: true })
    window.dispatchEvent(evento)
    expect(evento.defaultPrevented).toBe(false)
  })
})
