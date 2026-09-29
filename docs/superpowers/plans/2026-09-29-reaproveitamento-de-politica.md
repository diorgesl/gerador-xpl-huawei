# Reaproveitamento de política entre peers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um peer pode declarar que reaproveita a política de outro peer do mesmo tipo e ASN, e o bloco dele passa a emitir só a sessão, chamando os filtros da origem pelo nome dela.

**Architecture:** Um campo `politica_de: int | None` no `Peer`, apontando para o `id` da origem. O render ganha o parâmetro `origem` e uma macro nova que emite a sessão com os nomes de filtro trocados; nenhum objeto `xpl` é emitido por quem reaproveita. O render é quem ignora os campos de política do peer que reaproveita, e o formulário continua mostrando tudo, com uma nota dizendo de quem a política vem.

**Tech Stack:** Python 3.14, FastAPI, pydantic, Jinja2 (templates XPL), pytest; React + TypeScript + vitest no front.

**Spec:** `docs/superpowers/specs/2026-09-29-reaproveitamento-de-politica-design.md`

## Global Constraints

- O XPL gerado é **ASCII puro**. Um acento que escape para um template quebra o pipeline de TFTP/diff do equipamento.
- Comentários e strings em `app/*.py`, `templates/*.j2` e `tests/*.py` são **sem acento**. A prosa do `PLANO.md` e dos specs é com acento.
- **Gerar ou editar um peer não pode mexer na saída de outro.** Quem reaproveita derruba e recria apenas o próprio bloco.
- Nomes de campo e de função em português, seguindo o cadastro existente (`apelido`, `politica_de`, `tem_filtro_proprio`).
- Suíte: `.venv/bin/python -m pytest` na raiz e `npm run test` dentro de `web/`.
- Toda implementação acontece em **worktree** criada com `superpowers:using-git-worktrees` antes do primeiro commit.

## Review Focus

Cinco entradas que a spec não fecha e que quebram o programa de um jeito que a pessoa não espera, da mais provável para a menos:

1. **A origem não existe no arquivo** (YAML editado à mão, ou peer apagado antes do render). O bloco não pode estourar com um `KeyError` nem sair com o nome de filtro de um peer que não está lá.
2. **A origem teve o token renomeado.** Quem reaproveita fica apontando para nomes que o equipamento não tem mais. O app avisa e não regenera sozinho, e é isso que o teste tem que pinar.
3. **`politica_de` apontando para peer de outro tipo ou ASN**, chegando por YAML editado, sem passar pela validação. O nome do filtro sai com o prefixo do tipo de quem reaproveita (o `PREFIXO_DO_TIPO` lê `alvo.tipo`), então não sai prefixo errado: sai um nome que não existe no equipamento, do peer de outro tipo. O bloco cola sem erro e a sessão fica sem filtro.
4. **Exclusão da origem pela API** enquanto alguém a reaproveita. Precisa ser recusada, e não apagar o bloco dos dois.
5. **Quem reaproveita com campo de política preenchido.** A tela mostra os valores e o gerador tem que ignorá-los. Se o render consultar qualquer um deles, o operador vê uma coisa e o equipamento recebe outra.

---

## Task 1: O campo e as regras

**Files:**
- Modify: `app/peers.py` (o dataclass `Peer`, perto de `grupo_id` na linha 63; e o `Peer.para_dict`, linha 176)
- Modify: `app/validate.py` (`dono_da_politica` no nível do módulo, logo acima de `validar`)
- Test: `tests/test_validate.py`, `tests/test_peers.py`

**Interfaces:**
- Consumes: `achar_grupo_id(grupos, ident)` de `app/peers.py`, já importado no `validate.py`.
- Produces: `Peer.politica_de: int | None`; `dono_da_politica(peer) -> bool` em `app/validate.py`, usado pela validação desta task. Nenhuma outra task o consome: o front reimplementa o mesmo predicado em TypeScript (Task 5), porque do lado de lá o dado é o resumo da lista e não o `Peer`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `tests/test_validate.py`:

```python
def test_politica_de_apontando_para_peer_inexistente_e_erro():
    p = um_peer(politica_de=99)
    assert "politica_de" in campos(validate.validar(p, []))


def test_politica_de_exige_o_mesmo_tipo():
    outro = um_peer(id=2, tipo="upstream", asn=268127, classe=None,
                    aprendizado=3100, prefixos={"v4": [], "v6": []})
    p = um_peer(politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [outro]))


def test_politica_de_exige_o_mesmo_asn():
    outro = um_peer(id=2, asn=9999)
    p = um_peer(politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [outro]))


def test_a_origem_tem_que_ser_dona_da_propria_politica():
    # corrente: a origem nao pode reaproveitar de ninguem. Sem isto o nome
    # do objeto vira uma cadeia para resolver, e o render teria que seguir
    # o ponteiro ate o fim
    meio = um_peer(id=2, politica_de=3)
    fim = um_peer(id=3)
    p = um_peer(politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [meio, fim]))


def test_a_origem_nao_pode_ser_membro_de_grupo():
    # membro de grupo nao tem os filtros no proprio bloco: eles sao do
    # grupo, e o bloco do membro so referencia o group
    grupo = Grupo(id=1, nome="CLIENTES", tipo="cliente", asn=268127,
                  classe="residencial", origem=1110, pop=2001)
    origem = um_peer(id=2, grupo_id=1, prefixos={"v4": [], "v6": []})
    p = um_peer(politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [origem], grupos=[grupo]))


def test_o_peer_nao_pode_reaproveitar_de_si_mesmo():
    p = um_peer(id=2, politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [p]))


def test_nao_pode_reaproveitar_e_estar_em_grupo_ao_mesmo_tempo():
    grupo = Grupo(id=1, nome="CLIENTES", tipo="cliente", asn=268127,
                  classe="residencial", origem=1110, pop=2001)
    p = um_peer(id=2, grupo_id=1, politica_de=3)
    origem = um_peer(id=3)
    assert "politica_de" in campos(validate.validar(p, [origem], grupos=[grupo]))


def test_o_caso_bom_nao_acusa_nada():
    origem = um_peer(id=1, nome="NETMAC")
    backup = um_peer(id=2, nome="NETMAC-BKP", politica_de=1,
                     sessoes={"v4": {"local": "198.51.100.9",
                                     "remoto": "198.51.100.10"}, "v6": {}})
    assert "politica_de" not in campos(validate.validar(backup, [origem]))
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_validate.py -q -k politica_de or mesma_politica or reaproveitar`
Expected: FAIL, com `TypeError: __init__() got an unexpected keyword argument 'politica_de'`.

- [ ] **Step 3: Acrescentar o campo ao `Peer`**

Em `app/peers.py`, logo depois de `grupo_id: int | None = None` no dataclass `Peer`:

```python
    # o peer cuja politica este vale. A referencia e por id e nao por token:
    # o token muda quando o apelido muda, e a referencia nao pode se
    # desfazer por causa de uma renomeacao. O efeito colateral - o bloco de
    # quem reaproveita fica apontando para nomes velhos ate ser gerado de
    # novo - esta tratado no aviso do formulario da origem.
    politica_de: int | None = None
```

- [ ] **Step 4: Acrescentar as regras ao `validar`**

Em `app/validate.py`, antes do laço `for outro in peers:` (linha ~700), crie a função que as duas Tasks usam:

```python
def dono_da_politica(peer):
    """O peer carrega a propria politica no proprio bloco?

    Nao carrega quando esta num grupo (os filtros sao do grupo e o bloco do
    membro so referencia o group) nem quando reaproveita de outro (o bloco
    dele nao define objeto nenhum). E o predicado que a validacao usa para
    saber quem pode ser origem, e que o render usa na Task 2.
    """
    return peer.grupo_id is None and peer.politica_de is None
```

E logo depois de `_valida_ascii(peer, erros)`, ainda dentro do `validar`, acrescente o bloco das regras novas:

```python
    # --- reaproveitamento de politica ---------------------------------
    if peer.politica_de is not None:
        origem = next((o for o in peers if o.id == peer.politica_de), None)
        if origem is None:
            erros.append(Erro("politica_de", "peer de origem nao encontrado"))
        elif origem is anterior or origem is peer:
            erros.append(Erro("politica_de", "o peer nao pode reaproveitar de si mesmo"))
        elif origem.tipo != peer.tipo:
            erros.append(Erro(
                "politica_de",
                "o peer %s e de %s, e este e de %s" % (origem.nome, origem.tipo, peer.tipo)))
        elif origem.asn != peer.asn:
            erros.append(Erro(
                "politica_de",
                "o peer %s e do ASN %d, e este e do ASN %d"
                % (origem.nome, origem.asn, peer.asn)))
        elif not dono_da_politica(origem):
            erros.append(Erro(
                "politica_de",
                "o peer %s nao tem politica propria para ceder: ele %s"
                % (origem.nome,
                   "esta num grupo" if origem.grupo_id is not None
                   else "reaproveita de outro")))
        if peer.grupo_id is not None:
            erros.append(Erro(
                "politica_de",
                "um membro de grupo ja herda a politica do grupo: escolha um "
                "caminho so"))
```

- [ ] **Step 5: Listar o campo no `para_dict`**

O `Peer.para_dict` monta o dicionário campo a campo, e o `gravar` do `peers.py` é quem escreve o YAML do tenant a partir dele. Um campo que não esteja na lista some na gravação sem erro nenhum: o operador escolhe a origem, salva, e o vínculo não está mais lá.

Em `app/peers.py`, ao lado de `"grupo_id": self.grupo_id,`:

```python
            "politica_de": self.politica_de,
```

E o teste da propriedade, em `tests/test_peers.py`, que é onde o ida-e-volta do modelo mora:

```python
def test_o_reaproveitamento_sobrevive_ao_gravar_e_carregar(tmp_path):
    """O `para_dict` lista os campos um a um, entao um campo novo que ele
    nao liste some na gravacao sem erro nenhum. O teste cobre o caminho
    inteiro, que e o unico que pega um campo esquecido na lista."""
    caminho = tmp_path / "264130.yaml"
    peers_mod.gravar([Peer(id=1, tipo="cliente", asn=270620, politica_de=1)],
                     caminho)
    assert peers_mod.carregar(caminho)[0].politica_de == 1
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `.venv/bin/python -m pytest tests/test_validate.py tests/test_peers.py -q`
Expected: PASS, com os casos novos verdes e nenhum antigo quebrado.

- [ ] **Step 7: Commit**

```bash
git add app/peers.py app/validate.py tests/test_validate.py tests/test_peers.py
git commit -m "O peer pode declarar de quem reaproveita a politica

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 2: O render, com a sessão apontando para a origem

**Files:**
- Modify: `app/plan.py` (acrescenta `PREFIXO_DO_TIPO`, perto de `TIPOS` na linha 22)
- Modify: `app/render.py` (`render_peer`, `escrever_peer`)
- Modify: `templates/_macros.j2` (macro nova, no fim do arquivo)
- Modify: `templates/cliente.txt.j2`, `templates/upstream.txt.j2`, `templates/ix.txt.j2`, `templates/pni.txt.j2`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Peer.politica_de` da Task 1.
- Produces: `render.render_peer(peer, grupo=None, rede=None, origem=None)` e `render.escrever_peer(peer, grupo=None, rede=None, origem=None, *, saida)`. A Task 4 é quem passa o `origem`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `tests/test_render.py`:

```python
# --- o peer que reaproveita a politica de outro ------------------------


def par_de_reaproveitamento(**kw):
    """O par principal/backup: o segundo reaproveita a politica do primeiro."""
    # o apelido da origem e o que da o token dela, e e com esse token que o
    # bloco de quem reaproveita nomeia os filtros que chama. Sem apelido o
    # token seria o ASN, e o teste nao distinguiria "usa o token da origem"
    # de "usa o ASN da origem"
    origem = peer_cliente(id=1, asn=270620, apelido="NETMAC", nome="NETMAC",
                          descricao="NETMAC")
    backup = peer_cliente(
        id=2, asn=270620, apelido="NETMAC-BKP", nome="NETMAC-BKP",
        descricao="NETMAC-BKP", politica_de=1,
        sessoes={"v4": {"local": "198.51.100.9", "remoto": "198.51.100.10"},
                 "v6": {}},
        **kw)
    return origem, backup


def test_o_bloco_de_quem_reaproveita_nao_define_objeto_nenhum():
    # a razao de existir do recurso: dois links do mesmo cliente sem a
    # politica escrita duas vezes
    origem, backup = par_de_reaproveitamento()
    texto = render.render_peer(backup, origem=origem)
    assert "xpl " not in texto


def test_o_bloco_de_quem_reaproveita_chama_os_filtros_da_origem():
    origem, backup = par_de_reaproveitamento()
    texto = render.render_peer(backup, origem=origem)
    assert ("peer 198.51.100.10 route-filter CUST-NETMAC-IMPORT-V4 import"
            in texto)
    assert ("peer 198.51.100.10 route-filter CUST-NETMAC-EXPORT-V4 export"
            in texto)
    # o token de quem reaproveita aparece no comentario de cabecalho, que e o
    # nome do registro; o que nao pode e ele nomear filtro nenhum
    assert "CUST-NETMAC-BKP" not in texto


def test_o_bloco_de_quem_reaproveita_traz_a_sessao_dele():
    # nao ha grupo do VRP carregando a sessao: timers, bfd, route-limit e
    # advertise-community sao deste link, com os valores dele
    _, backup = par_de_reaproveitamento(
        route_limit=99, timer_keepalive=30, timer_hold=90, bfd=True)
    texto = render.render_peer(backup, origem=par_de_reaproveitamento()[0])
    assert "peer 198.51.100.10 route-limit 99 alert-only" in texto
    assert "peer 198.51.100.10 timer keepalive 30 hold 90" in texto
    assert "peer 198.51.100.10 bfd enable" in texto
    assert "peer 198.51.100.10 advertise-community" in texto


def test_o_filtro_sai_com_o_prefixo_do_tipo():
    # o prefixo do nome do filtro e do tipo, e nao do token: um upstream que
    # reaproveita chama UP-, e nao CUST-
    origem = peer_upstream(id=1, asn=14840, apelido="OP", descricao="OP")
    outro = peer_upstream(id=2, asn=14840, apelido="OP-BKP", nome="OP-BKP",
                          descricao="OP-BKP", politica_de=1)
    texto = render.render_peer(outro, origem=origem)
    assert "route-filter UP-OP-IMPORT-V4 import" in texto
    assert "CUST-" not in texto


def test_o_campo_de_politica_de_quem_reaproveita_e_ignorado():
    # a tela mostra os campos e o operador pode digitar neles. O que vale e
    # a origem, e o render nao pode consultar nenhum deles
    origem, backup = par_de_reaproveitamento(
        lp_base=999, origem=1999, pop=2222, prepend_base=3, bh_upstream="1:666",
        communities=["64512:1900"], ap_block=["65000"])
    texto = render.render_peer(backup, origem=origem)
    assert "999" not in texto
    assert "64512:1900" not in texto
    assert "65000" not in texto
    assert "xpl " not in texto


def test_gerar_quem_reaproveita_nao_muda_a_saida_da_origem():
    # o requisito de sempre: gerar um nao mexe na saida do outro
    origem, backup = par_de_reaproveitamento()
    antes = render.render_peer(origem)
    render.render_peer(backup, origem=origem)
    assert render.render_peer(origem) == antes
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_render.py -q -k reaproveita`
Expected: FAIL, com `TypeError: render_peer() got an unexpected keyword argument 'origem'`.

- [ ] **Step 3: Acrescentar `PREFIXO_DO_TIPO` ao `plan.py`**

Logo depois de `FAMILIAS = ("v4", "v6")`:

```python
# O prefixo do nome dos filtros de cada tipo. Sai daqui e nao do template
# porque quem monta o nome num terceiro lugar - o peer que reaproveita a
# politica de outro - precisa do mesmo valor, e duas copias divergem na
# primeira vez que alguem renomear um filtro.
PREFIXO_DO_TIPO = {"cliente": "CUST", "parceiro": "CUST", "upstream": "UP",
                   "ix": "IX", "pni": "PNI"}
```

- [ ] **Step 4: Acrescentar a macro do bloco**

No fim de `templates/_macros.j2`:

```jinja
{# O peer que reaproveita a politica de outro: so a sessao, apontando para
   os filtros da origem. Nenhum objeto xpl - e essa a diferenca para o peer
   avulso, que define o par inteiro com o proprio token no nome.

   A sessao sai inteira e com os valores deste peer, e nao os da origem:
   aqui nao ha grupo do VRP carregando timers, bfd e advertise-community,
   entao o bloco de quem reaproveita tem que trazer o que o peer avulso
   traz. O que muda de dono e so a politica. #}
{% macro bloco_reaproveita(alvo, origem) -%}
bgp {{ plan.ASN }}
{% for fam in alvo.familias() %}
{{ sessao_do_peer(alvo, fam) }}{{ "\n" if not loop.last -}}
{% endfor %}
{% for fam in alvo.familias() %}
{% set U = fam|upper %}
{% set P = plan.PREFIXO_DO_TIPO[alvo.tipo] %}
{{ familia_bgp(alvo, fam,
     P ~ "-" ~ origem.token ~ "-IMPORT-" ~ U,
     P ~ "-" ~ origem.token ~ "-EXPORT-" ~ U) }}
{% endfor %}
{%- endmacro %}
```

- [ ] **Step 5: Ligar o ramo nos quatro templates**

Em `templates/cliente.txt.j2`, `upstream.txt.j2`, `ix.txt.j2` e `pni.txt.j2`, troque a abertura do ramo condicional. O ramo começa em `{% if grupo %}` nos quatro; ele vira:

```jinja
{% if peer.politica_de is not none %}
{{ m.bloco_reaproveita(peer, origem) }}
{% elif grupo %}
```

O `is not none` nao e preciosismo: **`0` e falso em Jinja**, e o `id` 0 e o primeiro peer de todo cadastro novo. Com o `if peer.politica_de` cru, quem reaproveita de um peer de id 0 cai no ramo avulso e emite a politica inteira uma segunda vez, alem do bloco de remocao derrubar objetos que nao cria.

O `{% endif %}` do fim de cada arquivo continua valendo para a cadeia inteira.

Os quatro já importam as macros com o alias `m`: `upstream.txt.j2`, `ix.txt.j2` e `pni.txt.j2` na linha 1, e `cliente.txt.j2` na linha 5, depois dos comentários de cabeçalho. Não precisa acrescentar import nenhum.

- [ ] **Step 6: Passar a origem pelo `render.py`**

Em `app/render.py`, troque as duas funções:

```python
def render_peer(peer, grupo=None, rede=None, origem=None):
    """O bloco do peer. O `origem` so importa para quem reaproveita: e dela
    que sai o token que nomeia os filtros chamados no bloco."""
    nome = TEMPLATE_POR_TIPO.get(peer.tipo, "%s.txt.j2" % peer.tipo)
    return ambiente(rede).get_template(nome).render(
        peer=peer, grupo=grupo, origem=origem)


def escrever_peer(peer, grupo=None, rede=None, origem=None, *, saida):
    saida.mkdir(parents=True, exist_ok=True)
    destino = peer.arquivo(saida)
    destino.write_text(render_peer(peer, grupo=grupo, rede=rede,
                                   origem=origem),
                       encoding="ascii")
    return destino
```

- [ ] **Step 7: Rodar e confirmar que passa**

Run: `.venv/bin/python -m pytest tests/test_render.py -q`
Expected: PASS. Os goldens existentes não mudam, porque nenhum peer dos fixtures tem `politica_de`.

- [ ] **Step 8: Commit**

```bash
git add app/plan.py app/render.py templates/ tests/test_render.py
git commit -m "O bloco de quem reaproveita sai so com a sessao

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 3: A remoção e o quadro "ao criar"

**Files:**
- Modify: `templates/remover.txt.j2` (o topo do arquivo)
- Modify: `app/plan.py` (`quadro_ao_criar`, linha 156)
- Test: `tests/test_render.py`, `tests/test_plan.py`

**Interfaces:**
- Consumes: `Peer.politica_de` da Task 1.
- Produces: nada que outra task consuma.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_render.py`:

```python
def test_a_remocao_de_quem_reaproveita_nao_derruba_objeto_da_origem():
    # derrubar o filtro da origem apagaria a politica dos dois links
    _, backup = par_de_reaproveitamento()
    texto = render.render_remove(backup)
    assert "undo xpl" not in texto
    assert "undo peer 198.51.100.10" in texto
```

A remoção não precisa da origem: o bloco dela não nomeia filtro nenhum.

Em `tests/test_plan.py`, no topo, some ao import existente de `test_render`:

```python
from test_render import peer_cliente
```

E ao fim do arquivo:

```python
def test_o_quadro_ao_criar_nao_existe_para_quem_reaproveita():
    # o par CL-PEER/APPLY-PEER e da origem: criar um aqui daria dois
    # objetos para o mesmo papel
    assert not plan.quadro_ao_criar(peer_cliente(politica_de=1), False)
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_render.py tests/test_plan.py -q -k reaproveita or quadro_ao_criar`
Expected: FAIL nos dois. O do render porque o `undo xpl` do peer ainda sai, o do plan porque o quadro sai para quem reaproveita.

- [ ] **Step 3: O ramo no `remover.txt.j2`**

O arquivo derruba a sessão nas linhas 1-8 (o `undo peer <ip>`), os objetos com eixo de família nas 14-39, os sem eixo nas 45-76 e a `CL-PEER` comentada nas 78-87. Quem reaproveita só tem o primeiro bloco.

Envolva os blocos 14-76 num `{% if not peer.politica_de %}`, aberto entre a linha 8 e a 14, e fechado depois da linha 76. O cabeçalho do arquivo (linhas 1-8) fica intocado, porque o `undo peer <ip>` vale para quem reaproveita como para qualquer peer.

```jinja
{#- quem reaproveita nao criou objeto nenhum, entao nao tem o que derrubar
    alem da propria sessao. Quem carrega os filtros e o bloco da origem, e
    tirar os dele apagaria a politica dos dois links. #}
{% if peer.politica_de is none %}
```

Pelo mesmo motivo do ramo dos templates: `not 0` e verdadeiro, entao o `not peer.politica_de` cru barraria o ramo de quem reaproveita de um peer de id 0, e a remocao dele derrubaria objetos que ele nao cria.

E na linha 78, o portão da `CL-PEER` ganha a mesma guarda:

```jinja
{% if peer.tipo in plan.TIPOS_COM_APPLY_PEER and peer.politica_de is none %}
```

- [ ] **Step 4: Tirar o quadro de quem reaproveita**

Em `app/plan.py`, dentro de `quadro_ao_criar(alvo, de_grupo)`, logo depois da docstring:

```python
    # quem reaproveita a politica de outro nao tem CL-PEER propria: o par
    # CL-PEER/APPLY-PEER e da origem, e criar um aqui daria dois objetos
    # para o mesmo papel
    if getattr(alvo, "politica_de", None) is not None:
        return False
```

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `.venv/bin/python -m pytest tests/test_render.py tests/test_plan.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/remover.txt.j2 app/plan.py tests/
git commit -m "A remocao de quem reaproveita derruba so a sessao

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 4: A API resolve a origem e guarda a exclusão

**Files:**
- Modify: `app/modelos_api.py` (`PeerForm`, `PeerResumo`)
- Modify: `app/formulario.py` (`CAMPOS_INT`, `peer_do_formulario`)
- Modify: `app/api.py` (`modelo_do_peer`, `listar_peers`, `_salvar_peer`, `excluir_peer`, `saida_peer`, `previa_peer`, `_criar_lista_do_peer`, `_secao_peer`)
- Modify: `web/src/api/schema.d.ts` (regerado: `npm run api:tipos` em `web/`)
- Test: `tests/test_api_peers.py`, `tests/test_api_config.py`

**Interfaces:**
- Consumes: `render.render_peer(..., origem=...)` e `render.escrever_peer(..., origem=...)` da Task 2.
- Produces: `PeerForm.politica_de: str`; `_origem_do_peer(peer, peers)` em `app/api.py`, que devolve o `Peer` da origem ou `None`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_api_peers.py`:

```python
def test_criar_o_segundo_link_reaproveitando_o_primeiro(api, tmp_path):
    """O caminho de ponta a ponta do recurso, pela API.

    O bloco do segundo link nao define objeto nenhum e chama os filtros do
    primeiro, que continuam saindo no bloco dele.
    """
    assert api.post("/api/peers", json=CLIENTE).status_code == 201
    backup = dict(CLIENTE, apelido="ACME-BKP", id="", politica_de="0",
                  sessao_v4_local="198.51.100.9", sessao_v4_remoto="198.51.100.10")
    r = api.post("/api/peers", json=backup)
    assert r.status_code == 201, r.text

    texto = (tmp_path / "out" / str(ASN_DE_TESTE) / "ACME-BKP-cliente.txt").read_text("ascii")
    assert "xpl " not in texto
    assert "route-filter CUST-268127-IMPORT-V4 import" in texto


def test_excluir_a_origem_e_recusado_enquanto_alguem_a_reaproveita(api, tmp_path):
    # apagar a origem deixaria o bloco do outro apontando para filtros que
    # nao existem mais no equipamento
    api.post("/api/peers", json=CLIENTE)
    api.post("/api/peers", json=dict(CLIENTE, apelido="ACME-BKP", id="",
                                     politica_de="0",
                                     sessao_v4_local="198.51.100.9",
                                     sessao_v4_remoto="198.51.100.10"))
    r = api.delete("/api/peers/0")
    assert r.status_code == 422
    assert "reaproveita" in r.json()["erros"]["_"]
    # e o bloco do segundo continua onde estava
    assert (tmp_path / "out" / str(ASN_DE_TESTE) / "ACME-BKP-cliente.txt").exists()


def test_a_previa_de_quem_reaproveita_tambem_nao_tem_objeto(api):
    api.post("/api/peers", json=CLIENTE)
    r = api.post("/api/peers/previa",
                 json=dict(CLIENTE, apelido="ACME-BKP", id="", politica_de="0"))
    assert r.status_code == 200
    assert "xpl " not in r.json()["bloco"]


def test_a_origem_apagada_a_mao_e_recusada_com_erro_claro(api, tmp_path):
    """A segunda barreira, para o arquivo editado por fora.

    O `politica_de` apontando para um id que nao existe e recusado pela
    validacao, mas o arquivo do tenant pode chegar torto por edicao a mao.
    O template roda com StrictUndefined: uma origem nula estoura ali dentro
    com um erro que nao diz nada a quem le. O que a API faz e recusar antes,
    com o nome do campo.
    """
    api.post("/api/peers", json=CLIENTE)
    caminho = caminho_tenant(tmp_path)
    texto = caminho.read_text("utf-8")
    # o peer torto entra no arquivo direto, apontando para um id que nao existe
    caminho.write_text(texto.replace(
        "peers:", "peers:\n- id: 40\n  apelido: TORTO\n  nome: TORTO\n"
        "  tipo: cliente\n  asn: 268127\n  politica_de: 99\n"
        "  descricao: TORTO\n", 1), "utf-8")

    r = api.get("/api/peers/40/saida")
    assert r.status_code == 422
    assert "politica_de" in r.json()["erros"]

    # a previa valida antes de renderizar, entao a origem pendurada volta
    # como erro de campo no 200, e nao como recusa: e o contrato da rota, o
    # mesmo que o grupo_id pendurado ja tinha
    r = api.post("/api/peers/previa",
                 json=dict(CLIENTE, id="40", apelido="TORTO", politica_de="99",
                           sessao_v4_local="198.51.100.9",
                           sessao_v4_remoto="198.51.100.10"))
    assert r.status_code == 200
    assert "politica_de" in r.json()["erros"]
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `.venv/bin/python -m pytest tests/test_api_peers.py -q -k reaproveita or origeme`
Expected: FAIL. O `politica_de` no corpo do POST é ignorado (o pydantic descarta campo desconhecido) e o bloco do backup sai com os objetos dele.

- [ ] **Step 3: O campo no modelo do formulário**

Em `app/modelos_api.py`, no `PeerForm`, ao lado de `grupo_id`:

```python
    politica_de: str = ""
```

E no `PeerResumo`, a lista que a barra lateral e a paleta usam:

```python
    # quem reaproveita precisa que a tela saiba, para nao se oferecer como
    # origem de ninguem: quem cede politica e dono dela
    politica_de: int | None = None
```

Em `app/formulario.py`, acrescente `"politica_de"` à tupla `CAMPOS_INT`.

Em `app/api.py`, dentro de `modelo_do_peer`, ao lado de `grupo_id`:

```python
        politica_de=_texto(peer.politica_de),
```

Em `_criar_lista_do_peer`, que hoje filtra só por tipo e devolve `''` para quem reaproveita — um terceiro estado contra o `string | null` que o schema do front documenta. Reúna o critério no `quadro_ao_criar`, que é quem decide isso:

```python
def _criar_lista_do_peer(peer, rede):
    # o par CL-PEER-<T> / APPLY-PEER-<T> e de cliente, parceiro e upstream,
    # e quem reaproveita a politica de outro nao tem o par: o da origem ja
    # cobre. O criterio e o mesmo do template, entao os dois nao podem
    # discordar.
    if not plan.quadro_ao_criar(peer, False):
        return None
    return render.render_criar_lista(peer, rede=rede)
```

E em `listar_peers`, que monta o `PeerResumo` campo a campo:

```python
    return [PeerResumo(id=p.id, token=p.token, tipo=p.tipo, asn=p.asn,
                       apelido=p.apelido, nome=p.nome, grupo_id=p.grupo_id,
                       politica_de=p.politica_de)
            for p in _peers(t)]
```

- [ ] **Step 4: Resolver a origem e passá-la ao render**

Em `app/api.py`, ao lado de `_grupo_do_peer`:

```python
def _origem_do_peer(peer, peers):
    """O peer de quem este reaproveita a politica, ou None.

    Quem chama trata o None quando `politica_de` esta setado: um arquivo
    editado a mao pode deixar a referencia apontando para um id que nao
    existe, e o template roda com StrictUndefined, entao uma origem nula
    estoura la dentro com um erro que nao diz nada ao operador. A validacao
    recusa esse cadastro, e aqui e a segunda barreira.
    """
    if peer.politica_de is None:
        return None
    return peers_mod.achar_id(peers, peer.politica_de)


def _sem_origem(peer, peers):
    """O 422 de quem reaproveita de um peer que nao esta no cadastro."""
    if peer.politica_de is None or _origem_do_peer(peer, peers) is not None:
        return None
    return _falha(422, [validate.Erro(
        "politica_de", "peer de origem nao encontrado no cadastro")])
```

Em `_salvar_peer`, troque a chamada do render:

```python
    destino = render.escrever_peer(peer, grupo=_grupo_do_peer(peer, grupos),
                                   rede=rede,
                                   origem=_origem_do_peer(peer, peers),
                                   saida=t.saida)
```

Nas **leituras que renderizam sem validar** — `saida_peer` e `_secao_peer`, que montam o bloco de um registro lido do yaml —, antes de renderizar:

```python
    erro = _sem_origem(peer, peers)
    if erro is not None:
        return erro
```

E passe `origem=_origem_do_peer(peer, peers)` para `render.render_peer`.

**A prévia fica de fora da guarda, e isso é deliberado.** `previa_peer` chama `_peer_do_pedido`, que roda o `validar`, e o `validar` já emite `Erro("politica_de", "peer de origem nao encontrado")` para uma origem que não resolve. Então a origem pendurada chega como erro de campo, a rota volta no `if erros` com **200 e sem bloco** — o contrato que o docstring dela declara — e o render no fim só é alcançado quando não há erro, ou seja, quando a origem resolveu. Com a guarda ali, o 200 virava 422 e a rota divergia do `grupo_id` pendurado, que continua voltando 200 com o campo nomeado.

Em `_salvar_peer` a guarda também não é necessária, pelo mesmo motivo.

- [ ] **Step 5: A guarda na exclusão**

Em `app/api.py`, dentro de `excluir_peer`, antes do `unlink`:

```python
    dependentes = [p for p in peers if p.politica_de == ident]
    if dependentes:
        return _falha(422, [validate.Erro(
            "_",
            "o peer %s reaproveita a politica deste: %s"
            % (dependentes[0].nome,
               "troque a origem dele antes de excluir"
               if len(dependentes) == 1
               else "%d peers reaproveitam a politica deste"
               % len(dependentes)))])
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `.venv/bin/python -m pytest tests/test_api_peers.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/modelos_api.py app/formulario.py app/api.py tests/test_api_peers.py
git commit -m "A API resolve a origem do reaproveitamento e guarda a exclusao

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 5: O formulário

**Files:**
- Modify: `web/src/telas/peers/camposPeer.ts` (o tipo `Campo` e a tabela `CAMPOS_PEER`)
- Modify: `web/src/telas/peers/PeerTela.tsx` (passa a lista de peers ao formulário)
- Modify: `web/src/telas/peers/FormularioPeer.tsx` (recebe a lista e monta as candidatas)
- Modify: `web/src/components/Formulario.tsx` (resolve `campo.origens` e desenha a nota)
- Test: `web/src/telas/peers/FormularioPeer.test.tsx`

**Interfaces:**
- Consumes: `PeerForm.politica_de` e `PeerResumo.politica_de` da Task 4.
- Produces: `Contexto.origens: Opcao[]` no `camposPeer.ts`; `Formulario` ganha a prop `notaDaPolitica?: ReactNode`.

- [ ] **Step 1: Escrever os testes que falham**

Em `web/src/telas/peers/FormularioPeer.test.tsx`, comece pela lista que serve os casos. O `ACME-BKP` existe para provar que quem reaproveita não se oferece como origem, e o `OUTRO` e o `Upstream` para provar os filtros de tipo e de ASN:

```tsx
const PEERS = [
  { id: 1, token: "268127", tipo: "cliente", asn: 268127, apelido: "ACME",
    nome: "Cliente ACME", grupo_id: null, politica_de: null },
  { id: 2, token: "268128", tipo: "cliente", asn: 268128, apelido: "OUTRO",
    nome: "Cliente OUTRO", grupo_id: null, politica_de: null },
  { id: 3, token: "14840", tipo: "upstream", asn: 14840, apelido: "",
    nome: "Upstream", grupo_id: null, politica_de: null },
  { id: 4, token: "ACME-BKP", tipo: "cliente", asn: 268127, apelido: "ACME-BKP",
    nome: "Cliente ACME BKP", grupo_id: null, politica_de: 1 },
]
```

O `Montar` do arquivo passa `peers={PEERS}` para o `FormularioPeer`, e os casos novos vão ao fim do `describe`:

```tsx
it("a lista de origem so traz peer do mesmo tipo e ASN, e dono da politica", async () => {
  render(<Montar iniciais={{ tipo: "cliente", asn: "268127" }} />)
  const opcoes = await screen.findAllByRole("option", { name: /ACME/ })
  // o OUTRO e de outro ASN, o Upstream e de outro tipo, e o ACME-BKP ja
  // reaproveita de alguem
  expect(opcoes.map((o) => o.textContent)).toEqual(["Cliente ACME"])
})

it("escolher a origem deixa a nota, e nao esconde campo", async () => {
  // a decisao da spec: o operador nao perde de vista o que esta cadastrado
  render(<Montar iniciais={{ tipo: "cliente", asn: "268127" }} />)
  await userEvent.selectOptions(screen.getByLabelText(/reaproveitar/i), "1")
  expect(screen.getByText(/a política vem do peer/i)).toBeInTheDocument()
  expect(screen.getByLabelText("LP base")).toBeInTheDocument()
  expect(screen.getByLabelText("origem")).toBeInTheDocument()
})

it("o peer que cede politica avisa que renomear mexe no bloco do outro", async () => {
  // o aviso mora no formulario da origem, que e onde a renomeacao acontece
  render(<Montar iniciais={{ id: "1", tipo: "cliente", asn: "268127" }} />)
  expect(await screen.findByText(/um peer reaproveita a política deste/i))
    .toBeInTheDocument()
})
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `cd web && npx vitest run src/telas/peers/FormularioPeer.test.tsx`
Expected: FAIL, com `Unable to find a label with the text of: /reaproveitar/i`.

- [ ] **Step 3: O campo na tabela**

Em `web/src/telas/peers/camposPeer.ts`, acrescente ao tipo `Campo`:

```ts
  // a lista de origens candidatas sai dos peers ja cadastrados, e nao do
  // /api/plano: o filtro depende do tipo e do ASN que o formulario tem
  // agora, e so a tela tem a lista
  origens?: boolean
```

E na tabela `CAMPOS_PEER`, antes de `{ nome: "classe" ... }`:

```ts
  { nome: "politica_de", rotulo: "Reaproveitar a política de", tipo: "select", secao: "identificacao",
    origens: true,
    ajuda: "o segundo link de um cliente usa a política do primeiro: nenhum filtro é gerado de novo" },
```

E o campo entra também na lista de campos da seção, em `web/src/lib/campos.ts` (`SECOES_PEER`, a seção `identificacao`). Sem essa entrada o badge de erro da seção e o painel de saída não enxergam uma recusa no campo, e o operador só vê a mensagem embaixo do controle.

- [ ] **Step 4: Alimentar o select e a nota**

Em `web/src/telas/peers/PeerTela.tsx`, no `FormularioPeer` da linha 430, passe a lista que a tela já carrega para a barra lateral:

```tsx
              peers={peers.data ?? []}
```

Em `web/src/telas/peers/camposPeer.ts`, o `Contexto` ganha a lista:

```ts
export type Contexto = {
  plano: Plano
  tipo: string
  grupos: Opcao[]
  // as origens possiveis do reaproveitamento. Sai da lista de peers e nao do
  // /api/plano: o filtro depende do tipo e do ASN que o formulario tem agora,
  // e quem tem os dois e a tela
  origens: Opcao[]
}
```

Em `web/src/telas/peers/FormularioPeer.tsx`, acrescente `peers` às props (`PeerResumo[]`), e onde o `ctx` é montado:

```tsx
  // Quem cede politica e dono dela: nao pode reaproveitar de outro nem estar
  // num grupo, porque nos dois casos o bloco dele nao define os filtros que
  // quem reaproveita iria chamar.
  // O `id` em branco e o do peer novo, e `Number("")` e 0: sem a guarda, o
  // formulario novo enxergaria o peer de id 0 como ele mesmo e o esconderia
  // da lista.
  const meuId = String(valores.id ?? "") === "" ? null : Number(valores.id)

  // A opcao vazia e o caminho de volta: sem ela, escolher uma origem vira
  // uma porta so de ida pela tela, e voltar a carregar a propria politica
  // dependeria da API - que e o caminho que esta tela existe para fechar.
  const origens: Opcao[] = [
    { valor: "", rotulo: "— carrega a própria política —" },
    ...peers
      .filter((p) => p.id !== meuId
        && p.tipo === valores.tipo
        && p.asn === Number(valores.asn)
        && p.politica_de == null
        && p.grupo_id == null)
      .map((p) => ({ valor: String(p.id), rotulo: p.apelido || p.nome || p.token })),
  ]

  const escolhida = origens.find((o) => o.valor === String(valores.politica_de))
  const notaDaPolitica = escolhida && escolhida.valor
    ? `A política vem do peer ${escolhida.rotulo}. Editar estes campos não muda o que é gerado.`
    : undefined
```

**Trocar o tipo ou o ASN limpa a seleção**, como os outros selects encadeados do formulário já fazem: sem isso o id antigo fica no campo como uma opção fora da lista, o gatilho mostra um número solto, e o operador só descobre que está errado quando o salvar recusa.

E passe `origens={origens}` no `ctx` e `notaDaPolitica={notaDaPolitica}` para o `<Formulario>`.

Em `web/src/components/Formulario.tsx`, na resolução das opções (a linha `const base = campo.opcoes?.(ctx) ?? []`), troque por:

```tsx
  const base = campo.origens ? ctx.origens : (campo.opcoes?.(ctx) ?? [])
```

Acrescente a prop `notaDaPolitica?: string` ao tipo `Props` e à desestruturação, e desenhe a nota acima dos campos da seção de política, logo depois do `<legend>`:

```tsx
            {secao.id === "politica" && notaDaPolitica && (
              <p className="px-2 pb-1 text-xs text-muted-foreground">{notaDaPolitica}</p>
            )}
```

- [ ] **Step 5: O aviso do token na origem**

Ainda em `FormularioPeer.tsx`, ao lado do cálculo das origens:

```tsx
  // quem cede politica carrega o token que nomeia os filtros que o outro
  // chama: renomear o apelido daqui muda o nome dos objetos do bloco de la,
  // que fica desatualizado ate ser gerado de novo
  const dependentes = peers.filter((p) => p.politica_de === Number(valores.id))
  const avisoDoToken = dependentes.length === 0
    ? undefined
    : `${dependentes.length === 1
        ? "Um peer reaproveita"
        : `${dependentes.length} peers reaproveitam`} a política deste. Mudar o apelido troca o token, e com ele o nome dos filtros que ele chama.`
```

Passe `avisoDoToken={avisoDoToken}` ao `<Formulario>`.

Em `web/src/components/Formulario.tsx`, acrescente `avisoDoToken?: string` às props, e troque a linha do `nota=` no `CampoRender` por:

```tsx
                nota={campo.nome === "apelido" && avisoDoToken
                  ? avisoDoToken
                  : pertenceAoTipo(campo.nome, camposPorTipo, tipo)
                    ? undefined
                    : `o bloco de ${tipo} não usa este campo`}
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd web && npx vitest run src/telas/peers/FormularioPeer.test.tsx && npx tsc -b`
Expected: PASS e `tsc` limpo.

- [ ] **Step 7: Commit**

```bash
git add web/src/telas/peers/ web/src/components/Formulario.tsx
git commit -m "O formulario do peer escolhe de quem reaproveitar a politica

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Task 6: A documentação

**Files:**
- Modify: `PLANO.md` (seção nova, depois de "Grupo nos cinco tipos")
- Modify: `README.md` (a lista do "O que não faz")

**Interfaces:**
- Consumes: nada.
- Produces: nada.

- [ ] **Step 1: A seção no PLANO**

Depois da seção "Grupo nos cinco tipos", acrescente:

```markdown
## Reaproveitamento de política entre peers

Dois links do mesmo cliente, um principal e um backup, têm a mesma política e
o mesmo ASN. Escrever o par de filtros duas vezes faz a política dos dois
divergir na primeira edição feita num só, e o grupo resolve isso criando um
`peer group` no equipamento, que é um objeto a mais e faz os membros
compartilharem também o que é de sessão.

O campo `politica_de` no cadastro do peer resolve o mesmo problema sem grupo:
o segundo link não define objeto nenhum e chama os filtros do primeiro pelo
nome dele.

```scss
bgp 64512
 peer 198.51.100.10 description NETMAC-BKP
 peer 198.51.100.10 as-number 270620
 peer 198.51.100.10 route-limit 50 alert-only
 ipv4-family unicast
  peer 198.51.100.10 enable
  peer 198.51.100.10 route-filter CUST-NETMAC-IMPORT-V4 import
  peer 198.51.100.10 route-filter CUST-NETMAC-EXPORT-V4 export
```

O exemplo omite as linhas fixas de sessão que todo bloco traz
(`public-as-only force`, `advertise-community` e `advertise-large-community`),
e a ordem é a do gerador: `as-number` antes de `description`.

O que o peer que reaproveita guarda de próprio é a sessão: IPs, `route-limit`,
timers, `bfd`, graceful-restart, e as linhas fixas que todo bloco de sessão
traz (`public-as-only force`, `advertise-community`,
`advertise-large-community`). O resto da **política** vem da origem, incluindo
o LP, que mora dentro do filtro de import. Os dois links ficam com a mesma
preferência, e a diferença entre eles vem do que o cliente anuncia em cada um.

A origem tem que ser dona da própria política: não pode reaproveitar de
outro nem estar num grupo. E ninguém apaga uma origem enquanto alguém a
reaproveita.

Renomear o apelido da origem troca o token dela e com ele o nome dos objetos
que quem reaproveita chama: o bloco do segundo link fica apontando para nomes
que o equipamento não tem mais, até ser gerado de novo.
```

- [ ] **Step 2: O README**

Em `README.md`, na lista do "O que não faz", depois do bullet do PDF:

```markdown
- **Não regenera o bloco de quem reaproveita a política de outro peer.** Trocar
  o apelido da origem muda o token dela, e com ele o nome dos filtros chamados
  no bloco do outro. O app avisa e deixa a reaplicação para o operador, porque
  regenerar sozinho o bloco de outro peer quebraria a regra de que gerar um não
  mexe na saída do outro.
```

- [ ] **Step 3: Conferir que o PLANO continua consistente**

Run: `grep -n "politica_de\|reaproveita" PLANO.md README.md`
Expected: as duas seções novas, e nenhuma afirmação que contradiga "Grupo nos cinco tipos".

- [ ] **Step 4: Commit**

```bash
git add PLANO.md README.md
git commit -m "O plano e o README sabem do reaproveitamento de politica

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Verificação final

- [ ] `.venv/bin/python -m pytest -q` — a suíte inteira verde
- [ ] `cd web && npm run test && npx tsc -b` — o front verde e o tipo limpo
- [ ] Gerar o par de exemplo com o cadastro real e conferir que o bloco do segundo link não tem `xpl` e chama os filtros do primeiro
