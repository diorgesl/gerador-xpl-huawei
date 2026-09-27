import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { PainelSaida, type AbaSaida } from "./PainelSaida"

// A linha do meio e TROCADA, e nao inserida: uma linha a mais conta so como
// incluida, e a assercao deste arquivo e a que conta os dois lados
const BLOCO = "xpl route-filter CUST-1-EXPORT-V4\nfinish\nend-filter"
const ANTIGO = "xpl route-filter CUST-1-EXPORT-V4\npass\nend-filter"

const aba = (extra: Partial<AbaSaida> = {}): AbaSaida => ({
  id: "bloco", rotulo: "bloco do peer", conteudo: BLOCO, arquivo: "CUST-1.txt", salvo: BLOCO, ...extra,
})

const montar = (props: Partial<Parameters<typeof PainelSaida>[0]> = {}) =>
  render(
    <PainelSaida
      abas={[aba()]} sujo={false} carregando={false} erro={null}
      // o padrao e a copia que deu certo, que e o caso comum da tela
      onCopiar={vi.fn().mockResolvedValue(true)} {...props}
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
    const onSalvarECopiar = vi.fn().mockResolvedValue(true)
    const onCopiar = vi.fn()
    montar({ sujo: true, onSalvarECopiar, onCopiar })
    await userEvent.click(screen.getByRole("button", { name: /salvar e copiar/i }))
    expect(onSalvarECopiar).toHaveBeenCalled()
    expect(onCopiar).not.toHaveBeenCalled()
  })

  it("nao confirma quando o salvamento recusa", async () => {
    // a spec: salvar recusado nao copia nada, e o botao nao pode dizer que
    // copiou. A tela devolve false e o rotulo fica onde estava
    const onSalvarECopiar = vi.fn().mockResolvedValue(false)
    montar({ sujo: true, onSalvarECopiar })
    await userEvent.click(screen.getByRole("button", { name: /salvar e copiar/i }))
    expect(onSalvarECopiar).toHaveBeenCalled()
    expect(screen.queryByRole("button", { name: /copiado/i })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: /salvar e copiar/i })).toBeInTheDocument()
  })

  it("nao confirma quando a copia caiu no degrau da selecao manual", async () => {
    // sem clipboard e sem execCommand o texto fica so selecionado, e o toast
    // pede o Ctrl+C: o botao nao pode dizer que copiou
    const onCopiar = vi.fn().mockResolvedValue(false)
    montar({ onCopiar })
    await userEvent.click(screen.getByRole("button", { name: /^copiar$/i }))
    expect(screen.queryByRole("button", { name: /copiado/i })).not.toBeInTheDocument()
  })

  it("nao dispara o salvamento duas vezes no mesmo clique duplo", async () => {
    let liberar: (v: boolean) => void = () => {}
    const onSalvarECopiar = vi.fn(() => new Promise<boolean>((resolver) => { liberar = resolver }))
    montar({ sujo: true, onSalvarECopiar })
    const botao = screen.getByRole("button", { name: /salvar e copiar/i })
    await userEvent.click(botao)
    await userEvent.click(botao)
    expect(onSalvarECopiar).toHaveBeenCalledTimes(1)
    // o botao so volta a aceitar quando o primeiro salvamento responde
    await act(async () => { liberar(true) })
    expect(await screen.findByRole("button", { name: /copiado/i })).toBeInTheDocument()
  })

  it("confirma com copiado por um segundo e meio", async () => {
    // `vi.useFakeTimers()` puro trava o clique: o `asyncWrapper` do
    // testing-library espera um `setTimeout(0)` para liberar e so o adianta se
    // achar um global `jest`, que nao existe no Vitest. Com shouldAdvanceTime
    // o relogio falso anda sozinho o bastante para o userEvent nao pendurar.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const usuario = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const onCopiar = vi.fn().mockResolvedValue(true)
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

  it("a aba de remocao continua copiavel com a previa em erro", async () => {
    // a remocao vem do registro salvo, e nao da previa: o erro do formulario
    // nao pode levar embora o botao de uma aba que tem bloco proprio
    montar({
      erro: "com erro",
      abas: [aba({ conteudo: null }), aba({ id: "remover", rotulo: "remoção", soLeitura: true, salvo: ANTIGO })],
    })
    await userEvent.click(screen.getByRole("tab", { name: /remoção/i }))
    expect(screen.getByRole("button", { name: /^copiar$/i })).toBeInTheDocument()
  })
})

describe("as abas", () => {
  it("uma aba por bloco, e so as disponiveis", async () => {
    montar({
      abas: [aba(), aba({ id: "criar", rotulo: "ao criar o peer", conteudo: "xpl community-list CL-PEER-1", arquivo: "criar.txt", salvo: null })],
    })
    expect(screen.getByRole("tab", { name: /bloco do peer/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole("tab", { name: /ao criar o peer/i }))
    // o tokenizador parte a linha em spans, entao a busca nao pode pedir a
    // linha inteira; o pedaco ainda falha se a troca de aba nao acontecer
    expect(screen.getByText(/CL-PEER-1/)).toBeInTheDocument()
  })
})
