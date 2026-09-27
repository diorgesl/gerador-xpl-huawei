# Pendências do front e do app Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar as pendencias que as tres etapas do front deixaram registradas: as perguntas de produto que ninguem respondeu, os minors adiados das telas, os do e2e e os comentarios que o corte tornou obsoletos.

**Architecture:** Uma leva so, agrupada por area. O backend muda uma funcao (`validate.avisos`) e nada mais; o front conserta a raiz de dois defeitos (`camposDoErro` deixando de inventar campo, e a aba ativa subindo para a tela) e o resto e acabamento local; o e2e ganha typecheck, globais certos e a medicao do Safari.

**Tech Stack:** Python 3.14, FastAPI, pytest; React 19, Vite, TypeScript estrito, Tailwind, Vitest com Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-27-pendencias-do-front-design.md` (secoes "Decisoes do brainstorming", "Comportamento", "Front", "e2e", "Testes").

**Planos das etapas anteriores (ja executados):** `2026-09-26-api-json.md`, `2026-09-26-front-spa.md` e `2026-09-27-corte-das-telas-html.md`. As pendencias desta leva estao registradas no fim dos dois ultimos.

## Mapa das tasks

| # | Task | Entrega |
| --- | --- | --- |
| 1 | O aviso de origem | `validate.avisos` avisa quando a origem do peer nao esta na tabela do tipo, sem bloquear |
| 2 | `camposDoErro` nao inventa campo | chave que nao e campo deixa de fechar o painel e de prometer link |
| 3 | O id do grupo rebusca o id livre | a recusa por `id` deixa de ser beco sem saida |
| 4 | Todos os avisos de um campo | o campo mostra as N linhas de aviso, e nao so a primeira |
| 5 | A aba ativa sobe para a tela | "copiar o bloco aberto" copia a aba da tela, nas tres telas |
| 6 | O resumo leva a secao | chave que cobre varios campos leva ao topo da secao, e nao ao primeiro campo |
| 7 | O retry do `Falha` | botao "tentar de novo" desabilita enquanto o refetch corre |
| 8 | O tema com marca acessivel | `aria-pressed` no botao do tema escolhido |
| 9 | Dois consertos pequenos | o `_corpo` dos prefixos e o comentario do harness |
| 10 | e2e | aspas, typecheck, globais de Node, a copia provando o bloco, e a medicao do Safari |
| 11 | Comentarios e registro | os comentarios obsoletos e onde cada pendencia foi fechada |
| 12 | O erro de token | a colisao de token aponta o apelido quando e o apelido que colide |
| 13 | O campo que invade a coluna | o select de valor longo para de pintar por cima do vizinho |
| 14 | As sobras da tela dos prefixos | o recado do IRR deixa de mostrar o `_corpo`, e o caso da Task 9 espera o registro antes de clicar |

## Global Constraints

- **A saida gerada nao muda um byte.** `plan.py`, `render.py`, `peers.py`, `prefixes.py`, `api.py` e `modelos_api.py` nao sao tocados, e os templates `.j2` de XPL tambem nao. O unico arquivo de regra que muda e `validate.py`, e so no `avisos` (que nao entra na geracao).
- **A mudanca de validacao e aviso, nao erro.** Nada que hoje salva passa a ser recusado nesta leva.
- **ASCII no XPL e nos comentarios de codigo.** As mensagens do `validate.py` continuam em ASCII, como estao.
- **`peers.yaml` e o cadastro real do operador**: ele nao entra em commit e nao e editado por esta leva.
- **Uma worktree por plano**, e o merge no checkout principal fica com o operador.
- **A suite inteira verde em cada task**: `.venv/bin/python -m pytest -q`, e no `web/` `npm test`, `npm run lint` e `npm run api:conferir`.

## Review Focus

O que a spec pede mas nenhum teste de task exercita sozinho:

1. **O aviso que so aparece no cadastro velho.** O `_origem_padrao` devolve valor dentro da tabela, entao peer novo e copia nascem sem aviso: quem ve o aviso e o cadastro que ja existia. Um teste que so cria peer novo nao prova nada sobre esta leva, e por isso a Task 1 escreve o caso do peer gravado com origem fora da tabela.
2. **A chave de erro que ainda pode fechar o painel.** A Task 2 faz `camposDoErro` devolver `[]` para chave que nao e campo, mas quem fecha o painel e o `comErro` de `PeerTela`/`GrupoTela`, que so olha o tamanho da lista. O teste tem que ser do painel, e nao da funcao pura.
3. **A aba ativa e a previa que demora.** O callback sobe a aba no clique, mas o `blocoAberto` que a paleta publica tem que acompanhar o *conteudo* da aba, e nao o id: uma previa que ainda nao chegou nao pode fazer a paleta copiar o bloco de outra aba.
4. **O Safari do "salvar e copiar".** A task do e2e mede, e o resultado pode ser "o WebKit recusou": nesse caso o socorro de dois cliques entra no mesmo commit, e o caso passa a assertar o fluxo de dois cliques no WebKit.
5. **O typecheck do e2e pode achar o que ninguem viu.** Ao ligar `playwright.config.ts` e `e2e/` no `tsc`, e provavel que apareca erro de tipo em codigo que nunca foi checado. Eles entram no mesmo commit, e o plano nao autoriza `any` nem `@ts-expect-error` para silenciar.

---

### Task 1: O aviso de origem

O peer so confere a origem nos tipos downstream, e confere a *faixa* 1xxx (`validate.py:612-613`); em `upstream`, `ix` e `pni` nao ha conferencia nenhuma. O grupo, no mesmo arquivo, confere contra a tabela do proprio tipo (`validate.py:442-447`) e o codigo registra a assimetria como mudanca separada (`validate.py:438-441`). Esta task e essa mudanca, e ela vem como aviso: recusar trancaria BRDIGITAL (1120), ALT (1100) e VIAMS (1100), tres upstreams do cadastro real, e mudar a origem deles muda a community que sai no bloco.

**Files:**
- Modify: `app/validate.py` (funcao `avisos`, perto da linha 68)
- Test: `tests/test_validate.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `plan.ORIGENS_POR_TIPO` e `plan.TIPOS_DOWNSTREAM`.
- Produces: um `validate.Erro("origem", mensagem)` a mais na lista de `avisos(peer, peers, rede)`. Nada muda em `validar` nem no envelope da API, que ja carrega `avisos`.

- [ ] **Step 1: Escrever o teste que falha**

No fim de `tests/test_validate.py`, com os helpers que o arquivo ja tem (`um_peer`, `campos`):

```python
def test_origem_fora_da_tabela_do_tipo_e_aviso_nos_tipos_sem_conferencia():
    """O peer de upstream/ix/pni nao confere a origem contra a tabela do tipo.

    O grupo confere (validar_grupo), e o peer so olha a faixa 1xxx, e so nos
    tipos downstream. A assimetria esta registrada no proprio codigo como
    mudanca separada, e esta e ela: aviso, e nao erro, porque fechar trancaria
    cadastro que ja existe (tres upstreams do peers.yaml real).
    """
    for tipo, permitidas in (("upstream", (1400, 1000, 1900)),
                             ("ix", (1300, 1200, 1000, 1900)),
                             ("pni", (1500, 1200, 1000, 1900))):
        fora = validate.avisos(um_peer(tipo=tipo, origem=1100), [])
        assert [e.campo for e in fora] == ["origem"], tipo
        assert "nao esta na tabela do %s" % tipo in fora[0].mensagem
        assert str(permitidas[0]) in fora[0].mensagem

        dentro = validate.avisos(um_peer(tipo=tipo, origem=permitidas[0]), [])
        assert dentro == [], (tipo, "origem da tabela nao pode avisar")


def test_origem_no_downstream_nao_ganha_aviso_novo():
    """Nos downstream a faixa 1xxx ja e erro no validar, e nao aviso aqui."""
    for origem in (1100, 1120):
        assert validate.avisos(um_peer(tipo="cliente", origem=origem), []) == []
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
.venv/bin/python -m pytest tests/test_validate.py -q -k origem_fora_da_tabela
```

Expected: FAIL, porque hoje `avisos` devolve lista vazia para esse peer.

- [ ] **Step 3: Escrever o aviso**

Em `app/validate.py`, dentro de `avisos`, logo depois do aviso do `route_limit` (antes do `_avisa_communities`):

```python
    # O grupo confere a origem contra a tabela do proprio tipo e o peer nao
    # (o peer so olha a faixa 1xxx, e so nos tipos downstream). O resultado e
    # um upstream com origem de cliente, que carimba a rota mentindo sobre a
    # procedencia. Aqui e aviso, e nao erro: fechar isso trancaria cadastro
    # que ja existe no peers.yaml, e trocar a origem desses peers e decisao de
    # rede, nao de app (spec 2026-09-27, "Por que a origem vira aviso").
    if peer.tipo not in plan.TIPOS_DOWNSTREAM:
        permitidas = plan.ORIGENS_POR_TIPO.get(peer.tipo, ())
        if peer.origem is not None and permitidas and peer.origem not in permitidas:
            saida.append(Erro(
                "origem",
                "origem %d nao esta na tabela do %s: o plano usa %s"
                % (peer.origem, peer.tipo,
                   ", ".join(str(o) for o in permitidas))))
```

- [ ] **Step 4: Rodar e ver passar**

```bash
.venv/bin/python -m pytest tests/test_validate.py -q -k origem
```

Expected: PASS, os dois casos novos e os que ja falavam de origem.

- [ ] **Step 5: O aviso chegando pela rota**

No fim de `tests/test_api.py`, com `UPSTREAM` acrescentado ao import do `dados_api`
(o arquivo importa so `CLIENTE` hoje):

```python
from dados_api import CLIENTE, UPSTREAM
```

E os dois casos:

```python
def test_o_aviso_de_origem_fora_da_tabela_chega_no_upstream(api, tmp_path):
    """O aviso de origem sai no envelope, e o peer grava assim mesmo.

    O peer de upstream do cadastro real carrega origem de downstream; o que
    esta leva faz e o operador ver isso, e nao impedir o salvar.
    """
    r = api.post("/api/peers", json=dict(UPSTREAM, origem="1100"))

    assert r.status_code == 201, r.text
    assert [a["campo"] for a in r.json()["avisos"]] == ["origem"]
    assert "nao esta na tabela do upstream" in r.json()["avisos"][0]["mensagem"]
    assert [p.origem for p in peers_mod.carregar(tmp_path / "peers.yaml")] == [1100]


def test_a_origem_da_tabela_nao_avisa(api):
    # o peer em branco e a copia nascem com a origem do default, que esta
    # dentro da tabela: quem ve o aviso e o cadastro antigo, e nao o novo
    corpo = api.get("/api/peers/novo", params={"tipo": "upstream"}).json()
    r = api.post("/api/peers", json=dict(UPSTREAM, origem=corpo["formulario"]["origem"]))

    assert r.status_code == 201, r.text
    assert r.json()["avisos"] == []
```

- [ ] **Step 6: Rodar a suite do Python**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS. Se o `test_o_peer_novo_traz_os_defaults_do_tipo` ou outro caso de aviso quebrar, e porque a guarda `peer.tipo not in plan.TIPOS_DOWNSTREAM` deixou passar um tipo a mais.

- [ ] **Step 7: Commit**

```bash
git add app/validate.py tests/test_validate.py tests/test_api.py
git commit -m "A origem fora da tabela do tipo vira aviso no peer"
```

---

### Task 2: `camposDoErro` nao inventa campo

`campos.ts` trata qualquer chave fora de `SEM_CAMPO` como nome de campo (`campos.ts:130`). E isso que faz uma chave que o formulario daquele tipo nao tem (o `id` no grupo, ou uma chave nova do backend) prometer um link que nao leva a lugar nenhum e, pior, fechar o painel de saida: `PeerTela.tsx:150-152` e `GrupoTela.tsx:126-128` perguntam so se a lista de campos tem tamanho.

**Files:**
- Modify: `web/src/lib/campos.ts` (a funcao `camposDoErro`)
- Test: `web/src/lib/campos.test.ts`, `web/src/telas/peers/PeerTela.test.tsx`

**Interfaces:**
- Consumes: `SECOES_PEER` e `SECOES_GRUPO`, que ja listam todos os campos de cada formulario, secao por secao.
- Produces: `camposDoErro(chave, tipo, deGrupo)` devolvendo `[]` para chave que nao e campo daquele formulario. O resto da assinatura nao muda, e `campoDoErro` continua sendo `camposDoErro(...)[0] ?? null`.

- [ ] **Step 1: Escrever o teste que falha**

Em `web/src/lib/campos.test.ts`, no describe do mapeamento de erro:

```ts
  it("chave que nao e campo do formulario nao vira campo", () => {
    // o `id` nao existe no formulario do grupo, e uma chave nova do backend
    // tambem nao: as duas prometiam um link que nao levava a lugar nenhum e
    // fechavam o painel de saida, que pergunta so se ha campo
    expect(camposDoErro("id", "parceiro", true)).toEqual([])
    expect(camposDoErro("campo_que_nao_existe", "cliente")).toEqual([])
  })

  it("o id do peer continua sendo campo", () => {
    // a guarda e por formulario, e nao uma lista de proibidos: o mesmo `id`
    // e campo na tela do peer
    expect(camposDoErro("id", "cliente")).toEqual(["id"])
  })
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npx vitest run src/lib/campos.test.ts
```

Expected: FAIL nos dois casos novos (`["id"]` e `["campo_que_nao_existe"]` em vez de `[]`).

- [ ] **Step 3: Consultar a tabela da tela**

Em `web/src/lib/campos.ts`, troque a funcao:

```ts
export function camposDoErro(chave: string, tipo: string, deGrupo = false): string[] {
  if (SEM_CAMPO.includes(chave)) return []
  const daTela = (deGrupo ? SECOES_GRUPO : SECOES_PEER).flatMap((s) => s.campos)
  const eCampo = (campo: string) => daTela.includes(campo)
  if (ERRO_PARA_CAMPO[chave]) return ERRO_PARA_CAMPO[chave].filter(eCampo)
  // no grupo do IX o aprendizado mora no campo do bloco do IX: a tela antiga
  // tinha a mesma volta, com a ancora trocando pelo tipo
  if (deGrupo && chave === "aprendizado" && tipo === "ix") return ["aprendizado_ix"]
  // Chave que nao e campo DESTE formulario nao vira campo: o `id` existe no
  // peer e nao no grupo, e uma chave nova do backend nao existe em nenhum.
  // Sem esta guarda o resumo prometia um link que nao levava a lugar nenhum e
  // o painel de saida fechava sem desenhar campo
  return eCampo(chave) ? [chave] : []
}
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd web && npx vitest run src/lib/campos.test.ts
```

Expected: PASS. Os casos das chaves compostas (`sessoes`, `prefixos`, `te_prefixos`) continuam passando, porque os campos delas estao nas secoes.

- [ ] **Step 5: O painel que nao fecha**

Em `web/src/telas/peers/PeerTela.test.tsx`, junto dos casos de recusa:

```tsx
  it("uma chave de erro que nao e campo nao fecha o painel", async () => {
    // o painel pergunta se ha campo no erro para decidir se mostra o bloco;
    // com uma chave desconhecida ele fechava sem desenhar campo nenhum, e o
    // operador ficava sem o bloco e sem saber onde corrigir
    mockFetch({
      ...BASE,
      "PUT /api/peers/7": { status: 422, corpo: { erros: { campo_novo: "algo que so o backend conhece" }, avisos: [] } },
    })
    montarRota(rotas, "/peers/7")
    await userEvent.click(await screen.findByRole("button", { name: /^salvar$/i }))

    expect(await screen.findByText("algo que so o backend conhece")).toBeInTheDocument()
    expect(await screen.findByText(/CUST-268127-IMPORT-V4/)).toBeInTheDocument()
  })
```

- [ ] **Step 6: Rodar a suite do front**

```bash
cd web && npm test && npm run lint
```

Expected: PASS. Se algum caso de `GrupoTela.test.tsx` esperava o link do erro de `id`, ele e o que muda de comportamento aqui, e o Step 3 da Task 3 e quem o reescreve.

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/campos.ts web/src/lib/campos.test.ts web/src/telas/peers/PeerTela.test.tsx
git commit -m "Uma chave de erro que nao e campo nao vira campo"
```

---

### Task 3: O id do grupo rebusca o id livre

A recusa nasce em `api.py:428-432`, quando o id do formulario em branco foi tomado por outro registro. O formulario do grupo nao tem campo `id`, entao o operador nao tem como corrigir nada: so recarregar `/grupos/novo` e perder o que digitou. Esta task faz a tela pedir o proximo id livre e seguir com o resto do formulario intacto.

**Files:**
- Modify: `web/src/telas/grupos/GrupoTela.tsx` (o ramo de erro do `gravar`)
- Test: `web/src/telas/grupos/GrupoTela.test.tsx`

**Interfaces:**
- Consumes: `GET /api/grupos/novo`, que ja existe e devolve `{id, formulario, ...}` (`api.py:477-486`); o `form` do react-hook-form da tela.
- Produces: nada para as tasks seguintes.

- [ ] **Step 1: Escrever o teste que falha**

Em `web/src/telas/grupos/GrupoTela.test.tsx`, junto dos casos de recusa do salvar:

```tsx
  it("a recusa por id rebusca o proximo livre e mantem o formulario", async () => {
    // o formulario do grupo nao tem campo id, entao essa recusa era beco sem
    // saida: a unica saida era recarregar /grupos/novo e perder o digitado
    mockFetch({
      ...BASE,
      "POST /api/grupos": { status: 422, corpo: { erros: { id: "ID ja usado pelo grupo PARCEIROS" }, avisos: [] } },
      "GET /api/grupos/novo": { corpo: { id: 9, formulario: { ...GRUPO, id: "9" } } },
    })
    montarRota(rotas, "/grupos/novo")
    await screen.findByLabelText("Nome")
    await userEvent.type(screen.getByLabelText("Nome"), "OPERADORA")

    await userEvent.click(screen.getByRole("button", { name: /^salvar$/i }))

    expect(await screen.findByText(/ID ja usado pelo grupo/)).toBeInTheDocument()
    expect(screen.getByLabelText("Nome")).toHaveValue("OPERADORA")
    expect(peticoes().some((p) => p.metodo === "GET" && p.caminho === "/api/grupos/novo")).toBe(true)
  })
```

O arquivo ja tem `BASE`, `GRUPO` e `rotas` com esses nomes; se o `BASE` ja mapear
`GET /api/grupos/novo`, o mapa do caso sobrescreve a chave, que e o que se quer aqui.

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npx vitest run src/telas/grupos/GrupoTela.test.tsx -t "rebusca o proximo livre"
```

Expected: FAIL no `GET /api/grupos/novo` depois da recusa (hoje so a recusa e a mensagem acontecem).

- [ ] **Step 3: Pedir o proximo id livre**

Em `web/src/telas/grupos/GrupoTela.tsx`, no ramo de erro do `gravar`, depois do `setRecusa(recusaComMarca(r.error))` e antes do `return null`:

```tsx
      // A recusa por `id` acontece quando o formulario em branco foi aberto
      // com um id que outro registro tomou no meio do caminho. O formulario do
      // grupo nao tem esse campo, entao sem esta linha a unica saida era
      // recarregar a tela e perder o que foi digitado: a tela rebusca o
      // proximo livre e o operador so clica em salvar de novo
      if (recusaComMarca(r.error).erros.id && ident === null) {
        const livre = await cliente.GET("/api/grupos/novo", { params: { query: { tipo } } })
        if (livre.data) form.setValue("id", livre.data.id, { shouldDirty: true })
      }
```

`cliente`, `tipo` e `form` ja estao no escopo da funcao; se o nome do cliente importado for outro no arquivo, use o mesmo que o resto do `gravar` usa.

- [ ] **Step 4: Rodar e ver passar**

```bash
cd web && npx vitest run src/telas/grupos/GrupoTela.test.tsx
```

Expected: PASS, o caso novo e os que ja estavam.

- [ ] **Step 5: Commit**

```bash
git add web/src/telas/grupos/GrupoTela.tsx web/src/telas/grupos/GrupoTela.test.tsx
git commit -m "A recusa por id no grupo rebusca o proximo livre"
```

---

### Task 4: Todos os avisos de um campo

`Formulario.tsx:119` usa `avisos.find((a) => a.campo === campo.nome)?.mensagem`, entao so o primeiro aviso de cada campo aparece. A API pode devolver varios para o mesmo campo: `validate.py:300-309` emite um por community fora do plano, e o `_avisos` da API nao deduplica por campo.

**Files:**
- Modify: `web/src/components/Campo.tsx` (a prop `aviso` e o trecho que a desenha)
- Modify: `web/src/components/Formulario.tsx` (a linha do `aviso` no `CampoRender` e a prop dele)
- Test: `web/src/telas/peers/FormularioPeer.test.tsx`

**Interfaces:**
- Produces: `Campo` e `CampoRender` passam a receber `avisos?: string[]` no lugar de `aviso?: string`. Quem monta `Campo` fora do `Formulario` (se houver) tem que acompanhar.

- [ ] **Step 1: Escrever o teste que falha**

Em `web/src/telas/peers/FormularioPeer.test.tsx`, junto dos casos de aviso (o
helper `Montar` do proprio arquivo ja aceita `avisos`):

```tsx
  it("mostra todos os avisos do campo, e nao so o primeiro", () => {
    // As communities fora do plano geram um aviso por valor (o append do
    // _avisa_communities roda dentro do for), e o campo desenhava so o
    // primeiro: o operador corrigia um e o outro seguia escondido
    render(
      <Montar
        avisos={[
          { campo: "communities", mensagem: "community fora do namespace: 64512:50" },
          { campo: "communities", mensagem: "community fora da faixa do plano: 64512:51" },
        ]}
      />,
    )

    const campo = document.querySelector('[data-campo="communities"]')
    expect(campo).toHaveTextContent("community fora do namespace: 64512:50")
    expect(campo).toHaveTextContent("community fora da faixa do plano: 64512:51")
  })
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npx vitest run src/telas/peers/FormularioPeer.test.tsx -t "todos os avisos"
```

Expected: FAIL: a segunda mensagem nao aparece.

- [ ] **Step 3: A lista no `Campo`**

Em `web/src/components/Campo.tsx`:

```tsx
type Props = {
  nome: string
  rotulo: string
  ajuda?: string
  erro?: string
  avisos?: string[]
  // "o bloco de <tipo> nao usa este campo": o campo esta a vista porque tem
  // valor guardado ou erro, e nao porque pertence ao tipo aberto
  nota?: string
  largo?: boolean
  children: ReactNode
}

export function Campo({ nome, rotulo, ajuda, erro, avisos, nota, largo, children }: Props) {
```

e o trecho que desenhava um aviso passa a desenhar a lista (o comentario de cima continua valendo):

```tsx
      {avisos?.map((a) => (
        <p key={a} className="flex items-start gap-1 text-xs text-aviso-texto">
          <TriangleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
          {a}
        </p>
      ))}
```

- [ ] **Step 4: A lista no formulario**

Em `web/src/components/Formulario.tsx`, a linha do aviso no `CampoRender` passa a juntar todos os do campo:

```tsx
                avisos={avisos.filter((a) => a.campo === campo.nome).map((a) => a.mensagem)}
```

e a prop do `CampoRender` (e o repasse ao `Campo`) acompanha:

```tsx
function CampoRender({ campo, ctx, bruto, erro, avisos, nota, aoMudar, aoTrocarTipo, aoTrocarClasse }: {
  campo: CampoTabela
  ctx: Contexto
  bruto: unknown
  erro?: string
  avisos?: string[]
  nota?: string
  aoMudar: (nome: string, valor: unknown) => void
  aoTrocarTipo: (tipo: string) => void
  aoTrocarClasse: (classe: string) => void
}) {
```

- [ ] **Step 5: Rodar a suite do front**

```bash
cd web && npm test && npm run lint
```

Expected: PASS. O grupo usa o mesmo `Formulario`, e o caso do grupo que le aviso (`a recusa do salvar sai quando a proxima previa responde`) tem que continuar verde.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/Campo.tsx web/src/components/Formulario.tsx web/src/telas/peers/FormularioPeer.test.tsx
git commit -m "O campo mostra todos os avisos, e nao so o primeiro"
```

---

### Task 5: A aba ativa sobe para a tela

`PainelSaida.tsx:46` guarda a aba corrente em estado interno, e as tres telas publicam `abas[0]` para a paleta (`PeerTela.tsx:304`, `GrupoTela.tsx:262`, `PrefixosTela.tsx:165`). Com mais de uma aba, "copiar o bloco aberto" copia a primeira.

**Files:**
- Modify: `web/src/components/PainelSaida.tsx` (prop nova `aoTrocarAba` e o clique da aba)
- Modify: `web/src/telas/peers/PeerTela.tsx`, `web/src/telas/grupos/GrupoTela.tsx`, `web/src/telas/prefixos/PrefixosTela.tsx`
- Test: `web/src/components/PainelSaida.test.tsx`, `web/src/telas/peers/PeerTela.test.tsx`

**Interfaces:**
- Produces: `PainelSaida({ ..., aoTrocarAba?: (id: string) => void })`. O painel continua dono do estado; a prop so avisa a tela.

- [ ] **Step 1: Escrever o teste que falha**

Em `web/src/components/PainelSaida.test.tsx`:

```tsx
  it("avisa a tela quando a aba muda", async () => {
    // a tela precisa saber qual aba esta aberta para publicar a copia certa
    // para a paleta: sem o aviso, ela copiava sempre a primeira
    const aoTrocarAba = vi.fn()
    montar([aba("bloco", "xpl bloco"), aba("remover", "undo peer")], { aoTrocarAba })
    await userEvent.click(screen.getByRole("tab", { name: /remoção/i }))
    expect(aoTrocarAba).toHaveBeenCalledWith("remover")
  })
```

Use o helper de montagem que o arquivo ja tem; se ele nao aceitar props extras, passe o `aoTrocarAba` pela mesma porta que os casos existentes usam.

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npx vitest run src/components/PainelSaida.test.tsx -t "avisa a tela"
```

Expected: FAIL, porque a prop ainda nao existe (o teste nem compila).

- [ ] **Step 3: O aviso no painel**

Em `web/src/components/PainelSaida.tsx`, acrescente a prop e chame no clique da aba:

```tsx
type Props = {
  abas: AbaSaida[]
  sujo: boolean
  carregando: boolean
  erro: string | null
  // A aba ativa e do painel, e a tela so precisa saber qual e para publicar a
  // copia certa para a paleta. Por isso o aviso, e nao o estado controlado
  aoTrocarAba?: (id: string) => void
  onCopiar?: (aba: AbaSaida) => Promise<boolean> | boolean
  onSalvarECopiar?: (aba: AbaSaida) => Promise<boolean>
}

export function PainelSaida({ abas, sujo, carregando, erro, aoTrocarAba, onCopiar, onSalvarECopiar }: Props) {
```

e, no botao de cada aba:

```tsx
            onClick={() => { setAbaAtual(a.id); aoTrocarAba?.(a.id) }}
```

- [ ] **Step 4: A tela espelhando a aba**

Nas tres telas, o `blocoAberto` deixa de ser o primeiro:

```tsx
  // A aba corrente vem do painel pelo `aoTrocarAba`: a copia da paleta tem que
  // ser a da aba que o operador esta vendo, e nao a primeira do painel
  const [abaAtiva, setAbaAtiva] = useState(abas[0]?.id ?? "")
  const blocoAberto = abas.find((a) => a.id === abaAtiva)?.conteudo ?? null
```

e o painel recebe a prop:

```tsx
          <PainelSaida
            abas={abas}
            aoTrocarAba={setAbaAtiva}
```

O `useState` de cada tela ja esta no topo do componente; se as `abas` mudarem de tamanho (a previa chegando com o quadro "ao criar"), o `abas.find` continua achando a aba corrente, e o `?? null` cobre a que sumiu.

- [ ] **Step 5: O caso que prova o caminho inteiro**

Em `web/src/telas/peers/PeerTela.test.tsx`, junto do caso "a paleta oferece copiar o bloco quando ele existe":

```tsx
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
```

O `cascaComPeer` e o mesmo arranjo de rotas que o caso vizinho monta (`Casca` + `peers/:id`).

- [ ] **Step 6: Rodar a suite do front**

```bash
cd web && npm test && npm run lint
```

Expected: PASS. Se a tela dos prefixos ou a do grupo tiver caso que conta as chamadas de `PainelSaida`, ele e o que muda.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/PainelSaida.tsx web/src/components/PainelSaida.test.tsx web/src/telas/peers/PeerTela.tsx web/src/telas/peers/PeerTela.test.tsx web/src/telas/grupos/GrupoTela.tsx web/src/telas/prefixos/PrefixosTela.tsx
git commit -m "A copia da paleta leva o bloco da aba que esta aberta"
```

---

### Task 6: O resumo leva a secao

`ResumoErros.tsx:24-26` usa `campos[0]`, entao um erro que cobre varios campos (um `prefixos` com o v4 e o v6 tortos) sempre leva ao primeiro. A medicao desta leva: nenhuma chave cobre campos de secoes diferentes, entao o conserto e levar ao campo quando a chave cobre um so, e ao topo da secao quando cobre varios.

**Files:**
- Modify: `web/src/components/ResumoErros.tsx`
- Modify: `web/src/telas/peers/PeerTela.tsx` e `web/src/telas/grupos/GrupoTela.tsx` (o `aoIrPara`)
- Test: `web/src/components/ResumoErros.test.tsx`

**Interfaces:**
- Consumes: `#secao-<id>`, o id que o `Formulario` ja poe no `fieldset` de cada secao.
- Produces: `aoIrPara(campo, secao)` passa a ser chamado com `campo = null` quando a chave cobre mais de um campo. Os dois chamadores tem que saber rolar para a secao nesse caso.

- [ ] **Step 1: Escrever o teste que falha**

Em `web/src/components/ResumoErros.test.tsx`:

```tsx
  it("um erro que cobre varios campos leva a secao, e nao ao primeiro campo", async () => {
    // o teste de `prefixos` pode ser o v4 ou o v6, e a mensagem nao diz qual:
    // prometer o campo v4 era pior que levar ao topo da secao
    const aoIrPara = vi.fn()
    render(
      <ResumoErros
        erros={{ prefixos: "prefixo invalido: 2001:db8::/129" }}
        tipo="cliente"
        aoIrPara={aoIrPara}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /prefixo invalido/ }))
    expect(aoIrPara).toHaveBeenCalledWith(null, "prefixos")
  })

  it("um erro de um campo so continua indo no campo", async () => {
    const aoIrPara = vi.fn()
    render(<ResumoErros erros={{ asn: "ASN ja usado" }} tipo="cliente" aoIrPara={aoIrPara} />)
    await userEvent.click(screen.getByRole("button", { name: /ASN ja usado/ }))
    expect(aoIrPara).toHaveBeenCalledWith("asn", "identificacao")
  })
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npx vitest run src/components/ResumoErros.test.tsx
```

Expected: FAIL no primeiro caso (hoje recebe `("prefixos_v4", "prefixos")`).

- [ ] **Step 3: Escolher destino pelo tamanho do mapa**

Em `web/src/components/ResumoErros.tsx`:

```tsx
        {itens.map(([chave, mensagem]) => {
          const campos = camposDoErro(chave, tipo, deGrupo)
          // Um campo so: vai nele. Varios: a mensagem nao diz qual deles esta
          // torto (o `prefixo invalido` de v4 e o de v6 saem na mesma chave), e
          // prometer o primeiro era pior que levar ao topo da secao que os tem
          const campo = campos.length === 1 ? campos[0] : null
          const secao = campos.length > 0
            ? secoes.find((s) => campos.every((c) => s.campos.includes(c)))?.id ?? null
            : null
          return (
            <li key={chave}>
              {campos.length > 0 ? (
                <button
                  type="button"
                  className="text-left underline decoration-dotted"
                  onClick={() => aoIrPara(campo, secao)}
                >
                  {mensagem}
                </button>
              ) : (
                <span>{mensagem}</span>
              )}
            </li>
          )
        })}
```

- [ ] **Step 4: Os dois chamadores sabem rolar para a secao**

Em `web/src/telas/peers/PeerTela.tsx`, no `aoIrPara` do `FormularioPeer` (por volta da linha 399):

```tsx
              aoIrPara={(campo, secao) => {
                if (!campo && !secao) return
                // Sem campo o alvo e a secao: e o caso do erro que cobre varios
                // campos, em que apontar um deles seria mentir sobre onde esta
                if (!campo) {
                  document.getElementById(`secao-${secao}`)?.scrollIntoView({ block: "start" })
                  return
                }
                const alvo = document.querySelector<HTMLElement>(`[data-campo="${campo}"] input, [data-campo="${campo}"] textarea, [data-campo="${campo}"] button`)
                alvo?.focus()
                alvo?.scrollIntoView({ block: "center" })
              }}
```

O mesmo em `web/src/telas/grupos/GrupoTela.tsx`, no `aoIrPara` dela.

- [ ] **Step 5: Rodar a suite do front**

```bash
cd web && npm test && npm run lint
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/ResumoErros.tsx web/src/components/ResumoErros.test.tsx web/src/telas/peers/PeerTela.tsx web/src/telas/grupos/GrupoTela.tsx
git commit -m "O resumo de erros leva a secao quando o erro cobre varios campos"
```

---

### Task 7: O retry do `Falha`

`Falha.tsx` nao tem estado: o botao chama `aoTentar` direto, e o refetch do TanStack reinicia o pedido em voo, entao o clique duplo dispara dois pedidos (nos peer e grupo, quatro, porque cada um refaz duas consultas).

**Files:**
- Modify: `web/src/components/Falha.tsx`
- Modify: os cinco chamadores: `web/src/telas/peers/PeerTela.tsx` (~:329), `web/src/telas/grupos/GrupoTela.tsx` (~:279), `web/src/telas/prefixos/PrefixosTela.tsx` (~:181), `web/src/telas/base/BaseTela.tsx` (~:60), `web/src/telas/configuracoes/ConfiguracoesTela.tsx` (~:80)
- Test: `web/src/telas/prefixos/PrefixosTela.test.tsx`

**Interfaces:**
- Produces: `Falha({ mensagem, tentando }: { mensagem: string; tentando?: boolean })`. Os cinco chamadores passam o `isFetching` do que eles refazem.

- [ ] **Step 1: Escrever o teste que falha**

Em `web/src/telas/prefixos/PrefixosTela.test.tsx`, com o helper `segurarLeitura` que o arquivo ja tem:

```tsx
  it("o tentar de novo desabilita enquanto o pedido corre", async () => {
    // O refetch do TanStack reinicia o pedido em voo: com o botao sempre
    // clicavel, o clique duplo disparava dois pedidos, e nos peer e grupo
    // quatro, porque cada um refaz duas consultas
    mockFetch({ ...BASE, "GET /api/blocos": { status: 500, corpo: { erros: { _: "boom" }, avisos: [] } } })
    montarRota(rotas, "/prefixos")
    const soltar = segurarLeitura("GET /api/blocos")
    await userEvent.click(await screen.findByRole("button", { name: /tentar de novo/i }))
    expect(screen.getByRole("button", { name: /tentar de novo/i })).toBeDisabled()
    soltar()
  })
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npx vitest run src/telas/prefixos/PrefixosTela.test.tsx -t "desabilita enquanto"
```

Expected: FAIL, porque o botao nao tem `disabled`.

- [ ] **Step 3: O estado no componente**

**Superado pelo adendo do fim da task.** O JSDoc abaixo nao e o que entrou no
codigo: o adendo, logo depois do Step 6, e o registro do que venceu.

Em `web/src/components/Falha.tsx`:

```tsx
/**
 * Uma consulta que falhou deixa a tela sem dado nenhum. O que o operador
 * digitou nao se perde: o formulario nao e desmontado por causa de um refetch
 * que falhou, so a tela mostra o aviso e o botao.
 *
 * O `tentando` vem do `isFetching` de quem refaz: sem ele o botao segue
 * clicavel durante o pedido, e o refetch do TanStack reinicia o que esta em
 * voo, entao o clique duplo vira dois pedidos.
 */
export function Falha({ mensagem, tentando = false, aoTentar }: {
  mensagem: string
  tentando?: boolean
  aoTentar: () => void
}) {
  return (
    <div role="alert" className="m-3 rounded border border-erro-texto/30 bg-erro-fundo p-3 text-erro-texto">
      <p className="text-sm">{mensagem}</p>
      <Button size="sm" variant="ghost" className="mt-2" disabled={tentando} onClick={aoTentar}>
        tentar de novo
      </Button>
    </div>
  )
}
```

- [ ] **Step 4: Os cinco chamadores**

Cada um passa o `isFetching` do que o `aoTentar` dispara:

```tsx
        <Falha
          mensagem="não deu para falar com a API"
          tentando={plano.isFetching || inicial.isFetching}
          aoTentar={() => { void plano.refetch(); void inicial.refetch() }}
        />
```

Nos outros: `PrefixosTela` usa `blocos.isFetching`, `BaseTela` usa `base.isFetching`, `ConfiguracoesTela` usa `plano.isFetching`.

- [ ] **Step 5: Rodar a suite do front**

```bash
cd web && npm test && npm run lint
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/Falha.tsx web/src/telas
git commit -m "O tentar de novo desabilita enquanto o pedido corre"
```

**Adendo (medido na execucao, 2026-09-27).** O conserto como este plano o
escreveu e um no-op, e a premissa da task estava errada. Com
`tentando={X.isFetching}` e mais nada, o caso nao passa: no clique o TanStack
zera o `error` de uma consulta sem dado quando ela e refeita
(`@tanstack/query-core/query.js:486`), entao o aviso de falha sai da tela, a tela
volta ao formulario vazio e o botao a desabilitar deixa de existir. E, sem o
`retentando`, nao existe clique duplo a evitar: o primeiro clique ja tira o botao
da tela.

O que foi entregue, e o que o criterio de aceite virou: cada um dos cinco
chamadores calcula

```tsx
const retentando = tentando && X.data === undefined && X.errorUpdateCount > 0
```

e o aviso fica de pe, com o botao desabilitado, enquanto o retry corre (o
`errorUpdateCount` sobrevive ao refetch; o `data === undefined` deixa de fora o
refetch de fundo de quem ja tem dado). O efeito observavel deixa de ser "evitar
dois pedidos" e passa a ser "a tela nao pisca o formulario vazio durante o
retry", que e o defeito que existia de verdade.

---

### Task 8: O tema com marca acessivel

`ConfiguracoesTela.tsx:140-150` marca o tema escolhido so por `variant` e `ring-1`. A paleta ja marca pelo texto " (atual)", que o leitor de tela le; esta task mexe so na tela das configuracoes.

**Files:**
- Modify: `web/src/telas/configuracoes/ConfiguracoesTela.tsx`
- Test: `web/src/telas/configuracoes/ConfiguracoesTela.test.tsx`

> Nota de execucao (2026-09-27): esta task **nao tinha rodado** quando a revisao
> final da leva a leu - o plano, a spec e o ledger a davam por fechada, e o
> componente seguia sem `aria-pressed` e sem o caso de teste. A execucao entrou
> na rodada de conserto, e o Step 1 abaixo ja esta na versao executada: o
> `mockFetch(BASE)` que o snippet do brief omitia (sem ele o `afterEach` do
> arnes acusa "rota sem mapa") e as **tres** assercoes, e nao duas. O tema padrao
> e `sistema` (`web/src/app/tema.ts:12-19`), entao o clique em `claro` muda o
> estado de verdade, e a terceira assercao - o `sistema` em `false` depois do
> clique - e a que pega a **marca presa no padrao**: medida na execucao, um
> `aria-pressed={tema === t || t === "sistema"}` passa nas duas assercoes do
> brief e falha so nela, porque o "pressionado" ficaria em dois botoes ao mesmo
> tempo. Um `aria-pressed={true}` fixo, esse, ja falha na segunda do brief -
> tambem medido.

- [ ] **Step 1: Escrever o teste que falha**

```tsx
  it("o tema escolhido se anuncia como pressionado", async () => {
    // a marca era so a cor (variant + ring): quem usa leitor de tela nao sabia
    // qual dos tres estava valendo. O tema padrao e "sistema", entao o clique
    // em "claro" muda o estado de verdade, e a marca tem que SAIR do sistema
    mockFetch(BASE)
    montarRota(rotas, "/configuracoes")
    await screen.findByRole("button", { name: "claro" })
    expect(screen.getByRole("button", { name: "sistema" })).toHaveAttribute("aria-pressed", "true")

    await userEvent.click(screen.getByRole("button", { name: "claro" }))

    expect(screen.getByRole("button", { name: "claro" })).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("button", { name: "escuro" })).toHaveAttribute("aria-pressed", "false")
    // sem esta terceira linha o caso passaria com a marca fixa: e ela que prova
    // que o "pressionado" andou de um botao para o outro
    expect(screen.getByRole("button", { name: "sistema" })).toHaveAttribute("aria-pressed", "false")
  })
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npx vitest run src/telas/configuracoes/ConfiguracoesTela.test.tsx
```

Expected: FAIL: os botoes nao tem `aria-pressed`.

- [ ] **Step 3: O atributo**

Em `web/src/telas/configuracoes/ConfiguracoesTela.tsx`:

```tsx
            <Button
              key={t}
              size="sm"
              variant={tema === t ? "secondary" : "ghost"}
              className={cn(tema === t && "ring-1")}
              aria-pressed={tema === t}
              onClick={() => trocarTema(t)}
            >
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd web && npx vitest run src/telas/configuracoes/ConfiguracoesTela.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/telas/configuracoes/ConfiguracoesTela.tsx web/src/telas/configuracoes/ConfiguracoesTela.test.tsx
git commit -m "O tema escolhido se anuncia como pressionado"
```

---

### Task 9: Dois consertos pequenos

Duas pendencias que nao pertencem a nenhuma das outras tasks: o `_corpo` "resposta inesperada da API" que a tela dos prefixos mostra junto do aviso novo, e o comentario do harness que explica o que o `toast.dismiss()` isola.

**Files:**
- Modify: `web/src/telas/prefixos/PrefixosTela.tsx` (o ramo de erro do `salvar`)
- Modify: `web/src/teste/roteador.tsx` (o comentario do `afterEach`)
- Test: `web/src/telas/prefixos/PrefixosTela.test.tsx`

- [ ] **Step 1: Escrever o teste que falha**

```tsx
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
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npx vitest run src/telas/prefixos/PrefixosTela.test.tsx -t "resposta inesperada"
```

Expected: FAIL: o texto aparece.

- [ ] **Step 3: O mesmo tratamento do peer e do grupo**

Em `web/src/telas/prefixos/PrefixosTela.tsx`, no ramo de erro do `salvar`:

```tsx
      if (r.error) {
        // o 5xx e falha do servidor, e nao do texto: o aviso com o caminho de
        // volta entra junto, e o "tentar de novo" repete o mesmo PUT
        if (falhaDoServidor(r.response.status)) {
          avisarFalhaDeRede(() => salvar.mutate())
          // Sem corpo de recusa nao ha o que mostrar no painel, e o `_corpo`
          // do lerRecusa ("resposta inesperada da API") seria ruido em cima do
          // aviso: e o mesmo caminho do peer e do grupo
          if (!temRecusa(r.error)) return
        }
        // (o comentario sobre o refetch da previa continua aqui)
        setRecusa(recusaComMarca(r.error))
        return
      }
```

Se `temRecusa` ainda nao estiver importado no arquivo, traga-o de `@/api/consultas`, de onde o `lerRecusa` ja vem.

- [ ] **Step 4: O comentario do harness**

Em `web/src/teste/roteador.tsx`, o `toast.dismiss()` do `afterEach` ganha o nome do que ele isola:

```ts
  // O que a tela avisou fica no modulo do sonner, e nao na arvore que a limpeza
  // automatica desmonta: sem esta linha os toasts de um caso aparecem no
  // seguinte, e uma assercao por texto acha o do caso anterior. Os casos que
  // quebram sem ela, medidos: PeerTela.test.tsx:529 (acha tres copias de
  // "gravado em out/"), PeerTela.test.tsx:659 e GrupoTela.test.tsx:342
  // (encontram um "nao deu para falar com a API" que nao e do caso deles)
  toast.dismiss()
```

- [ ] **Step 5: Rodar a suite do front**

```bash
cd web && npm test && npm run lint
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/telas/prefixos/PrefixosTela.tsx web/src/telas/prefixos/PrefixosTela.test.tsx web/src/teste/roteador.tsx
git commit -m "Os prefixos suprimem o _corpo no 5xx, como o peer e o grupo"
```

---

### Task 10: e2e

Os quatro pendentes do e2e e a medicao do Safari. Esta task e a unica que pode mudar de rumo no meio: se o WebKit recusar a escrita depois da requisicao, o socorro de dois cliques entra aqui.

**Files:**
- Modify: `web/playwright.config.ts` (aspas nos caminhos)
- Create: `web/tsconfig.e2e.json`, Modify: `web/tsconfig.json` (a referencia)
- Create: `web/e2e/clipboard.d.ts` (o tipo minimo do `navigator.clipboard`, na emenda do Step 2)
- Modify: `web/eslint.config.js` (globais de Node)
- Modify: `web/e2e/copiar.spec.ts` (a assercao forte e o caso novo)
- Modify: `README.md` (a contagem de casos do e2e)

- [ ] **Step 1: As aspas nos caminhos**

Em `web/playwright.config.ts`, o comando do `webServer` passa a citar cada caminho interpolado, porque ele e montado como shell:

```ts
    command: `node "${repo}web/e2e/global-setup.ts" && cd "${temp}" && BGPGEN_WEB="${repo}web/dist" "${repo}.venv/bin/python" -m uvicorn app.app:app --port ${PORTA}`,
```

- [ ] **Step 2: O typecheck do e2e**

> Nota de execucao (2026-09-27): a config abaixo nasceu sem `"lib"`, e o default
> do `target` trazia a lib DOM para dentro do programa do e2e: `document`,
> `window` e `localStorage` seguiam typecheckando, que e o oposto do que o
> Step 3 quer (o bloco de lint existe porque o e2e "hoje recebe `document`,
> `window` e `localStorage` como definidos"). Medido na rodada de conserto com
> `--lib ES2022`: so `navigator.clipboard` quebrava - tres pontos, o `:22` e o
> `:74` do `copiar.spec.ts` **e o `:113` do `fluxos.spec.ts`**, que a revisao
> nao contou. A emenda entrou na mesma rodada: o `"lib": ["ES2022"]` no
> `tsconfig.e2e.json` e o tipo local minimo do `clipboard` em
> `web/e2e/clipboard.d.ts` - uma declaracao, zero `any`, zero
> `@ts-expect-error`, zero cast.
>
> O que a config entrega depois da emenda, medido: escrever `document.title`,
> `window.location` ou um campo do `navigator` fora do `clipboard` num arquivo
> do `e2e/` e erro de tipo (`TS2584`/`TS2304`); o `localStorage` continua
> passando, e nao pela DOM - o `@types/node` 24 declara
> `web-globals/storage.d.ts` com `var localStorage: Storage`, porque o Node tem
> esse global. Ou seja: a garantia e "ES2022 mais os globais de Node", e nao
> "nada de navegador".

Crie `web/tsconfig.e2e.json`:

```json
{
  "compilerOptions": {
    // o mesmo destino dos outros dois: sem isto o `tsc -b` larga um
    // tsconfig.e2e.tsbuildinfo solto na raiz do web/, fora do gitignore
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.e2e.tsbuildinfo",
    "target": "ES2022",
    // sem o lib, a DOM entra pelo default do target e `document`, `window` e
    // `localStorage` seguem typecheckando no e2e, que roda em navegador e nao
    // pode contar com eles: o que o e2e enxerga aqui e o ES2022 mais os globais
    // de Node, e so
    "lib": ["ES2022"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "types": ["node"]
  },
  "include": ["playwright.config.ts", "e2e/**/*.ts"]
}
```

e acrescente a referencia em `web/tsconfig.json`:

```json
{ "files": [], "references": [ { "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" }, { "path": "./tsconfig.e2e.json" } ] }
```

(mantenha o que o arquivo ja tem e so acrescente a terceira referencia).

Rode o typecheck e **conserte o que aparecer**, sem `any` e sem `@ts-expect-error`:

```bash
cd web && npx tsc -b
```

Expected: PASS na primeira vez, ou erros de tipo em codigo que nunca foi checado. Cada erro e conserto real, no mesmo commit.

Com o `"lib": ["ES2022"]` o que aparece sao os tres `navigator.clipboard` (dois
no `copiar.spec.ts`, um no `fluxos.spec.ts`), e o conserto e o tipo local minimo
em `web/e2e/clipboard.d.ts` - o que o e2e usa do navegador e o `readText`, e so:

```ts
interface Navigator {
  readonly clipboard: { readText(): Promise<string> }
}
```

E uma declaracao de global, e nao um cast: o compilador continua conferindo o
resto (`navigator.clipboar` e erro de propriedade inexistente, e `document` nao
existe no programa). O `declare global` dentro de um dos specs cobriria os dois
arquivos pelo mesmo programa, mas o `.d.ts` ao lado deles diz de onde vem o
tipo sem precisar procurar em qual spec ele foi declarado.

- [ ] **Step 3: Os globais certos no lint**

Em `web/eslint.config.js`, antes do bloco que usa `globals.browser`:

```js
    {
      files: ["playwright.config.ts", "e2e/**/*.ts"],
      languageOptions: { globals: globals.node },
    },
```

(Se o bloco existente tiver `files` restrito a `src/`, os dois convivem; se ele pegar `**/*.{ts,tsx}`, este entra depois e vence para os arquivos do e2e.)

```bash
cd web && npm run lint
```

Expected: PASS, com o bloco no lugar - e ele fica como registro de intencao, e
nao como se estivesse conferindo alguma coisa. Medido: o bloco **nao** muda nada
hoje. Tirando-o, `npx eslint e2e playwright.config.ts` continua em exit 0, porque
o `typescript-eslint` desliga o `no-undef` nos arquivos TS (o `--print-config` o
resolve como desligado) e ele e o unico rule que olharia para globais; e os
globais ainda se mesclam com os do bloco anterior, em vez de o novo vencer. Quem
cobre os globais do e2e de verdade e o `types: ["node"]` do `tsconfig.e2e.json`
do Step 2.

- [ ] **Step 4: A copia provando o bloco daquele peer**

Em `web/e2e/copiar.spec.ts`, a assercao do clipboard passa a exigir algo do peer 1 (o `ACME` do cadastro do e2e):

```ts
    const texto = await page.evaluate(() => navigator.clipboard.readText())
    // "end-filter" casa com qualquer bloco XPL, de qualquer peer: o que prova
    // que a copia e do bloco DESTE peer e o token dele
    expect(texto).toContain("end-filter")
    expect(texto).toContain("268127")
```

- [ ] **Step 5: A medicao do Safari**

Em `web/e2e/copiar.spec.ts`, um caso novo, no mesmo describe, que roda nos dois projetos (o `webkit` roda o arquivo inteiro):

```ts
  test("salvar e copiar leva o bloco gravado, e nao o digitado", async ({ page, context, browserName }) => {
    // O caso que a spec do front deixou em aberto: o writeText acontece depois
    // da requisicao do salvar, e o WebKit pode recusar. O que este caso mede e
    // exatamente isso, e o socorro (salvar, trocar o botao para "copiar" e
    // pedir o segundo clique) entra se ele falhar aqui
    await context.grantPermissions(["clipboard-read", "clipboard-write"]).catch(() => {})
    await page.goto("/peers/3")
    await page.getByLabel("Descrição").fill(`medido em ${browserName}`)
    const botao = page.getByRole("button", { name: /salvar e copiar/i })
    await botao.click()

    await expect(page.getByText(/gravado em out\//)).toBeVisible()
    await expect(botao).toHaveText(/copiado/, { timeout: 3000 })
    const texto = await page.evaluate(() => navigator.clipboard.readText())
    expect(texto).toContain(`medido em ${browserName}`)
  })
```

O `clipboard-read` nao existe no WebKit: se o `readText` falhar la, o caso le o texto pelo proprio painel (o `getByRole("tabpanel")` tem o bloco) e a assercao forte fica no Chromium. Ajuste conforme o que o navegador permitir, e diga no comentario qual caminho cada um provou.

- [ ] **Step 6: Rodar o e2e nos dois**

```bash
cd web && npm run e2e
```

Expected: PASS. Se o caso novo falhar **so no WebKit** na parte da copia, o plano autoriza uma mudanca: implemente o socorro de dois cliques em `PainelSaida` e `web/src/lib/copiar.ts` (salvar, deixar o botao em "copiar" habilitado e pedir o segundo clique), ajuste o caso para assertar o fluxo de dois cliques no WebKit e um clique no Chromium, e rode de novo. Se falhar nos dois, e defeito do caso, e nao do app.

- [ ] **Step 7: A contagem no README**

O `copiar.spec` ganhou um caso, que roda em dois projetos: o total vai de 12 para 14.

```
npm run e2e             # Playwright: compila e roda os 14 casos contra um uvicorn (8 fluxos + 6 de copia)
```

- [ ] **Step 8: Commit**

```bash
git add web/playwright.config.ts web/tsconfig.e2e.json web/tsconfig.json web/eslint.config.js web/e2e/copiar.spec.ts README.md
git commit -m "O e2e mede o salvar e copiar no WebKit, e o resto dos pendentes"
```

---

### Task 11: Comentarios e registro

**Files:**
- Modify: `app/api.py` e `app/formulario.py` (os comentarios obsoletos)
- Modify: `docs/superpowers/plans/2026-09-26-front-spa.md` e `docs/superpowers/plans/2026-09-27-corte-das-telas-html.md` (o registro)

- [ ] **Step 1: Os comentarios**

Em `app/api.py`, os comentarios que citavam as telas Jinja e as rotas que sairam;
em `app/formulario.py`, os que citavam `_contexto`, `_contexto_grupo`,
`POP_USADOS` e as tags da tela. A revisao da Task 1 acrescentou mais um, que ela
nao podia consertar (o brief daquela task limitava a mudanca ao `avisos`):
`app/validate.py:452-455` diz "O peer fica como esta; alinha-lo e
mudanca separada (ver a spec)", e a Task 1 E aquela mudanca, entao o comentario
passa a dizer que o grupo recusa e o peer avisa. Cada um passa a descrever o que
o codigo faz hoje. Os tres que citam funcoes apagadas:

```python
# app/api.py:6, hoje "de cada campo e o bloco gerado sao os mesmos nas duas telas."
#   vira: "de cada campo e o bloco gerado saem do mesmo lugar: o formulario em
#   texto do POST/PUT vira Peer, e o Peer vira JSON de volta."

# app/api.py:372, hoje "# GET /saida/{token} da tela HTML"
#   vira: "# o que o GET /api/peers/{ident}/saida responde no campo bloco"

# app/formulario.py:63-66 (o docstring de _usados)
#   vira: "O helper nao soma lado nenhum: ele varre a lista que recebe. Quem
#   monta a lista e quem chama: o /api/plano passa peers + grupos juntos para
#   o aprendizado (o 3xxx e um espaco so) e so os peers para o POP."
```

Os outros seguem a mesma regra: a tela HTML nao existe mais, entao a comparacao vira o que a API faz. Nenhum deles muda comportamento.

- [ ] **Step 2: Conferir que nada quebrou**

```bash
.venv/bin/python -m pytest -q
cd web && npm test && npm run lint && npm run api:conferir
```

Expected: PASS nos quatro.

- [ ] **Step 3: O registro nos planos das etapas**

No fim de `docs/superpowers/plans/2026-09-26-front-spa.md`, na secao "Pendencias conhecidas", cada item ganha uma linha dizendo onde ele foi fechado (`docs/superpowers/specs/2026-09-27-pendencias-do-front-design.md` e o plano desta leva), e no `Fechamento` do `2026-09-27-corte-das-telas-html.md` a mesma linha para os itens que ele listou. Os dois que **nao** fecham:

```
- A tela de lista continua nao existindo no corpo: decidido em 2026-09-27 como
  estado vazio, e a lista e a barra lateral.
- A origem fora da tabela nos tres upstreams do cadastro real continua la: o
  aviso mostra, e corrigir e decisao de rede.
```

- [ ] **Step 4: Commit**

```bash
git add app/api.py app/formulario.py docs/superpowers/plans/2026-09-26-front-spa.md docs/superpowers/plans/2026-09-27-corte-das-telas-html.md
git commit -m "Os comentarios deixam de citar as telas que sairam"
```

---

### Task 12: O erro de token aponta o campo onde o token nasce

O operador duplicou o ALT (upstream, apelido `ALT`, ASN 53062, membro do grupo
`ALT_53062`) e levou tres erros: `ASN ja usado pelo peer ALT` no campo do ASN, e
dois `endereco ja usado pelo peer ALT`. Os dois de endereco sao o esperado numa
copia (os IPs remotos vieram junto), e o banner da tela ja diz para troca-los.

O primeiro nao. O que colide nao e o ASN: e o **token**, que e
`apelido or str(asn)` (`peers.py:111-119`) e e o nome do peer no equipamento e
nos arquivos de `out/`. Como o ALT tem apelido, o token dele e `ALT`, e o da
copia tambem. Trocar o ASN nao resolve (o token continua `ALT`), e a mensagem
segue culpando o ASN. Dois peers **podem** ter o mesmo ASN (foi a decisao
registrada no spec desta leva, em "Por que o ASN repetido fica como esta"); o
que nao pode e repetir o token.

Hoje `validate.py:695-706` reporta a colisao sempre no campo `asn`, menos para
`ix`/`pni` sem apelido (que vai para `apelido`, com a mensagem do route server).
Esta task faz o campo e a mensagem seguirem de onde o token nasce.

> Nota de execucao (2026-09-27): o operador levantou, com a tela do ALT na mao,
> que "nao pode ter trava no ASN, pois um mesmo cliente pode ter mais de um
> peer". Nao havia trava — o validador compara tokens, e a spec desta leva ja
> registrava que o mesmo ASN com apelidos diferentes e legitimo —, mas o ramo do
> peer **sem apelido** ainda mandava o operador mexer no ASN. A emenda entrou na
> execucao, antes do commit: os Steps 1, 2, 3 e 4 abaixo ja estao na versao
> emendada, e o conjunto de recusas ficou igual (mudaram o campo e a mensagem).

**Files:**
- Modify: `app/validate.py` (o laco de colisao do peer)
- Modify: `tests/test_validate.py`
- Modify: `web/e2e/fluxos.spec.ts:79` (a assercao do fluxo "duplicar e ajustar", que espera a mensagem antiga)

**Interfaces:**
- Produces: a mesma lista de `Erro` do `validar`, com o campo da colisao de token escolhido pela origem do token. A regra nao muda: um registro por token.

- [ ] **Step 1: Escrever o teste que falha**

No fim de `tests/test_validate.py`:

```python
def test_a_colisao_de_token_aponta_o_campo_onde_o_token_nasce():
    """Token repetido: o erro aponta o campo que resolve, e nao o ASN sempre.

    O token e `apelido or str(asn)`. Com apelido, e ele que colide: apontar o
    ASN mandava o operador trocar um campo que nao resolve, e o erro continuava
    depois da troca, culpando o ASN de novo. Sem apelido, o token e o ASN, e
    quem resolve e dar um apelido: o campo do erro e o apelido, e a mensagem
    diz isso, em vez de mandar mexer num ASN que pode muito bem repetir (um
    mesmo cliente em dois POPs e dois peers legitimos).
    """
    com_apelido = um_peer(id=1, apelido="ALT", nome="ALT", tipo="upstream",
                          asn=53062)
    copia = um_peer(id=2, apelido="ALT", nome="ALT", tipo="upstream", asn=64500)
    erros = validate.validar(copia, [com_apelido], grupos=[])
    assert [(e.campo, e.mensagem) for e in erros if "token" in e.mensagem] == [
        ("apelido", "o apelido ALT ja e o token do peer ALT")]

    sem_apelido = um_peer(id=3, apelido="", nome="UP A", tipo="upstream",
                          asn=53062)
    repetido = um_peer(id=4, apelido="", nome="UP B", tipo="upstream",
                       asn=53062)
    erros = validate.validar(repetido, [sem_apelido], grupos=[])
    assert [(e.campo, e.mensagem) for e in erros if e.campo == "apelido"] == [
        ("apelido",
         "o ASN 53062 ja e o token do peer UP A: de um apelido a este peer")]
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
.venv/bin/python -m pytest tests/test_validate.py -q -k colisao_de_token
```

Expected: FAIL nos dois casos: o primeiro recebe `("asn", "ASN ja usado pelo peer ALT")`
e o segundo, `("asn", "ASN ja usado pelo peer UP A")`.

- [ ] **Step 3: O campo segue a origem do token**

Em `app/validate.py`, troque o ramo da colisao de token (perto da linha 695):

```python
        if outro.token == peer.token:
            # O token e `apelido or str(asn)`, e o campo do erro segue de onde
            # ele nasce: com apelido, e o apelido que o operador tem que mexer,
            # e apontar o ASN mandava trocar um campo que nao resolve (a copia
            # do ALT recebeu "ASN ja usado", trocou o ASN e o erro continuou).
            # O ix/pni sem apelido continua no apelido, porque ali o ASN e o
            # do route server e o apelido e a saida.
            if peer.apelido:
                erros.append(Erro(
                    "apelido",
                    "o apelido %s ja e o token do peer %s"
                    % (peer.apelido, outro.nome)))
            elif peer.tipo in ("ix", "pni"):
                erros.append(Erro(
                    "apelido",
                    "apelido obrigatorio: o ASN %d e o do route server e ja "
                    "esta no peer %s" % (peer.asn, outro.nome)))
            else:
                # Sem apelido o token E o ASN, e por isso ele colide: nao ha
                # trava no ASN (dois peers do mesmo cliente sao legitimos), o
                # que nao pode e repetir o token, que e o nome do peer no
                # equipamento e nos arquivos de out/. O campo e o apelido
                # porque e ele que resolve
                erros.append(Erro(
                    "apelido",
                    "o ASN %d ja e o token do peer %s: de um apelido a este "
                    "peer" % (peer.asn, outro.nome)))
```

- [ ] **Step 4: Rodar e ver passar**

```bash
.venv/bin/python -m pytest tests/test_validate.py tests/test_api_peers.py -q
```

Expected: PASS. Tres testes que prendiam o campo antigo mudam junto, na mesma
classe, porque o `CLIENTE` do `dados_api` nao tem apelido:
`test_validate.py::test_asn_repetido_e_erro`,
`::test_asn_renomeado_para_um_ja_usado_e_erro_no_modo_edicao` e
`test_api_peers.py::test_asn_repetido_e_recusado_no_campo`.

- [ ] **Step 5: O e2e que esperava a mensagem antiga**

Em `web/e2e/fluxos.spec.ts`, no fluxo "duplicar e ajustar" (linha ~79), a assercao passa a esperar a mensagem nova:

```ts
  // o peer 1 do cadastro do e2e tem apelido (ACME), entao a copia colide no
  // apelido, e o erro aponta o apelido: a mensagem antiga culpava o ASN
  await expect(page.getByRole("alert").first()).toContainText("ja e o token do peer")
```

- [ ] **Step 6: Rodar a suite e o e2e**

```bash
.venv/bin/python -m pytest -q
cd web && npm test && npm run e2e
```

Expected: PASS nos tres.

- [ ] **Step 7: Commit**

```bash
git add app/validate.py tests/test_validate.py web/e2e/fluxos.spec.ts
git commit -m "O erro de token aponta o apelido quando e o apelido que colide"
```

---

### Task 13: O campo de valor longo nao invade a coluna vizinha

O operador abriu a copia do ALT num viewport logo acima do `xl` e viu os campos
sobrepostos: o select da origem ("1100 - fora da tabela do tipo") pintado por
cima do rotulo do POP, e o do prepend por cima do keepalive.

A causa: `web/src/components/ui/select.tsx:43` monta o `SelectTrigger` com
`w-fit` e `whitespace-nowrap`, e `Formulario.tsx:229` o usa sem classe nenhuma.
Em `xl` o painel de saida toma `minmax(0, 42rem)` da largura (o grid de duas
colunas da tela esta em `PeerTela.tsx:411`), entao as tres colunas do formulario
ficam com **88,66px** cada (medido em 2026-09-27; o plano estimava ~110px): o
select, que e do tamanho do proprio texto, estoura a celula do grid e pinta por
cima do vizinho. O `line-clamp-1` que o componente ja poe no valor nao ajuda
enquanto o gatilho nao tiver largura para clampar.

> Nota de execucao (2026-09-27): o Step 1 e o Step 3 abaixo estao na versao que
> foi executada. A assercao do plano comparava a origem com o POP e foi medida
> como insatisfazivel — o POP abre a linha de baixo (y=603,5 contra y=516,5) no
> x=281, e a origem comeca em x=482,33, entao nenhuma largura passaria; a
> fronteira virou a propria celula. E o `min-w-0` do `Campo.tsx` foi medido
> INERTE nos tres pontos de uso (o `grid-cols-3` do Tailwind ja emite
> `repeat(3, minmax(0, 1fr))`, minimo zero): quem conserta e o `w-full`.

**Files:**
- Modify: `web/src/components/Formulario.tsx:229` (a classe do `SelectTrigger`)
- Modify: `web/src/components/Campo.tsx` (o `min-w-0` do item do grid)
- Modify: `web/e2e/fluxos.spec.ts` (o caso que mede as caixas)

**Interfaces:**
- Produces: nada para as outras tasks. O `CampoCombo` (o input com `datalist`) e o `Input` comum ja sao `w-full` e nao sofrem disso.

- [ ] **Step 1: Escrever o teste que falha**

Em `web/e2e/fluxos.spec.ts`, no fim:

```ts
test("um valor longo nao invade a coluna vizinha", async ({ page }) => {
  // No xl o painel de saida toma 42rem, entao cada uma das tres colunas do
  // formulario fica com 88,66px (medido, e o que a celula da origem mede
  // abaixo). O select do shadcn nasce `w-fit`: com um valor longo ele estourava
  // a celula do grid e pintava por cima do campo ao lado. A medida e a unica
  // prova possivel aqui: jsdom nao calcula layout
  await page.goto("/peers/1")
  const origem = page.getByLabel("Origem da rota")
  await expect(origem).toBeVisible()

  // A celula do grid e a fronteira da coluna, e e ela que a invasao atravessa:
  // a origem fecha a terceira coluna da linha, e o que ficava por cima era o
  // painel de saida. O POP nao serve de fronteira: ele abre a linha de baixo
  // (celula em y=603,5 contra y=516,5 da origem) e comeca a esquerda dela.
  // Medido antes do conserto: o gatilho terminava em 733,61 e a celula em 570,98
  const celula = await page.locator('[data-campo="origem"]').boundingBox()
  const a = await origem.boundingBox()
  expect(a && celula).toBeTruthy()

  // A medida so prova algo enquanto a coluna for estreita: a partir de ~245px o
  // gatilho w-fit cabe sozinho e o caso ficaria verde sem conserto nenhum. Hoje
  // a celula mede 88,66, entao a folga e grande: a guarda e para o dia em que a
  // largura mudar, e nao para hoje
  expect(celula!.width).toBeLessThan(150)
  expect(a!.x + a!.width).toBeLessThanOrEqual(celula!.x + celula!.width + 1)
})
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npm run e2e -- --project=chromium -g "nao invade"
```

Expected: FAIL, porque o gatilho atravessa a borda da propria celula. Se ele
passar de primeira, o viewport do caso nao esta reproduzindo o aperto do `xl`:
confira que a janela tem 1280 de largura (o padrao do `devices["Desktop Chrome"]`)
e que as tres colunas estao de pe.

- [ ] **Step 3: O gatilho com largura da coluna**

Em `web/src/components/Formulario.tsx:229`:

```tsx
            <SelectTrigger id={id} className="w-full min-w-0">
```

O `w-full` faz o gatilho caber na celula, e o `line-clamp-1` que o componente ja
aplica ao valor passa a ter efeito: o texto longo e cortado com reticencias em
vez de vazar. O `min-w-0` fica como defensivo: medido em 2026-09-27, ele e INERTE neste ponto
de uso (a celula mede 88,66 com e sem a classe), e quem faz o gatilho caber e o
`w-full`. O componente base (`web/src/components/ui/select.tsx:43`) nasce com
`w-fit` e `whitespace-nowrap`, sem `min-w-0` nenhum.

- [ ] **Step 4: O item do grid tambem encolhe**

Em `web/src/components/Campo.tsx`, o wrapper do campo:

```tsx
    <div
      data-campo={nome}
      className={cn("flex min-w-0 flex-col gap-1", largo && "sm:col-span-2")}
    >
```

O `min-w-0` fica (e o que o campo pede de um item de grid), mas ele foi medido
INERTE nos tres pontos de uso: o `grid-cols-3` do Tailwind emite
`repeat(3, minmax(0, 1fr))`, ou seja o minimo da trilha ja e zero, e a celula
mede 88,66 com e sem a classe. A explicacao do `min-width: auto` vale para uma
trilha `1fr` pura, que nao e a daqui — quem conserta o campo e o `w-full` do
Step 3.

- [ ] **Step 5: Rodar e ver passar**

```bash
cd web && npm run e2e -- --project=chromium -g "nao invade"
```

Expected: PASS.

- [ ] **Step 6: Rodar tudo o que a mudanca pode ter tocado**

```bash
cd web && npm test && npm run lint && npm run e2e
.venv/bin/python -m pytest -q
```

Expected: PASS nos quatro. O layout do formulario e usado pelas telas de peer e
de grupo, entao o e2e inteiro (os cinco fluxos e a copia) e a prova de que nada
quebrou de visual.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/Formulario.tsx web/src/components/Campo.tsx web/e2e/fluxos.spec.ts
git commit -m "O campo de valor longo para de invadir a coluna vizinha"
```

---

### Task 14: As duas sobras da tela dos prefixos

A revisao da Task 9 achou duas coisas que nao pertencem ao brief dela: o recado do IRR ainda cai no `_corpo` generico antes do recado proprio, e o caso que ela escreveu clica no salvar sem esperar o registro chegar.

**Files:**
- Modify: `web/src/telas/prefixos/PrefixosTela.tsx:112` (a corrente do recado do IRR)
- Modify: `web/src/telas/prefixos/PrefixosTela.test.tsx` (o caso novo e a espera do caso da Task 9)

- [ ] **Step 1: Escrever o teste que falha**

```tsx
  it("um 5xx fora do modelo na consulta ao IRR usa o recado do IRR", async () => {
    // o `_corpo` do lerRecusa ("resposta inesperada da API") e o que sobra
    // quando o corpo nao tem forma de recusa, e ele nao diz nada sobre o IRR:
    // no ramo do salvar a Task 9 ja o tinha tirado, e aqui ficou
    mockFetch({ ...BASE, "POST /api/blocos/irr": { status: 500, corpo: "sem forma" } })
    montarRota(rotas, "/prefixos")
    await screen.findByLabelText(/IPv4/)
    await userEvent.click(screen.getByRole("button", { name: /consultar IRR/i }))

    expect(await screen.findByText(/a consulta ao IRR falhou/)).toBeInTheDocument()
    expect(screen.queryByText(/resposta inesperada da API/)).not.toBeInTheDocument()
  })
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd web && npx vitest run src/telas/prefixos/PrefixosTela.test.tsx -t "fora do modelo"
```

Expected: FAIL: o que aparece na tela e o texto do `_corpo`.

- [ ] **Step 3: O `_corpo` sai da corrente**

Em `web/src/telas/prefixos/PrefixosTela.tsx:112`:

```tsx
        // O `_corpo` do lerRecusa fica fora desta corrente: ele e o texto de
        // quando o corpo nao tem forma de recusa, e nao diz nada sobre a
        // consulta. O recado proprio e a mensagem que sobra
        setRecusa(recusaComMarca(r.error, lida.erros.bgpq4 ?? lida.erros._ ?? "a consulta ao IRR falhou"))
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd web && npx vitest run src/telas/prefixos/PrefixosTela.test.tsx -t "fora do modelo"
```

Expected: PASS.

- [ ] **Step 5: A espera que faltava no caso da Task 9**

No caso "um 5xx sem corpo de recusa nao mostra o texto de resposta inesperada", depois do `montarRota`:

```tsx
    montarRota(rotas, "/prefixos")
    // o botao so habilita com o registro na mao, e o clique antes disso nao
    // sai: a espera e a do estado, e nao a da existencia do formulario, que
    // existe desde o primeiro render
    const botao = await screen.findByRole("button", { name: /^salvar/i })
    await waitFor(() => expect(botao).toBeEnabled())
    await userEvent.click(botao)
```

A espera da forma original deste step (`await screen.findByLabelText(/IPv4/)`) foi
medida como no-op: o rotulo existe desde o primeiro render, porque o formulario
inteiro esta montado antes de o registro chegar, entao ela nao esperava nada. Quem
entrou foi a espera do estado habilitado, que nao resolve enquanto o
`GET /api/blocos` esta preso (rodada 2 da Task 14).

- [ ] **Step 6: A suite do front e o lint**

```bash
cd web && npm test && npm run lint
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/src/telas/prefixos/PrefixosTela.tsx web/src/telas/prefixos/PrefixosTela.test.tsx
git commit -m "O recado do IRR nao mostra mais o texto de corpo fora do modelo"
```

---

## Tabela de pendencias

Cada pendencia registrada nas etapas anteriores e onde ela fecha nesta leva.

| Pendencia (onde foi registrada) | Onde fecha |
| --- | --- |
| A tela de lista nao existe (plano do front, "Pendencias conhecidas") | Nao fecha: decidido em 2026-09-27 como estado vazio, e a lista e a barra lateral |
| ASN repetido entre peers (plano do front) | Nao fecha: decidido em 2026-09-27 que o token e a identidade, e duas sessoes do mesmo cliente sao legitimas |
| O risco de Safari no "salvar e copiar" (plano do front) | Task 10, medido nos dois navegadores |
| A precondicao do `test_tipos_api.py` (plano do front) | Nao entra: o container nao tem `npm`, e a condicao atual ja olha os dois |
| Os minors adiados do front (plano do front) | Tasks 3, 4, 5, 6, 7 e 8 |
| Os tres registros de manutencao da re-revisao (plano do front) | Tasks 9 (dois deles) e 2 (`camposDoErro`) |
| Os quatro do e2e (plano do front) | Task 10 |
| O buraco da origem no upstream (plano do corte) | Task 1, como aviso |
| O `graphify update .` no checkout principal (plano do corte) | Feito no merge, fora desta leva |
| Os comentarios que citam `_contexto` e "a tela HTML" (revisao do corte) | Task 11 |
| A mensagem `ASN ja usado` apontando o ASN quando o que colide e o apelido (achado pelo operador, na copia do ALT) | Task 12 |
| Os campos sobrepostos no formulario, com o select de valor longo pintando por cima do vizinho (achado pelo operador, na mesma tela) | Task 13 |
| O recado do IRR caindo no `_corpo` generico e a espera do caso dos prefixos (revisao da Task 9) | Task 14 |

## Fechamento

Ao fim das quatorze tasks, o que as tres etapas do front deixaram registrado esta
fechado ou decidido, mais os dois achados que o operador trouxe da tela da copia
do ALT (o erro de token e os campos sobrepostos). Duas coisas continuam em aberto de proposito, e as duas
estao escritas nos planos das etapas: a tela de lista no corpo (que virou estado
vazio por decisao) e a origem dos tres upstreams do cadastro real (que o aviso
mostra e o operador decide).

O que **nao** muda: nenhuma linha de `plan.py`, `render.py`, `peers.py`,
`prefixes.py`, `api.py` ou `modelos_api.py`; nenhum byte da saida gerada; e o
`peers.yaml` do operador continua intocado.

