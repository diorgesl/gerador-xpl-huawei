import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { PainelSaida, type AbaSaida } from "./PainelSaida"

// O out/ guardado tem "pass" onde a previa tem "finish": uma linha trocada
// conta como incluida e removida. Fosse uma linha so inserida no fim, o
// "end-filter" continuaria igual dos dois lados e o diff contaria 1 e 0.
const BLOCO = "xpl route-filter CUST-1-EXPORT-V4\nfinish\nend-filter"
const ANTIGO = "xpl route-filter CUST-1-EXPORT-V4\npass\nend-filter"

const aba = (extra: Partial<AbaSaida> = {}): AbaSaida => ({
  id: "bloco", rotulo: "bloco do peer", conteudo: BLOCO, arquivo: "CUST-1.txt", salvo: BLOCO, ...extra,
})

const montar = (props: Partial<Parameters<typeof PainelSaida>[0]> = {}) =>
  render(
    <PainelSaida
      abas={[aba()]} sujo={false} carregando={false} erro={null}
      onCopiar={vi.fn()} {...props}
    />,
  )

afterEach(() => vi.useRealTimers())

describe("o estado do bloco em relacao ao out/", () => {
  it("igual ao salvo", () => {
    montar()
    expect(screen.getByText(/igual ao salvo/)).toBeInTheDocument()
  })

  it("arquivo novo, quando o registro ainda nao foi gravado", () => {
    montar({ abas: [aba({ salvo: null })] })
    expect(screen.getByText(/arquivo novo/)).toBeInTheDocument()
  })

  it("conta as linhas quando ha edicao nao salva", () => {
    montar({ abas: [aba({ salvo: ANTIGO })], sujo: true })
    expect(screen.getByText(/1 linha incluída, 1 removida/)).toBeInTheDocument()
  })

  it("a diferenca sem edicao nenhuma e out/ desatualizado", () => {
    montar({ abas: [aba({ salvo: ANTIGO })], sujo: false })
    expect(screen.getByText(/o arquivo em out\/ está desatualizado/)).toBeInTheDocument()
  })
})

describe("o botao de copiar", () => {
  it("e copiar quando o formulario esta igual ao salvo", () => {
    montar()
    expect(screen.getByRole("button", { name: /^copiar$/i })).toBeInTheDocument()
  })

  it("vira salvar e copiar com alteracao nao salva", () => {
    montar({ sujo: true })
    expect(screen.getByRole("button", { name: /salvar e copiar/i })).toBeInTheDocument()
  })

  it("vira salvar e copiar quando o out/ esta desatualizado", () => {
    montar({ abas: [aba({ salvo: ANTIGO })] })
    expect(screen.getByRole("button", { name: /salvar e copiar/i })).toBeInTheDocument()
  })

  it("na aba de remocao e sempre copiar, porque ela vem do registro salvo", () => {
    montar({ sujo: true, abas: [aba({ id: "remover", rotulo: "remoção", soLeitura: true, salvo: ANTIGO })] })
    expect(screen.getByRole("button", { name: /^copiar$/i })).toBeInTheDocument()
  })

  it("o salvar e copiar nao copia antes de gravar", async () => {
    const onSalvarECopiar = vi.fn().mockResolvedValue(undefined)
    const onCopiar = vi.fn()
    montar({ sujo: true, onSalvarECopiar, onCopiar })
    await userEvent.click(screen.getByRole("button", { name: /salvar e copiar/i }))
    expect(onSalvarECopiar).toHaveBeenCalled()
    expect(onCopiar).not.toHaveBeenCalled()
  })

  it("confirma com copiado por um segundo e meio", async () => {
    // O shouldAdvanceTime e o que destrava a interacao. O asyncWrapper do
    // testing-library espera um setTimeout(0) e so o adianta quando encontra um
    // global `jest`, que aqui nao existe: com o relogio parado o clique nunca
    // volta. Andando, o clique volta; o timer de 1,5 s segue sob controle do
    // teste, que o adianta na mao.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const usuario = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const onCopiar = vi.fn().mockResolvedValue(undefined)
    montar({ onCopiar })
    await usuario.click(screen.getByRole("button", { name: /^copiar$/i }))
    expect(await screen.findByRole("button", { name: /copiado/i })).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(1600))
    expect(screen.getByRole("button", { name: /^copiar$/i })).toBeInTheDocument()
  })
})

describe("a previa com erro de validacao", () => {
  it("nao mostra bloco e diz quando ele volta", () => {
    montar({ erro: "prefixo invalido: 10.0.0.0/33", abas: [aba({ conteudo: null })] })
    expect(screen.getByText(/a prévia volta quando os erros forem corrigidos/)).toBeInTheDocument()
    expect(screen.queryByText(/end-filter/)).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /copiar/i })).not.toBeInTheDocument()
  })
})

describe("as abas", () => {
  it("uma aba por bloco, e so as disponiveis", async () => {
    montar({
      abas: [aba(), aba({ id: "criar", rotulo: "ao criar o peer", conteudo: "xpl community-list CL-PEER-1", arquivo: "criar.txt", salvo: null })],
    })
    expect(screen.getByRole("tab", { name: /bloco do peer/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole("tab", { name: /ao criar o peer/i }))
    // O bloco entra tokenizado: "community-list" e "CL-PEER-1" sao spans
    // separados, e o getByText casa com o texto de um elemento so
    expect(screen.getByText(/CL-PEER-1/)).toBeInTheDocument()
  })
})
