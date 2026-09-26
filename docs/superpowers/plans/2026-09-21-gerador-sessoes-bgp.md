# Gerador de sessões BGP — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerar, a partir de um formulário web, a configuração XPL completa de uma sessão BGP do AS64512 — sets, route-filters e bloco `bgp` — sem tocar nos outros peers já gerados.

**Architecture:** App FastAPI local, sem banco, com o estado num `peers.yaml` versionado. Duas saídas separadas: um bloco base (sets e filtros compartilhados, gerado uma vez) e um bloco por peer (sobrescrito a cada gravação). O bloco base nunca é reescrito pela edição de um peer, e é isso que faz o "sem mexer nos outros" valer. `render.py` e `validate.py` concentram toda a decisão; o formulário é fino.

**Tech Stack:** Python 3, FastAPI + uvicorn, Jinja2, htmx, PyYAML, pytest. Sem npm, sem bundler, sem etapa de build.

**Spec:** `docs/superpowers/specs/2026-09-21-gerador-sessoes-bgp-design.md`

## Global Constraints

- **Saída ASCII puro.** Nada de acento em template, comentário gerado ou nome de objeto. Caractere fora de ASCII quebra o pipeline de TFTP, backup e diff. Vale também para o separador dentro dos comentários: use hífen, nunca `·` nem travessão.
- **Nenhum `$` na saída gerada.** Os filtros do PLANO são parametrizados; o gerador emite valor literal. O `xpl simulate` não aceita filtro parametrizado, então filtro com parâmetro não teria como ser testado no equipamento.
- **Nenhuma limpeza no egress**, com uma exceção: o ramo de blackhole do export de upstream, onde o `overwrite` define o anúncio sintético. O valor sai do campo `bh_upstream` do peer, nunca literal no template.
- **`apply community` só usa `additive` ou `overwrite`.** Não existe remoção seletiva.
- **O par `CL-PEER-<T>` / `APPLY-PEER-<T>` só existe em cliente e upstream.** IX e PNI não emitem nenhum dos dois.
- **A `CL-PEER-<T>` nunca é emitida dentro do bloco do peer.** Ela aparece só no quadro "ao criar o peer" da interface.
- **`call route-filter APPLY-PEER-<T>` é a última linha do import de cliente e o último passo do export de upstream**, imediatamente antes do `finish`.
- **Comentário gerado usa `!-`**, nunca `//` ou `#`.
- **Placeholders do PLANO não viram dado.** `268127`, `14840`, `64500`, `45.169.232.0/22` são exemplos. Nenhum ASN ou community de operadora terceira pode existir como constante em `app/plan.py`; o que existe ali é o que os goldens de teste mostram como dado de exemplo.
- **Nomes de objeto seguem `TIPO-FUNÇÃO-ESCOPO`**, maiúsculo, com hífen. O token `<T>` é o ASN do peer, ou um apelido no caso de IX.
- **Formatação de prefixo no XPL é `addr len`, sem barra.** `45.169.232.0/22` vira `45.169.232.0 22`. Vale para v4 e v6.
- **Literal com chave em Jinja passa por `plan.conjunto`.** Escrever `{` colado a `{{` colide com o delimitador de expressão e o texto sai truncado. Use `{{ plan.conjunto(a, b) }}`, que devolve `{a, b}`.

---

## File Structure

```
requirements.txt              deps do app e do teste
pytest.ini                    pythonpath e testpaths
app/__init__.py               vazio
app/plan.py                   tabelas do PLANO.md como dados
app/peers.py                  dataclass Peer, ler/gravar peers.yaml
app/validate.py               o que o app recusa antes de gerar
app/render.py                 Jinja2, render_base / render_peer / render_remove
app/prefixes.py               bgpq4 mais o cache em disco
app/app.py                    rotas FastAPI e o formulario
templates/_macros.j2          pedacos comuns aos quatro tipos
templates/base.txt.j2         bloco base
templates/cliente.txt.j2      bloco de peer, tipo cliente
templates/upstream.txt.j2     bloco de peer, tipo upstream
templates/ix.txt.j2           bloco de peer, tipo IX
templates/pni.txt.j2          bloco de peer, tipo PNI
templates/remover.txt.j2      bloco de undo
templates/criar_lista.txt.j2  quadro "ao criar o peer"
templates/pagina.html         tela unica: lista a esquerda, form a direita, saida abaixo
tests/test_plan.py
tests/test_peers.py
tests/test_validate.py
tests/test_render.py
tests/test_isolamento.py
tests/test_prefixes.py
tests/test_app.py
tests/golden/
peers.yaml
out/
```

Cada template de tipo é independente: um erro no de IX não deve obrigar a mexer no de cliente. O que os quatro compartilham mora em `_macros.j2`.

---

### Task 1: Esqueleto do projeto e `plan.py`

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `app/__init__.py`, `app/plan.py`, `tests/test_plan.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nada.
- Produces: as constantes e funções de `app.plan` que todo o resto consulta —
  constantes `TIPOS`, `FAMILIAS`, `LP_BASE`, `LP_IX_CDN`, `LP_TE_PREFER`, `LP_BLACKHOLE`, `LP_CLIENTE`, `LP_CLIENTE_DEFAULT`, `ORIGEM`, `ORIGEM_CLASSE`, `CLASSES_CLIENTE`, `GEO_PNI`, `POP_MIN`, `POP_MAX`, `APRENDIZADO_MIN`, `APRENDIZADO_MAX`, `ROUTE_LIMIT`, `ROUTE_LIMIT_EXEMPLO`, `ACAO_LIMITE`, `AS_ONLY`, `NOADV`, `NOADV_CUST`, `ONLY_NOT`, `CLASSE_6CA`, `DIGITO_PREPEND`, `BLACKHOLE`, `BLACKHOLE_PROPAGATE`, `BLACKHOLE_INFO`, `GSHUT`, `ORIGEM_ANUNCIAVEL`, `TIMER_PADRAO`, `FAIXAS`;
  funções `c4pp0(peer_id) -> str`, `c5ppa(peer_id, digito) -> str`, `c6ca(classe, digito) -> str`, `c_large(funcao, asn) -> str`, `noadv(tipo, peer_id) -> list[str]`, `noadv_cust() -> list[str]`, `only_not(tipo) -> list[str]`, `conjunto(*itens) -> str`, `cidr_para_xpl(cidr) -> str`, `faixa_ok(community) -> bool`.

- [ ] **Step 1: Criar `requirements.txt`**

```
fastapi==0.115.6
uvicorn==0.34.0
jinja2==3.1.5
PyYAML==6.0.2
python-multipart==0.0.20
pytest==8.3.4
httpx==0.28.1
```

- [ ] **Step 2: Criar `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 3: Criar o ambiente e instalar**

Run:
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

- [ ] **Step 4: Criar `app/__init__.py` vazio**

```bash
touch app/__init__.py
```

- [ ] **Step 5: Escrever o teste que falha**

`tests/test_plan.py`:

```python
import pytest

from app import plan

# nomes locais so para as assercoes ficarem legiveis na horizontal
C200, C201, C202, C203, C204 = ("64512:%d" % v for v in (200, 201, 202, 203, 204))
C210, C211, C212, C213 = ("64512:%d" % v for v in (210, 211, 212, 213))


def test_lp_base_por_tipo():
    assert plan.LP_BASE == {"cliente": 300, "upstream": 100, "ix": 190, "pni": 200}


def test_origem_por_tipo():
    assert plan.ORIGEM == {"cliente": 1100, "upstream": 1400, "ix": 1300, "pni": 1500}


def test_classe_do_cliente_troca_a_origem():
    assert plan.ORIGEM_CLASSE == {
        "transito": 1100,
        "residencial": 1110,
        "corporativo": 1120,
        "cgnat": 1130,
    }


def test_escada_de_local_preference():
    # GSHUT antes da escada, escada em ordem crescente, default no fim
    assert plan.LP_BASE["cliente"] == plan.LP_CLIENTE_DEFAULT == 300
    assert plan.LP_CLIENTE == (
        ("64512:101", 50),
        ("64512:102", 80),
        ("64512:103", 150),
        ("64512:104", 250),
        ("64512:105", 350),
    )
    assert plan.LP_IX_CDN == 195
    assert plan.LP_TE_PREFER == 250
    assert plan.LP_BLACKHOLE == 400


def test_route_limit_por_tipo():
    assert plan.ROUTE_LIMIT == {
        "cliente": 50,
        "upstream": 1500000,
        "ix": 500000,
        "pni": 10000,
    }
    # o exemplo de aplicacao do PLANO usa um valor diferente do da tabela
    assert plan.ROUTE_LIMIT_EXEMPLO["upstream"] == 1100000


def test_timer_por_tipo():
    # o PLANO so poe timer explicito no upstream
    assert plan.TIMER_PADRAO["upstream"] == (10, 30)
    assert plan.TIMER_PADRAO["cliente"] == (None, None)
    assert set(plan.TIMER_PADRAO) == set(plan.TIPOS)


def test_escala_do_prepend():
    assert plan.DIGITO_PREPEND == {4: 3, 3: 2, 2: 1}
    # o digito 1 (P1 explicito) nao tem ramo: existe para barrar a classe
    assert 1 not in plan.DIGITO_PREPEND


def test_classe_6ca_por_tipo():
    # a tabela do PLANO tem 3 para "IX privado e PNI" e 4 para CDN; o
    # exemplo de PNI e de CDN e usa 4, e e ele que o gerador segue
    assert plan.CLASSE_6CA == {"upstream": 1, "ix": 2, "pni": 4}
    assert set(plan.CLASSE_6CA) == {"upstream", "ix", "pni"}


def test_noadv_por_tipo():
    # o terceiro valor e o 5PPA com digito 0: "nao anunciar para este peer"
    assert plan.noadv("upstream", 1) == [C200, C201, "64512:5010"]
    assert plan.noadv("ix", 10) == [C200, C203, "64512:5100"]
    assert plan.noadv("pni", 20) == [C200, C202, "64512:5200"]


def test_noadv_do_cliente_nao_tem_eixo_por_peer():
    assert plan.noadv_cust() == [C200, C204]


def test_only_not_por_tipo():
    # 213 fica de fora de ONLY-NOT-CLIENT: ele E o "somente cliente"
    assert plan.only_not("cliente") == [C210, C211, C212]
    assert plan.only_not("upstream") == [C211, C212, C213]
    assert plan.only_not("ix") == [C210, C212, C213]
    assert plan.only_not("pni") == [C210, C211, C213]


def test_blackhole_e_manutencao():
    assert plan.BLACKHOLE == ("65535:666", "64512:666")
    assert plan.BLACKHOLE_PROPAGATE == "64512:667"
    assert plan.BLACKHOLE_INFO == "64512:9666"
    assert plan.GSHUT == "65535:0"


def test_origem_anunciavel():
    assert plan.ORIGEM_ANUNCIAVEL == (
        "64512:1000", "64512:1100", "64512:1110",
        "64512:1120", "64512:1130",
    )
    # e exatamente a origem propria mais as quatro classes de cliente
    assert plan.ORIGEM_ANUNCIAVEL[0] == "64512:%d" % plan.ORIGEM["cliente"]
    assert plan.ORIGEM_ANUNCIAVEL[1:] == tuple(
        "64512:%d" % plan.ORIGEM_CLASSE[c] for c in plan.CLASSES_CLIENTE)


def test_formatos_de_community():
    assert plan.c4pp0(1) == "64512:4010"
    assert plan.c4pp0(10) == "64512:4100"
    assert plan.c5ppa(1, 0) == "64512:5010"
    assert plan.c5ppa(1, 4) == "64512:5014"
    assert plan.c5ppa(10, 1) == "64512:5101"
    assert plan.c6ca(1, 4) == "64512:614"
    assert plan.c6ca(2, 2) == "64512:622"
    assert plan.c6ca(4, 4) == "64512:644"
    assert plan.c_large(3, 14840) == "64512:3:14840"


def test_5ppa_e_o_large_equivalente_andam_juntos():
    # digito 2 -> 1 prepend -> 64512:1:<ASN>; digito 4 -> 3 -> 64512:3:<ASN>
    for digito, asn in ((2, 64500), (3, 64500), (4, 64500)):
        assert plan.c5ppa(1, digito)[-1] == str(digito)
        assert plan.c_large(digito - 1, asn) == "64512:%d:%d" % (digito - 1, asn)
    # digito 0 -> nao anunciar -> 64512:0:<ASN>
    assert plan.c5ppa(1, 0) == "64512:5010"
    assert plan.c_large(0, 64500) == "64512:0:64500"


def test_conjunto():
    assert plan.conjunto("64512:200") == "{64512:200}"
    assert plan.conjunto("64512:1", "64512:2") == "{64512:1, 64512:2}"


def test_c4pp0_nao_colide_com_o_regex_de_informativa():
    # quatro digitos, mas nao comeca com 1, 2, 3 nem 9
    assert plan.c4pp0(1)[6] == "4"


def test_cidr_para_xpl():
    assert plan.cidr_para_xpl("45.169.232.0/22") == "45.169.232.0 22"
    assert plan.cidr_para_xpl("2001:db8::/32") == "2001:db8:: 32"


def test_cidr_para_xpl_recusa_entrada_sem_mascara():
    with pytest.raises(ValueError):
        plan.cidr_para_xpl("45.169.232.0")


def test_faixa_ok():
    assert plan.faixa_ok("64512:100")
    assert plan.faixa_ok("64512:699")
    assert plan.faixa_ok("64512:1000")
    assert plan.faixa_ok("64512:9999")
    assert not plan.faixa_ok("64512:99")
    assert not plan.faixa_ok("64512:10000")
    assert not plan.faixa_ok("14840:100")
    assert not plan.faixa_ok("64512:6:1")
    assert not plan.faixa_ok("64512:abc")
```

- [ ] **Step 6: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_plan.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.plan'`

- [ ] **Step 7: Escrever `app/plan.py`**

```python
"""As tabelas do PLANO.md como dados.

Nao ha texto de template aqui. O que este modulo guarda e o que os
templates de tipo consultam para decidir valor e para validar faixa.

Nenhum valor de operadora terceira: os ASNs e as IDs que aparecem na
saida vem do formulario. As funcoes de formatacao sao as unicas que
sabem montar o numero da community.
"""

TIPOS = ("cliente", "upstream", "ix", "pni")
FAMILIAS = ("v4", "v6")

# --- local preference -------------------------------------------------

LP_BASE = {"cliente": 300, "upstream": 100, "ix": 190, "pni": 200}
LP_IX_CDN = 195          # membro de IX marcado no AP-IX-<T>
LP_TE_PREFER = 250       # excecao de TE no import de upstream
LP_BLACKHOLE = 400       # ramo de blackhole do import de cliente

# escada do APPLY-CUSTOMER-LP, na ordem em que os ramos saem no filtro
LP_CLIENTE = (
    ("64512:101", 50),
    ("64512:102", 80),
    ("64512:103", 150),
    ("64512:104", 250),
    ("64512:105", 350),
)
LP_CLIENTE_DEFAULT = 300

# --- origem -----------------------------------------------------------

ORIGEM = {"cliente": 1100, "upstream": 1400, "ix": 1300, "pni": 1500}
ORIGEM_CLASSE = {
    "transito": 1100,
    "residencial": 1110,
    "corporativo": 1120,
    "cgnat": 1130,
}
CLASSES_CLIENTE = tuple(ORIGEM_CLASSE)

# o export so libera o que carrega marca de origem propria ou de cliente
ORIGEM_ANUNCIAVEL = ("64512:%d" % ORIGEM["cliente"],) + tuple(
    "64512:%d" % ORIGEM_CLASSE[c] for c in CLASSES_CLIENTE)

# geografia fixa do PNI, PLANO.md secao "Communities informativas"
GEO_PNI = 1200
# 2xxx e geografia/POP. 2000 fica de fora: e "aprendida de fora".
POP_MIN, POP_MAX = 2001, 2999
# 3xxx e ponto de aprendizado, por peer
APRENDIZADO_MIN, APRENDIZADO_MAX = 3000, 3999

# --- sessao -----------------------------------------------------------

ROUTE_LIMIT = {
    "cliente": 50,
    "upstream": 1500000,
    "ix": 500000,
    "pni": 10000,
}
# o exemplo de aplicacao do PLANO usa outros valores; ficam como nota no
# formulario, nao como default. O da tabela acima e que vale.
ROUTE_LIMIT_EXEMPLO = {"cliente": 50, "upstream": 1100000, "ix": 500000, "pni": 10000}

ACAO_LIMITE = "alert-only"
AS_ONLY = "public-as-only force"

# keepalive e hold. O PLANO so poe timer explicito no upstream; nos
# outros tipos o equipamento usa o default. None = nao emitir a linha.
TIMER_PADRAO = {
    "cliente": (None, None),
    "upstream": (10, 30),
    "ix": (None, None),
    "pni": (None, None),
}

# --- escopo de anuncio ------------------------------------------------

NOADV = {"upstream": (200, 201), "ix": (200, 203), "pni": (200, 202)}
NOADV_CUST = (200, 204)
ONLY_NOT = {
    "cliente": (210, 211, 212),
    "upstream": (211, 212, 213),
    "ix": (210, 212, 213),
    "pni": (210, 211, 213),
}

# --- prepend por classe (6CA) -----------------------------------------

# classe C do 64512:6CA. A tabela do PLANO da 3 a "IX privado e PNI" e 4
# a CDN; o unico exemplo de PNI do documento e de CDN e usa 4.
CLASSE_6CA = {"upstream": 1, "ix": 2, "pni": 4}
# digito do 5PPA/6CA -> numero de prepends. O digito 1 nao tem ramo:
# ele existe para barrar a classe, e por isso o aninhamento e if/elseif.
DIGITO_PREPEND = {4: 3, 3: 2, 2: 1}

# --- blackhole e manutencao -------------------------------------------

BLACKHOLE = ("65535:666", "64512:666")
BLACKHOLE_PROPAGATE = "64512:667"
BLACKHOLE_INFO = "64512:9666"
GSHUT = "65535:0"

# uma community e action (3 digitos, 100-699) ou informativa (4, 1000-9999)
FAIXAS = ((100, 699), (1000, 9999))


def c4pp0(peer_id):
    """Informativa 4PP0: de qual peer a rota veio."""
    return "64512:4%02d0" % peer_id


def c5ppa(peer_id, digito):
    """Alias em standard do prepend e do escopo por peer."""
    return "64512:5%02d%d" % (peer_id, digito)


def c6ca(classe, digito):
    """Prepend por classe de peer."""
    return "64512:6%d%d" % (classe, digito)


def c_large(funcao, asn):
    """Large community no formato 64512:<funcao>:<ASN> (RFC 8195)."""
    return "64512:%d:%d" % (funcao, asn)


def conjunto(*itens):
    """Monta o literal de conjunto do XPL.

    Existe porque escrever "{" num template colado a "{{" faz o Jinja
    ler o delimitador de expressao e o texto sai truncado.
    """
    return "{%s}" % ", ".join(str(i) for i in itens)


def noadv(tipo, peer_id):
    """Composicao do CL-NOADV-<T>: proibicao absoluta e do tipo, mais este peer."""
    um, dois = NOADV[tipo]
    return ["64512:%d" % um, "64512:%d" % dois, c5ppa(peer_id, 0)]


def noadv_cust():
    """O egress de cliente nao tem eixo por peer."""
    return ["64512:%d" % v for v in NOADV_CUST]


def only_not(tipo):
    return ["64512:%d" % v for v in ONLY_NOT[tipo]]


def cidr_para_xpl(cidr):
    """`45.169.232.0/22` -> `45.169.232.0 22`. O VRP nao usa barra aqui."""
    if "/" not in cidr:
        raise ValueError("prefixo sem mascara: %s" % cidr)
    addr, mascara = cidr.split("/", 1)
    return "%s %d" % (addr.strip(), int(mascara))


def faixa_ok(community):
    """A community esta numa das faixas do plano, no namespace 64512?"""
    partes = community.split(":")
    if len(partes) != 2 or partes[0] != "64512":
        return False
    try:
        valor = int(partes[1])
    except ValueError:
        return False
    return any(lo <= valor <= hi for lo, hi in FAIXAS)
```

- [ ] **Step 8: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_plan.py -v`
Expected: PASS nos 20 testes.

- [ ] **Step 9: Ajustar o `.gitignore`**

Acrescentar ao `.gitignore` existente (que já tem `.superpowers/`, `out/.cache/`, `__pycache__/`, `*.py[cod]`, `.venv/`, `venv/`, `.DS_Store`):

```
# saida gerada: derivada do peers.yaml, nao e fonte
out/*.txt
```

`peers.yaml` **não** entra: é o estado, e vai versionado.

- [ ] **Step 10: Commit**

```bash
git add requirements.txt pytest.ini app/__init__.py app/plan.py tests/test_plan.py .gitignore
git commit -m "Adiciona as tabelas do plano como dados"
```

---

### Task 2: `peers.py` — o `peers.yaml` e o `Peer`

**Files:**
- Create: `app/peers.py`, `tests/test_peers.py`

**Interfaces:**
- Consumes: `app.plan.FAMILIAS`.
- Produces: `@dataclass Peer` com exatamente estes campos —
  `id: int`, `token: str`, `nome: str`, `tipo: str`, `asn: int`, `classe: str|None`, `descricao: str`,
  `lp_base: int`, `origem: int|None`, `pop: int|None`, `aprendizado: int|None`, `ix_id: int|None`,
  `prefixos: dict` (`{"v4": [...], "v6": [...]}`), `te_prefixos: dict` (mesma forma),
  `ap_block: list`, `ap_te: list`, `ap_allowed: list`, `ap_prefer: list`,
  `bfd: bool`, `graceful_restart: bool`, `timer_keepalive: int|None`, `timer_hold: int|None`,
  `prepend_base: int`, `route_limit: int`, `sessoes: dict` (`{"v4": {"local":..., "remoto":...}, "v6": {}}`), `bh_upstream: str`;
  métodos `familias() -> list[str]`, `arquivo() -> Path`, `para_dict() -> dict`, `de_dict(d) -> Peer`;
  funções `carregar(caminho=PEERS_YAML) -> list[Peer]`, `gravar(peers, caminho=PEERS_YAML)`, `proximo_id(peers) -> int`, `achar(peers, token) -> Peer | None`;
  constantes `RAIZ`, `PEERS_YAML`, `OUT`, `MAX_PEERS`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_peers.py`:

```python
import pytest

from app import peers as mod


def test_proximo_id_comeca_em_zero_com_a_lista_vazia():
    assert mod.proximo_id([]) == 0


def test_proximo_id_pula_os_ocupados():
    a = mod.Peer(id=0, token="A", nome="a", tipo="cliente", asn=1)
    b = mod.Peer(id=2, token="B", nome="b", tipo="cliente", asn=2)
    assert mod.proximo_id([a, b]) == 1


def test_proximo_id_estoura_quando_nao_ha_vaga():
    cheio = [mod.Peer(id=i, token="T%d" % i, nome="x", tipo="cliente", asn=i)
             for i in range(100)]
    with pytest.raises(ValueError):
        mod.proximo_id(cheio)


def test_round_trip_do_yaml(tmp_path):
    caminho = tmp_path / "peers.yaml"
    original = mod.Peer(
        id=1, token="268127", nome="Cliente ACME", tipo="cliente",
        asn=268127, classe="residencial", descricao="CLIENTE-AS268127",
        lp_base=300, origem=1110, pop=2001, aprendizado=None, ix_id=None,
        prefixos={"v4": ["45.169.232.0/22"], "v6": []},
        te_prefixos={"v4": [], "v6": []},
        ap_block=[], ap_te=[], ap_allowed=[], ap_prefer=[],
        bfd=True, graceful_restart=True, timer_keepalive=None, timer_hold=None,
        prepend_base=0, route_limit=50,
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"}, "v6": {}},
    )
    mod.gravar([original], caminho)
    assert mod.carregar(caminho) == [original]


def test_gravar_reescreve_a_lista_inteira(tmp_path):
    caminho = tmp_path / "peers.yaml"
    a = mod.Peer(id=0, token="A", nome="a", tipo="cliente", asn=1)
    b = mod.Peer(id=1, token="B", nome="b", tipo="cliente", asn=2)
    mod.gravar([a, b], caminho)
    b.nome = "b editado"
    mod.gravar([a, b], caminho)
    lido = mod.carregar(caminho)
    assert lido[1].nome == "b editado"
    assert lido[0].nome == "a"


def test_carregar_de_arquivo_ausente_devolve_lista_vazia(tmp_path):
    assert mod.carregar(tmp_path / "nao_existe.yaml") == []


def test_de_dict_ignora_chave_desconhecida():
    p = mod.Peer.de_dict({"id": 3, "token": "X", "nome": "x", "tipo": "pni",
                          "asn": 1, "campo_que_nao_existe": 9})
    assert p.id == 3 and p.token == "X"


def test_arquivo_do_peer(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "OUT", tmp_path)
    p = mod.Peer(id=1, token="268127", nome="x", tipo="cliente", asn=268127)
    assert p.arquivo().name == "268127-cliente.txt"


def test_familias_so_as_preenchidas():
    p = mod.Peer(id=1, token="T", nome="x", tipo="cliente", asn=1,
                 sessoes={"v4": {"local": "1.1.1.1", "remoto": "1.1.1.2"}, "v6": {}})
    assert p.familias() == ["v4"]


def test_achar_por_token():
    a = mod.Peer(id=0, token="A", nome="a", tipo="cliente", asn=1)
    assert mod.achar([a], "A") is a
    assert mod.achar([a], "Z") is None


def test_defaults_da_sessao():
    p = mod.Peer()
    assert p.bfd is True
    assert p.graceful_restart is True
    assert p.timer_keepalive is None
    assert p.timer_hold is None


def test_listas_por_familia_nao_sao_compartilhadas_entre_instancias():
    # default_factory, nao um dict no corpo da classe
    a, b = mod.Peer(), mod.Peer()
    a.prefixos["v4"].append("10.0.0.0/8")
    assert b.prefixos["v4"] == []
    assert a.sessoes is not b.sessoes
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_peers.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.peers'`

- [ ] **Step 3: Escrever `app/peers.py`**

```python
"""O peers.yaml: ler, gravar e alocar ID.

O arquivo e o estado do app. Ele guarda o cadastro de cada peer, mas
nao guarda o conteudo da CL-PEER-<T>: essa lista vive so no equipamento,
editada a mao, e o gerador nao tem como reproduzi-la.

O campo se chama `id` e nao `ident` porque ele aparece no nome de objeto
do XPL (CL-5PPA-01) e no formulario com esse nome. Sombra o builtin
dentro da dataclass, e isso e inofensivo.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.plan import FAMILIAS

RAIZ = Path(__file__).resolve().parent.parent
PEERS_YAML = RAIZ / "peers.yaml"
OUT = RAIZ / "out"

MAX_PEERS = 100


def _listas_por_familia():
    return {fam: [] for fam in FAMILIAS}


def _sessoes_vazias():
    return {fam: {} for fam in FAMILIAS}


@dataclass
class Peer:
    id: int = 0
    token: str = ""
    nome: str = ""
    tipo: str = "cliente"
    asn: int = 0
    classe: str | None = None
    descricao: str = ""

    lp_base: int = 300
    origem: int | None = None
    pop: int | None = None
    aprendizado: int | None = None
    ix_id: int | None = None

    # prefixos anunciados pelo peer (bgpq4 ou mao)
    prefixos: dict = field(default_factory=_listas_por_familia)
    # excecoes de TE: prefixos que se alcanca melhor pela borda do upstream
    te_prefixos: dict = field(default_factory=_listas_por_familia)
    # ASNs que este upstream nao pode anunciar
    ap_block: list = field(default_factory=list)
    # ASNs alcancados melhor pela borda do upstream
    ap_te: list = field(default_factory=list)
    # PNI: ASNs que a CDN pode anunciar
    ap_allowed: list = field(default_factory=list)
    # IX: membros que recebem LP 195 em vez de 190
    ap_prefer: list = field(default_factory=list)

    # knobs de sessao do bloco bgp
    bfd: bool = True
    graceful_restart: bool = True
    timer_keepalive: int | None = None
    timer_hold: int | None = None

    prepend_base: int = 0
    route_limit: int = 50

    sessoes: dict = field(default_factory=_sessoes_vazias)
    # community de blackhole DESTE upstream; vazia desliga o ramo
    bh_upstream: str = ""

    def familias(self):
        return [f for f in FAMILIAS if self.sessoes.get(f)]

    def arquivo(self):
        return OUT / ("%s-%s.txt" % (self.token, self.tipo))

    def para_dict(self):
        return {
            "id": self.id, "token": self.token, "nome": self.nome,
            "tipo": self.tipo, "asn": self.asn, "classe": self.classe,
            "descricao": self.descricao, "lp_base": self.lp_base,
            "origem": self.origem, "pop": self.pop,
            "aprendizado": self.aprendizado, "ix_id": self.ix_id,
            "prefixos": self.prefixos, "te_prefixos": self.te_prefixos,
            "ap_block": self.ap_block, "ap_te": self.ap_te,
            "ap_allowed": self.ap_allowed, "ap_prefer": self.ap_prefer,
            "bfd": self.bfd, "graceful_restart": self.graceful_restart,
            "timer_keepalive": self.timer_keepalive,
            "timer_hold": self.timer_hold,
            "prepend_base": self.prepend_base, "route_limit": self.route_limit,
            "sessoes": self.sessoes, "bh_upstream": self.bh_upstream,
        }

    @classmethod
    def de_dict(cls, d):
        conhecidos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in conhecidos})


def carregar(caminho=PEERS_YAML):
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    return [Peer.de_dict(d) for d in dados.get("peers", [])]


def gravar(peers, caminho=PEERS_YAML):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = {"peers": [p.para_dict() for p in peers]}
    caminho.write_text(
        yaml.safe_dump(dados, allow_unicode=False, sort_keys=False),
        encoding="utf-8")


def proximo_id(peers):
    usados = {p.id for p in peers}
    for i in range(MAX_PEERS):
        if i not in usados:
            return i
    raise ValueError("sem ID livre: a faixa 0-99 esta cheia")


def achar(peers, token):
    for p in peers:
        if p.token == token:
            return p
    return None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_peers.py -v`
Expected: PASS nos 12 testes.

- [ ] **Step 5: Commit**

```bash
git add app/peers.py tests/test_peers.py
git commit -m "Adiciona leitura e gravacao do peers.yaml"
```

---

### Task 3: `validate.py`

**Files:**
- Create: `app/validate.py`, `tests/test_validate.py`

**Interfaces:**
- Consumes: `app.plan` (Task 1), `app.peers.Peer` (Task 2).
- Produces: `@dataclass Erro(campo: str, mensagem: str)`; `validar(peer, peers, editando=False) -> list[Erro]`; `avisos(peer, peers) -> list[Erro]`; `erros_para_dict(erros) -> dict[str, str]`; `community_valida(community) -> bool`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_validate.py`:

```python
from app import validate
from app.peers import Peer


def um_peer(**kw):
    base = dict(
        id=1, token="268127", nome="Cliente ACME", tipo="cliente",
        asn=268127, classe="residencial", descricao="CLIENTE-AS268127",
        lp_base=300, origem=1110, pop=2001, aprendizado=None, ix_id=None,
        prefixos={"v4": ["45.169.232.0/22"], "v6": []},
        te_prefixos={"v4": [], "v6": []},
        ap_block=[], ap_te=[], ap_allowed=[], ap_prefer=[],
        bfd=True, graceful_restart=True, timer_keepalive=None, timer_hold=None,
        prepend_base=0, route_limit=50,
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"},
                 "v6": {}},
    )
    base.update(kw)
    return Peer(**base)


def campos(erros):
    return {e.campo for e in erros}


def test_peer_valido_nao_tem_erro():
    assert validate.validar(um_peer(), []) == []


def test_asn_reservado_e_erro():
    for asn in (0, 23456, 4294967295):
        assert "asn" in campos(validate.validar(um_peer(asn=asn), [])), asn


def test_asn_privado_e_aviso_e_nao_erro():
    assert validate.validar(um_peer(asn=64512), []) == []
    assert "asn" in campos(validate.avisos(um_peer(asn=64512), []))


def test_id_fora_da_faixa_e_erro():
    assert "id" in campos(validate.validar(um_peer(id=100), []))


def test_id_repetido_e_erro():
    outro = um_peer(id=1, token="9999", asn=9999)
    assert "id" in campos(validate.validar(um_peer(), [outro]))


def test_id_repetido_no_proprio_peer_editado_nao_e_erro():
    assert validate.validar(um_peer(), [um_peer()], editando=True) == []


def test_token_invalido_e_erro():
    for token in ("", "ix sp", "-IX", "IX-", "TOKENMUITOLONGO", "ix"):
        assert "token" in campos(validate.validar(um_peer(token=token), [])), token


def test_token_com_hifen_no_meio_e_aceito():
    assert "token" not in campos(validate.validar(um_peer(token="IX-SP"), []))


def test_token_repetido_e_erro():
    outro = um_peer(id=2, token="268127", asn=9999)
    assert "token" in campos(validate.validar(um_peer(), [outro]))


def test_sessao_duplicada_entre_peers_e_erro():
    outro = um_peer(id=2, token="9999", asn=9999,
                    sessoes={"v4": {"local": "10.0.0.1", "remoto": "198.51.100.2"},
                             "v6": {}})
    assert "sessoes.v4.remoto" in campos(validate.validar(um_peer(), [outro]))


def test_peer_sem_familia_nenhuma_e_erro():
    p = um_peer(sessoes={"v4": {}, "v6": {}})
    assert "sessoes" in campos(validate.validar(p, []))


def test_endereco_de_familia_errada_e_erro():
    p = um_peer(sessoes={"v4": {"local": "2001:db8::1", "remoto": "198.51.100.2"},
                         "v6": {}})
    assert "sessoes.v4.local" in campos(validate.validar(p, []))


def test_cliente_sem_prefix_list_e_erro():
    p = um_peer(prefixos={"v4": [], "v6": []})
    assert "prefixos" in campos(validate.validar(p, []))


def test_bloco_de_cliente_sobreposto_e_erro():
    outro = um_peer(id=2, token="9999", asn=9999,
                    prefixos={"v4": ["45.169.232.0/23"], "v6": []})
    assert "prefixos" in campos(validate.validar(um_peer(), [outro]))


def test_bloco_de_cliente_adjacente_nao_sobrepoe():
    outro = um_peer(id=2, token="9999", asn=9999,
                    prefixos={"v4": ["45.169.236.0/22"], "v6": []})
    assert "prefixos" not in campos(validate.validar(um_peer(), [outro]))


def test_lp_base_fora_da_faixa_e_erro():
    assert "lp_base" in campos(validate.validar(um_peer(lp_base=70000), []))


def test_route_limit_zero_e_erro():
    assert "route_limit" in campos(validate.validar(um_peer(route_limit=0), []))


def test_community_fora_da_faixa_e_erro():
    assert "origem" in campos(validate.validar(um_peer(origem=1700), []))


def test_pop_fora_da_faixa_e_erro():
    assert "pop" in campos(validate.validar(um_peer(pop=2000), []))
    assert "pop" in campos(validate.validar(um_peer(pop=3000), []))


def test_upstream_exige_ponto_de_aprendizado():
    p = um_peer(tipo="upstream", token="14840", asn=14840, classe=None,
                aprendizado=None, prefixos={"v4": [], "v6": []})
    assert "aprendizado" in campos(validate.validar(p, []))


def test_ix_exige_id_do_peeringdb():
    p = um_peer(tipo="ix", token="IX-SP", asn=26162, classe=None, ix_id=None,
                aprendizado=3010, prefixos={"v4": [], "v6": []})
    assert "ix_id" in campos(validate.validar(p, []))


def test_cliente_exige_classe():
    assert "classe" in campos(validate.validar(um_peer(classe=None), []))


def test_pni_exige_allowlist():
    p = um_peer(tipo="pni", token="CDN-A", asn=64510, classe=None,
                prefixos={"v4": [], "v6": []}, ap_allowed=[])
    assert "ap_allowed" in campos(validate.validar(p, []))


def test_upstream_sem_prefixos_de_te_em_branco_e_valido():
    p = um_peer(tipo="upstream", token="14840", asn=14840, classe=None,
                aprendizado=3100, prefixos={"v4": [], "v6": []})
    assert validate.validar(p, []) == []


def test_timer_pela_metade_e_erro():
    p = um_peer(timer_keepalive=10, timer_hold=None)
    assert "timer_hold" in campos(validate.validar(p, []))


def test_hold_menor_que_o_keepalive_e_erro():
    p = um_peer(timer_keepalive=30, timer_hold=10)
    assert "timer_hold" in campos(validate.validar(p, []))


def test_timer_par_valido():
    p = um_peer(timer_keepalive=10, timer_hold=30)
    assert "timer_hold" not in campos(validate.validar(p, []))


def test_community_valida():
    assert validate.community_valida("64512:1100")
    assert not validate.community_valida("14840:666")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_validate.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.validate'`

- [ ] **Step 3: Escrever `app/validate.py`**

```python
"""O que o app recusa antes de gerar.

Toda regra devolve um Erro com o nome do campo, para o formulario marcar
o campo certo em vez de mostrar um aviso solto no topo.
"""

import ipaddress
import re
from dataclasses import dataclass

from app import plan

TOKEN_RE = re.compile(r"^[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?$")
TOKEN_MAX = 12
ASN_MIN, ASN_MAX = 1, 4294967294
ASN_RESERVADOS = (0, 23456, 4294967295)
ASN_PRIVADOS = ((64496, 64511), (64512, 65534),
                (65536, 65551), (4200000000, 4294967294))


@dataclass
class Erro:
    campo: str
    mensagem: str


def erros_para_dict(erros):
    return {e.campo: e.mensagem for e in erros}


def avisos(peer, peers):
    """Coisas que o usuario precisa saber mas que nao impedem gerar."""
    saida = []
    if any(lo <= peer.asn <= hi for lo, hi in ASN_PRIVADOS):
        saida.append(Erro("asn", "ASN privado: confirme que o peer tambem o usa"))
    if peer.route_limit != plan.ROUTE_LIMIT.get(peer.tipo):
        saida.append(Erro(
            "route_limit",
            "a tabela do plano sugere %d para %s"
            % (plan.ROUTE_LIMIT[peer.tipo], peer.tipo)))
    return saida


def community_valida(community):
    return plan.faixa_ok(community)


def _sobrepoe(a, b):
    ra = ipaddress.ip_network(a, strict=False)
    rb = ipaddress.ip_network(b, strict=False)
    if ra.version != rb.version:
        return False
    return ra.overlaps(rb)


def _blocos(peer):
    for fam in plan.FAMILIAS:
        for cidr in peer.prefixos.get(fam) or []:
            yield fam, cidr


def _valida_timer(peer, erros):
    k, h = peer.timer_keepalive, peer.timer_hold
    if k is None and h is None:
        return
    if k is None or h is None:
        faltando = "timer_keepalive" if k is None else "timer_hold"
        erros.append(Erro(faltando, "os dois valores do timer andam juntos"))
        return
    if h <= k:
        erros.append(Erro("timer_hold", "hold tem que ser maior que keepalive"))


def validar(peer, peers, editando=False):
    erros = []

    if not (ASN_MIN <= peer.asn <= ASN_MAX) or peer.asn in ASN_RESERVADOS:
        erros.append(Erro("asn", "ASN reservado pela IANA"))

    if not (0 <= peer.id <= 99):
        erros.append(Erro("id", "o ID tem que ficar entre 0 e 99"))

    if not peer.token or len(peer.token) > TOKEN_MAX or not TOKEN_RE.match(peer.token):
        erros.append(Erro("token", "token: A-Z, 0-9 e hifen no meio, ate 12 caracteres"))

    if not (0 <= peer.lp_base <= 65535):
        erros.append(Erro("lp_base", "local preference entre 0 e 65535"))

    if peer.route_limit <= 0:
        erros.append(Erro("route_limit", "route-limit tem que ser maior que zero"))

    _valida_timer(peer, erros)

    if peer.tipo == "cliente":
        if peer.classe not in plan.CLASSES_CLIENTE:
            erros.append(Erro("classe", "cliente exige uma classe"))
        if not any(peer.prefixos.get(f) for f in plan.FAMILIAS):
            erros.append(Erro("prefixos", "cliente sem prefix-list nao sobe"))
        if peer.origem is not None and not (1000 <= peer.origem <= 1999):
            erros.append(Erro("origem", "origem fora da faixa 1xxx"))
        if peer.pop is not None and not (plan.POP_MIN <= peer.pop <= plan.POP_MAX):
            erros.append(Erro("pop", "POP entre 2001 e 2999"))
    else:
        if peer.tipo in ("upstream", "ix") and peer.aprendizado is None:
            erros.append(Erro("aprendizado", "ponto de aprendizado 3xxx obrigatorio"))
        elif peer.aprendizado is not None and not (
                plan.APRENDIZADO_MIN <= peer.aprendizado <= plan.APRENDIZADO_MAX):
            erros.append(Erro("aprendizado", "ponto de aprendizado entre 3000 e 3999"))
        if peer.tipo == "ix" and not peer.ix_id:
            erros.append(Erro("ix_id", "sessao de IX exige o ID do IX no PeeringDB"))
        if peer.tipo == "pni" and not peer.ap_allowed:
            erros.append(Erro("ap_allowed", "PNI sem allowlist de AS-path nao sobe"))

    familias = [f for f in plan.FAMILIAS if peer.sessoes.get(f)]
    if not familias:
        erros.append(Erro("sessoes", "configure pelo menos uma familia"))

    for fam in familias:
        sessao = peer.sessoes[fam]
        esperado = 4 if fam == "v4" else 6
        for lado in ("local", "remoto"):
            campo = "sessoes.%s.%s" % (fam, lado)
            valor = sessao.get(lado)
            if not valor:
                erros.append(Erro(campo, "endereco obrigatorio"))
                continue
            try:
                end = ipaddress.ip_address(valor)
            except ValueError:
                erros.append(Erro(campo, "endereco invalido"))
                continue
            if end.version != esperado:
                erros.append(Erro(campo, "endereco nao bate com a familia"))

    if not editando:
        for outro in peers:
            if outro.id == peer.id:
                erros.append(Erro("id", "ID ja usado pelo peer %s" % outro.nome))
            if outro.token == peer.token:
                erros.append(Erro("token", "token ja usado pelo peer %s" % outro.nome))
            for fam in familias:
                remoto = (peer.sessoes[fam] or {}).get("remoto")
                outro_remoto = (outro.sessoes.get(fam) or {}).get("remoto")
                if remoto and remoto == outro_remoto:
                    erros.append(Erro("sessoes.%s.remoto" % fam,
                                      "endereco ja usado pelo peer %s" % outro.nome))
            if peer.tipo == "cliente" and outro.tipo == "cliente":
                for fam_a, a in _blocos(peer):
                    for fam_b, b in _blocos(outro):
                        if fam_a == fam_b and _sobrepoe(a, b):
                            erros.append(Erro(
                                "prefixos",
                                "%s sobrepoe %s do peer %s" % (a, b, outro.nome)))

    return _sem_duplicata(erros)


def _sem_duplicata(erros):
    vistos, saida = set(), []
    for e in erros:
        chave = (e.campo, e.mensagem)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(e)
    return saida
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_validate.py -v`
Expected: PASS nos 28 testes.

- [ ] **Step 5: Commit**

```bash
git add app/validate.py tests/test_validate.py
git commit -m "Adiciona a validacao do formulario"
```

---

### Task 4: O bloco base

**Files:**
- Create: `app/render.py`, `templates/base.txt.j2`, `tests/golden/_base.txt`, `tests/test_render.py`

**Interfaces:**
- Consumes: `app.plan`.
- Produces: `ambiente() -> jinja2.Environment`; `render_base() -> str`; `escrever_base() -> Path`; `render_peer(peer) -> str`; `escrever_peer(peer) -> Path`; `render_remove(peer) -> str`; `render_criar_lista(peer) -> str`; `CABECALHO_BASE: str`; constantes `RAIZ`, `TEMPLATES`, `OUT`.

**O corpo de cada objeto do bloco base é transcrição literal do PLANO.md.** A fonte de cada um:

| Objeto | Seção do PLANO.md |
| --- | --- |
| `PL-BOGONS-V4`, `PL-BOGONS-V6` | Sets XPL / Bogons de prefixo |
| `AP-BOGON-ASN` | Sets XPL / Bogons de ASN |
| `AP-LOCAL-ORIGIN`, `AP-PATH-TOO-LONG` | Sets XPL / AS-path auxiliares |
| `CL-BLACKHOLE`, `CL-BLACKHOLE-PROPAGATE`, `CL-GSHUT`, `CL-ORIGEM-ANUNCIAVEL` | Sets XPL / Communities |
| `CL-NOADV-CUST`, `CL-ONLY-NOT-*`, `CL-OWN-ALL` | idem |
| `IMPORT-SANITY`, `EXPORT-SANITY`, `APPLY-CUSTOMER-LP` | Route-filters reutilizáveis |
| rotas de descarte | RTBH fim a fim / Rota de descarte |

Uma extensão ao PLANO, registrada na spec como autorizada: `IMPORT-SANITY` é um filtro só no documento, sem sufixo, usando `PL-BOGONS-V4`. O bloco base emite **dois**, `IMPORT-SANITY-V4` e `IMPORT-SANITY-V6`, com a mesma casca e a prefix-list da família. Sem isso a sessão v6 não tem sanidade.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_render.py`:

```python
from pathlib import Path

from app import render

GOLDEN = Path(__file__).resolve().parent / "golden"


def test_base_e_ascii():
    assert render.render_base().isascii()


def test_base_tem_os_objetos_compartilhados():
    texto = render.render_base()
    for nome in (
        "xpl ip-prefix-list PL-BOGONS-V4",
        "xpl ipv6-prefix-list PL-BOGONS-V6",
        "xpl as-path-list AP-BOGON-ASN",
        "xpl as-path-list AP-LOCAL-ORIGIN",
        "xpl as-path-list AP-PATH-TOO-LONG",
        "xpl community-list CL-BLACKHOLE",
        "xpl community-list CL-BLACKHOLE-PROPAGATE",
        "xpl community-list CL-GSHUT",
        "xpl community-list CL-ORIGEM-ANUNCIAVEL",
        "xpl community-list CL-NOADV-CUST",
        "xpl community-list CL-ONLY-NOT-UP",
        "xpl community-list CL-ONLY-NOT-IX",
        "xpl community-list CL-ONLY-NOT-PNI",
        "xpl community-list CL-ONLY-NOT-CLIENT",
        "xpl community-list CL-OWN-ALL",
        "xpl route-filter IMPORT-SANITY-V4",
        "xpl route-filter IMPORT-SANITY-V6",
        "xpl route-filter EXPORT-SANITY",
        "xpl route-filter APPLY-CUSTOMER-LP",
        "ip route-static 192.0.2.1 255.255.255.255 NULL0 tag 666",
        "ipv6 route-static 100:: 64 NULL0 tag 666",
    ):
        assert nome in texto, nome


def test_base_nao_emite_o_strip_external():
    # existe no PLANO so como registro do que nao funciona
    assert "STRIP-EXTERNAL" not in render.render_base()


def test_base_nao_emite_nada_por_peer():
    # nenhum objeto com o nome de um peer: o bloco base e igual para todos
    texto = render.render_base()
    for nome in ("CL-PEER-", "APPLY-PEER-", "CL-NOADV-", "LC-NOADV-",
                 "PL-CUST-", "AP-CUST-", "AP-BLOCK-", "CL-5PPA-", "LC-5PPA-"):
        assert nome not in texto, nome


def test_import_sanity_fecha_em_break_nas_duas_familias():
    texto = render.render_base()
    for fam in ("V4", "V6"):
        corpo = texto.split("xpl route-filter IMPORT-SANITY-%s" % fam)[1].split("end-filter")[0]
        assert corpo.strip().endswith("break")
        assert "finish" not in corpo
        assert "approve" not in corpo
        assert "refuse" in corpo


def test_cada_import_sanity_usa_os_bogons_da_propria_familia():
    texto = render.render_base()
    v4 = texto.split("xpl route-filter IMPORT-SANITY-V4")[1].split("end-filter")[0]
    v6 = texto.split("xpl route-filter IMPORT-SANITY-V6")[1].split("end-filter")[0]
    assert "PL-BOGONS-V4" in v4 and "PL-BOGONS-V6" not in v4
    assert "PL-BOGONS-V6" in v6 and "PL-BOGONS-V4" not in v6


def test_export_sanity_fecha_em_break():
    texto = render.render_base()
    corpo = texto.split("xpl route-filter EXPORT-SANITY")[1].split("end-filter")[0]
    assert corpo.strip().endswith("break")
    assert "finish" not in corpo


def test_apply_customer_lp_fecha_em_break_em_todos_os_ramos():
    texto = render.render_base()
    corpo = texto.split("xpl route-filter APPLY-CUSTOMER-LP")[1].split("end-filter")[0]
    # cinco ramos da escada, o GSHUT e o default
    assert corpo.count("break") == 7
    assert "finish" not in corpo
    assert "apply local-preference 300" in corpo


def test_apply_customer_lp_ordena_o_gshut_antes_da_escada():
    texto = render.render_base()
    corpo = texto.split("xpl route-filter APPLY-CUSTOMER-LP")[1].split("end-filter")[0]
    assert corpo.index("CL-GSHUT") < corpo.index("64512:101")


def test_bogons_v4_usa_a_forma_sem_barra():
    texto = render.render_base()
    corpo = texto.split("xpl ip-prefix-list PL-BOGONS-V4")[1].split("end-list")[0]
    assert "0.0.0.0 8 le 32" in corpo
    assert "224.0.0.0 3 le 32" in corpo
    assert "/" not in corpo


def test_base_nao_tem_overwrite():
    # o bloco base nao carimba community: quem carimba e o import de cada sessao
    assert "overwrite" not in render.render_base()


def test_base_nao_tem_parametro():
    assert "$" not in render.render_base()


def test_golden_do_bloco_base():
    assert render.render_base() == (GOLDEN / "_base.txt").read_text(encoding="ascii")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_render.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.render'`

- [ ] **Step 3: Escrever `app/render.py`**

```python
"""Jinja2 sobre os templates. Um template de bloco base e um por tipo."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app import plan

RAIZ = Path(__file__).resolve().parent.parent
TEMPLATES = RAIZ / "templates"
OUT = RAIZ / "out"

CABECALHO_BASE = ("bloco base: sets e filtros compartilhados. "
                  "Cole antes do bloco de qualquer peer.")


def ambiente():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,  # nome errado de variavel falha no teste, nao na config
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["plan"] = plan
    return env


def render_base():
    return ambiente().get_template("base.txt.j2").render()


def escrever_base():
    OUT.mkdir(parents=True, exist_ok=True)
    destino = OUT / "_base.txt"
    destino.write_text(render_base(), encoding="ascii")
    return destino


def render_peer(peer):
    return ambiente().get_template("%s.txt.j2" % peer.tipo).render(peer=peer)


def escrever_peer(peer):
    OUT.mkdir(parents=True, exist_ok=True)
    destino = peer.arquivo()
    destino.write_text(render_peer(peer), encoding="ascii")
    return destino


def render_remove(peer):
    return ambiente().get_template("remover.txt.j2").render(peer=peer)


def render_criar_lista(peer):
    """O quadro 'ao criar o peer': a CL-PEER-<T> vazia, colada uma vez so."""
    return ambiente().get_template("criar_lista.txt.j2").render(peer=peer)
```

O `encoding="ascii"` na escrita é de propósito: se um acento escapar de um template, o erro aparece ao gravar, não no TFTP de madrugada.

- [ ] **Step 4: Escrever `templates/base.txt.j2`**

```jinja
!- gerado por bgpgen - nao editar a mao
!- bloco base: sets e filtros compartilhados do AS64512
!- cole isto no F1A antes do bloco de qualquer peer
!- fonte: PLANO.md, secoes "Sets XPL" e "Route-filters reutilizaveis"

!- PLANO.md / Bogons de prefixo
xpl ip-prefix-list PL-BOGONS-V4
 0.0.0.0 8 le 32,
 10.0.0.0 8 le 32,
 100.64.0.0 10 le 32,
 127.0.0.0 8 le 32,
 169.254.0.0 16 le 32,
 172.16.0.0 12 le 32,
 192.0.0.0 24 le 32,
 192.0.2.0 24 le 32,
 192.88.99.0 24 le 32,
 192.168.0.0 16 le 32,
 198.18.0.0 15 le 32,
 198.51.100.0 24 le 32,
 203.0.113.0 24 le 32,
 224.0.0.0 3 le 32
 end-list

xpl ipv6-prefix-list PL-BOGONS-V6
 :: 0 le 0,
 :: 128,
 ::1 128,
 ::ffff:0:0 96 le 128,
 64:ff9b:1:: 48 le 128,
 100:: 64 le 128,
 2001:: 32 le 128,
 2001:2:: 48 le 128,
 2001:db8:: 32 le 128,
 2002:: 16 le 128,
 3fff:: 20 le 128,
 fc00:: 7 le 128,
 fe80:: 10 le 128,
 ff00:: 8 le 128
 end-list

!- PLANO.md / Bogons de ASN. Cobre a alocacao completa do IANA.
xpl as-path-list AP-BOGON-ASN
 regular _0_,
 pass '23456',
 pass '[64496..64511]',
 pass '[64512..65534]',
 pass '65535',
 pass '[65536..65551]',
 pass '[65552..131071]',
 pass '[4200000000..4294967294]',
 pass '4294967295'
 end-list

!- PLANO.md / AS-path auxiliares
xpl as-path-list AP-LOCAL-ORIGIN
 regular ^$
 end-list

!- filtro de leak barato: 40 ou mais hops e quase sempre vazamento
xpl as-path-list AP-PATH-TOO-LONG
 length ge 40
 end-list

!- PLANO.md / Communities
xpl community-list CL-BLACKHOLE
 65535:666,
 64512:666
 end-list

xpl community-list CL-BLACKHOLE-PROPAGATE
 64512:667
 end-list

xpl community-list CL-GSHUT
 65535:0
 end-list

!- so sai do AS o que carrega marca de origem propria ou de cliente
xpl community-list CL-ORIGEM-ANUNCIAVEL
{% for c in plan.ORIGEM_ANUNCIAVEL %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

!- 2xx de proibicao absoluta, visao de egress para cliente.
!- 201, 202 e 203 ficam de fora: dizem "nao anunciar para aquele tipo",
!- nao "nao anunciar para cliente", entao a rota segue para o cliente.
xpl community-list CL-NOADV-CUST
{% for c in plan.noadv_cust() %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

!- as 21x que excluem cada tipo de peer
xpl community-list CL-ONLY-NOT-UP
{% for c in plan.only_not("upstream") %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

xpl community-list CL-ONLY-NOT-IX
{% for c in plan.only_not("ix") %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

xpl community-list CL-ONLY-NOT-PNI
{% for c in plan.only_not("pni") %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

!- as 21x que excluem cliente: 213 fica de fora de proposito
xpl community-list CL-ONLY-NOT-CLIENT
{% for c in plan.only_not("cliente") %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

!- CL-OWN-ALL serve apenas para matches-any, nunca para apply.
!- Sem uso nos filtros de hoje, mantida para diagnostico manual.
xpl community-list CL-OWN-ALL
 64512:*
 end-list

!- PLANO.md / Route-filters reutilizaveis.
!- IMPORT-SANITY e emitido por familia: o do PLANO usa PL-BOGONS-V4 e
!- o documento usa a mesma casca nas duas. Fecha em break, nao em
!- finish: com finish a rota boa nunca chega ao resto do filtro.
{% for fam in ["v4", "v6"] %}
xpl route-filter IMPORT-SANITY-{{ fam|upper }}
 if ip route-destination in PL-BOGONS-{{ fam|upper }} then
  refuse
 endif
 if as-path matches-any AP-BOGON-ASN then
  refuse
 endif
 if as-path matches-any AP-PATH-TOO-LONG then
  refuse
 endif
 !- path vazio vindo de sessao eBGP so acontece com o check-first-as
 !- desligado naquela sessao; com ele no default esta linha nunca dispara
 if as-path matches-any AP-LOCAL-ORIGIN then
  refuse
 endif
 break
 end-filter

{% endfor %}
xpl route-filter EXPORT-SANITY
 !- so sai o que carrega marca de origem propria ou de cliente.
 !- e seguro por dois motivos: o ingress de upstream, IX e PNI usa
 !- overwrite, entao nada forjado por eles sobrevive; e a unica sessao
 !- que carimba origem sem sobrescrever e a de cliente, que tem
 !- prefix-list no import.
 if not community matches-any CL-ORIGEM-ANUNCIAVEL then
  refuse
 endif
 !- break incondicional: mesma regra do IMPORT-SANITY
 break
 end-filter

!- PLANO.md / Local preference. Fecha em break, nao em finish: cada ramo
!- precisa encerrar ali, senao o ramo seguinte sobrescreve o LP recem
!- gravado, e o import do cliente ainda tem trabalho depois da chamada.
xpl route-filter APPLY-CUSTOMER-LP
 if community matches-any CL-GSHUT then
  apply local-preference 0
  break
 endif
{% for community, lp in plan.LP_CLIENTE %}
 if community matches-any {{ plan.conjunto(community) }} then
  apply local-preference {{ lp }}
  break
 endif
{% endfor %}
 apply local-preference {{ plan.LP_CLIENTE_DEFAULT }}
 break
 end-filter

!- PLANO.md / RTBH fim a fim, rota de descarte.
!- Os dois enderecos sao placeholders de documentacao (RFC 5737 e
!- RFC 6666). O next-hop e o /32 do ramo de blackhole do import de
!- cliente; a rota de descarte so existe para o tag 666 ter destino.
ip route-static 192.0.2.1 255.255.255.255 NULL0 tag 666
ipv6 route-static 100:: 64 NULL0 tag 666
```

- [ ] **Step 5: Gerar o golden e conferir contra o PLANO.md**

Run:
```bash
.venv/bin/python -c "from app import render; print(render.render_base())" > tests/golden/_base.txt
```

Depois **leia o arquivo inteiro** e compare objeto por objeto com as seções "Sets XPL" e "Route-filters reutilizáveis" do PLANO.md. Corrija o template onde divergir. Este passo não é formalidade: é a única barreira contra transcrição silenciosamente errada.

- [ ] **Step 6: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_render.py -v`
Expected: PASS nos 14 testes.

- [ ] **Step 7: Commit**

```bash
git add app/render.py templates/base.txt.j2 tests/golden/_base.txt tests/test_render.py
git commit -m "Adiciona o render do bloco base"
```

---

### Task 5: Template de cliente

**Files:**
- Create: `templates/_macros.j2`, `templates/cliente.txt.j2`, `tests/golden/cliente.txt`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes: `app.render.ambiente()`, `app.plan`, `Peer`.
- Produces: as macros Jinja que os Tasks 6, 7 e 8 reusam — `cabecalho(peer)`, `sessao_do_peer(peer, fam)`, `familia_bgp(peer, fam, import_nome, export_nome)`.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/test_render.py`:

```python
from app.peers import Peer


def peer_cliente(**kw):
    base = dict(
        id=1, token="268127", nome="Cliente ACME", tipo="cliente",
        asn=268127, classe="residencial", descricao="CLIENTE-AS268127",
        lp_base=300, origem=1110, pop=2001,
        prefixos={"v4": ["45.169.232.0/22"], "v6": []},
        prepend_base=0, route_limit=50,
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"}, "v6": {}},
    )
    base.update(kw)
    return Peer(**base)


def test_cliente_e_ascii():
    assert render.render_peer(peer_cliente()).isascii()


def test_cliente_emite_os_objetos_do_tipo():
    texto = render.render_peer(peer_cliente())
    for nome in (
        "xpl ip-prefix-list PL-CUST-268127-V4",
        "xpl ip-prefix-list PL-CUST-268127-BH-V4",
        "xpl as-path-list AP-CUST-268127",
        "xpl route-filter CUST-268127-IMPORT-V4",
        "xpl route-filter CUST-268127-EXPORT-V4",
        "xpl route-filter APPLY-PEER-268127",
        "bgp 64512",
    ):
        assert nome in texto, nome


def test_cliente_nao_emite_a_community_list_do_peer():
    # o bloco do peer nao pode zerar a lista editada a mao
    assert "xpl community-list CL-PEER-268127" not in render.render_peer(peer_cliente())


def test_apply_peer_e_a_ultima_linha_do_import():
    texto = render.render_peer(peer_cliente())
    trecho = texto.split("xpl route-filter CUST-268127-IMPORT-V4")[1].split("end-filter")[0]
    corpo = [l.strip() for l in trecho.splitlines() if l.strip()]
    assert corpo[-2] == "call route-filter APPLY-PEER-268127"
    assert corpo[-1] == "finish"


def test_apply_peer_fecha_em_break():
    texto = render.render_peer(peer_cliente())
    corpo = texto.split("xpl route-filter APPLY-PEER-268127")[1].split("end-filter")[0]
    assert corpo.strip().endswith("break")
    assert "finish" not in corpo
    assert "apply community community-list CL-PEER-268127 additive" in corpo


def test_import_do_cliente_ordena_sanidade_blackhole_e_prefixo():
    texto = render.render_peer(peer_cliente())
    trecho = texto.split("xpl route-filter CUST-268127-IMPORT-V4")[1].split("end-filter")[0]
    assert trecho.index("call route-filter IMPORT-SANITY-V4") < trecho.index("PL-CUST-268127-BH-V4")
    assert trecho.index("PL-CUST-268127-BH-V4") < trecho.index("if not ip route-destination in PL-CUST-268127-V4")


def test_cliente_usa_additive_e_nunca_overwrite():
    texto = render.render_peer(peer_cliente())
    assert "overwrite" not in texto[texto.index("xpl route-filter CUST-268127-IMPORT-V4"):]


def test_export_do_cliente_nao_leva_export_sanity():
    assert "call route-filter EXPORT-SANITY" not in render.render_peer(peer_cliente())


def test_export_do_cliente_escada_de_prepend():
    texto = render.render_peer(peer_cliente())
    export = texto.split("xpl route-filter CUST-268127-EXPORT-V4")[1].split("end-filter")[0]
    assert "if large-community matches-any {64512:3:268127} then" in export
    assert "if large-community matches-any {64512:2:268127} then" in export
    assert "if large-community matches-any {64512:1:268127} then" in export
    assert "if large-community matches-any {64512:0:268127} then" in export


def test_prefixo_sai_sem_barra():
    texto = render.render_peer(peer_cliente())
    assert "45.169.232.0 22 le 24" in texto
    assert "45.169.232.0/22 le" not in texto


def test_bloco_bgp_do_cliente():
    texto = render.render_peer(peer_cliente())
    assert "peer 198.51.100.2 as-number 268127" in texto
    assert "peer 198.51.100.2 description CLIENTE-AS268127" in texto
    assert "peer 198.51.100.2 route-limit 50 alert-only" in texto
    assert "peer 198.51.100.2 public-as-only force" in texto
    assert "peer 198.51.100.2 route-filter CUST-268127-IMPORT-V4 import" in texto
    assert "peer 198.51.100.2 route-filter CUST-268127-EXPORT-V4 export" in texto
    assert "peer 198.51.100.2 advertise-community" in texto
    assert "peer 198.51.100.2 advertise-large-community" in texto


def test_bloco_bgp_traz_bfd_e_graceful_restart():
    texto = render.render_peer(peer_cliente())
    assert "peer 198.51.100.2 bfd enable" in texto
    assert "peer 198.51.100.2 capability-advertise graceful-restart" in texto


def test_bgp_sem_bfd_nao_emite_a_linha():
    texto = render.render_peer(peer_cliente(bfd=False))
    assert "bfd enable" not in texto


def test_bgp_sem_graceful_restart_nao_emite_a_linha():
    texto = render.render_peer(peer_cliente(graceful_restart=False))
    assert "graceful-restart" not in texto


def test_cliente_sem_timer_nao_emite_linha_de_timer():
    # o PLANO so poe timer explicito no upstream
    assert "timer keepalive" not in render.render_peer(peer_cliente())


def test_golden_do_cliente():
    assert render.render_peer(peer_cliente()) == (GOLDEN / "cliente.txt").read_text(encoding="ascii")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_render.py -k cliente -v`
Expected: FAIL com `TemplateNotFound: cliente.txt.j2`

- [ ] **Step 3: Escrever `templates/_macros.j2`**

```jinja
{% macro cabecalho(peer) -%}
!- gerado por bgpgen - nao editar a mao
!- peer {{ peer.id }} - {{ peer.tipo }} - AS{{ peer.asn }} - token {{ peer.token }}
!- bloco base pressuposto: out/_base.txt
{%- endmacro %}

{% macro sessao_do_peer(peer, fam) -%}
{% set s = peer.sessoes[fam] %}
 peer {{ s.remoto }} as-number {{ peer.asn }}
 peer {{ s.remoto }} description {{ peer.descricao }}
 peer {{ s.remoto }} route-limit {{ peer.route_limit }} {{ plan.ACAO_LIMITE }}
 peer {{ s.remoto }} {{ plan.AS_ONLY }}
{% if peer.timer_keepalive and peer.timer_hold %}
 peer {{ s.remoto }} timer keepalive {{ peer.timer_keepalive }} hold {{ peer.timer_hold }}
{% endif %}
{% if peer.graceful_restart %}
 peer {{ s.remoto }} capability-advertise graceful-restart
{% endif %}
{% if peer.bfd %}
 peer {{ s.remoto }} bfd enable
{% endif %}
{%- endmacro %}

{% macro familia_bgp(peer, fam, import_nome, export_nome) -%}
{% set s = peer.sessoes[fam] %}

 {{ "ipv6-family" if fam == "v6" else "ipv4-family" }} unicast
  peer {{ s.remoto }} enable
  peer {{ s.remoto }} route-filter {{ import_nome }} import
  peer {{ s.remoto }} route-filter {{ export_nome }} export
  peer {{ s.remoto }} advertise-community
  peer {{ s.remoto }} advertise-large-community
{%- endmacro %}
```

A ordem das linhas de sessão é a do gerador. O PLANO mostra duas ordens diferentes — `bfd` antes do `capability-advertise` no cliente, o inverso no upstream — e o VRP aceita qualquer uma, porque são comandos de peer independentes.

- [ ] **Step 4: Escrever `templates/cliente.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% for fam in peer.familias() %}
{% set U = fam|upper %}
{% set kw = "ipv6-prefix-list" if fam == "v6" else "ip-prefix-list" %}
{% set maxlen = 48 if fam == "v6" else 24 %}
{% set hostlen = 128 if fam == "v6" else 32 %}
{% set nexthop = "100::" if fam == "v6" else "192.0.2.1" %}
!- PLANO.md / Prefixos de cliente. Dois sets: anuncio normal com
!- le {{ maxlen }}, blackhole so com host. O le generico deixaria o
!- cliente picar o bloco em /{{ hostlen }} e tornaria o RTBH ambiguo.
xpl {{ kw }} PL-CUST-{{ peer.token }}-{{ U }}
{% for cidr in peer.prefixos[fam] %}
 {{ plan.cidr_para_xpl(cidr) }} le {{ maxlen }}{{ "," if not loop.last }}
{% endfor %}
 end-list

xpl {{ kw }} PL-CUST-{{ peer.token }}-BH-{{ U }}
{% for cidr in peer.prefixos[fam] %}
 {{ plan.cidr_para_xpl(cidr) }} ge {{ hostlen }} le {{ hostlen }}{{ "," if not loop.last }}
{% endfor %}
 end-list

!- saida do cliente. origin, nao pass: o que interessa e o ASN que
!- originou, nao por onde o path passou.
xpl as-path-list AP-CUST-{{ peer.token }}
 origin '{{ peer.asn }}'
 end-list

xpl route-filter CUST-{{ peer.token }}-IMPORT-{{ U }}
 call route-filter IMPORT-SANITY-{{ U }}

 !- blackhole: host dentro do bloco do cliente, com a community certa.
 !- Vem antes do teste de prefixo normal, que um /{{ hostlen }} nao passaria.
 if (community matches-any CL-BLACKHOLE or tag eq 666) and ip route-destination in PL-CUST-{{ peer.token }}-BH-{{ U }} then
  apply {{ "ipv6" if fam == "v6" else "ip" }} next-hop {{ nexthop }}
  apply local-preference {{ plan.LP_BLACKHOLE }}
  apply community {{ plan.conjunto(plan.BLACKHOLE_INFO, "64512:200") }} additive
  apply large-community {{ plan.conjunto(plan.c_large(1000, peer.asn)) }} additive
  finish
 endif

 !- anuncio normal: so o bloco autorizado
 if not ip route-destination in PL-CUST-{{ peer.token }}-{{ U }} then
  refuse
 endif

 if not as-path matches-any AP-CUST-{{ peer.token }} then
  refuse
 endif

 call route-filter APPLY-CUSTOMER-LP
 apply community {{ plan.conjunto("64512:%d" % peer.origem, "64512:%d" % peer.pop) }} additive
 apply large-community {{ plan.conjunto(plan.c_large(1000, peer.asn)) }} additive

 !- ULTIMA acao: a community que a operadora envia a este bloco, escrita
 !- quando o cliente pede. A lista CL-PEER-{{ peer.token }} vive so no
 !- equipamento, editada a mao, e o gerador nao a reproduz.
 call route-filter APPLY-PEER-{{ peer.token }}
 finish
 end-filter

xpl route-filter CUST-{{ peer.token }}-EXPORT-{{ U }}
 !- 200 e 204: nao anunciar para ninguem nem para outros clientes.
 !- 201, 202 e 203 ficam de fora: sao escopo relativo, nao proibicao
 !- de anunciar para cliente, entao a rota segue.
 if community matches-any CL-NOADV-CUST then
  refuse
 endif

 if community matches-any CL-ONLY-NOT-CLIENT then
  refuse
 endif

 if large-community matches-any {{ plan.conjunto(plan.c_large(0, peer.asn)) }} then
  refuse
 endif

 !- infra interna nunca vai para cliente. O 1901 saiu do plano junto
 !- com o overwrite de egress; a checagem fica como defesa em
 !- profundidade contra configuracao antiga que ainda o escreva.
 if community matches-any {{ plan.conjunto("64512:1900", "64512:1901") }} then
  refuse
 endif

 !- prepend no que enviamos a este cliente, se ele pedir
 if large-community matches-any {{ plan.conjunto(plan.c_large(3, peer.asn)) }} then
  apply as-path 64512 3 additive
 elseif large-community matches-any {{ plan.conjunto(plan.c_large(2, peer.asn)) }} then
  apply as-path 64512 2 additive
 elseif large-community matches-any {{ plan.conjunto(plan.c_large(1, peer.asn)) }} then
  apply as-path 64512 1 additive
 endif

 finish
 end-filter
{% endfor %}

!- criado junto com o peer e mantido a mao: o gerador nao reescreve
!- esta lista depois de cria-la. Ela aparece so no quadro "ao criar o
!- peer" da interface, nunca dentro do bloco do peer.
xpl route-filter APPLY-PEER-{{ peer.token }}
 !- confirmar com "?" se o "community-list" do meio e obrigatorio: o
 !- legado usa "apply community community-list <nome>", mas la e
 !- route-policy, e as duas views divergem em outros pontos.
 apply community community-list CL-PEER-{{ peer.token }} additive
 break
 end-filter

bgp 64512
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "CUST-" ~ peer.token ~ "-IMPORT-" ~ U,
     "CUST-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_render.py -k cliente -v`
Expected: PASS nos 16 testes. Se `test_apply_peer_e_a_ultima_linha_do_import` falhar, sobrou linha em branco depois do `call`.

- [ ] **Step 6: Gerar o golden e conferir contra o PLANO.md**

Run:
```bash
.venv/bin/python -c "
from app import render
from app.peers import Peer
p = Peer(id=1, token='268127', nome='Cliente ACME', tipo='cliente', asn=268127,
         classe='residencial', descricao='CLIENTE-AS268127', lp_base=300,
         origem=1110, pop=2001, prefixos={'v4': ['45.169.232.0/22'], 'v6': []},
         route_limit=50,
         sessoes={'v4': {'local': '198.51.100.1', 'remoto': '198.51.100.2'}, 'v6': {}})
print(render.render_peer(p))
" > tests/golden/cliente.txt
```

Compare linha a linha com "Exemplo: cliente de trânsito". Diferenças que **devem** existir:

- sem `$`, e sem `call route-filter EXPORT-SANITY`
- `CUST-268127-IMPORT-V4` no lugar de `CUST-IMPORT-268127` (o sufixo de família é o que separa v4 de v6)
- `call route-filter APPLY-PEER-268127` antes do `finish` — está no PLANO e no spec
- no bloco `bgp`, as linhas de BFD e graceful-restart vêm na ordem do gerador, não na do PLANO

Qualquer outra diferença é erro no template.

- [ ] **Step 7: Commit**

```bash
git add templates/_macros.j2 templates/cliente.txt.j2 tests/golden/cliente.txt tests/test_render.py
git commit -m "Adiciona o template de cliente"
```

---

### Task 6: Template de upstream

**Files:**
- Create: `templates/upstream.txt.j2`, `tests/golden/upstream.txt`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes: as macros do Task 5, `plan.noadv("upstream", id)`, `plan.only_not("upstream")`, `plan.CLASSE_6CA["upstream"]`, `plan.DIGITO_PREPEND`, `plan.TIMER_PADRAO["upstream"]`.
- Produces: nada que os Tasks 7 e 8 consumam.

- [ ] **Step 1: Escrever o teste que falha**

```python
def peer_upstream(**kw):
    base = dict(
        id=1, token="14840", nome="Upstream #1", tipo="upstream",
        asn=14840, classe=None, descricao="UPSTREAM-01-AS14840",
        lp_base=100, origem=1400, aprendizado=3100,
        prefixos={"v4": [], "v6": []},
        te_prefixos={"v4": ["198.51.100.0/24"], "v6": []},
        ap_block=["270814"], ap_te=["264381"],
        timer_keepalive=10, timer_hold=30,
        prepend_base=1, route_limit=1500000,
        sessoes={"v4": {"local": "203.0.113.2", "remoto": "203.0.113.1"}, "v6": {}},
        bh_upstream="14840:666",
    )
    base.update(kw)
    return Peer(**base)


def test_upstream_emite_os_objetos_do_tipo():
    texto = render.render_peer(peer_upstream())
    for nome in (
        "xpl as-path-list AP-BLOCK-14840",
        "xpl as-path-list AP-TE-PREFER-14840",
        "xpl ip-prefix-list PL-TE-PREFER-14840-V4",
        "xpl community-list CL-NOADV-14840",
        "xpl large-community-list LC-NOADV-14840",
        "xpl community-list CL-5PPA-01",
        "xpl large-community-list LC-5PPA-14840",
        "xpl large-community-list LC-PREP1-14840",
        "xpl large-community-list LC-PREP2-14840",
        "xpl large-community-list LC-PREP3-14840",
        "xpl route-filter UP-14840-IMPORT-V4",
        "xpl route-filter UP-14840-EXPORT-V4",
        "xpl route-filter APPLY-PEER-14840",
    ):
        assert nome in texto, nome


def test_upstream_nao_emite_a_community_list_do_peer():
    assert "xpl community-list CL-PEER-14840" not in render.render_peer(peer_upstream())


def test_noadv_do_upstream_leva_absoluta_do_tipo_e_deste_peer():
    texto = render.render_peer(peer_upstream())
    corpo = texto.split("xpl community-list CL-NOADV-14840")[1].split("end-list")[0]
    assert "64512:200" in corpo and "64512:201" in corpo and "64512:5010" in corpo


def test_cl_5ppa_tem_os_cinco_digitos():
    texto = render.render_peer(peer_upstream())
    corpo = texto.split("xpl community-list CL-5PPA-01")[1].split("end-list")[0]
    for d in range(5):
        assert "64512:501%d" % d in corpo


def test_ap_te_prefer_usa_origin():
    # PLANO.md: "AP-TE-PREFER-14840 / origin '264381'"
    texto = render.render_peer(peer_upstream())
    corpo = texto.split("xpl as-path-list AP-TE-PREFER-14840")[1].split("end-list")[0]
    assert "origin '264381'" in corpo
    assert "pass" not in corpo


def test_import_do_upstream_carimba_com_overwrite_antes_da_excecao_de_te():
    texto = render.render_peer(peer_upstream())
    import_ = texto.split("xpl route-filter UP-14840-IMPORT-V4")[1].split("end-filter")[0]
    assert "apply community {64512:1400, 64512:3100, 64512:2000} overwrite" in import_
    assert "apply large-community {64512:1000:14840} overwrite" in import_
    assert "apply local-preference 100" in import_
    assert "apply local-preference 250" in import_
    assert import_.index("overwrite") < import_.index("apply local-preference 250")
    assert [l.strip() for l in import_.splitlines() if l.strip()][-1] == "approve"


def test_import_do_upstream_recusa_o_ap_block():
    texto = render.render_peer(peer_upstream())
    import_ = texto.split("xpl route-filter UP-14840-IMPORT-V4")[1].split("end-filter")[0]
    assert "if as-path matches-any AP-BLOCK-14840 then" in import_


def test_te_em_branco_nao_emite_o_ramo_nem_a_lista():
    p = peer_upstream(te_prefixos={"v4": [], "v6": []}, ap_te=[])
    texto = render.render_peer(p)
    import_ = texto.split("xpl route-filter UP-14840-IMPORT-V4")[1].split("end-filter")[0]
    assert "PL-TE-PREFER-14840-V4" not in import_
    assert "AP-TE-PREFER-14840" not in import_
    assert "apply local-preference 250" not in import_
    assert "xpl ip-prefix-list PL-TE-PREFER-14840-V4" not in texto
    assert "xpl as-path-list AP-TE-PREFER-14840" not in texto


def test_te_so_com_prefixo_de_uma_familia_nao_emite_o_ramo_da_outra():
    # v4 tem prefixo, v6 nao: o ramo de TE so sai no filtro v4
    p = peer_upstream(
        sessoes={"v4": {"local": "203.0.113.2", "remoto": "203.0.113.1"},
                 "v6": {"local": "2001:db8::2", "remoto": "2001:db8::1"}})
    texto = render.render_peer(p)
    v6 = texto.split("xpl route-filter UP-14840-IMPORT-V6")[1].split("end-filter")[0]
    assert "apply local-preference 250" not in v6


def test_export_do_upstream_chama_o_apply_peer_por_ultimo():
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    corpo = [l.strip() for l in export.splitlines() if l.strip()]
    assert corpo[-2] == "call route-filter APPLY-PEER-14840"
    assert corpo[-1] == "finish"


def test_export_do_upstream_tem_exatamente_um_overwrite():
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert export.count("overwrite") == 1
    assert "apply community {14840:666} overwrite" in export


def test_blackhole_do_upstream_usa_a_community_do_campo():
    texto = render.render_peer(peer_upstream(bh_upstream="64500:666"))
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "apply community {64500:666} overwrite" in export


def test_blackhole_sem_community_nao_emite_overwrite():
    texto = render.render_peer(peer_upstream(bh_upstream=""))
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "overwrite" not in export
    # o ramo continua existindo: o /32 que nao propaga e recusado
    assert "refuse" in export


def test_blackhole_do_upstream_precede_o_export_sanity():
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert export.index("CL-BLACKHOLE-PROPAGATE") < export.index("call route-filter EXPORT-SANITY")


def test_ramo_5ppa_aninha_e_a_classe_6ca_fica_no_else():
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "if community matches-any CL-5PPA-01 or large-community matches-any LC-5PPA-14840 then" in export
    assert "{64512:5014}" in export and "{64512:5013}" in export and "{64512:5012}" in export
    assert "{64512:5011}" not in export      # P1 explicito so barra a classe
    assert "if community matches-any {64512:614} then" in export
    assert export.index("CL-5PPA-01") < export.index("64512:614")


def test_prepend_base_zero_nao_emite_linha():
    texto = render.render_peer(peer_upstream(prepend_base=0))
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "apply as-path 64512 0 additive" not in export


def test_prepend_base_maior_que_zero_emite_linha_literal():
    texto = render.render_peer(peer_upstream(prepend_base=1))
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "apply as-path 64512 1 additive" in export


def test_export_do_upstream_med_zero_e_rede_do_2000():
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "apply med 0" in export
    assert "if community matches-any {64512:2000} then" in export


def test_bloco_bgp_do_upstream_traz_o_timer():
    texto = render.render_peer(peer_upstream())
    assert "peer 203.0.113.1 timer keepalive 10 hold 30" in texto
    assert "peer 203.0.113.1 route-limit 1500000 alert-only" in texto
    assert "peer 203.0.113.1 bfd enable" in texto
    assert "peer 203.0.113.1 capability-advertise graceful-restart" in texto


def test_golden_do_upstream():
    assert render.render_peer(peer_upstream()) == (GOLDEN / "upstream.txt").read_text(encoding="ascii")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_render.py -k upstream -v`
Expected: FAIL com `TemplateNotFound: upstream.txt.j2`

- [ ] **Step 3: Escrever `templates/upstream.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% for fam in peer.familias() %}
{% set U = fam|upper %}
{% set kw = "ipv6-prefix-list" if fam == "v6" else "ip-prefix-list" %}
{% set maxlen = 48 if fam == "v6" else 24 %}
!- PLANO.md / AS-path por peer
xpl as-path-list AP-BLOCK-{{ peer.token }}
{% for asn in peer.ap_block %}
 pass '{{ asn }}'{{ "," if not loop.last }}
{% endfor %}
 end-list

{% if peer.ap_te %}
!- ASNs que se alcanca melhor pela borda deste upstream. origin, como
!- no PLANO: o que interessa e quem originou, nao por onde passou.
xpl as-path-list AP-TE-PREFER-{{ peer.token }}
{% for asn in peer.ap_te %}
 origin '{{ asn }}'{{ "," if not loop.last }}
{% endfor %}
 end-list

{% endif %}
{% if peer.te_prefixos[fam] %}
!- conteudo de EXEMPLO no PLANO: troque pelos prefixos reais antes de subir
xpl {{ kw }} PL-TE-PREFER-{{ peer.token }}-{{ U }}
{% for cidr in peer.te_prefixos[fam] %}
 {{ plan.cidr_para_xpl(cidr) }} le {{ maxlen }}{{ "," if not loop.last }}
{% endfor %}
 end-list

{% endif %}
!- um set por peer: evita cadeia de OR na condicao.
!- o 5xx aqui e o alias 5PPA do "nao anunciar para o peer".
xpl community-list CL-NOADV-{{ peer.token }}
{% for c in plan.noadv("upstream", peer.id) %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

xpl large-community-list LC-NOADV-{{ peer.token }}
 {{ plan.c_large(0, peer.asn) }}
 end-list

!- qualquer 5PPA do peer, inclusive o digito 0. Nao carrega acao:
!- serve para o egress saber que o cliente falou deste peer e para
!- barrar a classe 6CA, que perderia para o especifico.
xpl community-list CL-5PPA-{{ "%02d"|format(peer.id) }}
{% for d in range(5) %}
 {{ plan.c5ppa(peer.id, d) }}{{ "," if not loop.last }}
{% endfor %}
 end-list

!- espelho do CL-5PPA no eixo de 32 bits.
xpl large-community-list LC-5PPA-{{ peer.token }}
{% for f in range(5) %}
 {{ plan.c_large(f, peer.asn) }}{{ "," if not loop.last }}
{% endfor %}
 end-list

xpl large-community-list LC-PREP1-{{ peer.token }}
 {{ plan.c_large(1, peer.asn) }}
 end-list

xpl large-community-list LC-PREP2-{{ peer.token }}
 {{ plan.c_large(2, peer.asn) }}
 end-list

xpl large-community-list LC-PREP3-{{ peer.token }}
 {{ plan.c_large(3, peer.asn) }}
 end-list

xpl route-filter UP-{{ peer.token }}-IMPORT-{{ U }}
 call route-filter IMPORT-SANITY-{{ U }}

{% if peer.ap_block %}
 if as-path matches-any AP-BLOCK-{{ peer.token }} then
  refuse
 endif

{% endif %}
 apply local-preference {{ peer.lp_base }}

 !- overwrite: nada do que o upstream escreveu em community sobrevive.
 !- e o que torna seguro o matches-any CL-ORIGEM-ANUNCIAVEL no export.
 !- 2000 marca "aprendida de fora", e o export de outro upstream recusa.
 apply community {{ plan.conjunto("64512:%d" % peer.origem, "64512:%d" % peer.aprendizado, "64512:2000") }} overwrite
 apply large-community {{ plan.conjunto(plan.c_large(1000, peer.asn)) }} overwrite

{% if peer.te_prefixos[fam] or peer.ap_te %}
 !- excecoes de TE, aplicadas depois do carimbo base.
 !- Se a lista ficar vazia a excecao simplesmente nao existe; o risco e
 !- o oposto, prefixo errado faz o trafego sair e voltar.
 if{% if peer.te_prefixos[fam] %} ip route-destination in PL-TE-PREFER-{{ peer.token }}-{{ U }}{% endif %}{% if peer.te_prefixos[fam] and peer.ap_te %} or{% endif %}{% if peer.ap_te %} as-path matches-any AP-TE-PREFER-{{ peer.token }}{% endif %} then
  apply local-preference {{ plan.LP_TE_PREFER }}
 endif

{% endif %}
 approve
 end-filter

xpl route-filter UP-{{ peer.token }}-EXPORT-{{ U }}
 !- 1. blackhole primeiro: finish para nao cair no EXPORT-SANITY.
 !- O overwrite aqui nao e limpeza: e a definicao do anuncio de
 !- blackhole. Durante ataque o host sai com a community de blackhole
 !- deste upstream e nada mais, para que nenhuma community escrita
 !- pelo cliente a neutralize.
 if (community matches-any CL-BLACKHOLE or tag eq 666) and ip route-destination in {{ "{0.0.0.0 0 ge 32 le 32}" if fam == "v4" else "{:: 0 ge 128 le 128}" }} then
  if community matches-any CL-BLACKHOLE-PROPAGATE then
{% if peer.bh_upstream %}
   apply community {{ plan.conjunto(peer.bh_upstream) }} overwrite
{% endif %}
   finish
  else
   refuse
  endif
 endif

 !- 2. sanidade antes de liberar a rota
 call route-filter EXPORT-SANITY

 !- 3. rede de seguranca do 2000: rota aprendida de fora ja caiu acima,
 !- entao isto so alcanca rota de cliente que escreveu o 2000 sozinha.
 if community matches-any {{ plan.conjunto("64512:2000") }} then
  refuse
 endif

 !- 4. escopo pedido pelo cliente para este peer
 if community matches-any CL-NOADV-{{ peer.token }} or large-community matches-any LC-NOADV-{{ peer.token }} then
  refuse
 endif

 !- 5. somente para outro peer
 if community matches-any CL-ONLY-NOT-UP then
  refuse
 endif

 !- 6. 5PPA por peer especifico: P4=3x, P3=2x, P2=1x. Se veio QUALQUER
 !- 5PPA do peer, a classe 6CA nao entra: especifico vence generico.
 !- O P1 explicito so impede a classe, e por isso o aninhamento e
 !- if/elseif e nao finish, que saltaria os passos 8 e 9.
 if community matches-any CL-5PPA-{{ "%02d"|format(peer.id) }} or large-community matches-any LC-5PPA-{{ peer.token }} then
  if community matches-any {{ plan.conjunto(plan.c5ppa(peer.id, 4)) }} or large-community matches-any LC-PREP3-{{ peer.token }} then
   apply as-path 64512 3 additive
  elseif community matches-any {{ plan.conjunto(plan.c5ppa(peer.id, 3)) }} or large-community matches-any LC-PREP2-{{ peer.token }} then
   apply as-path 64512 2 additive
  elseif community matches-any {{ plan.conjunto(plan.c5ppa(peer.id, 2)) }} or large-community matches-any LC-PREP1-{{ peer.token }} then
   apply as-path 64512 1 additive
  endif
 else
  !- 7. sem 5PPA, vale a classe 6CA (classe {{ plan.CLASSE_6CA["upstream"] }} = upstream)
  if community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["upstream"], 4)) }} then
   apply as-path 64512 3 additive
  elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["upstream"], 3)) }} then
   apply as-path 64512 2 additive
  elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["upstream"], 2)) }} then
   apply as-path 64512 1 additive
  endif
 endif

{% if peer.prepend_base %}
 !- 8. prepend base de engenharia: o valor JA E o numero de prepends,
 !- entao a linha nao sai quando ele e zero.
 apply as-path 64512 {{ peer.prepend_base }} additive
{% endif %}
 !- 9. saida comum
 apply med 0

 !- ULTIMA acao: as communities deste upstream, para tudo que sai por
 !- ele. Lista mantida a mao no equipamento, nao gerada.
 call route-filter APPLY-PEER-{{ peer.token }}
 finish
 end-filter
{% endfor %}

xpl route-filter APPLY-PEER-{{ peer.token }}
 apply community community-list CL-PEER-{{ peer.token }} additive
 break
 end-filter

bgp 64512
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "UP-" ~ peer.token ~ "-IMPORT-" ~ U,
     "UP-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

Duas decisões que merecem registro no próprio template:

- **A prefix-list de TE leva token e família (`PL-TE-PREFER-14840-V4`); a as-path-list leva só o token (`AP-TE-PREFER-14840`).** Esta não tem eixo por família, então o sufixo seria ruído. As demais listas seguem a mesma regra: só a prefix-list tem família no nome.
- **Lista de TE vazia não emite o ramo.** Com as duas listas vazias, o `if` inteiro sai do filtro em vez de virar um `matches-any` contra lista vazia, cuja semântica o PLANO não confirma. Quando só uma das listas tem conteúdo, o `if` sai com uma condição só, montada condicionalmente — sem `false` literal, que o VRP não aceita.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_render.py -k upstream -v`
Expected: PASS nos 20 testes.

- [ ] **Step 5: Gerar o golden e conferir contra o PLANO.md**

Run:
```bash
.venv/bin/python -c "
from app import render
from app.peers import Peer
p = Peer(id=1, token='14840', nome='Upstream #1', tipo='upstream', asn=14840,
         descricao='UPSTREAM-01-AS14840', lp_base=100, origem=1400, aprendizado=3100,
         prefixos={'v4': [], 'v6': []},
         te_prefixos={'v4': ['198.51.100.0/24'], 'v6': []},
         ap_block=['270814'], ap_te=['264381'],
         timer_keepalive=10, timer_hold=30,
         prepend_base=1, route_limit=1500000,
         sessoes={'v4': {'local': '203.0.113.2', 'remoto': '203.0.113.1'}, 'v6': {}},
         bh_upstream='14840:666')
print(render.render_peer(p))
" > tests/golden/upstream.txt
```

Conferir contra "Exemplo: upstream". Diferenças que **devem** existir:

- sem `$` e sem `()` na chamada do `route-filter` dentro do `bgp`
- com `call APPLY-PEER-14840` antes do `finish`
- `PL-TE-PREFER-14840-V4` onde o PLANO escreve `PL-TE-PREFER-14840` (a lista ganha o eixo de família)
- `CL-NOADV-14840` onde o PLANO escreve `CL-NOADV-UP1` (ver divergências no fim)
- `apply as-path 64512 1 additive` no lugar da chamada parametrizada `UP-EXPORT-14840(1)`, que é o mesmo efeito com valor literal
- o `route-limit` sai `1500000` pela tabela, não `1100000` do exemplo — é a nota do formulário

Qualquer outra diferença é erro no template.

- [ ] **Step 6: Commit**

```bash
git add templates/upstream.txt.j2 tests/golden/upstream.txt tests/test_render.py
git commit -m "Adiciona o template de upstream"
```

---

### Task 7: Template de IX

**Files:**
- Create: `templates/ix.txt.j2`, `tests/golden/ix.txt`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes: as macros do Task 5, `plan.noadv("ix", id)`, `plan.only_not("ix")`, `plan.CLASSE_6CA["ix"]`, `plan.LP_IX_CDN`.
- Produces: nada que o Task 8 consuma.

- [ ] **Step 1: Escrever o teste que falha**

```python
def peer_ix(**kw):
    base = dict(
        id=10, token="IX-SP", nome="IX.br Sao Paulo", tipo="ix",
        asn=26162, classe=None, descricao="IX-SP-AS26162",
        lp_base=190, origem=1300, aprendizado=3010, ix_id=9999,
        prefixos={"v4": [], "v6": []}, ap_prefer=["15169"],
        prepend_base=0, route_limit=500000,
        sessoes={"v4": {"local": "187.16.192.1", "remoto": "187.16.192.2"}, "v6": {}},
    )
    base.update(kw)
    return Peer(**base)


def test_ix_emite_os_objetos_do_tipo():
    texto = render.render_peer(peer_ix())
    for nome in (
        "xpl community-list CL-NOADV-IX-SP",
        "xpl large-community-list LC-NOADV-IX-SP",
        "xpl as-path-list AP-IX-SP",
        "xpl route-filter IX-IX-SP-IMPORT-V4",
        "xpl route-filter IX-IX-SP-EXPORT-V4",
    ):
        assert nome in texto, nome


def test_ix_nao_emite_o_par_do_peer():
    texto = render.render_peer(peer_ix())
    assert "CL-PEER-IX-SP" not in texto
    assert "APPLY-PEER-IX-SP" not in texto
    assert "apply community community-list" not in texto


def test_noadv_do_ix_leva_absoluta_do_tipo_e_deste_peer():
    texto = render.render_peer(peer_ix())
    corpo = texto.split("xpl community-list CL-NOADV-IX-SP")[1].split("end-list")[0]
    assert "64512:200" in corpo and "64512:203" in corpo and "64512:5100" in corpo


def test_ap_prefer_usa_peer_is():
    # PLANO.md: "AP-IX-CDN-A / peer-is '64510'"
    texto = render.render_peer(peer_ix())
    corpo = texto.split("xpl as-path-list AP-IX-SP")[1].split("end-list")[0]
    assert "peer-is '15169'" in corpo
    assert "pass" not in corpo


def test_ix_import_recusa_path_longo_antes_de_carimbar():
    texto = render.render_peer(peer_ix())
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert "if as-path length ge 4 then" in import_
    assert import_.index("length ge 4") < import_.index("overwrite")


def test_ix_import_carimba_com_overwrite_e_a_informativa_do_ix():
    texto = render.render_peer(peer_ix())
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert "apply community {64512:1300, 64512:3010, 64512:2000} overwrite" in import_
    assert "apply large-community {64512:1001:9999} overwrite" in import_


def test_ix_import_sobe_lp_para_membro_preferido():
    texto = render.render_peer(peer_ix())
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert "if as-path matches-any AP-IX-SP then" in import_
    assert "apply local-preference 195" in import_
    assert "apply local-preference 190" in import_


def test_ix_sem_membro_preferido_nao_emite_o_ramo_de_195():
    texto = render.render_peer(peer_ix(ap_prefer=[]))
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert "apply local-preference 190" in import_
    assert "apply local-preference 195" not in import_
    assert "xpl as-path-list AP-IX-SP" not in texto


def test_ix_import_fecha_em_finish():
    texto = render.render_peer(peer_ix())
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert [l.strip() for l in import_.splitlines() if l.strip()][-1] == "finish"


def test_ix_export_nao_tem_prepend_por_peer():
    texto = render.render_peer(peer_ix())
    export = texto.split("xpl route-filter IX-IX-SP-EXPORT-V4")[1].split("end-filter")[0]
    assert "5PPA" not in export


def test_ix_export_usa_a_classe_2():
    texto = render.render_peer(peer_ix())
    export = texto.split("xpl route-filter IX-IX-SP-EXPORT-V4")[1].split("end-filter")[0]
    assert "64512:624" in export and "64512:623" in export and "64512:622" in export


def test_ix_export_nao_limpa_e_nao_chama_apply_peer():
    texto = render.render_peer(peer_ix())
    export = texto.split("xpl route-filter IX-IX-SP-EXPORT-V4")[1].split("end-filter")[0]
    assert "overwrite" not in export
    assert "APPLY-PEER" not in export


def test_ix_export_chama_export_sanity():
    texto = render.render_peer(peer_ix())
    export = texto.split("xpl route-filter IX-IX-SP-EXPORT-V4")[1].split("end-filter")[0]
    assert "call route-filter EXPORT-SANITY" in export


def test_golden_do_ix():
    assert render.render_peer(peer_ix()) == (GOLDEN / "ix.txt").read_text(encoding="ascii")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_render.py -k "peer_ix or test_ix" -v`
Expected: FAIL com `TemplateNotFound: ix.txt.j2`

- [ ] **Step 3: Escrever `templates/ix.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% for fam in peer.familias() %}
{% set U = fam|upper %}
!- um set por peer: evita cadeia de OR na condicao.
xpl community-list CL-NOADV-{{ peer.token }}
{% for c in plan.noadv("ix", peer.id) %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

xpl large-community-list LC-NOADV-{{ peer.token }}
 {{ plan.c_large(0, peer.asn) }}
 end-list

{% if peer.ap_prefer %}
!- membros deste IX que recebem LP {{ plan.LP_IX_CDN }} em vez de {{ peer.lp_base }}.
!- peer-is, nao pass: o route server e transparente e nao insere o
!- proprio ASN no path, entao peer-is identifica quem realmente
!- anunciou, e da politica por membro com uma unica sessao contra o RS.
xpl as-path-list AP-IX-{{ peer.token }}
{% for asn in peer.ap_prefer %}
 peer-is '{{ asn }}'{{ "," if not loop.last }}
{% endfor %}
 end-list

{% endif %}
xpl route-filter IX-{{ peer.token }}-IMPORT-{{ U }}
 call route-filter IMPORT-SANITY-{{ U }}

 !- anti-leak de IX: membro nao deve anunciar rota de transito
 if as-path length ge 4 then
  refuse
 endif

 !- overwrite: nada do que o membro do IX escreveu sobrevive.
 !- 1001:<ix_id> e a informativa de IX; o id e o do PeeringDB, nao o
 !- ASN do route server.
 apply community {{ plan.conjunto("64512:%d" % peer.origem, "64512:%d" % peer.aprendizado, "64512:2000") }} overwrite
 apply large-community {{ plan.conjunto(plan.c_large(1001, peer.ix_id)) }} overwrite

{% if peer.ap_prefer %}
 if as-path matches-any AP-IX-{{ peer.token }} then
  apply local-preference {{ plan.LP_IX_CDN }}
 else
  apply local-preference {{ peer.lp_base }}
 endif
{% else %}
 apply local-preference {{ peer.lp_base }}
{% endif %}

 finish
 end-filter

xpl route-filter IX-{{ peer.token }}-EXPORT-{{ U }}
 call route-filter EXPORT-SANITY

 !- rede de seguranca do 2000, igual ao egress de upstream:
 !- rota aprendida de fora ja caiu no EXPORT-SANITY acima.
 if community matches-any {{ plan.conjunto("64512:2000") }} then
  refuse
 endif

 if community matches-any CL-NOADV-{{ peer.token }} or large-community matches-any {{ plan.conjunto(plan.c_large(0, peer.asn)) }} then
  refuse
 endif

 if community matches-any CL-ONLY-NOT-IX then
  refuse
 endif

 !- 6CA classe {{ plan.CLASSE_6CA["ix"] }} = IX publico; P2=1x, P3=2x, P4=3x.
 !- Sem ramo 5PPA: o route server repassa o mesmo AS-path a todos os
 !- membros, entao prepend no egress da sessao com o RS prependa para
 !- todo mundo. Prepend por membro so com sessao bilateral.
 if community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["ix"], 4)) }} then
  apply as-path 64512 3 additive
 elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["ix"], 3)) }} then
  apply as-path 64512 2 additive
 elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["ix"], 2)) }} then
  apply as-path 64512 1 additive
 endif

 !- sem limpeza no fecho: a rota sai com tudo o que carrega, e o que
 !- decide o anuncio sao os matches-any acima.
 finish
 end-filter
{% endfor %}

bgp 64512
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "IX-" ~ peer.token ~ "-IMPORT-" ~ U,
     "IX-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

Nota sobre o nome: o token de IX já é um apelido, então o filtro sai `IX-<T>-IMPORT-<FAM>`. Com o token `IX-SP` isso dá `IX-IX-SP-IMPORT-V4`, que é feio mas é a única forma que não colide: encurtar para `IX-SP-IMPORT-V4` faria dois IXs de tokens diferentes colidirem se um deles se chamasse `SP`. O spec fixa o prefixo de tipo; o token é do usuário. Está na lista de divergências.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_render.py -k "peer_ix or test_ix" -v`
Expected: PASS nos 14 testes.

- [ ] **Step 5: Gerar o golden e conferir contra o PLANO.md**

Run:
```bash
.venv/bin/python -c "
from app import render
from app.peers import Peer
p = Peer(id=10, token='IX-SP', nome='IX.br Sao Paulo', tipo='ix', asn=26162,
         descricao='IX-SP-AS26162', lp_base=190, origem=1300, aprendizado=3010,
         ix_id=9999, prefixos={'v4': [], 'v6': []}, ap_prefer=['15169'],
         route_limit=500000,
         sessoes={'v4': {'local': '187.16.192.1', 'remoto': '187.16.192.2'}, 'v6': {}})
print(render.render_peer(p))
" > tests/golden/ix.txt
```

Conferir contra "Exemplo: IX e PNI / IX via route server". No PLANO o filtro chama-se `IX-IMPORT-SP` e a lista de membro preferido chama-se `AP-IX-CDN-A`; aqui saem como `IX-IX-SP-IMPORT-V4` e `AP-IX-SP`. O `9999` do campo `ix_id` é o placeholder do PLANO e continua no golden: troque por um ID real antes de usar de verdade.

- [ ] **Step 6: Commit**

```bash
git add templates/ix.txt.j2 tests/golden/ix.txt tests/test_render.py
git commit -m "Adiciona o template de IX"
```

---

### Task 8: Template de PNI

**Files:**
- Create: `templates/pni.txt.j2`, `tests/golden/pni.txt`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes: as macros do Task 5, `plan.noadv("pni", id)`, `plan.only_not("pni")`, `plan.CLASSE_6CA["pni"]`, `plan.GEO_PNI`.
- Produces: nada.

- [ ] **Step 1: Escrever o teste que falha**

```python
def peer_pni(**kw):
    base = dict(
        id=20, token="CDN-A", nome="PNI CDN A", tipo="pni",
        asn=64510, classe=None, descricao="PNI-CDN-A-AS64510",
        lp_base=200, origem=1500, aprendizado=None,
        prefixos={"v4": [], "v6": []}, ap_allowed=["64510"],
        prepend_base=0, route_limit=10000,
        sessoes={"v4": {"local": "10.0.0.1", "remoto": "10.0.0.2"}, "v6": {}},
    )
    base.update(kw)
    return Peer(**base)


def test_pni_emite_os_objetos_do_tipo():
    texto = render.render_peer(peer_pni())
    for nome in (
        "xpl as-path-list AP-CDN-A-ALLOWED",
        "xpl community-list CL-NOADV-CDN-A",
        "xpl large-community-list LC-NOADV-CDN-A",
        "xpl route-filter PNI-CDN-A-IMPORT-V4",
        "xpl route-filter PNI-CDN-A-EXPORT-V4",
    ):
        assert nome in texto, nome


def test_pni_nao_emite_o_par_do_peer():
    texto = render.render_peer(peer_pni())
    assert "CL-PEER-CDN-A" not in texto
    assert "APPLY-PEER-CDN-A" not in texto
    assert "apply community community-list" not in texto


def test_pni_nao_carrega_ponto_de_aprendizado():
    # 3xxx e ponto de aprendizado, e so upstream e IX o tem
    assert "64512:30" not in render.render_peer(peer_pni())


def test_noadv_do_pni_leva_absoluta_do_tipo_e_deste_peer():
    texto = render.render_peer(peer_pni())
    corpo = texto.split("xpl community-list CL-NOADV-CDN-A")[1].split("end-list")[0]
    assert "64512:200" in corpo and "64512:202" in corpo and "64512:5200" in corpo


def test_allowlist_usa_pass():
    # PLANO.md: "AP-CDNA-ALLOWED / pass '64510'"
    texto = render.render_peer(peer_pni())
    corpo = texto.split("xpl as-path-list AP-CDN-A-ALLOWED")[1].split("end-list")[0]
    assert "pass '64510'" in corpo


def test_pni_import_recusa_quem_nao_esta_na_allowlist():
    texto = render.render_peer(peer_pni())
    import_ = texto.split("xpl route-filter PNI-CDN-A-IMPORT-V4")[1].split("end-filter")[0]
    assert "if not as-path matches-any AP-CDN-A-ALLOWED then" in import_
    assert "refuse" in import_


def test_pni_import_carimba_geografia_fixa_e_lp_200():
    texto = render.render_peer(peer_pni())
    import_ = texto.split("xpl route-filter PNI-CDN-A-IMPORT-V4")[1].split("end-filter")[0]
    assert "apply community {64512:1500, 64512:1200, 64512:2000} overwrite" in import_
    assert "apply large-community {64512:1000:64510} overwrite" in import_
    assert "apply local-preference 200" in import_
    assert [l.strip() for l in import_.splitlines() if l.strip()][-1] == "finish"


def test_pni_export_usa_a_classe_cdn():
    texto = render.render_peer(peer_pni())
    export = texto.split("xpl route-filter PNI-CDN-A-EXPORT-V4")[1].split("end-filter")[0]
    assert "64512:644" in export and "64512:643" in export and "64512:642" in export


def test_pni_export_nao_limpa_e_nao_prepende_por_peer():
    texto = render.render_peer(peer_pni())
    export = texto.split("xpl route-filter PNI-CDN-A-EXPORT-V4")[1].split("end-filter")[0]
    assert "overwrite" not in export
    assert "5PPA" not in export
    assert "APPLY-PEER" not in export


def test_pni_export_chama_export_sanity():
    texto = render.render_peer(peer_pni())
    export = texto.split("xpl route-filter PNI-CDN-A-EXPORT-V4")[1].split("end-filter")[0]
    assert "call route-filter EXPORT-SANITY" in export


def test_golden_do_pni():
    assert render.render_peer(peer_pni()) == (GOLDEN / "pni.txt").read_text(encoding="ascii")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_render.py -k "peer_pni or test_pni" -v`
Expected: FAIL com `TemplateNotFound: pni.txt.j2`

- [ ] **Step 3: Escrever `templates/pni.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% for fam in peer.familias() %}
{% set U = fam|upper %}
!- CDN via PNI: so estes ASNs podem chegar por esta sessao.
!- pass, nao origin: o que se quer e aceitar path que passe pelo ASN
!- da CDN, que costuma anunciar por tras do transito dela.
xpl as-path-list AP-{{ peer.token }}-ALLOWED
{% for asn in peer.ap_allowed %}
 pass '{{ asn }}'{{ "," if not loop.last }}
{% endfor %}
 end-list

!- um set por peer: evita cadeia de OR na condicao.
xpl community-list CL-NOADV-{{ peer.token }}
{% for c in plan.noadv("pni", peer.id) %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

xpl large-community-list LC-NOADV-{{ peer.token }}
 {{ plan.c_large(0, peer.asn) }}
 end-list

xpl route-filter PNI-{{ peer.token }}-IMPORT-{{ U }}
 call route-filter IMPORT-SANITY-{{ U }}

 !- sessao bilateral: so entra o que a CDN pode anunciar
 if not as-path matches-any AP-{{ peer.token }}-ALLOWED then
  refuse
 endif

 apply local-preference {{ peer.lp_base }}
 !- overwrite: a CDN nao escreve no nosso namespace.
 !- {{ plan.GEO_PNI }} e a geografia fixa do PNI.
 !- 2000 porque a rota vem de fora: nao e propria nem de cliente.
 apply community {{ plan.conjunto("64512:%d" % peer.origem, "64512:%d" % plan.GEO_PNI, "64512:2000") }} overwrite
 apply large-community {{ plan.conjunto(plan.c_large(1000, peer.asn)) }} overwrite

 finish
 end-filter

xpl route-filter PNI-{{ peer.token }}-EXPORT-{{ U }}
 call route-filter EXPORT-SANITY

 !- rede de seguranca do 2000, igual aos demais egress externos.
 if community matches-any {{ plan.conjunto("64512:2000") }} then
  refuse
 endif

 if community matches-any CL-NOADV-{{ peer.token }} or large-community matches-any {{ plan.conjunto(plan.c_large(0, peer.asn)) }} then
  refuse
 endif

 if community matches-any CL-ONLY-NOT-PNI then
  refuse
 endif

 !- 6CA classe {{ plan.CLASSE_6CA["pni"] }} = CDN; P2=1x, P3=2x, P4=3x.
 !- O PNI e bilateral e o ramo 5PPA funcionaria aqui, mas o exemplo do
 !- PLANO nao o traz; fica na lista de pendencias, nao como decisao.
 if community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["pni"], 4)) }} then
  apply as-path 64512 3 additive
 elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["pni"], 3)) }} then
  apply as-path 64512 2 additive
 elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["pni"], 2)) }} then
  apply as-path 64512 1 additive
 endif

 !- igual ao egress do IX: sem limpeza no fecho. A CDN nao tem
 !- community propria hoje; se tiver, entra a mesma montagem de
 !- APPLY-PEER-<T> usada no upstream.
 finish
 end-filter
{% endfor %}

bgp 64512
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "PNI-" ~ peer.token ~ "-IMPORT-" ~ U,
     "PNI-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

O `CLASSE_6CA["pni"]` é 4 (CDN), que é o que o único exemplo de PNI do PLANO usa. A tabela de classes também dá 3 para "IX privado e PNI"; se aparecer um PNI que não é CDN, ele é classe 3 e isso vira uma edição em `plan.py`. Está nas divergências.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_render.py -k "peer_pni or test_pni" -v`
Expected: PASS nos 11 testes.

- [ ] **Step 5: Gerar o golden e conferir contra o PLANO.md**

Run:
```bash
.venv/bin/python -c "
from app import render
from app.peers import Peer
p = Peer(id=20, token='CDN-A', nome='PNI CDN A', tipo='pni', asn=64510,
         descricao='PNI-CDN-A-AS64510', lp_base=200, origem=1500,
         prefixos={'v4': [], 'v6': []}, ap_allowed=['64510'],
         route_limit=10000,
         sessoes={'v4': {'local': '10.0.0.1', 'remoto': '10.0.0.2'}, 'v6': {}})
print(render.render_peer(p))
" > tests/golden/pni.txt
```

Conferir contra "Exemplo: IX e PNI / PNI de CDN": os nomes de filtro saem como `PNI-CDN-A-IMPORT-V4` onde o PLANO escreve `PNI-IMPORT-CDNA`, e a informação de origem vem do campo (`64512:1500`).

- [ ] **Step 6: Commit**

```bash
git add templates/pni.txt.j2 tests/golden/pni.txt tests/test_render.py
git commit -m "Adiciona o template de PNI"
```

---

### Task 9: O isolamento entre peers

**Files:**
- Create: `tests/test_isolamento.py`

Esta é a propriedade que o app existe para garantir. Ela não é consequência automática de ter um template por tipo: um `{% include %}` mal colocado, um global no `Environment` ou um nome de arquivo fixo quebram tudo sem quebrar nenhum golden.

**Interfaces:**
- Consumes: `render.render_peer`, `render.escrever_peer`, `render.render_base`, `peers.Peer`.
- Produces: nada.

- [ ] **Step 1: Escrever o teste**

`tests/test_isolamento.py`:

```python
"""Gerar o peer B nao pode mexer na saida do peer A."""

import pytest

from app import peers as mod
from app import render


def faz(token, ident, asn, **kw):
    base = dict(
        id=ident, token=token, nome=token, tipo="cliente", asn=asn,
        classe="transito", descricao="%s-AS%d" % (token, asn),
        lp_base=300, origem=1100, pop=2001,
        prefixos={"v4": ["45.169.%d.0/24" % ident], "v6": []},
        prepend_base=0, route_limit=50,
        sessoes={"v4": {"local": "198.51.100.1",
                        "remoto": "198.51.%d.2" % ident}, "v6": {}},
    )
    base.update(kw)
    return mod.Peer(**base)


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "OUT", tmp_path)
    monkeypatch.setattr(render, "OUT", tmp_path)
    return tmp_path


def test_gerar_b_nao_muda_a_saida_de_a(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)

    render.escrever_peer(a)
    primeira = a.arquivo().read_text(encoding="ascii")

    render.escrever_peer(b)
    render.escrever_peer(a)
    assert a.arquivo().read_text(encoding="ascii") == primeira


def test_gerar_b_nao_toca_no_mtime_de_a(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)
    render.escrever_peer(a)
    mtime = a.arquivo().stat().st_mtime_ns
    render.escrever_peer(b)
    assert a.arquivo().stat().st_mtime_ns == mtime


def test_a_saida_de_a_nao_menciona_b(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)
    render.escrever_peer(b)
    texto = render.render_peer(a)
    assert "CLIENTEB" not in texto
    assert "64501" not in texto
    assert "198.51.2.2" not in texto


def test_cada_peer_grava_no_proprio_arquivo(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)
    render.escrever_peer(a)
    render.escrever_peer(b)
    assert a.arquivo().name == "CLIENTEA-cliente.txt"
    assert b.arquivo().name == "CLIENTEB-cliente.txt"
    assert a.arquivo().read_text() != b.arquivo().read_text()


def test_o_bloco_base_nao_depende_de_peer_nenhum(out):
    vazio = render.render_base()
    render.escrever_peer(faz("CLIENTEA", 1, 64500))
    render.escrever_peer(faz("CLIENTEB", 2, 64501))
    assert render.render_base() == vazio


def test_a_ordem_de_gravacao_nao_importa(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)

    render.escrever_peer(a)
    render.escrever_peer(b)
    ab = (a.arquivo().read_text(encoding="ascii"),
          b.arquivo().read_text(encoding="ascii"))

    render.escrever_peer(b)
    render.escrever_peer(a)
    ba = (a.arquivo().read_text(encoding="ascii"),
          b.arquivo().read_text(encoding="ascii"))

    assert ab == ba


def test_os_tipos_nao_dividem_arquivo(out):
    # mesmo token, tipos diferentes: arquivos distintos, sem sobrescrita
    c = faz("PARCEIRO", 1, 64500, tipo="cliente")
    u = faz("PARCEIRO", 2, 64501, tipo="upstream", classe=None,
            aprendizado=3100, prefixos={"v4": [], "v6": []})
    render.escrever_peer(c)
    render.escrever_peer(u)
    assert c.arquivo().name == "PARCEIRO-cliente.txt"
    assert u.arquivo().name == "PARCEIRO-upstream.txt"
    assert c.arquivo().read_text(encoding="ascii") == render.render_peer(c)


def test_gerar_um_peer_de_cada_tipo_nao_mistura_nada(out):
    gente = [
        faz("CLIENTEA", 1, 64500),
        faz("UPSTREAMX", 2, 64502, tipo="upstream", classe=None,
            aprendizado=3100, prefixos={"v4": [], "v6": []}),
        faz("IXY", 3, 64503, tipo="ix", classe=None, aprendizado=3010,
            ix_id=1234, prefixos={"v4": [], "v6": []}),
        faz("PNIZ", 4, 64504, tipo="pni", classe=None,
            prefixos={"v4": [], "v6": []}, ap_allowed=["64504"]),
    ]
    for p in gente:
        render.escrever_peer(p)
    for p in gente:
        texto = p.arquivo().read_text(encoding="ascii")
        for outro in gente:
            if outro is p:
                continue
            assert outro.token not in texto, (p.token, outro.token)


def test_o_peers_yaml_guarda_os_dois_sem_perder_nada(tmp_path):
    caminho = tmp_path / "peers.yaml"
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)
    mod.gravar([a, b], caminho)
    lido = mod.carregar(caminho)
    assert [p.token for p in lido] == ["CLIENTEA", "CLIENTEB"]
    assert lido == [a, b]
```

- [ ] **Step 2: Rodar**

Run: `.venv/bin/pytest tests/test_isolamento.py -v`
Expected: PASS logo de cara se os Tasks 5 a 8 estiverem certos. **Se algum falhar, o defeito está no template ou no `render.py`, nunca no teste.** Os suspeitos, em ordem: `OUT` lido como constante em tempo de import em vez de atributo de módulo (aí o `monkeypatch` não pega), estado guardado no `Environment` do Jinja2 entre chamadas, e `peer.arquivo()` montado a partir de algo que não seja o token.

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolamento.py
git commit -m "Adiciona o teste de isolamento entre peers"
```

---

### Task 10: `prefixes.py` — bgpq4 e o cache

**Files:**
- Create: `app/prefixes.py`, `tests/test_prefixes.py`

**Interfaces:**
- Consumes: nada.
- Produces: `coletar(asn, token, familias=("v4", "v6"), forcar=False) -> dict[str, list[str]]` (família → lista de CIDRs); `do_cache(asn) -> dict | None`; `idade_horas(asn) -> float | None`; constantes `RAIZ`, `CACHE`, `TTL_HORAS`, `SERVIDOR_IRR`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_prefixes.py`:

```python
import json
import shutil
import time

import pytest

from app import prefixes


@pytest.fixture
def fake_bgpq4(tmp_path, monkeypatch):
    """Um bgpq4 de mentira no PATH, que devolve prefixos fixos."""
    binario = tmp_path / "bin" / "bgpq4"
    binario.parent.mkdir(parents=True, exist_ok=True)
    binario.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        "  *' -6 '*) echo '2001:db8::/32'; exit 0;;\n"
        "  *) echo '45.169.232.0/22'; echo '45.169.236.0/23'; exit 0;;\n"
        "esac\n",
        encoding="ascii",
    )
    binario.chmod(0o755)
    monkeypatch.setenv("PATH", str(binario.parent))
    monkeypatch.setattr(prefixes, "CACHE", tmp_path / ".cache")
    return binario


def test_coletar_le_a_saida_do_bgpq4(fake_bgpq4):
    r = prefixes.coletar(268127, "TESTOK")
    assert r["v4"] == ["45.169.232.0/22", "45.169.236.0/23"]
    assert r["v6"] == ["2001:db8::/32"]


def test_coletar_grava_o_cache(fake_bgpq4):
    prefixes.coletar(268127, "TESTOK")
    assert (prefixes.CACHE / "268127.json").exists()


def test_a_segunda_coleta_usa_o_cache(fake_bgpq4):
    prefixes.coletar(268127, "TESTOK")
    shutil.rmtree(str(fake_bgpq4.parent))       # sem bgpq4 no PATH
    assert prefixes.coletar(268127, "TESTOK")["v4"] == [
        "45.169.232.0/22", "45.169.236.0/23"]


def test_forcar_ignora_o_cache(fake_bgpq4):
    prefixes.coletar(268127, "TESTOK")
    caminho = prefixes.CACHE / "268127.json"
    dados = json.loads(caminho.read_text())
    dados["prefixos"]["v4"] = ["10.0.0.0/8"]
    caminho.write_text(json.dumps(dados))
    r = prefixes.coletar(268127, "TESTOK", forcar=True)
    assert r["v4"] == ["45.169.232.0/22", "45.169.236.0/23"]


def test_cache_vencido_e_ignorado(fake_bgpq4):
    prefixes.coletar(268127, "TESTOK")
    caminho = prefixes.CACHE / "268127.json"
    dados = json.loads(caminho.read_text())
    dados["coletado_em"] = time.time() - 25 * 3600
    caminho.write_text(json.dumps(dados))
    assert prefixes.idade_horas(268127) > 24
    assert prefixes.do_cache(268127) is None


def test_ttl_e_24_horas():
    assert prefixes.TTL_HORAS == 24


def test_o_comando_monta_os_argumentos(fake_bgpq4, monkeypatch):
    vistos = []
    monkeypatch.setattr(prefixes, "_rodar", lambda cmd: vistos.append(cmd) or [])
    prefixes.coletar(268127, "TESTOK", forcar=True)
    v4 = [c for c in vistos if "-4" in c][0]
    assert "AS268127" in v4
    assert "PL-CUST-TESTOK-V4" in v4
    assert "whois.radb.net" in v4


def test_bgpq4_ausente_e_erro_com_mensagem():
    with pytest.raises(RuntimeError):
        prefixes._rodar(["bgpq4-que-nao-existe"])
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_prefixes.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.prefixes'`

- [ ] **Step 3: Escrever `app/prefixes.py`**

```python
"""bgpq4 mais o cache em disco.

O bgpq4 e o ponto de partida, nao a palavra final: a lista sempre pode
ser editada no formulario depois da consulta. Por isso o cache guarda o
que o bgpq4 devolveu, e nao o que o usuario digitou.
"""

import ipaddress
import json
import subprocess
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "out" / ".cache"
TTL_HORAS = 24
SERVIDOR_IRR = "whois.radb.net"


def _comando(asn, token, fam):
    return ["bgpq4", "-4" if fam == "v4" else "-6", "-X", "-A",
            "-h", SERVIDOR_IRR, "-l", "PL-CUST-%s-%s" % (token, fam.upper()),
            "AS%d" % asn]


def _rodar(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError("bgpq4 nao esta no PATH: e dependencia de execucao")
    if proc.returncode != 0:
        raise RuntimeError("bgpq4 falhou: %s" % (proc.stderr.strip() or proc.returncode))
    return [l.strip() for l in proc.stdout.splitlines() if l.strip()]


def _caminho(asn):
    return CACHE / ("%d.json" % asn)


def do_cache(asn):
    """O conteudo do cache, se ele existir e nao estiver vencido."""
    caminho = _caminho(asn)
    if not caminho.exists():
        return None
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if time.time() - dados.get("coletado_em", 0) > TTL_HORAS * 3600:
        return None
    return dados.get("prefixos")


def idade_horas(asn):
    caminho = _caminho(asn)
    if not caminho.exists():
        return None
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return (time.time() - dados.get("coletado_em", 0)) / 3600.0


def _normalizar(bruto):
    """O bgpq4 devolve CIDR; o formulario trabalha em CIDR tambem."""
    saida = []
    for linha in bruto:
        linha = linha.rstrip(",").strip()
        if not linha:
            continue
        ipaddress.ip_network(linha, strict=False)
        if linha not in saida:
            saida.append(linha)
    return saida


def coletar(asn, token, familias=("v4", "v6"), forcar=False):
    if not forcar:
        em_cache = do_cache(asn)
        if em_cache is not None:
            return em_cache

    prefixos = {}
    for fam in familias:
        prefixos[fam] = _normalizar(_rodar(_comando(asn, token, fam)))

    CACHE.mkdir(parents=True, exist_ok=True)
    _caminho(asn).write_text(
        json.dumps({"asn": asn, "coletado_em": time.time(), "prefixos": prefixos},
                   indent=2),
        encoding="utf-8")
    return prefixos
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_prefixes.py -v`
Expected: PASS nos 8 testes.

- [ ] **Step 5: Verificar o bgpq4 real, se estiver instalado**

Run: `which bgpq4 && bgpq4 -4 -X -A -h whois.radb.net -l PL-TESTE AS268127 | head -3`
Expected: ou uma lista de prefixos, ou nada (não encontrado). **Não é bloqueio** — o app só precisa do binário em produção. Anote no README que ele é dependência de execução.

- [ ] **Step 6: Commit**

```bash
git add app/prefixes.py tests/test_prefixes.py
git commit -m "Adiciona a coleta de prefixos com bgpq4 e cache"
```

---

### Task 11: O app — tela única, formulário e gravação

**Files:**
- Create: `app/app.py`, `templates/pagina.html`, `templates/remover.txt.j2`, `templates/criar_lista.txt.j2`, `tests/test_app.py`

**Interfaces:**
- Consumes: tudo das tasks anteriores.
- Produces: `app` (instância `FastAPI`); rotas `GET /`, `GET /peer/novo`, `GET /peer/{token}`, `POST /peer`, `POST /peer/{token}/excluir`, `GET /saida/{token}`, `GET /saida/{token}/criar-lista`, `GET /base.txt`, `POST /bgpq4`; funções `peer_do_formulario(dados, peers, token_original=None)`, `lista()`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_app.py`:

```python
import os
import time

import pytest
from fastapi.testclient import TestClient

from app import app as mod
from app import peers as peers_mod
from app import render

CLIENTE = {
    "token": "268127", "nome": "Cliente ACME", "tipo": "cliente",
    "asn": "268127", "classe": "residencial", "descricao": "CLIENTE-AS268127",
    "lp_base": "300", "origem": "1110", "pop": "2001", "route_limit": "50",
    "bfd": "on", "graceful_restart": "on",
    "prefixos_v4": "45.169.232.0/22", "prefixos_v6": "",
    "sessao_v4_local": "198.51.100.1", "sessao_v4_remoto": "198.51.100.2",
}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(peers_mod, "PEERS_YAML", tmp_path / "peers.yaml")
    monkeypatch.setattr(peers_mod, "OUT", tmp_path / "out")
    monkeypatch.setattr(render, "OUT", tmp_path / "out")
    monkeypatch.setattr(mod, "PEERS_YAML", tmp_path / "peers.yaml")
    monkeypatch.setattr(mod, "OUT", tmp_path / "out")
    return TestClient(mod.app)


def salvar(c, dados=None, **kw):
    return c.post("/peer", data=dict(dados or CLIENTE, **kw),
                  follow_redirects=False)


def test_a_tela_comeca_vazia(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "nenhum peer" in r.text.lower()


def test_a_tela_tem_lista_e_formulario(cliente):
    # tela unica: lista a esquerda, formulario a direita
    r = cliente.get("/")
    assert 'id="lista"' in r.text
    assert 'id="formulario"' in r.text
    assert 'name="token"' in r.text
    assert 'name="asn"' in r.text


def test_salvar_cria_o_peer_e_o_arquivo(cliente, tmp_path):
    r = salvar(cliente)
    assert r.status_code == 303
    assert (tmp_path / "out" / "268127-cliente.txt").exists()
    assert "268127" in cliente.get("/").text


def test_salvar_com_erro_nao_grava_arquivo(cliente, tmp_path):
    r = salvar(cliente, asn="0")
    assert r.status_code == 200
    assert "ASN reservado" in r.text
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()


def test_desmarcar_bfd_chega_no_yaml(cliente, tmp_path):
    dados = dict(CLIENTE)
    dados.pop("bfd")
    salvar(cliente, dados)
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert lido[0].bfd is False
    assert lido[0].graceful_restart is True


def test_o_formulario_de_um_tipo_novo_vem_com_os_defaults_da_tabela(cliente):
    r = cliente.get("/peer/novo?tipo=upstream")
    assert r.status_code == 200
    assert 'value="1500000"' in r.text          # ROUTE_LIMIT["upstream"]
    assert 'name="timer_keepalive"' in r.text


def test_o_painel_de_saida_tem_as_duas_abas(cliente):
    salvar(cliente)
    r = cliente.get("/saida/268127")
    assert r.status_code == 200
    assert 'data-aba="criar"' in r.text
    assert 'data-aba="remover"' in r.text


def test_a_aba_de_criacao_nao_leva_undo(cliente):
    salvar(cliente)
    r = cliente.get("/saida/268127")
    criar = r.text.split('data-aba="criar"')[1].split('data-aba="remover"')[0]
    assert "undo " not in criar


def test_o_quadro_ao_criar_o_peer_mostra_a_lista_vazia(cliente):
    salvar(cliente)
    r = cliente.get("/saida/268127/criar-lista")
    assert r.status_code == 200
    assert "xpl community-list CL-PEER-268127" in r.text
    assert "APPLY-PEER-268127" in r.text
    assert r.text.isascii()


def test_editar_existente_nao_duplica(cliente, tmp_path):
    salvar(cliente)
    salvar(cliente, nome="editado")
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert len(lido) == 1
    assert lido[0].nome == "editado"
    assert lido[0].id == 0


def test_excluir_tira_da_lista_e_apaga_o_arquivo(cliente, tmp_path):
    salvar(cliente)
    arquivo = tmp_path / "out" / "268127-cliente.txt"
    assert arquivo.exists()
    cliente.post("/peer/268127/excluir", data={"confirmado": "sim"},
                 follow_redirects=False)
    assert not arquivo.exists()
    assert peers_mod.carregar(tmp_path / "peers.yaml") == []


def test_excluir_sem_confirmar_nao_apaga(cliente, tmp_path):
    salvar(cliente)
    r = cliente.post("/peer/268127/excluir", data={}, follow_redirects=False)
    assert r.status_code == 200
    assert (tmp_path / "out" / "268127-cliente.txt").exists()
    assert len(peers_mod.carregar(tmp_path / "peers.yaml")) == 1


def test_o_bloco_de_remocao_deixa_a_community_list_do_peer_comentada(cliente):
    # CL-PEER-<T> carrega valor posto a mao: o undo dela sai comentado
    salvar(cliente)
    r = cliente.get("/saida/268127")
    remover = r.text.split('data-aba="remover"')[1]
    assert "!- undo xpl community-list CL-PEER-268127" in remover
    assert "\nundo xpl community-list CL-PEER-268127" not in remover


def test_o_bloco_de_remocao_poe_o_undo_peer_antes_dos_undo_xpl(cliente):
    salvar(cliente)
    r = cliente.get("/saida/268127")
    remover = r.text.split('data-aba="remover"')[1]
    assert remover.index("undo peer") < remover.index("undo xpl")
    assert "APPLY-PEER-268127" in remover


def test_o_cliente_nao_leva_undo_de_noadv_por_peer(cliente):
    # o egress de cliente usa a CL-NOADV-CUST compartilhada
    salvar(cliente)
    r = cliente.get("/saida/268127")
    remover = r.text.split('data-aba="remover"')[1]
    assert "undo xpl community-list CL-NOADV-268127" not in remover


def test_gerar_o_peer_b_nao_muda_a_saida_do_a(cliente, tmp_path):
    a = dict(CLIENTE, token="CLIENTEA", asn="64500", descricao="C-AS64500",
             classe="transito", origem="1100", prefixos_v4="45.169.0.0/24",
             sessao_v4_remoto="198.51.100.10")
    b = dict(a, token="CLIENTEB", asn="64501", descricao="C-AS64501",
             prefixos_v4="45.169.1.0/24", sessao_v4_remoto="198.51.100.11")
    salvar(cliente, a)
    primeira = (tmp_path / "out" / "CLIENTEA-cliente.txt").read_text(encoding="ascii")
    salvar(cliente, b)
    salvar(cliente, a)
    assert (tmp_path / "out" / "CLIENTEA-cliente.txt").read_text(encoding="ascii") == primeira


def test_a_tela_avisa_que_o_base_nao_existe(cliente):
    assert "bloco base" in cliente.get("/").text


def test_a_tela_avisa_quando_o_base_esta_velho(cliente, tmp_path):
    salvar(cliente)
    base = tmp_path / "out" / "_base.txt"
    base.write_text("x", encoding="ascii")
    velho = time.time() - 3600
    os.utime(base, (velho, velho))
    assert "desatualizado" in cliente.get("/").text


def test_a_tela_nao_avisa_com_o_base_em_dia(cliente):
    salvar(cliente)
    render.escrever_base()
    assert "desatualizado" not in cliente.get("/").text


def test_download_do_bloco_base(cliente):
    r = cliente.get("/base.txt")
    assert r.status_code == 200
    assert "IMPORT-SANITY-V4" in r.text
    assert r.text.isascii()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/pytest tests/test_app.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.app'`

- [ ] **Step 3: Escrever `templates/remover.txt.j2`**

A ordem é a que o VRP aceita: o `undo peer` vem antes dos `undo xpl`, porque ele recusa apagar objeto ainda referenciado por uma sessão.

```jinja
!- gerado por bgpgen - nao editar a mao
!- remocao do peer {{ peer.id }} - {{ peer.tipo }} - AS{{ peer.asn }}
!- cole so isto para excluir a sessao do equipamento

{% for fam in peer.familias() %}
{% set s = peer.sessoes[fam] %}
undo peer {{ s.remoto }}
{% endfor %}

{% for fam in peer.familias() %}
{% set U = fam|upper %}
{% set kw = "ipv6-prefix-list" if fam == "v6" else "ip-prefix-list" %}
{% if peer.tipo == "cliente" %}
undo xpl route-filter CUST-{{ peer.token }}-EXPORT-{{ U }}
undo xpl route-filter CUST-{{ peer.token }}-IMPORT-{{ U }}
undo xpl as-path-list AP-CUST-{{ peer.token }}
undo xpl {{ kw }} PL-CUST-{{ peer.token }}-BH-{{ U }}
undo xpl {{ kw }} PL-CUST-{{ peer.token }}-{{ U }}
{% elif peer.tipo == "upstream" %}
undo xpl route-filter UP-{{ peer.token }}-EXPORT-{{ U }}
undo xpl route-filter UP-{{ peer.token }}-IMPORT-{{ U }}
undo xpl as-path-list AP-BLOCK-{{ peer.token }}
undo xpl as-path-list AP-TE-PREFER-{{ peer.token }}
undo xpl {{ kw }} PL-TE-PREFER-{{ peer.token }}-{{ U }}
undo xpl community-list CL-5PPA-{{ "%02d"|format(peer.id) }}
undo xpl large-community-list LC-5PPA-{{ peer.token }}
undo xpl large-community-list LC-PREP1-{{ peer.token }}
undo xpl large-community-list LC-PREP2-{{ peer.token }}
undo xpl large-community-list LC-PREP3-{{ peer.token }}
{% elif peer.tipo == "ix" %}
undo xpl route-filter IX-{{ peer.token }}-EXPORT-{{ U }}
undo xpl route-filter IX-{{ peer.token }}-IMPORT-{{ U }}
undo xpl as-path-list AP-IX-{{ peer.token }}
{% elif peer.tipo == "pni" %}
undo xpl route-filter PNI-{{ peer.token }}-EXPORT-{{ U }}
undo xpl route-filter PNI-{{ peer.token }}-IMPORT-{{ U }}
undo xpl as-path-list AP-{{ peer.token }}-ALLOWED
{% endif %}
{% endfor %}

{% if peer.tipo in ("cliente", "upstream") %}
undo xpl route-filter APPLY-PEER-{{ peer.token }}
{% endif %}
{% if peer.tipo != "cliente" %}
undo xpl large-community-list LC-NOADV-{{ peer.token }}
undo xpl community-list CL-NOADV-{{ peer.token }}
{% endif %}

!- ATENCAO: CL-PEER-{{ peer.token }} carrega valor posto a mao no
!- equipamento. Apagar e perder o trabalho, e o gerador nao tem como
!- reproduzir. Descomente so se tiver certeza.
!- undo xpl community-list CL-PEER-{{ peer.token }}
```

O `CL-NOADV-<T>` não existe no cliente: o egress dele usa a `CL-NOADV-CUST` compartilhada, que pertence ao bloco base e não se apaga ao remover um peer. Daí o `{% if peer.tipo != "cliente" %}`.

- [ ] **Step 4: Escrever `templates/criar_lista.txt.j2`**

```jinja
!- gerado por bgpgen - nao editar a mao
!- ao criar o peer {{ peer.id }} - {{ peer.tipo }} - AS{{ peer.asn }}
!- Cole este par UMA VEZ, na primeira vez que a sessao subir.
!- O gerador nao volta a emitir estas linhas: reaplicar o bloco do peer
!- mexe so nos filtros e nao tem como zerar o que voce escrever aqui.

xpl community-list CL-PEER-{{ peer.token }}
 end-list

xpl route-filter APPLY-PEER-{{ peer.token }}
 apply community community-list CL-PEER-{{ peer.token }} additive
 break
 end-filter
```

- [ ] **Step 5: Escrever `app/app.py`**

```python
"""Rotas do app.

Tela unica: a lista de peers a esquerda, o formulario a direita, e a
saida abaixo depois de salvar. Sem banco: o estado e o peers.yaml.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import plan, prefixes, render, validate
from app import peers as peers_mod
from app.peers import Peer

RAIZ = Path(__file__).resolve().parent.parent
PEERS_YAML = peers_mod.PEERS_YAML
OUT = peers_mod.OUT

app = FastAPI(title="bgpgen")

templates = Jinja2Templates(directory=str(render.TEMPLATES))
templates.env.globals["plan"] = plan
templates.env.trim_blocks = True
templates.env.lstrip_blocks = True

CAMPOS_INT = ("asn", "id", "lp_base", "origem", "pop", "aprendizado",
              "ix_id", "prepend_base", "route_limit",
              "timer_keepalive", "timer_hold")


def lista():
    return peers_mod.carregar(PEERS_YAML)


def _texto(dados, nome, padrao=""):
    return (dados.get(nome) or padrao).strip()


def _linhas(dados, nome):
    return [l.strip() for l in _texto(dados, nome).splitlines() if l.strip()]


def _sessoes(dados):
    sessoes = {}
    for fam in plan.FAMILIAS:
        local = _texto(dados, "sessao_%s_local" % fam)
        remoto = _texto(dados, "sessao_%s_remoto" % fam)
        sessoes[fam] = {"local": local, "remoto": remoto} if (local or remoto) else {}
    return sessoes


def peer_do_formulario(dados, peers, token_original=None):
    """Formulario achatado -> Peer. Devolve (peer, erros_de_campo).

    O formulario usa nomes planos (prefixos_v4, sessao_v4_remoto) porque
    e isso que o htmx manda; o Peer e aninhado por familia.
    """
    tipo = _texto(dados, "tipo", "cliente")
    anterior = peers_mod.achar(peers, token_original) if token_original else None

    erros = []
    valores = {}
    for nome in CAMPOS_INT:
        bruto = _texto(dados, nome)
        if not bruto:
            valores[nome] = None
            continue
        try:
            valores[nome] = int(bruto)
        except ValueError:
            erros.append(validate.Erro(nome, "valor numerico invalido"))
            valores[nome] = None

    k, h = plan.TIMER_PADRAO.get(tipo, (None, None))
    # id, lp_base e route_limit caem no default da tabela quando em branco
    ident = valores.get("id")
    if ident is None:
        ident = anterior.id if anterior else peers_mod.proximo_id(peers)
    lp = valores.get("lp_base")
    if lp is None:
        lp = plan.LP_BASE.get(tipo, 300)
    limite = valores.get("route_limit")
    if limite is None:
        limite = plan.ROUTE_LIMIT.get(tipo, 50)

    peer = Peer(
        id=ident,
        token=_texto(dados, "token"),
        nome=_texto(dados, "nome"),
        tipo=tipo,
        asn=valores.get("asn") or 0,
        classe=_texto(dados, "classe") or None,
        descricao=_texto(dados, "descricao"),
        lp_base=lp,
        origem=valores.get("origem"),
        pop=valores.get("pop"),
        aprendizado=valores.get("aprendizado"),
        ix_id=valores.get("ix_id"),
        prefixos={f: _linhas(dados, "prefixos_%s" % f) for f in plan.FAMILIAS},
        te_prefixos={f: _linhas(dados, "te_prefixos_%s" % f) for f in plan.FAMILIAS},
        ap_block=_linhas(dados, "ap_block"),
        ap_te=_linhas(dados, "ap_te"),
        ap_allowed=_linhas(dados, "ap_allowed"),
        ap_prefer=_linhas(dados, "ap_prefer"),
        bfd=dados.get("bfd") == "on",
        graceful_restart=dados.get("graceful_restart") == "on",
        timer_keepalive=valores.get("timer_keepalive") or k,
        timer_hold=valores.get("timer_hold") or h,
        prepend_base=valores.get("prepend_base") or 0,
        route_limit=limite,
        sessoes=_sessoes(dados),
        bh_upstream=_texto(dados, "bh_upstream"),
    )
    return peer, erros


def _base_desatualizado(peers):
    """True quando um peer foi gravado depois do bloco base."""
    base = OUT / "_base.txt"
    if not base.exists():
        return False        # ausente tem aviso proprio
    quando = base.stat().st_mtime
    return any(p.arquivo().exists() and p.arquivo().stat().st_mtime > quando
               for p in peers)


def _contexto(request, peer=None, erros=None, avisos=None):
    peers = lista()
    return {
        "request": request,
        "peers": peers,
        "peer": peer,
        "erros": validate.erros_para_dict(erros or []),
        "avisos": avisos or [],
        "saida": None,
        "saida_remover": None,
        "tipos": plan.TIPOS,
        "LP_BASE": plan.LP_BASE,
        "ROUTE_LIMIT": plan.ROUTE_LIMIT,
        "ROUTE_LIMIT_EXEMPLO": plan.ROUTE_LIMIT_EXEMPLO,
        "TIMER_PADRAO": plan.TIMER_PADRAO,
        "CLASSES_CLIENTE": plan.CLASSES_CLIENTE,
        "ORIGEM_CLASSE": plan.ORIGEM_CLASSE,
        "POP_MIN": plan.POP_MIN,
        "POP_MAX": plan.POP_MAX,
        "APRENDIZADO_MIN": plan.APRENDIZADO_MIN,
        "APRENDIZADO_MAX": plan.APRENDIZADO_MAX,
        "base_existe": (OUT / "_base.txt").exists(),
        "base_desatualizado": _base_desatualizado(peers),
    }


@app.get("/", response_class=HTMLResponse)
def raiz(request: Request):
    return templates.TemplateResponse("pagina.html", _contexto(request))


@app.get("/peer/novo", response_class=HTMLResponse)
def novo(request: Request, tipo: str = "cliente"):
    # o formulario em branco ja vem com os defaults da tabela do plano
    if tipo not in plan.TIPOS:
        tipo = "cliente"
    k, h = plan.TIMER_PADRAO.get(tipo, (None, None))
    peer = Peer(tipo=tipo, id=peers_mod.proximo_id(lista()),
                lp_base=plan.LP_BASE.get(tipo, 300),
                route_limit=plan.ROUTE_LIMIT.get(tipo, 50),
                timer_keepalive=k, timer_hold=h)
    return templates.TemplateResponse("pagina.html", _contexto(request, peer=peer))


@app.get("/peer/{token}", response_class=HTMLResponse)
def editar(request: Request, token: str):
    peer = peers_mod.achar(lista(), token)
    if peer is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("pagina.html", _contexto(request, peer=peer))


@app.post("/peer", response_class=HTMLResponse)
async def salvar(request: Request):
    dados = dict(await request.form())
    peers = lista()
    original = _texto(dados, "token_original") or None
    peer, erros = peer_do_formulario(dados, peers, original)

    outros = [p for p in peers if p.token != (original or peer.token)]
    erros = erros + validate.validar(peer, outros, editando=original is not None)
    if erros:
        return templates.TemplateResponse(
            "pagina.html",
            _contexto(request, peer=peer, erros=erros,
                      avisos=validate.avisos(peer, outros)),
            status_code=200)

    antigo = peers_mod.achar(peers, original) if original else None
    if antigo is None:
        peers.append(peer)
    else:
        peers[peers.index(antigo)] = peer
    if original and original != peer.token:
        (OUT / ("%s-%s.txt" % (original, peer.tipo))).unlink(missing_ok=True)

    peers_mod.gravar(peers, PEERS_YAML)
    render.escrever_peer(peer)
    return RedirectResponse("/saida/%s" % peer.token, status_code=303)


@app.post("/peer/{token}/excluir", response_class=HTMLResponse)
async def excluir(request: Request, token: str):
    dados = dict(await request.form())
    peers = lista()
    peer = peers_mod.achar(peers, token)
    if peer is None:
        return RedirectResponse("/", status_code=303)
    if dados.get("confirmado") != "sim":
        return templates.TemplateResponse(
            "pagina.html",
            _contexto(request, peer=peer,
                      erros=[validate.Erro("confirmado",
                                           "confirme para excluir o peer")]),
            status_code=200)
    peer.arquivo().unlink(missing_ok=True)
    peers.remove(peer)
    peers_mod.gravar(peers, PEERS_YAML)
    return RedirectResponse("/", status_code=303)


@app.get("/saida/{token}", response_class=HTMLResponse)
def saida(request: Request, token: str):
    peer = peers_mod.achar(lista(), token)
    if peer is None:
        return RedirectResponse("/", status_code=303)
    contexto = _contexto(request, peer=peer)
    contexto["saida"] = render.render_peer(peer)
    contexto["saida_remover"] = render.render_remove(peer)
    return templates.TemplateResponse("pagina.html", contexto)


@app.get("/saida/{token}/criar-lista", response_class=HTMLResponse)
def criar_lista(request: Request, token: str):
    peer = peers_mod.achar(lista(), token)
    if peer is None:
        return RedirectResponse("/", status_code=303)
    contexto = _contexto(request, peer=peer)
    contexto["saida"] = render.render_criar_lista(peer)
    return templates.TemplateResponse("pagina.html", contexto)


@app.get("/base.txt", response_class=HTMLResponse)
def baixar_base():
    return HTMLResponse(render.render_base(), media_type="text/plain")


@app.post("/bgpq4", response_class=HTMLResponse)
def consultar_bgpq4(asn: int = 0, token: str = "", forcar: int = 0):
    try:
        coleta = prefixes.coletar(asn, token or str(asn), forcar=bool(forcar))
    except (RuntimeError, ValueError) as exc:
        return HTMLResponse("<p class='erro'>%s</p>" % exc, status_code=200)
    pedacos = []
    for fam in plan.FAMILIAS:
        pedacos.append(
            "<label>%s <textarea name='prefixos_%s'>%s</textarea></label>"
            % (fam, fam, "\n".join(coleta.get(fam) or [])))
    return HTMLResponse("".join(pedacos))
```

- [ ] **Step 6: Escrever `templates/pagina.html`**

```html
<!doctype html>
<html lang="pt-BR">
<head>
 <meta charset="utf-8">
 <title>bgpgen - sessoes BGP do AS64512</title>
 <script src="https://unpkg.com/htmx.org@1.9.12"></script>
 <style>
  body { font: 13px/1.5 ui-monospace, monospace; margin: 0; }
  .linha { display: flex; gap: 16px; padding: 12px; align-items: flex-start; }
  #lista { flex: 0 0 300px; }
  #formulario { flex: 1 1 auto; }
  .erro { color: #a00; font-weight: bold; }
  .aviso { color: #a60; }
  table { border-collapse: collapse; width: 100%; }
  td, th { border: 1px solid #ccc; padding: 2px 6px; text-align: left; }
  label { display: block; margin-top: 6px; }
  textarea { width: 100%; height: 90px; }
  pre { background: #f6f6f6; padding: 8px; overflow: auto; }
  [data-aba] { padding: 4px 10px; border: 1px solid #ccc; }
 </style>
</head>
<body>
<div class="linha">
 <div id="lista">
  <h2>Peers</h2>
  {% if peers %}
  <table>
   <tr><th>ID</th><th>token</th><th>tipo</th><th>ASN</th></tr>
   {% for p in peers %}
   <tr>
    <td>{{ "%02d"|format(p.id) }}</td>
    <td><a href="/peer/{{ p.token }}">{{ p.token }}</a></td>
    <td>{{ p.tipo }}</td>
    <td>{{ p.asn }}</td>
   </tr>
   {% endfor %}
  </table>
  {% else %}
  <p>nenhum peer cadastrado</p>
  {% endif %}
  <p><a href="/peer/novo">criar peer</a></p>
  <p>
   {% if base_existe %}bloco base em out/_base.txt{% else %}
   <span class="aviso">bloco base ainda nao gerado</span>{% endif %}
   - <a href="/base.txt">baixar</a>
   {% if base_desatualizado %}
   <br><span class="aviso">bloco base desatualizado: gere de novo e cole
   antes dos blocos de peer</span>
   {% endif %}
  </p>
 </div>

 <div id="formulario">
  <h2>{{ "editar" if peer and peer.token else "novo peer" }}</h2>
  {% if erros %}<p class="erro">{{ erros.values()|join("; ") }}</p>{% endif %}
  {% for a in avisos %}<p class="aviso">{{ a.mensagem }}</p>{% endfor %}
  <form method="post" action="/peer">
   {% if peer and peer.token %}
   <input type="hidden" name="token_original" value="{{ peer.token }}">
   {% endif %}
   <label>token <input name="token" value="{{ peer.token if peer else '' }}"></label>
   <label>nome <input name="nome" value="{{ peer.nome if peer else '' }}"></label>
   <label>tipo
    <select name="tipo">
     {% for t in tipos %}
     <option value="{{ t }}"{{ " selected" if peer and peer.tipo == t }}>{{ t }}</option>
     {% endfor %}
    </select>
   </label>
   <label>ASN <input name="asn" value="{{ peer.asn if peer else '' }}"></label>
   <label>descricao <input name="descricao" value="{{ peer.descricao if peer else '' }}"></label>
   <label>classe
    <select name="classe">
     <option value="">-</option>
     {% for c in CLASSES_CLIENTE %}
     <option value="{{ c }}"{{ " selected" if peer and peer.classe == c }}>
      {{ c }} - 64512:{{ ORIGEM_CLASSE[c] }}</option>
     {% endfor %}
    </select>
   </label>
   <label>local-preference <input name="lp_base" value="{{ peer.lp_base if peer else '' }}"></label>
   <label>origem (1xxx) <input name="origem" value="{{ peer.origem or '' }}"></label>
   <label>POP ({{ POP_MIN }}-{{ POP_MAX }}) <input name="pop" value="{{ peer.pop or '' }}"></label>
   <label>ponto de aprendizado ({{ APRENDIZADO_MIN }}-{{ APRENDIZADO_MAX }})
    <input name="aprendizado" value="{{ peer.aprendizado or '' }}"></label>
   <label>ID do IX no PeeringDB <input name="ix_id" value="{{ peer.ix_id or '' }}"></label>
   <label>route-limit <input name="route_limit" value="{{ peer.route_limit if peer else '' }}">
    <small>tabela do plano: {{ ROUTE_LIMIT }};
    exemplo de aplicacao: {{ ROUTE_LIMIT_EXEMPLO }}</small></label>
   <label>prepend base, numero de prepends, 0 desliga
    <input name="prepend_base" value="{{ peer.prepend_base if peer else 0 }}"></label>
   <label>timer keepalive <input name="timer_keepalive"
    value="{{ peer.timer_keepalive or '' }}"></label>
   <label>timer hold <input name="timer_hold" value="{{ peer.timer_hold or '' }}">
    <small>em branco = default do equipamento</small></label>
   <label><input type="checkbox" name="bfd"{{ " checked" if not peer or peer.bfd }}> bfd enable</label>
   <label><input type="checkbox" name="graceful_restart"{{ " checked" if not peer or peer.graceful_restart }}> capability-advertise graceful-restart</label>
   <label>community de blackhole deste upstream, so no tipo upstream
    <input name="bh_upstream" value="{{ peer.bh_upstream if peer else '' }}"></label>

   <h3>prefixos anunciados, um por linha</h3>
   <label>v4 <textarea name="prefixos_v4">{{ peer.prefixos['v4']|join("\n") if peer else "" }}</textarea></label>
   <label>v6 <textarea name="prefixos_v6">{{ peer.prefixos['v6']|join("\n") if peer else "" }}</textarea></label>

   <h3>prefixos de excecao de TE, um por linha</h3>
   <label>v4 <textarea name="te_prefixos_v4">{{ peer.te_prefixos['v4']|join("\n") if peer else "" }}</textarea></label>
   <label>v6 <textarea name="te_prefixos_v6">{{ peer.te_prefixos['v6']|join("\n") if peer else "" }}</textarea></label>

   <h3>AS-path, um por linha</h3>
   <label>ASNs bloqueados (upstream) <textarea name="ap_block">{{ peer.ap_block|join("\n") if peer else "" }}</textarea></label>
   <label>ASNs com TE preferencial (upstream) <textarea name="ap_te">{{ peer.ap_te|join("\n") if peer else "" }}</textarea></label>
   <label>ASNs permitidos (PNI) <textarea name="ap_allowed">{{ peer.ap_allowed|join("\n") if peer else "" }}</textarea></label>
   <label>membros com LP 195 (IX) <textarea name="ap_prefer">{{ peer.ap_prefer|join("\n") if peer else "" }}</textarea></label>

   <h3>sessoes</h3>
   <label>v4 local <input name="sessao_v4_local" value="{{ peer.sessoes['v4'].get('local','') if peer else '' }}"></label>
   <label>v4 remoto <input name="sessao_v4_remoto" value="{{ peer.sessoes['v4'].get('remoto','') if peer else '' }}"></label>
   <label>v6 local <input name="sessao_v6_local" value="{{ peer.sessoes['v6'].get('local','') if peer else '' }}"></label>
   <label>v6 remoto <input name="sessao_v6_remoto" value="{{ peer.sessoes['v6'].get('remoto','') if peer else '' }}"></label>

   <p><button type="submit">salvar</button>
    {% if peer and peer.token %}
    <button type="submit" formaction="/peer/{{ peer.token }}/excluir">excluir</button>
    <label><input type="checkbox" name="confirmado" value="sim"> confirmar exclusao</label>
    {% endif %}
   </p>
  </form>
 </div>
</div>

{% if peer and peer.token %}
<div id="saida">
 <h2>saida de {{ peer.token }}</h2>
 <p>
  <a href="/saida/{{ peer.token }}">bloco do peer</a> |
  <a href="/saida/{{ peer.token }}/criar-lista">ao criar o peer</a> |
  <a href="/base.txt">bloco base</a>
 </p>
{% if saida %}
 <pre data-aba="criar">{{ saida }}</pre>
{% endif %}
{% if saida_remover %}
 <pre data-aba="remover">{{ saida_remover }}</pre>
{% endif %}
</div>
{% endif %}
</body>
</html>
```

- [ ] **Step 7: Rodar e ver passar**

Run: `.venv/bin/pytest tests/test_app.py -v`
Expected: PASS nos 20 testes.

- [ ] **Step 8: Subir o app e conferir na mão**

Run: `.venv/bin/uvicorn app.app:app --reload --port 8000`
Conferir: criar um cliente de exemplo, ver a saída nas duas abas, editar o mesmo peer e ver que a lista não duplicou, excluir e ver o bloco de `undo`.

- [ ] **Step 9: Commit**

```bash
git add app/app.py templates/pagina.html templates/remover.txt.j2 templates/criar_lista.txt.j2 tests/test_app.py
git commit -m "Adiciona a tela, o formulario e o painel de saida"
```

---

### Task 12: `README.md`

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: nada.
- Produces: nada.

Esta task é só documentação. O aviso de bloco base desatualizado e a rota `GET /base.txt` já entraram no Task 11, com os testes que os fixam.

- [ ] **Step 1: Escrever o `README.md`**

Cinco seções curtas:

- **O que é.** Gera o bloco XPL de uma sessão BGP do AS64512 a partir de um formulário, mais um bloco base com os sets e filtros compartilhados.
- **O que não faz.** Não fala com o equipamento, não decide política, não guarda o conteúdo da `CL-PEER-<T>` (essa lista vive só no roteador, editada à mão), não importa nada do `PLANO.md`.
- **Como subir.**
  ```bash
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
  .venv/bin/uvicorn app.app:app --port 8000
  ```
  O `bgpq4` é dependência de execução e precisa estar no `PATH`; sem ele o botão de consultar prefixos devolve erro e o resto funciona.
- **Ordem de colagem no F1A.** `out/_base.txt` primeiro (uma vez), depois o bloco de cada peer, e a `CL-PEER-<T>` do quadro "ao criar o peer" na primeira vez que aquela sessão subir.
- **O que confirmar no equipamento antes do primeiro peer.** Se `apply community` aceita lista nomeada e com que sintaxe; se uma `community-list` sem membro é aceita; se um filtro que declara `($prepend_base)` na assinatura aceita ser chamado sem os parênteses. O caso do `apply as-path <asn> 0 additive` já está resolvido (`PLANO.md` registra erro no equipamento, mínimo 1), então a escala do prepend de engenharia é 1 a 6 e a sessão sem prepend é a que não recebe o argumento.

- [ ] **Step 2: Rodar a suíte inteira**

Run: `.venv/bin/pytest -v`
Expected: PASS em tudo.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Adiciona o README"
```

---

## Conferência final

Antes de considerar o plano executado:

- [ ] `.venv/bin/pytest` passa inteiro
- [ ] os goldens e o bloco base são ASCII puro:
      `.venv/bin/python -c "import pathlib; [print(p.name, p.read_text(encoding='ascii').isascii()) for p in pathlib.Path('tests/golden').iterdir()]"`
- [ ] nenhum `$` de interpolação de shell em nenhuma saída gerada (o `^$` de expressão regular nos sets é XPL legítimo e fica)
- [ ] nenhum `apply community {...} overwrite` em egress, salvo o ramo de blackhole do export de upstream
- [ ] `call route-filter APPLY-PEER-<T>` é a última linha antes do `finish` no import de cliente e no export de upstream
- [ ] `CL-PEER-<T>` não aparece em nenhum bloco de peer gerado
- [ ] a `CL-PEER-<T>` aparece no quadro "ao criar o peer" e, comentada, no bloco de remoção, só nos tipos cliente e upstream
- [ ] nenhum ASN, ID ou prefixo de exemplo do PLANO.md virou constante em `app/plan.py`
- [ ] os goldens batem com os exemplos de aplicação do PLANO.md, incluindo as linhas de sessão do bloco `bgp`
- [ ] `out/_base.txt` colado antes dos blocos de peer, na ordem do README
- [ ] `peers.yaml` versionado; `out/*.txt` e `out/.cache/` ignorados

## O que este plano deliberadamente não faz

- A originação dos próprios prefixos (`network ... route-policy ORIGIN-*`). É por prefixo, não por peer, e a cláusula `network` não aceita `route-filter`.
- A checagem espelhada do `64512:4:<ASN>` nos egress que não são o do próprio ASN. Depende de confirmar o coringa em large-community-list no equipamento.
- GSHUT em upstream, IX e PNI. Hoje só o `APPLY-CUSTOMER-LP` lê o `65535:0`.
- O prepend por peer no egress de PNI. O exemplo do PLANO não traz o ramo.
- A seção de scrubbing center do PLANO, que tem ponto em aberto sobre `apply preference` e `apply preferred-value`.
- Teste de UI.

## Divergências que este plano resolve

Onde o PLANO.md e o spec discordam, ou onde o PLANO não mostra o suficiente para copiar. Cada uma está marcada no task correspondente. O critério geral: vale o spec quando o assunto é decisão de desenho, e vale o PLANO.md quando o assunto é nome de objeto e corpo de lista.

1. **Token com hífen.** O spec diz `[A-Z0-9]` e, duas seções antes, dá `IX-SP` como exemplo de apelido. As duas não fecham. Implementado `^[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?$`, que aceita `IX-SP` sem aceitar `-IX` nem `IX-`, com teto de 12 caracteres (Task 3).
2. **`PL-TE-PREFER` sem o token e sem a família.** O spec lista a prefix-list de exceção de TE sem o `<T>`, e o PLANO.md nomeia `PL-TE-PREFER-14840`, também sem família. Sem o token, dois upstreams dividiriam a mesma prefix-list e isso quebra o isolamento. Implementado `PL-TE-PREFER-<T>-<fam>` (Task 6).
3. **`CL-NOADV-UP1` no exemplo de upstream.** O PLANO escreve `CL-NOADV-UP1`, sem o token; os exemplos de IX e PNI escrevem `CL-NOADV-IX-SP` e `CL-NOADV-PNI-CDNA`, com o token; e o spec pede `CL-NOADV-<T>` nos três. Implementado `CL-NOADV-<T>` para os três, que é o que o spec decide e o que dois dos três exemplos do PLANO mostram (Task 6).
4. **`AP-IX-CDN-A`.** O PLANO nomeia a lista de membro preferido do IX com o nome da CDN do exemplo. A cláusula é `peer-is` e o corpo sai igual ao do PLANO; só o nome muda, para `AP-IX-<T>`, pela mesma razão do item 3 (Task 7).
5. **`AP-CDNA-ALLOWED` e os filtros `PNI-IMPORT-CDNA` / `PNI-EXPORT-CDNA`.** O PLANO nomeia a allowlist do PNI com `CDN` no lugar do token e sem prefixo de tipo, e nomeia os filtros com o sufixo `CDNA`. O gerador emite `AP-<T>-ALLOWED` e `PNI-<T>-IMPORT-<FAM>` / `PNI-<T>-EXPORT-<FAM>` para que o nome carregue o token e o eixo de família, que é o que o isolamento e a dupla pilha exigem (Task 8). O corpo da lista sai igual ao do PLANO: `pass '<asn>'`, e não `origin`, porque a CDN costuma anunciar por trás do próprio trânsito.
6. **Lista vazia.** O PLANO não mostra o que `matches-any` faz contra uma lista sem membros, e o spec pede que lista de TE em branco não quebre o filtro. Implementado: lista de TE vazia não emite nem a lista nem o ramo; IX sem membro preferido emite `apply local-preference` direto, sem o `if` (Tasks 6 e 7).
7. **Campo `ix_id`.** O spec não lista o campo no formulário, mas o import de IX do PLANO precisa de `64512:1001:<id do PeeringDB>`, e o próprio PLANO avisa que o `9999` do exemplo é placeholder. Implementado como campo obrigatório para o tipo IX (Tasks 3 e 7).
8. **Token de IX no nome do filtro.** Com o token `IX-SP`, o filtro sai `IX-IX-SP-IMPORT-V4`. Encurtar para `IX-SP-IMPORT-V4` faria dois IXs colidirem se um deles se chamasse `SP`. O prefixo de tipo é do spec, o token é do usuário, e o nome feio é o preço de não ter colisão (Task 7).
9. **Ordem das linhas de sessão no bloco `bgp`.** O PLANO põe `bfd` antes de `capability-advertise graceful-restart` no cliente e o inverso no upstream. São comandos de peer independentes, então a ordem é do gerador; o golden fixa uma (Task 5).
10. **`route-limit` do upstream.** A tabela do PLANO diz `1500000`, o exemplo de aplicação diz `1100000`. Fica o da tabela como default e o do exemplo como nota no formulário, que é o que o spec decide (Tasks 1 e 3).
11. **Classe 6CA do PNI.** A tabela de classes do PLANO dá `3` para "IX privado e PNI" e `4` para "CDN". O único exemplo de PNI do documento é um PNI de CDN, e o egress dele usa `64512:644/643/642`, ou seja, classe 4. O gerador segue o exemplo. Um PNI que não seja CDN é classe 3 e isso vira uma edição em `plan.py` (Task 8).
12. **`AP-LOCAL-ORIGIN` e `AP-PATH-TOO-LONG` no bloco base.** O PLANO os põe na seção de AS-path auxiliares junto com as listas por peer. Como não têm token, moram no bloco base (Task 4).

Se a leitura estiver errada em alguma, corrija o spec primeiro e o plano acompanha.

## Pendências que o plano não fecha

Coisas que o PLANO.md lista como "falta confirmar" e que o código não resolve:

- Se `apply community` aceita lista nomeada, e se a sintaxe leva `community-list` no meio. O template emite `apply community community-list CL-PEER-<T> additive` e marca com `!-`.
- Se uma `community-list` sem membro é aceita. É o que o quadro "ao criar o peer" emite.
- Se um filtro que declara `($prepend_base)` na assinatura aceita ser chamado sem os parênteses. Se não aceitar, a sessão sem prepend de engenharia precisa de uma segunda variante do filtro. O caso do `apply as-path <asn> 0 additive` já está fechado: o PLANO registra erro no equipamento e o mínimo da cláusula é 1.
- Se `apply preference` e `apply preferred-value` existem na view do `route-filter`.
- O coringa em large-community-list, que trava a checagem espelhada do `64512:4:<ASN>`.
- Se `64512:*` casa mesmo em `CL-OWN-ALL` como diagnóstico. O PLANO confirma para `64512:*` e nega para `64512:1*`: o `*` substitui um campo inteiro.

## Buracos de validação que ficam abertos

Achados na re-revisão final. Nenhum é regressão desta implementação: os dois são
anteriores ao ciclo de correções. Ficam registrados, e não consertados por
palpite.

- **`origem` fora da faixa 1xxx nos tipos que não são cliente.** O check
  `peer.origem not in ORIGENS_CLIENTE` mora dentro do `if peer.tipo ==
  "cliente"`, em `app/validate.py`. Nos outros três tipos, `64512:14` ou
  `64512:99999` é emitido sem erro nenhum, embora `plan.faixa_ok("64512:14")`
  seja `False`. Não estoura e não vaza rota: a community não casa em filtro
  nenhum e o marcador de origem simplesmente some. Precisa de digitação do
  operador, porque o formulário preenche o campo com a tabela.
- **`prepend_base` sem faixa nenhuma.** Medido: `-1` vira `apply as-path 64512
  -1 additive` com zero erros de validação, e `99` passa igual. O mínimo `1` está
  verificado no equipamento (`PLANO.md:393`); **o máximo não está**. A escala de 1
  a 6 do `6CA` é convenção do plano, e um limite superior inventado seria pior
  que limite nenhum. A pergunta fica aberta: qual é o maior prepend que o F1A
  aceita nessa cláusula?
