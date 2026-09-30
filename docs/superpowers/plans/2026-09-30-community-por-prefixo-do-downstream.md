# Community por prefixo do downstream — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o campo `prefixos` do peer aceitar a linha `cidr community community`, com o mesmo tratamento por prefixo que o bloco próprio já tem, e gerar a cláusula correspondente no import da sessão.

**Architecture:** O campo `prefixos` do `Peer` deixa de ser lista de CIDR em texto e passa a ser lista de `Bloco`, a mesma dataclass do bloco próprio, com leitura tolerante do yaml antigo e gravação que só muda de forma quando a linha tem tratamento. O template do import ganha uma cadeia `if/elseif` por prefixo, do mais longo para o mais curto, depois da CL-PEER. A tabela de recusa das communities é a mesma do bloco próprio, com o `1xx` a mais, porque a rota do downstream passa pelo `APPLY-CUSTOMER-LP`. Cliente e parceiro são o mesmo caminho: os dois saem do `cliente.txt.j2`.

**Tech Stack:** Python 3.14, FastAPI, Jinja2, PyYAML, pytest; React + TypeScript + Vitest no `web/`. Nenhuma dependência nova.

**Spec:** `docs/superpowers/specs/2026-09-29-community-por-prefixo-do-downstream-design.md`

## Global Constraints

- **Saída ASCII puro.** Nada de acento em template, comentário gerado ou nome de objeto. Comentário gerado usa `!-`, nunca `//` nem `#`.
- **A config de quem não usa a feature sai byte a byte igual.** Os `tests/golden/*.txt` são a prova, e nenhum deles pode ser reescrito nesta mudança.
- **Community sempre na forma completa `ASN:VALOR`.** O `_forma_ok` do validate exige o namespace, e o exemplo `613` da spec dos blocos próprios não passa.
- **`apply community` no import é sempre `additive`.** O tratamento por prefixo soma ao que a sessão carimbou; `overwrite` apaga.
- **O `!-` vale nas duas pontas:** no começo da linha, prefixo fora de serviço; no fim, marca do ausente na consulta ao IRR, ignorada no salvamento.
- **Prefixo longo demais é aviso, não erro.** O `peers.yaml` de hoje aceita essa linha, e virar erro travaria um salvamento que sempre funcionou.
- **Nada de `$` na saída gerada**, e literal com chave em Jinja passa pelo `plan`: escrever `{` colado a `{{` colide com o delimitador de expressão.
- **Testes Python:** `.venv/bin/python -m pytest` da raiz da worktree. O venv fica no checkout principal: `/Users/diorgera/Projetos/POLITICA_BGP/.venv/bin/python -m pytest`.
- **Testes do front:** `cd web && npm ci && npm test`. A worktree nasce sem `node_modules`; se o `npm ci` falhar por rede, pare e avise, porque o `schema.d.ts` da Task 5 sai dele.
- **O `web/src/api/schema.d.ts` é gerado** por `npm run api:tipos` e conferido por `tests/test_tipos_api.py`. Quem mexer no `modelos_api.py` regenera.
- **O grupo fica de fora:** o `prefixos` dele continua lista de CIDR em texto, e a linha com community ali é erro com mensagem própria. Nenhuma tarefa mexe no formulário, no template ou na validação de prefixo do grupo, além dessa recusa.
- **Toda tarefa termina com a suíte verde.** `.venv/bin/python -m pytest -q` antes do commit, e nenhum golden reescrito.

## Review Focus

O que mais provavelmente morde quem usar isto, em ordem:

1. **`peers.yaml` de mão com os dois formatos juntos** (a string de hoje e o dicionário novo no mesmo arquivo). Esperado: carrega, e um salvamento não muda a forma de quem não tem tratamento.
2. **`!-` nas duas pontas na mesma linha** (`!- 45.169.232.0/22 64512:210  !- nao veio na consulta ao IRR`). Esperado: prefixo fora de serviço, tratamento preservado, marca ignorada.
3. **Duas linhas onde uma contém a outra** (um /22 e um /24 dentro dele). Esperado: só o /24 aplica, e não os dois somados.
4. **Tenant com `asn_politica`** (namespace diferente de 64512). Esperado: a tabela de recusa usa o namespace da rede, e não o de fábrica.
5. **Prefixo torto no yaml, escrito à mão.** Esperado: o validate nomeia o campo e o prefixo, como hoje, e nada estoura num lugar novo.

Cada item desses tem o teste dele na tarefa dona do código.

---

## File Structure

```
app/plan.py            comprimento() e conjunto_do_prefixo(), o teto por familia
app/peers.py           canoniza(), Peer.prefixos como Bloco, cidrs(), tratamentos()
app/formulario.py      a linha da textarea <-> Bloco, e o texto de volta
app/validate.py        a tabela de recusa com lido_no_import, repetido, aviso do teto
app/api.py             modelo_do_peer com linhas, /api/irr mesclando, rede no validar
app/modelos_api.py     IrrPedido com as linhas da tela
templates/_macros.j2   a cadeia por prefixo no import, e cidrs() nas listas
web/src/telas/peers/   a ajuda do campo e o corpo do pedido do IRR
web/src/telas/grupos/  o mesmo no pedido do IRR do grupo
web/src/api/schema.d.ts  regerado
PLANO.md               o import do downstream e a referencia de sintaxe
tests/                 peers, formulario, validate, render, api, e o golden novo
```

---

> **Nota de execução (2026-09-30).** Duas coisas mudaram na execução, e as duas estão no ledger da worktree (`.superpowers/sdd/2026-09-30-community-por-prefixo-do-downstream/progress.md`): a **Task 2 foi absorvida pela Task 1**, porque trocar `Peer.prefixos` por `Bloco` quebra o `validate`, o `modelo_do_peer` e os dois laços de prefix-list no mesmo passo, e as adaptações mecânicas dos três tiveram que entrar junto para a suíte fechar verde; e o **"Expected" de suíte verde da Task 1** vale com essa fusão, não sem ela. As tarefas 3, 4, 5 e 6 correram como estão escritas.

---

### Task 1: O prefixo do peer vira Bloco

**Files:**
- Modify: `app/plan.py` (junto de `endereco` / `mascara`, por volta da linha 384)
- Modify: `app/peers.py` (`Peer`, `Grupo`, e os helpers novos perto de `Bloco`)
- Modify: `app/formulario.py:75-114` (o `_canoniza` muda de casa)
- Test: `tests/test_peers.py`, `tests/test_plan.py`

**Interfaces:**
- Consumes: `Bloco` de `app/peers.py:443`; `plan.FAMILIAS`.
- Produces: `plan.comprimento(cidr) -> int`; `peers.canoniza(cidr) -> str`; `Peers.prefixos: dict[str, list[Bloco]]`; `Peer.cidrs(fam) -> list[str]`; `Peer.tratamentos(fam) -> list[tuple[str, list[str]]]`; `Grupo.cidrs(fam) -> list[str]`; `Grupo.tratamentos(fam) -> list` (vazia).

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_peers.py`, no fim do arquivo:

```python
def test_o_prefixo_do_yaml_antigo_carrega_como_bloco(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text(
        "peers:\n"
        "- id: 1\n"
        "  asn: 268127\n"
        "  prefixos:\n"
        "    v4:\n"
        "    - 45.169.232.0/22\n",
        encoding="utf-8")
    (peer,) = mod.carregar(caminho)
    assert [b.prefixo for b in peer.prefixos["v4"]] == ["45.169.232.0/22"]
    assert peer.prefixos["v4"][0].communities == []


def test_o_prefixo_do_peer_e_canonico_na_leitura(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text(
        "peers:\n"
        "- id: 1\n"
        "  asn: 268127\n"
        "  prefixos:\n"
        "    v4:\n"
        "    - 45.169.232.9/22\n",
        encoding="utf-8")
    (peer,) = mod.carregar(caminho)
    assert peer.prefixos["v4"][0].prefixo == "45.169.232.0/22"


def test_o_prefixo_do_peer_carrega_o_tratamento_do_yaml(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text(
        "peers:\n"
        "- id: 1\n"
        "  asn: 268127\n"
        "  prefixos:\n"
        "    v4:\n"
        "    - prefixo: 45.169.232.0/22\n"
        "      communities: [64512:210, 64512:5070]\n"
        "    - 45.169.236.0/23\n",
        encoding="utf-8")
    (peer,) = mod.carregar(caminho)
    assert peer.prefixos["v4"][0].communities == ["64512:210", "64512:5070"]
    assert peer.prefixos["v4"][1].communities == []


def test_gravar_sem_tratamento_escreve_a_string_de_sempre(tmp_path):
    """Quem nunca usou a tela nao pode ganhar um diff de forma no peers.yaml."""
    caminho = tmp_path / "peers.yaml"
    mod.gravar([mod.Peer(id=1, asn=268127,
                         prefixos={"v4": ["45.169.232.0/22"], "v6": []})],
               caminho)
    texto = caminho.read_text(encoding="utf-8")
    assert "- 45.169.232.0/22" in texto
    assert "prefixo:" not in texto


def test_gravar_com_tratamento_escreve_o_dicionario(tmp_path):
    caminho = tmp_path / "peers.yaml"
    mod.gravar([mod.Peer(
        id=1, asn=268127,
        prefixos={"v4": [mod.Bloco(prefixo="45.169.232.0/22",
                                   communities=["64512:210"])], "v6": []})],
        caminho)
    texto = caminho.read_text(encoding="utf-8")
    assert "- prefixo: 45.169.232.0/22" in texto
    assert "communities:" in texto
    (peer,) = mod.carregar(caminho)
    assert peer.prefixos["v4"][0].communities == ["64512:210"]


def test_o_prefixo_fora_de_servico_sai_das_listas():
    peer = mod.Peer(prefixos={"v4": [
        mod.Bloco(prefixo="45.169.232.0/22", communities=["64512:210"]),
        mod.Bloco(prefixo="45.169.236.0/23", communities=["64512:211"],
                  ativo=False)], "v6": []})
    assert peer.cidrs("v4") == ["45.169.232.0/22"]
    assert [p for p, _ in peer.tratamentos("v4")] == ["45.169.232.0/22"]


def test_tratamentos_ordena_do_mais_longo_para_o_mais_curto():
    peer = mod.Peer(prefixos={"v4": [
        mod.Bloco(prefixo="45.169.232.0/22", communities=["64512:210"]),
        mod.Bloco(prefixo="45.169.232.0/24", communities=["64512:211"]),
        mod.Bloco(prefixo="45.169.236.0/24", communities=[])], "v6": []})
    assert [p for p, _ in peer.tratamentos("v4")] == [
        "45.169.232.0/24", "45.169.232.0/22"]


def test_o_grupo_nao_tem_tratamento_por_prefixo():
    grupo = mod.Grupo(nome="PARCEIROS", prefixos={"v4": ["45.169.232.0/22"],
                                                  "v6": []})
    assert grupo.cidrs("v4") == ["45.169.232.0/22"]
    assert grupo.tratamentos("v4") == []
```

Em `tests/test_plan.py`, no fim:

```python
def test_o_comprimento_do_cidr():
    assert plan.comprimento("45.169.232.0/22") == 22
    assert plan.comprimento("2804:36b4::/32") == 32
    # o torto devolve 0 em vez de estourar: quem recusa e o validate, e a
    # ordenacao nao pode ser mais um lugar que morre no mesmo dado
    assert plan.comprimento("nao-e-cidr") == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_peers.py -k "prefixo_do_yaml or gravar_sem_tratamento or fora_de_servico or tratamentos_ordena or grupo_nao_tem_tratamento" tests/test_plan.py -k comprimento -v`
Expected: FAIL com `AttributeError: 'str' object has no attribute 'prefixo'` e `AttributeError: module 'app.plan' has no attribute 'comprimento'`.

- [ ] **Step 3: Implementar o `plan.comprimento`**

Em `app/plan.py`, logo depois de `mascara`:

```python
def comprimento(cidr):
    """O comprimento da mascara, ou 0 no que nao analisa.

    O 0 nao esconde erro nenhum: CIDR torto ja e recusado pelo validate e
    ja estoura no `cidr_para_xpl` do render. Ele so evita que a ordenacao
    dos tratamentos e o aviso do teto sejam mais um lugar que morre no
    mesmo dado.
    """
    try:
        return _rede_do_cidr(cidr).prefixlen
    except ValueError:
        return 0
```

- [ ] **Step 4: Implementar o `canoniza`, o `__post_init__` e os helpers em `app/peers.py`**

Logo depois de `Bloco` (antes de `carregar_blocos`), entram:

```python
def canoniza(cidr):
    """O CIDR canonico, ou o texto como veio quando nao analisa.

    A barra e exigida antes de analisar: o ip_network aceita um endereco
    cru e devolve /32, e sem esta linha o validate nunca veria o texto
    original e o prefixo sairia anunciado como host route. O que nao
    analisa fica como veio, para o validate recusar e o operador ler a
    mensagem.
    """
    if "/" not in cidr:
        return cidr
    try:
        return str(ipaddress.ip_network(cidr, strict=False))
    except ValueError:
        return cidr


def _bloco(item):
    """Um item de `prefixos`: a string de hoje ou o Bloco ja montado."""
    if isinstance(item, Bloco):
        return item
    return Bloco(prefixo=canoniza(str(item)))


def _prefixo_gravado(bloco):
    """O item como ele vai para o yaml: string quando nao ha o que guardar.

    Um `peers.yaml` que nunca usou o tratamento continua com a lista de CIDR
    de sempre, e o primeiro salvamento de qualquer peer nao vira um diff de
    forma em todos os outros.
    """
    if bloco.ativo and not bloco.communities:
        return bloco.prefixo
    return bloco.para_dict()
```

Em `Peer`, logo depois do campo `politica_de`:

```python
    def __post_init__(self):
        """Todo item de `prefixos` e um Bloco, sem excecao.

        A normalizacao mora aqui, e nao no `de_dict`, porque o Peer nasce em
        tres caminhos: do yaml, do formulario e dos testes, que montam a
        lista de CIDR em texto. Um lugar so cobre os tres, e a lista de
        strings dos fixtures continua valendo.
        """
        self.prefixos = {
            fam: [_bloco(i) for i in (self.prefixos or {}).get(fam) or []]
            for fam in FAMILIAS}

    def cidrs(self, fam):
        """Os prefixos em servico da familia, para as duas prefix-lists."""
        return [b.prefixo for b in self.prefixos.get(fam) or [] if b.ativo]

    def tratamentos(self, fam):
        """(prefixo, communities) de cada linha com tratamento, na ordem da cadeia.

        Do mais longo para o mais curto: a cadeia do filtro e if/elseif, e
        um /24 escrito dentro de um /22 tem que vencer o /22. O empate fica
        na ordem do cadastro, porque o sorted do Python e estavel.
        """
        com_community = [b for b in self.prefixos.get(fam) or []
                         if b.ativo and b.communities]
        return sorted(((b.prefixo, list(b.communities)) for b in com_community),
                      key=lambda par: -plan.comprimento(par[0]))
```

Em `Peer.para_dict`, a linha do `prefixos` vira:

```python
            "prefixos": {fam: [_prefixo_gravado(b)
                               for b in self.prefixos.get(fam) or []]
                         for fam in FAMILIAS},
```

Em `Grupo`, antes do `para_dict`:

```python
    def cidrs(self, fam):
        """Os CIDR do grupo, que nao tem tratamento por prefixo.

        O metodo existe porque as macros do import sao de alvo duplo: o
        StrictUndefined do render estoura no teste quando o alvo nao tem o
        que a macro pede.
        """
        return list(self.prefixos.get(fam) or [])

    def tratamentos(self, fam):
        """O grupo nao tem community por prefixo: a linha dele e CIDR puro."""
        return []
```

- [ ] **Step 5: Mover o `_canoniza` para o `peers.py`**

Em `app/formulario.py`, apagar a função `_canoniza` (linhas 75 a 96) e trocar a chamada da linha 114 por `canoniza(pedacos[0])`. O import da linha 12 vira:

```python
from app.peers import Bloco, Grupo, Peer, canoniza
```

- [ ] **Step 6: Rodar os testes**

Run: `.venv/bin/python -m pytest tests/test_peers.py tests/test_plan.py tests/test_formulario.py tests/test_api_blocos.py -v`
Expected: PASS. Os testes antigos que montam `Peer(prefixos={"v4": ["45.169.232.0/22"]})` continuam passando, porque o `__post_init__` normaliza.

- [ ] **Step 7: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: 792 passed, 1 skipped (o mesmo baseline), mais os novos.

- [ ] **Step 8: Commit**

```bash
git add app/plan.py app/peers.py app/formulario.py tests/test_peers.py tests/test_plan.py
git commit -m "O prefixo do peer vira Bloco, com o tratamento por linha"
```

---

### Task 2 (absorvida pela Task 1): A ida e volta do campo na tela

**Files:**
- Modify: `app/formulario.py` (`_blocos_do_formulario`, `_texto_blocos`, e os helpers novos)
- Modify: `app/api.py:60-88` (`modelo_do_peer`)
- Test: `tests/test_formulario.py`, `tests/test_api_peers.py`

**Interfaces:**
- Consumes: `peers.canoniza`, `Bloco`, e o `Peer.prefixos` como `list[Bloco]` da Task 1.
- Produces: `form._bloco_da_linha(linha) -> Bloco | None`; `form._blocos_das_linhas(linhas) -> list[Bloco]`; `form._linha_do_bloco(bloco, marcado=False) -> str`; `form._linhas_de_blocos(blocos, ausentes=()) -> list[str]`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_formulario.py`, no fim:

```python
def test_a_linha_com_community_vira_bloco_com_ela():
    (bloco,) = formulario._blocos_das_linhas(["45.169.232.0/22 64512:210"])
    assert bloco.prefixo == "45.169.232.0/22"
    assert bloco.communities == ["64512:210"]
    assert bloco.ativo is True


def test_a_linha_fora_de_servico_guarda_o_tratamento():
    (bloco,) = formulario._blocos_das_linhas(["!- 45.169.232.0/22 64512:210"])
    assert bloco.ativo is False
    assert bloco.communities == ["64512:210"]


def test_a_marca_do_irr_no_fim_da_linha_e_ignorada():
    """As duas pontas do `!-` valendo na mesma linha: fora de servico, com o
    tratamento guardado e a marca do ausente descartada."""
    (bloco,) = formulario._blocos_das_linhas(
        ["!- 45.169.232.0/22 64512:210  !- nao veio na consulta ao IRR"])
    assert bloco.ativo is False
    assert bloco.communities == ["64512:210"]


def test_o_texto_do_bloco_marca_o_ausente_e_o_fora_de_servico():
    ativos = [formulario.Bloco(prefixo="45.169.232.0/22",
                               communities=["64512:210"])]
    fora = formulario.Bloco(prefixo="45.169.236.0/23", communities=[],
                            ativo=False)
    ausente = formulario.Bloco(prefixo="45.169.240.0/24",
                               communities=["64512:211"])
    assert formulario._linhas_de_blocos(ativos + [fora]) == [
        "45.169.232.0/22 64512:210", "!- 45.169.236.0/23"]
    assert formulario._texto_blocos({"v4": ativos + [ausente], "v6": []},
                                    ausentes=[ausente])["v4"] == (
        "45.169.232.0/22 64512:210\n"
        "45.169.240.0/24 64512:211  !- nao veio na consulta ao IRR")
```

Em `tests/test_api_peers.py`, no fim:

```python
def test_a_linha_tratada_atravessa_o_post_e_a_volta(api, tmp_path):
    r = api.post("/api/peers", json=dict(
        CLIENTE, prefixos_v4=["45.169.232.0/22 64512:210 64512:5070"]))
    assert r.status_code == 201, r.text
    peer = peers_mod.carregar(caminho_tenant(tmp_path))[0]
    assert peer.prefixos["v4"][0].communities == ["64512:210", "64512:5070"]
    assert r.json()["registro"]["formulario"]["prefixos_v4"] == [
        "45.169.232.0/22 64512:210 64512:5070"]


def test_o_fora_de_servico_volta_com_o_menos_na_frente(api, tmp_path):
    r = api.post("/api/peers", json=dict(
        CLIENTE, prefixos_v4=["!- 45.169.232.0/22 64512:210"]))
    assert r.status_code == 201, r.text
    assert r.json()["registro"]["formulario"]["prefixos_v4"] == [
        "!- 45.169.232.0/22 64512:210"]
    peer = peers_mod.carregar(caminho_tenant(tmp_path))[0]
    assert peer.prefixos["v4"][0].ativo is False
```

Os dois arquivos já importam o que estes testes usam: `peers_mod`, `caminho_tenant` e `CLIENTE` no `tests/test_api_peers.py`; `Bloco` no `tests/test_formulario.py`, que importa `from app import formulario`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_formulario.py -k "linha_com_community or fora_de_servico or marca_do_irr or texto_do_bloco" -v`
Expected: FAIL com `AttributeError: module 'app.formulario' has no attribute '_blocos_das_linhas'`.

- [ ] **Step 3: Implementar os helpers e o parse no `app/formulario.py`**

Substituir o corpo de `_blocos_do_formulario` (linhas 97 a 118) por:

```python
def _bloco_da_linha(linha):
    """Uma linha de textarea em Bloco, com o `!-` das duas pontas.

    Linha que comeca com `!-` e prefixo fora de servico: ele continua no
    cadastro com o tratamento dele e nao sai em configuracao nenhuma. O
    `!-` no fim da linha e a marca do que sumiu da consulta, e o que vem
    depois dele nao e lido.
    """
    ativo = not linha.startswith("!-")
    corpo = linha[2:] if not ativo else linha
    pedacos = corpo.split("!-")[0].split()
    if not pedacos:
        return None
    return Bloco(prefixo=canoniza(pedacos[0]), communities=pedacos[1:],
                 ativo=ativo)


def _blocos_das_linhas(linhas):
    """As linhas de uma familia em lista de Bloco."""
    return [b for b in (_bloco_da_linha(l) for l in linhas or [])
            if b is not None]


def _blocos_do_formulario(dados):
    """As duas listas do bloco proprio: uma linha por prefixo.

    O formato e `<cidr> community community ...`. Linha que comeca com
    `!-` e um prefixo fora de servico: ele continua no cadastro com o
    tratamento dele e nao sai em configuracao nenhuma. O `!-` no fim da
    linha e a marca do que sumiu da consulta, e o salvamento ignora.
    """
    return {fam: _blocos_das_linhas(_linhas(dados, "blocos_%s" % fam))
            for fam in plan.FAMILIAS}
```

Substituir o corpo de `_texto_blocos` (linhas 120 a 138) por:

```python
def _linha_do_bloco(bloco, marcado=False):
    """O texto de um bloco na textarea, com a marca do ausente quando houver."""
    corpo = " ".join([bloco.prefixo] + list(bloco.communities))
    if not bloco.ativo:
        return "!- " + corpo
    return corpo + ("  !- nao veio na consulta ao IRR" if marcado else "")


def _linhas_de_blocos(blocos, ausentes=()):
    """As linhas de um registro, uma por bloco, sem a marca do ausente."""
    return [_linha_do_bloco(b) for b in blocos or []]


def _texto_blocos(blocos, ausentes=()):
    """O texto das duas textareas, com a marca de quem sumiu da consulta."""
    marcados = {b.prefixo for b in ausentes}
    return {fam: "\n".join(_linha_do_bloco(b, b.prefixo in marcados)
                           for b in blocos.get(fam) or [])
            for fam in plan.FAMILIAS}
```

Em `peer_do_formulario` (linha 371), a lista de prefixos vira:

```python
        prefixos={f: _blocos_das_linhas(_linhas(dados, "prefixos_%s" % f))
                  for f in plan.FAMILIAS},
```

O `grupo_do_formulario` (linha 491) **não muda**: o grupo continua com `_linhas`, que é lista de CIDR em texto.

- [ ] **Step 4: Implementar o `modelo_do_peer` no `app/api.py`**

Na linha 84, trocar:

```python
        campos["prefixos_%s" % fam] = _lista(peer.prefixos.get(fam))
```

por:

```python
        campos["prefixos_%s" % fam] = form._linhas_de_blocos(
            peer.prefixos.get(fam))
```

O `modelo_do_grupo` (linha 114) fica como está.

- [ ] **Step 5: Rodar os testes**

Run: `.venv/bin/python -m pytest tests/test_formulario.py tests/test_api_peers.py tests/test_api_blocos.py tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, com os goldens intactos.

- [ ] **Step 7: Commit**

```bash
git add app/formulario.py app/api.py tests/test_formulario.py tests/test_api_peers.py
git commit -m "A linha do prefixo do peer entra e volta com o tratamento"
```

---

### Task 3: A validação do prefixo do peer

**Files:**
- Modify: `app/plan.py` (a constante do teto)
- Modify: `app/validate.py` (`_motivo_da_recusa`, `_motivo_da_community`, `validar_blocos`, `_valida_prefixos`, `_blocos`, `avisos`, `validar`)
- Modify: `app/api.py:332-341` e as duas chamadas de `_peer_do_pedido`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `Peer.prefixos` como `list[Bloco]` (Task 1); `plan.comprimento` (Task 1).
- Produces: `plan.TETO_PREFIXO` (`{"v4": 24, "v6": 48}`); `validar(peer, peers, anterior=None, grupos=None, rede=None)`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_validate.py`, no fim (o `bloco()` e o `um_peer()` do arquivo já servem):

```python
def com_prefixo(*blocos):
    return um_peer(prefixos={"v4": list(blocos), "v6": []})


def erros_do_prefixo(communities):
    return validate.validar(
        com_prefixo(Bloco(prefixo="45.169.232.0/22", communities=communities)),
        [])


def test_o_1xx_vale_no_prefixo_do_peer():
    """O APPLY-CUSTOMER-LP le o 1xx no import da sessao, e e por isso que
    ele entra aqui e nao no bloco proprio."""
    assert erros_do_prefixo(["64512:104"]) == []


def test_a_mesma_tabela_do_bloco_proprio_vale_no_prefixo_do_peer():
    for valor in ("64512:673", "64512:4:14840", "64512:301", "64512:2000"):
        erros = erros_do_prefixo([valor])
        assert [e.campo for e in erros] == ["prefixos"], valor
    assert erros_do_prefixo(["64512:200", "64512:211", "64512:5070",
                             "64512:613"]) == []


def test_o_prefixo_repetido_e_recusado():
    peer = com_prefixo(
        Bloco(prefixo="45.169.232.0/22", communities=[]),
        Bloco(prefixo="45.169.232.0/22", communities=["64512:210"]))
    (erro,) = validar(peer, [])
    assert erro.campo == "prefixos"
    assert "prefixo repetido" in erro.mensagem
```

Atenção: o `tests/test_validate.py` já importa `validar`, `validar_grupo` e `Bloco` no topo (linhas 1 a 3), então não falta import para nenhum destes testes.

O aviso do teto, no mesmo arquivo:

```python
def test_o_prefixo_mais_longo_que_o_teto_avisa_sem_recusar():
    peer = com_prefixo(Bloco(prefixo="45.169.232.0/25", communities=[]))
    assert validate.validar(peer, []) == []
    (aviso,) = validate.avisos(peer, [])
    assert aviso.campo == "prefixos"
    assert "/25" in aviso.mensagem


def test_o_prefixo_no_teto_nao_avisa():
    peer = com_prefixo(Bloco(prefixo="45.169.232.0/24", communities=[]))
    assert validate.avisos(peer, []) == []
```

E o grupo, que não aceita community na linha:

```python
def test_o_grupo_recusa_a_linha_com_community():
    grupo = um_grupo(prefixos={"v4": ["45.169.232.0/22 64512:210"], "v6": []})
    (erro,) = validar_grupo(grupo, [grupo], [], anterior=grupo)
    assert erro.campo == "prefixos"
    assert "peer avulso" in erro.mensagem
```

Onde `um_grupo` é o helper do arquivo; confira o nome dele antes de escrever o teste (`grep -n "def um_grupo" tests/test_validate.py`).

O namespace do tenant:

```python
def test_o_prefixo_do_peer_usa_o_namespace_da_rede():
    """Com asn_politica declarado, o que vale e 65532:673, e nao 64512:673."""
    rede = plan.Rede(asn=264130, politica=65532)
    peer = com_prefixo(Bloco(prefixo="45.169.232.0/22",
                             communities=["65532:673"]))
    (erro,) = validate.validar(peer, [], rede=rede)
    assert "classe 7" in erro.mensagem
    assert validate.validar(peer, [], rede=plan.Rede()) == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_validate.py -k "1xx_vale or tabela_do_bloco_proprio_vale or prefixo_repetido or mais_longo_que_o_teto or grupo_recusa_a_linha or namespace_da_rede" -v`
Expected: FAIL com `TypeError: validar() got an unexpected keyword argument 'rede'` e `AttributeError: module 'app.plan' has no attribute 'TETO_PREFIXO'`.

- [ ] **Step 3: Implementar no `app/validate.py`**

O teto, em `app/plan.py`, junto das tabelas de escopo (`NOADV` / `ONLY_NOT`):

```python
# o teto de mascara que o confinamento do downstream libera, por familia. E o
# mesmo `le` das duas prefix-lists do cliente e da clausula por prefixo do
# import, e por isso ele mora aqui: um numero, tres consumidores.
TETO_PREFIXO = {"v4": 24, "v6": 48}
```

Em `validate.py`, a assinatura e o ramo do `1xx`:

```python
def _motivo_da_recusa(valor, rede, lido_no_import=False):
    """Por que a community nao serve, ou None se serve.

    `lido_no_import=True` e o prefixo do downstream: ali a rota passa pelo
    import da sessao e o APPLY-CUSTOMER-LP le o 1xx, que e justamente o
    valor que o bloco proprio recusa por nao passar por import nenhum.
    """
```

e dentro dela:

```python
    if 100 <= n <= 199:
        if lido_no_import:
            return None
        return ("o 1xx e lido pelo import de cliente, e a rota propria "
                "nao passa por import nenhum: use o local-preference da "
                "propria filtragem de originacao")
```

O `_motivo_da_community` ganha o mesmo parâmetro e o repassa:

```python
def _motivo_da_community(valor, rede, lido_no_import=False):
    """A forma da large tem tres campos, e a da standard tem dois."""
    if len(valor.split(":")) == 3:
        return _motivo_da_recusa_large(valor, rede)
    return _motivo_da_recusa(valor, rede, lido_no_import)
```

A lista de recusa, extraída para servir os dois donos:

```python
def _valida_lista_de_communities(communities, campo, rede, lido_no_import,
                                 erros):
    """A tabela de recusa, para o bloco proprio e para o prefixo do peer."""
    for valor in communities or []:
        if not _forma_ok(valor):
            erros.append(Erro(
                campo, "community invalida: %s (esperado ASN:VALOR ou "
                "ASN:V1:V2)" % valor))
            continue
        motivo = _motivo_da_community(valor, rede, lido_no_import)
        if motivo:
            erros.append(Erro(campo, "%s: %s" % (valor, motivo)))
```

O laço de dentro de `validar_blocos` (linhas 283 a 294) vira a chamada:

```python
            _valida_lista_de_communities(bloco.communities, campo, rede,
                                         False, erros)
```

O `_valida_prefixos` passa a distinguir os dois alvos:

```python
def _valida_prefixos(alvo, erros, rede=None, tratado=False):
    """As duas listas de prefixo do peer, ou as do grupo.

    `tratado=True` e o Peer: os itens sao Bloco, com community e `!-`, e a
    lista passa pela tabela de recusa com `lido_no_import`, porque a rota do
    downstream passa pelo import. No grupo os itens sao CIDR em texto, e a
    linha com mais de um campo e recusada com mensagem propria: o grupo nao
    tem tratamento por prefixo.

    O `te_prefixos` e CIDR em texto nos dois casos, e continua so com a
    varredura de CIDR.
    """
    rede = rede if rede is not None else plan.Rede()
    for campo, listas in (("prefixos", alvo.prefixos),
                          ("te_prefixos",
                           getattr(alvo, "te_prefixos", None) or {})):
        for fam in plan.FAMILIAS:
            itens = listas.get(fam) or []
            if tratado and campo == "prefixos":
                vistos = set()
                for bloco in itens:
                    if bloco.prefixo in vistos:
                        erros.append(Erro(
                            campo, "prefixo repetido: %s" % bloco.prefixo))
                    vistos.add(bloco.prefixo)
                    if not _cidr_ok(bloco.prefixo):
                        erros.append(Erro(
                            campo, "prefixo invalido: %s" % bloco.prefixo))
                    _valida_lista_de_communities(bloco.communities, campo,
                                                 rede, True, erros)
                continue
            for texto in itens:
                if not tratado and campo == "prefixos" and len(texto.split()) > 1:
                    erros.append(Erro(
                        campo, "o grupo nao aceita community por prefixo: o "
                        "tratamento por prefixo e do peer avulso"))
                    continue
                if not _cidr_ok(texto):
                    erros.append(Erro(campo, "prefixo invalido: %s" % texto))
```

O `_blocos` (o predicado de sobreposição entre peers) passa a ler o Bloco:

```python
def _blocos(peer):
    for fam in plan.FAMILIAS:
        for bloco in peer.prefixos.get(fam) or []:
            yield fam, bloco.prefixo
```

O `validar` ganha o `rede` e o repassa:

```python
def validar(peer, peers, anterior=None, grupos=None, rede=None):
```

e, na chamada da linha 610:

```python
    _valida_prefixos(peer, erros, rede, tratado=True)
```

O `validar_grupo` (linha 481) fica como está, que o `tratado` já é `False` por padrão.

- [ ] **Step 4: Implementar o aviso do teto em `avisos`**

No fim de `validate.avisos`, antes do `return saida`:

```python
    # o teto do confinamento: a linha mais longa que ele nao casa rota
    # nenhuma, porque o PL-CUST para no teto. Aviso e nao erro porque o
    # peers.yaml de hoje aceita essa linha, e virar erro travaria o
    # salvamento de um cadastro que sempre funcionou.
    for fam in plan.FAMILIAS:
        for bloco in peer.prefixos.get(fam) or []:
            if plan.comprimento(bloco.prefixo) > plan.TETO_PREFIXO[fam]:
                saida.append(Erro(
                    "prefixos",
                    "%s e mais longo que o teto /%d do confinamento: a linha "
                    "nao alcanca rota nenhuma"
                    % (bloco.prefixo, plan.TETO_PREFIXO[fam])))
```

- [ ] **Step 5: Levar o `rede` até o `validar` no `app/api.py`**

O `_peer_do_pedido` (linha 332) ganha o parâmetro e o repassa:

```python
def _peer_do_pedido(formulario, peers, grupos, anterior, rede):
    """(peer, erros) do formulario, pelo mesmo caminho do POST /api/peers.

    A propria entrada fica na lista: quem a dispensa e o validar, pelo
    registro `anterior`, que por isso tem que ser o objeto desta mesma lista.
    O `rede` desce ate a validacao porque a tabela de recusa das
    communities compara com o namespace da rede, e nao com o de fabrica.
    """
    peer, erros = form.peer_do_formulario(
        dados_do_formulario(formulario), peers, anterior, grupos=grupos)
    erros = erros + validate.validar(peer, peers, anterior=anterior,
                                     grupos=grupos, rede=rede)
    return peer, erros
```

As duas chamadas passam o `rede`: na linha 400 (`_salvar_peer`, que já tem `rede` em escopo) e na linha 501 (`previa_peer`, idem), ambas viram `_peer_do_pedido(formulario, peers, grupos, anterior, rede)`.

- [ ] **Step 6: Rodar os testes**

Run: `.venv/bin/python -m pytest tests/test_validate.py tests/test_api_peers.py tests/test_api.py -v`
Expected: PASS.

- [ ] **Step 7: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, com os goldens intactos.

- [ ] **Step 8: Commit**

```bash
git add app/plan.py app/validate.py app/api.py tests/test_validate.py
git commit -m "A tabela de recusa vale no prefixo do peer, com o 1xx a mais"
```

---

### Task 4: A cadeia por prefixo no import gerado

**Files:**
- Modify: `app/plan.py` (`conjunto_do_prefixo`, perto de `conjunto`)
- Modify: `templates/_macros.j2` (`prefix_lists_downstream` na linha 78, `te_prefix_list` na 240, `filtro_downstream_import` na 133)
- Test: `tests/test_plan.py`, `tests/test_render.py`
- Create: `tests/golden/cliente-tratado.txt`

**Interfaces:**
- Consumes: `Peer.cidrs`, `Peer.tratamentos`, `Grupo.cidrs`, `Grupo.tratamentos` (Task 1); `plan.TETO_PREFIXO` (Task 3).
- Produces: `plan.conjunto_do_prefixo(cidr, teto) -> str`; a cláusula no `CUST-<T>-IMPORT-<U>`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_plan.py`:

```python
def test_o_conjunto_do_prefixo():
    assert plan.conjunto_do_prefixo("45.169.232.0/22", 24) == (
        "{45.169.232.0 22 le 24}")
    assert plan.conjunto_do_prefixo("2804:36b4::/32", 48) == (
        "{2804:36b4:: 32 le 48}")
```

Em `tests/test_render.py`, no fim, com `Bloco` importado de `app.peers` (confira o import no topo do arquivo; se não estiver lá, acrescente):

```python
def test_o_tratamento_por_prefixo_vem_depois_do_apply_peer():
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", communities=["64512:210"])], "v6": []}))
    trecho = texto.split("xpl route-filter CUST-268127-IMPORT-V4")[1]
    corpo = [l.strip() for l in trecho.split("end-filter")[0].splitlines()
             if l.strip()]
    assert corpo[-1] == "finish"
    assert corpo[-2] == "endif"
    assert corpo.index("call route-filter APPLY-PEER-268127") < corpo.index(
        "if ip route-destination in {45.169.232.0 22 le 24} then")
    assert "apply community {64512:210} additive" in corpo


def test_o_mais_especifico_vence_e_os_dois_nao_somam():
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", communities=["64512:210"]),
        Bloco(prefixo="45.169.232.0/24", communities=["64512:211"])], "v6": []}))
    trecho = texto.split("xpl route-filter CUST-268127-IMPORT-V4")[1]
    corpo = [l.strip() for l in trecho.split("end-filter")[0].splitlines()
             if l.strip()]
    # um `elseif` so, e o /24 na frente: e o if/elseif que impede as duas
    # linhas de somarem numa rota so
    assert sum(1 for l in corpo if l.startswith("elseif")) == 1
    assert corpo.index("if ip route-destination in {45.169.232.0 24 le 24} then") \
        < corpo.index("elseif ip route-destination in {45.169.232.0 22 le 24} then")


def test_o_tratamento_em_v6_usa_o_teto_da_familia():
    texto = render.render_peer(peer_cliente(
        prefixos={"v4": [], "v6": [
            Bloco(prefixo="2804:3300::/32", communities=["64512:210"])]},
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"},
                 "v6": {"local": "2001:db8::1", "remoto": "2001:db8::2"}}))
    assert "if ip route-destination in {2804:3300:: 32 le 48} then" in texto


def test_o_parceiro_ganha_a_cadeia_depois_do_carimbo_do_tipo():
    texto = render.render_peer(peer_parceiro(prefixos={"v4": [
        Bloco(prefixo="45.169.236.0/22", communities=["64512:210"])], "v6": []}))
    trecho = texto.split("xpl route-filter CUST-64500-IMPORT-V4")[1]
    corpo = trecho.split("end-filter")[0]
    assert corpo.index("64512:2091") < corpo.index(
        "if ip route-destination in {45.169.236.0 22 le 24} then")


def test_o_peer_sem_tratamento_nao_ganha_clausula():
    # o resto do bloco deste peer ja esta coberto pelo golden do cliente, que
    # nao pode mudar uma linha nesta feature
    texto = render.render_peer(peer_cliente())
    assert "elseif ip route-destination" not in texto
    assert "tratamento por prefixo" not in texto


def test_golden_do_cliente_tratado():
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", communities=["64512:210", "64512:5070"]),
        Bloco(prefixo="45.169.236.0/23", communities=["64512:211"])], "v6": []}))
    assert texto == (GOLDEN / "cliente-tratado.txt").read_text(encoding="ascii")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_plan.py -k conjunto_do_prefixo tests/test_render.py -k "tratamento or mais_especifico or golden_do_cliente_tratado" -v`
Expected: FAIL com `AttributeError: module 'app.plan' has no attribute 'conjunto_do_prefixo'` e o golden faltando.

- [ ] **Step 3: Implementar o `plan.conjunto_do_prefixo`**

Em `app/plan.py`, logo depois do `conjunto`:

```python
def conjunto_do_prefixo(cidr, teto):
    """O conjunto inline de um prefixo: `{45.169.232.0 22 le 24}`.

    O `le` cobre o proprio prefixo e os mais especificos ate o teto, que e o
    alcance do confinamento. Sai pronto do Python porque em Jinja o `{{`
    seguido de `{` fecha a expressao, e o mesmo motivo que levou o
    `conjunto` a existir.
    """
    return "{%s le %d}" % (cidr_para_xpl(cidr), teto)
```

- [ ] **Step 4: Trocar as listas para o `cidrs()` e o teto único**

Em `templates/_macros.j2`, no `prefix_lists_downstream` (linha 78), o teto e as duas listas:

```jinja
{% set maxlen = plan.TETO_PREFIXO[fam] %}
{% set hostlen = 128 if fam == "v6" else 32 %}
```

e os dois laços passam a ser `{% for cidr in alvo.cidrs(fam) %}`.

No `te_prefix_list` (linha 240), a linha `{% set maxlen = 48 if fam == "v6" else 24 %}` vira:

```jinja
{% set maxlen = plan.TETO_PREFIXO[fam] %}
```

- [ ] **Step 5: Emitir a cadeia no `filtro_downstream_import`**

Em `templates/_macros.j2`, no começo da macro `filtro_downstream_import`, junto dos outros `set`:

```jinja
{% set tratamentos = alvo.tratamentos(fam) %}
```

e, entre o `{% if chamar_apply_peer %}` que chama o `APPLY-PEER` e o ` finish`:

```jinja
{% if tratamentos %}
 !- tratamento por prefixo do cadastro, do mais especifico para o menos
{% for prefixo, communities in tratamentos %}
{% set std, lg = plan.separa_communities(communities) %}
 {{ "if" if loop.first else "elseif" }} ip route-destination in {{ plan.conjunto_do_prefixo(prefixo, plan.TETO_PREFIXO[fam]) }} then
{% if std %}
  apply community {{ plan.conjunto_de(std) }} additive
{% endif %}
{% if lg %}
  apply large-community {{ plan.conjunto_de(lg) }} additive
{% endif %}
{% endfor %}
 endif
{% endif %}
```

- [ ] **Step 6: Criar o golden**

Run: `.venv/bin/python -c "from app import render; from tests.test_render import peer_cliente; from app.peers import Bloco; open('tests/golden/cliente-tratado.txt','w',encoding='ascii').write(render.render_peer(peer_cliente(prefixos={'v4':[Bloco(prefixo='45.169.232.0/22', communities=['64512:210','64512:5070']), Bloco(prefixo='45.169.236.0/23', communities=['64512:211'])], 'v6': []})))"`
Expected: o arquivo nasce. Leia ele antes de commitar: a cadeia tem que estar entre o `call route-filter APPLY-PEER-268127` e o `finish`, com o `/22` e o `/23` (o `/23` primeiro). Se o `-c` não achar o módulo `tests`, rode de dentro da raiz e confira o `pytest.ini`, que é quem põe `tests/` no `pythonpath`.

- [ ] **Step 7: Rodar os testes**

Run: `.venv/bin/python -m pytest tests/test_render.py tests/test_plan.py -v`
Expected: PASS, incluindo os goldens antigos sem uma linha de diferença.

- [ ] **Step 8: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/plan.py templates/_macros.j2 tests/test_plan.py tests/test_render.py tests/golden/cliente-tratado.txt
git commit -m "A cadeia por prefixo entra no import, do mais especifico ao mais curto"
```

---

### Task 5: A reconsulta ao IRR e a tela

**Files:**
- Modify: `app/modelos_api.py:249-253` (`IrrPedido`)
- Modify: `app/api.py:544-567` (`consultar_irr`)
- Modify: `web/src/telas/peers/PeerTela.tsx:193-198`
- Modify: `web/src/telas/grupos/GrupoTela.tsx:155`
- Modify: `web/src/telas/peers/camposPeer.ts:122-123` (a ajuda)
- Modify: `web/src/api/schema.d.ts` (regerado)
- Test: `tests/test_api.py`, `web/src/telas/peers/PeerTela.test.tsx`

**Interfaces:**
- Consumes: `form._blocos_das_linhas` e `form._linhas_de_blocos` (Task 2); `peers.mesclar_blocos` (existente).
- Produces: `IrrPedido.v4` / `IrrPedido.v6` (as linhas da tela, `list[str]`).

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_api.py`, no fim:

```python
def test_o_irr_do_peer_preserva_o_tratamento_e_marca_o_ausente(api, fake_bgpq4):
    # a consulta devolve 45.169.232.0/22 e 45.169.236.0/23 em v4
    r = api.post("/api/irr", json={
        "asn": "268127",
        "v4": ["45.169.232.0/22 64512:210", "45.169.240.0/24 64512:211"],
        "v6": []})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "v4": ["45.169.232.0/22 64512:210",
               "45.169.236.0/23",
               "45.169.240.0/24 64512:211  !- nao veio na consulta ao IRR"],
        "v6": ["2001:db8::/32"]}


```

O `test_o_irr_devolve_os_prefixos_sem_gravar`, que já existe no arquivo, cobre o pedido sem as linhas na tela, que é o caso do cadastro que nunca teve tratamento: ele continua passando, e é a prova de que o caminho antigo não mudou.

Em `web/src/telas/peers/PeerTela.test.tsx`, um caso novo:

```tsx
it("a consulta ao IRR manda as linhas da tela e devolve as mescladas", async () => {
  // O tratamento escrito a mao so sobrevive a reconsulta se o pedido levar o
  // que esta no campo: sem isso o servidor mescla contra nada e a lista volta
  // como o IRR respondeu, apagando o trabalho.
  mockFetch({
    ...BASE,
    "POST /api/irr": {
      corpo: { v4: ["45.169.232.0/22 64512:210", "45.169.240.0/24 64512:211  !- nao veio na consulta ao IRR"], v6: [] },
    },
  })
  montarRota(rotas, "/peers/7")
  await userEvent.click(await screen.findByRole("button", { name: /^consultar IRR$/i }))
  await waitFor(() => {
    const pedido = peticoes().find((p) => p.caminho === "/api/irr")
    expect(pedido?.corpo).toMatchObject({
      v4: ["45.169.232.0/22"],
    })
  })
  expect(await screen.findByDisplayValue(/45.169.240.0\/24/)).toBeInTheDocument()
})
```

O `BASE` da tela já traz `prefixos_v4: ["45.169.232.0/22"]`; confira o nome do campo no `BASE` antes de escrever a expectativa.

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_api.py -k irr_do_peer -v`
Expected: FAIL: o `IrrPedido` ignora `v4`/`v6` (o `extra` do `Modelo` não é `forbid`) e a resposta volta sem a mesclagem.

- [ ] **Step 3: Implementar o `IrrPedido` e o endpoint**

Em `app/modelos_api.py`:

```python
class IrrPedido(Modelo):
    asn: str = ""
    # o token do cache e o do peer: o apelido quando ha, senao o ASN
    apelido: str = ""
    forcar: bool = False
    # as linhas que estao na tela, uma por prefixo: e o que a mesclagem usa
    # como base, para a reconsulta nao apagar o tratamento escrito a mao
    v4: list[str] = []
    v6: list[str] = []
```

Em `app/api.py`, no `consultar_irr`, depois do `coletar` e no lugar do `return Prefixos(...)`:

```python
    # a mesclagem e a mesma do bloco proprio: o que veio da consulta e ja
    # tinha linha mantem o tratamento, o prefixo novo entra sem tratamento, e
    # o que sumiu volta no fim marcado. A base e o que esta na tela, e nao o
    # arquivo: o operador pode ter mexido numa linha antes de consultar.
    linhas = {"v4": pedido.v4, "v6": pedido.v6}
    resposta = {}
    for fam in plan.FAMILIAS:
        salvos = form._blocos_das_linhas(linhas[fam])
        visiveis, ausentes = peers_mod.mesclar_blocos(
            salvos, coleta.get(fam) or [])
        resposta[fam] = form._linhas_de_blocos(visiveis, ausentes)
    return Prefixos(v4=resposta["v4"], v6=resposta["v6"])
```

- [ ] **Step 4: Levar as linhas no pedido das duas telas**

Em `web/src/telas/peers/PeerTela.tsx`, o corpo do `POST /api/irr` ganha os dois campos:

```tsx
        body: {
          asn: form.getValues("asn"), apelido: form.getValues("apelido"), forcar,
          // o que esta na tela vai junto: e a base da mesclagem, e sem ela a
          // reconsulta apagaria o tratamento escrito a mao
          v4: form.getValues("prefixos_v4"), v6: form.getValues("prefixos_v6"),
        },
```

Em `web/src/telas/grupos/GrupoTela.tsx`, o mesmo no pedido dele, com os campos do grupo (que têm os mesmos nomes). Vale para os dois: no grupo a mesclagem só muda a ordem e a marca do ausente.

- [ ] **Step 5: A ajuda do campo em `web/src/telas/peers/camposPeer.ts`**

As duas linhas dos prefixos ganham `ajuda`, no formato dos outros campos do arquivo:

```ts
  { nome: "prefixos_v4", rotulo: "IPv4", tipo: "area", secao: "prefixos", mono: true, linhas: 5,
    ajuda: "uma linha por prefixo: cidr e depois as communities. a linha começada por !- fica fora do anúncio" },
  { nome: "prefixos_v6", rotulo: "IPv6", tipo: "area", secao: "prefixos", mono: true, linhas: 5,
    ajuda: "uma linha por prefixo: cidr e depois as communities. a linha começada por !- fica fora do anúncio" },
```

- [ ] **Step 6: Regenerar o schema e rodar o front**

```bash
cd web
npm ci
npm run api:tipos
npm test
npm run lint
```

Expected: `schema.d.ts` muda só no `IrrPedido` (ganha `v4` e `v6`), o vitest passa e o lint não acusa nada. O `tests/test_tipos_api.py` passa a valer de novo.

- [ ] **Step 7: Rodar a suíte Python inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, incluindo o `test_tipos_api.py`.

- [ ] **Step 8: Commit**

```bash
git add app/modelos_api.py app/api.py web/src/api/schema.d.ts web/src/telas/peers/PeerTela.tsx web/src/telas/grupos/GrupoTela.tsx web/src/telas/peers/camposPeer.ts tests/test_api.py web/src/telas/peers/PeerTela.test.tsx
git commit -m "A reconsulta ao IRR mescla por prefixo e preserva o tratamento"
```

---

### Task 6: O `PLANO.md` e o exemplo da spec dos blocos

**Files:**
- Modify: `PLANO.md` (o import do downstream, na seção dos exemplos; e a referência de sintaxe XPL)
- Modify: `docs/superpowers/specs/2026-09-24-blocos-proprios-design.md` (o exemplo da tela)
- Modify: `README.md` (a seção do campo, se ela citar o formato)

**Interfaces:**
- Consumes: tudo o que as tarefas anteriores geraram; o texto do golden `cliente-tratado.txt` é a fonte do exemplo.
- Produces: documentação.

- [ ] **Step 1: Documentar a cláusula no `PLANO.md`**

Na seção do import do cliente de trânsito (o exemplo completo, perto da linha 1083), acrescentar o trecho da cadeia por prefixo antes do `finish`, copiado do `tests/golden/cliente-tratado.txt`, com um parágrafo explicando:

- de onde vem a lista (o cadastro do peer, campo `prefixos`, uma linha por prefixo);
- a ordem: do mais específico para o mais curto, em `if/elseif`, para um /24 dentro de um /22 aplicar só o dele;
- o `le` com o mesmo teto do `PL-CUST` (24 no v4, 48 no v6);
- a posição depois do `call APPLY-PEER`, e o `additive`, com a consequência: o `1xx` da linha vence o da CL-PEER, e duas marcas de escopo incompatíveis somam e a rota não sai por lugar nenhum.

- [ ] **Step 2: Documentar a forma na referência de sintaxe**

Na seção "Referência de sintaxe XPL", junto das notas de `ip route-destination`, registrar a forma `{<endereco> <comprimento> le <teto>}` e a regra do `if/elseif`. Se a forma já estiver documentada, só acrescente a nota do teto.

- [ ] **Step 3: Corrigir o exemplo da spec dos blocos próprios**

Em `docs/superpowers/specs/2026-09-24-blocos-proprios-design.md`, no bloco do formato da linha (por volta da linha 258), o exemplo `38.252.64.0/22  613 621 15169:12100` vira:

```
38.252.64.0/22  64512:613 64512:621 15169:12100
38.252.64.0/24  64512:211
```

com uma linha de nota: a community vai na forma completa, porque o `_forma_ok` exige `ASN:VALOR`. O `tests/golden/blocos.txt` e o `dados_api.BLOCOS` já escrevem assim, então é o documento que estava torto.

- [ ] **Step 4: Conferir o README**

Run: `grep -n "prefixos\|community" README.md | head -20`
Se o README descrever o campo de prefixos do peer, acrescentar o formato da linha. Se não houver nada sobre ele, não mexa.

- [ ] **Step 5: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS. Nenhum teste lê o `PLANO.md`, mas a suíte é a rede de segurança barata.

- [ ] **Step 6: Commit**

```bash
git add PLANO.md docs/superpowers/specs/2026-09-24-blocos-proprios-design.md README.md
git commit -m "O PLANO e a spec dos blocos com a community por prefixo"
```

---

## Depois do plano

O merge na `main` e o push são do usuário, de fora da worktree: esta sessão trabalha em `worktree-community-prefixo-cliente`, e a regra do projeto é que o merge definitivo não sai daqui.

Os dois itens do "O que confirmar no equipamento" da spec continuam abertos e não bloqueiam a implementação:

1. Que `if ip route-destination in {45.169.232.0 22 le 24}` casa o prefixo e os mais específicos, como a entrada equivalente de uma prefix-list nomeada.
2. Que a forma inline aceita `le` sem `ge` e vale no v6 com o mesmo `ip route-destination` que a macro já usa nas duas famílias.
