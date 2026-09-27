import { act, fireEvent, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { mockFetch, montarRota, peticoes, type Resposta } from "@/teste/roteador"
import { Casca } from "@/app/casca"
import { GrupoTela, TelaDoGrupo } from "./GrupoTela"
import { CAMPO_BRANCO_GRUPO } from "./camposGrupo"

const PLANO = {
  rede: { asn: "64512", politica: "65532" },
  padroes: { tipos: { upstream: { lp_base: 100, route_limit: 1500000, timer_keepalive: 10, timer_hold: 30 } }, origem_tipo: { upstream: 1400 }, origem_classe: {}, downstream: ["cliente", "parceiro"], origens_por_tipo: {}, origem_nome: {} },
  tipos: ["cliente", "parceiro", "upstream", "ix", "pni"], tipos_com_criar_lista: ["cliente", "parceiro", "upstream"],
  classes_cliente: [], lp_base: {}, route_limit: {}, route_limit_exemplo: {},
  prepend_max: 6, prepend_implementado: 3, pop_min: 2001, pop_max: 2999,
  aprendizado_min: 3000, aprendizado_max: 3999, pop_usados: [], aprendizado_usados: [],
  campos_por_tipo: {}, campos_por_tipo_grupo: {},
}

const GRUPO = {
  id: "2", nome: "OPERADORA", tipo: "upstream", asn: "14840", classe: "", lp_base: "100",
  origem: "1400", pop: "", aprendizado: "3100", aprendizado_ix: "", ix_id: "",
  prepend_base: "0", timer_keepalive: "10", timer_hold: "30", bfd: true,
  graceful_restart: true, default_route: false, bh_upstream: "",
  prefixos_v4: [], prefixos_v6: [], te_prefixos_v4: [], te_prefixos_v6: [],
  ap_block: [], ap_te: [], ap_allowed: [], ap_prefer: [], communities: [], large_communities: [],
}

const BASE = {
  "GET /api/plano": { corpo: PLANO },
  "GET /api/peers": { corpo: [{ id: 3, token: "BRDIGITAL", tipo: "upstream", asn: 14840, apelido: "BRDIGITAL", nome: "BRDIGITAL-20G", grupo_id: 2 }] },
  "GET /api/grupos": { corpo: [{ id: 2, nome: "OPERADORA", tipo: "upstream", membros: 1 }] },
  "GET /api/grupos/2": { corpo: { id: 2, nome: "OPERADORA", formulario: GRUPO, membros: [{ id: 3, token: "BRDIGITAL" }] } },
  "POST /api/grupos/previa": { corpo: { erros: {}, avisos: [], bloco: "xpl route-filter UP-OPERADORA-EXPORT-V4", criar_lista: null, arquivo: "grupo-OPERADORA.txt", salvo: "antigo" } },
  "GET /api/grupos/2/saida": { corpo: { bloco: "xpl route-filter UP-OPERADORA-EXPORT-V4", criar_lista: null, arquivo: "grupo-OPERADORA.txt" } },
}

const rotas = [
  { path: "/peers", element: <div>lista de peers</div> },
  // o destino do excluir e do registro que sumiu: sem a rota, a prova do
  // excluir nao teria onde ver a tela sair
  { path: "/grupos", element: <div>lista de grupos</div> },
  { path: "/grupos/novo", element: <GrupoTela /> },
  { path: "/grupos/:id", element: <GrupoTela /> },
]

// As rotas da casca com a tela do grupo dentro: quem guarda o que a tela publica
// e navega pelos links da barra lateral e a casca, entao os casos do guarda e da
// paleta montam por aqui
const CASCA = [{
  path: "/", element: <Casca />,
  children: [
    { path: "grupos", element: <GrupoTela /> },
    { path: "grupos/novo", element: <GrupoTela /> },
    // a rota por id monta pelo TelaDoGrupo, como no roteador: e ele que remonta
    // a tela na troca de registro
    { path: "grupos/:id", element: <TelaDoGrupo /> },
  ],
}]

/** O link da barra lateral que leva ao registro, e nao o texto dele. */
async function linkPara(destino: string) {
  const links = await screen.findAllByRole("link")
  return links.find((l) => l.getAttribute("href") === destino) as HTMLElement
}

// A limpeza do `unstubAllGlobals` e o resto do que cada caso deixa para tras sao
// do arnes, que os registra uma vez por arquivo (web/src/teste/roteador.tsx)

describe("a tela do grupo", () => {
  it("lista os membros com link para o peer", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/grupos/2")
    const membro = await screen.findByRole("link", { name: /BRDIGITAL/ })
    expect(membro).toHaveAttribute("href", "/peers/3")
  })

  it("trocar de registro recarrega o formulario, mesmo sujo", async () => {
    // O React Router reusa o elemento na troca de :id, entao a instancia do
    // useForm sobrevive com os valores do registro ANTERIOR, e o efeito de carga
    // nao roda com o formulario sujo: sem a chave por id, os campos ficam com o
    // grupo que estava sendo editado, e o salvar grava eles no grupo novo
    mockFetch({
      ...BASE,
      "GET /api/grupos": {
        corpo: [
          { id: 2, nome: "OPERADORA", tipo: "upstream", membros: 1 },
          { id: 9, nome: "OUTRO", tipo: "upstream", membros: 0 },
        ],
      },
      "GET /api/grupos/9": { corpo: { id: 9, nome: "OUTRO", formulario: { ...GRUPO, id: "9", nome: "OUTRO" }, membros: [] } },
      "GET /api/grupos/9/saida": { corpo: { bloco: "salvo", remover: null, criar_lista: null, arquivo: "grupo-OUTRO.txt" } },
    })
    montarRota(CASCA, "/grupos/2")
    await userEvent.type(await screen.findByLabelText("Nome"), " EDITADO")
    await userEvent.click(await linkPara("/grupos/9"))
    await userEvent.click(await screen.findByRole("button", { name: /sair sem salvar/i }))
    // os campos mostram o registro novo, e nao o que estava sendo editado
    await waitFor(() => expect(screen.getByLabelText("Nome")).toHaveValue("OUTRO"))
  })

  it("o excluir com membro mostra a recusa do 409 e nao exclui", async () => {
    mockFetch({
      ...BASE,
      "DELETE /api/grupos/2": { status: 409, corpo: { erros: { membros: "o grupo ainda tem peers membros: BRDIGITAL. Tire-os do grupo antes de excluir." }, avisos: [] } },
    })
    montarRota(rotas, "/grupos/2")
    // o excluir vive no menu "mais acoes" e a recusa aparece dentro do dialogo,
    // que sao os tres cliques do caminho: gatilho, item, botao do dialogo
    await userEvent.click(await screen.findByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    await userEvent.click(await screen.findByRole("button", { name: /^excluir$/i }))
    expect(await screen.findByText(/ainda tem peers membros/)).toBeInTheDocument()
    // e o grupo continua na tela, com o dialogo aberto: o 409 nao exclui nem
    // navega para a lista
    expect(screen.getByRole("dialog")).toBeInTheDocument()
  })

  it("uma recusa que nao e a dos membros tambem aparece no dialogo", async () => {
    // o dialogo so desenhava a mensagem dos membros, entao um 404 (ou um corpo
    // que o lerRecusa nao entende, com a chave `_corpo`) ficava em silencio: o
    // dialogo aberto, sem mensagem e sem toast, e o operador clicando para
    // sempre
    mockFetch({
      ...BASE,
      "DELETE /api/grupos/2": {
        status: 404,
        corpo: { erros: { _: "grupo nao encontrado", membros: "o grupo ainda tem peers membros: BRDIGITAL." }, avisos: [] },
      },
    })
    montarRota(rotas, "/grupos/2")
    await userEvent.click(await screen.findByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    await userEvent.click(await screen.findByRole("button", { name: /^excluir$/i }))
    expect(await screen.findByText("grupo nao encontrado")).toBeInTheDocument()
    expect(screen.getByText(/ainda tem peers membros/)).toBeInTheDocument()
  })

  it("o cancelar do dialogo limpa a recusa que estava na tela", async () => {
    // o onOpenChange limpa, e o botao cancelar fechava por fora dele: o texto do
    // 409 de antes voltava na proxima abertura, sobre outro clique
    mockFetch({
      ...BASE,
      "DELETE /api/grupos/2": { status: 409, corpo: { erros: { membros: "o grupo ainda tem peers membros: BRDIGITAL." }, avisos: [] } },
    })
    montarRota(rotas, "/grupos/2")
    await userEvent.click(await screen.findByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    await userEvent.click(await screen.findByRole("button", { name: /^excluir$/i }))
    expect(await screen.findByText(/ainda tem peers membros/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: /^cancelar$/i }))
    await userEvent.click(screen.getByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    expect(await screen.findByRole("dialog")).toBeInTheDocument()
    expect(screen.queryByText(/ainda tem peers membros/)).not.toBeInTheDocument()
  })

  it("o salvar bem-sucedido nao desfaz o que foi gravado", async () => {
    // o sujo entra por ref no efeito que enche o formulario com o registro
    // lido, e nao como dependencia dele: com ele na lista, o salvamento (que
    // zera o isDirty) faz o efeito rodar de novo e reaplicar o registro da
    // montagem, entao a tela volta ao valor de antes do salvar e o proximo
    // salvar grava os valores revertidos
    const salvo = { ...GRUPO, nome: "OPERADORA NOVA" }
    mockFetch({
      ...BASE,
      "PUT /api/grupos/2": {
        corpo: {
          registro: { id: 2, nome: "OPERADORA NOVA", formulario: salvo, membros: [] },
          arquivo: "grupo-OPERADORA-NOVA.txt", avisos: [],
        },
      },
    })
    montarRota(rotas, "/grupos/2")
    const campo = await screen.findByLabelText("Nome")
    await userEvent.clear(campo)
    await userEvent.type(campo, "OPERADORA NOVA")
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    await waitFor(() => expect(screen.getByLabelText("Nome")).toHaveValue("OPERADORA NOVA"))
  })

  it("o excluir sai sem perguntar sobre alteracao nao salva", async () => {
    // o excluir navega por conta propria, e a essa altura o registro ja nao
    // existe: com o bloqueio valendo, o operador veria o "sair sem salvar?"
    // sobre um grupo excluido, e a unica saida seria confirma-lo
    mockFetch({ ...BASE, "DELETE /api/grupos/2": { status: 204, corpo: null } })
    montarRota(rotas, "/grupos/2")
    await userEvent.type(await screen.findByLabelText("Nome"), " NOVA")
    await userEvent.click(screen.getByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    await userEvent.click(await screen.findByRole("button", { name: /^excluir$/i }))
    expect(await screen.findByText("lista de grupos")).toBeInTheDocument()
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
  })

  it("a saida que o operador pede continua perguntando", async () => {
    // O guarda existe para a navegacao que o OPERADOR pede. Sem esta prova, um
    // `permitir` sempre verdadeiro deixaria a suite verde, e a alteracao nao
    // salva se perderia sem aviso. Aqui a navegacao vem de um link da barra
    // lateral, que e o caminho de verdade
    mockFetch({
      ...BASE,
      "GET /api/grupos": {
        corpo: [
          { id: 2, nome: "OPERADORA", tipo: "upstream", membros: 1 },
          { id: 9, nome: "OUTRA OPERADORA", tipo: "upstream", membros: 0 },
        ],
      },
    })
    montarRota(CASCA, "/grupos/2")
    await userEvent.type(await screen.findByLabelText("Nome"), " NOVA")
    await userEvent.click(await linkPara("/grupos/9"))
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Sair sem salvar?")
  })

  it("o criar grupo grava o formulario em branco, e o id do 201 leva a url junto", async () => {
    // O UNICO fluxo de criacao do branch sem prova: o POST /api/grupos so
    // aparecia com 404. A fixture serve o formulario em branco, que e o corpo
    // que sai de uma tela que ninguem tocou: e o id vazio dele o caso que a API
    // le como "cria novo" (o proximo_id, app/formulario.py), medido e aceito. O
    // id do 201 e quem move a URL - sem essa volta, o proximo salvar bateria no
    // 404 de um registro que existe com outro id
    mockFetch({
      ...BASE,
      // o registro em branco que a tela abre: e daqui que sai o corpo do POST
      "GET /api/grupos/novo": { corpo: { id: 3, nome: "", formulario: { ...CAMPO_BRANCO_GRUPO }, membros: [] } },
      "POST /api/grupos": {
        status: 201,
        corpo: {
          registro: { id: 3, nome: "NOVO", formulario: { ...GRUPO, id: "3", nome: "NOVO" }, membros: [] },
          arquivo: "grupo-NOVO.txt", avisos: [],
        },
      },
      "GET /api/grupos/3": { corpo: { id: 3, nome: "NOVO", formulario: { ...GRUPO, id: "3", nome: "NOVO" }, membros: [] } },
      "GET /api/grupos/3/saida": { corpo: { bloco: "salvo", criar_lista: null, arquivo: "grupo-NOVO.txt" } },
    })
    montarRota(rotas, "/grupos/novo")
    await screen.findByRole("tab", { name: /bloco do grupo/i })
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    const post = peticoes().find((p) => p.metodo === "POST")
    expect(post?.caminho).toBe("/api/grupos")
    // o corpo inteiro, e nao so o campo que o caso digita: e o id vazio dele a
    // parte que nada mais exercita
    expect(post?.corpo).toEqual(CAMPO_BRANCO_GRUPO)
    expect(await screen.findByText(/gravado em out\/grupo-NOVO.txt/)).toBeInTheDocument()
    // a URL andou para o id do registro gravado
    await waitFor(() => expect(peticoes().map((p) => `${p.metodo} ${p.caminho}`)).toContain("GET /api/grupos/3"))
  })

  it("a recusa por id rebusca o proximo livre e mantem o formulario", async () => {
    // o formulario do grupo nao tem campo id, entao essa recusa era beco sem
    // saida: a unica saida era recarregar /grupos/novo e perder o digitado
    const mapa: Record<string, Resposta> = {
      ...BASE,
      "POST /api/grupos": { status: 422, corpo: { erros: { id: "ID ja usado pelo grupo PARCEIROS" }, avisos: [] } },
      // o formulario em branco que a tela abre, com o nome vazio como no outro
      // caso de /grupos/novo: com o nome do GRUPO aqui o campo comeca preenchido
      // e o digitado viraria "OPERADORAOPERADORA"
      "GET /api/grupos/novo": { corpo: { id: 8, nome: "", formulario: { ...GRUPO, id: "8", nome: "" }, membros: [] } },
    }
    mockFetch(mapa)
    montarRota(rotas, "/grupos/novo")
    await screen.findByLabelText("Nome")
    await userEvent.type(screen.getByLabelText("Nome"), "OPERADORA")
    // a previa da montagem chega ANTES do clique, como nos outros casos de
    // recusa deste arquivo: a recusa vale ate a previa seguinte responder, e
    // com a primeira ainda em voo a mensagem dependeria da corrida entre as
    // duas em vez de medir o que o caso diz medir
    await screen.findByText(/UP-OPERADORA-EXPORT-V4/)
    const antes = peticoes().filter((p) => p.metodo === "GET" && p.caminho === "/api/grupos/novo").length
    // o id da montagem esta tomado, e quem a rebusca devolve e outro. Os ids
    // DIFERENTES sao o que da o que medir: com o mesmo id nas duas chamadas o
    // caso passaria com o setValue removido, que e a linha que ele protege
    mapa["GET /api/grupos/novo"].corpo = { id: 9, nome: "", formulario: { ...GRUPO, id: "9", nome: "" }, membros: [] }

    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))

    expect(await screen.findByText(/ID ja usado pelo grupo/)).toBeInTheDocument()
    // a chave `id` nao e campo do formulario do grupo: a mensagem sai no resumo
    // como texto, e nao como o botao que prometia um link para lugar nenhum
    expect(screen.queryByRole("button", { name: /ID ja usado pelo grupo/ })).not.toBeInTheDocument()
    expect(screen.getByLabelText("Nome")).toHaveValue("OPERADORA")
    expect(peticoes().some((p) => p.metodo === "GET" && p.caminho === "/api/grupos/novo")).toBe(true)
    // o `some` acima ja e verdade pelo GET da MONTAGEM, entao quem mede a
    // rebusca do id livre e a contagem: um GET a mais depois da recusa
    expect(peticoes().filter((p) => p.metodo === "GET" && p.caminho === "/api/grupos/novo")).toHaveLength(antes + 1)
    // e o id que a rebusca trouxe entra no formulario: a previa seguinte sai com
    // os valores de la, e o corpo dela e o unico lugar da tela onde o `id`
    // aparece, porque nenhum campo do grupo desenha esse nome
    await waitFor(() =>
      expect(
        peticoes().some((p) => p.caminho === "/api/grupos/previa" && (p.corpo as { id?: string } | null)?.id === "9"),
      ).toBe(true),
    )
  })

  it("a rede fora na gravacao avisa com tentar de novo, e o formulario nao perde nada", async () => {
    // O openapi-fetch RE-LANCA a excecao de rede em vez de devolver `{error}`:
    // o mutateAsync rejeitava, nenhum onSuccess rodava, e o clique em salvar
    // nao deixava rastro nenhum na tela
    const mapa: Record<string, Resposta> = { ...BASE, "PUT /api/grupos/2": { rede: true } }
    mockFetch(mapa)
    montarRota(rotas, "/grupos/2")
    const nome = await screen.findByLabelText("Nome")
    await userEvent.type(nome, " NOVA")
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    expect(screen.getByLabelText("Nome")).toHaveValue("OPERADORA NOVA")
    mapa["PUT /api/grupos/2"] = {
      corpo: { registro: { id: 2, nome: "OPERADORA NOVA", formulario: GRUPO, membros: [] }, arquivo: "grupo-OPERADORA.txt", avisos: [] },
    }
    await userEvent.click(screen.getByRole("button", { name: /tentar de novo/i }))
    await waitFor(() => expect(peticoes().filter((p) => p.metodo === "PUT")).toHaveLength(2))
  })

  it("o 500 na gravacao avisa com tentar de novo, sem apagar o bloco", async () => {
    // o mesmo caminho do 500 do peer: o corpo sem recusa nao vira mensagem de
    // campo, e o que sobra e o aviso com o caminho de volta
    mockFetch({ ...BASE, "PUT /api/grupos/2": { status: 500, corpo: { detail: "falhou" } } })
    montarRota(rotas, "/grupos/2")
    await screen.findByText(/UP-OPERADORA-EXPORT-V4/)
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    expect(await screen.findByRole("button", { name: /tentar de novo/i })).toBeInTheDocument()
    expect(screen.queryByText(/resposta inesperada da API/)).not.toBeInTheDocument()
    expect(screen.getByText(/UP-OPERADORA-EXPORT-V4/)).toBeInTheDocument()
  })

  it("a rede fora no excluir avisa no dialogo, que fica aberto", async () => {
    // O excluir le a recusa do corpo, e uma excecao de rede nao tem corpo: sem
    // o aviso o dialogo ficava aberto e mudo, com o operador clicando
    mockFetch({ ...BASE, "DELETE /api/grupos/2": { rede: true } })
    montarRota(rotas, "/grupos/2")
    await userEvent.click(await screen.findByRole("button", { name: /mais ações/i }))
    await userEvent.click(await screen.findByRole("menuitem", { name: /excluir/i }))
    await userEvent.click(await screen.findByRole("button", { name: /^excluir$/i }))
    expect(await screen.findByText("não deu para falar com a API")).toBeInTheDocument()
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    // e o grupo continua na tela, com o bloco da previa: a exclusao que nao
    // chegou nao pode navegar para a lista
    expect(await screen.findByText(/UP-OPERADORA-EXPORT-V4/)).toBeInTheDocument()
  })

  it("a consulta ao IRR que falha nao apaga o bloco do painel", async () => {
    // A chave do bgpq4 nao tem campo: contar o mapa inteiro apagava o painel e
    // mandava o operador corrigir o que nao tem o que corrigir, e o bloco do
    // grupo sumia por causa de uma consulta que nao contesta o formulario
    mockFetch({
      ...BASE,
      "POST /api/irr": { status: 502, corpo: { erros: { bgpq4: "bgpq4 falhou: sem resposta do RADB" }, avisos: [] } },
    })
    montarRota(rotas, "/grupos/2")
    // a previa chega primeiro: e ela que traz o bloco, e a recusa do IRR vale
    // ate a proxima previa responder - clicar antes disso mediria a corrida
    // entre as duas, e nao o que o caso quer medir
    await screen.findByText(/UP-OPERADORA-EXPORT-V4/)
    await userEvent.click(screen.getByRole("button", { name: /^consultar IRR$/i }))
    // o recado sai na secao de prefixos, ao lado dos botoes do IRR, que e onde
    // o operador vai procurar o resultado da consulta
    const secao = document.querySelector("#secao-prefixos") as HTMLElement
    await waitFor(() =>
      expect(within(secao).getByText("bgpq4 falhou: sem resposta do RADB")).toBeInTheDocument(),
    )
    expect(screen.getByText(/UP-OPERADORA-EXPORT-V4/)).toBeInTheDocument()
    expect(screen.queryByText(/a prévia volta quando os erros forem corrigidos/)).not.toBeInTheDocument()
    // e o 502 e um 5xx como outro qualquer: o caminho de volta entra junto
    expect(screen.getByRole("button", { name: /tentar de novo/i })).toBeInTheDocument()
  })

  it("a previa que falhou diz que nao deu, em vez de gerar para sempre", async () => {
    // So a tela dos prefixos olhava o isError da previa: aqui o painel ficava
    // em "gerando previa..." para sempre, e o operador esperava por um bloco
    // que nao vem. A espera cobre o retry do cliente, que e o mesmo do app
    mockFetch({ ...BASE, "POST /api/grupos/previa": { status: 500, corpo: { detail: "falhou" } } })
    montarRota(rotas, "/grupos/2")
    expect(await screen.findByText(/a prévia volta quando os erros forem corrigidos/, {}, { timeout: 3000 })).toBeInTheDocument()
    expect(screen.queryByText(/gerando prévia/)).not.toBeInTheDocument()
  })

  it("/grupos/abc e registro que nao existe, e nao falha de rede", async () => {
    // o mesmo do peer: o Number("abc") vira NaN, o GET /api/grupos/NaN responde
    // 422 e o inicial.ts so trata o 404
    mockFetch({
      ...BASE,
      // o caminho com que o pedido sai quando o ident vira NaN, e o que a API
      // responde nele: e a medida do vermelho, e nao o que a tela pede agora
      "GET /api/grupos/NaN": { status: 422, corpo: { erros: { _corpo: "path.ident: Input should be a valid integer" }, avisos: [] } },
    })
    montarRota(rotas, "/grupos/abc")
    expect(await screen.findByText(/Registro não encontrado/)).toBeInTheDocument()
    expect(screen.queryByText("não deu para falar com a API")).not.toBeInTheDocument()
    // e nem gasta um pedido para um id que nao e id: a leitura nem sai
    expect(peticoes().some((p) => p.caminho.startsWith("/api/grupos/"))).toBe(false)
  })

  it("a marca da navegacao propria nao fica presa no destino de mesmo caminho", async () => {
    // O 404 do salvar manda para /grupos, que e o mesmo caminho onde o grupo
    // novo ja esta: com a marca chaveada pelo pathname o efeito nao roda de
    // novo, ela fica presa em true, e dali em diante o guarda fica desligado em
    // silencio, ate numa navegacao que o operador pede
    mockFetch({
      ...BASE,
      "GET /api/grupos/novo": { corpo: { id: 8, nome: "", formulario: { ...GRUPO, id: "8", nome: "" }, membros: [] } },
      "POST /api/grupos": { status: 404, corpo: { erros: { _: "registro nao encontrado" }, avisos: [] } },
    })
    montarRota(CASCA, "/grupos")
    await userEvent.type(await screen.findByLabelText("Nome"), "NOVO")
    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))
    await screen.findByText(/registro não encontrado/)
    await userEvent.click(await linkPara("/grupos/2"))
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Sair sem salvar?")
  })

  it("o salvar atualiza a aba ao criar", async () => {
    // o criar_lista e o `salvo` da aba "ao criar" vem de GET /saida, e nao da
    // previa: sem invalidar depois do salvar, o painel continuaria comparando o
    // bloco novo com o arquivo de antes
    const mapa = {
      ...BASE,
      "POST /api/grupos/previa": {
        corpo: {
          erros: {}, avisos: [], bloco: "xpl route-filter UP-OPERADORA-EXPORT-V4",
          criar_lista: "CL-ANTIGO", arquivo: "grupo-OPERADORA.txt", salvo: "antigo",
        },
      },
      "PUT /api/grupos/2": {
        corpo: {
          registro: { id: 2, nome: "OPERADORA", formulario: GRUPO, membros: [] },
          arquivo: "grupo-OPERADORA.txt", avisos: [],
        },
      },
      "GET /api/grupos/2/saida": {
        corpo: { bloco: "xpl route-filter UP-OPERADORA-EXPORT-V4", criar_lista: "CL-ANTIGO", arquivo: "grupo-OPERADORA.txt" },
      },
    }
    mockFetch(mapa)
    montarRota(rotas, "/grupos/2")
    await screen.findByRole("tab", { name: /ao criar o grupo/i })
    // o mapa e lido a cada chamada: o arquivo em out/ muda entre a leitura da
    // tela e o salvar, como muda quando alguem grava por fora
    mapa["GET /api/grupos/2/saida"].corpo.criar_lista = "CL-NOVO"
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    await userEvent.click(screen.getByRole("tab", { name: /ao criar o grupo/i }))
    // a aba corrente e a do criar (o conteudo dela e o da previa, intocado), e o
    // rotulo diz que o out/ relido nao bate mais com ela
    expect(await screen.findByText("CL-ANTIGO")).toBeInTheDocument()
    expect(await screen.findByText(/o arquivo em out\/ está desatualizado/)).toBeInTheDocument()
    expect(peticoes().filter((p) => p.caminho === "/api/grupos/2/saida").length).toBeGreaterThan(1)
  })

  it("o salvar do cabecalho nao grava antes de o registro chegar", async () => {
    // o botao so olhava o `isPending` do salvar, e enquanto o registro nao chega
    // o formulario esta em branco: a API recusa um nome vazio, e a recusa pinta
    // embaixo de um formulario que ninguem tocou
    mockFetch({
      ...BASE,
      "GET /api/grupos/2": { status: 500, corpo: {} },
      "PUT /api/grupos/2": {
        corpo: {
          registro: { id: 2, nome: "OPERADORA", formulario: GRUPO, membros: [] },
          arquivo: "grupo-OPERADORA.txt", avisos: [],
        },
      },
    })
    montarRota(rotas, "/grupos/2")
    // o registro ainda nao chegou (o GET falhou e a consulta esta no retry de 1s
    // do cliente), e o botao ja esta na tela: e o estado que a guarda cobre
    const botao = await screen.findByRole("button", { name: /^salvar$/i })
    expect(botao).toBeDisabled()
    fireEvent.click(botao)
    // a tela de falha chega quando o retry se esgota: esperar por ela e esperar
    // a janela inteira em que o botao esteve na tela sem o registro, e so entao
    // a ausencia de escrita quer dizer alguma coisa
    await screen.findByText("não deu para falar com a API", {}, { timeout: 3000 })
    expect(peticoes().some((p) => p.metodo === "PUT")).toBe(false)
  })

  it("o salvar recarrega as listas do plano", async () => {
    // o POP e o aprendizado ja cadastrados saem do /api/plano, que os monta de
    // peers MAIS grupos: sem invalidar, o grupo recem-gravado nao entra nas
    // sugestoes ate a janela voltar ao foco
    mockFetch({
      ...BASE,
      "PUT /api/grupos/2": {
        corpo: {
          registro: { id: 2, nome: "OPERADORA", formulario: GRUPO, membros: [] },
          arquivo: "grupo-OPERADORA.txt", avisos: [],
        },
      },
    })
    montarRota(rotas, "/grupos/2")
    await screen.findByRole("tab", { name: /bloco do grupo/i })
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))
    await waitFor(() =>
      expect(peticoes().filter((p) => p.caminho === "/api/plano").length).toBeGreaterThan(1),
    )
  })

  it("a paleta ve as acoes que a tela publica", async () => {
    // o caminho inteiro da publicacao: a tela publica no ProvedorAcoes da casca
    // e a paleta so oferece o que chegou la. Sem a chamada, "duplicar o
    // registro aberto" e "copiar o bloco aberto" nao aparecem em tela nenhuma
    mockFetch({
      ...BASE,
      "GET /api/grupos/2/copia": { corpo: { id: 8, nome: "OPERADORA", formulario: { ...GRUPO, id: "8" }, membros: [] } },
    })
    montarRota(CASCA, "/grupos/2")
    await screen.findByRole("tab", { name: /bloco do grupo/i })
    await userEvent.keyboard("{Control>}k{/Control}")
    expect(await screen.findByText("copiar o bloco aberto")).toBeInTheDocument()
    await userEvent.click(screen.getByText("duplicar o registro aberto"))
    // e a acao publicada leva ao destino dela, que e o grupo novo com a copia
    expect(await screen.findByText(/cópia de OPERADORA/)).toBeInTheDocument()
  })

  it("o duplicar do cabecalho pergunta com o formulario sujo", async () => {
    // o mesmo comando da paleta, e o operador tem que poder dizer nao nos dois:
    // o arquivo pinava so o da paleta, que foi feito para perguntar como este
    mockFetch({
      ...BASE,
      "GET /api/grupos/2/copia": { corpo: { id: 8, nome: "OPERADORA", formulario: { ...GRUPO, id: "8" }, membros: [] } },
    })
    montarRota(rotas, "/grupos/2")
    await userEvent.type(await screen.findByLabelText("Nome"), " NOVA")
    await userEvent.click(screen.getByRole("button", { name: /duplicar/i }))
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Sair sem salvar?")
  })

  it("o duplicar da paleta pergunta como o do cabecalho", async () => {
    // o mesmo comando nao pode perguntar num lugar e nao no outro: a copia vem
    // do registro SALVO, entao a alteracao nao salva se perde de qualquer jeito,
    // e o operador tem que poder dizer nao
    mockFetch(BASE)
    montarRota(CASCA, "/grupos/2")
    await userEvent.type(await screen.findByLabelText("Nome"), " NOVA")
    await userEvent.keyboard("{Control>}k{/Control}")
    await userEvent.click(await screen.findByText("duplicar o registro aberto"))
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Sair sem salvar?")
  })

  it("sem bloco aberto, o copiar da paleta nem aparece", async () => {
    // a previa em erro chega com conteudo nulo: sem a guarda, o item apareceria
    // e o clique nao faria nada. A espera e pelo erro na tela, e nao pelo item
    // ausente, que estaria ausente tambem antes de a previa responder
    mockFetch({
      ...BASE,
      "POST /api/grupos/previa": {
        corpo: { erros: { nome: "nome obrigatório" }, avisos: [], bloco: null, criar_lista: null, arquivo: null, salvo: null },
      },
    })
    montarRota(CASCA, "/grupos/2")
    await screen.findByRole("button", { name: "nome obrigatório" })
    await userEvent.keyboard("{Control>}k{/Control}")
    expect(await screen.findByText("duplicar o registro aberto")).toBeInTheDocument()
    expect(screen.queryByText("copiar o bloco aberto")).not.toBeInTheDocument()
  })

  it("o Ctrl+S da casca salva pelo que a tela publicou", async () => {
    // o terceiro callback publicado e o salvar, que a paleta nao mostra: quem o
    // alcanca e o Ctrl+S da casca (useAtalhos, em casca.tsx)
    mockFetch({
      ...BASE,
      "PUT /api/grupos/2": {
        corpo: {
          registro: { id: 2, nome: "OPERADORA", formulario: GRUPO, membros: [] },
          arquivo: "grupo-OPERADORA.txt", avisos: [],
        },
      },
    })
    montarRota(CASCA, "/grupos/2")
    await screen.findByRole("tab", { name: /bloco do grupo/i })
    await userEvent.keyboard("{Control>}s{/Control}")
    await waitFor(() =>
      expect(peticoes().some((p) => p.metodo === "PUT" && p.caminho === "/api/grupos/2")).toBe(true),
    )
  })

  it("o Ctrl+S nao salva antes de o registro chegar", async () => {
    // Na tela de falha o formulario nem esta montado, e o `aoSalvar` publicado
    // assim mesmo mandava um PUT com o formulario em branco: a API recusa um
    // nome vazio, e a recusa nao aparece aqui, porque so o formulario a mostra
    mockFetch({
      ...BASE,
      "GET /api/plano": { status: 500, corpo: {} },
      "PUT /api/grupos/2": {
        corpo: {
          registro: { id: 2, nome: "OPERADORA", formulario: GRUPO, membros: [] },
          arquivo: "grupo-OPERADORA.txt", avisos: [],
        },
      },
    })
    montarRota(CASCA, "/grupos/2")
    // a tela de falha so aparece depois do retry automatico da consulta do
    // plano, que o QueryClient do arnes deixa em um: a espera e maior que o
    // tempo dele, senao o caso mede o relogio e nao o estado
    await screen.findByText("não deu para falar com a API", {}, { timeout: 3000 })
    await userEvent.keyboard("{Control>}s{/Control}")
    // o PUT e o unico caminho de escrita do salvar, e ele nao pode sair sem o
    // plano e o registro na mao
    expect(peticoes().some((p) => p.metodo === "PUT")).toBe(false)
  })

  it("nao tem aba de remocao: o grupo nao gera bloco de remocao", async () => {
    // o `remover` entra no corpo de proposito: sem ele a assercao passaria mesmo
    // com a linha do peer (`if (saida.data?.remover)`) colada nesta tela, porque
    // o duble nunca devolvia o campo. O endpoint do grupo nao emite um, e a tela
    // tem que ignorar o que vier
    mockFetch({
      ...BASE,
      "GET /api/grupos/2/saida": {
        corpo: {
          bloco: "xpl route-filter UP-OPERADORA-EXPORT-V4", criar_lista: null,
          arquivo: "grupo-OPERADORA.txt", remover: "undo UP-OPERADORA-IMPORT-V4",
        },
      },
    })
    montarRota(rotas, "/grupos/2")
    await screen.findByRole("tab", { name: /bloco do grupo/ })
    // Duas esperas antes da ausencia, e as duas sao a diferenca entre esta
    // assercao dizer alguma coisa e nao dizer nada: a primeira e o GET /saida,
    // que e quem traz o corpo com o `remover`, e a segunda e a promessa da
    // consulta entrando no estado, que o `act` vazio deixa o React processar.
    // Medido: sem elas, a linha do peer colada aqui (`if (saida.data?.remover)`)
    // deixava o caso verde
    await waitFor(() => expect(peticoes().some((p) => p.caminho === "/api/grupos/2/saida")).toBe(true))
    await act(async () => {})
    expect(screen.queryByRole("tab", { name: /remoção/ })).not.toBeInTheDocument()
  })
})
