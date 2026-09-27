import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { CodigoXpl } from "./CodigoXpl"

const XPL = [
  "# gerado por bgpgen - nao editar a mao",
  "xpl route-filter CUST-268127-IMPORT-V4",
  " apply community {64512:1110} additive",
  "end-filter",
].join("\n")

describe("o bloco de codigo", () => {
  it("numera as linhas e pinta cada classe de token", () => {
    render(<CodigoXpl texto={XPL} />)
    expect(screen.getByText("1")).toBeInTheDocument()
    expect(screen.getByText("4")).toBeInTheDocument()
    expect(document.querySelector(".tk-comentario")?.textContent).toContain("# gerado por bgpgen")
    expect(document.querySelector(".tk-palavra-chave")?.textContent).toBe("xpl")
    expect(document.querySelector(".tk-objeto")?.textContent).toBe("CUST-268127-IMPORT-V4")
    expect(document.querySelector(".tk-community")?.textContent).toBe("64512:1110")
  })

  it("a numeracao fica fora do bloco de codigo", () => {
    render(<CodigoXpl texto={XPL} />)
    const pre = document.querySelector("pre")
    const linhasCodigo = Array.from(pre?.querySelectorAll("code > span") ?? [])
    // Cada linha e um span a parte e o numero mora na coluna da esquerda, fora
    // do `code`: juntando as linhas com quebra, o que sai e o XPL original, sem
    // numero nenhum no meio.
    expect(linhasCodigo.map((l) => l.textContent).join("\n")).toBe(XPL)
  })

  it("o botao de quebra de linha troca a rolagem pelo embrulho", async () => {
    render(<CodigoXpl texto={XPL} />)
    const code = () => document.querySelector("code")
    expect(code()?.className).toContain("whitespace-pre")
    await userEvent.click(screen.getByRole("button", { name: /quebrar linhas/i }))
    expect(code()?.className).toContain("whitespace-pre-wrap")
  })

  it("a linha de diff fica monocromatica, na cor do estado", () => {
    render(
      <CodigoXpl
        texto={XPL}
        linhas={[
          { texto: "linha igual", estado: "igual" },
          { texto: "apply community {64512:1110} additive", estado: "incluida" },
          { texto: "linha que saiu", estado: "removida" },
        ]}
      />,
    )
    const incluida = document.querySelector(".ln-incluida")
    expect(incluida?.textContent).toContain("64512:1110")
    // sem tokenizacao na linha marcada: o contraste da cor do estado manda
    expect(incluida?.querySelector(".tk-community")).toBeNull()
    expect(document.querySelector(".ln-removida")?.textContent).toContain("linha que saiu")
  })
})
