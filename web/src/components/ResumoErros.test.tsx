import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { ResumoErros } from "./ResumoErros"

describe("o resumo do topo do formulario", () => {
  it("lista um item por mensagem e leva ao campo", async () => {
    const aoIrPara = vi.fn()
    render(
      <ResumoErros
        erros={{ asn: "ASN ja usado pelo peer BRDIGITAL", "sessoes.v4.local": "endereco obrigatorio" }}
        tipo="cliente"
        aoIrPara={aoIrPara}
      />,
    )
    expect(screen.getByText("ASN ja usado pelo peer BRDIGITAL")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: /endereco obrigatorio/ }))
    expect(aoIrPara).toHaveBeenCalledWith("sessao_v4_local", "sessoes")
  })

  it("o erro sem campo nenhum aparece como texto, sem link", () => {
    render(<ResumoErros erros={{ bgpq4: "bgpq4 devolveu erro 1" }} tipo="cliente" aoIrPara={vi.fn()} />)
    expect(screen.getByText("bgpq4 devolveu erro 1")).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /bgpq4 devolveu/ })).not.toBeInTheDocument()
  })

  it("nao mostra nada quando nao ha erro", () => {
    const { container } = render(<ResumoErros erros={{}} tipo="cliente" aoIrPara={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it("o icone acompanha a mensagem, para o erro nao depender so da cor", () => {
    // a spec pede icone alem da cor no erro e no aviso: o matiz do aviso e
    // vizinho do badge de parceiro, e quem nao distingue cor precisa do sinal
    const { container } = render(
      <ResumoErros erros={{ asn: "ja usado" }} tipo="cliente" aoIrPara={vi.fn()} />,
    )
    expect(container.querySelector("svg")).toBeTruthy()
  })
})
