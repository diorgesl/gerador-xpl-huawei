# Tabela recebida pelo downstream: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cliente e parceiro passam a ter um campo `tabela` (`nenhuma | parcial | parcial_ix | full`) que decide o que o export entrega, ao lado do `default_route`, e o cadastro novo nasce recebendo só a default.

**Architecture:** O campo mora em `Peer` e `Grupo` (default `full` no dataclass, para o YAML antigo gerar o mesmo bloco). O `filtro_downstream_export` ganha um portão por modo, depois dos vetos, que usa a `CL-ORIGEM-ANUNCIAVEL` existente ou uma lista nova `CL-ORIGEM-PARCIAL-IX` no bloco base. O padrão "só default" entra pelo `peer_em_branco`/`grupo_em_branco`, pelo formulário em branco do front e pela cascata da troca de tipo; o contrato do POST não muda.

**Tech Stack:** Python 3 (FastAPI, pydantic, Jinja2, pytest), React + TypeScript (react-hook-form, vitest), XPL do Huawei VRP.

**Spec:** `docs/superpowers/specs/2026-10-01-tabela-recebida-pelo-downstream-design.md`

## Global Constraints

- Valores de `tabela`, nesta ordem: `("nenhuma", "parcial", "parcial_ix", "full")`, em `plan.TABELAS`.
- `tabela` ausente no YAML = `"full"`. `default_route` ausente no YAML = `False` (como hoje).
- Cadastro novo de cliente/parceiro: `default_route=True`, `tabela="nenhuma"`. Upstream, IX e PNI: `default_route=False`, `tabela=""` no formulário.
- O POST continua com `default_route` ausente = `False`. `tabela` ausente ou `""` num downstream vira `"nenhuma"`.
- Tudo que sai em bloco XPL (comentários `#` e `{# #}` renderizados, nomes de lista) é ASCII. A prosa do PDF (`app/politica.py`) e do PLANO tem acento.
- Nome da lista nova: `CL-ORIGEM-PARCIAL-IX`. Conteúdo: `ORIGEM_ANUNCIAVEL` + `c(ORIGEM["ix"], ns)` (o `1300`), no namespace da rede.
- `default-route-advertise` não passa pelo route-filter de export e origina a default mesmo sem default na RIB/FIB: confirmado no equipamento pelo operador. O texto não leva a marca de "a confirmar".
- Suíte Python: `.venv/bin/python -m pytest`. Front: `cd web && npm test`, `npm run lint`, `npm run api:conferir`.
- Comentários de código no estilo do repositório: português sem acento, explicando o porquê.
- A implementação roda numa worktree própria (superpowers:using-git-worktrees). O merge na `main` fica com o usuário.

## Review Focus

- `tabela` com valor fora da lista (YAML editado à mão, POST com `"PARCIAL"`): o `validate` recusa antes de gravar; o render nunca escolhe um modo por omissão. Teste na Task 4.
- Membro de grupo com `tabela` gravada diferente da do grupo: o bloco do membro não muda e o cabeçalho mostra a do grupo. Teste na Task 3.
- Peer que reaproveita a política de outro (`politica_de`): o cabeçalho mostra a tabela da origem, e o aviso de "sessão sem rota" não dispara. Testes nas Tasks 3 e 4.
- Troca de tipo no formulário, de cliente para upstream e de volta: a caixa da default e a tabela acompanham o padrão do tipo, sem deixar `default_route=true` num upstream (que o `validate` recusaria). Teste na Task 6.
- Rede com namespace trocado (`plan.Rede(asn=64500)`): a `CL-ORIGEM-PARCIAL-IX` sai com `64500:1300`, nunca com `64512:1300`. Teste na Task 1.

---

### Task 1: Constantes do plano e a lista nova no bloco base

**Files:**
- Modify: `app/plan.py` (perto de `_origem_anunciavel`, linha ~209, e em `Rede.__init__`, linha ~784)
- Modify: `templates/base.txt.j2` (logo depois da `CL-ORIGEM-ANUNCIAVEL`, linha ~93)
- Modify: `tests/golden/_base.txt` (regerado)
- Test: `tests/test_plan.py`, `tests/test_render.py`

**Interfaces:**
- Produces: `plan.TABELAS: tuple[str, ...]`, `plan.ORIGEM_PARCIAL_IX: tuple[str, ...]`, `plan._origem_parcial_ix(ns=ASN) -> tuple[str, ...]`, `Rede.ORIGEM_PARCIAL_IX`. Lista XPL `CL-ORIGEM-PARCIAL-IX` no bloco base.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_plan.py`, acrescentar `"ORIGEM_PARCIAL_IX"` à tupla `CAMPOS_DO_ASN` (linha ~197) e, dentro de `test_a_rede_troca_o_prefixo_de_tudo_que_e_do_plano`, depois da assercao do `ORIGEM_ANUNCIAVEL`:

```python
    assert r.ORIGEM_PARCIAL_IX == r.ORIGEM_ANUNCIAVEL + ("64500:1300",)
```

E um caso novo no fim do arquivo:

```python
def test_a_parcial_com_ix_e_a_anunciavel_mais_a_origem_do_ix():
    # o portao da parcial_ix e uma lista so: a anunciavel e a marca que o
    # import do IX carimba. PNI (1500) e upstream (1400) ficam de fora
    assert plan.TABELAS == ("nenhuma", "parcial", "parcial_ix", "full")
    assert plan.ORIGEM_PARCIAL_IX == plan.ORIGEM_ANUNCIAVEL + ("64512:1300",)
    assert "64512:1500" not in plan.ORIGEM_PARCIAL_IX
    assert "64512:1400" not in plan.ORIGEM_PARCIAL_IX
```

Em `tests/test_render.py`, na tupla de `test_base_tem_os_objetos_compartilhados`, depois de `"xpl community-list CL-ORIGEM-ANUNCIAVEL",`:

```python
        "xpl community-list CL-ORIGEM-PARCIAL-IX",
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_plan.py tests/test_render.py -q -k "parcial or rede_troca or objetos_compartilhados or CAMPOS_DO_ASN"`
Expected: FAIL com `AttributeError: module 'app.plan' has no attribute 'TABELAS'` e a lista ausente no base.

- [ ] **Step 3: Implementar**

Em `app/plan.py`, logo depois de `ORIGEM_ANUNCIAVEL = _origem_anunciavel()`:

```python
# o que a sessao de cliente e de parceiro recebe alem da default, que e o
# outro campo (default_route). A ordem e a da tela, do menos para o mais.
TABELAS = ("nenhuma", "parcial", "parcial_ix", "full")


# a tabela parcial + IX: a anunciavel mais a origem que o import do IX
# carimba. Uma lista so, e nao duas no mesmo if, para o portao do export de
# cliente nao depender da precedencia de and/or (PLANO, armadilhas de fluxo).
def _origem_parcial_ix(ns=ASN):
    return _origem_anunciavel(ns) + (c(ORIGEM["ix"], ns),)


ORIGEM_PARCIAL_IX = _origem_parcial_ix()
```

Em `Rede.__init__`, logo depois de `self.ORIGEM_ANUNCIAVEL = _origem_anunciavel(self.ns)`:

```python
        self.ORIGEM_PARCIAL_IX = _origem_parcial_ix(self.ns)
```

Atualizar a contagem nos comentários que dizem "os sete valores" (em `Rede.__init__` e no comentário de `_NOMES_COM_O_ASN`, perto das linhas 12 e 831) para "os oito valores", se o número citado ali for o desses campos. Confira lendo o comentário antes de trocar.

Em `templates/base.txt.j2`, logo depois do `end-list` da `CL-ORIGEM-ANUNCIAVEL`:

```
{# o portao da tabela parcial + IX no egress de cliente: a anunciavel mais a
   origem do IX. A parcial sem IX usa a CL-ORIGEM-ANUNCIAVEL de cima. #}
xpl community-list CL-ORIGEM-PARCIAL-IX
{% for c in plan.ORIGEM_PARCIAL_IX %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
end-list
```

- [ ] **Step 4: Regerar a golden do base e conferir o diff**

```bash
.venv/bin/python -c "from app import render; open('tests/golden/_base.txt','w',encoding='ascii').write(render.render_base())"
git diff --stat tests/golden/_base.txt && git diff tests/golden/_base.txt
```

Expected: o diff só acrescenta o bloco `xpl community-list CL-ORIGEM-PARCIAL-IX` com seis linhas de community (`64512:1000` ... `64512:1130`, `64512:1300`) e o `end-list`.

- [ ] **Step 5: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS. Se algum teste de base por rede (`tests/test_base.py`) comparar o base inteiro com outro arquivo de golden, regere esse arquivo do mesmo jeito e confira que o diff é só a lista nova.

- [ ] **Step 6: Commit**

```bash
git add app/plan.py templates/base.txt.j2 tests/golden/_base.txt tests/test_plan.py tests/test_render.py
git commit -m "A lista da tabela parcial com IX entra no bloco base"
```

---

### Task 2: O campo `tabela` no Peer e no Grupo

**Files:**
- Modify: `app/peers.py` (Peer: depois de `default_route`, linha ~100, e `para_dict`, linha ~235; Grupo: depois de `default_route`, linha ~405, e `para_dict`, linha ~461)
- Test: `tests/test_peers.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Peer.tabela: str = "full"`, `Grupo.tabela: str = "full"`, gravados por `para_dict` como `"tabela"`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_peers.py`, depois de `test_default_route_ausente_no_yaml_antigo_e_false`:

```python
def test_tabela_atravessa_o_yaml(tmp_path):
    # o para_dict lista os campos um a um: um campo que ele esqueca some na
    # gravacao sem erro nenhum
    caminho = tmp_path / "peers.yaml"
    mod.gravar([mod.Peer(id=0, nome="Cliente ACME", tipo="cliente",
                         asn=268127, tabela="parcial")], caminho)
    assert mod.carregar(caminho)[0].tabela == "parcial"


def test_tabela_do_grupo_atravessa_o_yaml(tmp_path):
    caminho = tmp_path / "peers.yaml"
    g = mod.Grupo(id=0, nome="CLIENTES", tipo="cliente", classe="transito",
                  origem=1100, pop=2001, tabela="parcial_ix")
    mod.gravar_grupos([g], caminho)
    assert mod.carregar_grupos(caminho)[0].tabela == "parcial_ix"


def test_tabela_ausente_no_yaml_antigo_e_full():
    # o campo nasceu depois: todo downstream recebia a full table, e o
    # cadastro antigo tem que gerar o mesmo bloco de antes
    assert mod.Peer.de_dict({"id": 0, "nome": "x", "asn": 1}).tabela == "full"
    assert mod.Grupo.de_dict({"id": 0, "nome": "G"}).tabela == "full"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_peers.py -q -k tabela`
Expected: FAIL com `TypeError: ... unexpected keyword argument 'tabela'`.

- [ ] **Step 3: Implementar**

Em `Peer`, logo depois de `default_route: bool = False`:

```python
    # cliente/parceiro: o que a sessao recebe alem da default (plan.TABELAS).
    # Ausente no yaml e "full", que e o que todo downstream recebia antes de
    # o campo existir. O peer novo nasce com "nenhuma" pelo peer_em_branco,
    # e nao por aqui, para o cadastro antigo nao mudar de saida.
    tabela: str = "full"
```

No `Peer.para_dict`, trocar `"default_route": self.default_route, "grupo_id": self.grupo_id,` por:

```python
            "default_route": self.default_route, "tabela": self.tabela,
            "grupo_id": self.grupo_id,
```

Em `Grupo`, logo depois de `default_route: bool = False`:

```python
    # o mesmo campo do peer, com o mesmo default pelo mesmo motivo. Vale para
    # os membros: o export do membro termina chamando o do grupo
    tabela: str = "full"
```

No `Grupo.para_dict`, trocar `"default_route": self.default_route, "bfd": self.bfd,` por:

```python
            "default_route": self.default_route, "tabela": self.tabela,
            "bfd": self.bfd,
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_peers.py -q`
Expected: PASS (inclui `test_o_peers_yaml_do_repositorio_nao_tem_membro_orfao`, que lê o `peers/264130.yaml` sem o campo).

- [ ] **Step 5: Commit**

```bash
git add app/peers.py tests/test_peers.py
git commit -m "Peer e grupo guardam a tabela que o downstream recebe"
```

---

### Task 3: O portão no export de downstream e o cabeçalho

**Files:**
- Modify: `templates/_macros.j2` (`cabecalho`, linhas 1-11; `cabecalho_grupo`, linhas 218-225; `filtro_downstream_export`, linhas 288-327)
- Modify: `templates/cliente.txt.j2:6` (chamada do `cabecalho`)
- Modify: `tests/golden/cliente.txt`, `parceiro.txt`, `cliente-coberto.txt`, `cliente-tratado.txt`, `cliente-reaproveita.txt`, `remover-*.txt` se mudarem (regerados)
- Create: `tests/golden/cliente-nenhuma.txt`, `tests/golden/cliente-parcial.txt`, `tests/golden/cliente-parcial-ix.txt`, `tests/golden/grupo-cliente-parcial.txt`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Peer.tabela`, `Grupo.tabela` (Task 2); lista `CL-ORIGEM-PARCIAL-IX` (Task 1).
- Produces: macro `cabecalho(peer, grupo=none, origem=none)`. Os outros templates (`upstream`, `ix`, `pni`) seguem chamando `cabecalho(peer)`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_render.py`, substituir `test_default_route_avisa_no_cabecalho` por:

```python
def test_default_route_avisa_no_cabecalho():
    # o VRP origina a default nesta sessao mesmo sem default na tabela, e o
    # filtro de export nao a ve: o aviso diz isso antes da colagem
    texto = render.render_peer(peer_cliente(default_route=True))
    cabecalho = [l for l in texto.splitlines()[:8] if l.startswith("#")]
    assert ("# default route: o VRP origina 0/0 e ::/0 nesta sessao mesmo "
            "sem default na tabela") in cabecalho
```

Em `test_bloco_do_grupo_com_default_route_avisa_e_anuncia` e `test_bloco_do_grupo_sem_default_route_nao_avisa_nem_anuncia`, trocar a string `"a default route vai para este cliente: confirme que ha um default na tabela"` / `"a default route vai para este cliente"` por `"default route: o VRP origina 0/0 e ::/0"`.

Acrescentar, depois de `test_golden_do_parceiro`:

```python
def _export(texto, token="268127", fam="V4"):
    return texto.split("xpl route-filter CUST-%s-EXPORT-%s" % (token, fam))[1] \
        .split("end-filter")[0]


def test_tabela_full_nao_tem_portao():
    export = _export(render.render_peer(peer_cliente(tabela="full")))
    assert "CL-ORIGEM-ANUNCIAVEL" not in export
    assert "CL-ORIGEM-PARCIAL-IX" not in export
    assert export.strip().endswith("finish")


def test_tabela_nenhuma_recusa_tudo():
    # a default nao passa por este filtro: o VRP a origina por fora dele
    export = _export(render.render_peer(peer_cliente(tabela="nenhuma")))
    linhas = [l.strip() for l in export.splitlines()
              if l.strip() and not l.strip().startswith("#")]
    assert linhas == ["refuse"]


def test_tabela_parcial_so_libera_propria_e_de_cliente():
    export = _export(render.render_peer(peer_cliente(tabela="parcial")))
    assert ("if not community matches-any CL-ORIGEM-ANUNCIAVEL then\n"
            "  refuse\n endif") in export
    assert "CL-ORIGEM-PARCIAL-IX" not in export


def test_tabela_parcial_ix_usa_a_lista_com_o_ix():
    export = _export(render.render_peer(peer_cliente(tabela="parcial_ix")))
    assert ("if not community matches-any CL-ORIGEM-PARCIAL-IX then\n"
            "  refuse\n endif") in export


def test_o_portao_vem_depois_dos_vetos_e_antes_do_prepend():
    export = _export(render.render_peer(peer_cliente(tabela="parcial")))
    assert export.index("CL-RESTRICAO") < export.index("CL-ORIGEM-ANUNCIAVEL")
    assert export.index("64512:1901") < export.index("CL-ORIGEM-ANUNCIAVEL")
    assert export.index("CL-ORIGEM-ANUNCIAVEL") < export.index("{64512:3:268127}")


def test_o_cabecalho_do_downstream_diz_a_tabela():
    texto = render.render_peer(peer_cliente(tabela="parcial"))
    assert "# tabela recebida: parcial" in texto.splitlines()[:8]


def test_o_cabecalho_do_upstream_nao_fala_de_tabela():
    assert "tabela recebida" not in render.render_peer(peer_upstream())


def test_o_membro_mostra_a_tabela_do_grupo_e_nao_a_dele():
    # o export do membro chama o do grupo: a tabela gravada no membro nao
    # vale, e o cabecalho nao pode dizer que vale
    grupo = grupo_cliente_sem_asn()
    grupo.tabela = "parcial"
    membro = peer_membro_sem_override(grupo.id)
    membro.tipo = "cliente"
    membro.tabela = "full"
    texto = render.render_peer(membro, grupo=grupo)
    assert ("# tabela recebida: parcial (a do grupo %s)" % grupo.nome
            in texto.splitlines()[:8])
    assert "CL-ORIGEM" not in texto


def test_o_grupo_de_cliente_aplica_o_portao():
    grupo = grupo_cliente_sem_asn()
    grupo.tabela = "parcial"
    texto = render.render_grupo(grupo)
    assert "# tabela recebida: parcial" in texto
    assert "if not community matches-any CL-ORIGEM-ANUNCIAVEL then" in texto


def test_quem_reaproveita_mostra_a_tabela_da_origem():
    origem = peer_cliente(tabela="parcial_ix")
    copia = peer_cliente(id=2, apelido="ACME-BKP", tabela="nenhuma",
                         politica_de=origem.id)
    texto = render.render_peer(copia, origem=origem)
    assert any(l.startswith("# tabela recebida: parcial_ix")
               for l in texto.splitlines()[:8])


@pytest.mark.parametrize("arquivo,tabela", [
    ("cliente-nenhuma.txt", "nenhuma"),
    ("cliente-parcial.txt", "parcial"),
    ("cliente-parcial-ix.txt", "parcial_ix"),
])
def test_golden_do_cliente_por_tabela(arquivo, tabela):
    assert render.render_peer(peer_cliente(tabela=tabela, default_route=True)) == (
        GOLDEN / arquivo).read_text(encoding="ascii")


def test_golden_do_grupo_de_cliente_parcial():
    grupo = grupo_cliente_sem_asn()
    grupo.tabela = "parcial"
    assert render.render_grupo(grupo) == (
        GOLDEN / "grupo-cliente-parcial.txt").read_text(encoding="ascii")
```

`peer_upstream`, `grupo_cliente_sem_asn` e `peer_membro_sem_override` já existem neste arquivo; confira os nomes com `grep -n "^def peer_upstream\|^def peer_membro_sem_override" tests/test_render.py` antes de rodar.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_render.py -q -k "tabela or cabecalho or default_route or reaproveita or grupo_de_cliente"`
Expected: FAIL (portão ausente, cabeçalho antigo, goldens novas inexistentes).

- [ ] **Step 3: Implementar o cabeçalho**

Em `templates/_macros.j2`, substituir o macro `cabecalho` inteiro por:

```jinja
{% macro cabecalho(peer, grupo=none, origem=none) -%}
# gerado por bgpgen - nao editar a mao
# peer {{ peer.id }} - {{ peer.tipo }} - AS{{ peer.asn }} - token {{ peer.token }}
{# A tabela que vale e a de quem define o export: o grupo, no membro, porque
   o export do membro termina chamando o do grupo; a origem, em quem
   reaproveita, porque o bloco dele chama os filtros dela. O valor gravado no
   proprio peer nesses dois casos nao chega a filtro nenhum. #}
{% if peer.tipo in plan.TIPOS_DOWNSTREAM %}
{% if origem is not none %}
# tabela recebida: {{ origem.tabela }} (a do peer {{ origem.token }}, de quem a politica vem)
{% elif grupo %}
# tabela recebida: {{ grupo.tabela }} (a do grupo {{ grupo.nome }})
{% else %}
# tabela recebida: {{ peer.tabela }}
{% endif %}
{% endif %}
{# o aviso da default route nao cabe no bloco bgp: nenhum tipo tem comentario
   renderizado dentro do grupo de sessao nem da familia. Ele fica aqui, que e
   o que o operador le antes de colar. O VRP origina a default nesta sessao
   mesmo sem default na RIB, e por fora do route-filter de export
   (confirmado no equipamento). #}
{% if peer.default_route %}
# default route: o VRP origina 0/0 e ::/0 nesta sessao mesmo sem default na tabela
{% endif %}
# pressupoe o bloco base ja aplicado neste equipamento
{%- endmacro %}
```

Substituir o `cabecalho_grupo` por:

```jinja
{% macro cabecalho_grupo(grupo) -%}
# gerado por bgpgen - nao editar a mao
# grupo {{ grupo.id }} - {{ grupo.tipo }} - nome {{ grupo.nome }}
{% if grupo.tipo in plan.TIPOS_DOWNSTREAM %}
# tabela recebida: {{ grupo.tabela }}
{% endif %}
{% if grupo.default_route %}
# default route: o VRP origina 0/0 e ::/0 nesta sessao mesmo sem default na tabela
{% endif %}
# pressupoe o bloco base ja aplicado neste equipamento
{%- endmacro %}
```

Em `templates/cliente.txt.j2:6`, trocar `{{ m.cabecalho(peer) }}` por:

```jinja
{{ m.cabecalho(peer, grupo, origem) }}
```

O render passa `grupo` e `origem` ao template (`render_peer`, `app/render.py:56`), com `None` quando não há; confira que `none` do Jinja aceita o `None` do Python no `is not none`.

- [ ] **Step 4: Implementar o portão**

Em `filtro_downstream_export`, envolver o corpo e acrescentar o portão. O macro inteiro fica:

```jinja
{% macro filtro_downstream_export(alvo, fam) -%}
{% set U = fam|upper %}
xpl route-filter CUST-{{ alvo.token }}-EXPORT-{{ U }}
{% if alvo.tabela == "nenhuma" %}
 {# So a default vai para esta sessao, e ela nao passa por este filtro: o VRP
    a origina por fora do export. Nao ha rota para vetar nem para prependar,
    e o filtro existe porque a sessao o referencia. #}
 refuse
{% else %}
 ... (os vetos de hoje, sem mudanca: CL-RESTRICAO, CL-BLACKHOLE, CL-NOADV-CUST,
      CL-ONLY-NOT-CLIENT, o 0:<asn>, o 1900/1901) ...
{% if alvo.tabela in ("parcial", "parcial_ix") %}
 {# A tabela parcial: so a rota propria e a de cliente, e na parcial_ix tambem
    a aprendida no IX. A rota de upstream e de PNI para aqui. Vem depois dos
    vetos, que valem em qualquer tabela, e antes do prepend, que nao tem o
    que fazer com rota recusada. #}
 if not community matches-any {{ "CL-ORIGEM-PARCIAL-IX" if alvo.tabela == "parcial_ix" else "CL-ORIGEM-ANUNCIAVEL" }} then
  refuse
 endif
{% endif %}
 ... (o ramo de prepend por ASN de hoje, sem mudanca) ...
 finish
{% endif %}
end-filter
{%- endmacro %}
```

As duas linhas `...` são o texto atual do macro, copiado sem mudança: os vetos vão de `if community matches-any CL-RESTRICAO then` até o `endif` do `{{ plan.conjunto(plan.c(1900), plan.c(1901)) }}`, e o prepend é o bloco `{% if alvo.asn %} ... {% endif %}` com os `apply as-path`. O `{% endif %}` novo fecha o `{% if alvo.tabela == "nenhuma" %}` antes do `end-filter`.

- [ ] **Step 5: Gerar as goldens novas e regerar as de downstream**

```bash
.venv/bin/python - <<'EOF'
import sys
sys.path.insert(0, "tests")
from pathlib import Path
from app import render
import test_render as t
G = Path("tests/golden")
for nome, tabela in [("cliente-nenhuma.txt", "nenhuma"), ("cliente-parcial.txt", "parcial"),
                     ("cliente-parcial-ix.txt", "parcial_ix")]:
    (G / nome).write_text(render.render_peer(t.peer_cliente(tabela=tabela, default_route=True)), encoding="ascii")
g = t.grupo_cliente_sem_asn(); g.tabela = "parcial"
(G / "grupo-cliente-parcial.txt").write_text(render.render_grupo(g), encoding="ascii")
EOF
.venv/bin/python -m pytest tests/test_render.py -q 2>&1 | tail -20
```

Os testes de golden de downstream que falharem (`cliente.txt`, `parceiro.txt`, `cliente-coberto.txt`, `cliente-tratado.txt`, `cliente-reaproveita.txt`) falham porque o cabeçalho ganhou a linha da tabela. Para cada um, encontre o teste que lê o arquivo (`grep -n "nome-do-arquivo" tests/test_render.py`), regere com a mesma chamada que o teste faz e confira o diff:

```bash
git diff tests/golden/
```

Expected: em cada golden de downstream existente, o diff é só `+# tabela recebida: full` (ou `+# tabela recebida: full (a do peer ..., de quem a politica vem)` no `cliente-reaproveita.txt`). Qualquer outra linha mudada num filtro é bug; pare e corrija o macro. Leia as quatro goldens novas inteiras e confira à mão: `cliente-nenhuma.txt` tem o export só com `refuse` e a sessão com `default-route-advertise`; `cliente-parcial.txt` tem o portão com `CL-ORIGEM-ANUNCIAVEL`; `cliente-parcial-ix.txt` com `CL-ORIGEM-PARCIAL-IX`.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS. `test_o_parceiro_difere_do_cliente_so_no_cabecalho_e_na_marca` tem que continuar passando (a linha da tabela é igual nos dois). `test_base_e_ascii`, `test_cliente_e_ascii` e `test_a_saida_do_grupo_e_do_membro_e_ascii_nos_cinco_tipos` cobram o ASCII.

- [ ] **Step 7: Commit**

```bash
git add templates/_macros.j2 templates/cliente.txt.j2 tests/test_render.py tests/golden/
git commit -m "O export de downstream respeita a tabela que o cliente recebe"
```

---

### Task 4: Validação

**Files:**
- Modify: `app/validate.py` (`avisos`, linha ~48; `validar_grupo`, ramo de downstream, linha ~518; `validar`, ramo de downstream, linha ~744)
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `plan.TABELAS` (Task 1), `Peer.tabela`/`Grupo.tabela` (Task 2).
- Produces: `Erro("tabela", ...)` em `validar`/`validar_grupo`; `Erro("tabela", ...)` em `avisos`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_validate.py`, no fim do arquivo:

```python
def test_tabela_fora_da_lista_e_erro_no_downstream():
    for valor in ("", "PARCIAL", "transito"):
        assert "tabela" in campos(validar(um_peer(tabela=valor), [])), valor
    for valor in plan.TABELAS:
        assert "tabela" not in campos(validar(um_peer(tabela=valor), [])), valor


def test_tabela_fora_da_lista_e_erro_no_grupo_de_downstream():
    g = um_grupo(tabela="tudo")
    assert "tabela" in campos(validar_grupo(g, [g], [], anterior=g))
    g = um_grupo(tabela="parcial")
    assert "tabela" not in campos(validar_grupo(g, [g], [], anterior=g))


def test_tabela_e_ignorada_fora_do_downstream():
    # o campo so e lido no export de downstream; o formulario nem o grava
    # nos outros tipos, mas um yaml editado a mao nao pode travar o upstream
    peer = um_peer(tipo="upstream", classe=None, aprendizado=3000, tabela="xyz")
    assert "tabela" not in campos(validar(peer, []))


def test_sessao_sem_rota_nenhuma_e_aviso_e_nao_erro():
    peer = um_peer(default_route=False, tabela="nenhuma")
    assert "tabela" not in campos(validar(peer, []))
    assert "tabela" in campos(validate.avisos(peer, []))


def test_sem_aviso_quando_a_sessao_recebe_alguma_coisa():
    assert "tabela" not in campos(validate.avisos(
        um_peer(default_route=True, tabela="nenhuma"), []))
    assert "tabela" not in campos(validate.avisos(
        um_peer(default_route=False, tabela="parcial"), []))


def test_membro_e_quem_reaproveita_nao_avisam_sessao_sem_rota():
    # a tabela deles vem do grupo ou da origem; a gravada no proprio peer
    # nao chega a filtro nenhum
    membro = um_peer(default_route=False, tabela="nenhuma", grupo_id=3)
    copia = um_peer(default_route=False, tabela="nenhuma", politica_de=0)
    assert "tabela" not in campos(validate.avisos(membro, []))
    assert "tabela" not in campos(validate.avisos(copia, []))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_validate.py -q -k "tabela or sem_rota or recebe_alguma or nao_avisam"`
Expected: FAIL nos casos de erro e de aviso.

- [ ] **Step 3: Implementar**

Em `validar`, dentro de `if peer.tipo in plan.TIPOS_DOWNSTREAM:`, logo depois da checagem do `pop` fora do `if exige` (a que termina em `"POP entre 2001 e 2999"`):

```python
        # o portao do export escolhe o ramo pelo valor: fora da lista o
        # filtro sairia sem portao, igual ao full, sem ninguem ter pedido
        if peer.tabela not in plan.TABELAS:
            erros.append(Erro(
                "tabela", "tabela recebida: escolha entre %s"
                % ", ".join(plan.TABELAS)))
```

Em `validar_grupo`, dentro de `if grupo.tipo in plan.TIPOS_DOWNSTREAM:`, depois da checagem do `pop`:

```python
        if grupo.tabela not in plan.TABELAS:
            erros.append(Erro(
                "tabela", "tabela recebida: escolha entre %s"
                % ", ".join(plan.TABELAS)))
```

Em `avisos`, antes de `_avisa_communities(peer, saida, rede)`:

```python
    # sem default e sem tabela a sessao sobe e nao recebe rota nenhuma. E
    # legitimo para quem so anuncia, e por isso aviso, mas costuma ser a caixa
    # da default desmarcada sem querer. Membro e quem reaproveita ficam de
    # fora: a tabela deles e a do grupo ou a da origem.
    if (peer.tipo in plan.TIPOS_DOWNSTREAM and peer.grupo_id is None
            and peer.politica_de is None and not peer.default_route
            and peer.tabela == "nenhuma"):
        saida.append(Erro(
            "tabela", "sem default route e sem tabela, a sessao nao recebe "
            "rota nenhuma"))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_validate.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/validate.py tests/test_validate.py
git commit -m "A tabela fora da lista e recusada, e a sessao sem rota avisa"
```

---

### Task 5: Formulário, API e o padrão do cadastro novo

**Files:**
- Modify: `app/formulario.py` (`peer_do_formulario` ~linha 422; `grupo_do_formulario` ~linha 521; `peer_em_branco` linha 612; `grupo_em_branco` linha 629; `_padroes` linha 193; `CAMPOS_POR_TIPO` linha 658; `CAMPOS_POR_TIPO_GRUPO` linha 678)
- Modify: `app/modelos_api.py` (`PeerForm`, `GrupoForm`, `TabelaTipo`, `Plano`, `GrupoResumo`)
- Modify: `app/api.py` (`modelo_do_peer` linha 60; `modelo_do_grupo` linha 92; `ler_plano` linha 238; `listar_grupos` linha 633)
- Modify: `web/src/api/schema.d.ts` (regerado)
- Test: `tests/test_formulario.py`, `tests/test_api_peers.py`, `tests/test_api_grupos.py`

**Interfaces:**
- Consumes: `plan.TABELAS`, `Peer.tabela`, `Grupo.tabela`.
- Produces (o front da Task 6 depende destes nomes):
  - `PeerForm.tabela: str = ""`, `GrupoForm.tabela: str = ""`.
  - `Plano.tabelas: list[str]`.
  - `TabelaTipo.default_route: bool`, `TabelaTipo.tabela: str` (em `plano.padroes.tipos[<tipo>]`).
  - `GrupoResumo.tabela: str`.
  - `CAMPOS_POR_TIPO["tabela"] == ("cliente", "parceiro")`, idem no `_GRUPO`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_formulario.py`, no dicionário `CHEIO`, acrescentar `"tabela": "parcial",`. Em `test_o_bloco_da_cascata_e_a_tabela_do_plano`, trocar a comparação do `p["tipos"][tipo]` por:

```python
        assert p["tipos"][tipo] == {
            "lp_base": plan.LP_BASE.get(tipo),
            "route_limit": plan.ROUTE_LIMIT.get(tipo),
            "timer_keepalive": plan.TIMER_PADRAO.get(tipo, (None, None))[0],
            "timer_hold": plan.TIMER_PADRAO.get(tipo, (None, None))[1],
            "default_route": tipo in plan.TIPOS_DOWNSTREAM,
            "tabela": "nenhuma" if tipo in plan.TIPOS_DOWNSTREAM else "",
        }, tipo
```

E casos novos no fim:

```python
def test_tabela_em_branco_no_downstream_vira_nenhuma():
    modelo = modelo_do_peer(peer_cliente()).model_copy(update={"tabela": ""})
    peer, _ = peer_do_formulario(dados_do_formulario(modelo), [], None, ())
    assert peer.tabela == "nenhuma"


def test_tabela_fora_do_downstream_fica_no_default():
    modelo = modelo_do_peer(peer_upstream()).model_copy(update={"tabela": "parcial"})
    peer, _ = peer_do_formulario(dados_do_formulario(modelo), [], None, ())
    assert peer.tabela == "full"


def test_o_modelo_so_mostra_a_tabela_de_quem_a_usa():
    # valor guardado aparece na tela mesmo fora do tipo: o upstream e o
    # membro de grupo teriam um select que nao faz nada
    assert modelo_do_peer(peer_cliente(tabela="parcial")).tabela == "parcial"
    assert modelo_do_peer(peer_upstream()).tabela == ""
    assert modelo_do_peer(peer_cliente(tabela="parcial", grupo_id=3)).tabela == ""


def test_o_peer_em_branco_de_downstream_recebe_so_a_default():
    for tipo in plan.TIPOS:
        p = formulario.peer_em_branco(tipo, [], [])
        g = formulario.grupo_em_branco(tipo, [], [])
        down = tipo in plan.TIPOS_DOWNSTREAM
        assert (p.default_route, g.default_route) == (down, down), tipo
        if down:
            assert (p.tabela, g.tabela) == ("nenhuma", "nenhuma"), tipo
```

Confira o import de `peer_upstream` no topo do arquivo (já vem de `test_render`).

Em `tests/test_api_peers.py`, depois de `test_o_peer_novo_traz_os_defaults_do_tipo`:

```python
def test_o_peer_novo_de_downstream_recebe_so_a_default(api):
    for tipo in ("cliente", "parceiro"):
        f = api.get("/api/peers/novo", params={"tipo": tipo}).json()["formulario"]
        assert (f["default_route"], f["tabela"]) == (True, "nenhuma"), tipo
    f = api.get("/api/peers/novo", params={"tipo": "upstream"}).json()["formulario"]
    assert (f["default_route"], f["tabela"]) == (False, "")


def test_post_de_cliente_sem_tabela_grava_nenhuma(api, tmp_path):
    r = api.post("/api/peers", json=CLIENTE)
    assert r.status_code == 201, r.text
    assert peers_mod.carregar(caminho_tenant(tmp_path))[0].tabela == "nenhuma"
```

Em `tests/test_api_grupos.py`, no fim:

```python
def test_o_grupo_novo_de_downstream_recebe_so_a_default(api):
    f = api.get("/api/grupos/novo", params={"tipo": "cliente"}).json()["formulario"]
    assert (f["default_route"], f["tabela"]) == (True, "nenhuma")


def test_a_lista_de_grupos_traz_a_tabela(api, tmp_path):
    peers_mod.gravar_grupos(
        [peers_mod.Grupo(id=3, nome="CLIENTES", tipo="cliente", classe="transito",
                         origem=1100, pop=2001, tabela="parcial")],
        caminho_tenant(tmp_path))
    assert api.get("/api/grupos").json()[0]["tabela"] == "parcial"


def test_o_plano_publica_as_tabelas(api):
    assert api.get("/api/plano").json()["tabelas"] == list(plan.TABELAS)
```

Confira os imports do `test_api_grupos.py` (`peers_mod`, `caminho_tenant`, `plan`) e acrescente o que faltar seguindo o topo do `test_api_peers.py`. Se o `/api/plano` exigir o parâmetro do tenant, copie a chamada de um teste existente desse endpoint (`grep -n "/api/plano" tests/*.py`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_formulario.py tests/test_api_peers.py tests/test_api_grupos.py -q`
Expected: FAIL (`tabela` desconhecida no `PeerForm`, padrões sem os campos novos).

- [ ] **Step 3: Implementar o back**

`app/modelos_api.py`:
- Em `PeerForm` e `GrupoForm`, logo depois de `default_route: bool = False`:

```python
    # em branco num downstream vira "nenhuma" no peer_do_formulario; nos
    # outros tipos o campo nao e lido
    tabela: str = ""
```

- Em `TabelaTipo`, acrescentar:

```python
    # a caixa da default e a tabela que o tipo recebe ao nascer: a cascata da
    # troca de tipo le estes dois junto com os de cima
    default_route: bool
    tabela: str
```

- Em `Plano`, depois de `classes_cliente: list[str]`: `tabelas: list[str]`.
- Em `GrupoResumo`, depois de `tipo: str`: `tabela: str`.

`app/formulario.py`:
- Em `peer_do_formulario`, no `Peer(...)`, depois de `default_route=dados.get("default_route") == "on",`:

```python
        # so o downstream le a tabela; nos outros tipos fica o default do
        # dataclass. O branco e "nenhuma", o padrao do cadastro novo
        **({"tabela": _texto(dados, "tabela") or "nenhuma"}
           if tipo in plan.TIPOS_DOWNSTREAM else {}),
```

- Em `grupo_do_formulario`, no `Grupo(...)`, depois de `default_route=dados.get("default_route") == "on",`, o mesmo `**({...} if tipo in plan.TIPOS_DOWNSTREAM else {}),`.
- Em `peer_em_branco` e `grupo_em_branco`, acrescentar ao construtor:

```python
                **_padrao_do_downstream(tipo))
```

com a função nova acima de `peer_em_branco`:

```python
def _padrao_do_downstream(tipo):
    """O cadastro novo de cliente e de parceiro recebe so a default.

    Fica aqui, e nao no dataclass, porque o default do dataclass e o do yaml
    antigo, que recebia a full table e tem que continuar recebendo.
    """
    if tipo in plan.TIPOS_DOWNSTREAM:
        return {"default_route": True, "tabela": "nenhuma"}
    return {}
```

- Em `_padroes`, no dicionário de cada tipo:

```python
                "default_route": t in plan.TIPOS_DOWNSTREAM,
                "tabela": "nenhuma" if t in plan.TIPOS_DOWNSTREAM else "",
```

- Em `CAMPOS_POR_TIPO` e `CAMPOS_POR_TIPO_GRUPO`, depois da linha do `default_route`: `"tabela": ("cliente", "parceiro"),`.

`app/api.py`:
- Em `modelo_do_peer`, no `dict(...)`, depois de `default_route=peer.default_route,`:

```python
        # so quem usa a tabela a mostra: valor guardado aparece na tela mesmo
        # fora do tipo, e no upstream e no membro de grupo o select nao faria
        # nada
        tabela=(peer.tabela if peer.tipo in plan.TIPOS_DOWNSTREAM
                and peer.grupo_id is None else ""),
```

- Em `modelo_do_grupo`, depois de `default_route=grupo.default_route,`:

```python
        tabela=grupo.tabela if grupo.tipo in plan.TIPOS_DOWNSTREAM else "",
```

- Em `ler_plano`, depois de `classes_cliente=...`: `tabelas=list(plan.TABELAS),`.
- Em `listar_grupos`: `GrupoResumo(id=g.id, nome=g.nome, tipo=g.tipo, tabela=g.tabela, membros=...)`.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_formulario.py tests/test_api_peers.py tests/test_api_grupos.py -q`
Expected: PASS. `test_dentro_da_tabela_o_campo_faz_diferenca` e `test_fora_da_tabela_o_campo_nao_muda_nada_ou_e_recusado` cobrem o `CAMPOS_POR_TIPO` novo.

- [ ] **Step 5: Regerar os tipos do front e rodar tudo**

```bash
cd web && npm run api:tipos && npm run api:conferir && cd ..
.venv/bin/python -m pytest -q
```

Expected: PASS. Se algum teste que posta um cliente sem `tabela` e confere `avisos == []` falhar (por exemplo `tests/test_api.py:251`), acrescente `"default_route": True` ao corpo daquele teste: o aviso novo é o comportamento pedido. Não mude o fixture `CLIENTE` de `tests/dados_api.py`.

- [ ] **Step 6: Commit**

```bash
git add app/formulario.py app/modelos_api.py app/api.py web/src/api/schema.d.ts tests/
git commit -m "O cadastro novo de downstream nasce recebendo so a default"
```

---

### Task 6: A tela

**Files:**
- Modify: `web/src/lib/campos.ts` (`Padroes`, `CAMPOS_POR_TIPO`, `SECOES_PEER`, `SECOES_GRUPO`, `CASCATA_PEER`, `CASCATA_GRUPO`, `cascata`)
- Modify: `web/src/telas/peers/camposPeer.ts` (campo novo e `CAMPO_BRANCO`)
- Modify: `web/src/telas/grupos/camposGrupo.ts` (campo novo e `CAMPO_BRANCO_GRUPO`)
- Modify: `web/src/telas/peers/FormularioPeer.tsx` (mapa de campos do membro e `aoEditarCampo`)
- Modify: `web/src/telas/peers/PeerTela.tsx:~376` (span do grupo)
- Test: `web/src/lib/campos.test.ts`, `web/src/telas/peers/FormularioPeer.test.tsx`, `web/src/telas/grupos/FormularioGrupo.test.tsx`; fixtures em `PeerTela.test.tsx` e `GrupoTela.test.tsx`

**Interfaces:**
- Consumes: `Plano.tabelas`, `padroes.tipos[t].default_route`, `padroes.tipos[t].tabela`, `PeerForm.tabela`, `GrupoForm.tabela`, `GrupoResumo.tabela` (Task 5, já no `schema.d.ts`).
- Produces: `ROTULO_TABELA: Record<string, string>` exportado de `web/src/lib/campos.ts`.

- [ ] **Step 1: Escrever os testes que falham**

Em `web/src/lib/campos.test.ts`, dentro do `describe("a cascata de defaults ao trocar o tipo", ...)`, usando o `PADROES` do arquivo (acrescente `default_route` e `tabela` a cada tipo dele: `true`/`"nenhuma"` em cliente e parceiro, `false`/`""` nos outros):

```ts
  it("a default e a tabela seguem o tipo, e a caixa continua booleana", () => {
    const doCliente = { tipo: "cliente", default_route: true, tabela: "nenhuma", origem: "1100", classe: "" }
    const novo = cascata("cliente", "upstream", doCliente, PADROES, ["default_route", "tabela"])
    expect(novo.default_route).toBe(false)
    expect(novo.tabela).toBe("")
    const volta = cascata("upstream", "cliente", novo, PADROES, ["default_route", "tabela"])
    expect(volta.default_route).toBe(true)
    expect(volta.tabela).toBe("nenhuma")
  })

  it("a tabela escolhida a mao nao volta ao padrao na troca entre downstreams", () => {
    const parcial = { tipo: "cliente", default_route: true, tabela: "parcial", origem: "1100", classe: "" }
    expect(cascata("cliente", "parceiro", parcial, PADROES, ["tabela"]).tabela).toBe("parcial")
  })
```

Em `web/src/telas/peers/FormularioPeer.test.tsx`, no `PLANO`: acrescentar `tabelas: ["nenhuma", "parcial", "parcial_ix", "full"],`, `tabela: ["cliente", "parceiro"]` em `campos_por_tipo`, e `default_route`/`tabela` em cada `padroes.tipos` (como acima). No `BRANCO`, `tabela: "nenhuma",`. Casos novos:

```tsx
  it("o cliente escolhe a tabela recebida entre as do plano", () => {
    render(<Montar />)
    const campo = screen.getByLabelText(/Tabela recebida/)
    expect(campo).toBeInTheDocument()
    // o select mostra o rotulo da opcao escolhida
    expect(campo).toHaveTextContent(/Nenhuma/)
  })

  it("o upstream nao tem tabela recebida", () => {
    render(<Montar iniciais={{ tipo: "upstream", tabela: "" }} />)
    expect(screen.queryByLabelText(/Tabela recebida/)).not.toBeInTheDocument()
  })

  it("o membro de grupo nao escolhe tabela: ela e a do grupo", () => {
    render(<Montar iniciais={{ grupo_id: "3", tabela: "" }} />)
    expect(screen.queryByLabelText(/Tabela recebida/)).not.toBeInTheDocument()
  })
```

Se o componente de select do `Formulario` não for um `<select>` nativo, ajuste a forma de ler o valor seguindo um teste que já leia um select (`grep -n "Prepend base\|getByLabelText(/Classe" web/src/telas/peers/FormularioPeer.test.tsx`).

Em `FormularioGrupo.test.tsx`, o mesmo acréscimo ao `PLANO` e ao formulário de base do arquivo, e:

```tsx
  it("o grupo de downstream escolhe a tabela recebida", () => {
    render(<Montar />)
    expect(screen.getByLabelText(/Tabela recebida/)).toBeInTheDocument()
  })
```

(use o nome do componente de montagem que o arquivo já define). Em `PeerTela.test.tsx` e `GrupoTela.test.tsx`, acrescentar `tabela` aos fixtures de formulário (`"nenhuma"`) e de resumo de grupo (`tabela: "parcial"`), e `tabelas`/padrões ao `PLANO`, só para os tipos fecharem.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd web && npm test -- --run src/lib/campos.test.ts src/telas/peers/FormularioPeer.test.tsx src/telas/grupos/FormularioGrupo.test.tsx`
Expected: FAIL (campo inexistente, cascata escrevendo `"false"` em texto).

- [ ] **Step 3: Implementar**

`web/src/lib/campos.ts`:
- No tipo `Padroes`, a entrada de `tipos` passa a:

```ts
  tipos: Record<string, { lp_base: number | null; route_limit: number | null;
                          timer_keepalive: number | null; timer_hold: number | null;
                          default_route: boolean; tabela: string }>
```

- Em `CAMPOS_POR_TIPO`, depois de `default_route`: `tabela: ["cliente", "parceiro"],`.
- Em `SECOES_PEER`, na seção `limites`, depois de `"default_route"`: `"tabela"`. Em `SECOES_GRUPO`, na seção `politica`, depois de `"default_route"`: `"tabela"`.
- `CASCATA_PEER` e `CASCATA_GRUPO` ganham `"default_route", "tabela"` no fim.
- Na `cascata`, trocar `if (texto(valores[campo]) === texto(velho)) novo[campo] = texto(novoValor)` por:

```ts
      // a caixa da default e booleana: escrita como texto, o "false" viraria
      // uma caixa marcada
      if (texto(valores[campo]) === texto(velho)) {
        novo[campo] = typeof novoValor === "boolean" ? novoValor : texto(novoValor)
      }
```

- Exportar os rótulos:

```ts
// O rotulo de cada valor de plan.TABELAS. Os valores vem do /api/plano; um
// valor novo no plano sem rotulo aqui aparece com o proprio nome
export const ROTULO_TABELA: Record<string, string> = {
  nenhuma: "Nenhuma (só a default, se marcada)",
  parcial: "Parcial: rotas próprias e de clientes",
  parcial_ix: "Parcial + IX",
  full: "Full table",
}
```

`web/src/telas/peers/camposPeer.ts`: importar `ROTULO_TABELA` de `@/lib/campos` e, depois da linha do `default_route`:

```ts
  { nome: "tabela", rotulo: "Tabela recebida", tipo: "select", secao: "limites",
    ajuda: "a default route é a caixa acima e vai junto com qualquer tabela",
    opcoes: (ctx) => ctx.plano.tabelas.map((t) => ({ valor: t, rotulo: ROTULO_TABELA[t] ?? t })) },
```

No `CAMPO_BRANCO`: `default_route: true,` e acrescentar `tabela: "nenhuma",`.

`web/src/telas/grupos/camposGrupo.ts`: o mesmo campo, com `secao: "politica"` e sem mudar o `ajuda`; no `CAMPO_BRANCO_GRUPO`: `default_route: true,` e `tabela: "nenhuma",`.

`web/src/telas/peers/FormularioPeer.tsx`:
- Trocar a definição de `camposPorTipo` por:

```tsx
  const camposDaApi = Object.keys(plano.campos_por_tipo ?? {}).length > 0
    ? plano.campos_por_tipo
    : CAMPOS_POR_TIPO
```

e, depois de `const valores = useWatch(...)`:

```tsx
  // o membro de grupo nao escolhe tabela: o export dele chama o do grupo, e
  // o select dele nao mudaria nada no que e gerado
  const membro = String(valores.grupo_id ?? "") !== ""
  const camposPorTipo = membro ? { ...camposDaApi, tabela: [] } : camposDaApi
```

- No começo de `aoEditarCampo`, antes do `if (campo !== "tipo" && campo !== "asn") return`:

```tsx
    // entrar num grupo limpa a tabela, para o campo sumir; sair devolve o
    // padrao do downstream, que e o que o peer avulso recebe ao nascer
    if (campo === "grupo_id") {
      const downstream = plano.padroes.downstream.includes(String(valores.tipo ?? ""))
      form.setValue("tabela", String(valor ?? "") === "" && downstream ? "nenhuma" : "",
                    { shouldDirty: true })
      return
    }
```

`web/src/telas/peers/PeerTela.tsx`: no span que mostra `grupo {grupo.nome}` (perto da linha 393), trocar por:

```tsx
        {grupo && <span className="text-xs text-muted-foreground">
          grupo {grupo.nome}{plano.data?.padroes.downstream.includes(grupo.tipo)
            ? ` · tabela ${ROTULO_TABELA[grupo.tabela] ?? grupo.tabela}` : ""}
        </span>}
```

Confira o nome da variável da consulta do plano nessa tela (`grep -n "usePlano\|plano\." web/src/telas/peers/PeerTela.tsx | head`) e importe `ROTULO_TABELA`.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd web && npm test -- --run && npm run lint && npm run api:conferir`
Expected: PASS nos três.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "A tela escolhe a tabela recebida, e o membro herda a do grupo"
```

---

### Task 7: O documento do cliente

**Files:**
- Modify: `app/politica.py` (função nova e a tupla de `documento`, linha ~389)
- Test: `tests/test_politica.py`, `tests/test_pdf.py`

**Interfaces:**
- Consumes: nada novo (o texto não cita community).
- Produces: `Secao` com título `"O que você recebe de nós"`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_politica.py`, no fim (use o helper `texto(doc)` do arquivo):

```python
def test_o_documento_diz_o_que_o_cliente_pode_receber():
    doc = politica.documento(REDE)
    secao = next(s for s in doc.secoes if s.titulo == "O que você recebe de nós")
    corpo = " ".join(secao.textos)
    for trecho in ("default", "parcial", "IX", "full table"):
        assert trecho in corpo, trecho
    # a default combina com qualquer tabela, e e o que o cadastro novo recebe
    assert "junto com qualquer" in corpo
```

Em `tests/test_pdf.py`, no fim, seguindo `test_o_pdf_diz_que_a_restricao_padronizada_e_honrada`:

```python
def test_o_pdf_diz_o_que_o_cliente_recebe():
    texto = secao("O que você recebe de nós")
    assert "full table" in texto
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_politica.py tests/test_pdf.py -q -k recebe`
Expected: FAIL com `StopIteration` / seção ausente.

- [ ] **Step 3: Implementar**

Em `app/politica.py`, depois de `_anuncio`:

```python
def _recebido(rede):
    # o que a sessao entrega e combinado na contratacao, e nao pedido por
    # community: a secao diz as opcoes, e nao como pedir cada uma
    return Secao(
        titulo="O que você recebe de nós",
        textos=(
            "A sessão BGP com o AS%s entrega uma destas tabelas, combinada "
            "na contratação: só a rota default; a tabela parcial, com os "
            "prefixos do AS%s e dos nossos clientes; a parcial com as rotas "
            "que aprendemos no IX; ou a full table." % (rede.ASN, rede.ASN),
            "A rota default (0.0.0.0/0 e ::/0) vai junto com qualquer uma "
            "delas quando contratada. Sem pedido em contrário, a sessão nova "
            "recebe só a default.",
        ),
        tabelas=(),
    )
```

Na tupla `secoes` de `documento`, entre `_anuncio(rede),` e `_prepend(rede),`: `_recebido(rede),`.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_politica.py tests/test_pdf.py -q`
Expected: PASS (inclui `test_nenhum_canto_do_pdf_mostra_o_namespace_de_fabrica`).

- [ ] **Step 5: Commit**

```bash
git add app/politica.py tests/test_politica.py tests/test_pdf.py
git commit -m "O documento do cliente diz qual tabela a sessao entrega"
```

---

### Task 8: O PLANO

**Files:**
- Modify: `PLANO.md` (parágrafo da linha ~96; seção "Export" do exemplo de cliente, linha ~1200; seção "Aplicação" do mesmo exemplo, linha ~1249; tabela pública, linha ~1978)

**Interfaces:** nenhuma; é texto.

- [ ] **Step 1: Trocar o parágrafo da lacuna**

Em `PLANO.md`, substituir o parágrafo que começa com "Fora isso, o egress de cliente não tem gate nenhum" por:

```markdown
Fora isso, o que o egress de cliente entrega depende da tabela contratada, que é um campo do cadastro de cada cliente e de cada parceiro. São quatro modos. Na `full`, o filtro termina em `finish` depois dos vetos e a full table sai inteira, que é o caso do cliente de trânsito do exemplo adiante. Na `parcial`, um portão depois dos vetos recusa o que não carrega `CL-ORIGEM-ANUNCIAVEL`, a mesma lista do `EXPORT-SANITY`: sai só a rota própria e a de cliente. Na `parcial_ix`, o portão usa a `CL-ORIGEM-PARCIAL-IX`, que é a anunciável mais o `64512:1300` que o import do IX carimba; rota de upstream e de PNI continuam fora. Na `nenhuma`, o filtro só tem `refuse`. A default route é outro campo, independente da tabela: o `peer <ip> default-route-advertise` da sessão. O cadastro novo nasce com a default e sem tabela; o cadastro gravado antes do campo existir é lido como `full`, para não mudar de saída.
```

- [ ] **Step 2: Nota no exemplo do cliente de trânsito**

Logo depois do bloco `scss` do `CUST-EXPORT-268127` (antes do parágrafo "Nenhum egress deste documento limpa..."), acrescentar o texto abaixo (a cerca de fora, `~~~`, é só do plano e não vai para o PLANO):

~~~markdown
O exemplo é o modo `full`. Nos modos `parcial` e `parcial_ix`, o filtro ganha um portão entre o último veto e o prepend:

```scss
 !- tabela parcial: so rota propria e de cliente (na parcial_ix, a lista
 !- e a CL-ORIGEM-PARCIAL-IX, que inclui a aprendida no IX)
 if not community matches-any CL-ORIGEM-ANUNCIAVEL then
  refuse
 endif
```

No modo `nenhuma` o corpo do filtro é só `refuse`, e a sessão recebe apenas a default, se ela estiver ligada.
~~~

- [ ] **Step 3: A default route na seção Aplicação**

Depois do parágrafo do `public-as-only force`, acrescentar:

```markdown
A default route sai pela sessão, e não pelo filtro: `peer 198.51.100.2 default-route-advertise` dentro da família. O VRP origina `0.0.0.0/0` e `::/0` nessa sessão mesmo quando não há default na RIB nem na FIB, e o anúncio não passa pelo route-filter de export, então nenhum `refuse` do filtro a segura. Comportamento confirmado no equipamento. É por isso que o modo `nenhuma` pode recusar tudo no export e a sessão continua recebendo a default.
```

- [ ] **Step 4: A tabela pública**

Na "Tabela pública para clientes", antes de "**Informativas que você recebe de nós**", acrescentar:

```markdown
**O que você recebe de nós**

A sessão BGP entrega uma destas tabelas, combinada na contratação: só a rota default; a tabela parcial, com os prefixos do AS64512 e dos nossos clientes; a parcial com as rotas que aprendemos no IX; ou a full table. A rota default (`0.0.0.0/0` e `::/0`) vai junto com qualquer uma delas quando contratada. Sem pedido em contrário, a sessão nova recebe só a default.
```

- [ ] **Step 5: Conferir consistência e ASCII dos blocos**

```bash
grep -n "falta o ramo correspondente" PLANO.md   # Expected: nada
grep -n "CL-ORIGEM-PARCIAL-IX" PLANO.md          # Expected: o parágrafo, o exemplo
.venv/bin/python - <<'EOF'
import re
texto = open("PLANO.md", encoding="utf-8").read()
for bloco in re.findall(r"```scss\n(.*?)```", texto, re.S):
    assert bloco.isascii(), bloco[:80]
print("blocos ascii")
EOF
.venv/bin/python -m pytest -q
```

Expected: o `grep` da lacuna vazio, os blocos ASCII, a suíte passando (algum teste pode ler o PLANO; se falhar, leia o teste antes de mexer no texto).

- [ ] **Step 6: Commit**

```bash
git add PLANO.md
git commit -m "O PLANO descreve a tabela recebida e a default fora do filtro"
```

---

### Task 9: Fechamento

- [ ] **Step 1: Suítes completas**

```bash
.venv/bin/python -m pytest -q
cd web && npm test -- --run && npm run lint && npm run api:conferir && cd ..
graphify update .
```

Expected: tudo PASS. O e2e do Playwright (`npm run e2e`) depende do `playwright install`, que falha nesta rede (o chromium sai do Google Storage); registre que ele não rodou em vez de dizer que passou.

- [ ] **Step 2: Conferir o cadastro real**

```bash
.venv/bin/python - <<'EOF'
from app import peers, render, plan
for p in peers.carregar("peers/264130.yaml"):
    if p.tipo in plan.TIPOS_DOWNSTREAM:
        print(p.nome, p.tabela, p.default_route)
EOF
```

Expected: os dois parceiros com `full`, um com `True` e outro com `False`, como antes.

- [ ] **Step 3: Commit do que sobrar (graph do graphify, se versionado)**

```bash
git status --short
```

Se só aparecer `graphify-out/`, confira se ele é versionado (`git ls-files graphify-out | head -1`) e commite junto com uma mensagem curta; se não for, deixe como está.
