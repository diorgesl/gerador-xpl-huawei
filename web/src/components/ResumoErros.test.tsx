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

  it("um erro que cobre varios campos leva a secao, e nao ao primeiro campo", async () => {
    // o teste de `prefixos` pode ser o v4 ou o v6, e a mensagem nao diz qual:
    // prometer o campo v4 era pior que levar ao topo da secao
    const aoIrPara = vi.fn()
    render(
      <ResumoErros
        erros={{ prefixos: "prefixo invalido: 2001:db8::/129" }}
        tipo="cliente"
        aoIrPara={aoIrPara}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /prefixo invalido/ }))
    expect(aoIrPara).toHaveBeenCalledWith(null, "prefixos")
  })

  it("um erro de um campo so continua indo no campo", async () => {
    const aoIrPara = vi.fn()
    render(<ResumoErros erros={{ asn: "ASN ja usado" }} tipo="cliente" aoIrPara={aoIrPara} />)
    await userEvent.click(screen.getByRole("button", { name: /ASN ja usado/ }))
    expect(aoIrPara).toHaveBeenCalledWith("asn", "identificacao")
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
