import { useState } from "react"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it } from "vitest"
import { mockFetch, montarRota, peticoes, type Resposta } from "@/teste/roteador"
import { AvisoNaoSalvo } from "@/components/AvisoNaoSalvo"
import { Casca } from "@/app/casca"
import { PrefixosTela } from "@/telas/prefixos/PrefixosTela"
import { useTenant } from "@/app/tenant"
import { usePublicarRascunho } from "./rascunho"

/**
 * A tela de formulario em miniatura, no lugar da tela do peer e da do grupo:
 * ela faz o que as duas fazem e interessa aqui - publica o rascunho, e arma o
 * AvisoNaoSalvo. O aviso entra junto porque o useBlocker dele e a armadilha da
 * troca: a tela que acabou de sair ainda esta de pe quando o seletor pede a
 * navegacao para a lista.
 */
function Formulario() {
  const { asn } = useTenant()
  const [texto, setTexto] = useState("")
  const sujo = texto !== ""
  usePublicarRascunho(sujo)
  return (
    <div>
      <p>tela da rede {asn}</p>
      <label>
        campo
        <input value={texto} onChange={(e) => setTexto(e.target.value)} />
      </label>
      <AvisoNaoSalvo sujo={sujo} />
    </div>
  )
}

const rotas = [
  {
    path: "/",
    element: <Casca />,
    children: [
      { path: "peers", element: <p>lista de peers</p> },
      { path: "peers/:id", element: <Formulario /> },
      // a tela de verdade, e nao um duble: e ela que mede a fiacao das tres
      // telas de formulario, que publicam o rascunho cada uma por si
      { path: "prefixos", element: <PrefixosTela /> },
    ],
  },
]

// o que a casca e o seletor perguntam em toda rota: a lista de redes, os
// registros da rede aberta e o bloco de prefixos que a tela de /prefixos edita
const mapa = (): Record<string, Resposta> => ({
  "GET /api/asns": { corpo: ["64512", "264130"] },
  "GET /api/peers": { corpo: [] },
  "GET /api/grupos": { corpo: [] },
  "GET /api/blocos": {
    corpo: { texto: { v4: "38.252.64.0/22 64512:613", v6: "" }, originacao: "", remover: "" },
  },
  "POST /api/blocos/previa": {
    corpo: { erros: {}, avisos: [], bloco: "", arquivo: "blocos.txt", salvo: "" },
  },
})

const PERGUNTA = /Há alterações que ainda não foram para o/

/** Abre o menu do seletor e pede a outra rede. */
async function escolherOutraRede() {
  await userEvent.click(screen.getByRole("button", { name: "AS64512" }))
  await userEvent.click(await screen.findByRole("menuitem", { name: "AS264130" }))
}

describe("a troca de tenant com rascunho sujo", () => {
  beforeEach(() => window.sessionStorage.clear())

  it("trocar de tenant com rascunho sujo pergunta antes", async () => {
    mockFetch(mapa())
    // /prefixos e a tela em que a troca nao navega: o rascunho e o unico
    // estrago em jogo, e por isso o caso isola a pergunta
    montarRota(rotas, "/prefixos")
    const v4 = await screen.findByLabelText("IPv4")
    await userEvent.type(v4, "  38.252.68.0/22 64512:613")

    await escolherOutraRede()

    expect(await screen.findByText(PERGUNTA)).toBeInTheDocument()
    // a pergunta vem ANTES da troca, e nao depois: com o ASN ja trocado a tela
    // de uma rede ficaria de pe consultando a outra, que e o buraco que este
    // aviso existe para fechar
    expect(screen.getByRole("button", { name: "AS64512" })).toBeInTheDocument()
    expect(peticoes().some((p) => p.query.includes("asn=264130"))).toBe(false)
  })

  it("cancelar mantem o tenant e o rascunho", async () => {
    mockFetch(mapa())
    montarRota(rotas, "/prefixos")
    const v4 = await screen.findByLabelText("IPv4")
    await userEvent.type(v4, "  38.252.68.0/22 64512:613")
    await escolherOutraRede()

    await userEvent.click(await screen.findByRole("button", { name: "continuar editando" }))

    // a pergunta some sem trocar nada: nem o tenant, nem a tela (que perde o
    // rascunho na remontagem), nem o que ja foi digitado
    expect(screen.queryByText(PERGUNTA)).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "AS64512" })).toBeInTheDocument()
    expect(screen.getByLabelText("IPv4")).toHaveValue("38.252.64.0/22 64512:613  38.252.68.0/22 64512:613")
    expect(peticoes().some((p) => p.query.includes("asn=264130"))).toBe(false)
  })

  it("confirmar troca o tenant e sai para /peers", async () => {
    mockFetch(mapa())
    // o registro aberto e do tenant antigo: /peers/1 nao existe do outro lado,
    // ou e outro peer, entao confirmar tem que sair da tela dele
    montarRota(rotas, "/peers/1")
    expect(await screen.findByText("tela da rede 64512")).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText("campo"), "rascunho da rede A")
    await escolherOutraRede()

    await userEvent.click(await screen.findByRole("button", { name: "trocar sem salvar" }))

    // saiu da tela do registro e esta na lista da rede nova
    expect(await screen.findByText("lista de peers")).toBeInTheDocument()
    expect(await screen.findByText("AS264130")).toBeInTheDocument()
    // a consulta seguinte ja e a da rede escolhida
    await waitFor(() => expect(peticoes().some(
      (p) => p.caminho === "/api/peers" && p.query.includes("asn=264130"))).toBe(true))
  })
})
