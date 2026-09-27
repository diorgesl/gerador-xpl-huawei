import { fireEvent, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Link } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import { mockFetch, montarRota, peticoes, type Pedido, type Resposta } from "@/teste/roteador"
import { PrefixosTela } from "./PrefixosTela"

const BASE = {
  "GET /api/blocos": {
    corpo: {
      texto: { v4: "38.252.64.0/22  64512:613", v6: "2001:db8::/32  64512:613" },
      originacao: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list",
      remover: "undo xpl ip-prefix-list PL-ORIGEM-V4",
    },
  },
  "POST /api/blocos/previa": {
    corpo: { erros: {}, avisos: [], bloco: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list", arquivo: "blocos.txt", salvo: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list" },
  },
  "PUT /api/blocos": {
    corpo: {
      texto: { v4: "38.252.64.0/22  64512:613", v6: "2001:db8::/32  64512:613" },
      originacao: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list",
      remover: "undo xpl ip-prefix-list PL-ORIGEM-V4",
    },
  },
}

const rotas = [{ path: "/prefixos", element: <PrefixosTela /> }]

// A saida da tela, para os casos que medem o guarda de alteracao nao salva: o
// bloqueio e da navegacao, e sem um destino o `useBlocker` nao teria o que
// barrar
const comSaida = [
  { path: "/prefixos", element: <><PrefixosTela /><Link to="/outra">sair</Link></> },
  { path: "/outra", element: <div>outra tela</div> },
]

// A limpeza do `unstubAllGlobals` e o resto do que cada caso deixa para tras sao
// do arnes, que os registra uma vez por arquivo (web/src/teste/roteador.tsx)
afterEach(() => {
  vi.unstubAllGlobals()
  // as espias deste arquivo sao do `vi.spyOn` (o clique do download), e nao do
  // `stubGlobal` do arnes: sem esta linha a do primeiro caso ficaria de pe
  vi.restoreAllMocks()
})

/**
 * Segura uma leitura ate o caso mandar soltar, e repassa o resto ao arnes: e a
 * janela em que a tela esta montada sem dado nenhum.
 */
function segurarLeitura(chave: string) {
  const doArnes = globalThis.fetch
  let liberar: () => void = () => {}
  const espera = new Promise<void>((resolve) => { liberar = resolve })
  vi.stubGlobal("fetch", async (entrada: Request) => {
    if (`${entrada.method} ${String(entrada.url).split("?")[0]}` === chave) await espera
    return doArnes(entrada)
  })
  return () => liberar()
}

/** O clique do download, sem criar blob de verdade: so o nome interessa. */
function espiarDownload(): HTMLAnchorElement[] {
  const cliques: HTMLAnchorElement[] = []
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    cliques.push(this)
  })
  vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() })
  return cliques
}

const pedidos = (pedido: Pedido) => `${pedido.metodo} ${pedido.caminho}`

describe("a tela dos prefixos proprios", () => {
  it("mostra os dois editores com o texto de hoje", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/prefixos")
    await waitFor(() => expect(screen.getByLabelText(/IPv4/)).toHaveValue("38.252.64.0/22  64512:613"))
    expect(screen.getByLabelText(/IPv6/)).toHaveValue("2001:db8::/32  64512:613")
  })

  it("explica o formato acima dos editores", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/prefixos")
    expect(await screen.findByText(/uma linha por prefixo/i)).toBeInTheDocument()
    expect(screen.getByText(/fora de serviço/i)).toBeInTheDocument()
  })

  it("oferece as abas de originacao e de remocao", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/prefixos")
    expect(await screen.findByRole("tab", { name: /originação/i })).toBeInTheDocument()
    expect(await screen.findByRole("tab", { name: /remoção/i })).toBeInTheDocument()
  })

  it("a consulta ao IRR substitui o texto dos dois editores sem gravar", async () => {
    mockFetch({
      ...BASE,
      "POST /api/blocos/irr": { corpo: { v4: "45.169.232.0/22\n45.169.236.0/23", v6: "2001:db8::/32" } },
    })
    montarRota(rotas, "/prefixos")
    await userEvent.click(await screen.findByRole("button", { name: /consultar IRR/i }))
    await waitFor(() => expect(screen.getByLabelText(/IPv4/)).toHaveValue("45.169.232.0/22\n45.169.236.0/23"))
    expect(screen.getByLabelText(/IPv6/)).toHaveValue("2001:db8::/32")
    // "sem gravar" e a segunda metade do nome do caso: sem esta linha uma tela
    // que gravasse junto com a consulta passaria
    expect(peticoes().some((p) => p.metodo === "PUT")).toBe(false)
  })

  it("diz que a consulta ao IRR esta em andamento", async () => {
    // o bgpq4 leva segundos, e sem o aviso o operador nao sabe se o clique
    // pegou: a consulta repoe os dois editores quando ela volta
    mockFetch({ ...BASE, "POST /api/blocos/irr": { corpo: { v4: "45.169.232.0/22", v6: "" } } })
    montarRota(rotas, "/prefixos")
    await screen.findByLabelText(/IPv4/)
    const soltar = segurarLeitura("POST /api/blocos/irr")
    await userEvent.click(screen.getByRole("button", { name: /consultar IRR/i }))
    expect(await screen.findByText(/consultando o IRR/)).toBeInTheDocument()
    soltar()
    await waitFor(() => expect(screen.queryByText(/consultando o IRR/)).not.toBeInTheDocument())
  })

  it("a falha da consulta ao IRR sai ao lado dos botoes, sem apagar o painel", async () => {
    // o erro do bgpq4 nao e de um campo: a tela desenhava so os dois nomes de
    // caixa, e a mensagem nao aparecia em lugar nenhum enquanto o painel ficava
    // marcado com erro, escondendo um bloco que a consulta falhada nao contesta
    mockFetch({
      ...BASE,
      "POST /api/blocos/irr": { status: 502, corpo: { erros: { bgpq4: "bgpq4 falhou: sem resposta do RADB" }, avisos: [] } },
    })
    montarRota(rotas, "/prefixos")
    await userEvent.click(await screen.findByRole("button", { name: /consultar IRR/i }))
    expect(await screen.findByText("bgpq4 falhou: sem resposta do RADB")).toBeInTheDocument()
    expect(screen.getByText(/PL-ORIGEM-V4/)).toBeInTheDocument()
  })

  it("o texto digitado fica onde esta quando a consulta ao IRR falha", async () => {
    // O par do test_bgpq4_fora_do_ar_nao_perde_a_lista_do_operador do
    // test_app.py. A API de hoje devolve so o erro, sem a lista de volta, entao
    // a prova de que o operador nao perde o que escreveu e o editor manter o
    // valor depois da recusa
    mockFetch({
      ...BASE,
      "POST /api/blocos/irr": { status: 502, corpo: { erros: { bgpq4: "bgpq4 nao esta no PATH" }, avisos: [] } },
    })
    montarRota(rotas, "/prefixos")
    const v4 = await screen.findByLabelText(/IPv4/)
    fireEvent.change(v4, { target: { value: "203.0.113.0/24  64512:211" } })

    await userEvent.click(screen.getByRole("button", { name: /consultar IRR/i }))

    expect(await screen.findByText("bgpq4 nao esta no PATH")).toBeInTheDocument()
    expect(screen.getByLabelText(/IPv4/)).toHaveValue("203.0.113.0/24  64512:211")
  })

  it("o erro do prefixo torto aparece no editor da familia dele", async () => {
    mockFetch({ ...BASE, "PUT /api/blocos": { status: 422, corpo: { erros: { blocos_v6: "prefixo invalido: 2001:db8::/129" }, avisos: [] } } })
    montarRota(rotas, "/prefixos")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar/i }))
    // a ancora e a caixa do IPv6, e nao o documento: o documento inteiro deixa
    // passar uma tela que desenhe a mensagem no lugar errado
    await waitFor(() =>
      expect(document.querySelector('[data-campo="blocos_v6"]')).toHaveTextContent("prefixo invalido: 2001:db8::/129"),
    )
    expect(document.querySelector('[data-campo="blocos_v4"]')).not.toHaveTextContent("prefixo invalido")
  })

  it("a recusa do salvar sai quando a proxima previa responde", async () => {
    // a recusa nao vence sozinha: quem a derruba e a proxima previa, com a lista
    // de erros dela. Sem olhar para a data da resposta, a mensagem do salvar
    // ficaria embaixo da caixa depois de o operador consertar a linha, e o
    // painel seguiria apagado por causa de um erro que ja nao existe
    mockFetch({ ...BASE, "PUT /api/blocos": { status: 422, corpo: { erros: { blocos_v6: "prefixo invalido: 2001:db8::/129" }, avisos: [] } } })
    montarRota(rotas, "/prefixos")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar/i }))
    expect(await screen.findByText("prefixo invalido: 2001:db8::/129")).toBeInTheDocument()
    expect(screen.queryByText(/PL-ORIGEM-V4/)).not.toBeInTheDocument()
    // o operador conserta a linha: a previa responde de novo, com a lista dela
    fireEvent.change(screen.getByLabelText(/IPv6/), { target: { value: "2001:db8::/32" } })
    await waitFor(() => expect(screen.queryByText("prefixo invalido: 2001:db8::/129")).not.toBeInTheDocument())
    expect(await screen.findByText(/PL-ORIGEM-V4/)).toBeInTheDocument()
  })

  it("a previa que falhou nao vira o bloco salvo no painel", async () => {
    // sem olhar o isError da previa o painel cai no bloco salvo e o mostra como
    // se fosse a previa do que esta escrito, com o botao de copiar vivo
    mockFetch({ ...BASE, "POST /api/blocos/previa": { status: 500, corpo: { detail: "falhou" } } })
    montarRota(rotas, "/prefixos")
    // a previa gasta o retry do cliente (um, com o atraso padrao de 1s) antes de
    // desistir, e a espera padrao de 1s fica em cima do relogio
    expect(await screen.findByText(/a prévia volta quando os erros forem corrigidos/, {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.queryByText(/PL-ORIGEM-V4/)).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /copiar/i })).not.toBeInTheDocument()
  })

  it("a previa rele o out/ depois do salvar", async () => {
    // o salvar invalida o registro, e a previa tem chave propria, com o texto:
    // sem invalidar ela tambem, o `salvo` continua sendo o arquivo de ANTES, e
    // o cabecalho diz que o out/ esta atrasado no segundo seguinte ao toast
    const antes = {
      erros: {}, avisos: [],
      bloco: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list",
      arquivo: "blocos.txt", salvo: "xpl ip-prefix-list PL-ORIGEM-V4-VELHO\nend-list",
    }
    const mapa = { ...BASE, "POST /api/blocos/previa": { corpo: antes } }
    mockFetch(mapa)
    montarRota(rotas, "/prefixos")
    expect(await screen.findByText(/o arquivo em out\/ está desatualizado/)).toBeInTheDocument()
    // O out/ vira o do salvar no clique, e o duble passa a responder esse: e o
    // que o backend faz quando a previa e refeita depois da gravacao. Nenhum
    // pedido de previa sai entre a troca e o clique, porque a chave dela nao muda
    mapa["POST /api/blocos/previa"].corpo = { ...antes, salvo: antes.bloco }
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByText(/igual ao salvo/)).toBeInTheDocument()
    expect(screen.queryByText(/o arquivo em out\/ está desatualizado/)).not.toBeInTheDocument()
  })

  it("a remocao baixa com o nome dela", async () => {
    // o nome do undo nao pode ser o mesmo da originacao: os dois downloads caem
    // na mesma pasta, e o segundo salvamento passa por cima do primeiro
    const cliques = espiarDownload()
    mockFetch(BASE)
    montarRota(rotas, "/prefixos")
    await userEvent.click(await screen.findByRole("tab", { name: /remoção/i }))
    await userEvent.click(screen.getByRole("button", { name: /baixar/i }))
    expect(cliques.map((a) => a.download)).toEqual(["remover-blocos.txt"])
  })

  it("o erro que vem da propria previa aparece e tira o bloco antigo do painel", async () => {
    // a previa responde 200 com o mapa de erros e o bloco nulo. Sem olhar para
    // esse mapa a tela ficaria muda, e o painel cairia no bloco salvo como se
    // ele fosse a previa do texto de agora
    mockFetch({
      ...BASE,
      "POST /api/blocos/previa": {
        corpo: {
          erros: { blocos_v6: "prefixo invalido: 2001:db8::/129" },
          avisos: [],
          bloco: null,
          arquivo: null,
          salvo: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list",
        },
      },
    })
    montarRota(rotas, "/prefixos")
    expect(await screen.findByText("prefixo invalido: 2001:db8::/129")).toBeInTheDocument()
    expect(await screen.findByText(/a prévia volta quando os erros forem corrigidos/)).toBeInTheDocument()
  })

  it("nao deixa salvar nem consultar o IRR enquanto o registro nao chegou", async () => {
    // A janela entre a montagem e a leitura, que e a unica em que a tela existe
    // sem o registro. O backend ACEITA os dois editores vazios (o
    // `validar_blocos` nao tem o que apontar) e gravaria um out/blocos.txt sem
    // nenhuma originacao; a consulta ao IRR encheria as caixas com um rascunho
    // que o salvar nao aceita, porque quem libera o salvar e o registro
    mockFetch(BASE)
    const soltar = segurarLeitura("GET /api/blocos")
    montarRota(rotas, "/prefixos")
    const salvar = await screen.findByRole("button", { name: /^salvar$/i })
    expect(salvar).toBeDisabled()
    expect(screen.getByRole("button", { name: /consultar IRR/i })).toBeDisabled()
    fireEvent.click(salvar)
    expect(peticoes().filter((p) => p.metodo !== "GET")).toEqual([])
    // e a direcao que mostra: com o registro na mao os dois voltam
    soltar()
    await waitFor(() => expect(screen.getByRole("button", { name: /^salvar$/i })).toBeEnabled())
    expect(screen.getByRole("button", { name: /consultar IRR/i })).toBeEnabled()
  })

  it("a rede fora no salvar avisa com tentar de novo, e o texto nao se perde", async () => {
    // O openapi-fetch RE-LANCA a excecao de rede: o mutate nao chama onSuccess
    // nem onError nenhum, e o clique em salvar nao deixava rastro na tela
    const mapa: Record<string, Resposta> = { ...BASE, "PUT /api/blocos": { rede: true } }
    mockFetch(mapa)
    montarRota(rotas, "/prefixos")
    await screen.findByLabelText(/IPv4/)
    fireEvent.change(screen.getByLabelText(/IPv4/), { target: { value: "45.169.232.0/22  64512:613" } })
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    expect(screen.getByLabelText(/IPv4/)).toHaveValue("45.169.232.0/22  64512:613")
    mapa["PUT /api/blocos"] = BASE["PUT /api/blocos"]
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    await waitFor(() => expect(peticoes().filter((p) => p.metodo === "PUT")).toHaveLength(2))
  })

  it("o 500 no salvar avisa com tentar de novo", async () => {
    // o 500 e o outro caso da mesma linha da spec ("500 ou rede fora"), e ele
    // chega pelo ramo do `r.error`, e nao pela excecao
    const mapa: Record<string, Resposta> = { ...BASE, "PUT /api/blocos": { status: 500, corpo: { detail: "falhou" } } }
    mockFetch(mapa)
    montarRota(rotas, "/prefixos")
    await screen.findByLabelText(/IPv4/)
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByRole("button", { name: /tentar de novo/i })).toBeInTheDocument()
    mapa["PUT /api/blocos"] = BASE["PUT /api/blocos"]
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    await waitFor(() => expect(peticoes().filter((p) => p.metodo === "PUT")).toHaveLength(2))
  })

  it("um 5xx sem corpo de recusa nao mostra o texto de resposta inesperada", async () => {
    // peer e grupo suprimem o `_corpo` nesse caso; os prefixos mostravam os
    // dois avisos juntos, e o "resposta inesperada da API" ficava por cima do
    // aviso que dizia o que fazer
    mockFetch({ ...BASE, "PUT /api/blocos": { status: 500, corpo: "sem forma" } })
    montarRota(rotas, "/prefixos")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar/i }))

    expect(await screen.findByText(/não deu para falar com a API/)).toBeInTheDocument()
    expect(screen.queryByText(/resposta inesperada da API/)).not.toBeInTheDocument()
  })

  it("o 500 que traz o mapa de erros mostra o aviso e a mensagem do servidor", async () => {
    // O par do caso de cima, e o que impede a guarda de virar um `return`
    // incondicional: ela suprime o `_corpo` do lerRecusa, que so existe quando
    // o corpo nao tem o mapa de erros. Com a recusa de verdade no corpo, o
    // aviso e a mensagem do servidor saem os dois, e engolir a mensagem
    // deixaria o operador sem saber o que corrigir
    mockFetch({
      ...BASE,
      "PUT /api/blocos": {
        status: 500,
        corpo: { erros: { blocos_v4: "linha 1: community fora da faixa numerica" }, avisos: [] },
      },
    })
    montarRota(rotas, "/prefixos")
    await screen.findByLabelText(/IPv4/)
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    await waitFor(() =>
      expect(document.querySelector('[data-campo="blocos_v4"]')).toHaveTextContent("linha 1: community fora da faixa numerica"),
    )
  })

  it("a rede fora na consulta ao IRR avisa com tentar de novo", async () => {
    // A consulta ao bgpq4 e a operacao mais lenta da tela: sem o aviso, o
    // clique que nao chegou a sair era indistinguivel da consulta em andamento
    const mapa: Record<string, Resposta> = { ...BASE, "POST /api/blocos/irr": { rede: true } }
    mockFetch(mapa)
    montarRota(rotas, "/prefixos")
    await userEvent.click(await screen.findByRole("button", { name: /consultar IRR/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    mapa["POST /api/blocos/irr"] = { corpo: { v4: "45.169.232.0/22", v6: "" } }
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    await waitFor(() => expect(peticoes().filter((p) => p.caminho === "/api/blocos/irr")).toHaveLength(2))
    // e o texto que a consulta trouxe chegou na tela: o caminho de volta
    // termina onde o de ida terminaria
    await waitFor(() => expect(screen.getByLabelText(/IPv4/)).toHaveValue("45.169.232.0/22"))
  })

  it("a API fora do ar mostra a falha, e o tentar de novo traz o registro", async () => {
    // Sem o guarda a tela abre com os dois editores vazios, o painel dizendo que
    // esta gerando uma previa que nao vem, e os botoes do IRR levando a um
    // rascunho que o salvar nao aceita
    const mapa: Record<string, Resposta> = { ...BASE, "GET /api/blocos": { status: 500, corpo: { detail: "falhou" } } }
    mockFetch(mapa)
    montarRota(rotas, "/prefixos")
    // a tela de falha so aparece depois de a consulta gastar o retry do cliente
    // (um, com o atraso padrao de 1s), que e o mesmo do app
    expect(await screen.findByText("não deu para falar com a API", {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /^salvar$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /consultar IRR/i })).not.toBeInTheDocument()
    // a API volta: o tentar de novo e o unico caminho de volta, e sem ele a tela
    // ficaria presa na falha ate um F5
    mapa["GET /api/blocos"] = BASE["GET /api/blocos"]
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    expect(await screen.findByLabelText(/IPv4/)).toHaveValue("38.252.64.0/22  64512:613")
    expect(peticoes().filter((p) => pedidos(p) === "GET /api/blocos").length).toBeGreaterThan(2)
  })

  it("o tentar de novo desabilita enquanto o pedido corre", async () => {
    // O defeito que este caso mede: no clique o TanStack zera o `error` de uma
    // consulta sem dado quando ela e refeita, entao sem o `retentando` a tela
    // pisca o formulario vazio enquanto o retry corre, e o botao aqui medido
    // nem existe nessa janela. Nao ha clique duplo a evitar: o primeiro clique
    // ja tira o botao da tela
    mockFetch({ ...BASE, "GET /api/blocos": { status: 500, corpo: { erros: { _: "boom" }, avisos: [] } } })
    montarRota(rotas, "/prefixos")
    const alvo = () => screen.getByRole("button", { name: /tentar de novo/i })
    // O botao so existe depois de o cliente gastar o retry dele (um, com o
    // atraso padrao de 1s), entao a espera precisa de prazo maior que o padrao
    // do `waitFor`, que e de 1s e cairia em cima do retry. Pelo `findBy*` o
    // prazo vale igual, mas no TERCEIRO argumento: a assinatura ja vem ligada
    // ao container, entao sao (role, opcoes, opcoes do waitFor), e um quarto
    // argumento e ignorado (medido: 3004ms contra 1002ms)
    await waitFor(() => expect(alvo()).toBeInTheDocument(), { timeout: 3000 })
    // A leitura presa e a do retry, e nao a da montagem: presa antes do
    // `montarRota`, a primeira seria a presa, a falha nunca chegaria, e sem
    // falha nao ha botao - o caso mediria outra coisa
    const soltar = segurarLeitura("GET /api/blocos")
    await userEvent.click(alvo())
    expect(alvo()).toBeDisabled()
    soltar()
  })

  it("avisa que ha alteracao nao salva ao sair", async () => {
    // a tela que reescreve o registro de originacao inteiro era a unica das
    // quatro sem o guarda: sair com texto digitado perdia o texto em silencio
    mockFetch(BASE)
    montarRota(comSaida, "/prefixos")
    fireEvent.change(await screen.findByLabelText(/IPv4/), { target: { value: "45.169.232.0/22  64512:613" } })
    await userEvent.click(screen.getByText("sair"))
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Sair sem salvar?")
  })

  it("sai sem perguntar quando nao ha o que salvar", async () => {
    mockFetch(BASE)
    montarRota(comSaida, "/prefixos")
    // o registro chega antes de o operador sair: e a saida sem nada digitado que
    // este caso mede, e nao a janela do carregando
    await waitFor(() => expect(screen.getByLabelText(/IPv4/)).toHaveValue("38.252.64.0/22  64512:613"))
    await userEvent.click(screen.getByText("sair"))
    expect(await screen.findByText("outra tela")).toBeInTheDocument()
  })

  it("o cabecalho conta as linhas quando o operador mexe no texto", async () => {
    // a fixture tem o out/ atras do bloco, e sem o sujo o cabecalho diz que o
    // arquivo esta desatualizado para quem acabou de digitar, que e o
    // diagnostico errado: o arquivo esta atras do cadastro, e nao da digitacao
    mockFetch({
      ...BASE,
      "POST /api/blocos/previa": {
        corpo: {
          erros: {}, avisos: [],
          bloco: "xpl ip-prefix-list PL-ORIGEM-V4\nend-list",
          arquivo: "blocos.txt", salvo: "xpl ip-prefix-list PL-ORIGEM-V4-VELHO\nend-list",
        },
      },
    })
    montarRota(rotas, "/prefixos")
    expect(await screen.findByText(/o arquivo em out\/ está desatualizado/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/IPv4/), { target: { value: "45.169.232.0/22  64512:613" } })
    expect(await screen.findByText(/1 linha incluída, 1 removida/)).toBeInTheDocument()
  })
})
