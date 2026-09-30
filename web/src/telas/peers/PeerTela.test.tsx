import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { mockFetch, montarRota, peticoes, type Resposta } from "@/teste/roteador"
import { Casca } from "@/app/casca"
import { PeerTela, TelaDoPeer } from "./PeerTela"

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
  sugestoes: { communities: [], large_communities: [] },
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

// A paleta mora na casca, e nao na tela: quem mede a copia da paleta precisa da
// tela dentro dela. E o mesmo arranjo que os casos da paleta montam a mao
const cascaComPeer = [
  {
    path: "/",
    element: <Casca />,
    children: [
      { path: "peers", element: <div>lista de peers</div> },
      { path: "peers/:id", element: <PeerTela /> },
    ],
  },
]

// A limpeza do `unstubAllGlobals` e o resto do que cada caso deixa para tras sao
// do arnes, que os registra uma vez por arquivo (web/src/teste/roteador.tsx)

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

  it("uma chave de erro que nao e campo nao fecha o painel", async () => {
    // o painel pergunta se ha campo no erro para decidir se mostra o bloco;
    // com uma chave desconhecida ele fechava sem desenhar campo nenhum, e o
    // operador ficava sem o bloco e sem saber onde corrigir
    mockFetch({
      ...BASE,
      "PUT /api/peers/7": { status: 422, corpo: { erros: { campo_novo: "algo que so o backend conhece" }, avisos: [] } },
    })
    montarRota(rotas, "/peers/7")
    // a previa da montagem responde ANTES do clique: e ela que fecha a janela
    // da recusa, porque a lista dela substitui a do salvar. Clicar antes disso
    // mediria a corrida entre as duas, e nao o que o caso quer medir
    await screen.findByText(/CUST-268127-IMPORT-V4/)
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))

    expect(await screen.findByText("algo que so o backend conhece")).toBeInTheDocument()
    // sem `findBy`: a espera daria tempo de a proxima previa chegar e reabrir o
    // painel, e o caso passaria sem o painel ter deixado de fechar
    expect(screen.getByText(/CUST-268127-IMPORT-V4/)).toBeInTheDocument()
  })

  it("o excluir pede confirmacao com o token no texto", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    expect(await screen.findByRole("dialog")).toHaveTextContent("268127")
  })

  it("o cancelar do dialogo nao exclui nada", async () => {
    // O par do test_excluir_sem_confirmar_nao_apaga do test_app.py: excluir sem
    // confirmar nao apaga. A confirmacao saiu do servidor (a API nao pede mais o
    // `confirmado`) e virou dialogo, entao quem prova isso agora e o cancelar
    // nao mandar DELETE nenhum. Sem este caso, um refactor que disparasse o
    // excluir na abertura do dialogo apagaria o registro e o out/ dele
    mockFetch(BASE)
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    await screen.findByRole("dialog")

    await userEvent.click(screen.getByRole("button", { name: /cancelar/i }))

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(peticoes().some((p) => p.metodo === "DELETE")).toBe(false)
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

  it("a community escolhida na busca entra no que o salvar envia", async () => {
    // as duas pontas tem teste proprio (a lista, no AdicionarCommunity; o
    // campo, no caso do IPv4 acima), e o que este caso cobre e a ligacao: o
    // valor que a lista entrega tem que virar linha no textarea e sair no
    // corpo do PUT
    const comCatalogo = {
      ...PLANO,
      sugestoes: {
        communities: [{ valor: "64512:613", rotulo: "Prepend 2x para os nossos upstreams", grupo: "Prepend" }],
        large_communities: [],
      },
    }
    mockFetch({
      ...BASE,
      "GET /api/plano": { corpo: comCatalogo },
      "PUT /api/peers/7": {
        corpo: { registro: { id: 7, token: "268127", formulario: FORMULARIO }, arquivo: "268127-cliente.txt", avisos: [] },
      },
    })
    montarRota(rotas, "/peers/7")

    await userEvent.click(await screen.findByRole("button", { name: "adicionar communities" }))
    await userEvent.type(screen.getByPlaceholderText(/buscar/i), "prepend")
    await userEvent.click(await screen.findByRole("option", { name: /nossos upstreams/ }))
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))

    await waitFor(() => {
      const put = peticoes().find((p) => p.metodo === "PUT")
      expect(put?.corpo).toMatchObject({ communities: ["64512:613"] })
    })
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

  it("a paleta oferece copiar o bloco quando ele existe", async () => {
    // a direcao que MOSTRA, e nao so a que suprime: sem ela, um `aoCopiarBloco`
    // sempre indefinido passaria no arquivo inteiro
    mockFetch(BASE)
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
    // o bloco da previa chegou, que e o estado do qual este caso fala
    await screen.findByText(/CUST-268127-IMPORT-V4/)
    await userEvent.keyboard("{Control>}k{/Control}")
    expect(await screen.findByText("copiar o bloco aberto")).toBeInTheDocument()
  })

  it("a copia da paleta leva o bloco da aba aberta", async () => {
    // A janela em que o defeito aparece: a tela esta na aba de remocao, e a
    // copia da paleta levava o bloco da previa. O texto de cada aba e distinto
    // de proposito, para a assercao dizer QUAL foi copiado
    const escrever = vi.fn()
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText: escrever } })
    mockFetch({
      ...BASE,
      "GET /api/peers/7/saida": { corpo: { bloco: "salvo", remover: "undo peer 198.51.100.2", criar_lista: null, arquivo: "268127-cliente.txt" } },
    })
    montarRota(cascaComPeer, "/peers/7")
    await screen.findByText(/CUST-268127-IMPORT-V4/)
    await userEvent.click(screen.getByRole("tab", { name: /remoção/i }))

    await userEvent.keyboard("{Control>}k{/Control}")
    await userEvent.click(await screen.findByText("copiar o bloco aberto"))

    await waitFor(() => expect(escrever).toHaveBeenCalledWith("undo peer 198.51.100.2"))
  })

  it("a copia da paleta segue o painel quando a aba aberta sai da lista", async () => {
    // O quadro "ao criar" so existe enquanto a previa manda o `criar_lista`, e
    // trocar o tipo e o que o derruba. Com a aba aberta saindo da lista, o
    // painel cai na primeira: a tela tem que cair na mesma, senao a paleta
    // oferece a copia de um bloco que nao e o que esta na tela (ou nao oferece
    // nada, com um bloco na tela). O texto de cada aba e distinto para a
    // assercao dizer QUAL foi copiado
    const escrever = vi.fn()
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText: escrever } })
    const respostaDaPrevia = (criar: string | null) => ({
      corpo: {
        erros: {}, avisos: [], arquivo: "268127-cliente.txt", salvo: null,
        bloco: "xpl route-filter CUST-268127-IMPORT-V4\nend-filter",
        criar_lista: criar,
      },
    })
    const mapa: Record<string, Resposta> = {
      ...BASE,
      // o seletor de tipo so oferece o que o plano lista
      "GET /api/plano": { corpo: { ...PLANO, tipos: ["cliente", "upstream"] } },
      "POST /api/peers/previa": respostaDaPrevia("xpl community-list CL-PEER-7"),
    }
    mockFetch(mapa)
    montarRota(cascaComPeer, "/peers/7")
    await screen.findByText(/CUST-268127-IMPORT-V4/)
    await userEvent.click(screen.getByRole("tab", { name: /ao criar o peer/i }))
    expect(screen.getByText(/CL-PEER-7/)).toBeInTheDocument()

    // a previa seguinte ja nao traz o quadro "ao criar". O mapa troca antes do
    // clique no tipo, que e a alteracao que dispara a previa (400ms depois)
    mapa["POST /api/peers/previa"] = respostaDaPrevia(null)
    await userEvent.click(screen.getByLabelText("Tipo"))
    await userEvent.click(await screen.findByRole("option", { name: "upstream" }))

    // o estado do qual o caso fala: a aba aberta saiu, e o painel esta na
    // primeira, que tem bloco
    await waitFor(() => expect(screen.queryByRole("tab", { name: /ao criar o peer/i })).not.toBeInTheDocument())
    expect(screen.getByRole("tab", { name: /bloco do peer/i })).toHaveAttribute("aria-selected", "true")

    await userEvent.keyboard("{Control>}k{/Control}")
    await userEvent.click(await screen.findByText("copiar o bloco aberto"))

    await waitFor(() =>
      expect(escrever).toHaveBeenCalledWith("xpl route-filter CUST-268127-IMPORT-V4\nend-filter"),
    )
  })

  it("o duplicar do cabecalho pergunta com o formulario sujo", async () => {
    // o mesmo comando da paleta, e o operador tem que poder dizer nao nos dois:
    // as duas telas pinavam so o da paleta
    mockFetch({
      ...BASE,
      "GET /api/peers/7/copia": { corpo: { id: 8, token: "268127", formulario: { ...FORMULARIO, id: "8" } } },
    })
    montarRota(rotas, "/peers/7")
    await userEvent.type(await screen.findByLabelText("ASN"), "9")
    await userEvent.click(screen.getByRole("button", { name: /duplicar/i }))
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Sair sem salvar?")
  })

  it("o Ctrl+S nao salva antes de o registro chegar", async () => {
    // Na tela de falha o formulario nem esta montado, e o `aoSalvar` publicado
    // assim mesmo mandava um PUT com o formulario em branco: a API recusa um
    // nome vazio, e a recusa nao aparece aqui, porque so o formulario a mostra
    mockFetch({
      ...BASE,
      // a API fora do ar e o caso do achado: nada chega, nem o plano nem o
      // registro
      "GET /api/plano": { status: 500, corpo: {} },
      "GET /api/peers/7": { status: 500, corpo: {} },
      "PUT /api/peers/7": { corpo: { registro: { id: 7, token: "268127", formulario: FORMULARIO }, arquivo: "268127-cliente.txt", avisos: [] } },
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
    // a tela de falha so aparece depois de a consulta do plano gastar o retry
    // do cliente (um, com o atraso padrao de 1s), que e o mesmo do app
    await screen.findByText("não deu para falar com a API", {}, { timeout: 3000 })
    await userEvent.keyboard("{Control>}s{/Control}")
    // nada de escrita saiu: sem o registro, a tela nao tem o que salvar. A
    // assercao lista o que saiu, e nao so um booleano: e a lista que diz qual
    // pedido foi
    expect(peticoes().filter((p) => p.metodo !== "GET")).toEqual([])
  })

  it("trocar de registro recarrega o formulario, mesmo sujo", async () => {
    // A instancia do useForm sobrevive a troca de :id (o React Router reusa o
    // elemento), e o efeito de carga nao roda com o formulario sujo: sem a
    // chave por id, os campos ficam com os valores do registro ANTERIOR, e o
    // salvar grava eles no registro novo
    mockFetch({
      ...BASE,
      "GET /api/peers": {
        corpo: [
          { id: 7, token: "268127", tipo: "cliente", asn: 268127, apelido: "", nome: "Cliente ACME", grupo_id: null },
          { id: 9, token: "268128", tipo: "cliente", asn: 268128, apelido: "", nome: "Cliente OUTRO", grupo_id: null },
        ],
      },
      "GET /api/peers/9": { corpo: { id: 9, token: "268128", formulario: { ...FORMULARIO, id: "9", nome: "Cliente OUTRO" } } },
      "GET /api/peers/9/saida": { corpo: { bloco: "salvo", remover: null, criar_lista: null, arquivo: "268128-cliente.txt" } },
    })
    montarRota(
      [
        {
          path: "/",
          element: <Casca />,
          children: [
            { path: "peers", element: <div>lista de peers</div> },
            // a rota usa o TelaDoPeer, que e o que a casca usa: e a chave dele
            // que remonta a tela na troca de registro
            { path: "peers/:id", element: <TelaDoPeer /> },
          ],
        },
      ],
      "/peers/7",
    )
    await userEvent.type(await screen.findByLabelText("ASN"), "9")
    const outro = (await screen.findAllByRole("link")).find((l) => l.getAttribute("href") === "/peers/9")
    await userEvent.click(outro as HTMLElement)
    await userEvent.click(await screen.findByRole("button", { name: /sair sem salvar/i }))
    // os campos mostram o registro novo, e nao o que estava sendo editado
    await waitFor(() => expect(screen.getByLabelText("Nome")).toHaveValue("Cliente OUTRO"))
  })

  it("o salvar do cabecalho espera o registro chegar", async () => {
    // a janela entre a montagem e a leitura do registro e a unica em que o
    // cabecalho existe sem o formulario: sem a guarda, o botao mandava o
    // formulario em branco, e a recusa da API pintava um formulario que o
    // operador nunca tocou
    mockFetch(BASE)
    const soltar = segurarLeitura("GET /api/peers/7")
    montarRota(rotas, "/peers/7")
    const salvar = await screen.findByRole("button", { name: /^salvar$/i })
    await waitFor(() => expect(salvar).toBeDisabled())
    await userEvent.click(salvar)
    expect(peticoes().filter((p) => p.metodo !== "GET")).toEqual([])
    // e a direcao que mostra: com o registro na mao, o botao volta
    soltar()
    await waitFor(() => expect(screen.getByRole("button", { name: /^salvar$/i })).toBeEnabled())
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
    // espera e a janela de 400ms, que rearma quando o registro lido chega.
    //
    // O pedaco e comparado solto, e nao a query inteira: o ?asn= do tenant
    // viaja na mesma string, e a prova do id nao pode depender do lugar dele
    await waitFor(() =>
      expect(
        peticoes().some((p) => p.caminho === "/api/peers/previa" && p.query.split("&").includes("id=8")),
      ).toBe(true),
    )
  })

  it("a rede fora no salvar avisa com tentar de novo, e o formulario nao perde nada", async () => {
    // O openapi-fetch RE-LANCA a excecao de rede em vez de devolver `{error}`:
    // sem ninguem apanhando a excecao, o clique em salvar nao deixava rastro
    // nenhum na tela (nem toast, nem alerta) e a promessa rejeitada subia
    // solta. A tabela de Erros da spec nomeia o caso: "500 ou rede fora: toast
    // com tentar de novo, o formulario nao perde nada"
    const mapa: Record<string, Resposta> = { ...BASE, "PUT /api/peers/7": { rede: true } }
    mockFetch(mapa)
    montarRota(rotas, "/peers/7")
    const nome = await screen.findByLabelText("Nome")
    await userEvent.clear(nome)
    await userEvent.type(nome, "Cliente NOVO")
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    expect(screen.getByLabelText("Nome")).toHaveValue("Cliente NOVO")
    // a API volta: o "tentar de novo" repete a escrita, e e ela que confirma
    // que o aviso carrega um caminho de volta, e nao so a frase
    mapa["PUT /api/peers/7"] = {
      corpo: { registro: { id: 7, token: "268127", formulario: FORMULARIO }, arquivo: "268127-cliente.txt", avisos: [] },
    }
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    await waitFor(() => expect(peticoes().filter((p) => p.metodo === "PUT")).toHaveLength(2))
    // o toast diz a pasta de verdade do arquivo, e nao so o nome dele: e por
    // ele que o operador acha o bloco que acabou de gravar
    expect(await screen.findByText(/gravado em out\/64512\/268127-cliente.txt/)).toBeInTheDocument()
  })

  it("o 500 no salvar avisa com tentar de novo, sem pintar campo nenhum", async () => {
    // A tabela de Erros da spec poe 500 e rede fora no mesmo caminho. O 500 sem
    // corpo de recusa nao diz nada sobre campo nenhum, entao o que sobra e o
    // aviso: o `_corpo` do lerRecusa seria "resposta inesperada da API" embaixo
    // de um resumo que nao leva a lugar nenhum
    mockFetch({ ...BASE, "PUT /api/peers/7": { status: 500, corpo: { detail: "falhou" } } })
    montarRota(rotas, "/peers/7")
    await screen.findByText(/CUST-268127-IMPORT-V4/)
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByRole("button", { name: /tentar de novo/i })).toBeInTheDocument()
    expect(screen.queryByText(/resposta inesperada da API/)).not.toBeInTheDocument()
    expect(screen.queryByText(/impede o salvar/)).not.toBeInTheDocument()
    // o bloco da previa continua onde estava: um 5xx nao contesta o formulario
    expect(screen.getByText(/CUST-268127-IMPORT-V4/)).toBeInTheDocument()
  })

  it("o 500 que traz a mensagem do servidor mostra as duas coisas", async () => {
    // O 500 do app nomeia o problema de verdade (o peers.yaml editado a mao,
    // com arquivo e linha), e essa mensagem nao pode se perder atras do aviso:
    // o aviso diz o que fazer agora, e a mensagem diz o que corrigir
    mockFetch({ ...BASE, "PUT /api/peers/7": { status: 500, corpo: { erros: { _: "peers.yaml: linha 12: ASN de 32 bits sem namespace" }, avisos: [] } } })
    montarRota(rotas, "/peers/7")
    await screen.findByText(/CUST-268127-IMPORT-V4/)
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByRole("button", { name: /tentar de novo/i })).toBeInTheDocument()
    expect(screen.getByText(/linha 12: ASN de 32 bits sem namespace/)).toBeInTheDocument()
  })

  it("a rede fora no salvar e copiar nao culpa a copia", async () => {
    // A excecao do salvar subia ate o painel, que a apanhava e dizia "nada foi
    // copiado: a operacao nao terminou": o operador lia isso como problema da
    // copia, e nao como a gravacao que nao chegou. O recado certo e o da
    // gravacao, com o caminho de volta
    mockFetch({ ...BASE, "PUT /api/peers/7": { rede: true } })
    montarRota(rotas, "/peers/7")
    await screen.findByText(/CUST-268127-IMPORT-V4/)
    await userEvent.click(screen.getByRole("button", { name: /salvar e copiar/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    expect(screen.queryByText(/nada foi copiado/)).not.toBeInTheDocument()
  })

  it("a rede fora no excluir avisa, e o dialogo fica aberto", async () => {
    // Sem o aviso o dialogo ficava aberto, mudo, com o operador clicando: a
    // excecao do DELETE subia solta, e nem o lerRecusa nem o toast rodavam
    mockFetch({ ...BASE, "DELETE /api/peers/7": { rede: true } })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    await userEvent.click(await screen.findByRole("button", { name: /^excluir$/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    // e o peer continua na tela: a exclusao que nao chegou nao pode navegar. A
    // espera e do bloco, e nao uma leitura direta: os cliques do dialogo correm
    // na frente da janela de 400ms da previa, e o bloco chega depois deles
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(await screen.findByText(/CUST-268127-IMPORT-V4/)).toBeInTheDocument()
  })

  it("a rede fora na consulta ao IRR avisa, e o tentar de novo repete o pedido", async () => {
    // A consulta nao e gravacao, mas o clique sem resposta e o mesmo buraco: o
    // bgpq4 leva segundos, e o operador nao tem como saber que nem saiu
    const mapa: Record<string, Resposta> = { ...BASE, "POST /api/irr": { rede: true } }
    mockFetch(mapa)
    montarRota(rotas, "/peers/7")
    // o "ignorando o cache" existe para dizer que o `forcar` do pedido original
    // e o que o "tentar de novo" repete, e nao o default do botao
    await userEvent.click(await screen.findByRole("button", { name: /consultar ignorando o cache/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    mapa["POST /api/irr"] = { corpo: { v4: [], v6: [] } }
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    await waitFor(() => expect(peticoes().filter((p) => p.caminho === "/api/irr")).toHaveLength(2))
    expect(peticoes().filter((p) => p.caminho === "/api/irr").map((p) => p.corpo)).toEqual([
      expect.objectContaining({ forcar: true }),
      expect.objectContaining({ forcar: true }),
    ])
  })

  it("a consulta ao IRR manda as linhas da tela e devolve as mescladas", async () => {
    // O tratamento escrito a mao so sobrevive a reconsulta se o pedido levar o
    // que esta no campo: sem isso o servidor mescla contra nada e a lista volta
    // como o IRR respondeu, apagando o trabalho
    mockFetch({
      ...BASE,
      "POST /api/irr": {
        corpo: {
          v4: ["45.169.232.0/22",
               "45.169.240.0/24 64512:211  !- nao veio na consulta ao IRR"],
          v6: [],
        },
      },
    })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /^consultar IRR$/i }))
    await waitFor(() => {
      const pedido = peticoes().find((p) => p.caminho === "/api/irr")
      expect(pedido?.corpo).toMatchObject({ v4: ["45.169.232.0/22"] })
    })
    expect(await screen.findByDisplayValue(/45\.169\.240\.0\/24/)).toBeInTheDocument()
  })

  it("a consulta ao IRR que falha nao apaga o bloco do painel", async () => {
    // O erro do bgpq4 nao e de campo nenhum, e contar o mapa inteiro apagava o
    // painel ("a previa volta quando os erros forem corrigidos") sem nenhum
    // campo para corrigir: o operador perdia o bloco por causa de uma consulta
    // que nao contesta o formulario
    mockFetch({
      ...BASE,
      "POST /api/irr": { status: 502, corpo: { erros: { bgpq4: "bgpq4 falhou: sem resposta do RADB" }, avisos: [] } },
    })
    montarRota(rotas, "/peers/7")
    // a previa chega primeiro: e ela que traz o bloco, e a recusa do IRR vale
    // ate a proxima previa responder - clicar antes disso mediria a corrida
    // entre as duas, e nao o que o caso quer medir
    await screen.findByText(/CUST-268127-IMPORT-V4/)
    await userEvent.click(screen.getByRole("button", { name: /^consultar IRR$/i }))
    // o recado sai na secao de prefixos, ao lado dos botoes do IRR, que e onde
    // o operador vai procurar o resultado da consulta
    const secao = document.querySelector("#secao-prefixos") as HTMLElement
    await waitFor(() =>
      expect(within(secao).getByText("bgpq4 falhou: sem resposta do RADB")).toBeInTheDocument(),
    )
    expect(screen.getByText(/CUST-268127-IMPORT-V4/)).toBeInTheDocument()
    expect(screen.queryByText(/a prévia volta quando os erros forem corrigidos/)).not.toBeInTheDocument()
    // e o 502 e um 5xx como outro qualquer: o caminho de volta entra junto
    expect(screen.getByRole("button", { name: /tentar de novo/i })).toBeInTheDocument()
  })

  it("a previa que falhou diz que nao deu, em vez de gerar para sempre", async () => {
    // So a tela dos prefixos olhava o isError da previa: aqui o painel ficava
    // em "gerando previa..." para sempre, e o operador esperava por um bloco
    // que nao vem. O retry do cliente gasta a janela antes de desistir, e o
    // mesmo relogio das outras telas
    mockFetch({ ...BASE, "POST /api/peers/previa": { status: 500, corpo: { detail: "falhou" } } })
    montarRota(rotas, "/peers/7")
    expect(await screen.findByText(/a prévia volta quando os erros forem corrigidos/, {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.queryByText(/gerando prévia/)).not.toBeInTheDocument()
  })

  it("/peers/abc e registro que nao existe, e nao falha de rede", async () => {
    // O Number("abc") vira NaN, o GET /api/peers/NaN responde 422, e o inicial.ts
    // so trata o 404: o operador caia na tela de falha de rede, cujo "tentar de
    // novo" nunca ia funcionar. Nao e uma consulta que falhou, e um endereco
    // que nao aponta para registro nenhum
    mockFetch({
      ...BASE,
      // o caminho com que o pedido sai quando o ident vira NaN, e o que a API
      // responde nele: e a medida do vermelho, e nao o que a tela pede agora
      "GET /api/peers/NaN": { status: 422, corpo: { erros: { _corpo: "path.ident: Input should be a valid integer" }, avisos: [] } },
    })
    montarRota(rotas, "/peers/abc")
    expect(await screen.findByText(/Registro não encontrado/)).toBeInTheDocument()
    expect(screen.queryByText("não deu para falar com a API")).not.toBeInTheDocument()
    // e nem gasta um pedido para um id que nao e id: a leitura nem sai
    expect(peticoes().some((p) => p.caminho.startsWith("/api/peers/"))).toBe(false)
  })

  it("o id da URL vence o de da query", async () => {
    // Com os dois na mao o `de` vencia: o cabecalho dizia "copia de 3", o
    // formulario trazia os valores do 3, e o salvar fazia PUT /api/peers/7 com
    // o id 8 do corpo, que a API le como troca de identidade - o peer 7 se
    // perderia. Nao e alcancavel pela interface, e a regra e a simples: o `de`
    // so vale quando nao ha id
    mockFetch({
      ...BASE,
      "GET /api/peers/3/copia": {
        corpo: { id: 8, token: "268127", formulario: { ...FORMULARIO, id: "8", nome: "Cliente COPIADO" } },
      },
      "PUT /api/peers/7": {
        corpo: { registro: { id: 7, token: "268127", formulario: FORMULARIO }, arquivo: "268127-cliente.txt", avisos: [] },
      },
    })
    montarRota(rotas, "/peers/7?de=3")
    expect(await screen.findByLabelText("Nome")).toHaveValue("Cliente ACME")
    expect(screen.queryByText(/cópia de/)).not.toBeInTheDocument()
    expect(peticoes().map((p) => `${p.metodo} ${p.caminho}`)).toContain("GET /api/peers/7")
    // e o corpo do salvar carrega a identidade do registro aberto, e nao a da
    // copia que a query pedia
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    await waitFor(() => expect(peticoes().some((p) => p.metodo === "PUT")).toBe(true))
    const put = peticoes().find((p) => p.metodo === "PUT")
    expect(put?.caminho).toBe("/api/peers/7")
    expect(put?.corpo).toMatchObject({ id: "7" })
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

  it("abrir quem reaproveita mantem a escolha gravada", async () => {
    // A limpeza da escolha vale na EDICAO do par tipo/ASN, e nao na leitura: o
    // reset do registro salvo e a lista de peers chegando escrevem no
    // formulario por fora do `por`, e uma regra presa ao dado (em vez da
    // edicao) apagaria aqui a escolha do registro aberto, antes de a lista
    // responder
    mockFetch({
      ...BASE,
      "GET /api/peers/7": {
        corpo: { id: 7, token: "268127-BKP", formulario: { ...FORMULARIO, apelido: "ACME-BKP", politica_de: "1" } },
      },
      "GET /api/peers": {
        corpo: [
          { id: 1, token: "268127", tipo: "cliente", asn: 268127, apelido: "ACME", nome: "Cliente ACME", grupo_id: null, politica_de: null },
          { id: 7, token: "268127-BKP", tipo: "cliente", asn: 268127, apelido: "ACME-BKP", nome: "Cliente ACME BKP", grupo_id: null, politica_de: 1 },
        ],
      },
    })
    montarRota(rotas, "/peers/7")
    expect(await screen.findByText(/a política vem do peer ACME\./i)).toBeInTheDocument()
  })
})
