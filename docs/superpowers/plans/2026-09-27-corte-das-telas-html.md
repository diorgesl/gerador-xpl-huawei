# Corte das telas HTML do bgpgen (etapa 3 do front em SPA) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A SPA passa a ser o unico front do bgpgen: `/` redireciona para `/peers`, as rotas HTML, os quatro templates das telas e o `tests/test_app.py` saem do repositorio, e cada comportamento que eles protegiam fica com par na suite de API ou na do front.

**Architecture:** O `app/app.py` fica do tamanho do que ele ainda serve: a API em `/api`, o `/base.txt`, o build do front em `/assets` e as rotas da SPA. O `app/formulario.py` continua sendo a casa dos helpers, agora sem os reexports que existiam so para as rotas HTML lerem pelo nome. Nenhuma regra de negocio muda: `plan.py`, `validate.py`, `render.py`, `peers.py` e `prefixes.py` nao sao tocados, e a saida gerada continua byte a byte a mesma.

**Tech Stack:** FastAPI, Starlette, Jinja2 (so para os blocos XPL), pytest; React 19, Vite, TypeScript estrito, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-26-front-spa-design.md` (secoes "Producao e desenvolvimento", "Etapas > 3. Corte" e "Testes > Etapa 3").

**Planos das etapas anteriores (ja executados):** `docs/superpowers/plans/2026-09-26-api-json.md` e `docs/superpowers/plans/2026-09-26-front-spa.md`. A API que fica em pe esta em `app/api.py` e `app/modelos_api.py`; a SPA esta em `web/`, e o que ela ainda nao tem e a tela de chegada (Task 1).

## Mapa das tasks

| # | Task | Entrega |
| --- | --- | --- |
| 1 | A tela de chegada da SPA | `/peers` e `/grupos` com estado vazio, e o indice do roteador levando para `/peers` |
| 2 | Os testes que faltavam | as 18 lacunas da tabela de pares viram teste na suite de `/api` (e uma no front) |
| 3 | O `/base.txt` sobrevive | `tests/test_base.py` com os testes que saem do `test_app.py` |
| 4 | O corte | fora as rotas HTML, os templates das telas, o `test_app.py` e os reexports; `/` vira 307 para `/peers`; `schema.d.ts` regerado |
| 5 | Documentacao | `README.md` e `CLAUDE.md` descrevem o app como ele fica; o healthcheck e o `compose.yaml` conferidos |

## Global Constraints

- **A saida gerada nao muda um byte.** `app/plan.py`, `app/validate.py`, `app/render.py`, `app/peers.py`, `app/prefixes.py`, `app/api.py`, `app/modelos_api.py`, `app/formulario.py` e os templates `.j2` de XPL (`base.txt.j2`, `bloco*`, `cliente.txt.j2`, `ix.txt.j2`, `pni.txt.j2`, `upstream.txt.j2`, `grupo_*.txt.j2`, `remover*.txt.j2`, `criar_lista.txt.j2`, `_macros.j2`) ficam como estao. Os golden de `tests/golden/` continuam valendo, e o `web/src/lib/xpl.test.ts` os le do mesmo lugar.
- **Os quatro templates que saem** sao `templates/pagina.html`, `templates/pagina_grupo.html`, `templates/_estilo.html` e `templates/_copiar.html`. `_macros.j2` **nao** sai: ele e importado pelos templates de bloco, e nao pelas telas.
- **ASCII no XPL e nos comentarios de codigo**, como manda o `CLAUDE.md` do projeto. Os textos de tela e do `README.md` sao em portugues e levam acento; as mensagens do `validate.py` continuam em ASCII.
- **`/base.txt` continua onde esta**, montado na hora do download, e continua fora da SPA.
- **Sem build em `BGPGEN_WEB`, as rotas da SPA respondem 503** com a instrucao de compilar, e a API continua funcionando. Os testes de API nao dependem do build.
- **Uma worktree por plano**, como manda o `CLAUDE.md` do usuario: a implementacao acontece numa worktree, e o merge no checkout principal fica com o operador.
- **A suite inteira verde em cada task**: `.venv/bin/python -m pytest -q`, e no `web/` `npm test`, `npm run lint` e `npm run api:conferir`.

## Review Focus

O que a spec pede mas nenhum teste de task exercita sozinho, e que e onde o corte costuma doer:

1. **O `schema.d.ts` regerado.** As dezesseis rotas das telas HTML entram hoje no `app.openapi()` (nenhuma delas tem `include_in_schema=False`), entao o arquivo versionado em `web/src/api/schema.d.ts` menciona `/peer`, `/grupo`, `/saida`, `/asn`, `/bgpq4` e `/blocos`. O corte muda o `openapi.json` de 36 caminhos para 20, e o `tests/test_tipos_api.py` roda `npm run api:conferir`: sem regerar, a suite fica vermelha por um motivo que nao tem a ver com o front.
2. **O que continua no ar depois do corte.** `/peer/novo` e `/grupo/novo` (singular) tem que dar 404, e `/peers/novo` (plural) tem que continuar servindo a SPA. As duas rotas sao parecidas o bastante para uma engolir a outra sem ninguem notar.
3. **O healthcheck do `Dockerfile`.** Ele bate em `http://127.0.0.1:8000/` esperando 200, e o `/` passa a ser um 307. O `urllib` segue redirect por padrao, entao o 200 vem do `/peers` servido pelo build, e essa corrente tem tres elos: um teste tem que fixar o primeiro.
4. **O `/` da SPA em desenvolvimento.** Com o Vite na 5173 nao existe o redirect do servidor: quem responde `/` e o proprio roteador da SPA. Sem a rota de indice apontando para `/peers`, o modo de desenvolvimento documentado no `README.md` abre o `NaoEncontrado`. Essa linha nao tem teste, porque o `roteador.tsx` nao tem teste de unidade e o e2e roda contra o uvicorn, onde quem responde `/` e o servidor. O Step 5 da Task 1 diz que ela se confere a mao, com o Vite de pe.
5. **Perder cobertura em silencio.** O `test_app.py` tem 151 testes, e a maioria e a unica prova de um comportamento. A tabela da secao "Tabela de pares" existe para que nenhum deles saia sem par, e a Task 2 fecha o que nao tinha.

---

### Task 1: A tela de chegada da SPA

Hoje `/peers` abre um formulario de peer novo em branco: `PeerTela` e o elemento das rotas `peers`, `peers/novo` e `peers/:id`, e sem `id` e sem `de` ela monta o formulario do zero. No corte, `/` passa a levar para `/peers`, e o operador que abre o app cai digitando num formulario em branco. A spec (`design.md:222`) pede outra coisa nessa rota: "Casca com a lista e um estado vazio ('escolha um peer ou crie um')". A casca ja e a lista: a barra lateral tem busca, badge de tipo e contagem de membros. O que falta e o corpo dizer o que fazer.

Sao duas mudancas pequenas e um detalhe que nao e obvio: o corpo **nao** ganha botao de criar. O e2e procura `getByRole("button", { name: /novo/ })` e, com dois botoes casando, o Playwright falha por ambiguidade. O "+ novo" da barra ja e o caminho.

**Files:**
- Create: `web/src/telas/Inicio.tsx`
- Create: `web/src/telas/Inicio.test.tsx`
- Modify: `web/src/app/roteador.tsx`
- Modify: `web/e2e/fluxos.spec.ts` (um caso novo no fim)

**Interfaces:**
- Produces: `Inicio({ oQue }: { oQue: "peer" | "grupo" })`: um componente sem props de dados, sem fetch e sem navegacao propria. As rotas `peers` e `grupos` do roteador o montam; nenhuma outra tela o importa.

- [ ] **Step 1: Escrever o teste que falha**

Crie `web/src/telas/Inicio.test.tsx`:

```tsx
import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { montarRota } from "@/teste/roteador"
import { Inicio } from "./Inicio"

// A tela nao pede nada a API: ela so diz o que fazer. O `montarRota` entra aqui
// porque o que a prova fixa e a rota que a monta, e nao o componente solto.
describe("a tela de chegada", () => {
  it("convida a escolher um peer quando nada esta aberto", () => {
    montarRota([{ path: "/peers", element: <Inicio oQue="peer" /> }], "/peers")
    expect(screen.getByText(/escolha um peer ou crie um/)).toBeInTheDocument()
  })

  it("fala de grupo na rota dos grupos", () => {
    montarRota([{ path: "/grupos", element: <Inicio oQue="grupo" /> }], "/grupos")
    expect(screen.getByText(/escolha um grupo ou crie um/)).toBeInTheDocument()
  })

  it("nao oferece um segundo botao de criar", () => {
    // o "+ novo" da barra e o unico: um botao aqui deixaria ambigua a busca do
    // e2e por "novo", que roda contra a tela inteira
    montarRota([{ path: "/peers", element: <Inicio oQue="peer" /> }], "/peers")
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rodar o teste e ver falhar**

```bash
cd web && npx vitest run src/telas/Inicio.test.tsx
```

Expected: FAIL: `Failed to resolve import "./Inicio"`.

- [ ] **Step 3: Escrever o componente**

Crie `web/src/telas/Inicio.tsx`:

```tsx
/**
 * A tela de chegada de /peers e /grupos.
 *
 * A casca ja lista os registros na barra a esquerda, com busca e badge de tipo,
 * entao o corpo nao repete a lista. Ele tambem nao oferece botao de criar: o
 * "+ novo" da barra ja e esse caminho, e um segundo botao com o mesmo rotulo
 * deixaria ambigua a busca do e2e por "novo", que enxerga a tela inteira.
 */
export function Inicio({ oQue }: { oQue: "peer" | "grupo" }) {
  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold">escolha um {oQue} ou crie um</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        a lista está na barra à esquerda: clique num registro para abrir, ou use
        o "+ novo" para criar.
      </p>
    </div>
  )
}
```

O comentario fica em ASCII e o texto de tela leva acento, como no resto do
`web/`: a regra de ASCII do projeto vale para o XPL e para os comentarios de
codigo.

- [ ] **Step 4: Rodar o teste e ver passar**

```bash
cd web && npx vitest run src/telas/Inicio.test.tsx
```

Expected: PASS, 3 casos.

- [ ] **Step 5: Ligar as rotas**

Em `web/src/app/roteador.tsx`, troque o elemento das duas rotas de lista e o
indice. O arquivo fica assim (o resto nao muda):

```tsx
import { Navigate, createBrowserRouter, RouterProvider } from "react-router-dom"
import { Casca } from "./casca"
import { NaoEncontrado } from "@/telas/NaoEncontrado"
import { Inicio } from "@/telas/Inicio"
import { PeerTela, TelaDoPeer } from "@/telas/peers/PeerTela"
import { GrupoTela, TelaDoGrupo } from "@/telas/grupos/GrupoTela"
import { PrefixosTela } from "@/telas/prefixos/PrefixosTela"
import { BaseTela } from "@/telas/base/BaseTela"
import { ConfiguracoesTela } from "@/telas/configuracoes/ConfiguracoesTela"

const roteador = createBrowserRouter([
  {
    path: "/",
    element: <Casca />,
    children: [
      // Em producao quem responde / e o uvicorn, com um 307 para /peers. Com o
      // Vite na 5173 esse redirect nao existe, e sem esta rota o modo de
      // desenvolvimento documentado no README abre o NaoEncontrado
      { index: true, element: <Navigate to="/peers" replace /> },
      // A rota da lista e a da chegada, e nao um formulario em branco: quem
      // cria e /peers/novo, que e para onde o "+ novo" da barra leva
      { path: "peers", element: <Inicio oQue="peer" /> },
      { path: "peers/novo", element: <PeerTela /> },
      { path: "peers/:id", element: <TelaDoPeer /> },
      { path: "grupos", element: <Inicio oQue="grupo" /> },
      { path: "grupos/novo", element: <GrupoTela /> },
      { path: "grupos/:id", element: <TelaDoGrupo /> },
      { path: "prefixos", element: <PrefixosTela /> },
      { path: "base", element: <BaseTela /> },
      { path: "configuracoes", element: <ConfiguracoesTela /> },
      { path: "*", element: <NaoEncontrado /> },
    ],
  },
])

export function Roteador() {
  return <RouterProvider router={roteador} />
}
```

O comentario do topo do arquivo (o que explica a rota de `/peers` vir junto com
a lista) fica como esta; ele continua valendo.

A linha do indice (`Navigate`) nao tem teste automatico, e nao da para ter: o
`roteador.tsx` nao tem teste de unidade, e o e2e bate no `/` do uvicorn, onde
quem responde e o 307 do servidor. Com o Vite de pe (`npm run dev`), abrir
`http://127.0.0.1:5173/` e a conferencia.

- [ ] **Step 6: Rodar a suite do front inteira**

```bash
cd web && npm test && npm run lint
```

Expected: PASS sem tocar em nenhum teste. Cada arquivo de teste monta a propria
tabela de rotas (`montarRota(rotas, inicial)` recebe as rotas por argumento), e o
`roteador.tsx` de verdade so e exercitado pelo e2e, e por isso o caso do
Step 7 existe.

- [ ] **Step 7: O caso do e2e**

No fim de `web/e2e/fluxos.spec.ts`, acrescente:

```ts
test("a lista convida a escolher quando nada esta aberto", async ({ page }) => {
  await page.goto("/peers")
  await expect(page.getByText(/escolha um peer ou crie um/)).toBeVisible()
  await page.goto("/grupos")
  await expect(page.getByText(/escolha um grupo ou crie um/)).toBeVisible()
})
```

- [ ] **Step 8: Rodar o e2e**

```bash
cd web && npx playwright install chromium  # uma vez, se ainda nao baixou
npm run e2e
```

Expected: PASS. O caso "criar um peer do zero", que comeca em `/peers` e clica no
botao "novo" da barra, continua passando, e e ele que prova que o corpo da tela
de chegada nao tem botao nenhum com esse nome.

- [ ] **Step 9: Commit**

```bash
git add web/src/telas/Inicio.tsx web/src/telas/Inicio.test.tsx web/src/app/roteador.tsx web/e2e/fluxos.spec.ts
git commit -m "A rota da lista abre a tela de chegada, e nao um formulario em branco"
```

---

### Task 2: Os testes que faltavam

A tabela da secao "Tabela de pares" diz, para cada um dos 151 testes do
`test_app.py`, quem cobre o mesmo comportamento depois do corte. Dezoito
comportamentos nao tinham ninguem, e 22 testes do arquivo eram a unica prova
deles. Esta task escreve os dezoito (em dezessete testes: um deles cobre dois)
antes de o `test_app.py` sair, e por isso ela vem antes da Task 4.

Nenhum destes testes e de comportamento novo: todos foram medidos contra a API
de hoje, e todos passam de primeira. Eles sao caracterizacao, no sentido literal: o que a tela HTML provava passa a ser provado
pela rota que fica.

**Files:**
- Modify: `tests/test_api_peers.py` (+ `GRUPO_PARCEIROS` e `membro_de` no import)
- Modify: `tests/test_api_grupos.py` (+ `CLIENTE` no import)
- Modify: `tests/test_api.py` (+ `CLIENTE` no import)
- Modify: `web/src/telas/prefixos/PrefixosTela.test.tsx`

**Interfaces:**
- Consumes: as fixtures `api` (`tests/conftest.py`) e `fake_bgpq4`; os formularios de `tests/dados_api.py` (`CLIENTE`, `UPSTREAM`, `GRUPO_PARCEIROS`, `GRUPO_UPSTREAM`, `membro_de`).

- [ ] **Step 1: Os sete casos de peer**

Em `tests/test_api_peers.py`, troque o import do `dados_api` por:

```python
from dados_api import CLIENTE, UPSTREAM, IX, GRUPO_PARCEIROS, arvore, membro_de
```

e acrescente ao fim do arquivo:

```python
def test_trocar_o_tipo_apaga_o_bloco_do_tipo_antigo(api, tmp_path):
    """O arquivo de out/ muda de nome quando o tipo muda.

    O nome e <token>-<tipo>.txt, entao trocar o tipo deixa o bloco velho orfao
    justamente no diretorio de onde o operador cola. O irmao deste caso
    (test_trocar_o_asn_apaga_o_bloco_antigo) cobre a outra metade, o token.
    """
    assert api.post("/api/peers", json=CLIENTE).status_code == 201
    assert (tmp_path / "out" / "268127-cliente.txt").exists()

    r = api.put("/api/peers/0", json=dict(CLIENTE, tipo="upstream",
                                          aprendizado="3100", prefixos_v4=[]))

    assert r.status_code == 200, r.text
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()
    assert (tmp_path / "out" / "268127-upstream.txt").exists()


def test_o_id_escolhido_no_corpo_e_o_do_registro(api, tmp_path):
    """O id do peer novo vem do formulario quando o operador o preenche.

    O id e a identidade do registro - e o que a URL da SPA usa -, e o campo
    sempre existiu. O id implicito tem teste (test_criar_grava_o_yaml_e_o_bloco)
    e o id que move um registro no PUT tambem
    (test_trocar_o_id_no_corpo_move_o_registro_da_url); o id no POST nao.
    """
    r = api.post("/api/peers", json=dict(CLIENTE, id="7"))

    assert r.status_code == 201, r.text
    assert r.json()["registro"]["id"] == 7
    assert [p.id for p in peers_mod.carregar(tmp_path / "peers.yaml")] == [7]


def test_tipo_desconhecido_no_corpo_e_erro_no_campo(api, tmp_path):
    """O tipo do corpo e conferido, e nao cai em cliente em silencio.

    O GET /api/peers/novo?tipo=xyz cai em cliente (test_tipo_desconhecido_vira_cliente),
    e isso e outra coisa: o formulario em branco nascer com o tipo de sempre.
    Num POST, um tipo que nao existe e recusa.
    """
    r = api.post("/api/peers", json=dict(CLIENTE, tipo="xyz"))

    assert r.status_code == 422
    assert r.json()["erros"]["tipo"] == "tipo desconhecido: xyz"
    assert peers_mod.carregar(tmp_path / "peers.yaml") == []

    # e o tipo vazio nao e tipo desconhecido: campo em branco cai no cliente,
    # como os outros campos do formulario caem no default da tabela
    assert api.post("/api/peers", json=dict(CLIENTE, tipo="")).status_code == 201
    assert [p.tipo for p in peers_mod.carregar(tmp_path / "peers.yaml")] == ["cliente"]


def test_peer_com_grupo_de_outro_tipo_e_recusado_no_campo(api, tmp_path):
    """O membro tem que ser do tipo do grupo.

    A regra e do validate (test_peer_com_tipo_diferente_do_grupo_e_erro, em
    test_validate.py, olha o campo); o que faltava era a mensagem inteira
    chegando pelo campo certo na rota que o operador usa.
    """
    grupo = api.post("/api/grupos", json=GRUPO_PARCEIROS).json()["registro"]

    r = api.post("/api/peers", json=dict(UPSTREAM, grupo_id=str(grupo["id"]),
                                         nome="MEMBRO", asn="14841"))

    assert r.status_code == 422
    assert r.json()["erros"]["grupo_id"] == (
        "grupo PARCEIROS_CDN e de parceiro, nao de upstream")
    assert peers_mod.carregar(tmp_path / "peers.yaml") == []


def test_membro_sem_filtro_proprio_nao_usa_o_lp_gravado(api, tmp_path):
    """O lp_base que ficou no cadastro do membro nao entra na saida dele.

    O membro sem filtro proprio herda a politica do grupo, e o render ja tem
    teste disso (test_membro_sem_override_so_referencia_o_grupo, em
    test_render.py). O que nao tinha par era o caso do valor GRAVADO e
    ignorado: o membro herda do grupo mesmo com 999 no proprio cadastro.
    """
    grupo = api.post("/api/grupos", json=GRUPO_PARCEIROS).json()["registro"]
    corpo = membro_de(grupo["id"])
    corpo.update(nome="Membro sem filtro", apelido="MEMBRO", asn="64510",
                 lp_base="999", sessao_v4_local="198.51.100.30",
                 sessao_v4_remoto="198.51.100.31")
    membro = api.post("/api/peers", json=corpo).json()["registro"]

    bloco = api.get("/api/peers/%d/saida" % membro["id"]).json()["bloco"]

    assert [p.lp_base for p in peers_mod.carregar(tmp_path / "peers.yaml")] == [999]
    assert "999" not in bloco
    assert "apply local-preference" not in bloco
    assert "group PARCEIROS_CDN" in bloco


def test_origem_fora_da_tabela_do_tipo_grava(api, tmp_path):
    """O upstream aceita uma origem que nao esta na tabela dele.

    Isto e buraco conhecido, e nao regra: o validate confere a faixa de origem
    dos tipos downstream (ORIGENS_CLIENTE) e cobra o ORIGENS_POR_TIPO do grupo,
    nunca do peer. O bloco de um upstream com origem 14 sai carimbando
    64512:14. O teste existe para o buraco ficar visivel no dia em que alguem
    for fecha-lo - e o comentario do test_app.py que o registrava sai no corte.
    """
    r = api.post("/api/peers", json=dict(UPSTREAM, origem="14"))

    assert r.status_code == 201, r.text
    assert [p.origem for p in peers_mod.carregar(tmp_path / "peers.yaml")] == [14]


def test_origem_em_branco_cai_no_default_da_classe_e_do_tipo(api, tmp_path):
    """A origem apagada no formulario nao zera o campo: ela cai na tabela.

    No cliente e no parceiro quem manda e a classe (cgnat e 1130); no upstream,
    que nao tem classe, e a origem do tipo (1400). O formulario em branco mostra
    esse valor e tem teste (test_o_peer_novo_traz_os_defaults_do_tipo); o POST
    com o campo apagado nao tinha, e era o caminho em que a origem em branco
    estourava o "%d" do render com o peer ja gravado.
    """
    assert api.post("/api/peers", json=dict(CLIENTE, origem="", classe="cgnat")).status_code == 201
    assert api.post("/api/peers", json=dict(UPSTREAM, origem="")).status_code == 201

    assert [p.origem for p in peers_mod.carregar(tmp_path / "peers.yaml")] == [1130, 1400]
```

- [ ] **Step 2: Rodar os sete**

```bash
.venv/bin/python -m pytest tests/test_api_peers.py -q
```

Expected: PASS. Os sete casos novos e os trinta e dois que ja estavam.

- [ ] **Step 3: Os quatro casos de grupo**

Em `tests/test_api_grupos.py`, acrescente `CLIENTE` ao import do `dados_api` e o
`plan` ao do app:

```python
from app import peers as peers_mod
from app import plan
from dados_api import CLIENTE, GRUPO_PARCEIROS, GRUPO_UPSTREAM, arvore, membro_de
```

e ao fim do arquivo:

```python
def test_o_grupo_novo_pula_o_id_do_peer(api, tmp_path):
    """Peer e grupo dividem o espaco de ids, e o grupo novo desvia do peer.

    O proximo_id puro tem teste (test_proximo_id_desvia_do_peer_e_do_grupo_juntos,
    em test_peers.py); a rota que o operador usa nao tinha, e era o caso que o
    test_app.py pegava no formulario em branco do grupo.
    """
    assert api.post("/api/peers", json=CLIENTE).status_code == 201

    assert api.get("/api/grupos/novo").json()["id"] == 1


def test_criar_grupo_com_id_de_peer_e_recusado(api, tmp_path):
    """A recusa por id olha as duas listas.

    O id ja usado por outro GRUPO tem teste
    (test_criar_com_id_de_outro_grupo_e_recusado); o id de um PEER nao tinha, e
    e o caso em que a mensagem nomeia o outro tipo de registro.
    """
    api.post("/api/peers", json=CLIENTE)

    r = api.post("/api/grupos", json=dict(GRUPO_UPSTREAM, id="0", nome="OUTRO"))

    assert r.status_code == 422
    assert r.json()["erros"]["id"] == "ID 0 ja usado pelo peer Cliente ACME"
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []


def test_o_default_do_grupo_nao_engole_o_valor_zero(api, tmp_path):
    """Campo em branco cai na tabela do tipo; zero e zero; id torto nao derruba.

    Os tres sao o mesmo portao do grupo_do_formulario, e o test_app.py provava
    cada um num teste separado (o lp_base zero, o lp_base em branco e o id que
    nao e numero). O que separa os dois primeiros e o `is None` do helper: com
    `or`, o zero viraria o default do tipo em silencio.
    """
    assert api.post("/api/grupos", json=dict(GRUPO_PARCEIROS, lp_base="0")).status_code == 201
    assert api.post("/api/grupos", json=dict(GRUPO_PARCEIROS, nome="SEM_LP",
                                             lp_base="")).status_code == 201
    assert api.post("/api/grupos", json=dict(GRUPO_PARCEIROS, nome="ID_TORTO",
                                             id="abc")).status_code == 201

    grupos = peers_mod.carregar_grupos(tmp_path / "peers.yaml")
    assert [(g.nome, g.lp_base) for g in grupos] == [
        ("PARCEIROS_CDN", 0),
        ("SEM_LP", plan.LP_BASE["parceiro"]),
        ("ID_TORTO", plan.LP_BASE["parceiro"]),
    ]
    # o id torto nao virou um segundo registro no lugar de outro: os tres ids
    # sao tres e o grupo do id ilegivel entrou como registro novo
    assert len({g.id for g in grupos}) == 3


def test_valor_numerico_torto_no_grupo_e_erro_no_campo(api, tmp_path):
    """O lp_base que nao e numero nao vira default em silencio.

    A mensagem e a mesma do peer, e do lado do peer ela tem teste
    (test_api_peers.py::test_erro_de_campo_volta_422_e_nao_grava); do lado do
    grupo nao tinha depois que o test_app.py sair, apesar de serem listas de
    campos diferentes (CAMPOS_INT e CAMPOS_INT_GRUPO).
    """
    r = api.post("/api/grupos", json=dict(GRUPO_PARCEIROS, lp_base="trezentos"))

    assert r.status_code == 422
    assert r.json()["erros"]["lp_base"] == "valor numerico invalido"
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []
```

- [ ] **Step 4: Rodar os quatro**

```bash
.venv/bin/python -m pytest tests/test_api_grupos.py -q
```

Expected: PASS.

- [ ] **Step 5: Os cinco casos da rede**

Em `tests/test_api.py`, acrescente ao import:

```python
from dados_api import CLIENTE
```

e ao fim do arquivo:

```python
def test_o_as_gravado_chega_no_bloco_do_peer(api, tmp_path):
    """O AS do topo do yaml entra na config gerada, e nao so na resposta.

    test_gravar_o_as_da_rede ve a gravacao; quem via a ponta - o bloco saindo
    com o AS novo e as communities no namespace novo - era o test_app.py. O
    render tem os testes dele com um Rede montado a mao
    (test_o_bloco_do_peer_segue_o_asn_declarado); o que faltava era o caminho
    HTTP inteiro.
    """
    assert api.put("/api/rede", json={"asn": "64500", "politica": ""}).status_code == 200

    r = api.post("/api/peers", json=CLIENTE)

    assert r.status_code == 201, r.text
    bloco = (tmp_path / "out" / r.json()["arquivo"]).read_text(encoding="ascii")
    assert "bgp 64500" in bloco
    assert "64500:1110" in bloco
    assert "64512" not in bloco


def test_o_as_de_32_bits_com_namespace_chega_no_bloco(api, tmp_path):
    """As duas chaves: o ASN no bgp e no as-path, o namespace nas communities."""
    assert api.put("/api/rede", json={"asn": "264130", "politica": "64500"}).status_code == 200
    corpo = dict(CLIENTE, asn="264130", nome="Cliente 32", apelido="C32",
                 prefixos_v4=["198.51.100.0/24"],
                 sessao_v4_remoto="198.51.100.9")

    r = api.post("/api/peers", json=corpo)

    assert r.status_code == 201, r.text
    bloco = (tmp_path / "out" / r.json()["arquivo"]).read_text(encoding="ascii")
    assert "bgp 264130" in bloco
    assert "apply as-path 264130" in bloco
    assert "64500:1110" in bloco
    assert "264130:1110" not in bloco


def test_o_namespace_em_branco_apaga_a_chave(api, tmp_path):
    """Voltar para um AS de 16 bits limpa o asn_politica do yaml.

    A funcao tem teste (test_gravar_asn_limpa_o_namespace_que_a_tela_nao_mandou,
    em test_peers.py); a rota nao tinha.
    """
    arquivo = tmp_path / "peers.yaml"
    api.put("/api/rede", json={"asn": "264130", "politica": "64500"})
    assert "asn_politica" in arquivo.read_text(encoding="utf-8")

    r = api.put("/api/rede", json={"asn": "64500", "politica": ""})

    assert r.status_code == 200, r.text
    assert "asn_politica" not in arquivo.read_text(encoding="utf-8")


def test_o_as_fora_da_faixa_do_asn_e_erro_de_campo(api, tmp_path):
    """AS_TRANS e o que passa do teto de 32 bits caem no campo asn_rede.

    O ASN que nao e digito tem teste (test_asn_torto_e_recusado_no_campo); as
    duas faixas de valor, nao.
    """
    r = api.put("/api/rede", json={"asn": "23456", "politica": ""})
    assert r.status_code == 422
    assert r.json()["erros"]["asn_rede"] == "ASN reservado pela IANA: 23456"

    r = api.put("/api/rede", json={"asn": "99999999999", "politica": ""})
    assert r.status_code == 422
    assert r.json()["erros"]["asn_rede"] == "ASN de 1 a 4294967294: 99999999999"

    # a recusa e antes da escrita: o arquivo fica com o AS de fabrica
    assert peers_mod.carregar_asn(tmp_path / "peers.yaml").asn == plan.ASN_PADRAO


def test_o_as_em_branco_e_erro_de_campo(api, tmp_path):
    """Sem o AS nao ha o que gravar, e o namespace sozinho nao salva o campo."""
    for corpo in ({"asn": "", "politica": ""}, {"asn": "", "politica": "64500"}):
        r = api.put("/api/rede", json=corpo)
        assert r.status_code == 422, corpo
        assert r.json()["erros"]["asn_rede"] == "informe o AS da rede"

    assert not (tmp_path / "peers.yaml").exists()
```

- [ ] **Step 6: Rodar os cinco**

```bash
.venv/bin/python -m pytest tests/test_api.py -q
```

Expected: PASS.

- [ ] **Step 7: O texto que a consulta falhada nao apaga**

O unico dos dezoito que nao e de rota: a API de hoje devolve so o erro quando o
bgpq4 falha (o `_falha` monta `erros` e `avisos`, sem `v4`/`v6`), entao quem
segura o texto do operador e o estado do editor. A tela do Jinja redesenhava o
formulario com o que ele tinha digitado, e era isso que o
`test_bgpq4_fora_do_ar_nao_perde_a_lista_do_operador` provava.

Em `web/src/telas/prefixos/PrefixosTela.test.tsx`, junto dos outros casos de
IRR:

```tsx
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
```

- [ ] **Step 8: Rodar o caso do front**

```bash
cd web && npx vitest run src/telas/prefixos/PrefixosTela.test.tsx
```

Expected: PASS, 21 casos.

- [ ] **Step 9: Rodar a suite inteira**

```bash
.venv/bin/python -m pytest -q
cd web && npm test
```

Expected: PASS nos dois. O `test_app.py` continua no lugar e continua verde: ele
nao foi tocado, e as rotas que ele exercita ainda existem.

- [ ] **Step 10: Commit**

```bash
git add tests/test_api_peers.py tests/test_api_grupos.py tests/test_api.py web/src/telas/prefixos/PrefixosTela.test.tsx
git commit -m "O que so a tela provava passa a ter prova na API e no front"
```

---

- [ ] **Step 4: Tirar do `conftest.py` o que nao existe mais**

Em `tests/conftest.py`, a fixture `api` perde as duas linhas do modulo do app e
o `OUT`. O corpo fica:

```python
    monkeypatch.setattr(peers_mod, "PEERS_YAML", tmp_path / "peers.yaml")
    monkeypatch.setattr(peers_mod, "OUT", tmp_path / "out")
    monkeypatch.setattr(render, "OUT", tmp_path / "out")
    monkeypatch.setattr(prefixes, "CACHE", tmp_path / "out" / ".cache")
    return TestClient(mod.app)
```

A docstring da fixture muda junto: ela dizia que "o app.app guardou uma copia do
caminho no import", e a copia deixou de existir.

- [ ] **Step 5: `tests/test_web.py`**

Tres mudancas:

**(a)** A docstring do modulo perde a frase "As telas HTML antigas continuam em
`/`, `/peer/...` e `/grupo/...` ate o corte." e passa a dizer que a SPA e o
unico front.

**(b)** `test_as_telas_antigas_continuam_no_ar` sai e entra, no lugar dela:

```python
def test_a_raiz_leva_para_a_spa(web):
    """O HEALTHCHECK do Dockerfile bate em / esperando 200.

    O 200 nao vem mais da raiz: vem do /peers que o 307 aponta, e o urllib
    segue redirect por padrao. Este caso fixa o primeiro elo da corrente; o
    segundo e o test_as_rotas_da_spa_servem_o_index_do_build.
    """
    r = web.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/peers"
    # e, seguindo o redirect, o que o healthcheck ve: o index do build
    assert web.get("/").status_code == 200


def test_as_telas_do_singular_saem_do_ar(web):
    """As telas antigas moravam em /peer/... e /grupo/..., no singular.

    Depois do corte elas nao existem: o 404 e o que prova que a SPA nao passou
    a responde-las - um curinga que engolisse o singular devolveria o index.
    """
    for rota in ("/peer/novo", "/peer/268127", "/saida/268127",
                 "/grupo/novo", "/grupo/PARCEIROS", "/saida/grupo/PARCEIROS"):
        r = web.get(rota, follow_redirects=False)
        assert r.status_code == 404, rota
        assert "id=root" not in r.text
```

**(c)** `test_a_rota_da_spa_nao_engole_a_do_peer_de_verdade` sai: ela comparava
o singular das telas com o plural da SPA, e o singular nao existe mais. O que
ela protegia - a SPA nao engolir a rota de verdade - passou a ser o caso acima.

O comentario do `test_o_favicon_sai_da_raiz_do_build` que diz "um curinga
engoliria as telas antigas do singular, que moram em /peer/... e /grupo/..."
fica sem essa justificativa; a rota continua sendo de um arquivo so, e nao um
curinga da raiz do build.

- [ ] **Step 6: `tests/test_isolamento.py`**

A fixture `cliente` perde os dois patches no modulo do app:

```python
@pytest.fixture
def cliente(out, monkeypatch):
    """O app apontando para o mesmo tmp_path que o `out` ja patcheia.

    O CACHE do bgpq4 entra pelo mesmo motivo do test_app: sem o patch, uma
    consulta de verdade escreveria out/.cache/ no repositorio.
    """
    monkeypatch.setattr(mod, "PEERS_YAML", out / "peers.yaml")
    monkeypatch.setattr(prefixes, "CACHE", out / ".cache")
    return TestClient(servidor.app)
```

E `test_excluir_grupo_com_membro_e_recusado_sem_tocar_em_arquivo` passa a bater
na API, que e quem sabe excluir grupo agora. O corpo do teste continua o mesmo
ate a chamada; o que muda e a chamada e a leitura da recusa:

```python
    r = cliente.delete("/api/grupos/%d" % grupo.id)

    assert r.status_code == 409
    assert "CLIENTEA" in r.json()["erros"]["membros"]
    assert "CLIENTEB" in r.json()["erros"]["membros"]
    assert [g.nome for g in mod.carregar_grupos(out / "peers.yaml")] == [
        "PARCEIROS_CDN"]
    # a recusa nao pode deixar rastro: nem o yaml, nem a saida do grupo,
    # nem a dos membros mudam de byte
    assert _retrato(out) == antes

    # os membros saem do grupo por fora (nao ha tela para isso ainda, ver
    # "Fora do escopo deste plano" do plano): so entao a exclusao passa
    mod.gravar([], out / "peers.yaml")
    antes = _retrato(out)

    r = cliente.delete("/api/grupos/%d" % grupo.id)

    assert r.status_code == 204
```

O resto do teste (a comparacao do retrato do disco, o arquivo do grupo que
some, a saida dos membros que fica byte a byte) fica como esta.

- [ ] **Step 7: `tests/test_formulario.py`**

Saem o import `from app import app as mod` e o
`test_os_helpers_moram_no_formulario_e_o_app_reexporta` (o unico teste que
existia por causa dos reexports). A docstring do modulo, que hoje diz "os
helpers que a tela HTML e a API dividem", passa a dizer que sao os da API.

- [ ] **Step 8: Rodar a suite do Python**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS. Se algo quebrar aqui, o mais provavel e um teste que ainda
aponta para uma rota que saiu; o traceback diz qual.

- [ ] **Step 9: Regerar o contrato do front**

Os caminhos das telas HTML entram hoje no `app.openapi()` (nenhum deles tinha
`include_in_schema=False`), entao o `web/src/api/schema.d.ts` versionado menciona
`/peer`, `/grupo`, `/saida`, `/asn`, `/bgpq4` e `/blocos`. Sem regerar, o
`tests/test_tipos_api.py`, que roda `npm run api:conferir`, fica vermelho.

```bash
cd web && npm run api:tipos && git diff --stat src/api/schema.d.ts
```

Expected: o diff tira 16 caminhos (`/asn`, `/bgpq4`, `/blocos`, `/blocos/bgpq4`,
`/grupo`, `/grupo/novo`, `/grupo/{nome}`, `/grupo/{nome}/excluir`, `/peer`,
`/peer/novo`, `/peer/{token}`, `/peer/{token}/excluir`, `/saida/{token}`,
`/saida/{token}/criar-lista`, `/saida/grupo/{nome}`,
`/saida/grupo/{nome}/criar-lista`) e mexe em um: o `/`, que era uma resposta
HTML e virou um 307. Ficam os 18 caminhos de `/api/...` e o `/base.txt`, que
nao mudou.

- [ ] **Step 10: Rodar tudo**

```bash
.venv/bin/python -m pytest -q
cd web && npm test && npm run lint && npm run api:conferir
```

Expected: PASS nos quatro. O `api:conferir` e o que fecha a Task: ele compara o
`schema.d.ts` com o `app.openapi()` de agora, e passa so porque o Step 9 rodou.

- [ ] **Step 11: Rodar o e2e e acrescentar o caso da raiz**

Em `web/e2e/fluxos.spec.ts`, junto do caso criado na Task 1:

```ts
test("a raiz cai na lista", async ({ page }) => {
  await page.goto("/")
  await expect(page).toHaveURL(/\/peers$/)
  await expect(page.getByText(/escolha um peer ou crie um/)).toBeVisible()
})
```

```bash
cd web && npm run e2e
```

Expected: PASS. Este caso e o unico que exercita o 307 do uvicorn com um
navegador de verdade: o `webServer` do Playwright sobe o uvicorn servindo o
`web/dist`.

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "As telas Jinja saem, e a raiz passa a levar para a SPA"
```

---

### Task 3: O `/base.txt` sobrevive em `tests/test_base.py`

O `/base.txt` e a unica rota que o corte nao tira, e hoje ela so tem prova dentro
do `test_app.py` (os casos `test_download_do_bloco_base`,
`test_baixar_o_base_nao_grava_arquivo`, `test_o_base_baixado_e_o_render_de_agora`
e a assercao de `/base.txt` do `test_o_as_gravado_chega_na_config_gerada`). Como
o arquivo inteiro sai na Task 4, estes quatro vao para um arquivo proprio antes
disso, sem reescrita, so a fixture: a `cliente` do `test_app.py` faz o mesmo
trabalho que a `api` do `conftest.py`.

**Files:**
- Create: `tests/test_base.py`

**Interfaces:**
- Consumes: a fixture `api` de `tests/conftest.py` (TestClient do app com `peers.yaml`, `out/` e o cache do bgpq4 em `tmp_path`).

- [ ] **Step 1: Escrever o arquivo**

Crie `tests/test_base.py`:

```python
"""O bloco base, servido em /base.txt.

Estes quatro casos vieram do tests/test_app.py, que sai no corte das telas
Jinja: /base.txt nao e HTML, nao muda com o corte, e era o unico lugar onde
ela tinha prova.
"""

from app import render


def test_download_do_bloco_base(api):
    r = api.get("/base.txt")
    assert r.status_code == 200
    assert "IMPORT-SANITY-V4" in r.text
    assert r.text.isascii()


def test_baixar_o_base_nao_grava_arquivo(api, tmp_path):
    # e o que o README promete: o corpo e montado na hora do download, entao
    # nao ha arquivo em out/ guardando uma versao antiga para o operador
    # conferir se esta desatualizada
    api.get("/base.txt")
    assert not (tmp_path / "out" / "_base.txt").exists()


def test_o_base_baixado_e_o_render_de_agora(api):
    # sem AS no peers.yaml o Rede e o de fabrica, e as duas pontas saem do
    # mesmo plan.py
    assert api.get("/base.txt").text == render.render_base()


def test_o_base_segue_o_as_gravado(api):
    # o caminho de ponta a ponta do PUT /api/rede: o AS vai para o topo do
    # yaml, e a proxima leitura do base ja sai com ele, sem reiniciar o app
    assert api.put("/api/rede",
                   json={"asn": "64500", "politica": ""}).status_code == 200
    texto = api.get("/base.txt").text
    assert "64500:1000" in texto
    assert "64512:" not in texto
```

As duas assercoes do ultimo caso foram medidas no render de agora: com o AS
64500, o base traz as informativas com o namespace novo (`64500:1000`) e nao
tem nenhum `64512:`. O unico `64512` que sobra no texto e o `[64512..65534]`
da faixa de AS privado, que nao tem dois pontos depois e nao colide com esta
asserção.

- [ ] **Step 2: Rodar**

```bash
.venv/bin/python -m pytest tests/test_base.py -v
```

Expected: PASS, 4 casos.

- [ ] **Step 3: Commit**

```bash
git add tests/test_base.py
git commit -m "O /base.txt ganha o arquivo de teste que ele vai herdar"
```

---

### Task 4: O corte

Aqui as telas Jinja saem e a SPA fica sozinha. Sao sete arquivos de uma vez, e
eles tem que sair juntos: enquanto as rotas HTML existirem, o `test_app.py` tem
o que exercitar; quando elas saem, ele e o `pagina.html` viram arquivo morto no
mesmo instante. Por isso e uma task so, e nao sete.

O `app.py` encolhe para o que ele ainda serve. O que sai dele:

| Sai | Por que |
| --- | --- |
| as rotas `/`, `/peer/novo`, `/peer/{token}`, `POST /peer`, `POST /peer/{token}/excluir`, `/saida/{token}`, `/saida/{token}/criar-lista`, `POST /asn`, `POST /bgpq4`, `POST /blocos`, `POST /blocos/bgpq4` | telas Jinja |
| as rotas `/grupo/novo`, `/grupo/{nome}`, `POST /grupo`, `POST /grupo/{nome}/excluir`, `/saida/grupo/{nome}`, `/saida/grupo/{nome}/criar-lista` | telas Jinja |
| `Jinja2Templates`, `templates`, `templates.env...` | as telas eram os unicos usuarios; o XPL sai do `render.py`, que monta o proprio ambiente |
| `_contexto`, `_contexto_grupo`, `lista`, `lista_grupos` | so as rotas acima chamavam |
| o reexport de `app/formulario.py` (22 nomes) | a API importa do `formulario.py` direto |
| os imports que ficam sem uso: `Request`, `plan`, `prefixes`, `validate`, `Peer`, `Grupo`, `Bloco` | idem |
| `OUT = peers_mod.OUT` | nao era lido nem hoje |

O que fica: `rede()`, `/base.txt`, o build do front (`SEM_BUILD`, `_dir_web`,
`pagina_spa`, `/assets`, `/favicon.svg`), as rotas da SPA e a API.

E o `rede()` muda de fonte: ele passa a ler `peers_mod.PEERS_YAML` em vez de uma
copia que o `app.py` guardava no import. Era a copia que os testes trocavam por
`monkeypatch`, e com uma fonte so os tres `monkeypatch.setattr(app.app, ...)`
das fixtures saem junto.

**Files:**
- Modify: `app/app.py` (reescrito)
- Delete: `templates/pagina.html`, `templates/pagina_grupo.html`, `templates/_estilo.html`, `templates/_copiar.html`
- Delete: `tests/test_app.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_web.py`
- Modify: `tests/test_isolamento.py`
- Modify: `tests/test_formulario.py`
- Modify: `web/src/api/schema.d.ts` (regerado por `npm run api:tipos`)

**Interfaces:**
- Produces: `app.app` com `app`, `rede()`, `baixar_base()`, `_dir_web()`, `pagina_spa()`, `assets_do_build()`, `favicon_do_build()` e `raiz()`. As fixtures de teste passam a tocar so `peers_mod.PEERS_YAML`, `peers_mod.OUT`, `render.OUT` e `prefixes.CACHE`.

- [ ] **Step 1: Reescrever o `app/app.py`**

O arquivo inteiro passa a ser:

```python
"""Rotas do app.

O uvicorn e o unico processo: ele serve a API em /api, o bloco base em
/base.txt, os arquivos do build do front em /assets e o index.html da SPA nas
rotas dela. A raiz leva para a SPA. Sem banco: o estado e o peers.yaml.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import (FileResponse, HTMLResponse, PlainTextResponse,
                               RedirectResponse)

from app import api, render
from app import peers as peers_mod

RAIZ = Path(__file__).resolve().parent.parent

app = FastAPI(title="bgpgen")

# a API JSON em /api, que a SPA consome
api.instalar(app)


def rede():
    """O plan.Rede do AS declarado no topo do peers.yaml.

    Sai do arquivo a cada requisicao, como as outras leituras: o operador grava
    o AS no topo e recarrega, sem reiniciar o app. Sem a chave no arquivo o
    Rede e o de fabrica, e a config gerada e a de sempre.

    Le o PEERS_YAML do peers.py, e nao uma copia daqui: era a copia que os
    testes trocavam por monkeypatch, e com uma fonte so o modulo do app nao
    tem mais estado de arquivo nenhum.
    """
    return peers_mod.carregar_asn(peers_mod.PEERS_YAML)


@app.get("/base.txt", response_class=HTMLResponse)
def baixar_base():
    # texto puro, e nao HTML: e o mesmo corpo de antes do corte, montado na
    # hora do download (nao ha arquivo em out/ com uma versao antiga dele)
    return HTMLResponse(render.render_base(rede=rede()), media_type="text/plain")


# --- o build do front (SPA) -------------------------------------------
#
# Em producao ha um processo so: o uvicorn serve a API em /api, os arquivos do
# build em /assets e o index.html da SPA nas rotas dela. O diretorio do build
# vem de BGPGEN_WEB, e o padrao e web/dist na raiz do projeto.
#
# O caminho e lido a cada requisicao, e nao no import: os testes o trocam, como
# fazem com o PEERS_YAML.

SEM_BUILD = ("front nao compilado: rode `npm run build` em `web/` "
             "ou use o Vite na 5173")


def _dir_web():
    return Path(os.environ.get("BGPGEN_WEB", str(RAIZ / "web" / "dist")))


def pagina_spa():
    """O index.html do build, ou o 503 que explica como compila-lo."""
    index = _dir_web() / "index.html"
    if not index.is_file():
        return PlainTextResponse(SEM_BUILD, status_code=503)
    return FileResponse(index)


@app.get("/assets/{caminho:path}", include_in_schema=False)
def assets_do_build(caminho: str):
    raiz = _dir_web() / "assets"
    # o caminho resolvido tem que continuar dentro do diretorio: sem isto um
    # /assets/../../peers.yaml levaria o cadastro embora
    alvo = (raiz / caminho).resolve()
    if not alvo.is_file() or raiz.resolve() not in alvo.parents:
        raise HTTPException(status_code=404)
    return FileResponse(alvo)


@app.get("/favicon.svg", include_in_schema=False)
def favicon_do_build():
    """O icone do build, que o Vite deixa na raiz do dist e nao em /assets.

    O index.html gerado linka /favicon.svg, entao sem esta rota o navegador
    pede um arquivo que ninguem serve, mesmo com o build inteiro no lugar. E
    um arquivo so, e nao um curinga da raiz do build.
    """
    alvo = _dir_web() / "favicon.svg"
    if not alvo.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(alvo)


@app.get("/")
def raiz():
    """A raiz leva para a lista da SPA.

    O 307 e temporario de proposito: um 308 ficaria no cache do navegador do
    operador, e voltar atras viraria limpeza de cache. Quem segue o redirect
    sem pensar e o HEALTHCHECK do Dockerfile, que bate em / desde antes deste
    corte e continua lendo 200 no fim da corrente (o /peers servido pelo build).
    """
    return RedirectResponse("/peers", status_code=307)


# As rotas da SPA.
#
# Fora do openapi(): elas devolvem o index.html, nao JSON, e nao acrescentam
# nada ao contrato que o front consome. Como o web/src/api/schema.d.ts e
# gerado do app.openapi(), deixa-las dentro mexeria no schema por uma rota que
# nao e da API - o test_tipos_api.py pega isso na hora.
for _rota in ("/peers", "/grupos", "/prefixos", "/base", "/configuracoes"):
    app.add_api_route(_rota, pagina_spa, methods=["GET"],
                      include_in_schema=False)
for _rota in ("/peers", "/grupos"):
    app.add_api_route(_rota + "/{caminho:path}", pagina_spa, methods=["GET"],
                      include_in_schema=False)
```

Os comentarios de `assets_do_build`, `favicon_do_build`, `pagina_spa` e das
rotas da SPA sao os que ja estavam no arquivo: nao ha o que reescrever neles,
so o comentario do favicon, que citava as telas antigas do singular, perde
essa frase.

- [ ] **Step 2: Apagar os quatro templates das telas**

```bash
git rm templates/pagina.html templates/pagina_grupo.html templates/_estilo.html templates/_copiar.html
```

O `templates/_macros.j2` e os `.j2` de bloco **nao** entram nesta lista: quem os
le e o `render.py`, e eles continuam gerando o XPL.

- [ ] **Step 3: Apagar o `tests/test_app.py`**

```bash
git rm tests/test_app.py
```

O que ele protegia esta na tabela da secao "Tabela de pares": o que tem par
saiu com par, o que nao tinha virou teste na Task 2, e o `/base.txt` ja mora em
`tests/test_base.py` desde a Task 3.

---

### Task 5: Documentacao

O `README.md` e o `CLAUDE.md` descrevem um app que nao existe mais depois da
Task 4: os dois falam das telas Jinja. O resto do repositorio, inclusive o
`Dockerfile` e o `compose.yaml`, continua valendo, e so os comentarios que
citavam as telas mudam.

O `CLAUDE.md` e em ingles e o `README.md` e em portugues; e a unica parte deste
plano em que o texto final nao esta escrito aqui inteiro, porque o que muda sao
frases dentro de secoes que continuam existindo. O Step 1 traz as frases exatas.

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `Dockerfile` (um comentario)
- Modify: `compose.yaml` (um comentario)

- [ ] **Step 1: O `README.md`**

Seis trechos mudam. Os textos abaixo sao o que fica no lugar.

**(a)** Depois da primeira frase (a que apresenta o gerador), entra a mencao a
SPA:

```
Gera o bloco XPL de uma sessão BGP do AS64512 a partir de um formulário, mais
um bloco base com os sets e filtros que todas as sessões compartilham. A tela é
uma SPA em `web/`, servida pelo próprio FastAPI.
```

**(b)** A abertura de "O que é" (hoje "A tela lista os peers e traz o formulário
ao lado...") e o parágrafo sobre a SPA em `/peers` viram:

```
A SPA lista os peers na barra da esquerda e abre cada um num formulário. Salvo o
formulário, o app escreve o bloco daquela sessão em `out/<token>-<tipo>.txt`,
sobrescrevendo só esse arquivo: gerar um peer não toca na saída dos outros. O
bloco base, que é igual para todos, sai em `GET /base.txt`.

Por baixo dela o app serve uma API JSON em `/api`, que é quem fala com o
`peers.yaml`: a SPA não reimplementa regra nenhuma, e o parsing, a validação e o
render continuam no Python. A raiz (`/`) leva para `/peers`, e a documentação
interativa da API fica em `/docs`. A prévia (`POST /api/peers/previa`) monta o
bloco sem gravar nada. O desenho está em
`docs/superpowers/specs/2026-09-26-front-spa-design.md`.
```

**(c)** No "Como subir" com Docker, a linha da tela:

```
A tela fica em http://127.0.0.1:8765/, que cai em `/peers`. O `compose.yaml`
monta o checkout em `/app`, então o `peers.yaml` e o `out/` são os do
repositório, e editar um template de bloco vale na hora.
```

**(d)** Em "O front (SPA)", a primeira frase deixa de dizer "a tela nova", e o
comentario do comando do uvicorn passa a dizer o que ele serve:

```
A tela é uma SPA em `web/`, servida pelo próprio FastAPI. Em produção não há
processo separado: o uvicorn serve a API, os arquivos do build e o `index.html`.
```

```bash
.venv/bin/uvicorn app.app:app --port 8000      # a API e a SPA
```

**(e)** Ainda em "O front (SPA)", o paragrafo do build perde a mencao as telas
antigas:

```
O diretório do build vem de `BGPGEN_WEB`, e o padrão é `web/dist`. Sem build, as
rotas da SPA respondem 503 com a instrução de compilar; a API continua
funcionando.
```

**(f)** Em "Testes do front", a contagem do e2e: os dois casos novos (o da lista
vazia, da Task 1, e o da raiz, da Task 4) levam o arquivo de 10 para 12 casos:

```bash
npm run e2e             # Playwright: compila e roda os 12 casos contra um uvicorn (8 fluxos + 4 de copia)
```

- [ ] **Step 2: O `CLAUDE.md`**

A linha do "Repository overview" que descreve o app vira:

```
This repository holds a design document, `PLANO.md`, specifying the BGP communities policy for AS64512 and its implementation in XPL (Huawei VRP's policy language) on the NetEngine 8000 F1A, plus the app that implements it: `app/` (FastAPI, serving the JSON API under `/api`, the generated blocks in `out/` and the SPA build) and `web/` (the React SPA the operator uses; `templates/` holds only the Jinja templates that render the XPL blocks). The document is written in Portuguese. The suite is `pytest` for Python and `vitest` for the front; the commands are in the `README.md`.
```

O resto do arquivo nao muda: as regras de ASCII, a convencao numerica e as
tabelas do `PLANO.md` continuam valendo.

- [ ] **Step 3: Os comentarios do `Dockerfile` e do `compose.yaml`**

No `Dockerfile`, o comentario do `HEALTHCHECK` (o que diz que o proprio python
responde se a tela esta de pe) ganha a segunda metade da frase:

```
# sem curl na imagem slim: o proprio python responde se a tela esta de pe. O /
# responde 307 para /peers desde o corte das telas HTML, e o urlopen segue o
# redirect sozinho: quem devolve o 200 e o index.html do build
```

No `compose.yaml`, o comentario dos volumes fala de "editar template": os
templates que restam sao os dos blocos XPL:

```
      # O checkout inteiro entra no lugar do que a imagem copiou. Assim o
      # peers.yaml e o out/ sao os mesmos do repositorio, editar um template de
      # bloco vale na hora e o bloco gerado aparece no disco da maquina para
      # colar no F1A. Apagar esta linha congela a imagem.
```

- [ ] **Step 4: Conferir que nada quebrou**

```bash
.venv/bin/python -m pytest -q
cd web && npm test && npm run lint && npm run api:conferir
```

Expected: PASS nos quatro.

- [ ] **Step 5: Atualizar o grafo do graphify e commitar**

O grafo de `graphify-out/` descreve o repositorio, e o corte mexeu em 8 arquivos
e apagou 6. O `CLAUDE.md` do usuario manda manter o grafo em dia depois de mexer
no codigo.

```bash
graphify update .
git add README.md CLAUDE.md Dockerfile compose.yaml graphify-out
git commit -m "O README e o CLAUDE.md descrevem o app sem as telas Jinja"
```

---

## Tabela de pares

O `tests/test_app.py` sai inteiro (Task 4). Os 151 testes dele estao abaixo, um
por linha, com o que cada um protegia e quem passou a proteger aquilo. Tres
grupos:

- **sem par**: o teste so conferia marcacao (id de elemento, classe, `onclick`,
  `datalist`, nome de template). A marcacao deixa de existir, e nao ha
  comportamento por baixo para provar;
- **com par**: o comportamento continua provado, por um teste da API, do front,
  ou de um dos arquivos de unidade que ficam (`test_render.py`, `test_validate.py`,
  `test_peers.py`, `test_plan.py`, `test_isolamento.py`, `test_formulario.py`);
- **lacuna**: o comportamento nao tinha prova nenhuma depois do corte. Os
  dezessete viraram teste na Task 2, e a coluna diz o nome do teste novo.

Vale a distincao que aparece em varias linhas: o que o `test_app.py` cobria era o
**caminho HTTP** (a rota, a gravacao, o redirect), e a **regra** costuma ter
prova propria nos arquivos de unidade, que ficam. Nesses casos o par e a regra, e
a rota ganha teste novo so quando ela tambem e comportamento, como o
`/api/rede` que muda o bloco gerado.

Numero de ordem = a posicao do teste no arquivo, que e a ordem em que o
inventario que gerou esta tabela os leu.

### A. Saem sem par (39)

| # | teste | o que ele conferia |
| --- | --- | --- |
| 1 | `test_a_tela_comeca_vazia` | `GET /` com "nenhum peer" no corpo |
| 2 | `test_a_tela_tem_lista_e_formulario` | os `id="lista"` e `id="formulario"` da tela |
| 14 | `test_a_caixa_da_default_route_nasce_desmarcada_e_chega_no_yaml` | a metade de marcacao: o `name="default_route"` na pagina (a metade de comportamento tem par: #14b em "com par") |
| 16 | `test_o_formulario_de_grupo_novo_nao_reusa_o_id_de_um_peer` | `value="1"` no campo id do formulario (a regra por baixo virou teste novo: ver #16 em "lacunas") |
| 18 | `test_o_formulario_de_um_tipo_novo_vem_com_os_defaults_da_tabela` | `value="1500000"` e o nome do campo de timer na pagina |
| 21 | `test_o_cliente_e_o_maior_lp_dos_tipos` | o `<script id="padroes">` da tela |
| 22 | `test_o_bloco_da_cascata_e_a_tabela_do_plano` | a metade de marcacao: o `<script id="padroes">` existir (a metade de comportamento tem par: #22b em "com par") |
| 23 | `test_a_cascata_esta_ligada_nos_dois_selects` | `addEventListener("change", cascata)`, `input[list]`, `list="d-..."` |
| 25 | `test_o_pop_ja_cadastrado_vira_sugestao` | o `<datalist id="d-pop">` e as `<option>ja cadastrado</option>` |
| 26 | `test_o_painel_de_saida_tem_as_duas_abas` | `data-aba="criar"` e `data-aba="remover"` |
| 27 | `test_o_painel_de_saida_tem_botao_de_copiar` | `onclick="copiar(...)"` e o `<script>` do `_copiar.html` |
| 31 | `test_o_painel_do_cliente_e_do_upstream_tem_o_link_do_quadro` | o href do link do quadro na pagina de saida |
| 43 | `test_a_tela_nao_avisa_sobre_o_base` | "ainda nao gerado" e "desatualizado" fora da pagina |
| 44 | `test_a_tela_nao_avisa_nem_com_um_base_velho_no_disco` | idem, com um `out/_base.txt` envelhecido |
| 53 | `test_a_tela_devolve_as_communities_gravadas` | o eco das communities na `<textarea>` |
| 64 | `test_a_saida_do_grupo_de_upstream_oferece_o_quadro_ao_criar` | o href `/saida/grupo/.../criar-lista` |
| 65 | `test_a_saida_do_grupo_de_ix_nao_oferece_o_quadro` | a ausencia do mesmo href |
| 66 | `test_a_saida_do_grupo_de_parceiro_nao_oferece_o_quadro` | idem |
| 73 | `test_grupo_novo_e_grupo_editar_respondem` | dois `GET` de pagina respondendo 200 |
| 81 | `test_o_lp_base_do_grupo_novo_acompanha_o_tipo` | `value=` do campo lp_base no formulario em branco |
| 82 | `test_o_aprendizado_do_grupo_novo_nasce_cheio` | `value="3100"` e `value="3010"` no formulario em branco |
| 83 | `test_o_tipo_sem_ponto_de_aprendizado_nao_ganha_numero` | o mesmo campo vazio nos tres tipos |
| 85 | `test_o_aprendizado_do_peer_novo_nasce_cheio_tambem` | idem, na tela do peer |
| 86 | `test_o_aprendizado_gasto_por_um_grupo_e_sugestao_no_peer` | a `<option>ja cadastrado</option>` na tela do peer |
| 87 | `test_a_tela_do_grupo_sugere_o_aprendizado_ja_cadastrado` | o `datalist` do aprendizado e suas options |
| 88 | `test_o_formulario_de_grupo_oferece_os_cinco_tipos` | as `<option>` do select de tipo |
| 89 | `test_o_select_de_origem_do_grupo_so_oferece_a_lista_do_tipo` | as `<option>` do select de origem |
| 91 | `test_nenhum_id_da_tela_do_grupo_se_repete` | unicidade dos `id="..."` da pagina |
| 92 | `test_o_grupo_marca_os_campos_por_tipo` | o atributo `data-para` |
| 93 | `test_a_tela_do_grupo_mostra_o_bh_upstream_gravado` | o `value=` do campo bh_upstream |
| 94 | `test_o_campo_do_bh_upstream_do_grupo_tem_onde_mostrar_o_erro` | sem par: o teste renderizava `pagina_grupo.html` na mao e fabricava o erro `bh_upstream` que ele procurava, e nenhuma validacao produz essa chave |
| 110 | `test_o_cabecalho_mostra_o_as_de_fabrica` | "AS64512" e `value="64512"` no cabecalho |
| 116 | `test_a_recusa_devolve_os_dois_campos_digitados` | os dois `value=` do cabecalho depois da recusa (o front guarda o digitado, e isso tem prova em `configuracoes/ConfiguracoesTela.test.tsx`: "o que o operador digita nao e apagado pelo dado que chega depois") |
| 117 | `test_sem_recusa_o_campo_mostra_o_que_esta_gravado` | os `value=` do cabecalho com o que esta no yaml |
| 143 | `test_a_pagina_tem_a_secao_dos_blocos` | `id="blocos"`, `name="blocos_v4"`, `action="/blocos"` |
| 144 | `test_a_secao_mostra_o_que_esta_salvo` | o conteudo da `<textarea>` dos blocos |
| 146 | `test_o_botao_de_consultar_manda_o_forcar` | o href `/blocos/bgpq4?forcar=1` |
| 147 | `test_a_secao_nao_quebra_a_pagina_sem_bloco` | a secao existir com o cadastro vazio |
| 148 | `test_o_alerta_do_topo_leva_ao_campo_do_bloco` | o `href="#f-blocos_v4"` do alerta |

### B. Saem com par (111)

| # | teste | par |
| --- | --- | --- |
| 3 | `test_salvar_cria_o_peer_e_o_arquivo` | `test_api_peers::test_criar_grava_o_yaml_e_o_bloco`; a lista ganhando o peer: e2e "criar um peer do zero" |
| 5 | `test_salvar_com_erro_na_grava_arquivo` | `test_api_peers::test_erro_de_campo_volta_422_e_nao_grava` |
| 8 | `test_origem_digitada_vence_o_default` | qualquer teste da API que grave com origem preenchida (o valor volta no yaml) |
| 9 | `test_o_parceiro_salva_como_cliente_e_sai_com_a_marca` | `test_render.py::test_o_parceiro_difere_do_cliente_so_no_cabecalho_e_na_marca` e `::test_a_marca_do_parceiro_so_entra_no_import` + `test_api_peers::test_criar_grava_o_yaml_e_o_bloco` |
| 10 | `test_origem_fora_da_faixa_volta_com_erro_na_tela` | `test_validate.py::test_community_fora_da_faixa_e_erro` (origem 1700 no cliente) |
| 11 | `test_prefixo_de_te_malformado_volta_com_erro_na_tela` | `test_validate.py` (prefixo de TE invalido) |
| 12 | `test_prefixo_de_te_valido_salva_normalmente` | `test_render.py` (a linha de TE no bloco) |
| 13 | `test_desmarcar_bfd_chega_no_yaml` | `test_peers.py::test_round_trip_do_yaml` (o par bfd/graceful_restart atravessa o yaml) |
| 14b | `test_a_caixa_da_default_route...` (metade de comportamento) | `test_peers.py::test_default_route_atravessa_o_yaml` |
| 15 | `test_o_formulario_deixa_escolher_o_id` | **lacuna** → `test_api_peers::test_o_id_escolhido_no_corpo_e_o_do_registro` |
| 17 | `test_salvar_grupo_com_id_de_peer_e_recusado` | **lacuna** → `test_api_grupos::test_criar_grupo_com_id_de_peer_e_recusado` |
| 19 | `test_o_formulario_novo_vem_com_a_origem_da_tabela` | `test_api_peers::test_o_peer_novo_traz_os_defaults_do_tipo` + `test_plan.py` (as tabelas `ORIGEM` e `ORIGEM_CLASSE`) |
| 20 | `test_o_select_de_origem_so_oferece_a_lista_do_tipo` | `test_api.py::test_o_plano_traz_as_tabelas_do_plan_sem_copia` (`origens_por_tipo`) + `web/src/lib/campos.test.ts` (a cascata) |
| 22b | `test_o_bloco_da_cascata_e_a_tabela_do_plano` (metade de comportamento) | `test_formulario.py::test_o_bloco_da_cascata_e_a_tabela_do_plano`, acrescentado na revisao final: o payload que a SPA le para se preencher bate com o `plan.py`, e o `test_api.py` so comparava `_padroes` com `_padroes` |
| 24 | `test_a_origem_gravada_fora_da_tabela_nao_e_trocada_em_silencio` | a metade de comportamento (grava) → **lacuna** → `test_api_peers::test_origem_fora_da_tabela_do_tipo_grava`; a de exibicao (a option com a nota) e marcacao, e sai |
| 28 | `test_a_aba_de_criacao_nao_leva_undo` | `test_api_peers::test_a_saida_traz_bloco_remocao_e_quadro` (o bloco e a remocao sao respostas separadas) |
| 29 | `test_o_quadro_ao_criar_o_peer_mostra_a_lista_vazia` | `test_api_peers::test_o_quadro_ao_criar_so_sai_nos_tipos_com_cl_peer` |
| 30 | `test_o_quadro_ao_criar_o_peer_nao_e_servido_para_ix_e_pni` | idem, o lado em que o quadro e `None` |
| 32 | `test_tipo_desconhecido_volta_com_erro_na_tela` | **lacuna** → `test_api_peers::test_tipo_desconhecido_no_corpo_e_erro_no_campo` |
| 33 | `test_tipo_vazio_no_post_cai_no_cliente` | **lacuna** → o mesmo teste novo, na segunda metade |
| 34 | `test_editar_existente_nao_duplica` | `test_api_peers::test_salvar_o_que_o_get_devolveu_nao_muda_nada` + `test_trocar_o_id_no_corpo_move_o_registro_da_url` |
| 35 | `test_post_sem_a_identidade_nao_sobrescreve_o_peer_do_asn` | `test_api_peers::test_asn_repetido_e_recusado_no_campo` |
| 36 | `test_trocar_o_asn_renomeia_o_peer_sem_duplicar` | `test_api_peers::test_trocar_o_asn_apaga_o_bloco_antigo` |
| 37 | `test_excluir_tira_da_lista_e_apaga_o_arquivo` | `test_api_peers::test_excluir_apaga_o_registro_e_o_bloco` |
| 38 | `test_excluir_sem_confirmar_nao_apaga` | `web/src/telas/peers/PeerTela.test.tsx` ("o cancelar do dialogo nao exclui nada", acrescentado na revisao final: a confirmacao saiu do servidor e virou dialogo, entao o que prova que nada e apagado sem o sim e o cancelar nao mandar DELETE) |
| 39 | `test_o_bloco_de_remocao_deixa_a_community_list_do_peer_comentada` | `test_render.py` (o bloco de remocao, com a `CL-PEER` comentada) |
| 40 | `test_o_bloco_de_remocao_poe_o_undo_peer_antes_dos_undo_xpl` | `test_render.py::test_remover_traz_o_undo_na_ordem_que_o_vrp_aceita` |
| 41 | `test_o_cliente_nao_leva_undo_de_noadv_por_peer` | `test_render.py` (o remover do cliente) |
| 42 | `test_gerar_o_peer_b_nao_muda_a_saida_do_a` | `test_isolamento.py::test_gerar_b_nao_muda_a_saida_de_a` |
| 45 | `test_download_do_bloco_base` | `tests/test_base.py::test_download_do_bloco_base` (Task 3) |
| 46 | `test_baixar_o_base_nao_grava_arquivo` | `tests/test_base.py::test_baixar_o_base_nao_grava_arquivo` (Task 3) |
| 47 | `test_o_base_baixado_e_o_render_de_agora` | `tests/test_base.py::test_o_base_baixado_e_o_render_de_agora` (Task 3) |
| 48 | `test_consultar_o_irr_preenche_os_prefixos` | `test_api.py::test_o_irr_devolve_os_prefixos_sem_gravar` + `web/src/telas/peers/PeerTela.test.tsx` ("a consulta ao IRR escreve os prefixos no formulario") |
| 49 | `test_o_botao_atualizar_ignora_o_cache` | `test_api.py::test_o_irr_devolve_os_prefixos_sem_gravar` (o `forcar` vai no corpo) |
| 50 | `test_consultar_sem_asn_nao_chama_o_bgpq4` | `test_api.py::test_irr_sem_asn_e_recusado_no_campo` |
| 51 | `test_uma_coleta_que_falha_nao_apaga_os_prefixos_digitados` | `test_api.py::test_irr_sem_bgpq4_volta_502` + `web/src/telas/peers/PeerTela.test.tsx` (a falha nao apaga o bloco) |
| 52 | `test_o_formulario_grava_as_communities_da_cl_peer` | `test_api_peers::test_o_registro_traz_o_formulario_do_peer` + `test_modelos_api.py` (round-trip das listas) |
| 54 | `test_o_quadro_ao_criar_o_peer_traz_a_lista_do_cadastro` | `test_api_peers::test_a_saida_traz_bloco_remocao_e_quadro` |
| 55 | `test_community_invalida_e_erro_no_campo_e_nao_grava` | `test_validate.py::test_community_fora_da_sintaxe_e_erro` + `test_api_peers::test_erro_de_campo_volta_422_e_nao_grava` |
| 56 | `test_community_fora_da_faixa_do_plano_grava_com_aviso` | `test_api_peers::test_asn_privado_salva_com_aviso` (o formato do aviso) |
| 57 | `test_o_aviso_da_community_fora_da_faixa_chega_na_tela` | idem (o aviso sai no corpo da resposta) |
| 58 | `test_criar_grupo_grava_no_yaml` | `test_api_grupos::test_criar_grupo_grava_o_yaml_e_o_bloco` |
| 59 | `test_criar_grupo_com_erro_nao_grava` | `test_api_grupos::test_nome_repetido_e_recusado` |
| 60 | `test_grupo_com_prefixo_malformado_nao_grava_nem_derruba_a_saida` | `test_validate.py::test_grupo_prefixo_malformado_e_erro` (a recusa acontece antes de qualquer gravacao) |
| 61 | `test_grupo_com_asn_reservado_nao_grava` | `test_validate.py::test_grupo_asn_fora_da_faixa_ou_reservado_e_erro` |
| 62 | `test_excluir_grupo_exige_confirmacao` | `test_api_grupos::test_excluir_grupo_sem_membro` (a API nao pede `confirmado`; quem confirma e o dialogo) + `web/src/telas/grupos/GrupoTela.test.tsx` |
| 63 | `test_saida_do_grupo_mostra_o_bloco` | `test_api_grupos::test_a_saida_do_grupo` |
| 67 | `test_a_rota_do_quadro_ao_criar_do_grupo_de_parceiro_redireciona` | `test_api_grupos::test_o_grupo_de_parceiro_nao_tem_quadro` |
| 68 | `test_a_rota_do_quadro_ao_criar_do_grupo_serve_a_lista` | `test_api_grupos::test_a_previa_do_grupo_e_o_bloco_que_o_salvar_escreve` |
| 69 | `test_a_rota_do_quadro_ao_criar_do_grupo_de_ix_redireciona` | `test_api_grupos::test_o_grupo_de_parceiro_nao_tem_quadro` (o `criar_lista` nulo) |
| 70 | `test_a_rota_do_quadro_ao_criar_de_grupo_inexistente_redireciona` | `test_api_grupos::test_grupo_que_nao_existe_e_404` |
| 71 | `test_o_quadro_ao_criar_do_grupo_nao_vira_rota_de_peer` | `test_api_peers::test_o_quadro_ao_criar_so_sai_nos_tipos_com_cl_peer` (o quadro do grupo sai pelo id do grupo) |
| 72 | `test_editar_grupo_sem_renomear_nao_grava_erro_de_duplicata` | `test_api_grupos::test_editar_mantem_o_id_da_url` |
| 74 | `test_o_formulario_do_grupo_traz_bfd_e_timers` | `test_api_grupos::test_salvar_o_que_o_get_do_grupo_devolveu_nao_muda_nada` (os campos do grupo atravessam a gravacao) + `test_validate.py::test_grupo_timer_pela_metade_e_erro` |
| 75 | `test_grupo_editar_inexistente_redireciona` | `test_api_grupos::test_grupo_que_nao_existe_e_404` |
| 76 | `test_excluir_grupo_inexistente_redireciona` | idem |
| 77 | `test_id_nao_numerico_no_post_de_grupo_nao_derruba` | **lacuna** → `test_api_grupos::test_o_default_do_grupo_nao_engole_o_valor_zero` |
| 78 | `test_valor_numerico_torto_no_grupo_volta_com_erro` | **lacuna** → `test_api_grupos::test_valor_numerico_torto_no_grupo_e_erro_no_campo` |
| 79 | `test_lp_base_zero_no_grupo_nao_vira_o_default` | **lacuna** → `test_api_grupos::test_o_default_do_grupo_nao_engole_o_valor_zero` |
| 80 | `test_lp_base_em_branco_cai_no_default_do_tipo` | **lacuna** → o mesmo teste novo |
| 84 | `test_o_aprendizado_do_grupo_novo_pula_o_que_ja_existe` | `test_api_grupos::test_o_grupo_novo_de_ix_poe_o_aprendizado_no_campo_do_ix` + `test_peers.py` (o proximo numero livre) |
| 90 | `test_a_origem_do_grupo_fora_da_tabela_nao_e_trocada_em_silencio` | `test_validate.py` (a origem do ix fora da lista, com a mensagem) |
| 95 | `test_salvar_grupo_de_upstream_grava_os_campos_do_tipo` | `test_api_grupos::test_salvar_o_que_o_get_do_grupo_devolveu_nao_muda_nada` (os campos atravessam a gravacao) + `test_modelos_api.py` (round-trip do grupo) |
| 96 | `test_o_bh_upstream_do_grupo_atravessa_dois_salvarios` | idem |
| 97 | `test_grupo_com_aprendizado_torto_volta_com_erro` | `test_validate.py` (o aprendizado do grupo) |
| 98 | `test_o_aprendizado_torto_no_grupo_vira_erro_de_campo` | idem |
| 99 | `test_o_bloco_escondido_nao_apaga_o_aprendizado_do_bloco_visivel` | `test_modelos_api.py::test_o_aprendizado_do_grupo_de_ix_vai_no_campo_do_ix` (o campo do bloco do tipo e quem vale) |
| 100 | `test_o_aprendizado_vem_do_bloco_do_tipo_escolhido` | idem |
| 101 | `test_o_erro_de_prefixo_do_grupo_ancora_num_campo_de_todo_tipo` | `test_validate.py::test_grupo_prefixo_malformado_e_erro` (o erro sai no campo `prefixos`; o que era da tela era a ancora do link) |
| 102 | `test_a_ancora_do_aprendizado_acompanha_o_bloco_do_tipo_da_tela` | `web/src/lib/campos.test.ts` (o alvo do erro por tipo) |
| 103 | `test_salvar_peer_com_grupo_grava_grupo_id` | `test_api_peers::test_o_registro_traz_o_formulario_do_peer` (o `grupo_id` no registro) + `test_render.py` (o `group` no bloco do membro) |
| 104 | `test_membro_com_asn_diferente_do_grupo_volta_com_erro` | `test_validate.py::test_membro_com_asn_diferente_do_grupo_e_erro` |
| 105 | `test_peer_de_upstream_membro_de_grupo_de_upstream_grava` | `test_validate.py::test_membro_com_o_mesmo_asn_do_grupo_passa` + `test_render.py` (o `group` no bloco) |
| 106 | `test_peer_de_upstream_com_grupo_de_outro_tipo_volta_com_o_erro` | `test_validate.py::test_peer_com_tipo_diferente_do_grupo_e_erro`; a mensagem inteira na rota → **lacuna** → `test_api_peers::test_peer_com_grupo_de_outro_tipo_e_recusado_no_campo` |
| 107 | `test_excluir_grupo_com_membro_e_recusado` | `test_api_grupos::test_excluir_grupo_com_membro_e_recusado_sem_mexer_em_nada` + `test_isolamento.py` (reescrito na Task 4 para a rota da API) |
| 108 | `test_saida_de_membro_com_o_grupo_sumido_nao_estoura` | `test_api_peers::test_a_saida_de_membro_de_grupo_que_saiu_e_recusada` |
| 109 | `test_a_tela_avisa_que_o_membro_sem_filtro_nao_usa_os_campos_de_politica` | a metade de comportamento → **lacuna** → `test_api_peers::test_membro_sem_filtro_proprio_nao_usa_o_lp_gravado` + `test_render.py` (o membro so referencia o grupo); a metade de marcacao (a tag e a legenda) sai |
| 111 | `test_gravar_o_as_grava_a_chave_no_topo` | `test_api.py::test_gravar_o_as_da_rede` |
| 112 | `test_o_as_gravado_chega_na_config_gerada` | a metade do bloco do peer → **lacuna** → `test_api.py::test_o_as_gravado_chega_no_bloco_do_peer`; a metade do `/base.txt` → `tests/test_base.py::test_o_base_segue_o_as_gravado` (Task 3) |
| 113 | `test_o_as_de_32_bits_com_namespace_grava_as_duas_chaves` | **lacuna** → `test_api.py::test_o_as_de_32_bits_com_namespace_chega_no_bloco` |
| 114 | `test_o_as_de_32_bits_sem_namespace_e_recusado_sem_estragar_o_arquivo` | `test_api.py::test_asn_de_32_bits_pede_o_namespace_no_campo_dele` |
| 115 | `test_o_namespace_fora_dos_16_bits_e_erro_no_proprio_campo` | `test_plan.py` (a faixa do namespace) + `test_api.py` (o erro sai no campo `asn_politica`) |
| 118 | `test_o_as_fora_da_faixa_do_asn_e_erro_de_campo` | **lacuna** → `test_api.py::test_o_as_fora_da_faixa_do_asn_e_erro_de_campo` |
| 119 | `test_o_namespace_em_branco_apaga_a_chave` | **lacuna** → `test_api.py::test_o_namespace_em_branco_apaga_a_chave` |
| 120 | `test_o_as_fora_de_digitos_e_erro_de_campo` | `test_api.py::test_asn_torto_e_recusado_no_campo` |
| 121 | `test_o_as_vazio_e_erro_de_campo` | **lacuna** → `test_api.py::test_o_as_em_branco_e_erro_de_campo` |
| 122 | `test_o_namespace_sem_o_as_e_erro_de_campo` | **lacuna** → o mesmo teste novo |
| 123 | `test_o_as_nao_salva_o_peer_que_estava_aberto` | `test_api.py::test_gravar_o_as_da_rede` (a gravacao do AS nao toca na lista de peers) + `test_api_peers` (a arvore do disco) |
| 124 | `test_o_formulario_le_uma_linha_por_prefixo` | `test_api_blocos.py::test_salvar_grava_o_yaml_e_o_out` + `test_formulario.py` (a tabela de campos) |
| 125 | `test_linha_fora_de_servico_fica_no_cadastro_marcada` | `test_api_blocos.py::test_fora_de_servico_fica_no_texto_e_so_sai_na_remocao` |
| 126 | `test_a_marca_do_ausente_nao_vira_community` | `test_api_blocos.py::test_o_irr_mescla_e_marca_o_ausente_sem_gravar` |
| 127 | `test_o_texto_do_formulario_volta_marcado` | `test_api_blocos.py::test_o_irr_mescla_e_marca_o_ausente_sem_gravar` (o texto de volta com a marca) |
| 128 | `test_salvar_blocos_grava_no_yaml` | `test_api_blocos.py::test_salvar_grava_o_yaml_e_o_out` |
| 129 | `test_salvar_blocos_escreve_o_arquivo_da_ordem_de_colagem` | idem (`out/blocos.txt`) |
| 130 | `test_o_arquivo_do_bloco_nao_leva_o_prefixo_fora_de_servico` | `test_api_blocos.py::test_fora_de_servico_fica_no_texto_e_so_sai_na_remocao` |
| 131 | `test_o_bloco_recusado_nao_escreve_o_arquivo` | `test_api_blocos.py::test_prefixo_torto_e_recusado_sem_gravar` |
| 132 | `test_salvar_blocos_com_community_que_ninguem_le_nao_grava` | idem (a recusa por community) |
| 133 | `test_prefixo_fora_do_irr_salva_igual` | `test_api_blocos.py::test_salvar_grava_o_yaml_e_o_out` |
| 134 | `test_a_reconsulta_nao_grava_o_yaml` | `test_api_blocos.py::test_o_irr_mescla_e_marca_o_ausente_sem_gravar` |
| 135 | `test_prefixo_torto_nao_derruba_a_tela` | `test_api_blocos.py::test_prefixo_torto_e_recusado_sem_gravar` |
| 136 | `test_a_reconsulta_com_prefixo_torto_tambem_nao_derruba` | `test_api_blocos.py::test_o_irr_com_prefixo_torto_recusa_antes_de_consultar` |
| 137 | `test_o_prefixo_e_canonizado_no_formulario` | `test_api_blocos.py::test_salvar_grava_o_yaml_e_o_out` (o prefixo canonico no yaml) |
| 138 | `test_a_linha_com_dois_pontos_guarda_o_tratamento` | `test_api_blocos.py::test_fora_de_servico_fica_no_texto_e_so_sai_na_remocao` |
| 139 | `test_o_fora_de_servico_nao_entra_na_saida` | idem |
| 140 | `test_endereco_sem_barra_e_recusado` | `test_api_blocos.py::test_prefixo_torto_e_recusado_sem_gravar` |
| 141 | `test_o_remover_cobre_o_prefixo_fora_de_servico` | `test_api_blocos.py::test_o_irr_mescla_e_marca_o_ausente_sem_gravar` (o `remover` cobre o cadastro inteiro) |
| 142 | `test_a_saida_nao_sai_no_caminho_de_erro` | `test_api_blocos.py::test_a_previa_com_prefixo_torto_volta_o_erro` (a previa com erro nao traz bloco) |
| 145 | `test_a_secao_mostra_a_saida_depois_de_salvar` | `test_api_blocos.py::test_salvar_grava_o_yaml_e_o_out` |
| 149 | `test_a_reconsulta_preserva_o_tratamento_do_prefixo_que_ficou` | `test_api_blocos.py::test_o_irr_mescla_e_marca_o_ausente_sem_gravar` |
| 150 | `test_a_reconsulta_marca_o_prefixo_que_sumiu` | idem (a marca do ausente) |
| 151 | `test_bgpq4_fora_do_ar_nao_perde_a_lista_do_operador` | **lacuna** → `web/src/telas/prefixos/PrefixosTela.test.tsx` ("o texto digitado fica onde esta quando a consulta ao IRR falha") |

### C. Lacunas fechadas pela Task 2

Esta tabela nao soma com as duas de cima: ela reune, por comportamento, os 22
testes que a Task 2 fecha (18 comportamentos, porque quatro deles cobrem dois ou
tres testes cada). Vinte e um aparecem em B marcados como lacuna, e o 16 aparece
em A. Os outros tres numeros (4, 6 e 7) nao estao em tabela nenhuma das duas: o
comportamento deles nao tinha par nenhum depois do corte.

| # | comportamento | teste novo |
| --- | --- | --- |
| 4 | trocar o tipo apaga o bloco do tipo antigo | `test_api_peers::test_trocar_o_tipo_apaga_o_bloco_do_tipo_antigo` |
| 6, 7 | origem em branco cai no default da classe (cgnat → 1130) e do tipo (upstream → 1400) | `test_api_peers::test_origem_em_branco_cai_no_default_da_classe_e_do_tipo` |
| 15 | o id escolhido no corpo e o id do registro | `test_api_peers::test_o_id_escolhido_no_corpo_e_o_do_registro` |
| 16 | o grupo novo pula o id que um peer ocupa | `test_api_grupos::test_o_grupo_novo_pula_o_id_do_peer` |
| 17 | grupo com o id de um peer e recusado, nomeando o peer | `test_api_grupos::test_criar_grupo_com_id_de_peer_e_recusado` |
| 24 | origem fora da tabela do tipo grava | `test_api_peers::test_origem_fora_da_tabela_do_tipo_grava` |
| 32 | tipo desconhecido no corpo e erro de campo | `test_api_peers::test_tipo_desconhecido_no_corpo_e_erro_no_campo` |
| 33 | tipo em branco no POST cai no cliente | idem, na segunda metade |
| 77, 79, 80 | lp_base zero nao vira default, lp_base em branco vira, id torto nao derruba | `test_api_grupos::test_o_default_do_grupo_nao_engole_o_valor_zero` |
| 78 | lp_base que nao e numero e erro no campo dele | `test_api_grupos::test_valor_numerico_torto_no_grupo_e_erro_no_campo` |
| 106 | grupo de outro tipo: a mensagem inteira no campo da rota | `test_api_peers::test_peer_com_grupo_de_outro_tipo_e_recusado_no_campo` |
| 109 | membro sem filtro proprio ignora o lp_base gravado | `test_api_peers::test_membro_sem_filtro_proprio_nao_usa_o_lp_gravado` |
| 112 | o AS gravado chega no bloco do peer | `test_api.py::test_o_as_gravado_chega_no_bloco_do_peer` |
| 113 | ASN de 32 bits com namespace chega no bloco | `test_api.py::test_o_as_de_32_bits_com_namespace_chega_no_bloco` |
| 118 | ASN reservado e ASN acima do teto caem no campo asn_rede | `test_api.py::test_o_as_fora_da_faixa_do_asn_e_erro_de_campo` |
| 119 | namespace em branco apaga a chave do yaml | `test_api.py::test_o_namespace_em_branco_apaga_a_chave` |
| 121, 122 | asn em branco (com ou sem namespace) e erro de campo | `test_api.py::test_o_as_em_branco_e_erro_de_campo` |
| 151 | o texto digitado sobrevive a uma consulta ao IRR que falha | `web/src/telas/prefixos/PrefixosTela.test.tsx` |

**Como as tres tabelas se somam.** Os 151 testes estao em A ou em B: 39 saem sem
par, 111 saem com par. O 14 e o 22 aparecem nos dois, porque cada um tinha as
duas metades: a marcacao sai, o comportamento fica (e o par do 22 so apareceu na
revisao final). Os outros tres (4, 6 e 7) nao tem par nenhum: eles eram a unica
prova dos seus comportamentos, e por isso a Task 2 teve que escrever teste novo
para eles antes de o arquivo sair.

Nada nestas tabelas foi conferido de memoria: cada "com par" saiu de um grep ou
de uma leitura do teste citado, e cada "lacuna" foi medida rodando a API antes de
o teste novo ser escrito.

---

## Fechamento

Ao fim das cinco tasks o bgpgen tem um front so: a raiz leva para `/peers`, as
telas Jinja e o `test_app.py` nao existem mais, e o `app.py` serve a API, o
`/base.txt` e o build.

O que **nao** muda e a parte que a spec chama de "o que nao entra": nenhuma linha
de `plan.py`, `validate.py`, `render.py`, `peers.py`, `prefixes.py`, `api.py` ou
`modelos_api.py`; nenhum byte da saida gerada; nenhuma mensagem do `validate.py`
(continuam em ASCII); nenhuma autenticacao ou edicao simultanea.

O que fica em aberto, e vale registrar:

- **A tela de lista nao entra.** A Task 1 faz o que a spec nomeia para `/peers`: a casca com a lista na barra e um estado vazio no corpo. Se o operador quiser
  uma tabela no corpo, com ASN e grupo em coluna, isso e uma tela nova, e nao
  este corte.
- **O buraco da origem no upstream continua aberto.** O peer de upstream aceita
  `origem` fora da tabela do tipo, e o bloco sai carimbando o que o operador
  digitou. A Task 2 deixa o caso medido e testado, e nao consertado: fechar isso
  mexe no `validate.py`, que a spec poe fora do corte.
- **O grafo do graphify so fica em dia na Task 5.** Entre a Task 4 e ela, o
  `graphify-out/` descreve um repositorio que mudou.
- **O e2e e o unico que exercita o 307 com um navegador.** Os testes do
  `test_web.py` fixam o cabecalho com o TestClient; quem segue o redirect de
  verdade e o Playwright e o HEALTHCHECK do container.

---
