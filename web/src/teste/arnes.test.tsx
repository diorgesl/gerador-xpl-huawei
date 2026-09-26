import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

function Ola() {
  return <p>ola</p>
}

describe("o arnes de teste", () => {
  it("renderiza um componente e le o texto", () => {
    render(<Ola />)
    expect(screen.getByText("ola")).toBeInTheDocument()
  })
})
