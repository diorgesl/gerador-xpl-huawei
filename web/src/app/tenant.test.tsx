import { screen, waitFor } from "@testing-library/react"
import { useContext } from "react"
import { beforeEach, describe, expect, it } from "vitest"
import { montarRota, mockFetch, peticoes } from "@/teste/roteador"
import { usePeers } from "@/api/consultas"
import { ContextoTenant } from "./tenant"

function Espiao() {
  const { asn, asns } = useContext(ContextoTenant)
  // o `String` e o que faz o nulo aparecer: o JSX nao desenha o `{null}`, e a
  // prova do estado sem tenant e justamente ele escrito na tela
  return <p>asn={String(asn)} lista={asns.join(",")}</p>
}

function Peers() {
  usePeers()
  return <p>peers</p>
}

describe("o tenant da aba", () => {
  beforeEach(() => window.sessionStorage.clear())

  it("cai no primeiro da lista quando nao ha nada guardado", async () => {
    mockFetch({ "GET /api/asns": { corpo: ["64512", "264130"] } })
    montarRota([{ path: "/", element: <Espiao /> }])
    expect(await screen.findByText("asn=64512 lista=64512,264130")).toBeTruthy()
  })

  it("usa o que esta guardado quando ele esta na lista", async () => {
    window.sessionStorage.setItem("bgpgen.asn", "264130")
    mockFetch({ "GET /api/asns": { corpo: ["64512", "264130"] } })
    montarRota([{ path: "/", element: <Espiao /> }])
    expect(await screen.findByText("asn=264130 lista=64512,264130")).toBeTruthy()
  })

  it("cai no primeiro quando o guardado sumiu da lista", async () => {
    window.sessionStorage.setItem("bgpgen.asn", "999")
    mockFetch({ "GET /api/asns": { corpo: ["64512"] } })
    montarRota([{ path: "/", element: <Espiao /> }])
    expect(await screen.findByText("asn=64512 lista=64512")).toBeTruthy()
  })

  it("nao dispara consulta de dados antes de saber o ASN", async () => {
    // O `Peers` e o que faz a prova morder, e nao um enfeite: o `Espiao` so
    // le o contexto, e com ele sozinho a linha dos caminhos passaria mesmo
    // sem nenhuma guarda de `enabled` no app inteiro, porque consulta de
    // dados nenhuma sairia de verdade. A rota do duble esta no mapa para o
    // caso falhar na assercao, e nao no "rota sem mapa" do arnes
    mockFetch({ "GET /api/asns": { corpo: [] }, "GET /api/peers": { corpo: [] } })
    montarRota([{ path: "/", element: <><Espiao /><Peers /></> }])
    await waitFor(() => expect(screen.getByText("asn=null lista=")).toBeTruthy())
    expect(peticoes().map((p) => p.caminho)).toEqual(["/api/asns"])
  })

  it("a consulta de peers leva o asn escolhido", async () => {
    window.sessionStorage.setItem("bgpgen.asn", "264130")
    mockFetch({
      "GET /api/asns": { corpo: ["64512", "264130"] },
      "GET /api/peers": { corpo: [] },
    })
    montarRota([{ path: "/", element: <Peers /> }])
    await waitFor(() => expect(peticoes().some((p) => p.caminho === "/api/peers")).toBe(true))
    const pedido = peticoes().find((p) => p.caminho === "/api/peers")!
    expect(pedido.query).toContain("asn=264130")
  })
})
