# Grupo de upstream, IX e PNI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o `bgpgen` aceitar grupo dos cinco tipos de peer, extraindo o miolo dos templates de upstream, IX e PNI para macros de alvo duplo e compartilhando o espaço de identificadores entre peers e grupos.

**Architecture:** O `Grupo` ganha os cinco campos que ainda faltam e passa a ser um alvo válido para as mesmas macros que o `Peer` usa. O miolo dos três templates de peer vira macro (`filtro_upstream_import`, `listas_ix`, e assim por diante), o template de peer passa a chamar as macros e um template de grupo novo por tipo chama as mesmas. `plan.c5ppa` já reserva 100 identificadores compartilhados, então `MAX_PEERS`/`MAX_GRUPOS` viram um `MAX_IDS` só e a colisão passa a ser recusada na validação nos dois sentidos.

**Tech Stack:** Python 3.14, FastAPI, Jinja2, pytest, `peers.yaml` como único estado. O interpretador da venv é `.venv/bin/python`; `python` puro não existe nesta máquina. Rodar teste é `.venv/bin/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-09-22-grupos-multitipo-design.md`

## Global Constraints

- **Comando de teste:** `.venv/bin/python -m pytest` da raiz do repositório. A suite tem 377 testes verdes e eles são a rede da mudança.
- **Byte a byte:** o texto que `render_peer` gera para `upstream`, `ix` e `pni` não pode mudar com a extração de macros. Os goldens em `tests/golden/{upstream,ix,pni}.txt` são o contrato, e não são para editar.
- **ASCII puro no que é gerado:** nenhum template, macro ou comentário XPL pode ganhar acento. `test_a_remocao_e_ascii_em_todos_os_tipos` cobre parte disso; a escrita de arquivo usa `encoding="ascii"` e estoura se entrar.
- **Nada de `$` no texto gerado:** os filtros XPL usam `{% if %}` do Jinja, nunca sintaxe de shell.
- **Framing de `!-` preservado:** comentário que hoje diz "confirmar com `xpl simulate`" ou "verificar no equipamento" continua dizendo isso. Não promover a fato.
- **`trim_blocks=True` e `lstrip_blocks=True`** no `ambiente()` de `app/render.py:21`. Bloco Jinja em linha própria come a própria quebra de linha, então a linha em branco depois dele é o que separa dois objetos no texto gerado. Macro abre com `{% macro ... -%}` e fecha com uma linha em branco e `{% endmacro %}`.
- **Nome de objeto XPL:** `<PREFIXO>-<token ou nome do alvo>-<SUFIXO>`. O token de um `Peer` é o ASN ou o apelido; o token de um `Grupo` é o nome (`Grupo.token` devolve `self.nome`).
- **Não inventar estrutura:** o `_macros.j2` já tem o padrão de alvo duplo (`prefix_lists_downstream`, `ap_cust_downstream`, `filtro_downstream_import`). Extensão dele, não paralelo novo.
- **Escopo de `plan.TIPOS_DOWNSTREAM`:** `("cliente", "parceiro")`. Checagem que só faz sentido em downstream continua presa nele, dentro do ramo.

---

## File Structure

| Arquivo | Papel nesta mudança |
| --- | --- |
| `app/peers.py` | `MAX_IDS` no lugar de `MAX_PEERS`/`MAX_GRUPOS`; `proximo_id` passa a receber as duas listas; `proximo_id_grupo` sai; `Grupo` ganha cinco campos |
| `app/plan.py` | não muda. `MAX_IDS` mora em `peers.py`, junto dos outros limites de cadastro |
| `app/validate.py` | `TIPOS_COM_GRUPO` sai; `validar_grupo` ganha faixa de id, colisão com peer e os ramos por tipo; `validar` ganha a colisão recíproca |
| `app/render.py` | `render_criar_lista_grupo` novo. `TEMPLATE_POR_TIPO_GRUPO` não muda |
| `app/app.py` | quatro sítios de `proximo_id`, `peer_do_formulario` e `grupo_do_formulario` ganham as duas listas; campos novos no `grupo_do_formulario`; `_contexto_grupo` passa `PADROES` e `TIPOS`; rota `/saida/grupo/{nome}/criar-lista` |
| `templates/_macros.j2` | sete macros novas para upstream, IX e PNI |
| `templates/upstream.txt.j2` | encolhe para ~26 linhas, chamando as macros |
| `templates/ix.txt.j2` | idem |
| `templates/pni.txt.j2` | idem |
| `templates/grupo_upstream.txt.j2` | novo |
| `templates/grupo_ix.txt.j2` | novo |
| `templates/grupo_pni.txt.j2` | novo |
| `templates/cliente.txt.j2` | ramo de membro perde a condição `peer.tipo == "cliente"` no `route-limit` |
| `templates/remover.txt.j2` | ramos de upstream/IX/PNI passam a valer também para membro |
| `templates/criar_lista.txt.j2` | vira dual-alvo (`peer` ou `grupo`) |
| `templates/pagina_grupo.html` | campos por tipo, `select` de origem, JS da cascata, link do quadro "ao criar" |
| `tests/test_peers.py` | testes do alocador compartilhado |
| `tests/test_validate.py` | colisão nos dois sentidos e as regras por tipo |
| `tests/test_render.py` | grupo por tipo, membro por tipo, `route-limit`, quadro "ao criar" |
| `tests/test_app.py` | POST de grupo por tipo, form por tipo, colisão pela tela |
| `PLANO.md` | seção de identificador compartilhado e a de grupo nos cinco tipos |

---

## Task 1: Espaço de identificadores compartilhado

O eixo `plan.c5ppa` monta `"64512:5%02d%d"`: dois dígitos de identificador e um de papel. São 100 slots, e peer e grupo disputam os mesmos. Hoje cada alocador começa do zero sobre o próprio conjunto, e o `peers.yaml` já tem a colisão: peer 0 `BRDIGITAL-20G` e grupo 0 `PARCEIROS`.

**Files:**
- Modify: `app/peers.py:28-29` (constantes), `app/peers.py:182-186` (`proximo_id`), `app/peers.py:276-280` (`proximo_id_grupo`, sai)
- Modify: `app/validate.py:207-235` (`TIPOS_COM_GRUPO` fica para a Task 8; aqui entra só o id), `app/validate.py:379-405` (colisão recíproca em `validar`)
- Modify: `app/app.py:159-199` (`peer_do_formulario`), `app/app.py:250-283` (`grupo_do_formulario`), `app/app.py:364` (`novo`), `app/app.py:539` (`grupo_novo`), `app/app.py:387` (`salvar`)
- Modify: `peers.yaml` (renumerar o grupo `PARCEIROS`)
- Test: `tests/test_peers.py`, `tests/test_validate.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `plan.c5ppa(peer_id, digito)` (inalterado), `plan.TIPOS_DOWNSTREAM` (inalterado)
- Produces: `peers.MAX_IDS = 100`; `peers.proximo_id(peers, grupos=())`; `validate.validar_grupo(grupo, grupos, peers, anterior=None)` recusando id fora de 0-99 e id de peer; `validate.validar(peer, peers, anterior=None, grupos=None)` recusando id de grupo

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_peers.py`, substituir `test_proximo_id_grupo_acha_o_primeiro_livre` (linha 190) por:

```python
def test_proximo_id_desvia_do_grupo():
    # o eixo 5PPA tem dois digitos (plan.c5ppa), entao peer e grupo
    # disputam os mesmos 100 numeros
    grupos = [mod.Grupo(id=0, nome="A"), mod.Grupo(id=2, nome="B")]
    assert mod.proximo_id([], grupos) == 1


def test_proximo_id_desvia_do_peer_e_do_grupo_juntos():
    a = mod.Peer(id=1, nome="a", tipo="cliente", asn=1)
    g = mod.Grupo(id=2, nome="G")
    assert mod.proximo_id([a], [g]) == 0


def test_proximo_id_sem_grupo_continua_do_zero():
    # chamada de dois argumentos tem que seguir valendo: os testes de peer
    # que ja existem chamam assim
    assert mod.proximo_id([]) == 0


def test_proximo_id_grupo_estoura_quando_nao_ha_vaga():
    cheio = [mod.Grupo(id=i, nome="G%d" % i) for i in range(100)]
    with pytest.raises(ValueError):
        mod.proximo_id([], cheio)
```

`test_proximo_id_estoura_quando_nao_ha_vaga` (linha 16) fica como está.

Em `tests/test_validate.py`, acrescentar (o arquivo já tem `um_peer()` na linha 5):

```python
def test_grupo_recusa_id_de_peer():
    grupo = Grupo(id=3, nome="G", tipo="cliente", classe="transito",
                  origem=1100, pop=2001)
    peer = um_peer()
    peer.id = 3
    erros = validar_grupo(grupo, [grupo], [peer], anterior=grupo)
    assert ("id", "ID 3 ja usado pelo peer %s" % peer.nome) in [
        (e.campo, e.msg) for e in erros]


def test_peer_recusa_id_de_grupo():
    grupo = Grupo(id=7, nome="PARCEIROS", tipo="parceiro")
    peer = um_peer()
    peer.id = 7
    erros = validar(peer, [peer], anterior=peer, grupos=[grupo])
    assert ("id", "ID ja usado pelo grupo PARCEIROS") in [
        (e.campo, e.msg) for e in erros]


def test_grupo_recusa_id_fora_da_faixa():
    # o %02d do plan.c5ppa trunca calado: um id 100 vira o 00 de outro
    for ident in (-1, 100):
        grupo = Grupo(id=ident, nome="G", tipo="cliente", classe="transito",
                      origem=1100, pop=2001)
        erros = validar_grupo(grupo, [grupo], [], anterior=grupo)
        assert "id" in [e.campo for e in erros], ident
```

Conferir o import do topo de `tests/test_validate.py`: precisa de `Grupo`, `validar` e `validar_grupo` de `app.validate` e `app.peers`.

Em `tests/test_app.py`, acrescentar:

```python
def test_o_formulario_de_grupo_novo_nao_reusa_o_id_de_um_peer(cliente, tmp_path):
    # o peers.yaml de verdade ja tem essa colisao (peer 0 e grupo 0). O
    # formulario em branco tem que desviar dela, e nao criar mais uma.
    salvar(cliente)
    r = cliente.get("/grupo/novo")
    assert 'name="id" value="1"' in r.text


def test_salvar_grupo_com_id_de_peer_e_recusado(cliente, tmp_path):
    salvar(cliente)
    r = cliente.post("/grupo", data={"nome": "PARCEIROS", "tipo": "parceiro",
                                     "id": "0", "classe": "transito",
                                     "origem": "1100", "pop": "2001"})
    assert "ja usado pelo peer" in r.text
```

O primeiro `salvar(cliente)` grava o `CLIENTE` de `tests/test_app.py:11`, que usa `asn: "268127"` e cai no id 0. O grupo novo tem que receber 1.

- [ ] **Step 2: Rodar os testes e confirmar que falham**

```bash
.venv/bin/python -m pytest tests/test_peers.py -k proximo_id -v
```

Esperado: `test_proximo_id_desvia_do_grupo` e os dois vizinhos estouram com `TypeError: proximo_id() takes 1 positional argument but 2 were given`. Os de `test_validate.py` falham com `AttributeError` ou asserção vazia. O de `test_app.py` falha porque o `id` do grupo em branco sai 0.

- [ ] **Step 3: Trocar as constantes e o alocador em `app/peers.py`**

Substituir as linhas 28-29:

```python
MAX_IDS = 100
```

Substituir `proximo_id` (linha 182):

```python
def proximo_id(peers, grupos=()):
    """O primeiro identificador livre nas duas listas.

    O eixo 64512:5PPA tem dois digitos de identificador e um de papel
    (plan.c5ppa), entao sao 100 numeros e peer e grupo disputam os mesmos:
    alocar cada um sobre o proprio conjunto dava o mesmo numero aos dois, e
    a partir dai duas politicas escrevem a mesma community.
    """
    usados = {p.id for p in peers} | {g.id for g in grupos}
    for i in range(MAX_IDS):
        if i not in usados:
            return i
    raise ValueError("sem ID livre: a faixa 0-99 esta cheia")
```

Apagar `proximo_id_grupo` (linhas 276-280) inteiro.

- [ ] **Step 4: Rodar os testes de `peers` e ver passar**

```bash
.venv/bin/python -m pytest tests/test_peers.py -v
```

Esperado: PASS. `test_proximo_id_grupo_acha_o_primeiro_livre` já saiu no Step 1.

- [ ] **Step 5: Ligar a colisão na validação dos dois lados**

Em `app/validate.py`, dentro de `validar_grupo`, logo depois da checagem de `nome` (antes da checagem de `tipo`, que continua `TIPOS_COM_GRUPO` até a Task 8):

```python
    if not (0 <= grupo.id <= 99):
        erros.append(Erro("id", "o ID do grupo tem que ficar entre 0 e 99"))
    for outro in peers:
        if outro.id == grupo.id:
            # o espaco e um so: um grupo e um peer no mesmo numero escrevem
            # a mesma community do eixo 5PPA
            erros.append(Erro(
                "id", "ID %d ja usado pelo peer %s" % (grupo.id, outro.nome)))
```

Em `validar` (o do peer), junto do laço de colisão que já existe perto da linha 395, antes do `if outro.id == peer.id`:

```python
    for outro in grupos or []:
        if outro.id == peer.id:
            erros.append(Erro("id", "ID ja usado pelo grupo %s" % outro.nome))
```

- [ ] **Step 6: Rodar a validação e ver passar**

```bash
.venv/bin/python -m pytest tests/test_validate.py -v
```

Esperado: PASS.

- [ ] **Step 7: Passar as duas listas para os quatro sítios do `app.py`**

`peer_do_formulario` (linha 159) ganha o parâmetro e o usa na linha 197:

```python
def peer_do_formulario(dados, peers, anterior=None, grupos=()):
```

```python
        ident = anterior.id if anterior else peers_mod.proximo_id(peers, grupos)
```

`grupo_do_formulario` (linha 250) ganha o parâmetro e o usa na linha 281:

```python
def grupo_do_formulario(dados, grupos, anterior=None, peers=()):
```

```python
        ident = anterior.id if anterior else peers_mod.proximo_id(peers, grupos)
```

Na linha 387 (`salvar`), a chamada vira:

```python
    grupos = peers_mod.carregar_grupos(PEERS_YAML)
    peer, erros = peer_do_formulario(dados, peers, antigo, grupos=grupos)
```

e a linha que hoje recarrega os grupos para o `validar` (linha 392) passa a usar essa mesma variável:

```python
    erros = erros + validate.validar(peer, peers, anterior=antigo, grupos=grupos)
```

Na linha 364 (`novo`):

```python
    peer = Peer(tipo=tipo, id=peers_mod.proximo_id(lista(), lista_grupos()),
```

Na linha 539 (`grupo_novo`):

```python
    grupo = Grupo(tipo="parceiro", id=peers_mod.proximo_id(lista(), lista_grupos()),
```

Na linha 561 (`grupo_salvar`), a chamada vira:

```python
    grupo, erros = grupo_do_formulario(dados, grupos, anterior, peers=lista())
```

- [ ] **Step 8: Rodar a suite inteira**

```bash
.venv/bin/python -m pytest -q
```

Esperado: PASS. Nenhum teste de `test_app.py` deve estourar: a fixture `cliente` (linha 24) já aponta `PEERS_YAML` para `tmp_path`, então o arquivo de verdade não entra.

- [ ] **Step 9: Renumerar o grupo `PARCEIROS` no `peers.yaml`**

O arquivo de verdade tem peer 0 e grupo 0. Com a colisão ligada, salvar qualquer um dos dois pela tela passa a ser recusado, então a renumeração entra junto. Editar `peers.yaml`, no bloco `grupos:`:

```yaml
- id: 1
  nome: PARCEIROS
```

O id do grupo só aparece hoje no comentário de cabeçalho que `cabecalho_grupo` emite, então a renumeração não muda uma linha de configuração do equipamento. Confirmar:

```bash
grep -n "^  id:" peers.yaml && .venv/bin/python -c "
from app import app as m
print([p.id for p in m.lista()], [g.id for g in m.lista_grupos()])"
```

Esperado: `[0, 10] [1]`. Regenerar o bloco do grupo para o cabeçalho acompanhar:

```bash
.venv/bin/python -c "
from app import app as m, render
render.escrever_grupo(m.lista_grupos()[0])" && head -3 out/grupo-PARCEIROS.txt
```

Esperado: `# grupo 1 - parceiro - nome PARCEIROS`.

- [ ] **Step 10: Commit**

```bash
git add app/peers.py app/validate.py app/app.py peers.yaml out/grupo-PARCEIROS.txt \
        tests/test_peers.py tests/test_validate.py tests/test_app.py
git commit -m "Um espaco de ids so para peer e grupo, com colisao recusada"
```

---

## Task 2: Os cinco campos que faltam no Grupo

Cruzando o que cada template lê contra o dataclass, faltam `aprendizado`, `ix_id` (IX e upstream), `te_prefixos` (upstream) e o par `communities`/`large_communities` (o `APPLY-PEER` de upstream). `de_dict` já filtra por `__dataclass_fields__`, então o `peers.yaml` de hoje carrega sem migração.

**Files:**
- Modify: `app/peers.py:210-256` (dataclass `Grupo` e `para_dict`)
- Test: `tests/test_peers.py`

**Interfaces:**
- Produces: `Grupo.aprendizado: int | None`, `Grupo.ix_id: int | None`, `Grupo.te_prefixos: dict` (por família, via `_listas_por_familia`), `Grupo.communities: list`, `Grupo.large_communities: list`, todos em `para_dict()`

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_peers.py`, junto dos testes de round-trip que já existem:

```python
def test_round_trip_do_grupo_leva_os_campos_dos_cinco_tipos(tmp_path):
    # o de_dict filtra por __dataclass_fields__, entao campo novo no
    # dataclass entra no round-trip sozinho - o que este teste trava e o
    # para_dict, que e escrito a mao
    caminho = tmp_path / "peers.yaml"
    g = mod.Grupo(
        id=3, nome="TRANSITO", tipo="upstream", asn=14840,
        aprendizado=3100, te_prefixos={"v4": ["1.1.1.0/24"], "v6": []},
        ap_block=[64500], ap_te=[64501], bh_upstream="14840:666",
        communities=["14840:9133"], large_communities=["14840:1:3333"])
    mod.gravar_grupos([g], caminho)
    assert mod.carregar_grupos(caminho) == [g]
    assert mod.carregar_grupos(caminho)[0].te_prefixos == {
        "v4": ["1.1.1.0/24"], "v6": []}


def test_grupo_antigo_no_yaml_carrega_com_os_defaults_novos(tmp_path):
    # o peers.yaml gravado antes desta mudanca nao tem os campos novos
    caminho = tmp_path / "peers.yaml"
    caminho.write_text(
        "grupos:\n- id: 1\n  nome: VELHO\n  tipo: parceiro\n", encoding="ascii")
    g = mod.carregar_grupos(caminho)[0]
    assert (g.aprendizado, g.ix_id, g.communities, g.large_communities) == (
        None, None, [], [])
    assert g.te_prefixos == {"v4": [], "v6": []}
```

- [ ] **Step 2: Rodar e confirmar que falha**

```bash
.venv/bin/python -m pytest tests/test_peers.py -k grupo -v
```

Esperado: `TypeError: Grupo.__init__() got an unexpected keyword argument 'aprendizado'`.

- [ ] **Step 3: Acrescentar os campos ao dataclass**

Em `app/peers.py`, no `Grupo`, depois de `pop`:

```python
    # so upstream e ix: o 3xxx do ponto de aprendizado, que o import carimba
    # na rota. O design anterior ja o listava na tabela do Grupo; a
    # implementacao nao o criou.
    aprendizado: int | None = None
    # so ix: o id do IX no PeeringDB, que vira a large-community 1001:<ix_id>
    ix_id: int | None = None
```

e depois de `prefixos`:

```python
    # excecoes de TE do upstream: prefixos que se alcanca melhor pela borda
    # deste transito
    te_prefixos: dict = field(default_factory=_listas_por_familia)
    # o conteudo da CL-PEER-<G> / LC-PEER-<G>. Para um upstream a community
    # descreve a REDE REMOTA, nao o link: dois links para o mesmo transito
    # levam a mesma, e repeti-la por membro e a duplicacao que o grupo
    # existe para eliminar (ver "Modelo de dados" da spec).
    communities: list = field(default_factory=list)
    large_communities: list = field(default_factory=list)
```

- [ ] **Step 4: Acrescentar os campos ao `para_dict`**

Em `para_dict` do `Grupo`, acrescentar as cinco chaves:

```python
            "aprendizado": self.aprendizado, "ix_id": self.ix_id,
            "te_prefixos": self.te_prefixos,
            "communities": self.communities,
            "large_communities": self.large_communities,
```

- [ ] **Step 5: Rodar e ver passar**

```bash
.venv/bin/python -m pytest tests/test_peers.py -q && .venv/bin/python -m pytest -q
```

Esperado: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/peers.py tests/test_peers.py
git commit -m "Grupo ganha aprendizado, ix_id, te_prefixos e o par de communities"
```

---

## Task 3: Extrair o miolo do upstream para macros de alvo duplo

Tarefa de refatoração pura. Nenhum texto gerado muda: os cinco goldens que citam upstream (`upstream.txt` e `remover-upstream.txt`) são o contrato.

O miolo sai em quatro macros. `filtro_upstream_import` e `filtro_upstream_export` viram filtros por família; `te_prefix_list` é a `PL-TE-PREFER` que nasce **dentro** do laço de família (`upstream.txt.j2:8-16`, único objeto do arquivo com eixo de família além dos dois filtros); `listas_upstream` é o resto, tudo sem eixo de família (`CL-NOADV`, `LC-NOADV`, `CL-5PPA`, `LC-5PPA`, `LC-PREP1/2/3`, `AP-BLOCK`, `AP-TE-PREFER`).

**Files:**
- Modify: `templates/_macros.j2` (append das quatro macros)
- Modify: `templates/upstream.txt.j2` (reescrito)
- Test: `tests/test_render.py:633` (`test_golden_do_upstream`), `tests/test_render.py:1092` (`test_golden_da_remocao_do_upstream`)

**Interfaces:**
- Consumes: `alvo.token`, `alvo.id`, `alvo.asn`, `alvo.origem`, `alvo.lp_base`, `alvo.aprendizado`, `alvo.te_prefixos`, `alvo.ap_block`, `alvo.ap_te`, `alvo.bh_upstream`, `alvo.prepend_base`; `plan.c5ppa`, `plan.c6ca`, `plan.c_large`, `plan.conjunto`, `plan.CLASSE_6CA`, `plan.LP_TE_PREFER`
- Produces: `m.te_prefix_list(alvo, fam)`, `m.filtro_upstream_import(alvo, fam)`, `m.filtro_upstream_export(alvo, fam, chamar_apply_peer)`, `m.listas_upstream(alvo)`
- **Não pode referenciar** `sessoes`, `familias()`, `route_limit` nem `descricao`: são do peer e o `Grupo` não os tem. `StrictUndefined` está ligado, então um nome errado estoura no teste, não na config.

- [ ] **Step 1: Registrar o estado de partida**

```bash
.venv/bin/python -m pytest tests/test_render.py -q
```

Esperado: PASS. Este é o verde que a extração não pode derrubar.

- [ ] **Step 2: Acrescentar as quatro macros ao fim de `templates/_macros.j2`**

```jinja
{# O miolo do bloco de upstream, em macro de alvo duplo: o Peer avulso e o
   Grupo passam os dois, porque o grupo de upstream existe justamente para
   que dois links do mesmo transito nao guardem a mesma politica em dois
   lugares. So o que os dois tem pode aparecer aqui: token, id, asn, origem,
   lp_base, aprendizado, te_prefixos, ap_block, ap_te, bh_upstream e
   prepend_base. sessoes, familias(), route_limit e descricao sao do peer e
   ficam de fora - o StrictUndefined do render estoura no teste se algum
   entrar. #}
{% macro te_prefix_list(alvo, fam) -%}
{% set U = fam|upper %}
{% set kw = "ipv6-prefix-list" if fam == "v6" else "ip-prefix-list" %}
{% set maxlen = 48 if fam == "v6" else 24 %}
{% if alvo.te_prefixos[fam] %}
!- conteudo de EXEMPLO no PLANO: troque pelos prefixos reais antes de subir
xpl {{ kw }} PL-TE-PREFER-{{ alvo.token }}-{{ U }}
{% for cidr in alvo.te_prefixos[fam] %}
 {{ plan.cidr_para_xpl(cidr) }} le {{ maxlen }}{{ "," if not loop.last }}
{% endfor %}
end-list

{% endif %}
{%- endmacro %}

{% macro filtro_upstream_import(alvo, fam) -%}
{% set U = fam|upper %}
xpl route-filter UP-{{ alvo.token }}-IMPORT-{{ U }}
 call route-filter IMPORT-SANITY-{{ U }}
{% if alvo.ap_block %}
 if as-path matches-any AP-BLOCK-{{ alvo.token }} then
  refuse
 endif
{% endif %}
 apply local-preference {{ alvo.lp_base }}
 {# overwrite: nada do que o upstream escreveu em community sobrevive. e o que
    torna seguro o matches-any CL-ORIGEM-ANUNCIAVEL no export. 2000 marca
    "aprendida de fora", e o export de outro upstream recusa. #}
 apply community {{ plan.conjunto("64512:%d" % alvo.origem, "64512:%d" % alvo.aprendizado, "64512:2000") }} overwrite
 apply large-community {{ plan.conjunto(plan.c_large(1000, alvo.asn)) }} overwrite
{% if alvo.te_prefixos[fam] or alvo.ap_te %}
 {# excecoes de TE, aplicadas depois do carimbo base. Se a lista ficar vazia a
    excecao simplesmente nao existe; o risco e o oposto, prefixo errado faz o
    trafego sair e voltar. #}
 if{% if alvo.te_prefixos[fam] %} ip route-destination in PL-TE-PREFER-{{ alvo.token }}-{{ U }}{% endif %}{% if alvo.te_prefixos[fam] and alvo.ap_te %} or{% endif %}{% if alvo.ap_te %} as-path matches-any AP-TE-PREFER-{{ alvo.token }}{% endif %} then
  apply local-preference {{ plan.LP_TE_PREFER }}
 endif
{% endif %}
 approve
end-filter
{%- endmacro %}

{% macro filtro_upstream_export(alvo, fam, chamar_apply_peer) -%}
{% set U = fam|upper %}
xpl route-filter UP-{{ alvo.token }}-EXPORT-{{ U }}
 {# 1. blackhole primeiro: finish para nao cair no EXPORT-SANITY. O overwrite
    aqui nao e limpeza: e a definicao do anuncio de blackhole. Durante ataque
    o host sai com a community de blackhole deste upstream e nada mais, para
    que nenhuma community escrita pelo cliente a neutralize. #}
 if (community matches-any CL-BLACKHOLE or tag eq 666) and ip route-destination in {{ "{0.0.0.0 0 ge 32 le 32}" if fam == "v4" else "{:: 0 ge 128 le 128}" }} then
  if community matches-any CL-BLACKHOLE-PROPAGATE then
{% if alvo.bh_upstream %}
   apply community {{ plan.conjunto(alvo.bh_upstream) }} overwrite
{% endif %}
   finish
  else
   refuse
  endif
 endif
 {# 2. sanidade antes de liberar a rota #}
 call route-filter EXPORT-SANITY
 {# 3. rede de seguranca do 2000: rota aprendida de fora ja caiu acima, entao
    isto so alcanca rota de cliente que escreveu o 2000 sozinha. #}
 if community matches-any {{ plan.conjunto("64512:2000") }} then
  refuse
 endif
 {# 4. escopo pedido pelo cliente para este peer #}
 if community matches-any CL-NOADV-{{ alvo.token }} or large-community matches-any LC-NOADV-{{ alvo.token }} then
  refuse
 endif
 {# 5. somente para outro peer #}
 if community matches-any CL-ONLY-NOT-UP then
  refuse
 endif
 {# 6. 5PPA por peer especifico: P4=3x, P3=2x, P2=1x. Se veio QUALQUER 5PPA do
    peer, a classe 6CA nao entra: especifico vence generico. O P1 explicito so
    impede a classe, e por isso o aninhamento e if/elseif e nao finish, que
    saltaria os passos 8 e 9. #}
 if community matches-any CL-5PPA-{{ "%02d"|format(alvo.id) }} or large-community matches-any LC-5PPA-{{ alvo.token }} then
  if community matches-any {{ plan.conjunto(plan.c5ppa(alvo.id, 4)) }} or large-community matches-any LC-PREP3-{{ alvo.token }} then
   apply as-path 64512 3 additive
  elseif community matches-any {{ plan.conjunto(plan.c5ppa(alvo.id, 3)) }} or large-community matches-any LC-PREP2-{{ alvo.token }} then
   apply as-path 64512 2 additive
  elseif community matches-any {{ plan.conjunto(plan.c5ppa(alvo.id, 2)) }} or large-community matches-any LC-PREP1-{{ alvo.token }} then
   apply as-path 64512 1 additive
  endif
 else
  {# 7. sem 5PPA, vale a classe 6CA (plan.CLASSE_6CA["upstream"] = upstream) #}
  if community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["upstream"], 4)) }} then
   apply as-path 64512 3 additive
  elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["upstream"], 3)) }} then
   apply as-path 64512 2 additive
  elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["upstream"], 2)) }} then
   apply as-path 64512 1 additive
  endif
 endif
{% if alvo.prepend_base %}
 {# 8. prepend base de engenharia: o valor JA E o numero de prepends, entao a
    linha nao sai quando ele e zero. #}
 apply as-path 64512 {{ alvo.prepend_base }} additive
{% endif %}
 {# 9. saida comum #}
 apply med 0
{# chamar_apply_peer=false: o bloco de um GRUPO nao aplica a CL-PEER por
   membro - o grupo tem a dele, e o membro sem filtro proprio nao tem nenhuma
   - entao quem decide e o caller, com o mesmo sinal que o filtro de
   downstream ja usa. #}
{% if chamar_apply_peer %}
 {# ULTIMA acao: as communities do cadastro deste upstream, para tudo que sai
    por ele. O quadro "ao criar o peer" traz o conteudo da lista; aqui so a
    chamada. #}
 call route-filter APPLY-PEER-{{ alvo.token }}
{% endif %}
 finish
end-filter
{%- endmacro %}

{% macro listas_upstream(alvo) -%}
{# um set por peer: evita cadeia de OR na condicao. o 5xx aqui e o alias 5PPA
   do "nao anunciar para o peer". #}
xpl community-list CL-NOADV-{{ alvo.token }}
{% for c in plan.noadv("upstream", alvo.id) %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
end-list

xpl large-community-list LC-NOADV-{{ alvo.token }}
 {{ plan.c_large(0, alvo.asn) }}
end-list

{# qualquer 5PPA do peer, inclusive o digito 0. Nao carrega acao: serve para o
   egress saber que o cliente falou deste peer e para barrar a classe 6CA, que
   perderia para o especifico. #}
xpl community-list CL-5PPA-{{ "%02d"|format(alvo.id) }}
{% for d in range(5) %}
 {{ plan.c5ppa(alvo.id, d) }}{{ "," if not loop.last }}
{% endfor %}
end-list

{# espelho do CL-5PPA no eixo de 32 bits. #}
xpl large-community-list LC-5PPA-{{ alvo.token }}
{% for f in range(5) %}
 {{ plan.c_large(f, alvo.asn) }}{{ "," if not loop.last }}
{% endfor %}
end-list

xpl large-community-list LC-PREP1-{{ alvo.token }}
 {{ plan.c_large(1, alvo.asn) }}
end-list

xpl large-community-list LC-PREP2-{{ alvo.token }}
 {{ plan.c_large(2, alvo.asn) }}
end-list

xpl large-community-list LC-PREP3-{{ alvo.token }}
 {{ plan.c_large(3, alvo.asn) }}
end-list

{% if alvo.ap_block %}
{# PLANO.md / AS-path por peer. Fora do laco de familia: a lista nao tem eixo
   de familia, e num peer dual-stack ela sairia definida duas vezes. Sem block
   list a excecao nao existe, e o import ja so consulta esta lista quando ela
   tem conteudo: a definicao segue a referencia. #}
xpl as-path-list AP-BLOCK-{{ alvo.token }}
{% for asn in alvo.ap_block %}
 pass '{{ asn }}'{{ "," if not loop.last }}
{% endfor %}
end-list

{% endif %}
{% if alvo.ap_te %}
{# ASNs que se alcanca melhor pela borda deste upstream. origin, como no
   PLANO: o que interessa e quem originou, nao por onde passou. #}
xpl as-path-list AP-TE-PREFER-{{ alvo.token }}
{% for asn in alvo.ap_te %}
 origin '{{ asn }}'{{ "," if not loop.last }}
{% endfor %}
end-list

{% endif %}
{%- endmacro %}
```

- [ ] **Step 3: Reescrever `templates/upstream.txt.j2`**

O arquivo inteiro passa a ser:

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% for fam in peer.familias() %}
{{ m.te_prefix_list(peer, fam) }}
{{ m.filtro_upstream_import(peer, fam) }}

{{ m.filtro_upstream_export(peer, fam, true) }}
{% endfor %}
{{ m.listas_upstream(peer) }}

{{ m.apply_peer(peer) }}

bgp 64512
{# o grupo de sessao termina em newline e familia_bgp ja abre com a linha em
   branco. Sem o corte abaixo a emenda sai com duas. O separador fica entre
   grupos, nunca depois do ultimo. #}
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}{{ "\n" if not loop.last -}}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "UP-" ~ peer.token ~ "-IMPORT-" ~ U,
     "UP-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

- [ ] **Step 4: Rodar o golden e fechar a diferença de linha em branco**

```bash
.venv/bin/python -m pytest tests/test_render.py -k upstream -v
```

Esperado: PASS nos dois testes (`test_golden_do_upstream`, `test_golden_da_remocao_do_upstream`).

Se falhar, é branco a mais ou a menos. Diagnosticar com:

```bash
.venv/bin/python -c "
from app import render
from tests.test_render import peer_upstream
from pathlib import Path
novo = render.render_peer(peer_upstream()).splitlines(keepends=True)
velho = Path('tests/golden/upstream.txt').read_text(encoding='ascii').splitlines(keepends=True)
import difflib, sys
sys.stdout.writelines(difflib.unified_diff(velho, novo, 'golden', 'novo'))"
```

O ponto de ajuste é sempre o mesmo: o macro com `{% macro ... -%}` come a quebra depois da tag de abertura, e o `{%- endmacro %}` come o branco antes do fecho. Uma linha em branco a mais ou a menos **na macro** (nunca no golden) alinha o bloco. Os comentários de `upstream.txt.j2:173-175` e `cliente.txt.j2:68-70` registram o mesmo tipo de ajuste na emenda sessão/família.

- [ ] **Step 5: Rodar a suite inteira**

```bash
.venv/bin/python -m pytest -q
```

Esperado: PASS. Se `test_golden_do_ix` ou `test_golden_do_pni` quebraram, alguma macro compartilhada vazou para eles: as quatro macros desta task só podem ser chamadas por `upstream.txt.j2`.

- [ ] **Step 6: Commit**

```bash
git add templates/_macros.j2 templates/upstream.txt.j2
git commit -m "Extrai o miolo do upstream para macros de alvo duplo"
```

---

## Task 4: Extrair o miolo do IX e do PNI

Mesma refatoração, dois arquivos menores. Aqui todas as listas são independentes de família (nenhum objeto do IX ou do PNI tem eixo de família fora dos dois filtros), então bastam duas macros de filtro e uma de lista por tipo.

**Files:**
- Modify: `templates/_macros.j2` (append de seis macros)
- Modify: `templates/ix.txt.j2`, `templates/pni.txt.j2` (reescritos)
- Test: `tests/test_render.py:824` (`test_golden_do_ix`), `tests/test_render.py:988` (`test_golden_do_pni`), `tests/test_render.py:1097` e `:1102` (remoções)

**Interfaces:**
- Consumes: `alvo.token`, `alvo.asn`, `alvo.origem`, `alvo.lp_base`, `alvo.aprendizado`, `alvo.ix_id`, `alvo.ap_prefer`, `alvo.ap_allowed`; `plan.noadv`, `plan.c_large`, `plan.LP_IX_CDN`, `plan.GEO_PNI`, `plan.CLASSE_6CA`
- Produces: `m.filtro_ix_import(alvo, fam)`, `m.filtro_ix_export(alvo, fam)`, `m.listas_ix(alvo)`, `m.filtro_pni_import(alvo, fam)`, `m.filtro_pni_export(alvo, fam)`, `m.listas_pni(alvo)`
- **Não pode referenciar** `sessoes`, `familias()`, `route_limit`, `descricao`, `te_prefixos`, `ap_block`, `ap_te`, `bh_upstream`, `prepend_base` nem `communities`: o grupo de IX e o de PNI não leem nenhum deles, e um nome a mais aqui é erro de escopo.

- [ ] **Step 1: Registrar o estado de partida**

```bash
.venv/bin/python -m pytest tests/test_render.py -q
```

Esperado: PASS.

- [ ] **Step 2: Acrescentar as seis macros ao fim de `templates/_macros.j2`**

```jinja
{# O miolo do IX. Tudo do IX sem eixo de familia cabe em listas_ix: nem o
   AP-IX nem os CL/LC-NOADV mudam com a familia. #}
{% macro filtro_ix_import(alvo, fam) -%}
{% set U = fam|upper %}
xpl route-filter IX-{{ alvo.token }}-IMPORT-{{ U }}
 call route-filter IMPORT-SANITY-{{ U }}

 {# anti-leak de IX: membro nao deve anunciar rota de transito #}
 if as-path length ge 4 then
  refuse
 endif

 {# overwrite: nada do que o membro do IX escreveu sobrevive. 1001:<ix_id> e a
    informativa de IX; o id e o do PeeringDB, nao o ASN do route server. #}
 apply community {{ plan.conjunto("64512:%d" % alvo.origem, "64512:%d" % alvo.aprendizado, "64512:2000") }} overwrite
 apply large-community {{ plan.conjunto(plan.c_large(1001, alvo.ix_id)) }} overwrite

{% if alvo.ap_prefer %}
 if as-path matches-any AP-IX-{{ alvo.token }} then
  apply local-preference {{ plan.LP_IX_CDN }}
 else
  apply local-preference {{ alvo.lp_base }}
 endif
{% else %}
 apply local-preference {{ alvo.lp_base }}
{% endif %}

 finish
 end-filter
{%- endmacro %}

{% macro filtro_ix_export(alvo, fam) -%}
{% set U = fam|upper %}
xpl route-filter IX-{{ alvo.token }}-EXPORT-{{ U }}
 call route-filter EXPORT-SANITY

 {# rede de seguranca do 2000, igual ao egress de upstream: rota aprendida de
    fora ja caiu no EXPORT-SANITY acima. #}
 if community matches-any {{ plan.conjunto("64512:2000") }} then
  refuse
 endif

 if community matches-any CL-NOADV-{{ alvo.token }} or large-community matches-any LC-NOADV-{{ alvo.token }} then
  refuse
 endif

 if community matches-any CL-ONLY-NOT-IX then
  refuse
 endif

 {# 6CA da classe plan.CLASSE_6CA["ix"] = IX publico; P2=1x, P3=2x, P4=3x. Sem
    ramo 5PPA: o route server repassa o mesmo AS-path a todos os membros,
    entao prepend no egress da sessao com o RS prependa para todo mundo.
    Prepend por membro so com sessao bilateral. #}
 if community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["ix"], 4)) }} then
  apply as-path 64512 3 additive
 elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["ix"], 3)) }} then
  apply as-path 64512 2 additive
 elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["ix"], 2)) }} then
  apply as-path 64512 1 additive
 endif

 {# sem limpeza no fecho: a rota sai com tudo o que carrega, e o que decide o
    anuncio sao os matches-any acima. #}
 finish
 end-filter
{%- endmacro %}

{% macro listas_ix(alvo) -%}
{# um set por peer: evita cadeia de OR na condicao. #}
xpl community-list CL-NOADV-{{ alvo.token }}
{% for c in plan.noadv("ix", alvo.id) %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

xpl large-community-list LC-NOADV-{{ alvo.token }}
 {{ plan.c_large(0, alvo.asn) }}
 end-list

{% if alvo.ap_prefer %}
{# membros deste IX que recebem LP plan.LP_IX_CDN em vez de alvo.lp_base.
   peer-is, nao pass: o route server e transparente e nao insere o proprio
   ASN no path, entao peer-is identifica quem realmente anunciou, e da
   politica por membro com uma unica sessao contra o RS. #}
xpl as-path-list AP-IX-{{ alvo.token }}
{% for asn in alvo.ap_prefer %}
 peer-is '{{ asn }}'{{ "," if not loop.last }}
{% endfor %}
 end-list

{% endif %}
{%- endmacro %}

{# O miolo do PNI. #}
{% macro filtro_pni_import(alvo, fam) -%}
{% set U = fam|upper %}
xpl route-filter PNI-{{ alvo.token }}-IMPORT-{{ U }}
 call route-filter IMPORT-SANITY-{{ U }}

 {# sessao bilateral: so entra o que a CDN pode anunciar #}
 if not as-path matches-any AP-{{ alvo.token }}-ALLOWED then
  refuse
 endif

 apply local-preference {{ alvo.lp_base }}
 {# overwrite: a CDN nao escreve no nosso namespace. plan.GEO_PNI e a
    geografia fixa do PNI. 2000 porque a rota vem de fora: nao e propria nem
    de cliente. #}
 apply community {{ plan.conjunto("64512:%d" % alvo.origem, "64512:%d" % plan.GEO_PNI, "64512:2000") }} overwrite
 apply large-community {{ plan.conjunto(plan.c_large(1000, alvo.asn)) }} overwrite

 finish
 end-filter
{%- endmacro %}

{% macro filtro_pni_export(alvo, fam) -%}
{% set U = fam|upper %}
xpl route-filter PNI-{{ alvo.token }}-EXPORT-{{ U }}
 call route-filter EXPORT-SANITY

 {# rede de seguranca do 2000, igual aos demais egress externos. #}
 if community matches-any {{ plan.conjunto("64512:2000") }} then
  refuse
 endif

 if community matches-any CL-NOADV-{{ alvo.token }} or large-community matches-any LC-NOADV-{{ alvo.token }} then
  refuse
 endif

 if community matches-any CL-ONLY-NOT-PNI then
  refuse
 endif

 {# 6CA da classe plan.CLASSE_6CA["pni"] = CDN; P2=1x, P3=2x, P4=3x. O PNI e
    bilateral e o ramo 5PPA funcionaria aqui, mas o exemplo do PLANO nao o
    traz; fica na lista de pendencias, nao como decisao. #}
 if community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["pni"], 4)) }} then
  apply as-path 64512 3 additive
 elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["pni"], 3)) }} then
  apply as-path 64512 2 additive
 elseif community matches-any {{ plan.conjunto(plan.c6ca(plan.CLASSE_6CA["pni"], 2)) }} then
  apply as-path 64512 1 additive
 endif

 {# igual ao egress do IX: sem limpeza no fecho. A CDN nao tem community
    propria hoje; se tiver, entra a mesma montagem de APPLY-PEER-<T> usada no
    upstream. #}
 finish
 end-filter
{%- endmacro %}

{% macro listas_pni(alvo) -%}
{# CDN via PNI: so estes ASNs podem chegar por esta sessao. pass, nao origin:
   o que se quer e aceitar path que passe pelo ASN da CDN, que costuma
   anunciar por tras do transito dela. #}
xpl as-path-list AP-{{ alvo.token }}-ALLOWED
{% for asn in alvo.ap_allowed %}
 pass '{{ asn }}'{{ "," if not loop.last }}
{% endfor %}
 end-list

{# um set por peer: evita cadeia de OR na condicao. #}
xpl community-list CL-NOADV-{{ alvo.token }}
{% for c in plan.noadv("pni", alvo.id) %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
 end-list

xpl large-community-list LC-NOADV-{{ alvo.token }}
 {{ plan.c_large(0, alvo.asn) }}
 end-list
{%- endmacro %}
```

- [ ] **Step 3: Reescrever `templates/ix.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% for fam in peer.familias() %}
{{ m.filtro_ix_import(peer, fam) }}

{{ m.filtro_ix_export(peer, fam) }}
{% endfor %}
{{ m.listas_ix(peer) }}

bgp 64512
{# o grupo de sessao termina em newline e familia_bgp ja abre com a linha em
   branco. Sem o corte abaixo a emenda sai com duas. O separador fica entre
   grupos, nunca depois do ultimo. #}
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}{{ "\n" if not loop.last -}}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "IX-" ~ peer.token ~ "-IMPORT-" ~ U,
     "IX-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

- [ ] **Step 4: Reescrever `templates/pni.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% for fam in peer.familias() %}
{{ m.filtro_pni_import(peer, fam) }}

{{ m.filtro_pni_export(peer, fam) }}
{% endfor %}
{{ m.listas_pni(peer) }}

bgp 64512
{# o grupo de sessao termina em newline e familia_bgp ja abre com a linha em
   branco. Sem o corte abaixo a emenda sai com duas. O separador fica entre
   grupos, nunca depois do ultimo. #}
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}{{ "\n" if not loop.last -}}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "PNI-" ~ peer.token ~ "-IMPORT-" ~ U,
     "PNI-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

- [ ] **Step 5: Rodar os goldens e fechar a diferença de linha em branco**

```bash
.venv/bin/python -m pytest tests/test_render.py -k "ix or pni" -v
```

Esperado: PASS em `test_golden_do_ix`, `test_golden_do_pni`, `test_golden_da_remocao_do_ix` e `test_golden_da_remocao_do_pni`.

Mesmo diagnóstico do Step 4 da Task 3, trocando `peer_upstream`/`upstream.txt` por `peer_ix`/`ix.txt` e `peer_pni`/`pni.txt`. O ajuste é sempre uma linha em branco na macro, nunca no golden.

- [ ] **Step 6: Rodar a suite inteira**

```bash
.venv/bin/python -m pytest -q
```

Esperado: PASS.

- [ ] **Step 7: Commit**

```bash
git add templates/_macros.j2 templates/ix.txt.j2 templates/pni.txt.j2
git commit -m "Extrai o miolo do ix e do pni para macros de alvo duplo"
```

---

## Task 5: O template de grupo de upstream

**Files:**
- Create: `templates/grupo_upstream.txt.j2`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `m.cabecalho_grupo`, `m.te_prefix_list`, `m.filtro_upstream_import`, `m.filtro_upstream_export`, `m.listas_upstream`, `m.apply_peer`, `m.sessao_do_grupo`, `m.familia_grupo` (as sete últimas das Tasks 3 e 4, e as três de grupo que já existem em `_macros.j2:166-199`)
- Produces: `render.render_grupo(grupo)` funcionando para `tipo="upstream"` sem mudança em `TEMPLATE_POR_TIPO_GRUPO` (`render.py:69` já cai em `"grupo_%s.txt.j2" % grupo.tipo`)

- [ ] **Step 1: Escrever o teste que falha**

Em `tests/test_render.py`, junto dos testes de grupo que já existem. A fixture segue o padrão de `peer_upstream` (linha 370):

```python
def grupo_upstream(**kw):
    base = dict(
        id=3, nome="BRDIGITAL", tipo="upstream", asn=14840,
        lp_base=100, origem=1400, aprendizado=3100,
        te_prefixos={"v4": ["1.1.1.0/24"], "v6": []},
        ap_block=[64500], ap_te=[64501],
        bh_upstream="14840:666", prepend_base=2,
        communities=["14840:9133"], large_communities=["14840:1:3333"],
    )
    base.update(kw)
    return Grupo(**base)


def test_render_do_grupo_de_upstream():
    texto = render.render_grupo(grupo_upstream())
    assert "group BRDIGITAL external" in texto
    assert "xpl route-filter UP-BRDIGITAL-IMPORT-V4" in texto
    assert "xpl route-filter UP-BRDIGITAL-EXPORT-V4" in texto
    # o par PL-TE-PREFER sai dentro do laco de familia, com o sufixo da
    # familia; o resto das listas sai fora dele
    assert "xpl ip-prefix-list PL-TE-PREFER-BRDIGITAL-V4" in texto
    assert "xpl ipv6-prefix-list PL-TE-PREFER-BRDIGITAL-V6" not in texto
    assert "xpl community-list CL-5PPA-03" in texto
    assert "xpl as-path-list AP-BLOCK-BRDIGITAL" in texto


def test_o_grupo_de_upstream_aplica_a_cl_peer():
    # a community de um upstream descreve a rede remota, nao o link: ela
    # mora no grupo e o bloco chama o filtro, igual ao peer avulso
    texto = render.render_grupo(grupo_upstream())
    assert "call route-filter APPLY-PEER-BRDIGITAL" in texto
    assert "xpl route-filter APPLY-PEER-BRDIGITAL" not in texto


def test_o_grupo_de_upstream_declara_as_duas_familias():
    # grupo nao tem sessao, entao nao ha peer.familias() para consultar: o
    # template declara as duas sempre, como o de downstream ja faz
    texto = render.render_grupo(grupo_upstream(te_prefixos={"v4": [], "v6": []}))
    assert "ipv4-family unicast" in texto
    assert "ipv6-family unicast" in texto


def test_o_grupo_de_upstream_sem_te_nao_define_a_lista():
    texto = render.render_grupo(grupo_upstream(te_prefixos={"v4": [], "v6": []}))
    assert "PL-TE-PREFER" not in texto


def test_o_grupo_de_upstream_sem_ap_nao_define_as_listas_de_as_path():
    texto = render.render_grupo(grupo_upstream(ap_block=[], ap_te=[]))
    assert "AP-BLOCK-BRDIGITAL" not in texto
    assert "AP-TE-PREFER-BRDIGITAL" not in texto
```

Conferir que `tests/test_render.py` importa `Grupo` de `app.peers`. Se não, acrescentar ao import.

- [ ] **Step 2: Rodar e confirmar que falha**

```bash
.venv/bin/python -m pytest tests/test_render.py -k grupo_de_upstream -v
```

Esperado: FAIL com `jinja2.exceptions.TemplateNotFound: grupo_upstream.txt.j2`.

- [ ] **Step 3: Criar o template**

`templates/grupo_upstream.txt.j2`:

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho_grupo(grupo) }}

{# grupo nao tem sessao, entao nao ha familias() a consultar: as duas
   familias saem sempre, como no grupo_cliente.txt.j2. O bloco em si e o
   mesmo do peer avulso, pelas mesmas macros. #}
{% for fam in ("v4", "v6") %}
{{ m.te_prefix_list(grupo, fam) }}
{{ m.filtro_upstream_import(grupo, fam) }}

{{ m.filtro_upstream_export(grupo, fam, true) }}
{% endfor %}
{{ m.listas_upstream(grupo) }}

{{ m.apply_peer(grupo) }}

bgp 64512
 group {{ grupo.nome }} external
{{ m.sessao_do_grupo(grupo) }}
{% for fam in ("v4", "v6") %}
{% set U = fam|upper %}
{{ m.familia_grupo(grupo, fam,
     "UP-" ~ grupo.nome ~ "-IMPORT-" ~ U,
     "UP-" ~ grupo.nome ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

- [ ] **Step 4: Rodar e ver passar**

```bash
.venv/bin/python -m pytest tests/test_render.py -k grupo_de_upstream -v && .venv/bin/python -m pytest -q
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/grupo_upstream.txt.j2 tests/test_render.py
git commit -m "Grupo de upstream gera o bloco proprio"
```

---

## Task 6: Os templates de grupo de IX e PNI

Mesma forma, sem `te_prefix_list` e sem `apply_peer` (nem o IX nem o PNI chamam `APPLY-PEER`, e `plan.TIPOS_COM_APPLY_PEER` não os inclui).

**Files:**
- Create: `templates/grupo_ix.txt.j2`, `templates/grupo_pni.txt.j2`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `m.cabecalho_grupo`, `m.filtro_ix_import`, `m.filtro_ix_export`, `m.listas_ix`, `m.filtro_pni_import`, `m.filtro_pni_export`, `m.listas_pni`, `m.sessao_do_grupo`, `m.familia_grupo`
- Produces: `render.render_grupo` funcionando para `tipo="ix"` e `tipo="pni"`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_render.py`:

```python
def grupo_ix(**kw):
    base = dict(
        id=4, nome="IXBR", tipo="ix", asn=26162,
        lp_base=190, origem=1300, aprendizado=3200, ix_id=1234,
        ap_prefer=[264130],
    )
    base.update(kw)
    return Grupo(**base)


def grupo_pni(**kw):
    base = dict(
        id=5, nome="CDN", tipo="pni", asn=264130,
        lp_base=200, origem=1500, ap_allowed=[264130, 64500],
    )
    base.update(kw)
    return Grupo(**base)


def test_render_do_grupo_de_ix():
    texto = render.render_grupo(grupo_ix())
    assert "group IXBR external" in texto
    assert "xpl route-filter IX-IXBR-IMPORT-V4" in texto
    assert "xpl route-filter IX-IXBR-EXPORT-V4" in texto
    assert "xpl as-path-list AP-IX-IXBR" in texto
    # o IX nao tem APPLY-PEER nem 5PPA: o route server repassa o mesmo
    # AS-path a todos os membros
    assert "APPLY-PEER" not in texto
    assert "5PPA" not in texto


def test_o_grupo_de_ix_sem_ap_prefer_nao_define_a_lista():
    texto = render.render_grupo(grupo_ix(ap_prefer=[]))
    assert "AP-IX-IXBR" not in texto


def test_render_do_grupo_de_pni():
    texto = render.render_grupo(grupo_pni())
    assert "group CDN external" in texto
    assert "xpl route-filter PNI-CDN-IMPORT-V4" in texto
    assert "xpl route-filter PNI-CDN-EXPORT-V4" in texto
    assert "xpl as-path-list AP-CDN-ALLOWED" in texto
    assert "APPLY-PEER" not in texto


def test_o_grupo_de_pni_com_allowlist_vazia_ainda_emite_o_header():
    # a macro nao tem guarda, igual ao pni.txt.j2:61: o header e o end-list
    # saem mesmo sem nenhum pass. Quem impede a lista vazia de existir na
    # pratica e a validacao da Task 8, nao o template
    texto = render.render_grupo(grupo_pni(ap_allowed=[]))
    assert "xpl as-path-list AP-CDN-ALLOWED" in texto
```

- [ ] **Step 2: Rodar e confirmar que falham**

```bash
.venv/bin/python -m pytest tests/test_render.py -k "grupo_de_ix or grupo_de_pni" -v
```

Esperado: FAIL com `TemplateNotFound: grupo_ix.txt.j2` e `grupo_pni.txt.j2`.

- [ ] **Step 3: Criar `templates/grupo_ix.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho_grupo(grupo) }}

{% for fam in ("v4", "v6") %}
{{ m.filtro_ix_import(grupo, fam) }}

{{ m.filtro_ix_export(grupo, fam) }}
{% endfor %}
{{ m.listas_ix(grupo) }}

bgp 64512
 group {{ grupo.nome }} external
{{ m.sessao_do_grupo(grupo) }}
{% for fam in ("v4", "v6") %}
{% set U = fam|upper %}
{{ m.familia_grupo(grupo, fam,
     "IX-" ~ grupo.nome ~ "-IMPORT-" ~ U,
     "IX-" ~ grupo.nome ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

- [ ] **Step 4: Criar `templates/grupo_pni.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho_grupo(grupo) }}

{% for fam in ("v4", "v6") %}
{{ m.filtro_pni_import(grupo, fam) }}

{{ m.filtro_pni_export(grupo, fam) }}
{% endfor %}
{{ m.listas_pni(grupo) }}

bgp 64512
 group {{ grupo.nome }} external
{{ m.sessao_do_grupo(grupo) }}
{% for fam in ("v4", "v6") %}
{% set U = fam|upper %}
{{ m.familia_grupo(grupo, fam,
     "PNI-" ~ grupo.nome ~ "-IMPORT-" ~ U,
     "PNI-" ~ grupo.nome ~ "-EXPORT-" ~ U) }}
{% endfor %}
```

- [ ] **Step 5: Rodar e ver passar**

```bash
.venv/bin/python -m pytest tests/test_render.py -q && .venv/bin/python -m pytest -q
```

Esperado: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/grupo_ix.txt.j2 templates/grupo_pni.txt.j2 tests/test_render.py
git commit -m "Grupo de ix e de pni geram o bloco proprio"
```

---

## Task 7: Membro de grupo nos três tipos novos

"Vários links, um upstream" só existe se o membro herdar do grupo. O gate de membro está hoje em `plan.TIPOS_DOWNSTREAM` em três lugares, e os três passam a valer para `plan.TIPOS`, com as checagens que só fazem sentido em downstream continuando presas ao `TIPOS_DOWNSTREAM` **dentro** do ramo. A validação da Task 8 é quem libera o cadastro.

Esta task também carrega o ruling do `route-limit`: `sessao_do_peer` (`_macros.j2:35`) emite o limite para todo tipo, mas o ramo de membro do `cliente.txt.j2:37` emite só para `cliente`, então um membro `parceiro` perde o limite que teria sozinho. É inconsistência do que está construído, não decisão: o limite é da sessão e `plan.ROUTE_LIMIT` tem valor para os cinco tipos.

**Files:**
- Modify: `templates/cliente.txt.j2:37-39`
- Modify: `templates/upstream.txt.j2`, `templates/ix.txt.j2`, `templates/pni.txt.j2` (ramo de membro)
- Modify: `templates/remover.txt.j2:26-38` e `:48-73` (gate de membro nos ramos dos três tipos)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `peer.tem_filtro_proprio()` (`app/peers.py`), `grupo.nome`, `grupo.asn`, `peer.sessoes[fam]`, `peer.descricao`, `peer.route_limit`, `plan.ACAO_LIMITE`
- Produces: `render.render_peer(peer, grupo=grupo)` funcionando para membro dos cinco tipos

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_render.py`:

```python
def test_membro_de_grupo_de_upstream_herda_a_politica():
    # o membro so referencia o group: quem carrega AS_ONLY, timers, bfd e
    # advertise-community e o arquivo do grupo, uma vez so
    p = peer_upstream(id=7, token_livre=True)
    g = grupo_upstream(nome="BRDIGITAL", id=3)
    texto = render.render_peer(p, grupo=g)
    assert " peer 203.0.113.1 group BRDIGITAL" in texto
    assert "ipv4-family unicast" in texto
    # o membro NAO reemite os knobs de sessao
    for cmd in ("public-as-only force", "capability-advertise graceful-restart",
                "bfd enable", "timer keepalive"):
        assert cmd not in texto, cmd
    # nem refaz os filtros do grupo
    assert "xpl route-filter UP-" not in texto


def test_membro_de_grupo_de_upstream_emite_o_route_limit():
    p = peer_upstream(id=7)
    g = grupo_upstream(nome="BRDIGITAL", id=3)
    texto = render.render_peer(p, grupo=g)
    assert " peer 203.0.113.1 route-limit 1500000 alert-only" in texto


def test_membro_parceiro_emite_o_route_limit():
    # hoje o ramo de membro so emite para cliente, entao um membro parceiro
    # sai sem limite nenhum
    p = peer_parceiro(apelido="PARC")
    g = grupo_cliente(id=9, nome="PARCEIROS", tipo="parceiro", asn=None,
                      classe="transito", origem=1100, pop=2001)
    texto = render.render_peer(p, grupo=g)
    assert "route-limit 50 alert-only" in texto


def test_membro_de_grupo_de_ix_referencia_o_group():
    p = peer_ix(id=8)
    g = grupo_ix(nome="IXBR", id=4)
    texto = render.render_peer(p, grupo=g)
    assert " peer 187.16.192.2 group IXBR" in texto
    assert "xpl route-filter IX-" not in texto


def test_membro_de_grupo_de_pni_referencia_o_group():
    p = peer_pni(id=9)
    g = grupo_pni(nome="CDN", id=5)
    texto = render.render_peer(p, grupo=g)
    assert " peer 187.16.192.2 group CDN" in texto
    assert "xpl route-filter PNI-" not in texto


def test_membro_sem_asn_do_grupo_declara_o_proprio():
    # o as-number do membro so sai quando o grupo nao tem o dele, como no
    # ramo de downstream
    p = peer_upstream(id=7)
    com_asn = render.render_peer(p, grupo=grupo_upstream(nome="X", id=3, asn=14840))
    sem_asn = render.render_peer(p, grupo=grupo_upstream(nome="X", id=3, asn=None))
    assert "as-number 14840" not in com_asn
    assert "as-number 14840" in sem_asn


def test_a_remocao_do_membro_de_upstream_nao_derruba_o_bloco_do_grupo():
    # o membro sem filtro proprio nao tem objeto nenhum para derrubar alem
    # da sessao
    p = peer_upstream(id=7)
    g = grupo_upstream(nome="BRDIGITAL", id=3)
    texto = render.render_remove(p, grupo=g)
    assert "undo xpl route-filter UP-" not in texto
    assert "undo xpl community-list CL-NOADV-" not in texto
    assert "undo peer 203.0.113.1" in texto


def test_a_remocao_do_membro_de_upstream_com_filtro_proprio_derruba_o_dele():
    p = peer_upstream(id=7, communities=["14840:9133"])
    g = grupo_upstream(nome="BRDIGITAL", id=3)
    texto = render.render_remove(p, grupo=g)
    assert "undo xpl route-filter UP-14840-IMPORT-V4" in texto
```

Notas de fixture:
- `peer_upstream()` e `peer_ix()` já existem (linhas 370 e 677). Seus ids e IPs remotos são fixos; ajustar `id=` onde o teste acima pedir e conferir o IP remoto real de cada fixture antes de fixar a asserção. `peer_ix` e `peer_pni` usam `187.16.192.2` como remoto; conferir no arquivo.
- `grupo_cliente(...)` é a fixture nova desta task: a Task 5 criou `grupo_upstream`, a 6 criou `grupo_ix` e `grupo_pni`. Criar `grupo_cliente` com o mesmo formato, `tipo="cliente"` ou `"parceiro"`.
- `peer_parceiro` pode não aceitar `apelido`; o `token` derivado do ASN serve, e é ele que aparece nas URLs.

- [ ] **Step 2: Rodar e confirmar que falham**

```bash
.venv/bin/python -m pytest tests/test_render.py -k membro -v
```

Esperado: FAIL. Os de upstream/IX/PNI saem com o bloco inteiro do peer avulso, porque `{% if grupo %}` só existe no `cliente.txt.j2`. O de `route-limit` do parceiro falha porque a linha não sai.

- [ ] **Step 3: Tirar a condição de tipo do `route-limit` no `cliente.txt.j2`**

Substituir as linhas 37-39 por:

```jinja
{# o limite e da sessao e o plan.ROUTE_LIMIT tem valor para os cinco tipos:
   condicionar a "cliente" deixava um membro parceiro sem limite nenhum,
   porque o ramo de membro nao chama sessao_do_peer. #}
 peer {{ peer.sessoes[fam].remoto }} route-limit {{ peer.route_limit }} {{ plan.ACAO_LIMITE }}
```

- [ ] **Step 4: Acrescentar o ramo de membro ao `upstream.txt.j2`**

Envolver o corpo do arquivo atual no `{% if grupo %}`, espelhando o `cliente.txt.j2`. O arquivo passa a ser:

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% if grupo %}
{# membro de grupo: quem carrega a politica e o arquivo do grupo. Este ramo
   nao chama sessao_do_peer/familia_bgp: essas macros sao do peer avulso e
   reemitiriam AS_ONLY/timers/graceful-restart/bfd/advertise-community por
   membro, coisa que so deve existir uma vez, no arquivo do grupo. #}
{% if peer.tem_filtro_proprio() %}
{% for fam in peer.familias() %}
{{ m.te_prefix_list(peer, fam) }}
{{ m.filtro_upstream_import(peer, fam) }}

{{ m.filtro_upstream_export(peer, fam, true) }}
{% endfor %}
{{ m.listas_upstream(peer) }}

{{ m.apply_peer(peer) }}

{% endif %}
bgp 64512
{% for fam in peer.familias() %}
 peer {{ peer.sessoes[fam].remoto }} description {{ peer.descricao }}
{% if not grupo.asn %}
 peer {{ peer.sessoes[fam].remoto }} as-number {{ peer.asn }}
{% endif %}
 peer {{ peer.sessoes[fam].remoto }} route-limit {{ peer.route_limit }} {{ plan.ACAO_LIMITE }}
 peer {{ peer.sessoes[fam].remoto }} group {{ grupo.nome }}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{% set s = peer.sessoes[fam] %}
 {{ "ipv6-family" if fam == "v6" else "ipv4-family" }} unicast
  peer {{ s.remoto }} enable
  peer {{ s.remoto }} group {{ grupo.nome }}
{% if peer.tem_filtro_proprio() %}
  peer {{ s.remoto }} route-filter UP-{{ peer.token }}-IMPORT-{{ U }} import
{% endif %}
{% endfor %}
{% else %}
{% for fam in peer.familias() %}
{{ m.te_prefix_list(peer, fam) }}
{{ m.filtro_upstream_import(peer, fam) }}

{{ m.filtro_upstream_export(peer, fam, true) }}
{% endfor %}
{{ m.listas_upstream(peer) }}

{{ m.apply_peer(peer) }}

bgp 64512
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}{{ "\n" if not loop.last -}}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "UP-" ~ peer.token ~ "-IMPORT-" ~ U,
     "UP-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
{% endif %}
```

- [ ] **Step 5: Acrescentar o ramo de membro ao `ix.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% if grupo %}
{# membro de grupo de IX: ver o comentario longo do cliente.txt.j2 sobre o
   porque de nao reusar as macros do peer avulso. #}
{% if peer.tem_filtro_proprio() %}
{% for fam in peer.familias() %}
{{ m.filtro_ix_import(peer, fam) }}

{{ m.filtro_ix_export(peer, fam) }}
{% endfor %}
{{ m.listas_ix(peer) }}

{% endif %}
bgp 64512
{% for fam in peer.familias() %}
 peer {{ peer.sessoes[fam].remoto }} description {{ peer.descricao }}
{% if not grupo.asn %}
 peer {{ peer.sessoes[fam].remoto }} as-number {{ peer.asn }}
{% endif %}
 peer {{ peer.sessoes[fam].remoto }} route-limit {{ peer.route_limit }} {{ plan.ACAO_LIMITE }}
 peer {{ peer.sessoes[fam].remoto }} group {{ grupo.nome }}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{% set s = peer.sessoes[fam] %}
 {{ "ipv6-family" if fam == "v6" else "ipv4-family" }} unicast
  peer {{ s.remoto }} enable
  peer {{ s.remoto }} group {{ grupo.nome }}
{% if peer.tem_filtro_proprio() %}
  peer {{ s.remoto }} route-filter IX-{{ peer.token }}-IMPORT-{{ U }} import
{% endif %}
{% endfor %}
{% else %}
{% for fam in peer.familias() %}
{{ m.filtro_ix_import(peer, fam) }}

{{ m.filtro_ix_export(peer, fam) }}
{% endfor %}
{{ m.listas_ix(peer) }}

bgp 64512
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}{{ "\n" if not loop.last -}}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "IX-" ~ peer.token ~ "-IMPORT-" ~ U,
     "IX-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
{% endif %}
```

- [ ] **Step 6: Acrescentar o ramo de membro ao `pni.txt.j2`**

```jinja
{% import "_macros.j2" as m %}
{{ m.cabecalho(peer) }}

{% if grupo %}
{# membro de grupo de PNI: ver o comentario longo do cliente.txt.j2. #}
{% if peer.tem_filtro_proprio() %}
{% for fam in peer.familias() %}
{{ m.filtro_pni_import(peer, fam) }}

{{ m.filtro_pni_export(peer, fam) }}
{% endfor %}
{{ m.listas_pni(peer) }}

{% endif %}
bgp 64512
{% for fam in peer.familias() %}
 peer {{ peer.sessoes[fam].remoto }} description {{ peer.descricao }}
{% if not grupo.asn %}
 peer {{ peer.sessoes[fam].remoto }} as-number {{ peer.asn }}
{% endif %}
 peer {{ peer.sessoes[fam].remoto }} route-limit {{ peer.route_limit }} {{ plan.ACAO_LIMITE }}
 peer {{ peer.sessoes[fam].remoto }} group {{ grupo.nome }}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{% set s = peer.sessoes[fam] %}
 {{ "ipv6-family" if fam == "v6" else "ipv4-family" }} unicast
  peer {{ s.remoto }} enable
  peer {{ s.remoto }} group {{ grupo.nome }}
{% if peer.tem_filtro_proprio() %}
  peer {{ s.remoto }} route-filter PNI-{{ peer.token }}-IMPORT-{{ U }} import
{% endif %}
{% endfor %}
{% else %}
{% for fam in peer.familias() %}
{{ m.filtro_pni_import(peer, fam) }}

{{ m.filtro_pni_export(peer, fam) }}
{% endfor %}
{{ m.listas_pni(peer) }}

bgp 64512
{% for fam in peer.familias() %}
{{ m.sessao_do_peer(peer, fam) }}{{ "\n" if not loop.last -}}
{% endfor %}
{% for fam in peer.familias() %}
{% set U = fam|upper %}
{{ m.familia_bgp(peer, fam,
     "PNI-" ~ peer.token ~ "-IMPORT-" ~ U,
     "PNI-" ~ peer.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
{% endif %}
```

- [ ] **Step 7: Passar o gate de membro nos ramos de `remover.txt.j2`**

Nos dois laços, os três ramos dos tipos novos ganham a condição de membro, igual ao que a linha 45 já faz para downstream:

Linhas 26, 32 e 35 (laço por família):

```jinja
{% elif peer.tipo == "upstream" and (not grupo or peer.tem_filtro_proprio()) %}
```

```jinja
{% elif peer.tipo == "ix" and (not grupo or peer.tem_filtro_proprio()) %}
```

```jinja
{% elif peer.tipo == "pni" and (not grupo or peer.tem_filtro_proprio()) %}
```

Linhas 48, 63 e 69 (laço sem eixo de família), mesma condição:

```jinja
{% elif peer.tipo == "upstream" and (not grupo or peer.tem_filtro_proprio()) %}
```

```jinja
{% elif peer.tipo == "ix" and (not grupo or peer.tem_filtro_proprio()) %}
```

```jinja
{% elif peer.tipo == "pni" and (not grupo or peer.tem_filtro_proprio()) %}
```

O bloco final de aviso (`remover.txt.j2:75-84`) não muda: `peer.tipo in plan.TIPOS_COM_APPLY_PEER` já cobre o upstream, e o membro sem filtro próprio não tem `CL-PEER` para avisar.

- [ ] **Step 8: Rodar e ver passar**

```bash
.venv/bin/python -m pytest tests/test_render.py -q && .venv/bin/python -m pytest -q
```

Esperado: PASS, incluindo os goldens dos peers avulsos (o ramo novo só entra com `grupo`).

- [ ] **Step 9: Commit**

```bash
git add templates/cliente.txt.j2 templates/upstream.txt.j2 templates/ix.txt.j2 \
        templates/pni.txt.j2 templates/remover.txt.j2 tests/test_render.py
git commit -m "Membro de grupo nos tres tipos novos, e o route-limit volta ao membro parceiro"
```

---

## Task 8: Validação por tipo

O formulário já oferecia `upstream` no `select` desde antes desta mudança, e escolher a opção que ele mesmo mostrava produzia o erro "grupo ainda so suporta cliente e parceiro". Com o render pronto (Tasks 5 e 6) e o membro pronto (Task 7), o portão sai.

**Files:**
- Modify: `app/validate.py:207-208` (`TIPOS_COM_GRUPO` sai), `app/validate.py:211-262` (`validar_grupo`)
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `plan.TIPOS`, `plan.TIPOS_DOWNSTREAM`, `plan.ORIGENS_POR_TIPO`, `plan.APRENDIZADO_MIN`, `plan.APRENDIZADO_MAX`, `plan.CLASSES_CLIENTE`, `ORIGENS_CLIENTE`, `_valida_prefixos`, `_valida_timer`, `_valida_communities`, `_sem_duplicata`
- Produces: `validate.validar_grupo` sem `TIPOS_COM_GRUPO`; erro `("tipo", "tipo desconhecido: <x>")` para tipo fora de `plan.TIPOS`

**Ruling registrado:** `_valida_communities` entra no `validar_grupo` mesmo não estando na tabela de validação da spec, porque a tabela lista as regras **por tipo** e as regras compartilhadas (faixa de `lp_base`, timer, formato de `prefixos`, nome único) já ficam fora dela e continuam sendo chamadas. `communities` no grupo tem o mesmo destino do campo no peer (`CL-PEER-<G>`) e o mesmo risco: uma community malformada passa pelo cadastro e só estoura no equipamento.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_validate.py`:

```python
def um_grupo(**kw):
    base = dict(id=20, nome="G", tipo="upstream", asn=14840, lp_base=100,
                origem=1400, aprendizado=3100)
    base.update(kw)
    return Grupo(**base)


def test_grupo_aceita_os_cinco_tipos():
    for tipo in plan.TIPOS:
        g = um_grupo(tipo=tipo, classe="transito", origem=None, pop=2001,
                     aprendizado=3100, ix_id=1, ap_allowed=[64500])
        erros = validar_grupo(g, [g], [], anterior=g)
        assert [e.campo for e in erros] == [], (tipo, [e.msg for e in erros])


def test_grupo_recusa_tipo_desconhecido():
    g = um_grupo(tipo="peer-fantasma")
    erros = validar_grupo(g, [g], [], anterior=g)
    assert "tipo" in [e.campo for e in erros]


def test_a_faixa_de_origem_do_grupo_depende_do_tipo():
    # upstream nao carrega origem de cliente: o carimbo mentiria sobre a
    # procedencia da rota. Aqui o grupo e mais estrito que o peer, que fora
    # de downstream so confere que a origem existe (ver o ruling da spec)
    g = um_grupo(tipo="upstream", origem=1110)
    erros = validar_grupo(g, [g], [], anterior=g)
    assert ("origem", "origem do upstream tem que ser uma de 1400, 1000, 1900") in [
        (e.campo, e.msg) for e in erros]
    assert validar_grupo(um_grupo(tipo="upstream", origem=1400),
                         [], [], anterior=None) == []


def test_grupo_de_upstream_e_ix_exige_aprendizado():
    for tipo in ("upstream", "ix"):
        g = um_grupo(tipo=tipo, aprendizado=None, ix_id=1)
        campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
        assert "aprendizado" in campos, tipo


def test_grupo_de_ix_exige_o_id_do_peeringdb():
    g = um_grupo(tipo="ix", aprendizado=3200, ix_id=None)
    campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
    assert "ix_id" in campos


def test_grupo_de_pni_exige_a_allowlist():
    g = um_grupo(tipo="pni", ap_allowed=[])
    campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
    assert "ap_allowed" in campos


def test_grupo_fora_de_downstream_recusa_default_route():
    for tipo in ("upstream", "ix", "pni"):
        g = um_grupo(tipo=tipo, default_route=True, ix_id=1,
                     ap_allowed=[64500], aprendizado=3100)
        campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
        assert "default_route" in campos, tipo


def test_grupo_de_upstream_nao_exige_classe_nem_pop():
    g = um_grupo(tipo="upstream", classe=None, pop=None, origem=1400)
    campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
    assert campos == [], [e.msg for e in validar_grupo(g, [g], [], anterior=g)]


def test_grupo_com_community_malformada_e_recusado():
    g = um_grupo(communities=["14840:9133", "nao-e-community"])
    campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
    assert "communities" in campos
```

Conferir os imports do topo de `tests/test_validate.py`: precisa de `plan`.

- [ ] **Step 2: Rodar e confirmar que falham**

```bash
.venv/bin/python -m pytest tests/test_validate.py -k grupo -v
```

Esperado: FAIL em `test_grupo_aceita_os_cinco_tipos` (o portão recusa `upstream`, `ix` e `pni`), em `test_a_faixa_de_origem_do_grupo_depende_do_tipo` e em `test_grupo_com_community_malformada_e_recusado` (o `validar_grupo` não chama `_valida_communities`).

- [ ] **Step 3: Tirar o portão e reescrever o `validar_grupo`**

Apagar `TIPOS_COM_GRUPO` (linhas 207-208) inteiro, junto do comentário "so estes dois tipos por enquanto".

Substituir o corpo de `validar_grupo` pelas partes que mudam. Depois do bloco de `id` da Task 1, entra:

```python
    # o tipo escolhe o template do render, como no peer: um tipo fora de
    # plan.TIPOS grava o grupo para estourar depois, no TemplateNotFound.
    # O formulario so oferece os cinco, mas o POST nao passa por ele.
    if grupo.tipo not in plan.TIPOS:
        erros.append(Erro("tipo", "tipo desconhecido: %s" % grupo.tipo))
```

No lugar das linhas 218-224 (`classe`/`origem`/`pop` incondicionais):

```python
    if grupo.tipo in plan.TIPOS_DOWNSTREAM:
        if grupo.classe not in plan.CLASSES_CLIENTE:
            erros.append(Erro("classe", "grupo de %s exige uma classe" % grupo.tipo))
        if grupo.origem is None or grupo.origem not in ORIGENS_CLIENTE:
            erros.append(Erro("origem", "origem obrigatoria, faixa 1xxx do plano"))
        if grupo.pop is None:
            erros.append(Erro("pop", "pop em branco: informe o POP do plano, de 2001 a 2999"))
        elif not (plan.POP_MIN <= grupo.pop <= plan.POP_MAX):
            erros.append(Erro("pop", "POP entre 2001 e 2999"))
    else:
        # a default route e servico de downstream, e o comando sai dos
        # macro que os cinco tipos usam: sem esta checagem um POST a mao
        # ligaria o anuncio da default para quem nao pediu.
        if grupo.default_route:
            erros.append(Erro(
                "default_route",
                "default route so em cliente ou parceiro: o %s nao a recebe"
                % grupo.tipo))
        # mais estrito que o caminho do peer de proposito: ORIGENS_POR_TIPO
        # diz quais origens cada tipo carrega, e um grupo de upstream com
        # origem de cliente carimba a rota mentindo sobre a procedencia. O
        # peer fica como esta; alinha-lo e mudanca separada (ver a spec).
        permitidas = plan.ORIGENS_POR_TIPO.get(grupo.tipo, ())
        if grupo.origem is None or grupo.origem not in permitidas:
            erros.append(Erro(
                "origem",
                "origem do %s tem que ser uma de %s"
                % (grupo.tipo, ", ".join(str(o) for o in permitidas))))
```

Depois do bloco de `lp_base`, entram os ramos por tipo:

```python
    if grupo.tipo in ("upstream", "ix"):
        if grupo.aprendizado is None:
            erros.append(Erro("aprendizado", "ponto de aprendizado 3xxx obrigatorio"))
        elif not (plan.APRENDIZADO_MIN <= grupo.aprendizado <= plan.APRENDIZADO_MAX):
            erros.append(Erro("aprendizado", "ponto de aprendizado entre 3000 e 3999"))
    if grupo.tipo == "ix" and not grupo.ix_id:
        erros.append(Erro("ix_id", "sessao de IX exige o ID do IX no PeeringDB"))
    if grupo.tipo == "pni" and not grupo.ap_allowed:
        erros.append(Erro("ap_allowed", "PNI sem allowlist de AS-path nao sobe"))
```

Junto do `_valida_prefixos` e do `_valida_timer` que já estão lá, entra:

```python
    # a tabela da spec lista as regras POR TIPO; esta e compartilhada, como a
    # faixa do lp_base e o timer. O campo tem o mesmo destino do campo do
    # peer (a CL-PEER-<G>) e o mesmo risco: community malformada passa pelo
    # cadastro e so estoura no equipamento.
    _valida_communities(grupo, erros)
```

O comentário do `_valida_prefixos`, para o caso de o campo ficar preenchido num tipo que não o usa:

```python
    # o campo so e preenchido pela tela em cliente/parceiro, mas a checagem
    # de formato fica de pe para os cinco: lista vazia passa, e um POST a mao
    # com prefixo torto nao pode chegar ao render
    _valida_prefixos(grupo, erros)
```

- [ ] **Step 4: Rodar e ver passar**

```bash
.venv/bin/python -m pytest tests/test_validate.py -q && .venv/bin/python -m pytest -q
```

Esperado: PASS. Se algum teste de `test_app.py` quebrar por causa de um grupo gravado com `tipo="parceiro"` sem classe, conferir a fixture: `_contexto_grupo` e `grupo_do_formulario` só preenchem `classe`/`origem`/`pop` para downstream, e a Task 1 já ajustou o `id`.

- [ ] **Step 5: Commit**

```bash
git add app/validate.py tests/test_validate.py
git commit -m "Grupo valida os cinco tipos, com a origem presa a tabela do tipo"
```

---

## Task 9: O formulário por tipo

A tela do grupo mostra os campos do tipo escolhido, com a mesma mecânica da tela do peer: o JS lê `PADROES` (o mesmo blob de `_padroes()`) e as tabelas do `plan`, em vez de repetir valor.

**Files:**
- Modify: `app/app.py:516-534` (`_contexto_grupo`), `app/app.py:250-303` (`grupo_do_formulario`), `app/app.py:32-33` (`CAMPOS_INT_GRUPO`)
- Modify: `templates/pagina_grupo.html`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `_padroes()` (inalterado: já tem `tipos`, `origem_tipo`, `origem_classe`, `downstream`, `origens_por_tipo`, `origem_nome`), `plan.ORIGENS_POR_TIPO`, `plan.TIPOS`
- Produces: `_contexto_grupo` com as chaves `TIPOS` e `PADROES`; `grupo_do_formulario` lendo `aprendizado`, `ix_id`, `te_prefixos_<fam>`, `communities`, `large_communities`, `ap_block`, `ap_te`, `ap_allowed`, `ap_prefer`, `bh_upstream`, `prepend_base`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_app.py`:

```python
def test_o_formulario_de_grupo_oferece_os_cinco_tipos(cliente):
    r = cliente.get("/grupo/novo")
    assert _opcoes(r.text, "tipo") == list(plan.TIPOS)


def test_o_lp_base_do_grupo_novo_acompanha_o_tipo(cliente):
    # o formulario em branco nasce com o LP do tipo, como o do peer: o
    # parceiro empata com o cliente em 300
    for tipo, esperado in (("upstream", 100), ("ix", 190), ("pni", 200)):
        r = cliente.get("/grupo/novo?tipo=%s" % tipo)
        assert 'name="lp_base" value="%d"' % esperado in r.text, tipo


def test_o_select_de_origem_do_grupo_so_oferece_a_lista_do_tipo(cliente):
    for tipo in plan.TIPOS:
        r = cliente.get("/grupo/novo?tipo=%s" % tipo)
        oferecidas = set(_opcoes(r.text, "origem"))
        permitidas = set(str(o) for o in plan.ORIGENS_POR_TIPO[tipo])
        assert oferecidas == permitidas, (tipo, oferecidas, permitidas)


def test_o_grupo_marca_os_campos_por_tipo(cliente):
    # data-para diz ao JS quais blocos mostrar; o HTML ja sai com o certo
    # para o tipo gravado, e o JS so corrige depois de uma troca
    r = cliente.get("/grupo/novo?tipo=upstream")
    assert 'data-para="upstream"' in r.text


def test_salvar_grupo_de_upstream_grava_os_campos_do_tipo(cliente, tmp_path):
    r = cliente.post("/grupo", data={
        "nome": "BRDIGITAL", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "te_prefixos_v4": "1.1.1.0/24", "ap_block": "64500",
        "ap_te": "64501", "bh_upstream": "14840:666", "prepend_base": "2",
        "communities": "14840:9133", "large_communities": "14840:1:3333",
    }, follow_redirects=False)
    assert r.status_code == 303
    g = peers_mod.carregar_grupos(tmp_path / "peers.yaml")[0]
    assert (g.tipo, g.aprendizado, g.prepend_base) == ("upstream", 3100, 2)
    assert g.te_prefixos["v4"] == ["1.1.1.0/24"]
    assert g.communities == ["14840:9133"]
    assert g.large_communities == ["14840:1:3333"]


def test_o_salvar_do_grupo_nao_perde_o_bh_upstream(cliente, tmp_path):
    # bh_upstream ja estava no dataclass e ja era lido pelo
    # grupo_do_formulario, mas nao tinha campo na tela: um salvar pela
    # pagina zerava o valor sem avisar
    cliente.post("/grupo", data={
        "nome": "BRDIGITAL", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "bh_upstream": "14840:666",
    }, follow_redirects=False)
    cliente.post("/grupo", data={
        "nome": "BRDIGITAL", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "bh_upstream": "14840:666",
    }, follow_redirects=False)
    g = peers_mod.carregar_grupos(tmp_path / "peers.yaml")[0]
    assert g.bh_upstream == "14840:666"


def test_grupo_com_aprendizado_torto_volta_com_erro(cliente, tmp_path):
    r = cliente.post("/grupo", data={
        "nome": "BRDIGITAL", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "abc",
    })
    assert "valor numerico invalido" in r.text
```

`_opcoes` já existe em `tests/test_app.py` (usada na linha 232). `peers_mod` e `plan` já estão importados.

- [ ] **Step 2: Rodar e confirmar que falham**

```bash
.venv/bin/python -m pytest tests/test_app.py -k grupo -v
```

Esperado: FAIL. O `select` de tipo do template lista `["cliente", "parceiro", "upstream"]` fixo, não tem campo de `origem` (é `<input>`), não tem `data-para` e não tem `aprendizado`.

- [ ] **Step 3: Passar `TIPOS` e `PADROES` para a tela do grupo**

Em `app/app.py`, o `_contexto_grupo` (linha 516) ganha duas chaves:

```python
        "CLASSES_CLIENTE": plan.CLASSES_CLIENTE,
        "TIPOS": plan.TIPOS,
        "PADROES": _padroes(),
        "saida": saida,
```

`grupo_novo` (linha 537) passa a aceitar o tipo pela query, como o `/peer/novo`:

```python
@app.get("/grupo/novo", response_class=HTMLResponse)
def grupo_novo(request: Request, tipo: str = "parceiro"):
    # o formulario em branco ja vem com os defaults da tabela do plano, e o
    # tipo da query e o que o select da tela de peer usa para nascer certo
    if tipo not in plan.TIPOS:
        tipo = "parceiro"
    k, h = plan.TIMER_PADRAO.get(tipo, (None, None))
    grupo = Grupo(tipo=tipo,
                  id=peers_mod.proximo_id(lista(), lista_grupos()),
                  lp_base=plan.LP_BASE.get(tipo, 300),
                  origem=_origem_padrao(tipo),
                  timer_keepalive=k, timer_hold=h)
    return templates.TemplateResponse(
        request, "pagina_grupo.html",
        _contexto_grupo(request, grupo, criando=True))
```

- [ ] **Step 4: Ler os campos novos no `grupo_do_formulario`**

`CAMPOS_INT_GRUPO` (linha 32) ganha os dois inteiros novos:

```python
CAMPOS_INT_GRUPO = ("id", "asn", "lp_base", "origem", "pop", "aprendizado",
                    "ix_id", "prepend_base", "timer_keepalive", "timer_hold")
```

O construtor do `Grupo` dentro de `grupo_do_formulario` (linha 289) ganha:

```python
        aprendizado=valores.get("aprendizado"),
        ix_id=valores.get("ix_id"),
        te_prefixos={f: _linhas(dados, "te_prefixos_%s" % f) for f in plan.FAMILIAS},
        communities=_linhas(dados, "communities"),
        large_communities=_linhas(dados, "large_communities"),
```

e o `classe` deixa de ser forçado a string vazia quando o tipo não é downstream. A linha atual:

```python
        classe=_texto(dados, "classe") or None,
```

passa a:

```python
        # o campo so aparece em cliente/parceiro. Num tipo que nao o usa, o
        # hidden nao existe e o form manda vazio: guardar None e o que a
        # validacao cobra depois, sem classe orfa num grupo de upstream
        classe=(_texto(dados, "classe") or None
                if tipo in plan.TIPOS_DOWNSTREAM else None),
        origem=valores.get("origem"),
        pop=valores.get("pop") if tipo in plan.TIPOS_DOWNSTREAM else None,
```

- [ ] **Step 5: Reescrever o formulário de `templates/pagina_grupo.html`**

Substituir o `select` de tipo (linhas 100-108) por um que lê `TIPOS`:

```jinja
     <label class="campo{{ ' campo-com-erro' if erros.get('tipo') }}" id="f-tipo">
      <span class="rotulo">tipo</span>
      <select name="tipo">
       {% for t in TIPOS %}
       <option value="{{ t }}"{{ " selected" if grupo.tipo == t }}>{{ t }}</option>
       {% endfor %}
      </select>
      {% if erros.get('tipo') %}<span class="msg-erro">{{ erros.get('tipo') }}</span>{% endif %}
     </label>
```

Envolver `asn`, `classe` e `origem`/`pop` nos blocos por tipo. `asn` fica para os cinco:

```jinja
     <label class="campo{{ ' campo-com-erro' if erros.get('asn') }}" id="f-asn">
      <span class="rotulo">ASN do grupo</span>
      <input name="asn" value="{{ grupo.asn or '' }}">
      <span class="ajuda">em branco = cada membro declara o proprio</span>
      {% if erros.get('asn') %}<span class="msg-erro">{{ erros.get('asn') }}</span>{% endif %}
     </label>
    </div>
   </fieldset>

   {# data-para diz ao JS quais blocos valem para o tipo escolhido. O HTML ja
      sai com o certo para o tipo gravado; o JS so corrige depois de uma
      troca no select, sem recarregar a pagina. #}
   <div data-para="cliente parceiro">
    <fieldset class="secao">
     <legend>downstream</legend>
     <div class="campos">
      <label class="campo{{ ' campo-com-erro' if erros.get('classe') }}" id="f-classe">
       <span class="rotulo">classe</span>
       <select name="classe">
        <option value="">&mdash; sem classe &mdash;</option>
        {% for c in CLASSES_CLIENTE %}
        <option value="{{ c }}"{{ " selected" if grupo.classe == c }}>{{ c }}</option>
        {% endfor %}
       </select>
       {% if erros.get('classe') %}<span class="msg-erro">{{ erros.get('classe') }}</span>{% endif %}
      </label>
      <label class="campo{{ ' campo-com-erro' if erros.get('pop') }}" id="f-pop">
       <span class="rotulo">POP <span class="tag">2001-2999</span></span>
       <input name="pop" value="{{ grupo.pop if grupo.pop is not none else '' }}">
       {% if erros.get('pop') %}<span class="msg-erro">{{ erros.get('pop') }}</span>{% endif %}
      </label>
     </div>
    </fieldset>
   </div>
```

O campo `origem` sai de onde está e vira o primeiro do bloco `politica`, como `select`:

```jinja
   <fieldset class="secao">
    <legend>politica</legend>
    <div class="campos">
     <label class="campo{{ ' campo-com-erro' if erros.get('origem') }}" id="f-origem">
      <span class="rotulo">origem <span class="tag">1xxx</span></span>
      <select name="origem">
       {% for o in plan.ORIGENS_POR_TIPO[grupo.tipo] %}
       <option value="{{ o }}"{{ " selected" if grupo.origem == o }}>{{ o }} - {{ plan.ORIGEM_NOME[o] }}</option>
       {% endfor %}
      </select>
      <span class="ajuda">a lista muda com o tipo</span>
      {% if erros.get('origem') %}<span class="msg-erro">{{ erros.get('origem') }}</span>{% endif %}
     </label>
     <label class="campo{{ ' campo-com-erro' if erros.get('lp_base') }}" id="f-lp_base">
      <span class="rotulo">LP base</span>
      <input name="lp_base" value="{{ grupo.lp_base }}">
      <span class="ajuda">o membro sem lp_base proprio usa este</span>
      {% if erros.get('lp_base') %}<span class="msg-erro">{{ erros.get('lp_base') }}</span>{% endif %}
     </label>
     <label class="campo campo-caixa{{ ' campo-com-erro' if erros.get('default_route') }}" id="f-default_route">
      <input type="checkbox" name="default_route"{{ " checked" if grupo.default_route }}>
      <span class="rotulo">default-route-advertise <span class="tag">cliente / parceiro</span></span>
      {% if erros.get('default_route') %}<span class="msg-erro">{{ erros.get('default_route') }}</span>{% endif %}
     </label>
    </div>
   </fieldset>
```

Depois do fieldset de `limites e timers`, e antes do de prefixos, entram os três blocos por tipo:

```jinja
   <div data-para="upstream">
    <fieldset class="secao">
     <legend>upstream</legend>
     <div class="campos">
      <label class="campo{{ ' campo-com-erro' if erros.get('aprendizado') }}" id="f-aprendizado">
       <span class="rotulo">aprendizado <span class="tag">3000-3999</span></span>
       <input name="aprendizado" value="{{ grupo.aprendizado if grupo.aprendizado is not none else '' }}">
       {% if erros.get('aprendizado') %}<span class="msg-erro">{{ erros.get('aprendizado') }}</span>{% endif %}
      </label>
      <label class="campo{{ ' campo-com-erro' if erros.get('bh_upstream') }}" id="f-bh_upstream">
       <span class="rotulo">blackhole do upstream</span>
       <input name="bh_upstream" value="{{ grupo.bh_upstream }}">
       <span class="ajuda">a community que marca o host atacado, so no RTBH</span>
      </label>
      <label class="campo{{ ' campo-com-erro' if erros.get('prepend_base') }}" id="f-prepend_base">
       <span class="rotulo">prepend base</span>
       <input name="prepend_base" value="{{ grupo.prepend_base }}">
      </label>
      <label class="campo campo-largo">
       <span class="rotulo">ap_block <span class="tag">um ASN por linha</span></span>
       <textarea name="ap_block" rows="3">{{ grupo.ap_block|join("\n") }}</textarea>
      </label>
      <label class="campo campo-largo">
       <span class="rotulo">ap_te <span class="tag">um ASN por linha</span></span>
       <textarea name="ap_te" rows="3">{{ grupo.ap_te|join("\n") }}</textarea>
      </label>
      <label class="campo campo-largo">
       <span class="rotulo">PL-TE-PREFER v4 <span class="tag">um CIDR por linha</span></span>
       <textarea name="te_prefixos_v4" rows="3">{{ grupo.te_prefixos["v4"]|join("\n") }}</textarea>
      </label>
      <label class="campo campo-largo">
       <span class="rotulo">PL-TE-PREFER v6 <span class="tag">um CIDR por linha</span></span>
       <textarea name="te_prefixos_v6" rows="3">{{ grupo.te_prefixos["v6"]|join("\n") }}</textarea>
      </label>
      <label class="campo campo-largo">
       <span class="rotulo">CL-PEER <span class="tag">a community da rede remota</span></span>
       <textarea name="communities" rows="3">{{ grupo.communities|join("\n") }}</textarea>
      </label>
      <label class="campo campo-largo">
       <span class="rotulo">LC-PEER <span class="tag">a versao de 32 bits</span></span>
       <textarea name="large_communities" rows="3">{{ grupo.large_communities|join("\n") }}</textarea>
      </label>
     </div>
    </fieldset>
   </div>

   <div data-para="ix">
    <fieldset class="secao">
     <legend>IX</legend>
     <div class="campos">
      <label class="campo{{ ' campo-com-erro' if erros.get('aprendizado') }}" id="f-aprendizado">
       <span class="rotulo">aprendizado <span class="tag">3000-3999</span></span>
       <input name="aprendizado" value="{{ grupo.aprendizado if grupo.aprendizado is not none else '' }}">
       {% if erros.get('aprendizado') %}<span class="msg-erro">{{ erros.get('aprendizado') }}</span>{% endif %}
      </label>
      <label class="campo{{ ' campo-com-erro' if erros.get('ix_id') }}" id="f-ix_id">
       <span class="rotulo">ID do IX <span class="tag">PeeringDB</span></span>
       <input name="ix_id" value="{{ grupo.ix_id if grupo.ix_id is not none else '' }}">
       {% if erros.get('ix_id') %}<span class="msg-erro">{{ erros.get('ix_id') }}</span>{% endif %}
      </label>
      <label class="campo campo-largo">
       <span class="rotulo">ap_prefer <span class="tag">um ASN por linha</span></span>
       <textarea name="ap_prefer" rows="3">{{ grupo.ap_prefer|join("\n") }}</textarea>
       <span class="ajuda">estes membros recebem LP 250 em vez do LP base</span>
      </label>
     </div>
    </fieldset>
   </div>

   <div data-para="pni">
    <fieldset class="secao">
     <legend>PNI</legend>
     <div class="campos">
      <label class="campo campo-largo">
       <span class="rotulo">ap_allowed <span class="tag">um ASN por linha</span></span>
       <textarea name="ap_allowed" rows="3">{{ grupo.ap_allowed|join("\n") }}</textarea>
       <span class="ajuda">so estes ASNs podem chegar por esta sessao</span>
      </label>
     </div>
    </fieldset>
   </div>
```

O fieldset de prefixos ganha o envoltório:

```jinja
   <div data-para="cliente parceiro">
    <fieldset class="secao{{ ' campo-com-erro' if erros.get('prefixos') }}" id="f-prefixos">
     ...
    </fieldset>
   </div>
```

O `ancoraveis` (linha 68) ganha os nomes novos:

```jinja
  {% set ancoraveis = ['nome', 'tipo', 'asn', 'classe', 'origem', 'pop',
                       'lp_base', 'aprendizado', 'ix_id', 'bh_upstream',
                       'prepend_base', 'timer_keepalive', 'timer_hold',
                       'prefixos', 'prefixos_v4', 'prefixos_v6',
                       'default_route', 'confirmado'] %}
```

O `id` escondido e o botão salvar não mudam. O formulário precisa do `data-tipo` no `<body>` para o JS ler o tipo inicial sem consultar o select:

```jinja
<body data-tipo="{{ grupo.tipo }}">
```

- [ ] **Step 6: Acrescentar o JS da cascata**

Em `templates/pagina_grupo.html`, logo depois do `{% include "_estilo.html" %}`, antes de `</head>`:

```jinja
{# As tabelas do plan.py chegam inteiras, e o JS so as le: nenhum valor de
   politica e reescrito na tela. E o mesmo blob da tela do peer, o mesmo
   `PADROES` do _padroes(), sem uma segunda copia para divergir. #}
<script id="padroes" type="application/json">{{ PADROES|tojson }}</script>
<script>
(function () {
 "use strict";
 var blob = document.getElementById("padroes");
 if (!blob) return;
 var p = JSON.parse(blob.textContent);

 function campo(nome) { return document.querySelector('[name="' + nome + '"]'); }
 function texto(nome) { var c = campo(nome); return c ? c.value : null; }
 function poe(nome, v) {
  var c = campo(nome);
  if (c && v !== null && v !== undefined) c.value = String(v);
 }

 // os blocos marcados com data-para so aparecem no tipo escolhido. O HTML
 // ja nasce certo para o tipo gravado; esta funcao corrige depois de uma
 // troca no select, que e o que o operador faz antes de salvar.
 function mostraCampos(tipo) {
  var blocos = document.querySelectorAll("[data-para]");
  for (var i = 0; i < blocos.length; i++) {
   var vale = blocos[i].getAttribute("data-para").split(" ");
   blocos[i].hidden = vale.indexOf(tipo) < 0;
  }
 }

 // a lista de origem muda com o tipo, e a origem do upstream nao serve no
 // cliente: trocar o tipo obriga a redesenhar as opcoes
 function redesenhaOrigens(tipo, manter) {
  var sel = campo("origem");
  if (!sel) return;
  var lista = p.origens_por_tipo[tipo] || p.origens_por_tipo.cliente;
  var escolhido = lista.indexOf(manter) >= 0 ? manter : lista[0];
  sel.innerHTML = "";
  for (var i = 0; i < lista.length; i++) {
   var o = document.createElement("option");
   o.value = String(lista[i]);
   o.textContent = " " + lista[i] + " - " + p.origem_nome[String(lista[i])];
   o.selected = lista[i] === escolhido;
   sel.appendChild(o);
  }
 }

 var tipoAnterior = document.body.getAttribute("data-tipo");

 function cascata() {
  var tipo = texto("tipo");
  var antes = p.tipos[tipoAnterior];
  var agora = p.tipos[tipo];

  // so reescreve o campo que ainda esta no default do tipo anterior: o que
  // o operador ja digitou por cima fica onde esta
  if (tipo !== tipoAnterior && antes && agora) {
   if (texto("lp_base") === String(antes.lp_base)) poe("lp_base", agora.lp_base);
   if (texto("timer_keepalive") === String(antes.timer_keepalive)) poe("timer_keepalive", agora.timer_keepalive);
   if (texto("timer_hold") === String(antes.timer_hold)) poe("timer_hold", agora.timer_hold);
  }

  if (tipo !== tipoAnterior) {
   mostraCampos(tipo);
   redesenhaOrigens(tipo, Number(texto("origem")));
  }

  tipoAnterior = tipo;
 }

 mostraCampos(tipoAnterior);
 var st = campo("tipo");
 if (st) st.addEventListener("change", cascata);
})();
</script>
```

- [ ] **Step 7: Rodar e ver passar**

```bash
.venv/bin/python -m pytest tests/test_app.py -q && .venv/bin/python -m pytest -q
```

Esperado: PASS. Conferir também na mão, porque o JS não é coberto por teste:

```bash
.venv/bin/python -m uvicorn app.app:app --port 8765 &
sleep 2
curl -s localhost:8765/grupo/novo?tipo=upstream | grep -c 'data-para="upstream"'
kill %1
```

Esperado: pelo menos `1`. Abrir `http://localhost:8765/grupo/novo?tipo=upstream` no navegador, trocar o `select` de tipo para `pni` e conferir que o bloco de PNI aparece, o de upstream some e o LP base vira 200.

- [ ] **Step 8: Commit**

```bash
git add app/app.py templates/pagina_grupo.html tests/test_app.py
git commit -m "A tela do grupo mostra os campos do tipo escolhido"
```

---

## Task 10: O quadro "ao criar" do grupo de upstream

`criar_lista.txt.j2` gera o `CL-PEER-<T>` vazio mais o `APPLY-PEER-<T>`, e o bloco do peer só chama o filtro. Isso é o que garante que reaplicar o bloco nunca mexe no que o operador escreveu na lista. Com `communities` no grupo de upstream, o grupo precisa do mesmo quadro. IX e PNI continuam sem: o egress do IX não tem `APPLY-PEER`, e o do PNI também não.

**Files:**
- Modify: `templates/criar_lista.txt.j2` (dual-alvo)
- Modify: `app/render.py:60-62` (`render_criar_lista` → dual-alvo)
- Modify: `app/app.py` (rota nova, logo depois de `grupo_saida` na linha 619)
- Modify: `templates/pagina_grupo.html` (abas da saída)
- Test: `tests/test_render.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `m.apply_peer(alvo)`, `plan.TIPOS_COM_APPLY_PEER`, `grupo.communities`, `grupo.large_communities`, `grupo.token` (`= grupo.nome`)
- Produces: `render.render_criar_lista(alvo)` aceitando `Peer` ou `Grupo`; rota `GET /saida/grupo/{nome}/criar-lista`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_render.py`:

```python
def test_o_quadro_ao_criar_do_grupo_de_upstream():
    g = grupo_upstream(nome="BRDIGITAL", id=3,
                       communities=["14840:9133", "14840:9134"])
    texto = render.render_criar_lista(g)
    assert "xpl community-list CL-PEER-BRDIGITAL" in texto
    assert " 14840:9133," in texto
    assert " 14840:9134" in texto
    assert "xpl large-community-list LC-PEER-BRDIGITAL" in texto
    assert "xpl route-filter APPLY-PEER-BRDIGITAL" in texto


def test_o_quadro_ao_criar_do_grupo_sem_large_community():
    g = grupo_upstream(nome="BRDIGITAL", id=3, communities=["14840:9133"],
                       large_communities=[])
    assert "LC-PEER" not in render.render_criar_lista(g)


def test_o_quadro_ao_criar_do_grupo_de_ix_e_de_pni_nao_sai():
    # IX e PNI nao tem APPLY-PEER: o route server repassa o mesmo AS-path a
    # todos os membros, e o egress do PNI nao chama filtro nenhum
    for g in (grupo_ix(nome="IXBR", id=4), grupo_pni(nome="CDN", id=5)):
        assert render.render_criar_lista(g).strip() == ""
```

Em `tests/test_app.py`:

```python
def test_a_saida_do_grupo_de_upstream_oferece_o_quadro_ao_criar(cliente, tmp_path):
    cliente.post("/grupo", data={
        "nome": "BRDIGITAL", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "communities": "14840:9133",
    }, follow_redirects=False)
    r = cliente.get("/saida/grupo/BRDIGITAL")
    assert "/saida/grupo/BRDIGITAL/criar-lista" in r.text


def test_a_saida_do_grupo_de_ix_nao_oferece_o_quadro(cliente, tmp_path):
    cliente.post("/grupo", data={
        "nome": "IXBR", "tipo": "ix", "id": "4", "asn": "26162",
        "lp_base": "190", "origem": "1300", "aprendizado": "3200",
        "ix_id": "1234",
    }, follow_redirects=False)
    r = cliente.get("/saida/grupo/IXBR")
    assert "/saida/grupo/IXBR/criar-lista" not in r.text


def test_o_quadro_ao_criar_do_grupo_nao_vira_rota_de_peer(cliente, tmp_path):
    # a rota de peer acha por token e a de grupo por nome; passar um nome de
    # grupo na rota de peer tem que redirecionar, nao estourar
    cliente.post("/grupo", data={
        "nome": "BRDIGITAL", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
    }, follow_redirects=False)
    r = cliente.get("/saida/BRDIGITAL/criar-lista", follow_redirects=False)
    assert r.status_code == 303
```

- [ ] **Step 2: Rodar e confirmar que falham**

```bash
.venv/bin/python -m pytest tests/test_render.py -k ao_criar -v
```

Esperado: FAIL com `jinja2.exceptions.UndefinedError: 'Grupo' has no attribute 'apelido'` (ou `communities` lido de um `grupo` que o template chama de `peer`), porque `criar_lista.txt.j2` só conhece `peer`.

- [ ] **Step 3: Tornar o `criar_lista.txt.j2` dual-alvo**

O template inteiro:

```jinja
{% import "_macros.j2" as m %}
{# O alvo e o peer avulso ou o grupo de upstream: a CL-PEER de um upstream
   descreve a REDE REMOTA, nao o link, entao ela mora no grupo e o quadro sai
   uma vez para os dois links em vez de uma por membro. #}
{% set alvo = grupo if grupo else peer %}
{% if alvo.tipo in plan.TIPOS_COM_APPLY_PEER %}
# gerado por bgpgen - nao editar a mao
# ao criar o {{ "grupo" if grupo else "peer" }} {{ alvo.id }} - {{ alvo.tipo }}{% if not grupo %} - AS{{ alvo.asn }}{% endif %}
# Cole este quadro na primeira vez que a sessao subir, e de novo quando a
# lista mudar: re-colar troca o conteudo pelo que esta no cadastro.
# O bloco do {{ "grupo" if grupo else "peer" }} so chama o filtro, entao
# reaplicar o bloco nunca mexe no que voce escreveu aqui.

xpl community-list CL-PEER-{{ alvo.token }}
{% for c in alvo.communities %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
end-list

{% if alvo.large_communities %}
xpl large-community-list LC-PEER-{{ alvo.token }}
{% for c in alvo.large_communities %}
 {{ c }}{{ "," if not loop.last }}
{% endfor %}
end-list
{% endif %}
{{ m.apply_peer(alvo) }}
{% endif %}
```

- [ ] **Step 4: Tornar o `render_criar_lista` dual-alvo**

`app/render.py:60-62`:

```python
def render_criar_lista(peer=None, grupo=None):
    """O quadro 'ao criar': a CL-PEER-<T> vazia, colada uma vez so.

    Serve o peer avulso e o grupo de upstream, que sao os dois donos
    possiveis de uma CL-PEER: o bloco so chama o filtro, entao colar o bloco
    de novo nunca mexe no que o operador escreveu aqui."""
    return ambiente().get_template("criar_lista.txt.j2").render(
        peer=peer, grupo=grupo)
```

- [ ] **Step 5: Acrescentar a rota do quadro do grupo**

Em `app/app.py`, logo depois de `grupo_saida` (linha 619):

```python
@app.get("/saida/grupo/{nome}/criar-lista", response_class=HTMLResponse)
def grupo_criar_lista(request: Request, nome: str):
    grupo = peers_mod.achar_grupo(lista_grupos(), nome)
    if grupo is None:
        return RedirectResponse("/", status_code=303)
    if grupo.tipo not in plan.TIPOS_COM_APPLY_PEER:
        # IX e PNI nao tem APPLY-PEER: o egress do IX nao chama filtro de
        # sessao e o do PNI tambem nao, entao o quadro nao tem o que criar e
        # a tela nem oferece o link
        return RedirectResponse("/saida/grupo/%s" % grupo.nome, status_code=303)
    contexto = _contexto_grupo(request, grupo, criando=False)
    contexto["saida"] = render.render_criar_lista(grupo=grupo)
    return templates.TemplateResponse(request, "pagina_grupo.html", contexto)
```

- [ ] **Step 6: Oferecer o link na tela do grupo**

Em `templates/pagina_grupo.html`, nas abas da saída (linhas 252-255), o link só aparece para os tipos que têm o quadro:

```jinja
   <div class="abas">
    <a class="btn btn-fantasma" href="/grupo/{{ grupo.nome }}">editar grupo</a>
    <a class="btn btn-fantasma" href="/base.txt">bloco base</a>
    {% if grupo.tipo in plan.TIPOS_COM_APPLY_PEER %}
    <a class="btn btn-fantasma" href="/saida/grupo/{{ grupo.nome }}/criar-lista">ao criar o grupo</a>
    {% endif %}
   </div>
```

- [ ] **Step 7: Rodar e ver passar**

```bash
.venv/bin/python -m pytest -q
```

Esperado: PASS. `test_golden_da_remocao_do_cliente` e os testes de `render_criar_lista` do peer continuam valendo: a chamada de uma posição só passa a cair no `peer=` como palavra-chave.

- [ ] **Step 8: Commit**

```bash
git add templates/criar_lista.txt.j2 app/render.py app/app.py \
        templates/pagina_grupo.html tests/test_render.py tests/test_app.py
git commit -m "Quadro ao criar o grupo de upstream, com a CL-PEER da rede remota"
```

---

## Task 11: PLANO.md

O `PLANO.md` é a razão do repositório existir, e nenhuma das duas seções novas está nele. Sem elas o documento descreve um plano que o gerador já não segue: o identificador passa a ser compartilhado e os cinco tipos passam a ter grupo.

**Files:**
- Modify: `PLANO.md`
- Test: leitura. Não há teste de documento; a conferência é a consistência com o que as Tasks 1, 5, 6 e 8 geram.

**Interfaces:**
- Consumes: os números reais das `Tabela de peers e IDs` (a fonte de verdade dos valores), `plan.TIPOS`, `plan.c5ppa`
- Produces: duas seções novas no `PLANO.md`

- [ ] **Step 1: Acrescentar a seção de identificador compartilhado**

Logo depois da "Tabela de peers e IDs", entra uma seção com este conteúdo, ajustando os nomes de peer e grupo aos valores reais que a tabela já tem:

```markdown
## Identificador compartilhado entre peer e grupo

O identificador de dois dígitos é um recurso único do AS64512, e não um campo
de cada cadastro. Peers e grupos disputam os mesmos 100 números, porque o
mesmo número aparece no eixo de community dos dois: `plan.c5ppa` monta
`64512:5<id><papel>`, com dois dígitos de identificador e um de papel, e a
`CL-NOADV-<T>` de um grupo carrega o identificador do grupo.

Consequências que valem para quem edita a tabela acima:

- Um número pertence a um peer ou a um grupo, nunca aos dois. O gerador
  recusa o cadastro que colide, nos dois sentidos, em vez de renumerar.
- A faixa é 0 a 99, sem exceção. Fora dela o `%02d` do `c5ppa` truncaria
  calado, e dois cadastros escreveriam a mesma community.
- Renumerar um cadastro é decisão do operador, porque o número é publicado:
  ele aparece na community que o cliente escreve para pedir prepend, e mudá-lo
  sem aviso quebra o que já foi combinado.
- Um grupo de cliente ou de parceiro não emite `5PPA`, então o número dele é
  reservado mesmo quando não aparece em configuração nenhuma.
```

- [ ] **Step 2: Acrescentar a seção de grupo por tipo**

Logo depois, com os nomes de objeto que os templates realmente emitem:

```markdown
## Grupo nos cinco tipos

Os cinco tipos podem ter grupo BGP no equipamento. O grupo existe para o caso
de vários links com uma política só: dois ou três acessos ao mesmo trânsito,
um IX visto por mais de um route server, um PNI com mais de um link direto.
Sem grupo, cada link é um cadastro avulso que repete o mesmo filtro com um
token diferente, e a política dos dois diverge na primeira edição feita num só.

O que o grupo carrega e o membro herda:

| Tipo | Objetos do grupo | O que o membro acrescenta |
| --- | --- | --- |
| `cliente`, `parceiro` | `CUST-<G>-IMPORT/EXPORT-<U>`, `PL-CUST-<G>-<U>` e a de blackhole, `AP-CUST-<G>` | o `route-limit` e, se o link tiver prefixo próprio, o filtro de import dele |
| `upstream` | `UP-<G>-IMPORT/EXPORT-<U>`, `PL-TE-PREFER-<G>-<U>`, `CL/LC-NOADV-<G>`, `CL-5PPA-<id>`, `LC-5PPA-<G>`, `LC-PREP1/2/3-<G>`, `AP-BLOCK-<G>`, `AP-TE-PREFER-<G>` | idem |
| `ix` | `IX-<G>-IMPORT/EXPORT-<U>`, `CL/LC-NOADV-<G>`, `AP-IX-<G>` | idem |
| `pni` | `PNI-<G>-IMPORT/EXPORT-<U>`, `CL/LC-NOADV-<G>`, `AP-<G>-ALLOWED` | idem |

O `<G>` é o nome do grupo e o `<U>` é `V4` ou `V6`.

Duas regras que valem para os cinco:

- O `route-limit` fica no membro, e não no grupo. Ele é da sessão, e um limite
  só para todos os membros apagaria o de cada um.
- O que é de sessão (AS-path confinado, timers, `bfd`, graceful-restart,
  `advertise-community`) sai uma vez, no bloco do grupo. O membro só referencia
  o `group`.

A community do bloco de sessão (`CL-PEER-<G>`) segue a mesma diferença entre
os tipos que a seção anterior descreve: num cliente ela descreve o link, e cada
membro pode ter a sua; num upstream ela descreve a rede remota, então mora no
grupo e vale para os dois links. Pelo mesmo motivo o grupo de upstream tem
quadro "ao criar" e o de IX e o de PNI não têm: o egress do IX não aplica
community de sessão nenhuma, e o do PNI também não.
```

- [ ] **Step 3: Conferir a consistência com o que o gerador emite**

```bash
grep -n "^## " PLANO.md
```

Esperado: a seção de identificador e a de grupo aparecem na ordem, e nenhuma seção existente saiu do lugar. Conferir as duas contra o texto gerado:

```bash
.venv/bin/python -c "
from app import plan, render
from tests.test_render import peer_upstream
print(plan.c5ppa(7, 0))
print([l for l in render.render_peer(peer_upstream(id=7)).splitlines()
       if '5PPA' in l][:3])"
```

Esperado: `64512:507` e as linhas de `CL-5PPA-07` / `LC-5PPA-<token>`, que é o `<G>`/`<id>` que a tabela nova descreve.

- [ ] **Step 4: Commit**

```bash
git add PLANO.md
git commit -m "PLANO descreve o identificador compartilhado e o grupo dos cinco tipos"
```

---

## Self-Review

**Cobertura da spec, seção por seção:**

| Seção da spec | Task |
| --- | --- |
| Problema / O que já existe e o que falta | Tasks 2 (campos), 5 e 6 (templates) |
| Escopo: os três tipos | Tasks 5, 6, 8 |
| Escopo: membros | Task 7 |
| Escopo: espaço de ids | Task 1 |
| Escopo: quadro "ao criar" | Task 10 |
| Escopo: `PLANO.md` | Task 11 |
| Modelo de dados (cinco campos) | Task 2 |
| `communities` no grupo | Task 2 (campo), Task 5 (o export chama o filtro), Task 10 (o quadro) |
| Macros de alvo duplo | Tasks 3 e 4 |
| Três templates de grupo | Tasks 5 e 6 |
| Nomes de objeto | Tasks 5, 6 e 7 (os `<PREFIXO>-<G>-...`) |
| Membros: gate nos três lugares | Task 7 (`cliente.txt.j2` não muda no gate, porque o `{% if grupo %}` dele é o modelo), Task 8 (`validar`) |
| Ruling `route-limit` | Task 7, Step 3, com teste próprio no Step 1 |
| Quadro "ao criar" | Task 10 |
| Formulário | Task 9 |
| Validação por tipo | Tasks 1 (id) e 8 (o resto) |
| Ruling origem fora de downstream | Task 8, Step 3 |
| Testes: identificador | Task 1 |
| Testes: extração byte a byte | Tasks 3 e 4 (os goldens que já existem) |
| Testes: grupo e membro por tipo | Tasks 5, 6 e 7 |
| Testes: `route-limit` no membro | Task 7 |
| Testes: validação por tipo | Tasks 1 e 8 |
| Testes: isolamento | Coberto pelo que existe em `tests/test_isolamento.py`; o `out` patcheado e o `escrever_grupo` novo já respeitam o padrão. Se a Task 5 passar a escrever grupo, acrescentar um caso de grupo ao `test_isolamento.py` no Step 4 dela |

**Pendências da spec que o plano resolve por decisão própria:**

- A ordem de implementação (pendência aberta pela spec): refatoração primeiro (Tasks 3 e 4), porque ela é a única parte que pode quebrar o que já funciona e tem os goldens como rede. Depois os templates de grupo, depois o membro, depois a validação, depois o formulário. Assim cada task tem teste rodando contra código que já existe.
- `poe`/`redesenhaOrigens`: portados da tela do peer em vez de reinventados, porque a spec pede "a mesma mecânica".
- `_valida_communities` no grupo: ruling registrado na Task 8, fora da tabela da spec.
- O `origem` da tela do grupo vira `select` alimentado por `plan.ORIGENS_POR_TIPO[tipo]`. A spec não pede a troca (o campo do grupo é `<input>` hoje), mas sem ela a lista por tipo não tem como aparecer na tela, e a validação da Task 8 recusa o que o campo livre aceitaria.
- `bh_upstream` e `prepend_base` já estavam no dataclass e já eram lidos pelo `grupo_do_formulario`, mas não tinham campo na tela do grupo: salvar pela página zerava o valor sem avisar. A Task 9 dá campo aos dois, com teste próprio.
