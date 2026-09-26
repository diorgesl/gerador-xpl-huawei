# Blocos do próprio AS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao operador um cadastro dos prefixos do próprio AS, com consulta ao IRR e um conjunto de communities por prefixo, do qual sai a originação completa: estática de ancoragem, filtro `ORIGEM-*` e a linha `network` que o amarra.

**Architecture:** A lista mora numa seção `blocos` do `peers.yaml`, com um `Bloco` por prefixo em `app/peers.py`. Um template novo (`blocos.txt.j2`) emite as três peças por prefixo em duas partes, uma fora da view do BGP e outra dentro. O egress não ganha ramo nenhum: as communities que o operador escreve são as mesmas que o cliente manda na sessão, e os filtros de saída já as leem. A única peça compartilhada que muda é o `EXPORT-SANITY`, que passa a dispensar a marca de origem para rota originada localmente e a barrar o `1900` explicitamente.

**Tech Stack:** Python 3, FastAPI, Jinja2, PyYAML, pytest. Sem banco: o estado é o `peers.yaml`.

**Spec:** `docs/superpowers/specs/2026-09-24-blocos-proprios-design.md`

## Global Constraints

- Todo arquivo que sai em `out/` é ASCII puro, escrito com `encoding="ascii"`. Acento quebra o pipeline de TFTP e o diff do equipamento.
- Community escrita por filtro passa por `plan.c()`, `plan.c5ppa()`, `plan.c6ca()`, `plan.c_large()` ou pelo `Rede`. Nenhum literal `64512` em template ou em código de geração.
- `apply community` e `apply large-community` sempre com `overwrite` explícito. `additive` só depois de um `overwrite`.
- Nome de objeto do VRP não aceita ponto nem dois-pontos. O nome do filtro é `ORIGEM-<endereco>_<mascara>`, tudo com traço.
- Os testes são pytest e rodam com `pytest` na raiz. Nenhum teste escreve em `out/` do checkout: usa `tmp_path` e `monkeypatch`.
- `peers.yaml` sem a chave `blocos` carrega como lista vazia, e gravar de volta não pode fazer a chave nascer. É a mesma decisão que a chave `asn` tomou.
- `plan.PREFERENCE_ORIGEM = 250` e `plan.LP_ORIGEM = 900`. Os dois valores são decisão do desenho, não campo do operador.

## Review Focus

Cada linha abaixo é um caso que a spec implica e que nenhum teste de tarefa cobre por si. O teste que fixa cada um está na tarefa que é dona do código, no passo em que ela o cria.

1. **`peers.yaml` que já existe, sem a seção `blocos`, gravado de novo.** Nada na seção, e o arquivo não pode ganhar `blocos:` — quem nunca usou a tela ficaria com um diff sem ter mexido em nada. Teste na Task 1.
2. **Prefixo digitado à mão que não está no IRR.** Salva igual, porque o gate é a consulta e não a verdade. O IRR é a fonte da sugestão, e o operador responde pelo que assume. Teste na Task 7.
3. **Consulta com o `bgpq4` fora do ar.** A lista salva não pode ser perdida nem truncada: o POST que falha não grava, e a tela devolve o erro com o texto que o operador já tinha. Teste na Task 7.
4. **Bloco com lista de communities vazia.** O filtro sai com o `1000` e mais nada, e o `apply large-community` não sai. É o caso mais comum, porque bloco sem tratamento manual é o default. Teste na Task 4.
5. **Dois prefixos distintos que gerariam o mesmo nome de filtro.** Colisão de nome de objeto no VRP é uma linha que derruba a outra em silêncio. Teste na Task 2.

---

### Task 1: O `Bloco` e a seção `blocos` no `peers.yaml`

**Files:**
- Modify: `app/peers.py`
- Test: `tests/test_peers.py`

**Interfaces:**
- Consumes: `FAMILIAS` e `Rede` de `app.plan`, já importados no topo de `peers.py`.
- Produces:
  - `peers_mod.CHAVE_BLOCOS: str` — a string `"blocos"`.
  - `peers_mod.Bloco` — dataclass com os campos `prefixo: str` e `communities: list`, mais `para_dict()` e `de_dict(d)`.
  - `peers_mod.carregar_blocos(caminho=PEERS_YAML) -> dict[str, list[Bloco]]` — chaves `"v4"` e `"v6"` sempre presentes, prefixo normalizado na leitura.
  - `peers_mod.gravar_blocos(blocos, caminho=PEERS_YAML) -> None`.
  - `peers_mod.mesclar_blocos(salvos, consultados) -> tuple[list[Bloco], list[Bloco]]`.

- [ ] **Step 1: Write the failing tests**

Acrescente ao fim de `tests/test_peers.py`. O topo do arquivo já traz `import pytest` e `from app import peers as mod`, e os testes que existem usam o apelido `mod.`: siga o mesmo apelido, e não um `peers.` que não existe no arquivo.

```python
def test_blocos_ausentes_no_yaml_carregam_vazios(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text("asn: 264130\npeers: []\n", encoding="utf-8")
    assert peers.carregar_blocos(caminho) == {"v4": [], "v6": []}


def test_gravar_blocos_vazios_nao_cria_a_chave(tmp_path):
    """Quem nunca usou a tela nao pode ganhar um diff no peers.yaml."""
    caminho = tmp_path / "peers.yaml"
    caminho.write_text("asn: 264130\npeers: []\n", encoding="utf-8")
    peers.gravar_blocos({"v4": [], "v6": []}, caminho)
    assert "blocos" not in caminho.read_text(encoding="utf-8")


def test_round_trip_dos_blocos(tmp_path):
    caminho = tmp_path / "peers.yaml"
    blocos = {"v4": [peers.Bloco(prefixo="38.252.64.0/22",
                                 communities=["64512:613", "64512:621"])],
              "v6": [peers.Bloco(prefixo="2804:36b4::/32", communities=[])]}
    peers.gravar_blocos(blocos, caminho)
    lido = peers.carregar_blocos(caminho)
    assert lido["v4"][0].prefixo == "38.252.64.0/22"
    assert lido["v4"][0].communities == ["64512:613", "64512:621"]
    assert lido["v6"][0].prefixo == "2804:36b4::/32"
    assert lido["v6"][0].communities == []


def test_o_prefixo_e_normalizado_na_leitura(tmp_path):
    """O nome do filtro e o casamento da reconsulta saem do prefixo
    canonico, entao um CIDR torto no yaml nao pode chegar ate la."""
    caminho = tmp_path / "peers.yaml"
    caminho.write_text(
        "blocos:\n  v4:\n  - prefixo: 38.252.64.7/22\n    communities: []\n",
        encoding="utf-8")
    assert peers.carregar_blocos(caminho)["v4"][0].prefixo == "38.252.64.0/22"


def test_prefixo_invalido_no_yaml_nomeia_o_arquivo(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text(
        "blocos:\n  v4:\n  - prefixo: nao-e-cidr\n    communities: []\n",
        encoding="utf-8")
    with pytest.raises(ValueError) as erro:
        peers.carregar_blocos(caminho)
    assert "blocos.v4" in str(erro.value)


def test_de_dict_do_bloco_ignora_chave_desconhecida():
    b = peers.Bloco.de_dict({"prefixo": "10.0.0.0/8", "acoes": [1]})
    assert b.prefixo == "10.0.0.0/8"
    assert b.communities == []


def test_mesclar_preserva_o_tratamento_do_prefixo_que_ficou():
    salvo = peers.Bloco(prefixo="38.252.64.0/22", communities=["64512:621"])
    visiveis, ausentes = peers.mesclar_blocos([salvo], ["38.252.64.0/22"])
    assert visiveis == [salvo]
    assert visiveis[0].communities == ["64512:621"]
    assert ausentes == []


def test_mesclar_poe_o_prefixo_novo_sem_tratamento():
    visiveis, _ = peers.mesclar_blocos([], ["38.252.64.0/24"])
    assert [(b.prefixo, b.communities) for b in visiveis] == [
        ("38.252.64.0/24", [])]


def test_mesclar_devolve_o_ausente_no_fim_e_marcado():
    salvo = peers.Bloco(prefixo="38.252.66.0/24", communities=["64512:211"])
    visiveis, ausentes = peers.mesclar_blocos([salvo], ["38.252.64.0/22"])
    assert [b.prefixo for b in visiveis] == ["38.252.64.0/22", "38.252.66.0/24"]
    assert ausentes == [salvo]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_peers.py -k bloco -v`
Expected: FAIL com `AttributeError: module 'app.peers' has no attribute 'carregar_blocos'`

- [ ] **Step 3: Add `import ipaddress` to `app/peers.py`**

Hoje o arquivo importa `dataclass`, `field`, `Path`, `yaml` e `plan`. Acrescente:

```python
import ipaddress
```

- [ ] **Step 4: Add the constant and the dataclass**

Em `app/peers.py`, logo abaixo de `CHAVE_POLITICA = "asn_politica"`:

```python
# a secao dos prefixos do proprio AS, no fim do arquivo. Ela e da rede e
# nao de um peer, como o asn e o asn_politica: o prefixo proprio nao tem
# sessao e nao disputa o espaco de identificadores do 5PPA.
CHAVE_BLOCOS = "blocos"
```

E depois da classe `Grupo`, no fim do arquivo:

```python
@dataclass
class Bloco:
    """Um prefixo do proprio AS e o que ele leva alem da marca de origem.

    O `1000` nao e campo: ele e escrito pelo filtro gerado, sempre, e nao
    ha valor aqui que o substitua. O que o operador escreve nesta lista e
    o que vem junto dele.
    """

    prefixo: str = ""
    communities: list = field(default_factory=list)

    def para_dict(self):
        return {"prefixo": self.prefixo, "communities": self.communities}

    @classmethod
    def de_dict(cls, d):
        conhecidos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in conhecidos})


def carregar_blocos(caminho=PEERS_YAML):
    """As duas listas do arquivo, com o prefixo ja canonico.

    A canonicalizacao e na leitura e nao na gravacao de proposito: o nome
    do filtro e o casamento da reconsulta saem os dois do prefixo, e um
    CIDR torto escrito a mao no yaml chegaria ate la sem que nada
    reclamasse. Canonico aqui, o resto do app so ve uma forma.
    """
    bruto = _ler_bruto(caminho).get(CHAVE_BLOCOS) or {}
    saida = {}
    for fam in FAMILIAS:
        saida[fam] = []
        for d in bruto.get(fam) or []:
            bloco = Bloco.de_dict(d)
            try:
                bloco.prefixo = str(ipaddress.ip_network(bloco.prefixo,
                                                         strict=False))
            except ValueError as erro:
                raise ValueError(
                    "%s: prefixo invalido em blocos.%s: %r"
                    % (caminho, fam, bloco.prefixo)) from erro
            saida[fam].append(bloco)
    return saida


def gravar_blocos(blocos, caminho=PEERS_YAML):
    """Grava as duas listas, e nao cria a chave quando as duas estao vazias.

    E o mesmo cuidado do gravar_asn: a ausencia da chave e o estado de
    quem nunca usou a tela, e gravar de volta nao tem por que transformar
    isso num diff.
    """
    dados = _ler_bruto(caminho)
    cheio = {fam: [b.para_dict() for b in blocos.get(fam) or []]
             for fam in FAMILIAS}
    if any(cheio.values()):
        dados[CHAVE_BLOCOS] = cheio
    else:
        dados.pop(CHAVE_BLOCOS, None)
    _escrever_bruto(dados, caminho)


def mesclar_blocos(salvos, consultados):
    """A lista da tela depois da consulta: (visiveis, ausentes).

    Casa por prefixo canonico, que e chave estavel: o tratamento escrito a
    mao sobrevive a reconsulta, o prefixo novo entra sem tratamento, e o
    que estava salvo e a consulta nao devolveu volta no fim da lista e
    tambem separado em `ausentes`, para a tela marcar. A decisao de manter
    ou remover e do operador, e por isso o ausente continua na lista.
    """
    por_prefixo = {b.prefixo: b for b in salvos}
    visiveis = []
    for cidr in consultados:
        chave = str(ipaddress.ip_network(cidr, strict=False))
        antigo = por_prefixo.pop(chave, None)
        visiveis.append(antigo if antigo is not None
                        else Bloco(prefixo=chave, communities=[]))
    ausentes = list(por_prefixo.values())
    return visiveis + ausentes, ausentes
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_peers.py -v`
Expected: PASS, com os testes novos e os que já existiam.

- [ ] **Step 6: Commit**

```bash
git add app/peers.py tests/test_peers.py
git commit -m "O bloco do proprio AS ganha lugar no peers.yaml"
```

---

### Task 2: O nome do filtro e os conjuntos no `plan.py`

**Files:**
- Modify: `app/plan.py`
- Test: `tests/test_plan.py`

**Interfaces:**
- Consumes: nada das tarefas anteriores.
- Produces:
  - `plan.PREFERENCE_ORIGEM = 250`
  - `plan.LP_ORIGEM = 900`
  - `plan.nome_origem(cidr) -> str`
  - `plan.endereco(cidr) -> str`
  - `plan.mascara(cidr) -> str`
  - `plan.separa_communities(valores) -> tuple[list[str], list[str]]`
  - `plan.conjunto_de(lista) -> str`
  - Os cinco nomes também respondem pelo `Rede`, pela delegação do `__getattr__` (nenhum contém o AS de fábrica, então não caem no `_NOMES_COM_O_ASN`).

- [ ] **Step 1: Write the failing tests**

Acrescente ao fim de `tests/test_plan.py`.

```python
def test_nome_origem_v4():
    assert plan.nome_origem("38.252.64.0/22") == "ORIGEM-38-252-64-0_22"


def test_nome_origem_v6_come_o_abreviador():
    """O `::` some junto com os hextetos que ele abrevia, e o que sobra e
    o prefixo escrito com os hextetos que existem."""
    assert plan.nome_origem("2804:36b4:8000::/34") == "ORIGEM-2804-36b4-8000_34"
    assert plan.nome_origem("2804:36b4::/32") == "ORIGEM-2804-36b4_32"


def test_nome_origem_normaliza_o_prefixo():
    assert plan.nome_origem("38.252.64.7/22") == plan.nome_origem("38.252.64.0/22")


def test_dois_prefixos_distintos_nao_colidem_no_nome():
    """Colisao de nome de objeto no VRP e uma linha derrubando a outra."""
    prefixos = ["38.252.64.0/22", "38.252.64.0/23", "38.252.64.0/24",
                "38.252.66.0/23", "38.252.66.0/24", "170.80.32.0/22",
                "2804:36b4::/32", "2804:36b4:8000::/34",
                "2804:36b4:8000::/33", "2804:36b4:c000::/34"]
    nomes = [plan.nome_origem(c) for c in prefixos]
    assert len(set(nomes)) == len(nomes)


def test_endereco_e_mascara_do_v4():
    assert plan.endereco("38.252.64.0/22") == "38.252.64.0"
    assert plan.mascara("38.252.64.0/22") == "255.255.252.0"


def test_endereco_e_mascara_do_v6():
    """Em v6 a mascara e o comprimento direto: e o que o `ipv6
    route-static` e o `network` da view da familia pedem."""
    assert plan.endereco("2804:36b4:8000::/34") == "2804:36b4:8000::"
    assert plan.mascara("2804:36b4:8000::/34") == "34"


def test_separa_communities_pela_contagem_de_dois_pontos():
    std, lg = plan.separa_communities(
        ["64512:613", "64512:0:14840", "15169:12100", "64512:4:14840"])
    assert std == ["64512:613", "15169:12100"]
    assert lg == ["64512:0:14840", "64512:4:14840"]


def test_conjunto_de_monta_o_literal_com_a_lista_pronta():
    assert plan.conjunto_de(["64512:1000", "64512:613"]) == "{64512:1000, 64512:613}"
    assert plan.conjunto_de([]) == "{}"


def test_o_rede_responde_pelos_nomes_novos():
    """Os templates falam com o Rede, nunca com o modulo."""
    assert plan.Rede().nome_origem("38.252.64.0/22") == "ORIGEM-38-252-64-0_22"
    assert plan.Rede(asn=264130, politica=65532).nome_origem(
        "38.252.64.0/22") == "ORIGEM-38-252-64-0_22"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_plan.py -k "origem or conjunto or separa or endereco or mascara" -v`
Expected: FAIL com `AttributeError: module 'app.plan' has no attribute 'nome_origem'`

- [ ] **Step 3: Add `import ipaddress` and the constants**

No topo de `app/plan.py`, hoje só há `import functools`. Acrescente:

```python
import functools
import ipaddress
```

Junto das outras constantes de originação, perto de `ORIGEM_ANUNCIAVEL`:

```python
# --- originacao dos prefixos proprios ---------------------------------

# a preferencia da estatica para NULL0 que ancora o `network`. Ela ganha
# do BGP, que e o que impede a rota de um cliente com sub-alocacao dentro
# do bloco de virar a origem do `network`, e perde do IGP e da estatica de
# preferencia default, para um agregado que exista de verdade na tabela
# sair com o next-hop de verdade em vez de ir para o NULL0.
PREFERENCE_ORIGEM = 250
# o LP de toda rota originada. E o valor do exemplo do PLANO.md e o do
# BGP_EXEMPLO.txt, e nao depende do tipo de peer nem do prefixo.
LP_ORIGEM = 900
```

- [ ] **Step 4: Add the helpers**

No fim de `app/plan.py`, depois de `conjunto` e antes de `noadv`:

```python
def _rede_do_cidr(cidr):
    """O ip_network do CIDR, sem exigir que ele venha canonico."""
    return ipaddress.ip_network(cidr, strict=False)


def nome_origem(cidr):
    """O nome do filtro de originacao: ORIGEM-<endereco>_<mascara>.

    O ponto vira traco porque nome de objeto no VRP nao aceita ponto, e em
    v6 os dois-pontos viram traco pelo mesmo motivo. O `::` some junto com
    os hextetos vazios que ele abrevia, entao o corpo do nome carrega so os
    hextetos que existem de verdade. O `_` antes da mascara le como
    mascara, que e o que o `m` da convencao antiga nao fazia.
    """
    rede = _rede_do_cidr(cidr)
    if rede.version == 4:
        corpo = str(rede.network_address).replace(".", "-")
    else:
        corpo = "-".join(p for p in str(rede.network_address).split(":") if p)
    return "ORIGEM-%s_%d" % (corpo, rede.prefixlen)


def endereco(cidr):
    """O endereco na forma que o comando pede: 38.252.64.0 ou 2804:36b4::."""
    return str(_rede_do_cidr(cidr).network_address)


def mascara(cidr):
    """A mascara na forma que o comando pede.

    Em v4 e pontuada, que e o que o `ip route-static` e o `network` de
    `ipv4-family` esperam. Em v6 e o comprimento direto, sem pontuacao,
    como no `network 2804:36B4:: 32` do BGP_EXEMPLO.txt.
    """
    rede = _rede_do_cidr(cidr)
    return str(rede.netmask) if rede.version == 4 else str(rede.prefixlen)


def separa_communities(valores):
    """(standard, large) na ordem em que vieram.

    A lista do cadastro do bloco e uma so, porque o operador escreve a
    community e nao a forma dela, e o VRP pede `apply community` e
    `apply large-community` em linhas separadas. Quem separa e a contagem
    de dois-pontos: dois e large (RFC 8195), um e standard (RFC 1997).
    """
    standard, large = [], []
    for valor in valores or []:
        (large if valor.count(":") == 2 else standard).append(valor)
    return standard, large


def conjunto_de(lista):
    """O mesmo conjunto do `conjunto`, para uma lista que ja veio pronta.

    O `conjunto` recebe os itens soltos e nao serve quando a lista foi
    montada no template por concatenacao, que e o caso do `1000` gerado
    mais o que o operador escreveu.
    """
    return conjunto(*lista)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_plan.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/plan.py tests/test_plan.py
git commit -m "O nome do filtro de originacao sai do prefixo"
```

---

### Task 3: A validação das communities do bloco

**Files:**
- Modify: `app/validate.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `plan.NOADV`, `plan.NOADV_CUST`, `plan.ONLY_NOT`, `plan.CLASSE_6CA`, `plan.Rede`.
- Produces:
  - `validate.ACOES_LIDAS: frozenset[int]`, `validate.CLASSES_6CA_LIDAS: frozenset[int]`, `validate.DIGITOS_6CA_LIDOS: frozenset[int]`, `validate.DIGITOS_5PPA_LIDOS: frozenset[int]`
  - `validate.validar_blocos(blocos, rede=None) -> list[Erro]` — `blocos` é o `dict[str, list[Bloco]]` da Task 1, e o `Erro.campo` é `"blocos_v4"` ou `"blocos_v6"`.

- [ ] **Step 1: Write the failing tests**

Acrescente ao fim de `tests/test_validate.py`. O topo do arquivo tem `from app.peers import Peer, Grupo`: acrescente `Bloco` a essa linha e use o nome direto nos testes.

```python
def bloco(prefixo="38.252.64.0/22", communities=None):
    return Bloco(prefixo=prefixo, communities=list(communities or []))


def erros_de(communities):
    return validate.validar_blocos({"v4": [bloco(communities=communities)],
                                    "v6": []})


def test_bloco_sem_communities_nao_tem_erro():
    assert erros_de([]) == []


def test_o_673_do_exemplo_do_plano_e_recusado():
    """O PLANO escreve 673 no exemplo de ORIGIN, e a classe 7 nao tem ramo
    em filtro nenhum: CLASSE_6CA so tem upstream, ix e pni."""
    (erro,) = erros_de(["64512:673"])
    assert erro.campo == "blocos_v4"
    assert "classe 7" in erro.mensagem


def test_a_large_4_e_recusada():
    """Anunciar somente para um ASN nao tem ramo: o egress implementa as
    funcoes 0, 1, 2 e 3."""
    (erro,) = erros_de(["64512:4:14840"])
    assert "funcao 4" in erro.mensagem


def test_o_1xx_e_recusado_porque_o_consumidor_e_o_import_de_cliente():
    (erro,) = erros_de(["64512:104"])
    assert "1xx" in erro.mensagem


def test_faixa_sem_dono_e_recusada():
    for valor in ("64512:301", "64512:401", "64512:711", "64512:812"):
        (erro,) = erros_de([valor])
        assert "sem dono" in erro.mensagem, valor


def test_escopo_que_o_egress_le_passa():
    assert erros_de(["64512:200", "64512:204", "64512:211", "64512:213"]) == []


def test_escopo_fora_da_tabela_e_recusado():
    (erro,) = erros_de(["64512:205"])
    assert "2xx" in erro.mensagem


def test_6ca_das_classes_implementadas_passa():
    """O 1 e o 9 caem fora da cadeia e nao prependam nada, mas os dois sao
    publicados no PLANO como P1 e como default explicito."""
    assert erros_de(["64512:613", "64512:622", "64512:644",
                     "64512:611", "64512:619"]) == []


def test_6ca_com_digito_sem_ramo_e_recusado():
    (erro,) = erros_de(["64512:615"])
    assert "digito 5" in erro.mensagem


def test_6ca_com_o_digito_0_e_recusado():
    """O PLANO da o 0 do 6CA como escopo, e nenhum ramo o le. No 5PPA o 0 e
    outra historia: la ele entra no CL-NOADV do peer."""
    (erro,) = erros_de(["64512:610"])
    assert "digito 0" in erro.mensagem


def test_informativa_acima_da_faixa_do_plano_e_recusada():
    """plan.FAIXAS fecha a informativa em 9999, e nenhum filtro le acima."""
    for valor in ("64512:10001", "64512:65535"):
        (erro,) = erros_de([valor])
        assert "sem dono" in erro.mensagem, valor


def test_5ppa_com_digito_0_a_4_passa():
    assert erros_de(["64512:5130", "64512:5131", "64512:5134"]) == []


def test_5ppa_com_digito_5_e_recusado():
    (erro,) = erros_de(["64512:5135"])
    assert "digito 5" in erro.mensagem


def test_blackhole_e_manutencao_passam():
    assert erros_de(["64512:666", "64512:667", "64512:9666"]) == []


def test_informativa_de_geografia_passa():
    assert erros_de(["64512:2101", "64512:2001"]) == []


def test_community_de_outro_as_passa():
    """O vocabulario do mundo nao da para conferir, e o bloco existe
    justamente para carregar a tag da operadora."""
    assert erros_de(["15169:12100", "14840:9133"]) == []


def test_cada_familia_marca_o_proprio_campo():
    erros = validate.validar_blocos(
        {"v4": [], "v6": [bloco(prefixo="2804:36b4::/32",
                                communities=["64512:673"])]})
    assert erros[0].campo == "blocos_v6"


def test_o_namespace_da_rede_vale_para_o_bloco_como_para_o_peer():
    """Com asn_politica declarado, o que vale e 65532:673, e nao 64512:673."""
    rede = plan.Rede(asn=264130, politica=65532)
    assert validate.validar_blocos({"v4": [], "v6": []}, rede) == []
    erros = validate.validar_blocos(
        {"v4": [bloco(communities=["65532:673"])], "v6": []}, rede)
    assert "classe 7" in erros[0].mensagem


def test_prefixo_invalido_e_erro_no_campo_da_familia():
    erros = validate.validar_blocos(
        {"v4": [bloco(prefixo="nao-e-cidr")], "v6": []})
    assert erros[0].campo == "blocos_v4"
    assert "CIDR" in erros[0].mensagem


def test_valor_com_tres_dois_pontos_e_recusado_pela_forma():
    """A tabela de faixas le so o primeiro campo, entao um valor torto
    passaria por ela, cairia na lista de standard e viraria uma linha de
    apply community que o equipamento recusa na hora de colar."""
    for valor in ("64512:1:2:3", "64512", "64512:", "a:b"):
        (erro,) = erros_de([valor])
        assert "invalida" in erro.mensagem, valor
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_validate.py -k bloco -v`
Expected: FAIL com `AttributeError: module 'app.validate' has no attribute 'validar_blocos'`

- [ ] **Step 3: Add the readable set and the reason helper**

Acrescente em `app/validate.py`, depois de `_valida_communities`:

```python
# --- blocos proprios --------------------------------------------------

# as acoes do plano que tem ramo em filtro de egress. Sai das tabelas do
# plan.py de proposito: uma acao que ganhe ramo entra aqui sozinha, e nao
# ha segunda lista de verdade para manter em sincronia.
ACOES_LIDAS = frozenset(
    [v for par in plan.NOADV.values() for v in par]
    + list(plan.NOADV_CUST)
    + [v for par in plan.ONLY_NOT.values() for v in par])
CLASSES_6CA_LIDAS = frozenset(plan.CLASSE_6CA.values())
# Os digitos 1 e 9 caem fora da cadeia if/elseif e nao prependam nada, que e
# o mesmo efeito de nao ter community nenhuma. Os dois ficam aceitos porque
# o PLANO publica os dois: o 1 e o P1 explicito, e o 9 e o "default
# explicito, cai no fim da cadeia". O que o documento marca como "ainda sem
# ramo nos filtros de egress" e de 5 a 8, e esses sao recusados.
#
# O digito 0 do 6CA e o caso que sobra, e ele e recusado: o documento o da
# como escopo ("nao anunciar para este destino") e nenhum ramo o le, que e
# a mesma forma do 673 e do large 4:<ASN>. No 5PPA o 0 e outra historia: ali
# ele entra no CL-NOADV do peer e e lido.
DIGITOS_6CA_LIDOS = frozenset((1, 2, 3, 4, 9))
DIGITOS_5PPA_LIDOS = frozenset(range(5))


def _motivo_da_recusa(valor, rede):
    """Por que a community nao serve num bloco proprio, ou None se serve.

    So opina sobre o namespace da rede: community de outro AS passa, porque
    o vocabulario do mundo nao da para conferir e o bloco existe justamente
    para carregar a tag da operadora. Dentro do namespace, a pergunta e uma
    so: algum filtro do gerado le este valor? O que nenhum le vira erro
    aqui, e nao um prefixo que anuncia e nao se comporta como pedido.
    """
    if not valor.startswith(rede.ns + ":"):
        return None
    corpo = valor.split(":", 1)[1]
    if not corpo.isdigit():
        return None
    n = int(corpo)

    # quatro digitos: informativa, ou o alias 5PPA, que e o unico de
    # quatro digitos que carrega acao. A faixa da informativa termina onde o
    # plan.FAIXAS termina, em 9999: o que passa disso nao esta no plano e
    # nenhum filtro le.
    if n >= 1000:
        if not 1000 <= n <= 9999:
            return "faixa sem dono no plano"
        if not 5000 <= n <= 5999:
            return None
        if n % 10 not in DIGITOS_5PPA_LIDOS:
            return "digito %d sem ramo no egress" % (n % 10)
        return None

    if 100 <= n <= 199:
        return ("o 1xx e lido pelo import de cliente, e a rota propria "
                "nao passa por import nenhum: use o local-preference da "
                "propria filtragem de originacao")
    if 200 <= n <= 299:
        if n not in ACOES_LIDAS:
            return "nenhum egress le este 2xx de escopo"
        return None
    if n in (666, 667):
        return None
    if 600 <= n <= 699:
        classe, digito = (n - 600) // 10, n % 10
        if classe not in CLASSES_6CA_LIDAS:
            return ("classe %d sem ramo no egress: o gerado implementa %s"
                    % (classe, ", ".join(str(c) for c in
                                         sorted(CLASSES_6CA_LIDAS))))
        if digito not in DIGITOS_6CA_LIDOS:
            return "digito %d sem ramo no egress" % digito
        return None
    return "faixa sem dono no plano"


def _motivo_da_recusa_large(valor, rede):
    """O mesmo para a large community, que tem tres campos."""
    partes = valor.split(":")
    if len(partes) != 3 or partes[0] != rede.ns or not partes[1].isdigit():
        return None
    n = int(partes[1])
    if n >= 1000:
        return None
    if n <= 3:
        return None
    if n == 4:
        return ("funcao 4 sem ramo no egress: anunciar somente para um ASN "
                "nao esta implementado, so as funcoes 0, 1, 2 e 3")
    return "funcao %d sem ramo no egress" % n


def _motivo_da_community(valor, rede):
    """A forma da large tem tres campos, e a da standard tem dois."""
    if len(valor.split(":")) == 3:
        return _motivo_da_recusa_large(valor, rede)
    return _motivo_da_recusa(valor, rede)


def _forma_ok(valor):
    """A forma da community: ASN:VALOR ou ASN:V1:V2, com campo numerico.

    Sem esta checagem um valor com tres dois-pontos passa pela tabela de
    faixas, que le so o primeiro campo, chega ao separa_communities, cai na
    lista de standard e vira uma linha de `apply community` que o
    equipamento recusa na hora de colar. As duas funcoes de forma ja
    existem para a CL-PEER do peer, e a checagem aqui e a mesma.
    """
    return community_ok(valor) or large_community_ok(valor)


def validar_blocos(blocos, rede=None):
    """Os erros das duas listas de prefixos do proprio AS.

    O campo do erro e o da familia, que e o nome da textarea no
    formulario, para a tela marcar a caixa certa em vez de avisar solto.
    """
    rede = rede if rede is not None else plan.Rede()
    erros = []
    for fam in plan.FAMILIAS:
        campo = "blocos_%s" % fam
        for bloco in blocos.get(fam) or []:
            if not _cidr_ok(bloco.prefixo):
                erros.append(Erro(campo, "prefixo invalido: %s (esperado CIDR)"
                                  % bloco.prefixo))
            for valor in bloco.communities or []:
                if not _forma_ok(valor):
                    erros.append(Erro(
                        campo, "community invalida: %s (esperado ASN:VALOR ou "
                        "ASN:V1:V2)" % valor))
                    continue
                motivo = _motivo_da_community(valor, rede)
                if motivo:
                    erros.append(Erro(campo, "%s: %s" % (valor, motivo)))
    return erros
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_validate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/validate.py tests/test_validate.py
git commit -m "Community que nenhum filtro le nao entra no bloco proprio"
```

---

### Task 4: O fragmento de originação

**Files:**
- Create: `templates/blocos.txt.j2`
- Modify: `app/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `plan.nome_origem`, `plan.endereco`, `plan.mascara`, `plan.separa_communities`, `plan.conjunto_de`, `plan.PREFERENCE_ORIGEM`, `plan.LP_ORIGEM` (Task 2) e `peers.Bloco` (Task 1).
- Produces:
  - `render.render_blocos(blocos, rede=None) -> str`
  - `render.escrever_blocos(blocos, rede=None) -> Path`, gravando `out/blocos.txt`

- [ ] **Step 1: Write the failing tests**

Acrescente ao fim de `tests/test_render.py`. O arquivo já importa `render`; acrescente `from app.peers import Bloco` junto do `from app.peers import Peer` que existe na linha 123.

```python
def bloco(prefixo, communities=None):
    return Bloco(prefixo=prefixo, communities=list(communities or []))


def dois_blocos():
    return {"v4": [bloco("38.252.64.0/22", ["64512:613", "64512:621",
                                            "15169:12100"]),
                   bloco("38.252.64.0/24", ["64512:211"])],
            "v6": [bloco("2804:36b4::/32")]}


def test_blocos_e_ascii():
    assert render.render_blocos(dois_blocos()).isascii()


def test_a_estatica_ancora_com_preference_250():
    texto = render.render_blocos(dois_blocos())
    assert ("ip route-static 38.252.64.0 255.255.252.0 NULL0 "
            "preference 250") in texto
    assert "ipv6 route-static 2804:36b4:: 32 NULL0 preference 250" in texto


def test_o_filtro_leva_o_lp_e_o_1000_gerado():
    texto = render.render_blocos(dois_blocos())
    assert "xpl route-filter ORIGEM-38-252-64-0_22" in texto
    assert " apply local-preference 900" in texto
    assert (" apply community {64512:1000, 64512:613, 64512:621, "
            "15169:12100} overwrite") in texto


def test_a_comunidade_de_outro_as_viaja_com_a_lista():
    assert "15169:12100" in render.render_blocos(dois_blocos())


def test_lista_vazia_sai_com_o_1000_e_sem_large():
    texto = render.render_blocos({"v4": [bloco("38.252.64.0/22")], "v6": []})
    assert " apply community {64512:1000} overwrite" in texto
    assert "apply large-community" not in texto


def test_a_large_sai_em_linha_propria():
    texto = render.render_blocos(
        {"v4": [bloco("38.252.64.0/22", ["64512:613", "64512:0:14840"])],
         "v6": []})
    assert " apply community {64512:1000, 64512:613} overwrite" in texto
    assert " apply large-community {64512:0:14840} overwrite" in texto


def test_o_filtro_fecha_em_break():
    texto = render.render_blocos(dois_blocos())
    corpo = texto.split("xpl route-filter ORIGEM-38-252-64-0_22")[1].split(
        "end-filter")[0]
    assert corpo.strip().endswith("break")
    assert "finish" not in corpo


def test_as_linhas_network_vao_no_fim_de_cada_familia():
    texto = render.render_blocos(dois_blocos())
    assert (" network 38.252.64.0 255.255.252.0 route-filter "
            "ORIGEM-38-252-64-0_22") in texto
    assert (" network 38.252.64.0 255.255.255.0 route-filter "
            "ORIGEM-38-252-64-0_24") in texto
    assert " network 2804:36b4:: 32 route-filter ORIGEM-2804-36b4_32" in texto


def test_sem_bloco_nao_sai_estatica_nem_filtro():
    """A varredura e pelos comandos, e nao pelas palavras: o cabecalho do
    arquivo cita "network" na frase que diz onde as linhas dele vao."""
    texto = render.render_blocos({"v4": [], "v6": []})
    assert "ip route-static" not in texto
    assert "ipv6 route-static" not in texto
    assert "xpl route-filter ORIGEM-" not in texto
    assert " route-filter ORIGEM-" not in texto


def test_o_bloco_traz_a_estatica_o_filtro_e_o_network_do_mesmo_prefixo():
    texto = render.render_blocos({"v4": [bloco("38.252.64.0/24")], "v6": []})
    for pedaco in ("ip route-static 38.252.64.0 255.255.255.0 NULL0",
                   "xpl route-filter ORIGEM-38-252-64-0_24",
                   "network 38.252.64.0 255.255.255.0 route-filter "
                   "ORIGEM-38-252-64-0_24"):
        assert pedaco in texto, pedaco


def test_o_bloco_do_asn_declarado_usa_o_namespace_dele():
    texto = render.render_blocos({"v4": [bloco("38.252.64.0/22")], "v6": []},
                                 rede=plan.Rede(asn=264130, politica=65532))
    assert "65532:1000" in texto
    assert "64512:1000" not in texto


def test_escrever_blocos_grava_em_out(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "OUT", tmp_path)
    destino = render.escrever_blocos(dois_blocos())
    assert destino == tmp_path / "blocos.txt"
    assert destino.read_text(encoding="ascii") == render.render_blocos(
        dois_blocos())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_render.py -k blocos -v`
Expected: FAIL com `AttributeError: module 'app.render' has no attribute 'render_blocos'`

- [ ] **Step 3: Write the template**

Crie `templates/blocos.txt.j2`:

```
# gerado por bgpgen - nao editar a mao
# blocos proprios do AS{{ plan.ASN }}
# fonte: peers.yaml, secao blocos
# fora da view do bgp: estaticas de ancoragem e filtros de originacao.
# as linhas "network" de cada familia vao no fim deste arquivo.

{% for fam in plan.FAMILIAS %}
{% for b in blocos[fam] %}
{% set nome = plan.nome_origem(b.prefixo) %}
{% set std, lg = plan.separa_communities(b.communities) %}
{% set kw = "ipv6 route-static" if fam == "v6" else "ip route-static" %}
{{ kw }} {{ plan.endereco(b.prefixo) }} {{ plan.mascara(b.prefixo) }} NULL0 preference {{ plan.PREFERENCE_ORIGEM }}

xpl route-filter {{ nome }}
 apply local-preference {{ plan.LP_ORIGEM }}
 apply community {{ plan.conjunto_de([plan.c(1000)] + std) }} overwrite
{% if lg %}
 apply large-community {{ plan.conjunto_de(lg) }} overwrite
{% endif %}
 break
end-filter

{% endfor %}
{% endfor %}
{%- for fam in plan.FAMILIAS if blocos[fam] %}
# --- dentro de {{ "ipv6-family unicast" if fam == "v6" else "ipv4-family unicast" }} ---
{% for b in blocos[fam] %}
 network {{ plan.endereco(b.prefixo) }} {{ plan.mascara(b.prefixo) }} route-filter {{ plan.nome_origem(b.prefixo) }}
{% endfor %}
{% endfor %}
```

Cuidados de Jinja que o resto do projeto já usa: o ambiente roda com `trim_blocks`, `lstrip_blocks` e `keep_trailing_newline`. O `trim_blocks` já come a quebra de linha que segue uma tag de bloco, então o `{%-` do segundo laço não tem efeito visível: ele fica ali por simetria com o laço de cima, e não porque controle branco. A linha em branco que separa o último filtro do comentário da família vem do branco que fecha o corpo do primeiro laço.

- [ ] **Step 4: Add the render functions**

Em `app/render.py`, depois de `render_remove`:

```python
def render_blocos(blocos, rede=None):
    """O bloco dos prefixos proprios: estaticas, filtros e as linhas network.

    Um arquivo so com as duas partes, como os blocos de peer: o operador
    cola o que esta fora da view do bgp e o que esta dentro, na ordem em
    que aparecem.
    """
    return ambiente(rede).get_template("blocos.txt.j2").render(blocos=blocos)


def escrever_blocos(blocos, rede=None):
    OUT.mkdir(parents=True, exist_ok=True)
    destino = OUT / "blocos.txt"
    destino.write_text(render_blocos(blocos, rede=rede), encoding="ascii")
    return destino
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_render.py -v`
Expected: PASS. Se o `test_golden_do_bloco_base` quebrar, é porque o template base foi tocado sem querer: nada nesta tarefa encosta em `base.txt.j2`.

- [ ] **Step 6: Commit**

```bash
git add templates/blocos.txt.j2 app/render.py tests/test_render.py
git commit -m "O bloco proprio sai em estatica, filtro e linha network"
```

---

### Task 5: O `EXPORT-SANITY` novo

**Files:**
- Modify: `templates/base.txt.j2:150-160`
- Modify: `tests/golden/_base.txt`
- Modify: `tests/test_render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `AP-LOCAL-ORIGIN`, que já existe em `base.txt.j2:55` com `regular ^$`.
- Produces: nada que outra tarefa consuma. Esta tarefa muda o bloco base para todos.

- [ ] **Step 1: Write the failing tests**

Substitua o corpo de `tests/test_render.py:75-79` (`test_export_sanity_fecha_em_break`) e acrescente os novos logo abaixo dele:

```python
def test_export_sanity_fecha_em_break():
    texto = render.render_base()
    corpo = texto.split("xpl route-filter EXPORT-SANITY")[1].split("end-filter")[0]
    assert corpo.strip().endswith("break")
    assert "finish" not in corpo


def test_export_sanity_barra_a_infra_interna_antes_de_tudo():
    """O 1900 e o 1901 nunca saem do AS. Ate agora quem os barrava era a
    ausencia de marca de origem, e isso deixa de bastar quando a rota
    originada localmente passa a dispensar a marca."""
    corpo = render.render_base().split(
        "xpl route-filter EXPORT-SANITY")[1].split("end-filter")[0]
    assert "64512:1900" in corpo
    assert "64512:1901" in corpo
    assert corpo.index("64512:1900") < corpo.index("AP-LOCAL-ORIGIN")


def test_export_sanity_dispensa_a_marca_da_rota_originada_aqui():
    corpo = render.render_base().split(
        "xpl route-filter EXPORT-SANITY")[1].split("end-filter")[0]
    assert "if not as-path matches-any AP-LOCAL-ORIGIN" in corpo
    assert "if not community matches-any CL-ORIGEM-ANUNCIAVEL" in corpo


def test_a_dispensa_do_path_vazio_usa_a_lista_que_ja_existe():
    """AP-LOCAL-ORIGIN ja e a definicao de "rota originada localmente" no
    IMPORT-SANITY. Uma segunda lista com o mesmo conteudo seria duas
    verdades sobre a mesma coisa."""
    base = render.render_base()
    assert base.count("xpl as-path-list AP-LOCAL-ORIGIN") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_render.py -k export_sanity -v`
Expected: FAIL em `test_export_sanity_barra_a_infra_interna_antes_de_tudo`, com `AssertionError: assert '64512:1900' in ...`

- [ ] **Step 3: Rewrite the filter in `base.txt.j2`**

Substitua o bloco que hoje começa em `xpl route-filter EXPORT-SANITY` e termina no `end-filter` dele por:

```
xpl route-filter EXPORT-SANITY
 {# infra interna nunca sai do AS, nem como rota propria. Ate agora quem a
    barrava era a ausencia de marca de origem, e a dispensa abaixo tira
    isso de cena: sem este ramo, um prefixo proprio marcado 1900 sairia
    por upstream, IX e PNI, e so o egress de cliente continuaria
    recusando. #}
 if community matches-any {{ plan.conjunto(plan.c(1900), plan.c(1901)) }} then
  refuse
 endif
 {# path vazio e rota originada aqui: nao precisa de marca. A lista e a
    mesma que o IMPORT-SANITY usa para recusar path vazio vindo de eBGP,
    entao "originada localmente" tem uma definicao so nos dois lados.
    Isto depende de ninguem colocar rota local com path vazio na RIB por
    import-route nem por aggregate. #}
 if not as-path matches-any AP-LOCAL-ORIGIN then
  if not community matches-any CL-ORIGEM-ANUNCIAVEL then
   refuse
  endif
 endif
 {# break incondicional: mesma regra do IMPORT-SANITY #}
 break
end-filter
```

- [ ] **Step 4: Regenerate the base golden**

```bash
python -c "from app import render; open('tests/golden/_base.txt','w',encoding='ascii').write(render.render_base())"
git diff --stat tests/golden/_base.txt
```

Expected: o diff do `_base.txt` mostra só o bloco do `EXPORT-SANITY`. Se aparecer qualquer outra linha, o template base foi tocado além do previsto: reverta e refaça o passo.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_render.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/base.txt.j2 tests/golden/_base.txt tests/test_render.py
git commit -m "A rota originada aqui dispensa a marca, e a infra interna ganha barreira"
```

---

### Task 6: O remover dos blocos

**Files:**
- Create: `templates/remover_blocos.txt.j2`
- Modify: `app/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `plan.nome_origem`, `plan.endereco`, `plan.mascara` (Task 2), `peers.Bloco` (Task 1).
- Produces: `render.render_remove_blocos(blocos, rede=None) -> str`

- [ ] **Step 1: Write the failing tests**

Acrescente ao fim de `tests/test_render.py`. O helper `bloco(prefixo, communities=None)` já existe no arquivo, criado pela Task 4: use-o e não o redefina.

```python
def test_remover_traz_o_undo_na_ordem_que_o_vrp_aceita():
    """O `undo network` vem antes do `undo xpl route-filter`: objeto em uso
    nao e apagavel, e a referencia sai primeiro."""
    texto = render.render_remove_blocos({"v4": [bloco("38.252.64.0/22")],
                                         "v6": []})
    ordem = [texto.index("undo network 38.252.64.0 255.255.252.0"),
             texto.index("undo xpl route-filter ORIGEM-38-252-64-0_22"),
             texto.index("undo ip route-static 38.252.64.0 255.255.252.0")]
    assert ordem == sorted(ordem)


def test_remover_avisa_que_o_caminho_de_tirar_so_o_tratamento_e_outro():
    texto = render.render_remove_blocos({"v4": [bloco("38.252.64.0/22")],
                                         "v6": []})
    assert "esvazie" in texto.lower()


def test_remover_do_v6_usa_os_comandos_de_v6():
    texto = render.render_remove_blocos({"v4": [],
                                         "v6": [bloco("2804:36b4::/32")]})
    assert "undo network 2804:36b4:: 32" in texto
    assert "undo ipv6 route-static 2804:36b4:: 32 NULL0" in texto


def test_remover_sem_bloco_nao_traz_undo():
    assert "undo " not in render.render_remove_blocos({"v4": [], "v6": []})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_render.py -k remover -v`
Expected: FAIL com `AttributeError: module 'app.render' has no attribute 'render_remove_blocos'`

- [ ] **Step 3: Write the template**

Crie `templates/remover_blocos.txt.j2`:

```
!- gerado por bgpgen - nao editar a mao
!- remocao dos blocos proprios do AS{{ plan.ASN }}
!- Desligar o prefixo e o que sai abaixo. Para tirar apenas o tratamento
!- manual e deixar o prefixo anunciado, esvazie a lista dele na tela e
!- cole o bloco de originacao de novo: o filtro continua existindo com o
!- 1000 e mais nada.
!- A ordem importa: o filtro nao pode ser apagado enquanto o network o
!- referencia, e a estatica sai por ultimo para o prefixo nao sumir da
!- tabela com o network ainda apontando para ela.

{% for fam in plan.FAMILIAS %}
{% for b in blocos[fam] %}
{% set kw = "ipv6 route-static" if fam == "v6" else "ip route-static" %}
undo network {{ plan.endereco(b.prefixo) }} {{ plan.mascara(b.prefixo) }}
undo xpl route-filter {{ plan.nome_origem(b.prefixo) }}
undo {{ kw }} {{ plan.endereco(b.prefixo) }} {{ plan.mascara(b.prefixo) }} NULL0

{% endfor %}
{% endfor %}
```

- [ ] **Step 4: Add the render function**

Em `app/render.py`, depois de `render_blocos`:

```python
def render_remove_blocos(blocos, rede=None):
    return ambiente(rede).get_template("remover_blocos.txt.j2").render(
        blocos=blocos)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_render.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/remover_blocos.txt.j2 app/render.py tests/test_render.py
git commit -m "O remover do bloco proprio derruba na ordem que o filtro exige"
```

---

### Task 7: A consulta e a reconsulta

**Files:**
- Modify: `app/prefixes.py`
- Modify: `app/app.py`
- Test: `tests/test_prefixes.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `peers_mod.Bloco`, `peers_mod.carregar_blocos`, `peers_mod.gravar_blocos`, `peers_mod.mesclar_blocos` (Task 1), `validate.validar_blocos` (Task 3), `plan.nome_origem` (Task 2).
- Produces:
  - `prefixes.coletar(asn, token, familias=("v4", "v6"), forcar=False, etiqueta=None) -> dict[str, list[str]]`
  - `app._blocos_do_formulario(dados) -> dict[str, list[Bloco]]`
  - `app._texto_blocos(blocos, ausentes=()) -> dict[str, str]`
  - Rota `POST /blocos/bgpq4` e rota `POST /blocos`
  - `_contexto` com as chaves novas `blocos`, `blocos_ausentes`, `texto_blocos`, `saida_blocos`, `saida_blocos_remover`

- [ ] **Step 1: Write the failing test for the query label**

Acrescente ao fim de `tests/test_prefixes.py`:

```python
def test_o_comando_aceita_etiqueta_propria(fake_bgpq4, monkeypatch):
    """O bloco proprio nao e lista de cliente: o rotulo da consulta diz o
    que ela e, e o cache continua sendo o mesmo, porque a consulta ao IRR
    nao depende do rotulo."""
    vistos = []
    monkeypatch.setattr(prefixes, "_rodar", lambda cmd: vistos.append(cmd) or [])
    prefixes.coletar(264130, "264130", forcar=True, etiqueta="ORIGEM")
    assert vistos[0][vistos[0].index("-l") + 1] == "ORIGEM-V4"
    assert vistos[1][vistos[1].index("-l") + 1] == "ORIGEM-V6"


def test_a_etiqueta_nao_muda_a_chave_do_cache(fake_bgpq4):
    prefixes.coletar(264130, "264130", etiqueta="ORIGEM")
    assert (prefixes.CACHE / "264130.json").exists()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_prefixes.py -k etiqueta -v`
Expected: FAIL com `TypeError: coletar() got an unexpected keyword argument 'etiqueta'`

- [ ] **Step 3: Add the parameter**

Em `app/prefixes.py`, troque `_comando` por:

```python
def _comando(asn, token, fam, etiqueta=None):
    """Monta a consulta.

    -F '%n/%l ' devolve CIDR puro, tudo numa linha separado por espaco.

    -A agrega, e o que ele agrega e irmao de mesmo tamanho virando pai: o
    agregado cobre exatamente o que o IRR tem, nunca buraco. Em AS3333 os
    /23 de 193.0.20.0 e 193.0.22.0 saem como 193.0.20.0/22, e os de 10.0
    e 12.0 continuam separados, porque o /22 entre eles nao esta
    registrado. Quem cobre buraco e o -R/-r, que marca um prefixo
    existente como faixa sem conferir se os mais especificos existem
    (sx_radix_node_refine, no sx_prefix.c do bgpq4 1.12).

    O -A repete uma entrada quando o agregado tambem e objeto registrado:
    o /32 v6 do AS264130 veio duas vezes. O _normalizar tira a repeticao.

    O rotulo do -l e so um nome para o objeto que o bgpq4 descreve, e com
    -F '%n/%l ' ele nem aparece na saida. A etiqueta existe para o bloco
    proprio nao sair chamado de PL-CUST; o cache nao a distingue, porque a
    resposta e a mesma.
    """
    rotulo = "%s-%s" % (etiqueta or ("PL-CUST-%s" % token), fam.upper())
    return ["bgpq4", "-4" if fam == "v4" else "-6", "-A", "-F", "%n/%l ",
            "-h", SERVIDOR_IRR, "-l", rotulo, "AS%d" % asn]
```

E em `coletar`, assine e repasse:

```python
def coletar(asn, token, familias=("v4", "v6"), forcar=False, etiqueta=None):
    if not forcar:
        em_cache = do_cache(asn)
        if em_cache is not None:
            return em_cache

    prefixos = {}
    for fam in familias:
        prefixos[fam] = _normalizar(_rodar(_comando(asn, token, fam,
                                                    etiqueta=etiqueta)))

    CACHE.mkdir(parents=True, exist_ok=True)
    _caminho(asn).write_text(
        json.dumps({"asn": asn, "versao": CACHE_VERSAO,
                    "coletado_em": time.time(), "prefixos": prefixos},
                   indent=2),
        encoding="utf-8")
    return prefixos
```

O cache continua com chave só no ASN. A consulta ao mesmo ASN é a mesma, e um peer que tenha o ASN da própria rede e o cadastro de blocos podem compartilhar a entrada sem prejuízo.

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/test_prefixes.py -v`
Expected: PASS, incluindo `test_o_comando_monta_os_argumentos`, que continua esperando `PL-CUST-TESTOK-V4`.

- [ ] **Step 5: Write the failing tests for the form helpers and the merge**

Acrescente ao fim de `tests/test_app.py`:

```python
BLOCOS = {
    "blocos_v4": "38.252.64.0/22  64512:613 64512:621\n38.252.64.0/24  64512:211",
    "blocos_v6": "",
}


def test_o_formulario_le_uma_linha_por_prefixo(cliente):
    blocos = mod._blocos_do_formulario(BLOCOS)
    assert [(b.prefixo, b.communities) for b in blocos["v4"]] == [
        ("38.252.64.0/22", ["64512:613", "64512:621"]),
        ("38.252.64.0/24", ["64512:211"])]
    assert blocos["v6"] == []


def test_linha_com_dois_pontos_e_ignorada(cliente):
    """E o que permite guardar um prefixo fora do ar sem perder o
    tratamento escrito nele."""
    blocos = mod._blocos_do_formulario(
        {"blocos_v4": "!- 38.252.64.0/24 64512:211\n38.252.64.0/22",
         "blocos_v6": ""})
    assert [b.prefixo for b in blocos["v4"]] == ["38.252.64.0/22"]


def test_a_marca_do_ausente_nao_vira_community(cliente):
    blocos = mod._blocos_do_formulario(
        {"blocos_v4": "38.252.66.0/24 64512:211  !- nao veio na consulta",
         "blocos_v6": ""})
    assert blocos["v4"][0].communities == ["64512:211"]


def test_o_texto_do_formulario_volta_marcado(cliente):
    salvo = peers_mod.Bloco(prefixo="38.252.66.0/24", communities=["64512:211"])
    texto = mod._texto_blocos({"v4": [salvo], "v6": []}, ausentes=[salvo])
    assert texto["v4"] == "38.252.66.0/24 64512:211  !- nao veio na consulta ao IRR"


def test_salvar_blocos_grava_no_yaml(cliente):
    r = cliente.post("/blocos", data=BLOCOS)
    assert r.status_code == 200
    lido = peers_mod.carregar_blocos(mod.PEERS_YAML)
    assert [b.prefixo for b in lido["v4"]] == ["38.252.64.0/22",
                                               "38.252.64.0/24"]


def test_salvar_blocos_com_community_que_ninguem_le_nao_grava(cliente):
    r = cliente.post("/blocos", data={"blocos_v4": "38.252.64.0/22 64512:673",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    assert "classe 7" in r.text
    assert peers_mod.carregar_blocos(mod.PEERS_YAML) == {"v4": [], "v6": []}


def test_prefixo_fora_do_irr_salva_igual(cliente):
    """O gate e a consulta, e nao a verdade: o operador responde pelo que
    assume, e um prefixo digitado a mao nao pode ser recusado."""
    r = cliente.post("/blocos", data={"blocos_v4": "203.0.113.0/24",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    assert [b.prefixo for b in
            peers_mod.carregar_blocos(mod.PEERS_YAML)["v4"]] == ["203.0.113.0/24"]


# Os tres testes que afirmam sobre a lista mesclada na TELA
# ("test_a_reconsulta_preserva_o_tratamento_do_prefixo_que_ficou",
# "test_a_reconsulta_marca_o_prefixo_que_sumiu" e
# "test_bgpq4_fora_do_ar_nao_perde_a_lista_do_operador") vivem no brief da
# Task 8, que e a tarefa que acrescenta a secao ao pagina.html. Aqui ficam
# os que afirmam sobre os helpers, sobre o YAML e sobre o contexto, que e o
# que esta tarefa entrega.


def test_a_reconsulta_nao_grava_o_yaml(cliente, fake_bgpq4):
    """Quem grava e o salvar: a consulta so redesenha a tela."""
    salvo = {"blocos_v4": "203.0.113.0/24 64512:211", "blocos_v6": ""}
    cliente.post("/blocos", data=salvo)
    cliente.post("/blocos/bgpq4", data=salvo)
    lido = peers_mod.carregar_blocos(mod.PEERS_YAML)
    assert [b.prefixo for b in lido["v4"]] == ["203.0.113.0/24"]
    assert "45.169.232.0/22" not in [
        b.prefixo for b in lido["v4"]], "a consulta nao pode ter gravado"


```

O teste do `bgpq4` fora do ar tambem afirma sobre a tela e vive no brief da Task 8, junto dos outros dois.

Este é o ultimo passo de codigo desta tarefa. A suite tem que fechar verde aqui, e fecha: os tres que afirmam sobre a lista mesclada na tela saem do arquivo junto com os outros.

O fixture `fake_bgpq4` está em `tests/test_prefixes.py`; para usá-lo aqui, mova-o para `tests/conftest.py` (crie o arquivo) e apague a definição de `test_prefixes.py`, deixando os dois arquivos de teste usando o mesmo. O fixture já faz `monkeypatch.setattr(prefixes, "CACHE", tmp_path / ".cache")`, que é o que o `test_app.py` precisa.

- [ ] **Step 6: Run them to verify they fail**

Run: `pytest tests/test_app.py -k "bloco or reconsulta or bgpq4_fora" -v`
Expected: FAIL com `AttributeError: module 'app.app' has no attribute '_blocos_do_formulario'`

- [ ] **Step 7: Add the form helpers to `app/app.py`**

Depois de `_usados`:

```python
def _blocos_do_formulario(dados):
    """As duas listas do bloco proprio: uma linha por prefixo.

    O formato e `<cidr> community community ...`. Linha que comeca com
    `!-` fica fora: e o que permite guardar um prefixo fora do ar sem
    perder o tratamento escrito nele. O `!-` no fim da linha e a marca do
    que sumiu da consulta, e o salvamento ignora.
    """
    blocos = {}
    for fam in plan.FAMILIAS:
        blocos[fam] = []
        for linha in _linhas(dados, "blocos_%s" % fam):
            if linha.startswith("!-"):
                continue
            pedacos = linha.split("!-")[0].split()
            if not pedacos:
                continue
            blocos[fam].append(Bloco(prefixo=pedacos[0],
                                     communities=pedacos[1:]))
    return blocos


def _texto_blocos(blocos, ausentes=()):
    """O texto das duas textareas, com a marca de quem sumiu da consulta."""
    marcados = {b.prefixo for b in ausentes}
    saida = {}
    for fam in plan.FAMILIAS:
        linhas = []
        for b in blocos.get(fam) or []:
            corpo = " ".join([b.prefixo] + list(b.communities))
            if b.prefixo in marcados:
                corpo += "  !- nao veio na consulta ao IRR"
            linhas.append(corpo)
        saida[fam] = "\n".join(linhas)
    return saida
```

O `from app.peers import Peer, Grupo` da linha 15 passa a incluir `Bloco`:

```python
from app.peers import Peer, Grupo, Bloco
```

- [ ] **Step 8: Add the two routes**

Depois da rota `consultar_bgpq4`:

```python
@app.post("/blocos", response_class=HTMLResponse)
async def salvar_blocos(request: Request):
    dados = dict(await request.form())
    rede_atual = rede()
    blocos = _blocos_do_formulario(dados)
    erros = validate.validar_blocos(blocos, rede_atual)
    if erros:
        return templates.TemplateResponse(
            request, "pagina.html",
            _contexto(request, erros=erros, blocos=blocos))
    peers_mod.gravar_blocos(blocos, PEERS_YAML)
    return templates.TemplateResponse(request, "pagina.html",
                                      _contexto(request, blocos=blocos))


@app.post("/blocos/bgpq4", response_class=HTMLResponse)
async def consultar_blocos(request: Request, forcar: int = 0):
    """Consulta o IRR no ASN da propria rede e redesenha a tela.

    A base da mesclagem e o que veio no formulario, e nao o que esta no
    arquivo: o operador pode ter mexido numa linha antes de consultar, e o
    POST que consulta nao grava nada. O ausente volta no fim da lista e
    marcado, e o que o operador fizer com ele e no salvar.
    """
    dados = dict(await request.form())
    rede_atual = rede()
    blocos = _blocos_do_formulario(dados)
    ausentes = {}
    erros = []
    try:
        consulta = prefixes.coletar(rede_atual.asn, rede_atual.ASN,
                                    forcar=bool(forcar), etiqueta="ORIGEM")
    except (RuntimeError, ValueError) as exc:
        erros = [validate.Erro("blocos_v4", str(exc)),
                 validate.Erro("blocos_v6", str(exc))]
    else:
        for fam in plan.FAMILIAS:
            blocos[fam], ausentes[fam] = peers_mod.mesclar_blocos(
                blocos[fam], consulta.get(fam) or [])
    return templates.TemplateResponse(
        request, "pagina.html",
        _contexto(request, erros=erros, blocos=blocos, blocos_ausentes=ausentes))
```

- [ ] **Step 9: Extend `_contexto`**

Na assinatura de `_contexto`, acrescente `blocos=None` e `blocos_ausentes=None`. No corpo, antes do `return`:

```python
    blocos = blocos if blocos is not None else peers_mod.carregar_blocos(PEERS_YAML)
    ausentes = blocos_ausentes or {}
    tem_bloco = any(blocos.get(fam) for fam in plan.FAMILIAS)
```

E nas chaves do dicionário:

```python
        "blocos": blocos,
        # a marca do ausente entra no proprio texto da textarea, e nao como
        # uma lista a parte: a tela nao tem onde mostrar duas coisas para o
        # mesmo prefixo, e o operador edita o texto.
        "texto_blocos": _texto_blocos(blocos, ausentes.get("v4", [])
                                      + ausentes.get("v6", [])),
        # a saida e barata de montar e so aparece quando ha bloco: um
        # `if` no template para economizar duas chamadas aqui seria o
        # tipo de economia que esconde o caso vazio.
        "saida_blocos": render.render_blocos(blocos, rede_atual) if tem_bloco else None,
        "saida_blocos_remover": (render.render_remove_blocos(blocos, rede_atual)
                                 if tem_bloco else None),
```

Hmm, `ausentes` como um set de prefixos por família — mas o mesmo prefixo pode existir em v4 e v6? Não, um mesmo CIDR não é das duas famílias. Então um set de prefixos serve.

- [ ] **Step 10: Run the tests to verify they pass**

Run: `pytest -v`
Expected: PASS. A rota `/blocos` já funciona mesmo sem a seção na página: o POST responde com a página, e o teste olha o arquivo e o texto.

- [ ] **Step 11: Commit**

```bash
git add app/prefixes.py app/app.py tests/conftest.py tests/test_prefixes.py tests/test_app.py
git commit -m "A consulta do bloco casa por prefixo e preserva o tratamento"
```

---

### Task 8: A seção na página

**Files:**
- Modify: `templates/pagina.html`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: as chaves do `_contexto` que a Task 7 produz, `blocos`, `texto_blocos`, `saida_blocos` e `saida_blocos_remover`. Não existe chave `ausentes`: a marca do prefixo que sumiu já vem dentro do `texto_blocos`, e `blocos_ausentes` é o parâmetro do `_contexto`, não uma chave do dicionário.
- Produces: nada que outra tarefa consuma.
- Herda três testes da Task 7, que afirmam sobre a lista mesclada na tela e não tinham como passar antes desta seção existir. Eles estão no bloco de testes do Step 1.

- [ ] **Step 1: Write the failing tests**

Acrescente ao fim de `tests/test_app.py`. A constante `BLOCOS`, no topo das adições da Task 7, e o fixture `fake_bgpq4`, que a Task 7 moveu para `tests/conftest.py`, já existem: use-os e não os redefina.

```python
def test_a_pagina_tem_a_secao_dos_blocos(cliente):
    r = cliente.get("/")
    assert 'id="blocos"' in r.text
    assert 'name="blocos_v4"' in r.text
    assert 'name="blocos_v6"' in r.text
    assert 'action="/blocos"' in r.text
    assert 'action="/blocos/bgpq4"' in r.text


def test_a_secao_mostra_o_que_esta_salvo(cliente):
    """A textarea sai com um espaco entre os campos, e nao com os dois que
    o operador pode ter digitado: separador de espaco no texto e do
    formulario, e nao do formato."""
    cliente.post("/blocos", data=BLOCOS)
    r = cliente.get("/")
    assert "38.252.64.0/22 64512:613 64512:621" in r.text
    assert "38.252.64.0/24 64512:211" in r.text


def test_a_secao_mostra_a_saida_depois_de_salvar(cliente):
    r = cliente.post("/blocos", data=BLOCOS)
    assert "xpl route-filter ORIGEM-38-252-64-0_22" in r.text
    assert "undo xpl route-filter ORIGEM-38-252-64-0_22" in r.text


def test_o_botao_de_consultar_manda_o_forcar(cliente):
    r = cliente.get("/")
    assert "/blocos/bgpq4?forcar=1" in r.text


def test_a_secao_nao_quebra_a_pagina_sem_bloco(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert 'id="blocos"' in r.text


# Os tres que vieram da Task 7. Eles afirmam sobre a lista mesclada na tela,
# e a tela so a mostra a partir daqui.

def test_a_reconsulta_preserva_o_tratamento_do_prefixo_que_ficou(
        cliente, fake_bgpq4):
    """O bgpq4 de mentira devolve 45.169.232.0/22 e 45.169.236.0/23 em v4.
    O primeiro ja estava salvo com tratamento, e o segundo e novo."""
    salvo = {"blocos_v4": "45.169.232.0/22  64512:613", "blocos_v6": ""}
    cliente.post("/blocos", data=salvo)
    r = cliente.post("/blocos/bgpq4", data=salvo)
    assert r.status_code == 200
    assert "45.169.232.0/22 64512:613" in r.text
    assert "45.169.236.0/23" in r.text


def test_a_reconsulta_marca_o_prefixo_que_sumiu(cliente, fake_bgpq4):
    salvo = {"blocos_v4": "203.0.113.0/24 64512:211", "blocos_v6": ""}
    cliente.post("/blocos", data=salvo)
    r = cliente.post("/blocos/bgpq4", data=salvo)
    assert "nao veio na consulta ao IRR" in r.text
    assert "203.0.113.0/24 64512:211" in r.text


def test_bgpq4_fora_do_ar_nao_perde_a_lista_do_operador(cliente,
                                                        monkeypatch):
    def explodir(*a, **k):
        raise RuntimeError("bgpq4 nao esta no PATH: e dependencia de execucao")

    monkeypatch.setattr(prefixes, "coletar", explodir)
    r = cliente.post("/blocos/bgpq4", data=BLOCOS)
    assert r.status_code == 200
    assert "bgpq4" in r.text
    assert "38.252.64.0/22" in r.text
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_app.py -k secao -v`
Expected: FAIL com `AssertionError: assert 'id="blocos"' in ...`

- [ ] **Step 3: Add the section to `pagina.html`**

O `</div>` da linha 622 fecha o `<div class="linha">`. A seção nova entra logo depois dele, fora das duas colunas, para não virar uma terceira coluna do layout:

```html
<section id="blocos" class="painel">
 <h2>prefixos proprios de AS{{ plan.ASN }}</h2>
 <div class="painel-corpo">
  <p class="dica">Uma linha por prefixo, no formato <code>&lt;cidr&gt; community community ...</code>. Linha que comeca com <code>!-</code> e um prefixo fora de servico: ele fica no cadastro com o tratamento, e nao sai em configuracao nenhuma.</p>
  <form method="post" action="/blocos">
   {% for fam in ["v4", "v6"] %}
   <label for="blocos_{{ fam }}">{{ fam }}</label>
   <textarea id="blocos_{{ fam }}" name="blocos_{{ fam }}" rows="6" spellcheck="false">{{ texto_blocos[fam] }}</textarea>
   {% endfor %}
   <div class="acoes">
    <button class="btn" type="submit">salvar blocos</button>
    <button class="btn btn-fantasma" type="submit" formaction="/blocos/bgpq4">consultar o IRR</button>
    <button class="btn btn-fantasma" type="submit" formaction="/blocos/bgpq4?forcar=1">reconsultar</button>
   </div>
   {% if erros.blocos_v4 %}<p class="erro">{{ erros.blocos_v4 }}</p>{% endif %}
   {% if erros.blocos_v6 %}<p class="erro">{{ erros.blocos_v6 }}</p>{% endif %}
  </form>
  {% if saida_blocos %}
  <div class="bloco">
   <div class="bloco-topo">
    <span class="bloco-nome">bloco de originacao</span>
    <button class="btn" type="button" onclick="copiar('saida-blocos')">copiar</button>
   </div>
   <pre id="saida-blocos">{{ saida_blocos }}</pre>
  </div>
  {% endif %}
  {% if saida_blocos_remover %}
  <div class="bloco">
   <div class="bloco-topo">
    <span class="bloco-nome">remocao dos blocos</span>
    <button class="btn" type="button" onclick="copiar('saida-blocos-remover')">copiar</button>
   </div>
   <pre id="saida-blocos-remover">{{ saida_blocos_remover }}</pre>
  </div>
  {% endif %}
 </div>
</section>
```

Quatro detalhes que o resto da página já resolve e que precisam ser respeitados aqui:

- As classes `painel`, `painel-corpo`, `bloco`, `bloco-topo`, `bloco-nome`, `btn`, `btn-fantasma` já existem em `_estilo.html`. Nenhuma classe nova.
- O `onclick="copiar('...')"` é o mesmo helper dos outros quadros de saída.
- O `formaction` nos dois botões de consulta dispensa um `<form>` por botão, e mantém tudo dentro de um formulário só, que é o que faz o POST levar as duas textareas.
- A legenda do quadro de remoção nomeia as views do CLI, porque o bloco alterna entre elas: `undo network` é da view da família (`ipv4-family unicast` ou `ipv6-family unicast`) e `undo xpl route-filter` e `undo ip route-static` são do system view. Sem isso o operador cola as três linhas na view errada e leva nove erros para descobrir. Um `bloco-nome` do tipo `remocao dos blocos (network na view da familia, o resto fora dela)` já resolve.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest -v`
Expected: PASS.

- [ ] **Step 5: Confira no navegador**

Run: `uvicorn app.app:app --reload` e abra `http://127.0.0.1:8000/`.
Expected: a seção aparece abaixo do formulário do peer, com as duas caixas, os três botões e, depois de salvar, os dois quadros de saída. Salve um prefixo e cole o resultado num arquivo: as três peças do mesmo prefixo têm que estar lá.

- [ ] **Step 6: Commit**

```bash
git add templates/pagina.html tests/test_app.py
git commit -m "A tela ganha a secao dos prefixos proprios"
```

---

### Task 9: O `PLANO.md`

**Files:**
- Modify: `PLANO.md`
- Test: nenhum. É documento.

**Interfaces:**
- Consumes: as decisões das tarefas anteriores.
- Produces: nada que o código consuma.

- [ ] **Step 1: Reescreva "Originação dos próprios prefixos"**

Na seção que hoje começa com `## Originação dos próprios prefixos`:

1. Troque a estática de exemplo de `preference 1` por `preference 250` e acrescente o parágrafo do motivo: com 250 ela ganha do BGP, que é o que impede a rota de um cliente com sub-alocação dentro do bloco de virar a origem do `network`, e perde do IGP e da estática de preferência default, para um agregado que exista de verdade sair com o next-hop de verdade.
2. Acrescente, depois do exemplo de `ORIGIN-201-131-152-0m22`, um parágrafo dizendo que a lista de prefixos sai de consulta ao IRR no próprio ASN, salva no `peers.yaml`, e que a reconsulta casa por prefixo e preserva o tratamento escrito à mão.
3. Acrescente um parágrafo sobre o nome: `ORIGEM-<endereco>_<mascara>`, com o motivo do `_` e com o que a release aceita hoje.
4. Substitua o corpo da subseção `### Por que não fazer isso em XPL` por um registro curto, no mesmo espírito do `STRIP-EXTERNAL`: a limitação era suposta e foi verificada. Fica algo assim, com as suas palavras:

   ```markdown
   ### Por que não fazer isso em XPL

   Registro de verificação, e não uma regra: durante o desenho a cláusula
   `network` era tida como aceitando só `route-policy`, e a originação
   ficaria em route-policy clássico por isso. Verificado no F1A em
   2026-09-24: `network <ip> <mask> route-filter <nome> ?` completa
   normalmente, então a originação é XPL como o resto do documento.
   ```

5. Apague o "Confirme na sua release se `network ... route-filter` existe como alternativa antes de assumir", que era o ponto em aberto, e a menção a ele no checklist de validação, se houver.

- [ ] **Step 2: Reescreva "EXPORT-SANITY"**

Na seção `### EXPORT-SANITY`, troque o corpo do filtro pelo que está em `templates/base.txt.j2` depois da Task 5, e acrescente os dois parágrafos:

- o `1900`/`1901` agora tem ramo próprio, porque a dispensa da marca tirava a única barreira que o segurava nos egress de upstream, IX e PNI;
- a dispensa da marca para rota originada localmente, que usa a `AP-LOCAL-ORIGIN` já definida, e a condição de que ela depende: ninguém pode colocar rota local com path vazio na RIB por `import-route` nem por `aggregate`, senão essa rota passa a ser anunciável em todo lugar sem marca de origem.

- [ ] **Step 3: Anote o `1000` em "Origem da rota — 1xxx"**

Na linha do `64512:1000` da tabela, ou logo abaixo dela, acrescente uma frase: a marca é escrita pelo filtro de originação do prefixo próprio, e desde a mudança do `EXPORT-SANITY` ela identifica o prefixo no `display` sem ser o que sustenta o anúncio.

- [ ] **Step 4: Confira a consistência**

Run: `grep -n "preference 1\|route-policy`? não existe\|Ponto em aberto" PLANO.md | head`

Expected: nenhuma ocorrência de `preference 1` ligada à originação, nenhuma promessa de `network ... route-filter` como pendência, e o ponto em aberto da originação respondido. Os outros "Ponto em aberto" do documento continuam onde estão: são de outras seções.

- [ ] **Step 5: Commit**

```bash
git add PLANO.md
git commit -m "O documento fecha o ponto do route-filter e a barreira do 1900"
```

---

## Depois das tarefas

Os quatro itens de hardware que a spec lista continuam abertos, e nenhum deles muda código:

1. Se o nome do filtro aceita ponto, em `xpl route-filter ORIGEM-38.252.64.0_22`. Se aceitar, o `nome_origem` da Task 2 troca o traço do endereço v4 por ponto, e o teste do nome muda junto.
2. Se `undo network <ip> <mask>` remove a entrada que tem `route-filter`. Se não remover, o remover da Task 6 precisa reemitir a linha sem filtro antes do `undo`, e o aviso no topo do template muda.
3. Se o `route-filter` do `network` roda na originação e aplica LP e communities. Se não rodar, a originação inteira volta para `route-policy` e as Tasks 4 e 6 mudam de forma.
4. Se a rota originada por `network` aparece com AS-path vazio no `display bgp routing-table`. É a premissa do `EXPORT-SANITY` da Task 5, e sem ela a dispensa da marca não vale.
