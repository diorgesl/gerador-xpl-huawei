# Grupos de peers (cliente/parceiro) — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao `bgpgen` uma camada de "grupo BGP" (o `group` do VRP) para os tipos `cliente` e `parceiro`: peers desses tipos podem compartilhar um único route-filter de import/export, com a possibilidade de um peer ter filtro próprio por cima.

**Architecture:** Uma entidade nova, `Grupo`, irmã de `Peer` em `peers.yaml`. Peer ganha `grupo_id` opcional. A lógica de filtro de import/export de cliente/parceiro — hoje só em `cliente.txt.j2` — é extraída para macros reutilizáveis em `_macros.j2`, parametrizadas por qualquer objeto com `.token`/`.asn`/`.tipo`/`.origem`/`.pop`/`.prefixos`. Essas macros passam a alimentar três saídas: o peer avulso (sem mudança de comportamento), o bloco do grupo (`out/grupo-<nome>.txt`, token = nome do grupo) e o filtro de override de um peer membro (mesmas macros, token = token do peer).

**Tech Stack:** Python 3.14, FastAPI, Jinja2, pytest — os mesmos do resto do `bgpgen`. Sem dependência nova.

**Spec:** `docs/superpowers/specs/2026-09-22-grupos-de-peers-design.md`

## Global Constraints

- Isolamento: gerar/editar/excluir um peer não pode mudar a saída de outro peer nem a do grupo; gerar/editar/excluir um grupo não pode mudar a saída de nenhum peer. Vale pra todo task que escreve em `out/`.
- Saída ASCII puro (o app já valida isso para peer; grupo segue a mesma regra).
- `xpl simulate` não aceita filtro parametrizado — nenhuma saída gerada leva `$`.
- `peers.yaml` é o único estado; sem banco, sem migração automática do cadastro existente.

## Fora do escopo deste plano

Este plano cobre só os tipos `cliente` e `parceiro`, e só o campo `asn`/`prefixos` do grupo como foram desenhados no spec. Ficam para um plano seguinte, depois deste rodar na prática:

- Grupo para `upstream`, `ix`, `pni` (o spec já cobre o desenho; a extração de macros deste plano é o que torna isso menor depois).
- `remover.txt.j2` para um peer com filtro próprio (override): o `undo` gerado ainda assume o peer avulso de hoje. Um membro sem override já sai correto (task 6 cobre os dois casos de membro; só o override de remoção fica years pendente).
- Bloco de remoção do próprio grupo (`undo group <NOME>` etc.).
- Integração do select de grupo na tela única (`pagina.html`) com o JS de mostrar/esconder campo por tipo que já existe lá. Este plano entrega uma página própria e mais simples para o CRUD de grupo, e um `<select>` estático no formulário de peer.

## Global Constraints — pré-requisito de cada task

Rodar a partir da raiz do checkout, com o venv já criado (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`). Toda task termina com `.venv/bin/python -m pytest -q` limpo antes do commit — **exceto** as 6 falhas pré-existentes em `tests/test_render.py` (route-limit de upstream/IX/PNI/parceiro, commit `66c6f54`), que são de outra frente de trabalho e não deste plano: se ainda estiverem quebradas quando você começar, rode só o arquivo/teste que a task tocou (`pytest tests/test_peers.py -q`, etc.) em vez da suíte inteira, e confirme no teste de isolamento (task 10) que nenhuma delas piorou.

---

### Task 1: `Grupo`, entidade nova em `app/peers.py`

**Files:**
- Modify: `app/peers.py`
- Test: `tests/test_peers.py`

**Interfaces:**
- Produces: `Grupo` (dataclass), `Grupo.para_dict()`, `Grupo.de_dict(d)`, `Grupo.token` (property, = `nome`), `Grupo.arquivo()` (= `OUT / "grupo-<nome>.txt"`), `carregar_grupos(caminho=PEERS_YAML)`, `gravar_grupos(grupos, caminho=PEERS_YAML)`, `achar_grupo(grupos, nome)`, `achar_grupo_id(grupos, ident)`, `proximo_id_grupo(grupos)`.
- Consumes: nada de outra task.

Hoje `gravar(peers, caminho)` sobrescreve o arquivo inteiro com `{"peers": [...]}"`, o que apagaria uma seção `grupos:` já gravada. Este task also corrige isso com um `_ler_bruto` compartilhado.

- [ ] **Step 1: Escreva o teste de round-trip de grupo**

Em `tests/test_peers.py`, adicione:

```python
def test_grupo_grava_e_relê_igual(tmp_path):
    caminho = tmp_path / "peers.yaml"
    g = mod.Grupo(id=0, nome="PARCEIROS_CDN", tipo="parceiro", lp_base=300,
                  origem=1100, pop=2001, classe="transito")
    mod.gravar_grupos([g], caminho)
    assert mod.carregar_grupos(caminho) == [g]


def test_gravar_peers_nao_apaga_grupos_existentes(tmp_path):
    caminho = tmp_path / "peers.yaml"
    g = mod.Grupo(id=0, nome="PARCEIROS_CDN", tipo="parceiro")
    mod.gravar_grupos([g], caminho)
    mod.gravar([mod.Peer(id=0, nome="Cliente", tipo="cliente", asn=64500)], caminho)
    assert mod.carregar_grupos(caminho) == [g]


def test_gravar_grupos_nao_apaga_peers_existentes(tmp_path):
    caminho = tmp_path / "peers.yaml"
    p = mod.Peer(id=0, nome="Cliente", tipo="cliente", asn=64500)
    mod.gravar([p], caminho)
    mod.gravar_grupos([mod.Grupo(id=0, nome="X", tipo="parceiro")], caminho)
    assert mod.carregar(caminho) == [p]


def test_proximo_id_grupo_acha_o_primeiro_livre():
    grupos = [mod.Grupo(id=0, nome="A"), mod.Grupo(id=2, nome="B")]
    assert mod.proximo_id_grupo(grupos) == 1


def test_achar_grupo_por_nome_e_por_id():
    g = mod.Grupo(id=5, nome="PARCEIROS_CDN")
    assert mod.achar_grupo([g], "PARCEIROS_CDN") is g
    assert mod.achar_grupo_id([g], 5) is g
    assert mod.achar_grupo([g], "NADA") is None
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `.venv/bin/python -m pytest tests/test_peers.py -k grupo -v`
Expected: FAIL — `AttributeError: module 'app.peers' has no attribute 'Grupo'`

- [ ] **Step 3: Implemente `Grupo` e as funções de persistência**

Em `app/peers.py`, depois da classe `Peer` (antes de `carregar`), adicione:

```python
MAX_GRUPOS = 100


@dataclass
class Grupo:
    id: int = 0
    nome: str = ""
    tipo: str = "cliente"
    # None: cada peer membro declara o proprio ASN. Setado: os membros
    # herdam, so precisam do proprio quando o grupo nao tem (ver spec,
    # "Modelo de dados").
    asn: int | None = None
    classe: str | None = None
    lp_base: int = 300
    origem: int | None = None
    pop: int | None = None
    ap_block: list = field(default_factory=list)
    ap_te: list = field(default_factory=list)
    ap_allowed: list = field(default_factory=list)
    ap_prefer: list = field(default_factory=list)
    prepend_base: int = 0
    bh_upstream: str = ""
    default_route: bool = False
    bfd: bool = True
    graceful_restart: bool = True
    timer_keepalive: int | None = None
    timer_hold: int | None = None
    # so cliente/parceiro; vazio = grupo sem confinamento de prefixo (o caso
    # "varios parceiros distintos"), preenchido = mesmo cliente redundante
    prefixos: dict = field(default_factory=_listas_por_familia)

    @property
    def token(self):
        return self.nome

    def arquivo(self):
        return OUT / ("grupo-%s.txt" % self.nome)

    def para_dict(self):
        return {
            "id": self.id, "nome": self.nome, "tipo": self.tipo,
            "asn": self.asn, "classe": self.classe, "lp_base": self.lp_base,
            "origem": self.origem, "pop": self.pop,
            "ap_block": self.ap_block, "ap_te": self.ap_te,
            "ap_allowed": self.ap_allowed, "ap_prefer": self.ap_prefer,
            "prepend_base": self.prepend_base, "bh_upstream": self.bh_upstream,
            "default_route": self.default_route, "bfd": self.bfd,
            "graceful_restart": self.graceful_restart,
            "timer_keepalive": self.timer_keepalive,
            "timer_hold": self.timer_hold, "prefixos": self.prefixos,
        }

    @classmethod
    def de_dict(cls, d):
        conhecidos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in conhecidos})
```

Substitua o corpo de `carregar` e `gravar` para passarem por um leitor cru compartilhado, e adicione o par de grupo:

```python
def _ler_bruto(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def _escrever_bruto(dados, caminho):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        yaml.safe_dump(dados, allow_unicode=False, sort_keys=False),
        encoding="utf-8")


def carregar(caminho=PEERS_YAML):
    dados = _ler_bruto(caminho)
    return [Peer.de_dict(d) for d in dados.get("peers", [])]


def gravar(peers, caminho=PEERS_YAML):
    dados = _ler_bruto(caminho)
    dados["peers"] = [p.para_dict() for p in peers]
    _escrever_bruto(dados, caminho)


def carregar_grupos(caminho=PEERS_YAML):
    dados = _ler_bruto(caminho)
    return [Grupo.de_dict(d) for d in dados.get("grupos", [])]


def gravar_grupos(grupos, caminho=PEERS_YAML):
    dados = _ler_bruto(caminho)
    dados["grupos"] = [g.para_dict() for g in grupos]
    _escrever_bruto(dados, caminho)


def proximo_id_grupo(grupos):
    usados = {g.id for g in grupos}
    for i in range(MAX_GRUPOS):
        if i not in usados:
            return i
    raise ValueError("sem ID livre: a faixa 0-99 esta cheia")


def achar_grupo(grupos, nome):
    for g in grupos:
        if g.nome == nome:
            return g
    return None


def achar_grupo_id(grupos, ident):
    for g in grupos:
        if g.id == ident:
            return g
    return None
```

Remova o corpo antigo de `carregar`/`gravar` (os que liam/escreviam só `{"peers": ...}` direto) — a versão acima os substitui.

- [ ] **Step 4: Rode e confirme que passa**

Run: `.venv/bin/python -m pytest tests/test_peers.py -v`
Expected: PASS — todos os testes de `test_peers.py`, os novos e os que já existiam (o `_ler_bruto`/`_escrever_bruto` não muda o formato do que já é lido/escrito para `peers`).

- [ ] **Step 5: Commit**

```bash
git add app/peers.py tests/test_peers.py
git commit -m "Adiciona a entidade Grupo e sua persistência em peers.yaml"
```

---

### Task 2: `Peer.grupo_id` e `Peer.tem_filtro_proprio()`

**Files:**
- Modify: `app/peers.py`
- Test: `tests/test_peers.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Peer.grupo_id: int | None` (persistido), `Peer.tem_filtro_proprio() -> bool` — usado pelas tasks 3, 6 e 10 como a única fonte de verdade sobre "este membro tem filtro próprio".

- [ ] **Step 1: Escreva o teste**

```python
def test_grupo_id_grava_e_rele():
    caminho_tmp = "grupo_id_roundtrip.yaml"
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        caminho = pathlib.Path(d) / caminho_tmp
        p = mod.Peer(id=0, nome="X", tipo="parceiro", asn=64500, grupo_id=3)
        mod.gravar([p], caminho)
        assert mod.carregar(caminho)[0].grupo_id == 3


def test_tem_filtro_proprio():
    sem_nada = mod.Peer(id=0, tipo="parceiro", asn=1, grupo_id=1)
    com_prefixo = mod.Peer(id=0, tipo="parceiro", asn=1, grupo_id=1,
                           prefixos={"v4": ["203.0.113.0/24"], "v6": []})
    com_community = mod.Peer(id=0, tipo="parceiro", asn=1, grupo_id=1,
                             communities=["64500:100"])
    assert sem_nada.tem_filtro_proprio() is False
    assert com_prefixo.tem_filtro_proprio() is True
    assert com_community.tem_filtro_proprio() is True
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `.venv/bin/python -m pytest tests/test_peers.py -k "grupo_id or filtro_proprio" -v`
Expected: FAIL — `TypeError: Peer.__init__() got an unexpected keyword argument 'grupo_id'`

- [ ] **Step 3: Implemente**

No dataclass `Peer`, logo depois do campo `default_route`:

```python
    # grupo BGP (VRP `group`) a que este peer pertence, ou None fora de
    # grupo. So cliente/parceiro por enquanto - ver spec de 2026-09-22.
    grupo_id: int | None = None
```

No `para_dict`, adicione `"grupo_id": self.grupo_id,` (mesma posição, perto de `default_route`). `de_dict` já pega o campo pela lista de `__dataclass_fields__`, não precisa mudar.

Adicione o método, perto de `familias()`:

```python
    def tem_filtro_proprio(self):
        """Membro de grupo com politica propria: prefixo ou CL-PEER.

        Fora de grupo isso nao significa nada - todo peer avulso ja tem
        filtro proprio. Dentro de um grupo, e o que decide se o membro
        recebe o filtro dele (igual ao peer avulso) ou so herda do grupo.
        """
        tem_prefixo = any(self.prefixos.get(f) for f in FAMILIAS)
        return bool(tem_prefixo or self.communities or self.large_communities)
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `.venv/bin/python -m pytest tests/test_peers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/peers.py tests/test_peers.py
git commit -m "Adiciona Peer.grupo_id e Peer.tem_filtro_proprio()"
```

---

### Task 3: Validação de grupo e de peer agrupado

**Files:**
- Modify: `app/validate.py`
- Modify: `app/app.py:295` (única chamada de `validate.validar`, precisa do novo argumento)
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `Peer.grupo_id`, `Peer.tem_filtro_proprio()` (task 2); `Grupo`, `achar_grupo_id` (task 1).
- Produces: `validar_grupo(grupo, grupos, peers) -> list[Erro]`, `validar(peer, peers, anterior=None, grupos=None) -> list[Erro]` (assinatura estendida, compatível: `grupos=None` equivale a `[]`).

Regras novas, do spec ("Validação — regras novas") mais o que a task 4/5 exige do grupo (`prefixos` preenchido exige `asn`, porque o filtro do grupo usa `alvo.asn` dentro do próprio ramo de `prefixos`):

- [ ] **Step 1: Escreva os testes**

Em `tests/test_validate.py`:

No topo de `tests/test_validate.py`, troque `from app.peers import Peer` por `from app.peers import Peer, Grupo`. Depois:

```python
def um_grupo(**over):
    base = dict(id=0, nome="PARCEIROS_CDN", tipo="parceiro", lp_base=300,
               classe="transito", origem=1100, pop=2001)
    base.update(over)
    return Grupo(**base)


def test_grupo_valido_sem_erro():
    assert validate.validar_grupo(um_grupo(), [], []) == []


def test_grupo_nome_invalido():
    assert "nome" in campos(validate.validar_grupo(um_grupo(nome="minusculo"), [], []))
    assert "nome" in campos(validate.validar_grupo(um_grupo(nome="A B"), [], []))


def test_grupo_nome_duplicado():
    outro = um_grupo(id=1, nome="PARCEIROS_CDN")
    assert "nome" in campos(validate.validar_grupo(um_grupo(id=0), [outro], []))


def test_grupo_tipo_fora_do_suportado():
    assert "tipo" in campos(validate.validar_grupo(um_grupo(tipo="upstream"), [], []))


def test_grupo_downstream_exige_classe_origem_pop():
    assert "classe" in campos(validate.validar_grupo(um_grupo(classe=None), [], []))
    assert "origem" in campos(validate.validar_grupo(um_grupo(origem=None), [], []))
    assert "pop" in campos(validate.validar_grupo(um_grupo(pop=None), [], []))


def test_grupo_com_prefixo_exige_asn():
    g = um_grupo(asn=None, prefixos={"v4": ["203.0.113.0/24"], "v6": []})
    assert "prefixos" in campos(validate.validar_grupo(g, [], []))


def test_grupo_sem_asn_e_sem_prefixo_passa():
    assert validate.validar_grupo(um_grupo(asn=None), [], []) == []


def test_peer_agrupado_dispensa_classe_origem_pop_prefixo():
    grupo = Grupo(id=1, nome="PARCEIROS_CDN", tipo="parceiro", lp_base=300,
                 classe="transito", origem=1100, pop=2001)
    p = um_peer(tipo="parceiro", classe=None, origem=None, pop=None,
               prefixos={"v4": [], "v6": []}, grupo_id=1)
    assert validate.validar(p, [], grupos=[grupo]) == []


def test_peer_agrupado_com_prefixo_proprio_exige_classe_origem_pop():
    grupo = Grupo(id=1, nome="PARCEIROS_CDN", tipo="parceiro")
    p = um_peer(tipo="parceiro", classe=None, origem=None, pop=None,
               prefixos={"v4": ["203.0.113.0/24"], "v6": []}, grupo_id=1)
    erros = campos(validate.validar(p, [], grupos=[grupo]))
    assert "classe" in erros and "origem" in erros and "pop" in erros


def test_peer_com_grupo_inexistente_e_erro():
    p = um_peer(tipo="parceiro", grupo_id=99)
    assert "grupo_id" in campos(validate.validar(p, [], grupos=[]))


def test_peer_com_tipo_diferente_do_grupo_e_erro():
    grupo = Grupo(id=1, nome="X", tipo="cliente")
    p = um_peer(tipo="parceiro", grupo_id=1)
    assert "grupo_id" in campos(validate.validar(p, [], grupos=[grupo]))
```

(`um_peer` já existe em `tests/test_validate.py`; confirme que ela aceita `**over` incluindo `grupo_id` e `classe=None` — se `um_peer` tiver um default de `classe` fixo, os testes acima que passam `classe=None` continuam valendo porque passam o `over` explícito.)

- [ ] **Step 2: Rode e confirme que falha**

Run: `.venv/bin/python -m pytest tests/test_validate.py -k grupo -v`
Expected: FAIL — `AttributeError: module 'app.validate' has no attribute 'validar_grupo'`

- [ ] **Step 3: Implemente**

Em `app/validate.py`, adicione depois de `_valida_ascii`:

```python
NOME_GRUPO_RE = re.compile(r"^[A-Z0-9_]{1,32}$")
# so estes dois tipos por enquanto - ver "Fora do escopo" do plano de
# 2026-09-22
TIPOS_COM_GRUPO = ("cliente", "parceiro")


def validar_grupo(grupo, grupos, peers):
    erros = []

    if not NOME_GRUPO_RE.match(grupo.nome or ""):
        erros.append(Erro("nome", "nome do grupo: A-Z, 0-9 e _, ate 32 caracteres"))

    if grupo.tipo not in TIPOS_COM_GRUPO:
        erros.append(Erro("tipo", "grupo ainda so suporta cliente e parceiro"))

    if grupo.classe not in plan.CLASSES_CLIENTE:
        erros.append(Erro("classe", "grupo de %s exige uma classe" % grupo.tipo))
    if grupo.origem is None or grupo.origem not in ORIGENS_CLIENTE:
        erros.append(Erro("origem", "origem obrigatoria, faixa 1xxx do plano"))
    if grupo.pop is None:
        erros.append(Erro("pop", "pop em branco: informe o POP do plano, de 2001 a 2999"))
    elif not (plan.POP_MIN <= grupo.pop <= plan.POP_MAX):
        erros.append(Erro("pop", "POP entre 2001 e 2999"))

    if not (0 <= grupo.lp_base <= 65535):
        erros.append(Erro("lp_base", "local preference entre 0 e 65535"))

    tem_prefixo = any(grupo.prefixos.get(f) for f in plan.FAMILIAS)
    if tem_prefixo and not grupo.asn:
        erros.append(Erro(
            "prefixos",
            "grupo com prefixo proprio exige ASN: o filtro usa o ASN do "
            "grupo para o blackhole e o confinamento de as-path"))

    for outro in grupos:
        if outro is grupo:
            continue
        if outro.nome == grupo.nome:
            erros.append(Erro("nome", "nome ja usado pelo grupo %s" % outro.id))

    return _sem_duplicata(erros)
```

Agora estenda `validar(peer, peers, anterior=None, grupos=None)`. A assinatura ganha o parâmetro novo; o corpo troca o trecho do `if peer.tipo in plan.TIPOS_DOWNSTREAM:` para levar em conta o grupo. Substitua:

```python
    if peer.tipo in plan.TIPOS_DOWNSTREAM:
        if peer.classe not in plan.CLASSES_CLIENTE:
            erros.append(Erro("classe", "%s exige uma classe" % peer.tipo))
        if not any(peer.prefixos.get(f) for f in plan.FAMILIAS):
            erros.append(Erro("prefixos", "%s sem prefix-list nao sobe" % peer.tipo))
        if peer.origem is not None and peer.origem not in ORIGENS_CLIENTE:
            erros.append(Erro("origem", "origem fora da faixa 1xxx"))
        if peer.pop is None:
            erros.append(Erro("pop", "pop em branco: informe o POP do plano, de 2001 a 2999"))
        if peer.pop is not None and not (plan.POP_MIN <= peer.pop <= plan.POP_MAX):
            erros.append(Erro("pop", "POP entre 2001 e 2999"))
```

por:

```python
    grupos = grupos or []
    grupo = None
    if peer.tipo in plan.TIPOS_DOWNSTREAM:
        if peer.grupo_id is not None:
            grupo = achar_grupo_id(grupos, peer.grupo_id)
            if grupo is None:
                erros.append(Erro("grupo_id", "grupo nao encontrado"))
            elif grupo.tipo != peer.tipo:
                erros.append(Erro(
                    "grupo_id",
                    "grupo %s e de %s, nao de %s" % (grupo.nome, grupo.tipo, peer.tipo)))

        # fora de grupo, ou dentro de um grupo mas com filtro proprio
        # (prefixo ou CL-PEER): as mesmas regras do peer avulso de sempre.
        # Dentro de um grupo sem filtro proprio, esses campos sao do grupo
        # e o peer nao precisa deles.
        exige = peer.grupo_id is None or peer.tem_filtro_proprio()
        if exige:
            if peer.classe not in plan.CLASSES_CLIENTE:
                erros.append(Erro("classe", "%s exige uma classe" % peer.tipo))
            if not any(peer.prefixos.get(f) for f in plan.FAMILIAS):
                erros.append(Erro("prefixos", "%s sem prefix-list nao sobe" % peer.tipo))
            if peer.pop is None:
                erros.append(Erro("pop", "pop em branco: informe o POP do plano, de 2001 a 2999"))
        if peer.origem is not None and peer.origem not in ORIGENS_CLIENTE:
            erros.append(Erro("origem", "origem fora da faixa 1xxx"))
        if peer.pop is not None and not (plan.POP_MIN <= peer.pop <= plan.POP_MAX):
            erros.append(Erro("pop", "POP entre 2001 e 2999"))
```

No topo do arquivo, importe `achar_grupo_id`:

```python
from app.peers import achar_grupo_id
```

(Confira que isso não fecha um import circular: `app/peers.py` não importa `app/validate.py`, então é seguro.)

Ajuste também a assinatura da função: `def validar(peer, peers, anterior=None, grupos=None):`.

Por fim, em `app/app.py:295`, troque:

```python
    erros = erros + validate.validar(peer, peers, anterior=antigo)
```

por:

```python
    erros = erros + validate.validar(peer, peers, anterior=antigo,
                                     grupos=peers_mod.carregar_grupos(PEERS_YAML))
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `.venv/bin/python -m pytest tests/test_validate.py tests/test_app.py -v`
Expected: PASS — os testes novos e os existentes (a assinatura antiga `validar(peer, peers)` e `validar(peer, peers, anterior=...)` continuam funcionando, `grupos` cai no default).

- [ ] **Step 5: Commit**

```bash
git add app/validate.py app/app.py tests/test_validate.py
git commit -m "Valida grupo e peer agrupado (cliente/parceiro)"
```

---

### Task 4: Extrai o filtro de cliente/parceiro para macros reutilizáveis

**Files:**
- Modify: `templates/_macros.j2`
- Modify: `templates/cliente.txt.j2`
- Test: `tests/test_render.py` (goldens existentes — nenhum teste novo, é um refactor)

**Interfaces:**
- Produces (macros novas em `_macros.j2`): `prefix_lists_downstream(alvo, fam)`, `ap_cust_downstream(alvo)`, `filtro_downstream_import(alvo, fam, chamar_apply_peer)`, `filtro_downstream_export(alvo, fam)`. `alvo` é qualquer objeto com `.token`, `.asn`, `.tipo`, `.origem`, `.pop`, `.prefixos[fam]` — `Peer` já tem todos; `Grupo` (task 1) também.
- Consumes: nada de outra task. É puro refactor do que já existe em `cliente.txt.j2`.

Este task **não muda comportamento nenhum** para peer avulso — é só extração. A prova disso são os goldens: se `test_golden_do_parceiro` (e o de cliente, se existir com esse nome — confira em `tests/test_render.py`) continuarem batendo byte a byte, a extração foi neutra.

- [ ] **Step 1: Rode os goldens atuais e guarde a saída de referência**

Run: `.venv/bin/python -m pytest tests/test_render.py -k golden -v`
Expected: os goldens de cliente/parceiro (e upstream/ix/pni, que este task não toca) no estado atual — anote quais já passavam antes de mexer, para comparar depois. Não há passo de "escrever teste que falha" neste task porque é refactor puro; a rede de segurança são os goldens existentes.

- [ ] **Step 2: Extraia as macros em `_macros.j2`**

Adicione ao fim de `templates/_macros.j2` (mantendo o que já existe acima):

```jinja
{% macro prefix_lists_downstream(alvo, fam) -%}
{% if alvo.prefixos[fam] %}
{% set U = fam|upper %}
{% set kw = "ipv6-prefix-list" if fam == "v6" else "ip-prefix-list" %}
{% set maxlen = 48 if fam == "v6" else 24 %}
{% set hostlen = 128 if fam == "v6" else 32 %}
xpl {{ kw }} PL-CUST-{{ alvo.token }}-{{ U }}
{% for cidr in alvo.prefixos[fam] %}
 {{ plan.cidr_para_xpl(cidr) }} le {{ maxlen }}{{ "," if not loop.last }}
{% endfor %}
end-list

xpl {{ kw }} PL-CUST-{{ alvo.token }}-BH-{{ U }}
{% for cidr in alvo.prefixos[fam] %}
 {{ plan.cidr_para_xpl(cidr) }} ge {{ hostlen }} le {{ hostlen }}{{ "," if not loop.last }}
{% endfor %}
end-list

{% endif -%}
{%- endmacro %}

{% macro ap_cust_downstream(alvo) -%}
{% if alvo.asn %}
xpl as-path-list AP-CUST-{{ alvo.token }}
 origin '{{ alvo.asn }}'
end-list
{% endif -%}
{%- endmacro %}

{# call_apply_peer=true: o caller de sempre, cliente/parceiro avulso e
   membro de grupo com filtro proprio, ambos tem CL-PEER-<token> deles
   mesmos. call_apply_peer=false: o filtro do GRUPO (task 5), que nao tem
   CL-PEER proprio - isso e por sessao, nao por grupo (ver spec). #}
{% macro filtro_downstream_import(alvo, fam, chamar_apply_peer) -%}
{% set U = fam|upper %}
{% set nexthop = "100::" if fam == "v6" else "192.0.2.1" %}
xpl route-filter CUST-{{ alvo.token }}-IMPORT-{{ U }}
 call route-filter IMPORT-SANITY-{{ U }}
{% if alvo.prefixos[fam] %}
 if (community matches-any CL-BLACKHOLE or tag eq 666) and ip route-destination in PL-CUST-{{ alvo.token }}-BH-{{ U }} then
  apply {{ "ipv6" if fam == "v6" else "ip" }} next-hop {{ nexthop }}
  apply local-preference {{ plan.LP_BLACKHOLE }}
  apply community {{ plan.conjunto(plan.BLACKHOLE_INFO, "64512:200") }} additive
  apply large-community {{ plan.conjunto(plan.c_large(1000, alvo.asn)) }} additive
  finish
 endif
 if not ip route-destination in PL-CUST-{{ alvo.token }}-{{ U }} then
  refuse
 endif
{% endif %}
{% if alvo.asn %}
 if not as-path matches-any AP-CUST-{{ alvo.token }} then
  refuse
 endif
{% endif %}
 call route-filter APPLY-CUSTOMER-LP
 apply community {{ plan.c_downstream(alvo.tipo, alvo.origem, alvo.pop) }} additive
{% if alvo.asn %}
 apply large-community {{ plan.conjunto(plan.c_large(1000, alvo.asn)) }} additive
{% endif %}
{% if chamar_apply_peer %}
 call route-filter APPLY-PEER-{{ alvo.token }}
{% endif %}
 finish
end-filter
{%- endmacro %}

{% macro filtro_downstream_export(alvo, fam) -%}
{% set U = fam|upper %}
xpl route-filter CUST-{{ alvo.token }}-EXPORT-{{ U }}
 if community matches-any CL-NOADV-CUST then
  refuse
 endif
 if community matches-any CL-ONLY-NOT-CLIENT then
  refuse
 endif
{% if alvo.asn %}
 if large-community matches-any {{ plan.conjunto(plan.c_large(0, alvo.asn)) }} then
  refuse
 endif
{% endif %}
 if community matches-any {{ plan.conjunto("64512:1900", "64512:1901") }} then
  refuse
 endif
{% if alvo.asn %}
 if large-community matches-any {{ plan.conjunto(plan.c_large(3, alvo.asn)) }} then
  apply as-path 64512 3 additive
 elseif large-community matches-any {{ plan.conjunto(plan.c_large(2, alvo.asn)) }} then
  apply as-path 64512 2 additive
 elseif large-community matches-any {{ plan.conjunto(plan.c_large(1, alvo.asn)) }} then
  apply as-path 64512 1 additive
 endif
{% endif %}
 finish
end-filter
{%- endmacro %}
```

- [ ] **Step 3: Rewire `cliente.txt.j2` para chamar as macros**

Troque o miolo do `{% for fam in peer.familias() %}` (linhas 8-88 do arquivo atual) para:

```jinja
{% for fam in peer.familias() %}
{{ m.prefix_lists_downstream(peer, fam) }}
# Filtro XPL Import
{{ m.filtro_downstream_import(peer, fam, true) }}

{{ m.filtro_downstream_export(peer, fam) }}
{% endfor %}

{{ m.ap_cust_downstream(peer) }}
{{ m.apply_peer(peer) }}
```

Isso substitui, na íntegra, tanto os dois `xpl {{kw}} PL-CUST-...` quanto os dois `xpl route-filter CUST-...-IMPORT/EXPORT...end-filter` e o `xpl as-path-list AP-CUST-...end-list` que hoje estão inline no template. O resto do arquivo (o cabeçalho `{{ m.cabecalho(peer) }}`, o `bgp 64512` e os dois `{% for fam in peer.familias() %}` finais com `sessao_do_peer`/`familia_bgp`) fica como está.

- [ ] **Step 4: Rode os goldens de novo e compare**

Run: `.venv/bin/python -m pytest tests/test_render.py -k "golden and (cliente or parceiro)" -v`
Expected: PASS, byte a byte igual ao que já passava no Step 1. Se algum golden que passava antes falhar agora, o diff do pytest mostra exatamente a diferença de whitespace/ordem — ajuste as quebras de linha das macros (`{%-`/`-%}`) até bater, não o golden.

Run a suíte inteira também, para confirmar que nada de fora de cliente/parceiro quebrou:

Run: `.venv/bin/python -m pytest tests/test_render.py -v`
Expected: as mesmas falhas pré-existentes de route-limit (fora deste plano) e nenhuma nova.

- [ ] **Step 5: Commit**

```bash
git add templates/_macros.j2 templates/cliente.txt.j2
git commit -m "Extrai o filtro de import/export de cliente/parceiro para macros reutilizaveis"
```

---

### Task 5: Bloco do grupo — `out/grupo-<nome>.txt`

**Files:**
- Create: `templates/grupo_cliente.txt.j2`
- Modify: `templates/_macros.j2`
- Modify: `app/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Grupo` (task 1), macros `prefix_lists_downstream`/`ap_cust_downstream`/`filtro_downstream_import`/`filtro_downstream_export` (task 4).
- Produces: `render.render_grupo(grupo) -> str`, `render.escrever_grupo(grupo) -> Path` (grava em `grupo.arquivo()`).

- [ ] **Step 1: Escreva os testes**

Em `tests/test_render.py`, adicione (perto dos outros `peer_*()` de fixture, no mesmo estilo):

```python
def grupo_com_asn():
    return peers.Grupo(id=0, nome="UP-REDUNDANTE", tipo="parceiro", asn=64500,
                       classe="transito", lp_base=300, origem=1100, pop=2001,
                       prefixos={"v4": ["203.0.113.0/24"], "v6": []})


def grupo_sem_asn():
    return peers.Grupo(id=1, nome="PARCEIROS_CDN", tipo="parceiro",
                       classe="transito", lp_base=300, origem=1100, pop=2001)


def test_bloco_do_grupo_com_asn_confina_prefixo_e_as_path():
    texto = render.render_grupo(grupo_com_asn())
    assert "group UP-REDUNDANTE external" in texto
    assert "peer UP-REDUNDANTE as-number 64500" in texto
    assert "xpl ip-prefix-list PL-CUST-UP-REDUNDANTE-V4" in texto
    assert "xpl as-path-list AP-CUST-UP-REDUNDANTE" in texto
    assert "if not ip route-destination in PL-CUST-UP-REDUNDANTE-V4 then" in texto
    assert "if not as-path matches-any AP-CUST-UP-REDUNDANTE then" in texto
    assert "peer UP-REDUNDANTE route-filter CUST-UP-REDUNDANTE-IMPORT-V4 import" in texto
    assert "peer UP-REDUNDANTE route-filter CUST-UP-REDUNDANTE-EXPORT-V4 export" in texto


def test_bloco_do_grupo_sem_asn_nao_confina_nada():
    texto = render.render_grupo(grupo_sem_asn())
    assert "group PARCEIROS_CDN external" in texto
    assert "as-number" not in texto
    assert "PL-CUST-PARCEIROS_CDN" not in texto
    assert "AP-CUST-PARCEIROS_CDN" not in texto
    assert "large-community" not in texto
    assert "peer PARCEIROS_CDN route-filter CUST-PARCEIROS_CDN-IMPORT-V4 import" in texto


def test_bloco_do_grupo_nao_chama_apply_peer():
    # CL-PEER e por sessao, nao por grupo - ver task 3/spec
    texto = render.render_grupo(grupo_com_asn())
    assert "APPLY-PEER" not in texto
    assert "CL-PEER" not in texto


def test_escrever_grupo_grava_no_arquivo_certo(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "OUT", tmp_path)
    monkeypatch.setattr(peers, "OUT", tmp_path)
    destino = render.escrever_grupo(grupo_com_asn())
    assert destino == tmp_path / "grupo-UP-REDUNDANTE.txt"
    assert destino.exists()
```

No topo do arquivo (se ainda não importar), confirme `from app import peers` (o arquivo já deve importar algo de `app.peers` para os `peer_*()` de fixture — se importar só `Peer`, troque para `from app import peers` e ajuste as fixtures existentes para `peers.Peer(...)`, ou adicione `from app.peers import Grupo` junto do que já existe).

- [ ] **Step 2: Rode e confirme que falha**

Run: `.venv/bin/python -m pytest tests/test_render.py -k grupo -v`
Expected: FAIL — `AttributeError: module 'app.render' has no attribute 'render_grupo'`

- [ ] **Step 3: Escreva o template e as macros de sessão do grupo**

Em `templates/_macros.j2`, adicione:

```jinja
{% macro cabecalho_grupo(grupo) -%}
# gerado por bgpgen - nao editar a mao
# grupo {{ grupo.id }} - {{ grupo.tipo }} - nome {{ grupo.nome }}
# pressupoe o bloco base ja aplicado neste equipamento
{%- endmacro %}

{% macro sessao_do_grupo(grupo) -%}
{% if grupo.asn %}
 peer {{ grupo.nome }} as-number {{ grupo.asn }}
{% endif %}
{% if grupo.timer_keepalive and grupo.timer_hold %}
 peer {{ grupo.nome }} timer keepalive {{ grupo.timer_keepalive }} hold {{ grupo.timer_hold }}
{% endif %}
{% if grupo.graceful_restart %}
 peer {{ grupo.nome }} capability-advertise graceful-restart
{% endif %}
{% if grupo.bfd %}
 peer {{ grupo.nome }} bfd enable
{% endif %}
{%- endmacro %}

{% macro familia_grupo(grupo, fam, import_nome, export_nome) -%}
 {{ "ipv6-family" if fam == "v6" else "ipv4-family" }} unicast
  peer {{ grupo.nome }} enable
  peer {{ grupo.nome }} route-filter {{ import_nome }} import
  peer {{ grupo.nome }} route-filter {{ export_nome }} export
  peer {{ grupo.nome }} advertise-community
  peer {{ grupo.nome }} advertise-large-community
{%- endmacro %}
```

Crie `templates/grupo_cliente.txt.j2`. A declaração `group <NOME> external` só existe dentro do `bgp <ASN>`, igual a um `peer` — sai uma vez só, lá dentro:

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho_grupo(grupo) }}

{% for fam in ("v4", "v6") %}
{{ m.prefix_lists_downstream(grupo, fam) }}
# Filtro XPL Import
{{ m.filtro_downstream_import(grupo, fam, false, grupo.prefixos[fam]) }}

{{ m.filtro_downstream_export(grupo, fam) }}
{% endfor %}
{{ m.ap_cust_downstream(grupo) }}

bgp 64512
 group {{ grupo.nome }} external
{{ m.sessao_do_grupo(grupo) }}
{% for fam in ("v4", "v6") %}
{% set U = fam|upper %}
{{ m.familia_grupo(grupo, fam,
     "CUST-" ~ grupo.nome ~ "-IMPORT-" ~ U,
     "CUST-" ~ grupo.nome ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

**Sobre o 4º argumento de `filtro_downstream_import`:** a task 4 (já implementada, revista e commitada) descobriu que a macro `filtro_downstream_import` precisa de um parâmetro explícito `confinar_prefixo` — sem default, igual ao `chamar_apply_peer` — porque um `Peer` avulso sempre confina (mesmo com a família vazia, que aí só recusa tudo, comportamento original preservado) e o `Grupo` precisa do oposto quando não tem prefixo próprio (sem confinamento nenhum, não "recusa tudo"). Passe `grupo.prefixos[fam]` direto (uma lista vazia já é falsy no Jinja) — é isso que ativa/desativa o bloco de blackhole e o `if not ip route-destination in PL-CUST-...` por família, independente do `grupo.asn` (que continua controlando só o confinamento de AS-path e as large-communities endereçadas por ASN, via os guards `{% if alvo.asn %}` que já existem na macro). Se a leitura da macro em `templates/_macros.j2` divergir do que está descrito aqui — ela é a fonte da verdade, não este texto — confirme a assinatura real antes de escrever a chamada.

Note que, diferente do peer, o grupo não tem `.familias()` (não há sessão IP para derivar isso) — o loop usa as duas famílias fixas, `("v4", "v6")`, sempre. Isso significa que o bloco do grupo hoje sempre sai dual-stack; se algum grupo precisar ser só v4, o operador ignora a parte v6 na hora de colar. Registrar isso como aceitável para o v1: adicionar um campo `familias` no `Grupo` para restringir é uma melhoria pequena e separada, não bloqueia este task. Também é normal (e não é bug) que `prefix_lists_downstream` ainda declare `PL-CUST-<NOME>-V6`/`-BH-V6` vazios quando só a família v4 tem prefixo — a macro sempre emite quando chamada (é o call site que decide se chama); esses objetos ficam sem uso na família sem confinamento, o que é inofensivo em XPL.

- [ ] **Step 4: `render.py`**

Em `app/render.py`, adicione:

```python
def render_grupo(grupo):
    nome = "grupo_%s.txt.j2" % grupo.tipo
    return ambiente().get_template(nome).render(grupo=grupo)


def escrever_grupo(grupo):
    OUT.mkdir(parents=True, exist_ok=True)
    destino = grupo.arquivo()
    destino.write_text(render_grupo(grupo), encoding="ascii")
    return destino
```

(`grupo_%s.txt.j2" % grupo.tipo` dá `grupo_cliente.txt.j2` tanto para `tipo="cliente"` quanto teria que dar para `tipo="parceiro"` — mas só existe o arquivo `grupo_cliente.txt.j2`. Adicione o mesmo mapeamento que `TEMPLATE_POR_TIPO` já faz para peer: `TEMPLATE_POR_TIPO_GRUPO = {"parceiro": "grupo_cliente.txt.j2"}`, e troque a linha por `nome = TEMPLATE_POR_TIPO_GRUPO.get(grupo.tipo, "grupo_%s.txt.j2" % grupo.tipo)` — mesmo padrão que `render_peer` já usa.)

- [ ] **Step 5: Rode e confirme que passa**

Run: `.venv/bin/python -m pytest tests/test_render.py -v`
Expected: PASS nos testes novos; as mesmas falhas pré-existentes de route-limit continuam (não são deste task) e nenhuma nova aparece.

- [ ] **Step 6: Commit**

```bash
git add templates/grupo_cliente.txt.j2 templates/_macros.j2 app/render.py tests/test_render.py
git commit -m "Gera o bloco do grupo (out/grupo-<nome>.txt) para cliente/parceiro"
```

---

### Task 6: Bloco do peer membro — enxuto, com override opcional

**Files:**
- Modify: `templates/cliente.txt.j2`
- Modify: `templates/remover.txt.j2`
- Modify: `app/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Peer.grupo_id`, `Peer.tem_filtro_proprio()` (task 2); `Grupo` (task 1); macros da task 4.
- Produces: `render.render_peer(peer, grupo=None)` (assinatura estendida), `render.escrever_peer(peer, grupo=None)`.

- [ ] **Step 1: Escreva os testes**

```python
def peer_membro_sem_override(grupo_id=1):
    return peers.Peer(id=2, nome="GIS TELECOM", tipo="parceiro", asn=264130,
                      grupo_id=grupo_id,
                      sessoes={"v4": {"local": "192.0.2.2",
                                     "remoto": "192.0.2.3"}, "v6": {}},
                      descricao="GIS TELECOM")


def peer_membro_com_override(grupo_id=1):
    p = peer_membro_sem_override(grupo_id)
    p.prefixos = {"v4": ["198.51.100.0/24"], "v6": []}
    p.classe = "transito"
    p.origem = 1100
    p.pop = 2001
    return p


def test_membro_sem_override_so_referencia_o_grupo():
    grupo = grupo_sem_asn()
    texto = render.render_peer(peer_membro_sem_override(grupo.id), grupo=grupo)
    assert "peer 192.0.2.3 as-number 264130" in texto
    assert "peer 192.0.2.3 group PARCEIROS_CDN" in texto
    assert "route-filter" not in texto
    assert "PL-CUST" not in texto


def test_membro_com_asn_no_grupo_nao_repete_as_number():
    grupo = grupo_com_asn()
    membro = peer_membro_sem_override(grupo.id)
    membro.asn = grupo.asn
    texto = render.render_peer(membro, grupo=grupo)
    assert "as-number" not in texto
    assert "peer 192.0.2.3 group UP-REDUNDANTE" in texto


def test_membro_com_override_tem_filtro_proprio_ao_lado_do_grupo():
    grupo = grupo_sem_asn()
    texto = render.render_peer(peer_membro_com_override(grupo.id), grupo=grupo)
    assert "xpl route-filter CUST-264130-IMPORT-V4" in texto
    assert "peer 192.0.2.3 group PARCEIROS_CDN" in texto
    assert "peer 192.0.2.3 route-filter CUST-264130-IMPORT-V4 import" in texto
    # export continua do grupo, nao vira filtro proprio (ver task, escopo)
    assert "CUST-264130-EXPORT" not in texto


def test_peer_sem_grupo_continua_igual_a_antes():
    # nenhuma mudanca de comportamento fora de grupo - mesma asserção do
    # golden, so que direto, para nao depender do arquivo golden aqui
    texto_com_none = render.render_peer(peer_cliente())
    texto_com_grupo_none = render.render_peer(peer_cliente(), grupo=None)
    assert texto_com_none == texto_com_grupo_none
```

(`peer_cliente()` já existe no arquivo — confirme o nome exato com `grep "^def peer_cliente" tests/test_render.py`.)

- [ ] **Step 2: Rode e confirme que falha**

Run: `.venv/bin/python -m pytest tests/test_render.py -k membro -v`
Expected: FAIL — `TypeError: render_peer() got an unexpected keyword argument 'grupo'`

- [ ] **Step 3: `render.py`**

Troque `render_peer`:

```python
def render_peer(peer, grupo=None):
    nome = TEMPLATE_POR_TIPO.get(peer.tipo, "%s.txt.j2" % peer.tipo)
    return ambiente().get_template(nome).render(peer=peer, grupo=grupo)


def escrever_peer(peer, grupo=None):
    OUT.mkdir(parents=True, exist_ok=True)
    destino = peer.arquivo()
    destino.write_text(render_peer(peer, grupo=grupo), encoding="ascii")
    return destino
```

- [ ] **Step 4: `cliente.txt.j2` — ramo de grupo**

O arquivo, depois das tasks 4 e 5, tem este miolo (note o 4º argumento `true` em `filtro_downstream_import` — a task 4 acrescentou o parâmetro `confinar_prefixo`, e o peer avulso sempre confina, mesmo com família vazia; **confirme contra o arquivo real antes de editar**, este é só o retrato do que o texto do plano previa):

```jinja
{% for fam in peer.familias() %}
{{ m.prefix_lists_downstream(peer, fam) }}
# Filtro XPL Import
{{ m.filtro_downstream_import(peer, fam, true, true) }}

{{ m.filtro_downstream_export(peer, fam) }}
{% endfor %}

{{ m.ap_cust_downstream(peer) }}
{{ m.apply_peer(peer) }}

bgp 64512
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}{{ "\n" if not loop.last -}}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "CUST-" ~ peer.token ~ "-IMPORT-" ~ U,
     "CUST-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

Envolva tudo num `{% if grupo %}...{% else %}...{% endif %}`, mantendo o `{% else %}` idêntico ao que já existe (peer avulso, sem mudança):

```jinja
{% if grupo %}
{% if peer.tem_filtro_proprio() %}
{% for fam in peer.familias() %}
{{ m.prefix_lists_downstream(peer, fam) }}
# Filtro XPL Import (override deste membro - o export continua do grupo)
{{ m.filtro_downstream_import(peer, fam, true, true) }}
{% endfor %}
{{ m.ap_cust_downstream(peer) }}
{{ m.apply_peer(peer) }}

{% endif %}
bgp 64512
{% for fam in peer.familias() %}
 peer {{ peer.sessoes[fam].remoto }} description {{ peer.descricao }}
{% if not grupo.asn %}
 peer {{ peer.sessoes[fam].remoto }} as-number {{ peer.asn }}
{% endif %}
 peer {{ peer.sessoes[fam].remoto }} group {{ grupo.nome }}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{% set s = peer.sessoes[fam] %}
 {{ "ipv6-family" if fam == "v6" else "ipv4-family" }} unicast
  peer {{ s.remoto }} enable
  peer {{ s.remoto }} group {{ grupo.nome }}
{% if peer.tem_filtro_proprio() %}
  peer {{ s.remoto }} route-filter CUST-{{ peer.token }}-IMPORT-{{ U }} import
{% endif %}
{% if peer.default_route %}
  peer {{ s.remoto }} default-route-advertise
{% endif %}
{% endfor %}
{% else %}
{% for fam in peer.familias() %}
{{ m.prefix_lists_downstream(peer, fam) }}
# Filtro XPL Import
{{ m.filtro_downstream_import(peer, fam, true, true) }}

{{ m.filtro_downstream_export(peer, fam) }}
{% endfor %}

{{ m.ap_cust_downstream(peer) }}
{{ m.apply_peer(peer) }}

bgp 64512
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}{{ "\n" if not loop.last -}}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "CUST-" ~ peer.token ~ "-IMPORT-" ~ U,
     "CUST-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
{% endif %}
```

- [ ] **Step 5: `remover.txt.j2` — não gerar `undo` de objetos que não existem para um membro sem override**

No template, o bloco `{% if peer.tipo in plan.TIPOS_DOWNSTREAM %}` (duas ocorrências, uma dentro do `{% for fam %}` e uma fora) hoje assume que `CUST-<T>-IMPORT/EXPORT`, `PL-CUST-<T>-*`, `AP-CUST-<T>` e `APPLY-PEER-<T>` sempre existem. Para um membro sem `tem_filtro_proprio()`, nenhum deles existe — só `PL-CUST`/`AP-CUST`/`CUST-...-IMPORT` se tiver override, e `CUST-...-EXPORT` nunca (export é sempre do grupo neste plano). Troque as duas ocorrências:

```jinja
{% if peer.tipo in plan.TIPOS_DOWNSTREAM %}
undo xpl route-filter CUST-{{ peer.token }}-EXPORT-{{ U }}
undo xpl route-filter CUST-{{ peer.token }}-IMPORT-{{ U }}
undo xpl {{ kw }} PL-CUST-{{ peer.token }}-BH-{{ U }}
undo xpl {{ kw }} PL-CUST-{{ peer.token }}-{{ U }}
```

por:

```jinja
{% if peer.tipo in plan.TIPOS_DOWNSTREAM and not grupo %}
undo xpl route-filter CUST-{{ peer.token }}-EXPORT-{{ U }}
undo xpl route-filter CUST-{{ peer.token }}-IMPORT-{{ U }}
undo xpl {{ kw }} PL-CUST-{{ peer.token }}-BH-{{ U }}
undo xpl {{ kw }} PL-CUST-{{ peer.token }}-{{ U }}
{% elif peer.tipo in plan.TIPOS_DOWNSTREAM and grupo and peer.tem_filtro_proprio() %}
undo xpl route-filter CUST-{{ peer.token }}-IMPORT-{{ U }}
undo xpl {{ kw }} PL-CUST-{{ peer.token }}-BH-{{ U }}
undo xpl {{ kw }} PL-CUST-{{ peer.token }}-{{ U }}
```

e a segunda ocorrência (fora do laço de família):

```jinja
{% if peer.tipo in plan.TIPOS_DOWNSTREAM %}
undo xpl as-path-list AP-CUST-{{ peer.token }}
undo xpl route-filter APPLY-PEER-{{ peer.token }}
```

por:

```jinja
{% if peer.tipo in plan.TIPOS_DOWNSTREAM and (not grupo or peer.tem_filtro_proprio()) %}
undo xpl as-path-list AP-CUST-{{ peer.token }}
undo xpl route-filter APPLY-PEER-{{ peer.token }}
```

(`AP-CUST-<T>` só sai quando `alvo.asn` é truthy — para um peer avulso sempre é; a condição acima ainda pode gerar um `undo` de uma lista que a macro não emitiu, se um override tiver `asn=0`, mas `asn` é obrigatório e validado > 0 para todo peer, então na prática isso não acontece. Registrar como nota, não é um novo `!-` necessário.)

O `render_remove` em `render.py` também precisa do `grupo`:

```python
def render_remove(peer, grupo=None):
    return ambiente().get_template("remover.txt.j2").render(peer=peer, grupo=grupo)
```

E o caller em `app/app.py` (`saida()`, veja task 8) passa o grupo do mesmo jeito que `render_peer`.

- [ ] **Step 6: Rode e confirme que passa**

Run: `.venv/bin/python -m pytest tests/test_render.py -v`
Expected: PASS nos testes novos; goldens de cliente/parceiro continuam batendo (o `{% else %}` é cópia exata do que já existia); mesmas falhas pré-existentes de route-limit, nenhuma nova.

- [ ] **Step 7: Commit**

```bash
git add templates/cliente.txt.j2 templates/remover.txt.j2 app/render.py tests/test_render.py
git commit -m "Gera o bloco enxuto do peer membro de grupo, com override opcional"
```

---

### Task 7: Rotas de grupo em `app.py`

**Files:**
- Modify: `app/app.py`
- Modify: `app/validate.py`
- Test: `tests/test_app.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `Grupo`, `carregar_grupos`, `gravar_grupos`, `achar_grupo`, `achar_grupo_id`, `proximo_id_grupo` (task 1); `validar_grupo` (task 3); `render.render_grupo`/`escrever_grupo` (task 5).
- Produces: rotas `GET /grupo/novo`, `GET /grupo/{nome}`, `POST /grupo`, `POST /grupo/{nome}/excluir`, `GET /saida/grupo/{nome}`, mais o helper `grupo_do_formulario(dados, grupos, anterior=None)`. Estende `validar_grupo(grupo, grupos, peers, anterior=None)`.

**Achado carregado da revisão da task 3 (ver ledger):** `validar_grupo`, como a task 3 a implementou, exclui só a própria instância (`outro is grupo`) da checagem de nome duplicado. Isso quebra a edição de um grupo existente sem trocar o nome: `grupo_salvar` (abaixo) monta um `Grupo` **novo** a cada POST (via `grupo_do_formulario`), e a lista `grupos` passada para `validar_grupo` ainda contém o objeto **antigo** (`anterior`, achado por `achar_grupo_id`) com o mesmo nome — `outro is grupo` nunca bate com ele, e `outro.nome == grupo.nome` bate, gerando "nome ja usado" numa edição legítima. Corrija isso nesta task, no mesmo espírito do `anterior` que `validar(peer, peers, anterior=antigo)` já usa para peer:

Em `app/validate.py`, troque a assinatura e o laço de duplicata:

```python
def validar_grupo(grupo, grupos, peers, anterior=None):
    ...
    for outro in grupos:
        if outro is anterior:
            continue
        if outro.nome == grupo.nome:
            erros.append(Erro("nome", "nome ja usado pelo grupo %s" % outro.id))
    ...
```

(Só a condição do `continue` muda, de `outro is grupo` para `outro is anterior` — o resto de `validar_grupo`, já implementado pela task 3, fica igual.)

Em `tests/test_validate.py`, adicione um teste cobrindo o caso que quebrava:

```python
def test_editar_grupo_sem_renomear_nao_acusa_duplicata():
    g = um_grupo(id=0, nome="PARCEIROS_CDN")
    editado = um_grupo(id=0, nome="PARCEIROS_CDN", lp_base=250)
    assert validate.validar_grupo(editado, [g], [], anterior=g) == []
```

- [ ] **Step 1: Escreva os testes**

Em `tests/test_app.py` (siga o padrão dos testes de peer existentes: `TestClient(app)`, POST de formulário, checar redirect e o que ficou em `peers.yaml`):

```python
def test_criar_grupo_grava_no_yaml(tmp_path, monkeypatch):
    _isola(monkeypatch, tmp_path)  # o helper que os testes de peer ja usam
    cliente = TestClient(app)
    resp = cliente.post("/grupo", data={
        "nome": "PARCEIROS_CDN", "tipo": "parceiro", "classe": "transito",
        "lp_base": "300", "origem": "1100", "pop": "2001",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/saida/grupo/PARCEIROS_CDN"
    grupos = peers_mod.carregar_grupos(tmp_path / "peers.yaml")
    assert len(grupos) == 1 and grupos[0].nome == "PARCEIROS_CDN"


def test_criar_grupo_com_erro_nao_grava(tmp_path, monkeypatch):
    _isola(monkeypatch, tmp_path)
    cliente = TestClient(app)
    resp = cliente.post("/grupo", data={"nome": "minusculo", "tipo": "parceiro"})
    assert resp.status_code == 200
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []


def test_excluir_grupo_exige_confirmacao(tmp_path, monkeypatch):
    _isola(monkeypatch, tmp_path)
    cliente = TestClient(app)
    cliente.post("/grupo", data={
        "nome": "X", "tipo": "parceiro", "classe": "transito",
        "lp_base": "300", "origem": "1100", "pop": "2001"})
    resp = cliente.post("/grupo/X/excluir", data={})
    assert resp.status_code == 200
    assert len(peers_mod.carregar_grupos(tmp_path / "peers.yaml")) == 1
    resp = cliente.post("/grupo/X/excluir", data={"confirmado": "sim"},
                        follow_redirects=False)
    assert resp.status_code == 303
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []


def test_saida_do_grupo_mostra_o_bloco(tmp_path, monkeypatch):
    _isola(monkeypatch, tmp_path)
    cliente = TestClient(app)
    cliente.post("/grupo", data={
        "nome": "X", "tipo": "parceiro", "classe": "transito",
        "lp_base": "300", "origem": "1100", "pop": "2001"})
    resp = cliente.get("/saida/grupo/X")
    assert resp.status_code == 200
    assert "group X external" in resp.text
```

Confira o nome exato do helper de isolamento de diretório que `tests/test_app.py` já usa para os testes de peer (algo como `monkeypatch.setattr(app_module, "PEERS_YAML", tmp_path / "peers.yaml")` e o mesmo para `OUT`) — use o mesmo padrão, com `_isola` sendo o helper existente, não um novo.

- [ ] **Step 2: Rode e confirme que falha**

Run: `.venv/bin/python -m pytest tests/test_app.py -k grupo -v`
Expected: FAIL — 404 nas rotas novas (elas ainda não existem).

- [ ] **Step 3: Implemente as rotas**

Em `app/app.py`, troque a linha `from app.peers import Peer` por `from app.peers import Peer, Grupo`. Depois adicione (perto de `CAMPOS_INT`):

```python
CAMPOS_INT_GRUPO = ("id", "asn", "lp_base", "origem", "pop", "prepend_base",
                    "timer_keepalive", "timer_hold")


def lista_grupos():
    return peers_mod.carregar_grupos(PEERS_YAML)


def grupo_do_formulario(dados, grupos, anterior=None):
    valores = {}
    for nome in CAMPOS_INT_GRUPO:
        bruto = _texto(dados, nome)
        if not bruto:
            valores[nome] = None
            continue
        try:
            valores[nome] = int(bruto)
        except ValueError:
            valores[nome] = None

    ident = valores.get("id")
    if ident is None:
        ident = anterior.id if anterior else peers_mod.proximo_id_grupo(grupos)

    grupo = Grupo(
        id=ident,
        nome=_texto(dados, "nome").upper(),
        tipo=_texto(dados, "tipo", "parceiro"),
        asn=valores.get("asn"),
        classe=_texto(dados, "classe") or None,
        lp_base=valores.get("lp_base") or 300,
        origem=valores.get("origem"),
        pop=valores.get("pop"),
        ap_block=_linhas(dados, "ap_block"),
        ap_te=_linhas(dados, "ap_te"),
        ap_allowed=_linhas(dados, "ap_allowed"),
        ap_prefer=_linhas(dados, "ap_prefer"),
        prepend_base=valores.get("prepend_base") or 0,
        bh_upstream=_texto(dados, "bh_upstream"),
        default_route=dados.get("default_route") == "on",
        bfd=dados.get("bfd") == "on",
        graceful_restart=dados.get("graceful_restart") == "on",
        timer_keepalive=valores.get("timer_keepalive"),
        timer_hold=valores.get("timer_hold"),
        prefixos={f: _linhas(dados, "prefixos_%s" % f) for f in plan.FAMILIAS},
    )
    return grupo


@app.get("/grupo/novo", response_class=HTMLResponse)
def grupo_novo(request: Request):
    grupo = Grupo(tipo="parceiro", id=peers_mod.proximo_id_grupo(lista_grupos()),
                 lp_base=plan.LP_BASE.get("parceiro", 300))
    return templates.TemplateResponse(request, "pagina_grupo.html",
                                      {"request": request, "grupo": grupo,
                                       "criando": True, "erros": {},
                                       "CLASSES_CLIENTE": plan.CLASSES_CLIENTE,
                                       "saida": None})


@app.get("/grupo/{nome}", response_class=HTMLResponse)
def grupo_editar(request: Request, nome: str):
    grupo = peers_mod.achar_grupo(lista_grupos(), nome)
    if grupo is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "pagina_grupo.html",
                                      {"request": request, "grupo": grupo,
                                       "criando": False, "erros": {},
                                       "CLASSES_CLIENTE": plan.CLASSES_CLIENTE,
                                       "saida": None})


@app.post("/grupo", response_class=HTMLResponse)
async def grupo_salvar(request: Request):
    dados = dict(await request.form())
    grupos = lista_grupos()
    ident_bruto = _texto(dados, "id")
    anterior = peers_mod.achar_grupo_id(grupos, int(ident_bruto)) if ident_bruto else None
    grupo = grupo_do_formulario(dados, grupos, anterior)
    erros = validate.validar_grupo(grupo, grupos, lista(), anterior=anterior)
    if erros:
        return templates.TemplateResponse(
            request, "pagina_grupo.html",
            {"request": request, "grupo": grupo, "criando": anterior is None,
             "erros": validate.erros_para_dict(erros),
             "CLASSES_CLIENTE": plan.CLASSES_CLIENTE, "saida": None},
            status_code=200)

    if anterior is None:
        grupos.append(grupo)
    else:
        grupos[grupos.index(anterior)] = grupo
        if anterior.nome != grupo.nome:
            anterior.arquivo().unlink(missing_ok=True)

    peers_mod.gravar_grupos(grupos, PEERS_YAML)
    render.escrever_grupo(grupo)
    return RedirectResponse("/saida/grupo/%s" % grupo.nome, status_code=303)


@app.post("/grupo/{nome}/excluir", response_class=HTMLResponse)
async def grupo_excluir(request: Request, nome: str):
    dados = dict(await request.form())
    grupos = lista_grupos()
    grupo = peers_mod.achar_grupo(grupos, nome)
    if grupo is None:
        return RedirectResponse("/", status_code=303)
    if dados.get("confirmado") != "sim":
        membros = [p.token for p in lista() if p.grupo_id == grupo.id]
        return templates.TemplateResponse(
            request, "pagina_grupo.html",
            {"request": request, "grupo": grupo, "criando": False,
             "erros": {"confirmado": "confirme para excluir o grupo"},
             "membros": membros, "CLASSES_CLIENTE": plan.CLASSES_CLIENTE,
             "saida": None},
            status_code=200)
    grupo.arquivo().unlink(missing_ok=True)
    grupos.remove(grupo)
    peers_mod.gravar_grupos(grupos, PEERS_YAML)
    return RedirectResponse("/", status_code=303)


@app.get("/saida/grupo/{nome}", response_class=HTMLResponse)
def grupo_saida(request: Request, nome: str):
    grupo = peers_mod.achar_grupo(lista_grupos(), nome)
    if grupo is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "pagina_grupo.html",
        {"request": request, "grupo": grupo, "criando": False, "erros": {},
         "CLASSES_CLIENTE": plan.CLASSES_CLIENTE,
         "saida": render.render_grupo(grupo)})
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `.venv/bin/python -m pytest tests/test_app.py -v`
Expected: PASS nos testes novos e nos existentes.

- [ ] **Step 5: Commit**

```bash
git add app/app.py tests/test_app.py
git commit -m "Adiciona rotas CRUD de grupo (criar, editar, excluir, saida)"
```

---

### Task 8: Formulário de peer ganha o select de grupo

**Files:**
- Modify: `app/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: tasks 1, 2, 3, 6, 7.
- Produces: `peer_do_formulario` lendo `grupo_id`; `salvar()`/`saida()` resolvendo o `Grupo` do peer e repassando pro `render` (o `excluir()` de peer não renderiza nada — só apaga o arquivo e regrava o YAML — então não precisa resolver grupo nenhum).

- [ ] **Step 1: Escreva o teste**

`tests/test_app.py` já isola estado por um **fixture** de pytest chamado `cliente` (não uma função `_isola` chamada à mão — confira `@pytest.fixture def cliente(tmp_path, monkeypatch): ...` perto do topo do arquivo, que já faz `monkeypatch.setattr` de `PEERS_YAML`/`OUT` em `peers_mod`, `mod` e `prefixes.CACHE`, e devolve um `TestClient(mod.app)` pronto). Os testes tomam esse fixture como parâmetro e usam o cliente devolvido direto — sem instanciar `TestClient(app)` de novo. Siga o mesmo padrão dos testes de peer que já existem no arquivo:

```python
def test_salvar_peer_com_grupo_grava_grupo_id(cliente, tmp_path):
    cliente.post("/grupo", data={
        "nome": "PARCEIROS_CDN", "tipo": "parceiro", "classe": "transito",
        "lp_base": "300", "origem": "1100", "pop": "2001"})
    grupo_id = peers_mod.carregar_grupos(mod.PEERS_YAML)[0].id
    resp = cliente.post("/peer", data={
        "tipo": "parceiro", "asn": "264130", "nome": "GIS TELECOM",
        "descricao": "GIS TELECOM", "grupo_id": str(grupo_id),
        "sessao_v4_local": "192.0.2.2", "sessao_v4_remoto": "192.0.2.3",
    }, follow_redirects=False)
    assert resp.status_code == 303
    peer = peers_mod.carregar(mod.PEERS_YAML)[0]
    assert peer.grupo_id == grupo_id
    saida = peer.arquivo().read_text()
    assert "group PARCEIROS_CDN" in saida
    assert "PL-CUST" not in saida  # sem override, sem prefixo
```

(`mod.PEERS_YAML`/`peer.arquivo()` funcionam porque o fixture `cliente` já fez o `monkeypatch.setattr` em `mod`/`peers_mod`/`render` para apontar pro `tmp_path` do teste — não precisa montar o caminho à mão. Confira o resto do arquivo para outros exemplos do mesmo padrão, ex. os testes que já cobrem `POST /peer`.)

- [ ] **Step 2: Rode e confirme que falha**

Run: `.venv/bin/python -m pytest tests/test_app.py -k grupo_id -v`
Expected: FAIL — o peer grava mas `grupo_id` vem `None` (o formulário ainda não lê o campo), ou a saída não tem `group PARCEIROS_CDN` (o `render.escrever_peer` ainda não recebe o grupo).

- [ ] **Step 3: Implemente**

**Não escreva um `int(grupo_id_bruto)` solto** — a task 7 já pagou o preço de um parse de inteiro sem `try/except` num campo de formulário (POST malformado vira 500). Este projeto já tem o jeito certo pra isso: a tupla `CAMPOS_INT` no topo de `app/app.py`, que o laço em `peer_do_formulario` já percorre com `try/except ValueError` por campo, guardando o resultado em `valores[nome]`. Acrescente `"grupo_id"` a essa tupla:

```python
CAMPOS_INT = ("asn", "id", "lp_base", "origem", "pop", "aprendizado",
              "ix_id", "prepend_base", "route_limit",
              "timer_keepalive", "timer_hold", "grupo_id")
```

E no `Peer(...)` dentro de `peer_do_formulario`, adicione `grupo_id=valores.get("grupo_id"),` (mesma posição de `default_route`) — sem criar uma leitura separada do campo, o laço existente já cobre.

Em `salvar()`, depois de `peers_mod.gravar(peers, PEERS_YAML)`, resolva o grupo antes de renderizar:

```python
    peers_mod.gravar(peers, PEERS_YAML)
    grupo = (peers_mod.achar_grupo_id(peers_mod.carregar_grupos(PEERS_YAML), peer.grupo_id)
            if peer.grupo_id is not None else None)
    render.escrever_peer(peer, grupo=grupo)
    return RedirectResponse("/saida/%s" % peer.token, status_code=303)
```

Em `saida()`, mesma resolução, antes de `contexto["saida"] = ...`:

```python
    grupo = (peers_mod.achar_grupo_id(peers_mod.carregar_grupos(PEERS_YAML), peer.grupo_id)
            if peer.grupo_id is not None else None)
    contexto = _contexto(request, peer=peer)
    contexto["saida"] = render.render_peer(peer, grupo=grupo)
    contexto["saida_remover"] = render.render_remove(peer, grupo=grupo)
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `.venv/bin/python -m pytest tests/test_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/app.py tests/test_app.py
git commit -m "Peer le e usa o grupo_id ao renderizar"
```

---

### Task 9: UI mínima — página de grupo e select no formulário de peer

**Files:**
- Modify: `templates/pagina_grupo.html` (**já existe** — a task 7 criou um stub mínimo só pra suas próprias rotas/testes renderizarem algo; esta task expande esse arquivo pro formulário completo abaixo, não cria do zero)
- Modify: `templates/pagina.html`
- Test: manual (ver Step 3) — sem teste automatizado de HTML, seguindo o padrão do projeto ("Nada de teste de UI", spec de 2026-09-21). **Rode `tests/test_app.py -k grupo` depois de editar** — os testes da task 7 já cobrem as rotas de grupo (criar, erro, excluir com confirmação, editar sem renomear, `/saida/grupo`) e usam `resp.text`/o YAML gravado, não IDs de HTML específicos, então continuam valendo contra o template novo; só confirme que nenhum quebrou.

**Interfaces:**
- Consumes: rotas da task 7, `Grupo` da task 1.

- [ ] **Step 1: `templates/pagina_grupo.html`**

Leia o arquivo atual primeiro (é o stub da task 7) para não perder nada que as rotas já esperam (`criando`, `erros`, `membros`, `saida`, `CLASSES_CLIENTE` no contexto). Substitua pelo formulário completo abaixo, sem o JS de mostrar/esconder campo por tipo que `pagina.html` tem (fica para depois, ver "Fora do escopo"):

```html
<!doctype html>
<html lang="pt-br">
<head>
 <meta charset="utf-8">
 <title>bgpgen — grupo</title>
 <link rel="stylesheet" href="/static/estilo.css">
</head>
<body>
 <p><a href="/">&larr; peers</a></p>
 <h1>{{ "Novo grupo" if criando else "Grupo " + grupo.nome }}</h1>

 {% if erros.get("confirmado") %}
 <form method="post" action="/grupo/{{ grupo.nome }}/excluir">
  <p>Confirma excluir o grupo <strong>{{ grupo.nome }}</strong>?
     {% if membros %}Peers apontando para ele: {{ membros|join(", ") }}.{% endif %}</p>
  <input type="hidden" name="confirmado" value="sim">
  <button type="submit">Confirmar exclusão</button>
 </form>
 {% endif %}

 <form method="post" action="/grupo">
  <input type="hidden" name="id" value="{{ grupo.id }}">
  <label>Nome (VRP, maiúsculo)
   <input name="nome" value="{{ grupo.nome }}" required>
   {% if erros.get("nome") %}<span class="erro">{{ erros["nome"] }}</span>{% endif %}
  </label>
  <label>Tipo
   <select name="tipo">
    <option value="cliente" {{ "selected" if grupo.tipo == "cliente" }}>cliente</option>
    <option value="parceiro" {{ "selected" if grupo.tipo == "parceiro" }}>parceiro</option>
   </select>
  </label>
  <label>ASN do grupo (vazio = cada membro declara o próprio)
   <input name="asn" value="{{ grupo.asn or '' }}">
  </label>
  <label>Classe
   <select name="classe">
    {% for c in CLASSES_CLIENTE %}
    <option value="{{ c }}" {{ "selected" if grupo.classe == c }}>{{ c }}</option>
    {% endfor %}
   </select>
   {% if erros.get("classe") %}<span class="erro">{{ erros["classe"] }}</span>{% endif %}
  </label>
  <label>Origem (1xxx)
   <input name="origem" value="{{ grupo.origem or '' }}">
   {% if erros.get("origem") %}<span class="erro">{{ erros["origem"] }}</span>{% endif %}
  </label>
  <label>POP (2001-2999)
   <input name="pop" value="{{ grupo.pop or '' }}">
   {% if erros.get("pop") %}<span class="erro">{{ erros["pop"] }}</span>{% endif %}
  </label>
  <label>LP base
   <input name="lp_base" value="{{ grupo.lp_base }}">
  </label>
  <label>Prefixos v4 do grupo (um por linha, vazio = sem confinamento)
   <textarea name="prefixos_v4">{{ grupo.prefixos.v4|join("\n") }}</textarea>
   {% if erros.get("prefixos") %}<span class="erro">{{ erros["prefixos"] }}</span>{% endif %}
  </label>
  <label>Prefixos v6 do grupo
   <textarea name="prefixos_v6">{{ grupo.prefixos.v6|join("\n") }}</textarea>
  </label>
  <label>
   <input type="checkbox" name="default_route" {{ "checked" if grupo.default_route }}>
   Anunciar a default route a este grupo
  </label>
  <button type="submit">Salvar</button>
 </form>

 {% if not criando %}
 <form method="post" action="/grupo/{{ grupo.nome }}/excluir">
  <button type="submit">Excluir</button>
 </form>
 {% endif %}

 {% if saida %}
 <h2>Bloco do grupo</h2>
 <pre>{{ saida }}</pre>
 {% endif %}
</body>
</html>
```

(`grupo.prefixos.v4` funciona em Jinja tanto para dict quanto atributo; se o ambiente Jinja do app não tiver essa permissividade configurada, troque por `grupo.prefixos["v4"]` — confira contra o que `pagina.html` já faz para `peer.prefixos`.)

- [ ] **Step 2: `pagina.html` — link para grupos e select no formulário de peer**

Na barra lateral (`<aside id="lista" class="painel">`, linha ~538 antes da task), adicione um link simples logo depois da abertura:

```html
 <aside id="lista" class="painel">
  <p><a href="/grupo/novo">+ novo grupo</a></p>
```

No formulário de peer, perto do `<select name="tipo">` (linha ~641), adicione o select de grupo. Como este plano não busca a lista de grupos filtrada por tipo via JS (isso é o polimento futuro), o select mostra todos e o nome do tipo ao lado, para o operador escolher com cuidado:

```html
      <select name="grupo_id">
       <option value="">— sem grupo —</option>
       {% for g in (grupos or []) %}
       <option value="{{ g.id }}" {{ "selected" if peer and peer.grupo_id == g.id }}>{{ g.nome }} ({{ g.tipo }})</option>
       {% endfor %}
      </select>
```

Em `_contexto()` (`app/app.py`), adicione `"grupos": peers_mod.carregar_grupos(PEERS_YAML),` ao dicionário retornado, para o `grupos` do template acima existir.

- [ ] **Step 3: Verificação manual**

Suba o app (`.venv/bin/uvicorn app.app:app --port 8000`), abra `http://127.0.0.1:8000/grupo/novo`, crie um grupo `PARCEIROS_CDN` tipo parceiro, confira o bloco gerado em `/saida/grupo/PARCEIROS_CDN`. Depois crie um peer tipo parceiro apontando pro grupo pelo select, confira que o bloco dele em `/saida/<token>` sai enxuto (só `group PARCEIROS_CDN`, sem `PL-CUST`). Não é um passo automatizável — reporte o resultado antes do commit.

- [ ] **Step 4: Commit**

```bash
git add templates/pagina_grupo.html templates/pagina.html app/app.py
git commit -m "UI minima para criar grupo e associar peer a um grupo"
```

---

### Task 10: Propriedade de isolamento, ponta a ponta

**Files:**
- Test: `tests/test_isolamento.py`

**Interfaces:**
- Consumes: tudo das tasks anteriores.

- [ ] **Step 1: Escreva o teste**

Em `tests/test_isolamento.py`, siga o padrão dos testes que já existem (`faz()` gera um peer e compara antes/depois de mexer em outro):

```python
def test_gerar_grupo_nao_muda_saida_de_peer_membro(tmp_path, monkeypatch):
    monkeypatch.setattr(peers, "OUT", tmp_path / "out")
    monkeypatch.setattr(render, "OUT", tmp_path / "out")
    grupo = peers.Grupo(id=0, nome="PARCEIROS_CDN", tipo="parceiro",
                        classe="transito", lp_base=300, origem=1100, pop=2001)
    membro = peers.Peer(id=1, nome="GIS", tipo="parceiro", asn=264130,
                        grupo_id=0, descricao="GIS",
                        sessoes={"v4": {"local": "192.0.2.2",
                                       "remoto": "192.0.2.3"}, "v6": {}})
    render.escrever_grupo(grupo)
    antes = render.escrever_peer(membro, grupo=grupo).read_text()

    outro_grupo = peers.Grupo(id=0, nome="PARCEIROS_CDN", tipo="parceiro",
                              classe="residencial", lp_base=250, origem=1110, pop=2002)
    render.escrever_grupo(outro_grupo)  # muda a politica do grupo

    depois = membro.arquivo().read_text()
    assert antes == depois  # regerar o grupo nao tocou no arquivo do membro


def test_gerar_peer_membro_nao_muda_saida_do_grupo(tmp_path, monkeypatch):
    monkeypatch.setattr(peers, "OUT", tmp_path / "out")
    monkeypatch.setattr(render, "OUT", tmp_path / "out")
    grupo = peers.Grupo(id=0, nome="PARCEIROS_CDN", tipo="parceiro",
                        classe="transito", lp_base=300, origem=1100, pop=2001)
    antes = render.escrever_grupo(grupo).read_text()

    membro = peers.Peer(id=1, nome="GIS", tipo="parceiro", asn=264130,
                        grupo_id=0, descricao="GIS",
                        sessoes={"v4": {"local": "192.0.2.2",
                                       "remoto": "192.0.2.3"}, "v6": {}})
    render.escrever_peer(membro, grupo=grupo)

    depois = grupo.arquivo().read_text()
    assert antes == depois


def test_gerar_um_membro_nao_muda_outro_membro(tmp_path, monkeypatch):
    monkeypatch.setattr(peers, "OUT", tmp_path / "out")
    monkeypatch.setattr(render, "OUT", tmp_path / "out")
    grupo = peers.Grupo(id=0, nome="PARCEIROS_CDN", tipo="parceiro",
                        classe="transito", lp_base=300, origem=1100, pop=2001)
    a = peers.Peer(id=1, nome="A", tipo="parceiro", asn=1, grupo_id=0,
                   descricao="A", sessoes={"v4": {"local": "10.0.0.1",
                                                  "remoto": "10.0.0.2"}, "v6": {}})
    b = peers.Peer(id=2, nome="B", tipo="parceiro", asn=2, grupo_id=0,
                   descricao="B", prefixos={"v4": ["198.51.100.0/24"], "v6": []},
                   classe="transito", origem=1100, pop=2001,
                   sessoes={"v4": {"local": "10.0.1.1", "remoto": "10.0.1.2"}, "v6": {}})
    antes = render.escrever_peer(a, grupo=grupo).read_text()
    render.escrever_peer(b, grupo=grupo)  # b tem override, filtro proprio
    depois = a.arquivo().read_text()
    assert antes == depois
```

- [ ] **Step 2: Rode e confirme que falha (se falhar)**

Run: `.venv/bin/python -m pytest tests/test_isolamento.py -k grupo -v`
Expected: se tudo nas tasks 1-8 foi implementado corretamente, isso já deve passar de cara — é um teste de regressão, não de uma feature nova. Se falhar, é sinal de acoplamento que escapou nas tasks anteriores; achar onde `escrever_grupo`/`escrever_peer` tocam em mais arquivo do que o próprio, e corrigir ali (não neste teste).

- [ ] **Step 3: Rode a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: só as 6 falhas pré-existentes de route-limit (fora deste plano), zero falhas novas.

- [ ] **Step 4: Commit**

```bash
git add tests/test_isolamento.py
git commit -m "Cobre a propriedade de isolamento entre grupo e peers membros"
```

## Self-review

**Cobertura do spec:** modelo de dados (tasks 1-2), rotas/UI (tasks 7-9), geração preservando isolamento (tasks 4-6, 10), override por peer (task 6), nomes de objeto (`CUST-<G>-*` reaproveitando `CUST-<T>-*` via macro compartilhada, tasks 4-5), validação (task 3), testes (todas). Os itens que o spec deixou como pendência (escopo de anúncio sem eixo por grupo, `ap_prefer` de IX) não entram porque este plano não cobre `ix`; ficam para o plano de extensão aos outros tipos.

**Sequenciamento:** cada task deixa a suíte num estado rodável e reverte pouco risco por vez — o refactor de macros (task 4) vem isolado e provado pelos goldens antes de qualquer código novo de grupo tocar nele.

**Pendência que este plano introduz e não resolve:** `remover.txt.j2` para um membro com override não foi testado ponta a ponta neste plano (task 6 cobre a geração, mas não há teste de golden específico pra remoção de membro com override) — considerar isso ao revisar a task 6, ou adicionar o golden como parte da revisão dela.
