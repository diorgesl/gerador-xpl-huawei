import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { mockFetch, montarRota, peticoes } from "@/teste/roteador"
import { Casca } from "@/app/casca"
import { PeerTela } from "./PeerTela"

const PLANO = {
  rede: { asn: "64512", politica: "65532" },
  padroes: {
    tipos: { cliente: { lp_base: 300, route_limit: 50, timer_keepalive: null, timer_hold: null } },
    origem_tipo: { cliente: 1100 }, origem_classe: { transito: 1100 },
    downstream: ["cliente", "parceiro"], origens_por_tipo: {}, origem_nome: {},
  },
  tipos: ["cliente"], tipos_com_criar_lista: ["cliente"], classes_cliente: [],
  lp_base: {}, route_limit: {}, route_limit_exemplo: {}, prepend_max: 6, prepend_implementado: 3,
  pop_min: 2001, pop_max: 2999, aprendizado_min: 3000, aprendizado_max: 3999,
  pop_usados: [], aprendizado_usados: [], campos_por_tipo: {}, campos_por_tipo_grupo: {},
}

const FORMULARIO = {
  id: "7", apelido: "", nome: "Cliente ACME", tipo: "cliente", grupo_id: "",
  asn: "268127", descricao: "", classe: "transito", lp_base: "300", origem: "1100",
  pop: "2001", aprendizado: "", ix_id: "", route_limit: "50", prepend_base: "0",
  timer_keepalive: "", timer_hold: "", bfd: true, graceful_restart: true,
  default_route: false, bh_upstream: "", prefixos_v4: ["45.169.232.0/22"], prefixos_v6: [],
  te_prefixos_v4: [], te_prefixos_v6: [], ap_block: [], ap_te: [], ap_allowed: [],
  ap_prefer: [], communities: [], large_communities: [],
  sessao_v4_local: "198.51.100.1", sessao_v4_remoto: "198.51.100.2",
  sessao_v6_local: "", sessao_v6_remoto: "",
}

const BASE = {
  "GET /api/plano": { corpo: PLANO },
  "GET /api/peers": { corpo: [{ id: 7, token: "268127", tipo: "cliente", asn: 268127, apelido: "", nome: "Cliente ACME", grupo_id: null }] },
  "GET /api/grupos": { corpo: [] },
  "GET /api/peers/7": { corpo: { id: 7, token: "268127", formulario: FORMULARIO } },
  "POST /api/peers/previa": {
    corpo: {
      erros: {}, avisos: [], criar_lista: null,
      bloco: "xpl route-filter CUST-268127-IMPORT-V4\nend-filter",
      arquivo: "268127-cliente.txt", salvo: null,
    },
  },
  "GET /api/peers/7/saida": { corpo: { bloco: "salvo", remover: "remover", criar_lista: null, arquivo: "268127-cliente.txt" } },
}

const rotas = [
  { path: "/peers", element: <div>lista de peers</div> },
  { path: "/peers/novo", element: <PeerTela /> },
  { path: "/peers/:id", element: <PeerTela /> },
]

// A limpeza do `unstubAllGlobals` e o resto do que cada caso deixa para tras sao
// do arnes, que os registra uma vez por arquivo (web/src/teste/roteador.tsx)

describe("a tela do peer", () => {
  it("abre com o token e o ASN no cabecalho", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    expect(await screen.findByText("268127")).toBeInTheDocument()
    expect(screen.getByText(/AS268127/)).toBeInTheDocument()
  })

  it("mostra a previa ao vivo, e o cabecalho diz que o arquivo e novo", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    expect(await screen.findByText(/CUST-268127-IMPORT-V4/)).toBeInTheDocument()
    expect(screen.getByText(/arquivo novo/)).toBeInTheDocument()
  })

  it("avisa que e copia e de onde ela veio", async () => {
    mockFetch({ ...BASE, "GET /api/peers/7/copia": { corpo: { id: 8, token: "268127", formulario: { ...FORMULARIO, id: "8" } } } })
    montarRota(rotas, "/peers/novo?de=7")
    expect(await screen.findByText(/cópia de 268127/)).toBeInTheDocument()
  })

  it("mostra os erros do salvar recusado", async () => {
    mockFetch({ ...BASE, "PUT /api/peers/7": { status: 422, corpo: { erros: { asn: "ASN ja usado pelo peer BRDIGITAL-20G" }, avisos: [] } } })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    // a mensagem aparece duas vezes de proposito: no resumo do topo, que leva
    // ao campo, e embaixo do campo. Por isso a busca e por papel, e nao por
    // texto, que acharia as duas
    expect(await screen.findByRole("button", { name: "ASN ja usado pelo peer BRDIGITAL-20G" })).toBeInTheDocument()
    expect(document.querySelector('[data-campo="asn"]')).toHaveTextContent("ASN ja usado pelo peer BRDIGITAL-20G")
  })

  it("o excluir pede confirmacao com o token no texto", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    expect(await screen.findByRole("dialog")).toHaveTextContent("268127")
  })

  it("duplicar leva para o peer novo preenchido com a copia", async () => {
    // A copia leva valores que a origem nao tem: o token e o mesmo dos dois
    // lados, entao so o token nao diz de qual registro a tela leu. Com o ASN e o
    // nome diferentes, quem abrisse o registro errado (o 7, e nao o /copia do
    // 7) ou nao aplicasse o reset do formulario reprova aqui
    mockFetch({
      ...BASE,
      "GET /api/peers/7/copia": {
        corpo: { id: 8, token: "268127", formulario: { ...FORMULARIO, id: "8", asn: "268999", nome: "Cliente COPIADO" } },
      },
    })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /duplicar/i }))
    expect(await screen.findByText(/cópia de 268127/)).toBeInTheDocument()
    expect(screen.getByLabelText("ASN")).toHaveValue("268999")
    expect(screen.getByLabelText("Nome")).toHaveValue("Cliente COPIADO")
    expect(peticoes().map((p) => `${p.metodo} ${p.caminho}`)).toContain("GET /api/peers/7/copia")
  })

  it("a recusa do salvar sai quando a previa responde de novo", async () => {
    // a recusa vale ate a proxima previa responder: a edicao rearma o atraso de
    // 400ms, a previa volta com a lista dela (vazia na fixture) e a mensagem do
    // salvar some junto
    mockFetch({ ...BASE, "PUT /api/peers/7": { status: 422, corpo: { erros: { asn: "ASN ja usado pelo peer BRDIGITAL-20G" }, avisos: [] } } })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByRole("button", { name: "ASN ja usado pelo peer BRDIGITAL-20G" })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText("Nome"), " 2")
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "ASN ja usado pelo peer BRDIGITAL-20G" })).not.toBeInTheDocument(),
    )
  })

  it("o campo de lista abre com o que o registro tem", async () => {
    // o rascunho do AreaTexto comeca vazio e quem o enche e o reset do registro
    // lido: sem este teste, um campo que so mostrasse o rascunho abriria em
    // branco num peer que tem prefixos
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    expect(await screen.findByLabelText(/^IPv4 \(1\)/)).toHaveValue("45.169.232.0/22")
  })

  it("o salvar bem-sucedido nao desfaz o que foi gravado", async () => {
    // o efeito do registro lido tem o sujo por ref, e nao por dependencia: com
    // ele na lista, o salvamento (que zera o isDirty) reaplicaria o registro da
    // montagem, e a tela voltaria ao valor de antes do salvar. Um salvamento
    // seguinte gravaria os valores revertidos
    const salvo = { ...FORMULARIO, prefixos_v4: ["45.169.232.0/22", "45.169.236.0/23"] }
    mockFetch({
      ...BASE,
      "PUT /api/peers/7": { corpo: { registro: { id: 7, token: "268127", formulario: salvo }, arquivo: "268127-cliente.txt", avisos: [] } },
    })
    montarRota(rotas, "/peers/7")
    const campo = await screen.findByLabelText(/^IPv4 \(/)
    await userEvent.clear(campo)
    await userEvent.type(campo, "45.169.232.0/22{enter}45.169.236.0/23")
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    await waitFor(() =>
      expect(screen.getByLabelText(/^IPv4 \(2\)/)).toHaveValue("45.169.232.0/22\n45.169.236.0/23"),
    )
    // e o corpo do PUT e o que a tela mandou de verdade, que e o trabalho dela:
    // o arnes le metodo, caminho, query e corpo, e ate aqui nada neste ramo
    // conferia o que sai numa escrita
    const put = peticoes().find((p) => p.metodo === "PUT")
    expect(put?.caminho).toBe("/api/peers/7")
    expect(put?.corpo).toMatchObject({ prefixos_v4: ["45.169.232.0/22", "45.169.236.0/23"] })
  })

  it("o excluir sai sem perguntar sobre alteracao nao salva", async () => {
    // o excluir navega por conta propria, e a essa altura o registro ja nao
    // existe: com o bloqueio valendo, o operador veria o aviso de "sair sem
    // salvar?" sobre um registro excluido, e a unica saida seria confirma-lo
    mockFetch({ ...BASE, "DELETE /api/peers/7": { status: 204, corpo: null } })
    montarRota(rotas, "/peers/7")
    await userEvent.type(await screen.findByLabelText("ASN"), "9")
    await userEvent.click(screen.getByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    await userEvent.click(await screen.findByRole("button", { name: /^excluir$/i }))
    expect(await screen.findByText("lista de peers")).toBeInTheDocument()
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })

  it("a saida que o operador pede continua perguntando", async () => {
    // O guarda existe para a navegacao que o OPERADOR pede. Sem esta prova, um
    // `permitir` sempre verdadeiro deixaria a suite verde, e a alteracao nao
    // salva se perderia sem aviso. Aqui a navegacao vem de um link da barra
    // lateral, que e o caminho de verdade
    mockFetch({
      ...BASE,
      "GET /api/peers": {
        corpo: [
          { id: 7, token: "268127", tipo: "cliente", asn: 268127, apelido: "", nome: "Cliente ACME", grupo_id: null },
          { id: 9, token: "268128", tipo: "cliente", asn: 268128, apelido: "", nome: "Cliente OUTRO", grupo_id: null },
        ],
      },
    })
    montarRota(
      [
        {
          path: "/",
          element: <Casca />,
          children: [
            { path: "peers", element: <div>lista de peers</div> },
            { path: "peers/:id", element: <PeerTela /> },
          ],
        },
      ],
      "/peers/7",
    )
    await userEvent.type(await screen.findByLabelText("ASN"), "9")
    const outro = (await screen.findAllByRole("link")).find((l) => l.getAttribute("href") === "/peers/9")
    await userEvent.click(outro as HTMLElement)
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Sair sem salvar?")
  })

  it("o 404 que volta para o mesmo caminho nao desliga o guarda", async () => {
    // O salvamento que toma 404 manda para /peers, que e a MESMA rota da tela
    // aberta: com a marca presa, o guarda ficaria desligado pelo resto da vida
    // da tela, e a proxima saida do operador levaria a alteracao nao salva em
    // silencio. A marca tem que sair limpa daqui, e quem diz que houve
    // navegacao e a chave da localizacao, nao o caminho
    mockFetch({
      ...BASE,
      "GET /api/peers": {
        corpo: [
          { id: 7, token: "268127", tipo: "cliente", asn: 268127, apelido: "", nome: "Cliente ACME", grupo_id: null },
          { id: 9, token: "268128", tipo: "cliente", asn: 268128, apelido: "", nome: "Cliente OUTRO", grupo_id: null },
        ],
      },
      "GET /api/peers/novo": { corpo: { id: 0, token: "novo", formulario: FORMULARIO } },
      "POST /api/peers": { status: 404, corpo: {} },
    })
    montarRota(
      [
        {
          path: "/",
          element: <Casca />,
          children: [
            { path: "peers", element: <PeerTela /> },
            { path: "peers/:id", element: <PeerTela /> },
          ],
        },
      ],
      "/peers",
    )
    await userEvent.type(await screen.findByLabelText("ASN"), "9")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    // a tela avisa e volta para /peers, o mesmo caminho de onde ela esta
    expect(await screen.findByText("registro não encontrado")).toBeInTheDocument()
    const outro = (await screen.findAllByRole("link")).find((l) => l.getAttribute("href") === "/peers/9")
    await userEvent.click(outro as HTMLElement)
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Sair sem salvar?")
  })

  it("o duplicar da paleta pergunta como o do cabecalho", async () => {
    // o comando e o mesmo nos dois lugares, e a copia vem do registro SALVO:
    // a alteracao nao salva se perde de qualquer jeito, entao a paleta nao pode
    // ser a porta por onde ela sai sem aviso
    mockFetch(BASE)
    montarRota(
      [
        {
          path: "/",
          element: <Casca />,
          children: [
            { path: "peers", element: <div>lista de peers</div> },
            { path: "peers/:id", element: <PeerTela /> },
            { path: "peers/novo", element: <PeerTela /> },
          ],
        },
      ],
      "/peers/7",
    )
    await userEvent.type(await screen.findByLabelText("ASN"), "9")
    await userEvent.keyboard("{Control>}k{/Control}")
    await userEvent.click(await screen.findByText("duplicar o registro aberto"))
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Sair sem salvar?")
  })

  it("a paleta nao oferece copiar o bloco quando a previa esta em erro", async () => {
    // com erro de validacao a previa chega sem bloco, e o item que copiaria o
    // vazio aparecia e nao fazia nada: a paleta oferece so o que a tela sabe
    // fazer agora
    mockFetch({
      ...BASE,
      "POST /api/peers/previa": {
        corpo: { erros: { asn: "ASN ja usado pelo peer BRDIGITAL-20G" }, avisos: [], criar_lista: null, bloco: null, arquivo: null, salvo: null },
      },
    })
    montarRota(
      [
        {
          path: "/",
          element: <Casca />,
          children: [
            { path: "peers", element: <div>lista de peers</div> },
            { path: "peers/:id", element: <PeerTela /> },
          ],
        },
      ],
      "/peers/7",
    )
    // a previa em erro e o estado do qual este caso fala
    await screen.findByRole("button", { name: "ASN ja usado pelo peer BRDIGITAL-20G" })
    await userEvent.keyboard("{Control>}k{/Control}")
    expect(await screen.findByText("duplicar o registro aberto")).toBeInTheDocument()
    expect(screen.queryByText("copiar o bloco aberto")).not.toBeInTheDocument()
  })

  it("o salvar atualiza a aba de remocao", async () => {
    // a remocao vem de GET /saida, e nao da previa: sem invalidar depois do
    // salvar, a aba continuaria com o bloco de antes, e o copiar dela levaria
    // para o equipamento um bloco que nao vale mais
    const mapa = {
      ...BASE,
      "PUT /api/peers/7": { corpo: { registro: { id: 7, token: "268127", formulario: FORMULARIO }, arquivo: "268127-cliente.txt", avisos: [] } },
      "GET /api/peers/7/saida": { corpo: { bloco: "salvo", remover: "undo REM-ANTIGO", criar_lista: null, arquivo: "268127-cliente.txt" } },
    }
    mockFetch(mapa)
    montarRota(rotas, "/peers/7")
    await screen.findByRole("tab", { name: /remoção/i })
    mapa["GET /api/peers/7/saida"].corpo.remover = "undo REM-NOVO"
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    await userEvent.click(await screen.findByRole("tab", { name: /remoção/i }))
    expect(await screen.findByText(/REM-NOVO/)).toBeInTheDocument()
  })

  it("o salvar que muda o id leva a url junto", async () => {
    // o id do formulario move o registro no servidor: com a url parada no id
    // velho, o salvamento seguinte bate no 404 de um registro que existe
    mockFetch({
      ...BASE,
      "PUT /api/peers/7": { corpo: { registro: { id: 8, token: "268127", formulario: FORMULARIO }, arquivo: "268127-cliente.txt", avisos: [] } },
      "GET /api/peers/8": { corpo: { id: 8, token: "268127", formulario: { ...FORMULARIO, id: "8" } } },
      "GET /api/peers/8/saida": { corpo: { bloco: "salvo", remover: null, criar_lista: null, arquivo: "268127-cliente.txt" } },
    })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    // a releitura no id novo e quem prova que a url andou: o campo ID passa a
    // mostrar o do registro lido em /peers/8, e nao o do corpo do PUT
    await waitFor(() => expect(screen.getByLabelText("ID")).toHaveValue("8"))
    expect(peticoes().map((p) => `${p.metodo} ${p.caminho}`)).toContain("GET /api/peers/8")
    // e a previa seguinte ja pergunta pelo id novo, na query: e o outro pedaco
    // que o arnes expoe, e o que diz que o id saiu da URL, e nao do corpo. A
    // espera e a janela de 400ms, que rearma quando o registro lido chega
    await waitFor(() =>
      expect(peticoes().some((p) => p.caminho === "/api/peers/previa" && p.query === "id=8")).toBe(true),
    )
  })

  it("a consulta ao IRR escreve os prefixos no formulario", async () => {
    // e o caminho em que o formulario muda por baixo do campo de lista, que e
    // onde o rascunho do AreaTexto tem que dar lugar ao valor de fora
    mockFetch({ ...BASE, "POST /api/irr": { corpo: { v4: ["45.169.244.0/22"], v6: [] } } })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /consultar IRR/i }))
    // a ancora evita o "IPv4 local" das sessoes, que e outro campo
    await waitFor(() => expect(screen.getByLabelText(/^IPv4 \(/)).toHaveValue("45.169.244.0/22"))
  })
})
