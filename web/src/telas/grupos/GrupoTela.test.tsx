import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { mockFetch, montarRota, peticoes } from "@/teste/roteador"
import { Casca } from "@/app/casca"
import { GrupoTela } from "./GrupoTela"

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

// A limpeza do `unstubAllGlobals` e o resto do que cada caso deixa para tras sao
// do arnes, que os registra uma vez por arquivo (web/src/teste/roteador.tsx)

describe("a tela do grupo", () => {
  it("lista os membros com link para o peer", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/grupos/2")
    const membro = await screen.findByRole("link", { name: /BRDIGITAL/ })
    expect(membro).toHaveAttribute("href", "/peers/3")
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

  it("a paleta ve as acoes que a tela publica", async () => {
    // o caminho inteiro da publicacao: a tela publica no ProvedorAcoes da casca
    // e a paleta so oferece o que chegou la. Sem a chamada, "duplicar o
    // registro aberto" e "copiar o bloco aberto" nao aparecem em tela nenhuma
    mockFetch({
      ...BASE,
      "GET /api/grupos/2/copia": { corpo: { id: 8, nome: "OPERADORA", formulario: { ...GRUPO, id: "8" }, membros: [] } },
    })
    montarRota(
      [{
        path: "/", element: <Casca />,
        children: [
          { path: "grupos/novo", element: <GrupoTela /> },
          { path: "grupos/:id", element: <GrupoTela /> },
        ],
      }],
      "/grupos/2",
    )
    await screen.findByRole("tab", { name: /bloco do grupo/i })
    await userEvent.keyboard("{Control>}k{/Control}")
    expect(await screen.findByText("copiar o bloco aberto")).toBeInTheDocument()
    await userEvent.click(screen.getByText("duplicar o registro aberto"))
    // e a acao publicada leva ao destino dela, que e o grupo novo com a copia
    expect(await screen.findByText(/cópia de OPERADORA/)).toBeInTheDocument()
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
    montarRota(
      [{
        path: "/", element: <Casca />,
        children: [
          { path: "grupos/novo", element: <GrupoTela /> },
          { path: "grupos/:id", element: <GrupoTela /> },
        ],
      }],
      "/grupos/2",
    )
    await screen.findByRole("tab", { name: /bloco do grupo/i })
    await userEvent.keyboard("{Control>}s{/Control}")
    await waitFor(() =>
      expect(peticoes().some((p) => p.metodo === "PUT" && p.caminho === "/api/grupos/2")).toBe(true),
    )
  })

  it("nao tem aba de remocao: o grupo nao gera bloco de remocao", async () => {
    mockFetch(BASE)
    montarRota(rotas, "/grupos/2")
    expect(await screen.findByRole("tab", { name: /bloco do grupo/ })).toBeInTheDocument()
    expect(screen.queryByRole("tab", { name: /remoção/ })).not.toBeInTheDocument()
  })
})
