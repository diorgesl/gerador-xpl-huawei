# Tenants por ASN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer do ASN da rede a unidade do bgpgen: cada rede vira um arquivo em `peers/`, toda rota de dados diz de qual ASN está falando, os blocos gerados saem em `out/<ASN>/`, e a tela ganha um seletor de qual rede está aberta.

**Architecture:** Um módulo novo, `app/tenants.py`, é o dono da pasta e o único que sabe transformar um número de ASN em caminho. Uma dependência do FastAPI (`tenant`) resolve o `?asn=` que passa a ser obrigatório em toda rota de dados e devolve um `Tenant` (asn, caminho, saída); o `app/peers.py` já é parametrizado por caminho, então ele só troca a fonte. No front, um contexto guarda o ASN escolhido no `sessionStorage`, os hooks do `react-query` montam as chaves com ele, e a barra lateral ganha o seletor.

**Tech Stack:** Python 3.14 + FastAPI + Pydantic + Jinja2 (`pytest`), React 19 + TypeScript + Vite + TanStack Query + openapi-fetch (`vitest`), Playwright no e2e.

**Spec:** `docs/superpowers/specs/2026-09-28-tenants-por-asn-design.md`

## Global Constraints

- **Comentários e mensagens de código em ASCII**, sem acento: é o que o pipeline de TFTP, backup e diff do equipamento aceita. Os textos de tela do front levam acento normalmente (como "Configurações" e "não deu para falar com a API" já levam).
- **Os escalares da API são texto**, mesmo quando são número: é o idioma do formulário, e quem converte é o `formulario.py`, que devolve o erro no campo. O `?asn=` é a exceção já existente no estilo do app, porque é parâmetro de query de rota tipada (o `id` do `/peers/previa` já é `int`).
- **`modelos_api.Modelo` tem `extra="forbid"`**: tirar um campo de um modelo quebra o front que ainda o manda, com 422. As duas pontas de uma mudança de contrato ficam em tarefas encadeadas, e o e2e é quem prova o conjunto.
- **O nome do arquivo é a verdade do tenant.** A chave `asn:` dentro dele é cópia de leitura: o app grava e nunca lê.
- **A pasta de saída vem por parâmetro, sem valor padrão.** Um default para a raiz do `out/` deixaria uma chamada esquecida escrever em `out/<token>-<tipo>.txt`, que é o nome que esta etapa elimina.
- **Mensagem de commit em português, ASCII, no estilo do repositório** ("O <sujeito> <verbo>..."), com a linha de `Co-Authored-By: Claude Code <noreply@anthropic.com>` no fim.
- **Comandos:** `.venv/bin/python -m pytest` na raiz; `npm test`, `npm run lint`, `npm run build` e `npm run api:tipos` dentro de `web/`.
- Cada tarefa termina com a suíte verde.

## Review Focus

O que a spec implica mas nenhum teste de rotina cobre, mais provável primeiro. Cada linha tem o teste que a fixa, na tarefa indicada.

| Risco | Comportamento esperado | Teste |
| --- | --- | --- |
| `peers.yaml` que não fecha (ASN de 32 bits sem `asn_politica`) no boot | O app sobe, a lista fica vazia, o arquivo fica intacto e o motivo sai no log | Tarefa 2 |
| `?asn=` ausente, não numérico, ou de um tenant que não existe | 422 no formato das recusas, e 404 no mesmo formato, nunca 500 nem lista vazia | Tarefa 3 |
| Rota de dados nova escrita sem o `Depends(tenant)` | O compilador não pega: o `?asn=` sumiria e a rota leria o tenant errado | Tarefa 3 (teste que varre a tabela de rotas) |
| `/base.txt`, que é `fetch` cru e não passa pelo cliente tipado | Precisa do `?asn=` como as outras, e um ASN sem cadastro recusa | Tarefa 3 |
| Dois tenants com um peer de mesmo token | Cada um escreve na própria pasta, e o bloco de um não apaga o do outro | Tarefa 3 |
| Front antes de a lista de ASNs chegar (`asn === null`) | Nenhuma consulta de dados dispara com ASN vazio | Tarefa 5 |

---

### Task 1: `app/tenants.py`, a pasta e a criação

**Files:**
- Create: `app/tenants.py`
- Create: `tests/test_tenants.py`

**Interfaces:**
- Consumes: `app.peers.gravar_asn(asn, politica=None, caminho=PEERS_YAML)` (já existe, `app/peers.py:244`), que grava `{asn: <asn>}` e, com política, `{asn, asn_politica}` e mais nada.
- Produces, para todas as tarefas seguintes: `RAIZ`, `PASTA`, `SAIDA`, `ORIGEM`, `BKP`, `Tenant(asn, caminho, saida)`, `caminho(asn)`, `saida(asn)`, `listar()`, `existe(asn)`, `abrir(asn)`, `criar(asn, politica=None)`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_tenants.py
"""A pasta dos tenants: a lista, a criacao e a migracao."""

import pytest

from app import tenants


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    """A pasta de tenants e a de saida num tmp_path.

    O patch e nos modulos, e nao nos caminhos de quem chama: toda funcao do
    tenants le a constante na hora da chamada, como o _yaml() do api.py.
    """
    monkeypatch.setattr(tenants, "PASTA", tmp_path / "peers")
    monkeypatch.setattr(tenants, "SAIDA", tmp_path / "out")
    monkeypatch.setattr(tenants, "ORIGEM", tmp_path / "peers.yaml")
    monkeypatch.setattr(tenants, "BKP", tmp_path / "peers.yaml.bak")
    return tmp_path


def test_a_lista_de_pasta_inexistente_e_vazia(pasta):
    assert tenants.listar() == []


def test_a_lista_traz_os_asns_ordenados(pasta):
    (pasta / "peers").mkdir()
    for nome in ("64512.yaml", "264130.yaml", "999.yaml"):
        (pasta / "peers" / nome).write_text("asn: 0\n")
    assert tenants.listar() == [999, 64512, 264130]


def test_a_lista_ignora_o_que_nao_tem_nome_de_asn(pasta):
    (pasta / "peers").mkdir()
    (pasta / "peers" / "64512.yaml").write_text("asn: 64512\n")
    (pasta / "peers" / "notas.txt").write_text("oi\n")
    (pasta / "peers" / "64512.txt").write_text("oi\n")
    (pasta / "peers" / "backup.yaml.bak").write_text("oi\n")
    (pasta / "peers" / ".DS_Store").write_text("")
    assert tenants.listar() == [64512]


def test_abrir_devolve_o_tenant_com_os_dois_caminhos(pasta):
    (pasta / "peers").mkdir()
    (pasta / "peers" / "64512.yaml").write_text("asn: 64512\n")
    achado = tenants.abrir(64512)
    assert achado.asn == 64512
    assert achado.caminho == pasta / "peers" / "64512.yaml"
    assert achado.saida == pasta / "out" / "64512"


def test_abrir_o_que_nao_existe_e_none(pasta):
    assert tenants.abrir(64512) is None


def test_criar_grava_o_arquivo_com_o_asn_e_a_politica(pasta):
    tenant = tenants.criar(264130, 65532)
    assert tenant.caminho.read_text(encoding="utf-8") == (
        "asn: 264130\nasn_politica: 65532\n")


def test_criar_sem_politica_nao_grava_a_chave(pasta):
    tenant = tenants.criar(64512)
    assert tenant.caminho.read_text(encoding="utf-8") == "asn: 64512\n"


def test_criar_nao_cria_as_listas_vazias(pasta):
    texto = tenants.criar(64512).caminho.read_text(encoding="utf-8")
    assert "peers" not in texto and "grupos" not in texto and "blocos" not in texto


def test_criar_o_que_ja_existe_e_erro(pasta):
    tenants.criar(64512)
    with pytest.raises(ValueError, match="ja tem cadastro"):
        tenants.criar(64512)


def test_criar_asn_de_32_bits_sem_politica_e_erro(pasta):
    with pytest.raises(ValueError, match="nao cabe nos 16 bits"):
        tenants.criar(264130)
    assert not (pasta / "peers" / "264130.yaml").exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_tenants.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.tenants'`

- [ ] **Step 3: Escrever `app/tenants.py`**

```python
"""A pasta dos tenants: um arquivo por ASN da rede.

O nome do arquivo E o ASN, e ele e a verdade: a chave `asn:` que mora dentro
e copia de leitura, escrita para o arquivo se descrever sozinho quando
alguem o abre no editor ou o copia para fora, e nunca lida de volta. Guardar
o mesmo dado duas vezes foi o que aposentou o campo `token` dos peers.

A pasta e a lista: um arquivo cujo nome nao e so digito nao e um tenant
torto, e um arquivo que nao e do app, e por isso some da lista em silencio.

O `criar` e burro de proposito: quem confere a faixa do ASN e o formulario,
que sabe dizer em que campo o operador errou. Aqui so o par incoerente
estoura, pelo plan.Rede, e o arquivo nunca chega a nascer.
"""

from dataclasses import dataclass
from pathlib import Path

from app import peers as peers_mod

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "peers"
SAIDA = RAIZ / "out"
# o cadastro de antes desta etapa, e a copia que a migracao deixa para tras
ORIGEM = RAIZ / "peers.yaml"
BKP = RAIZ / "peers.yaml.bak"


@dataclass(frozen=True)
class Tenant:
    asn: int
    caminho: Path
    saida: Path


def caminho(asn):
    return PASTA / ("%d.yaml" % asn)


def saida(asn):
    return SAIDA / str(asn)


def listar():
    """Os ASNs com arquivo na pasta, em ordem numerica.

    A ordem e numerica, e nao a do sistema de arquivos, para o seletor da
    tela nao depender da ordem em que o disco devolveu as entradas. O
    `isascii` junto do `isdigit` e o mesmo cuidado do formulario: digitos
    que nao sao ascii, como o sobrescrito, passam no isdigit e estouram no
    int().
    """
    if not PASTA.is_dir():
        return []
    asns = []
    for arquivo in PASTA.glob("*.yaml"):
        nome = arquivo.stem
        if nome.isascii() and nome.isdigit():
            asns.append(int(nome))
    return sorted(asns)


def existe(asn):
    return caminho(asn).is_file()


def abrir(asn):
    """O Tenant do ASN, ou None quando nao ha arquivo."""
    if not existe(asn):
        return None
    return Tenant(asn=asn, caminho=caminho(asn), saida=saida(asn))


def criar(asn, politica=None):
    """Grava o arquivo de um tenant novo e devolve o Tenant.

    O gravar_asn do peers.py ja escreve exatamente o que um tenant vazio
    precisa: a chave `asn`, o `asn_politica` quando declarado, e mais nada.
    Nao nascem `peers`, `grupos` nem `blocos`: a chave ausente e o estado de
    quem nunca usou a tela, como no gravar_blocos.

    O par incoerente estoura no plan.Rede, dentro do gravar_asn, antes de
    qualquer escrita: um ASN de 32 bits sem namespace nao tem como virar
    community standard, e um arquivo assim nasceria estourando na primeira
    leitura, sem a tela ter como conserta-lo.
    """
    if existe(asn):
        raise ValueError("o ASN %d ja tem cadastro" % asn)
    destino = caminho(asn)
    peers_mod.gravar_asn(asn, politica, destino)
    return Tenant(asn=asn, caminho=destino, saida=saida(asn))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_tenants.py -v`
Expected: PASS (11 testes)

- [ ] **Step 5: Commit**

```bash
git add app/tenants.py tests/test_tenants.py
git commit -m "A pasta dos tenants nasce com a lista e a criacao

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: A migração do `peers.yaml` e o boot

**Files:**
- Modify: `app/tenants.py` (acrescenta `migrar` e `_mover_saida`)
- Modify: `app/app.py:23-31` (o `lifespan` chama a migração)
- Modify: `tests/test_tenants.py` (acrescenta os testes da migração)

**Interfaces:**
- Consumes: `tenants.criar`, `tenants.caminho`, `tenants.saida`, `ORIGEM`, `BKP` (tarefa 1) e `app.peers.carregar_asn(caminho)`.
- Produces: `tenants.migrar() -> Path | None` (o caminho do tenant migrado, ou `None`).

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_tenants.py — acrescentar no fim
def test_migrar_sem_peers_yaml_nao_faz_nada(pasta):
    assert tenants.migrar() is None
    assert not (pasta / "peers").exists()


def test_migrar_move_o_arquivo_e_deixa_o_bak(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\npeers: []\n")
    destino = tenants.migrar()
    assert destino == pasta / "peers" / "264130.yaml"
    assert not (pasta / "peers.yaml").exists()
    assert (pasta / "peers.yaml.bak").read_text() == (
        "asn: 264130\nasn_politica: 65532\npeers: []\n")
    # o conteudo atravessa inteiro, e nao so a chave do ASN
    assert destino.read_text() == (pasta / "peers.yaml.bak").read_text()


def test_migrar_usa_o_as_de_fabrica_sem_a_chave(pasta):
    (pasta / "peers.yaml").write_text("peers: []\n")
    assert tenants.migrar() == pasta / "peers" / "64512.yaml"


def test_migrar_leva_os_blocos_da_raiz_do_out(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    (pasta / "out").mkdir()
    (pasta / "out" / "14840-upstream.txt").write_text("bloco\n")
    (pasta / "out" / "blocos.txt").write_text("origem\n")
    tenants.migrar()
    assert (pasta / "out" / "264130" / "14840-upstream.txt").read_text() == "bloco\n"
    assert (pasta / "out" / "264130" / "blocos.txt").read_text() == "origem\n"
    assert not (pasta / "out" / "14840-upstream.txt").exists()


def test_migrar_nao_toca_no_cache_do_bgpq4(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    (pasta / "out" / ".cache").mkdir(parents=True)
    (pasta / "out" / ".cache" / "14840.json").write_text("{}")
    tenants.migrar()
    assert (pasta / "out" / ".cache" / "14840.json").exists()


def test_migrar_nao_sobrescreve_o_que_ja_esta_no_destino(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    (pasta / "out" / "264130").mkdir(parents=True)
    (pasta / "out" / "264130" / "blocos.txt").write_text("novo\n")
    (pasta / "out" / "blocos.txt").write_text("velho\n")
    tenants.migrar()
    assert (pasta / "out" / "264130" / "blocos.txt").read_text() == "novo\n"
    assert (pasta / "out" / "blocos.txt").read_text() == "velho\n"


def test_migrar_nao_sobrescreve_um_tenant_que_ja_existe(pasta):
    (pasta / "peers").mkdir()
    (pasta / "peers" / "264130.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\npeers: []\n")
    assert tenants.migrar() is None
    assert (pasta / "peers.yaml").exists()
    assert not (pasta / "peers.yaml.bak").exists()


def test_migrar_duas_vezes_e_no_op(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    assert tenants.migrar() is not None
    assert tenants.migrar() is None


def test_migrar_yaml_torto_estoura_e_nao_move_nada(pasta):
    # ASN de 32 bits sem namespace: o mesmo ValueError que hoje estoura na
    # primeira requisicao
    (pasta / "peers.yaml").write_text("asn: 264130\n")
    with pytest.raises(ValueError, match="nao cabe nos 16 bits"):
        tenants.migrar()
    assert (pasta / "peers.yaml").exists()
    assert not (pasta / "peers.yaml.bak").exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_tenants.py -v`
Expected: FAIL com `AttributeError: module 'app.tenants' has no attribute 'migrar'`

- [ ] **Step 3: Implementar a migração**

```python
# app/tenants.py — acrescentar no fim; os imports ganham `import os`
def migrar():
    """O peers.yaml de antes desta etapa vira o tenant do AS dele.

    Roda uma vez, no boot. A copia para o .bak vem ANTES do move de
    proposito: e ela que faz o boot seguinte ser no-op, porque depois do
    move o ORIGEM nao existe mais. Ou os dois arquivos estao la (a
    migracao nao chegou a acontecer), ou so o .bak esta (terminou).

    O ASN sai do carregar_asn de sempre, que estoura com o mesmo ValueError
    de antes num arquivo que nao fecha. Quem chama decide o que fazer com
    ele: aqui nada e adivinhado e nenhum arquivo e tocado.

    Devolve o caminho do tenant migrado, ou None quando nao havia o que
    migrar.
    """
    if not ORIGEM.is_file():
        return None
    destino = caminho(peers_mod.carregar_asn(ORIGEM).asn)
    if destino.exists():
        # a pasta ja tem esse tenant: nao ha o que mover, e sobrescrever o
        # que esta la seria trocar um cadastro por outro em silencio
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ORIGEM, BKP)
    os.replace(ORIGEM, destino)
    _mover_saida(destino.stem)
    return destino


def _mover_saida(asn):
    """Os blocos da raiz do out/ para a pasta do tenant.

    So os .txt da raiz entram: o .cache/ do bgpq4 e derivado do IRR e nao
    da rede, e continua onde esta, compartilhado. O que ja existe no destino
    fica: em duvida entre o arquivo que ja estava e o que chegou, o que ja
    estava e o que corresponde a uma pasta de tenant que alguem criou.
    """
    destino = saida(int(asn))
    destino.mkdir(parents=True, exist_ok=True)
    for arquivo in sorted(SAIDA.glob("*.txt")):
        alvo = destino / arquivo.name
        if alvo.exists():
            print("bgpgen: %s nao migrou: %s ja existe" % (arquivo, alvo),
                  flush=True)
            continue
        os.replace(arquivo, alvo)
```

Também: `import os` e `import shutil` no topo do módulo.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_tenants.py -v`
Expected: PASS (20 testes)

- [ ] **Step 5: Ligar a migração no boot**

`app/app.py`, dentro do `ciclo`:

```python
@asynccontextmanager
async def ciclo(app: FastAPI):
    """O que roda uma vez por processo, antes da primeira requisicao.

    Hoje e o bootstrap do admin e a migracao do peers.yaml para a pasta
    dos tenants, nesta ordem: o login primeiro, para um erro na migracao
    nao deixar o app inalcancavel.

    A migracao nao pode derrubar o boot: um yaml torto (ASN de 32 bits sem
    namespace) deixaria o app num laco de restart do docker, quando o que
    ele tem a fazer e subir vazio e dizer no log o que houve.
    """
    auth.bootstrap()
    try:
        migrado = tenants.migrar()
    except (ValueError, OSError) as exc:
        print("bgpgen: peers.yaml nao migrou: %s" % exc, flush=True)
    else:
        if migrado is not None:
            print("bgpgen: peers.yaml virou %s (copia em peers.yaml.bak)"
                  % migrado, flush=True)
    yield
```

E o import: `from app import api, auth, render, tenants` (`app/app.py:17`).

- [ ] **Step 6: Provar o boot com um yaml torto**

```python
# tests/test_tenants.py — acrescentar no fim
def test_o_boot_nao_cai_com_peers_yaml_torto(pasta):
    """O lifespan roda a migracao e segue de pe, com a lista vazia."""
    from fastapi.testclient import TestClient

    from app import app as mod
    from app import auth

    (pasta / "peers.yaml").write_text("asn: 264130\n")
    with TestClient(mod.app) as cliente:
        assert cliente.get("/api/sessao").status_code == 200
    assert tenants.listar() == []
    assert (pasta / "peers.yaml").exists()
```

A fixture `pasta` não cobre `auth.USUARIOS_YAML`, então este teste precisa também de `usuarios_em_tmp` (a fixture do `tests/conftest.py:46`), que põe o arquivo de login num tmp próprio. Acrescente `usuarios_em_tmp` à assinatura do teste.

Run: `.venv/bin/python -m pytest tests/test_tenants.py -v`
Expected: PASS (21 testes)

- [ ] **Step 7: Commit**

```bash
git add app/tenants.py app/app.py tests/test_tenants.py
git commit -m "O peers.yaml vira o primeiro tenant no boot

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: A API fala do tenant

Esta é a tarefa grande, e é uma ideia só: toda rota de dados resolve um `Tenant`, e tudo que ela lê ou escreve mora nele. O diff é mecânico, mas espalhado; a suíte é quem prova.

**Files:**
- Modify: `app/peers.py` (`Peer.arquivo` e `Grupo.arquivo` recebem a pasta; `OUT` sai)
- Modify: `app/render.py` (`escrever_*` recebem a pasta; `OUT` sai)
- Modify: `app/prefixes.py` (`CACHE` passa a sair de `tenants.SAIDA`)
- Modify: `app/api.py` (a dependência `tenant`, `_peers`/`_grupos`/`_rede`, as 26 rotas, o `PUT /api/rede`)
- Modify: `app/app.py` (`/base.txt` e o `rede()` saem de um tenant)
- Modify: `tests/conftest.py` (a fixture cria o tenant de teste)
- Modify: `tests/test_api*.py`, `tests/test_isolamento.py`, `tests/test_render.py` (só onde passa `?asn=` ou escreve em `out/`)
- Modify: `web/src/api/schema.d.ts` (regerado, não editado à mão)

**Interfaces:**
- Consumes: `tenants.abrir(asn)`, `tenant.saida`, `tenant.caminho` (tarefa 1).
- Produces: `tenants.NaoEncontrado(asn)` (a exceção que vira 404); `tenants.Tenant` como tipo da dependência `app.api.tenant`; `peers.carregar_rede(caminho, asn)`, que monta o `plan.Rede` do tenant a partir do nome do arquivo e do `asn_politica` de dentro; `Peer.arquivo(saida)` e `Grupo.arquivo(saida)` com `saida` posicional obrigatório; `render.escrever_peer(peer, grupo=None, rede=None, *, saida)`, `escrever_grupo(grupo, rede=None, *, saida)` e `escrever_blocos(blocos, rede=None, *, saida)`, com `saida` obrigatório e só por palavra-chave.

- [ ] **Step 1: A pasta de saída vira parâmetro**

`app/peers.py`: apague `OUT = RAIZ / "out"` (linha 27) e troque os dois `arquivo`:

```python
    def arquivo(self, saida):
        """O caminho do bloco deste peer na pasta de saida do tenant dele.

        A pasta vem por parametro e nao tem padrao: um default para a raiz
        do out/ deixaria uma chamada esquecida escrever em
        out/<token>-<tipo>.txt, que e o nome que a etapa dos tenants
        elimina. O nome do arquivo continua saindo do token, que e unico
        dentro de um tenant.
        """
        return Path(saida) / ("%s-%s.txt" % (self.token, self.tipo))
```

e o mesmo para `Grupo.arquivo(self, saida)`, com `"grupo-%s.txt" % self.nome`.

Ainda no `app/peers.py`, ao lado do `carregar_asn` (`app/peers.py:221`), o `Rede` do tenant passa a nascer dos dois lugares certos:

```python
def carregar_rede(caminho, asn):
    """O plan.Rede do tenant: o ASN do nome do arquivo, o namespace de dentro.

    O namespace so existe dentro do arquivo, e e de la que ele sai. O ASN,
    nao: um arquivo editado a mao que diga outro numero na chave `asn`
    geraria a config de outra rede em silencio, enquanto o seletor e a pasta
    de saida seguem o nome. O nome ganha, e essa e a unica forma de o ganho
    valer de verdade.

    O ValueError do plan.Rede sai nomeando o arquivo, como no carregar_asn:
    e a mensagem que a tela mostra no toast quando o par nao fecha (ASN de
    32 bits sem namespace).
    """
    bruto = _ler_bruto(caminho).get(CHAVE_POLITICA)
    try:
        return Rede(asn=asn, politica=bruto)
    except ValueError as erro:
        raise ValueError("%s: %s" % (caminho, erro)) from erro
```

`app/render.py`: apague `OUT = RAIZ / "out"` (linha 15) e troque as três funções de escrita:

```python
def escrever_peer(peer, grupo=None, rede=None, *, saida):
    saida.mkdir(parents=True, exist_ok=True)
    destino = peer.arquivo(saida)
    destino.write_text(render_peer(peer, grupo=grupo, rede=rede),
                       encoding="ascii")
    return destino
```

O `*` antes do `saida` é para ele não ter como ser esquecido nem confundido de posição: a chamada de hoje, `escrever_peer(peer, grupo=..., rede=...)`, reprova com `TypeError` até alguém dizer de que tenant é o bloco. `escrever_grupo(grupo, rede=None, *, saida)` e `escrever_blocos(blocos, rede=None, *, saida)` seguem o mesmo: o `mkdir` sai do `OUT` e passa a ser o da pasta recebida, e o destino é `grupo.arquivo(saida)` e `saida / "blocos.txt"`.

`app/prefixes.py:15`: `CACHE = tenants.SAIDA / ".cache"`, com `from app import tenants` no topo.

- [ ] **Step 2: A exceção do tenant que não existe**

`app/tenants.py`, no fim:

```python
class NaoEncontrado(Exception):
    """O ASN pedido nao tem arquivo na pasta.

    E o mesmo desenho do auth.NaoAutenticado: quem transforma em resposta e
    um handler registrado no instalar() do api.py, no formato das outras
    recusas. Um HTTPException daria {"detail": ...}, que a SPA le como
    resposta fora do modelo.
    """

    def __init__(self, asn):
        self.asn = asn
        super().__init__("ASN %s nao tem cadastro em peers/" % asn)
```

- [ ] **Step 3: A dependência e os ajudantes no `app/api.py`**

Troque o bloco `_yaml`/`_rede`/`_peers`/`_grupos` (`app/api.py:129-145`) por:

```python
def tenant(asn: int = Query(...)) -> tenants_mod.Tenant:
    """O Tenant do ?asn= da URL, ou 404.

    A dependencia e o unico lugar do app que transforma o numero da query
    num arquivo: as rotas recebem o Tenant pronto e nao voltam a falar de
    caminho. Toda rota de dados declara `t: Tenant = Depends(tenant)`, e o
    test_toda_rota_de_dados_pede_o_asn varre a tabela de rotas para uma
    rota nova nao nascer sem ela.

    O ?asn= que falta, ou que nao e numero, nem chega aqui: o FastAPI
    recusa antes, e o _pedido_invalido responde 422 no formato das outras
    recusas.
    """
    achado = tenants_mod.abrir(asn)
    if achado is None:
        raise tenants_mod.NaoEncontrado(asn)
    return achado


def _rede(t):
    """O plan.Rede do tenant: o ASN do nome do arquivo, o namespace de dentro.

    O ASN nao sai da chave `asn` do arquivo: ela e copia de leitura, e um
    arquivo editado a mao que discorde do nome geraria em silencio a config
    de outra rede enquanto o seletor mostra o nome. Quem junta as duas
    metades e o carregar_rede do peers.py.

    O carregar_asn continua existindo para a migracao, que e o unico lugar
    sem nome de arquivo de onde tirar o ASN: o peers.yaml migrado tem o ASN
    dentro dele e em lugar nenhum mais.
    """
    return peers_mod.carregar_rede(t.caminho, t.asn)


def _peers(t):
    return peers_mod.carregar(t.caminho)


def _grupos(t):
    return peers_mod.carregar_grupos(t.caminho)
```

O import: `from app import tenants as tenants_mod`.

- [ ] **Step 4: As 26 rotas**

Cada rota abaixo ganha `t: tenants_mod.Tenant = Depends(tenant)` como primeiro parâmetro, e o corpo troca as chamadas de ajudante: `_rede()` → `_rede(t)`, `_peers()` → `_peers(t)`, `_grupos()` → `_grupos(t)`, `_yaml()` → `t.caminho`, `render.OUT` → `t.saida`, `.arquivo()` → `.arquivo(t.saida)`.

As rotas, com o que mais muda em cada uma além do padrão:

| Rota | `app/api.py` | O que muda além do `t` |
| --- | --- | --- |
| `GET /plano` | 169 | `_rede(t)`, `_peers(t)`, `_grupos(t)` |
| `PUT /rede` | 197 | só o corpo: ver o passo 5 |
| `GET /peers` | 225 | `_peers(t)` |
| `GET /peers/novo` | 234 | `_peers(t)`, `_grupos(t)` |
| `GET /peers/{ident}` | 239 | `_peers(t)` |
| `GET /peers/{ident}/copia` | 247 | `_peers(t)`, `_grupos(t)` |
| `POST /peers` | 300 | `_salvar_peer(t, ...)` |
| `PUT /peers/{ident}` | 305 | `_peers(t)`, `_salvar_peer(t, ...)` |
| `DELETE /peers/{ident}` | 319 | `peer.arquivo(t.saida).unlink(missing_ok=True)`, `peers_mod.gravar(peers, t.caminho)` |
| `POST /peers/previa` | 351 | `_peers(t)`, `_grupos(t)`, `_rede(t)`, `_ler(anterior.arquivo(t.saida))`, `peer.arquivo(t.saida).name` |
| `GET /peers/{ident}/saida` | 376 | idem |
| `POST /irr` | 394 | nada (não lê nem escreve tenant) |
| `GET /grupos` | 465 | `_peers(t)`, `_grupos(t)` |
| `GET /grupos/novo` | 474 | idem |
| `GET /grupos/{ident}` | 480 | idem |
| `GET /grupos/{ident}/copia` | 488 | idem |
| `POST /grupos` | 500 | `_salvar_grupo(t, ...)` |
| `PUT /grupos/{ident}` | 505 | `_grupos(t)`, `_salvar_grupo(t, ...)` |
| `DELETE /grupos/{ident}` | 514 | `grupo.arquivo(t.saida)`, `peers_mod.gravar_grupos(grupos, t.caminho)`, `_membros(grupo, _peers(t))` |
| `POST /grupos/previa` | 542 | `_grupos(t)`, `_peers(t)`, `_rede(t)`, `_ler(anterior.arquivo(t.saida))` |
| `GET /grupos/{ident}/saida` | 557 | `_grupos(t)`, `_rede(t)`, `grupo.arquivo(t.saida).name` |
| `GET /blocos` | 596 | `peers_mod.carregar_blocos(t.caminho)`, `_rede(t)` |
| `PUT /blocos` | 601 | `_rede(t)`, `peers_mod.gravar_blocos(blocos, t.caminho)`, `render.escrever_blocos(form._ativos(blocos), rede, saida=t.saida)` |
| `POST /blocos/previa` | 614 | `_rede(t)`, `_ler(t.saida / "blocos.txt")` |
| `POST /blocos/irr` | 628 | `_rede(t)` |
| `GET /config` | 706 | `_peers(t)`, `_grupos(t)`, `_rede(t)`, `peers_mod.carregar_blocos(t.caminho)` |

E os ajudantes que escrevem, que ganham o `t` como primeiro parâmetro:

```python
def _salvar_peer(t, formulario, peers, anterior):
    grupos, rede = _grupos(t), _rede(t)
    ...
        if anterior.arquivo(t.saida) != peer.arquivo(t.saida):
            anterior.arquivo(t.saida).unlink(missing_ok=True)
    peers_mod.gravar(peers, t.caminho)
    destino = render.escrever_peer(peer, grupo=_grupo_do_peer(peer, grupos),
                                   rede=rede, saida=t.saida)
```

O mesmo em `_salvar_grupo(t, formulario, grupos, anterior)` (com `render.escrever_grupo(grupo, rede=_rede(t), saida=t.saida)`), e nas três seções do `/config`:

```python
def _secao_originacao(blocos, rede, saida):
    ...
    arquivo = saida / "blocos.txt"


def _secao_grupo(grupo, rede, saida):
    destino = grupo.arquivo(saida)


def _secao_peer(peer, grupo, rede, saida):
    destino = peer.arquivo(saida)
```

chamadas de `ler_config` como `_secao_grupo(grupo, rede, t.saida)`.

- [ ] **Step 5: `PUT /api/rede` perde o ASN**

`app/modelos_api.py:109`: apague o campo `asn` do `RedeForm`, deixando só `politica`. Em `api.py`:

```python
@roteador.put("/rede", response_model=RedeAtual)
def gravar_rede(pedido: RedeForm, t: tenants_mod.Tenant = Depends(tenant)):
    """O namespace das standard do tenant, pelas conferencias do
    _asn_do_formulario.

    O ASN nao vem do corpo: ele e o nome do arquivo, e quem troca de ASN e
    o seletor, criando ou escolhendo outro tenant. Editar o campo para
    renomear o arquivo fica para a rodada do rename.
    """
    asn, politica, erros = form._asn_do_formulario(
        {"asn_rede": str(t.asn), "asn_politica": pedido.politica})
    if not erros:
        peers_mod.gravar_asn(asn, politica, t.caminho)
    if erros:
        return _falha(422, erros)
    return _modelo_rede(_rede(t))
```

- [ ] **Step 6: O `/base.txt` e o `rede()` do `app.py`**

`app/app.py:58`: `rede()` passa a receber o ASN e a sair do tenant.

```python
def rede(asn):
    """O plan.Rede do tenant do ASN pedido, para o bloco base.

    O /base.txt nao esta em /api, mas e do tenant como as outras: quem
    baixa o bloco base baixa o de uma rede, e o namespace das communities
    que saem nele e o dela.
    """
    achado = tenants.abrir(asn)
    if achado is None:
        raise tenants.NaoEncontrado(asn)
    return peers_mod.carregar_rede(achado.caminho, asn)


@app.get("/base.txt", response_class=HTMLResponse,
         dependencies=[Depends(auth.exigir_login)])
def baixar_base(asn: int = Query(...)):
    return HTMLResponse(render.render_base(rede=rede(asn)), media_type="text/plain")
```

O 404 do ASN sem cadastro sai pelo mesmo handler da API (passo 7). O `app/app.py:31` e o `app.py:69` são os dois pontos.

- [ ] **Step 7: O handler do 404 e o teste que varre as rotas**

```python
# app/api.py, junto dos outros handlers
async def _sem_tenant(request: Request, exc: tenants_mod.NaoEncontrado):
    """O 404 do ASN sem arquivo, no formato das outras recusas."""
    return _falha(404, [validate.Erro("_", str(exc))])


def instalar(app: FastAPI):
    """Monta as rotas /api e os tratadores de erro no app."""
    app.include_router(publico)
    app.include_router(roteador)
    app.add_exception_handler(RequestValidationError, _pedido_invalido)
    app.add_exception_handler(auth.NaoAutenticado, _sem_sessao)
    app.add_exception_handler(tenants_mod.NaoEncontrado, _sem_tenant)
    app.add_exception_handler(Exception, _falha_inesperada)
```

E o teste que impede uma rota nova de nascer sem tenant:

```python
# tests/test_api.py — acrescentar no fim
def test_toda_rota_de_dados_pede_o_asn():
    """Uma rota nova sem o Depends(tenant) leria o tenant errado em silencio.

    O /api/asns fica de fora: ele e quem lista os tenants, e nao ha o que
    resolver antes dele. As tres rotas de sessao estao no outro roteador e
    nao entram nesta varredura.
    """
    from app import api as api_mod

    sem_asn = [rota.path for rota in api_mod.roteador.routes
               if rota.path != "/api/asns"
               and "asn" not in {p.name for p in rota.dependant.query_params}]
    assert sem_asn == []
```

- [ ] **Step 8: As fixtures e os testes que apontam caminho**

`tests/dados_api.py`, que é o módulo dos dados que mais de um arquivo de teste reusa, ganha a constante que a suíte inteira compartilha:

```python
# o tenant que a suite usa; quem precisa de outro passa o proprio asn no
# `params`, que vence o padrao do ClienteComAsn
ASN_DE_TESTE = 64512
```

`tests/conftest.py`, trocando o `api_anonimo` (linhas 67-87) e com `from dados_api import ASN_DE_TESTE` no topo:

```python
class ClienteComAsn:
    """O TestClient com o ?asn= de teste em toda chamada.

    O parametro entra por padrao aqui, e nao em cada chamada dos testes:
    sao centenas, e o que quase todos provam nao e o tenant. Quem precisa
    de outro ASN passa o proprio `params`, que vence; quem precisa de
    nenhum usa o `.cru`, o TestClient de verdade.

    O `params` de quem chamou e mesclado, e nao substituido: os testes que
    ja mandam `params={"tipo": ...}` continuam funcionando sem mudanca.
    """

    def __init__(self, cliente, asn=ASN_DE_TESTE):
        self.cru = cliente
        self.asn = asn

    def _chamada(self, metodo, url, **kw):
        params = {"asn": self.asn, **kw.pop("params", {})}
        return getattr(self.cru, metodo)(url, params=params, **kw)

    def get(self, url, **kw):
        return self._chamada("get", url, **kw)

    def post(self, url, **kw):
        return self._chamada("post", url, **kw)

    def put(self, url, **kw):
        return self._chamada("put", url, **kw)

    def delete(self, url, **kw):
        return self._chamada("delete", url, **kw)


@pytest.fixture
def api_anonimo(tmp_path, monkeypatch, usuarios_em_tmp):
    """Um TestClient com a pasta de tenants, o out/ e o cache em tmp_path.

    A pasta nasce com o tenant de teste dentro, porque toda rota de dados
    resolve um tenant: sem arquivo nenhum, a suite inteira daria 404. O
    `with` roda o lifespan, e e ele que cria o admin no arquivo de
    usuarios_em_tmp.
    """
    from fastapi.testclient import TestClient

    from app import app as mod
    from app import prefixes, tenants

    monkeypatch.setattr(tenants, "PASTA", tmp_path / "peers")
    monkeypatch.setattr(tenants, "SAIDA", tmp_path / "out")
    monkeypatch.setattr(tenants, "ORIGEM", tmp_path / "peers.yaml")
    monkeypatch.setattr(tenants, "BKP", tmp_path / "peers.yaml.bak")
    monkeypatch.setattr(prefixes, "CACHE", tmp_path / "out" / ".cache")
    with TestClient(mod.app) as cliente:
        tenants.criar(ASN_DE_TESTE)
        yield ClienteComAsn(cliente)
```

Repare que `api_anonimo` passa a devolver o cliente embrulhado: `api` (`conftest.py:110`) vira `return logar(api_anonimo)`, e o `logar` (`conftest.py:91`) chama `cliente.post`, que o embrulho tem.

Os testes que patcham caminho na mão passam a apontar os do `tenants`:

- `tests/test_api.py:84` e `:96` patcham `peers_mod.carregar_asn` com um `quebrado` para provar o 500 do `_falha_inesperada`. A rota passou a chamar o `carregar_rede`, então o patch tem que ser nele: com o nome velho o teste continuaria passando por acidente, porque o yaml quebrado dele é um `peers.yaml` que agora nem é lido.
- O `tests/test_peers.py` testa o `carregar_asn` direto e não muda: ele continua existindo para a migração.
- `tests/test_isolamento.py:36-39` patcha `mod.OUT` e `render.OUT`: passa a patchar `tenants.PASTA` e `tenants.SAIDA` e a criar o tenant de teste, como a fixture do conftest.
- `tests/test_isolamento.py:264-275` monta o próprio cliente: usa o `ClienteComAsn` e `tenants.criar`.
- `tests/test_render.py:1480` e `:2261` patcham `render.OUT` e `peers.OUT`: passam a passar `saida=tmp_path` para o `escrever_*`.
- `tests/test_api_peers.py:9` e os outros `_grava(tmp_path, ...)` gravam `tmp_path / "peers.yaml"`: passam a gravar em `tmp_path / "peers" / ("%d.yaml" % ASN_DE_TESTE)`, com `(tmp_path / "peers").mkdir(exist_ok=True)`.

```python
# tests/test_api_peers.py
from dados_api import ASN_DE_TESTE


def _grava(tmp_path, *peers):
    pasta = tmp_path / "peers"
    pasta.mkdir(exist_ok=True)
    peers_mod.gravar(list(peers), pasta / ("%d.yaml" % ASN_DE_TESTE))
```

- [ ] **Step 9: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS. O que quebrar é rota que ainda lê o `_yaml()` ou `.arquivo()` sem pasta; o teste que varre as rotas (`test_toda_rota_de_dados_pede_o_asn`) aponta a primeira.

- [ ] **Step 10: Regerar o schema do front**

Run: `cd web && npm run api:tipos`
Expected: `web/src/api/schema.d.ts` ganha `asn` como query obrigatório em toda rota de dados e em `/base.txt`, e desaparece o `asn` do `RedeForm`. **Não edite esse arquivo à mão**: o `tests/test_tipos_api.py` compara com o `app.openapi()`.

- [ ] **Step 11: Os testes novos do tenant errado e da colisão**

```python
# tests/test_api_peers.py — acrescentar
def test_o_asn_sem_cadastro_da_404_no_formato_das_recusas(api):
    resposta = api.get("/api/peers", params={"asn": 999})
    assert resposta.status_code == 404
    assert "999" in resposta.json()["erros"]["_"]


def test_o_asn_que_falta_da_422(api):
    resposta = api.cru.get("/api/peers")
    assert resposta.status_code == 422
    assert "_corpo" in resposta.json()["erros"]


def test_o_asn_que_nao_e_numero_da_422(api):
    """A revisao da tarefa 3 deixou este caminho sem prova.

    O `?asn=` ausente ja era testado; o torto, que estoura na conversao para
    int antes de a dependencia rodar, nao. E o caso do operador que cola um
    pedaco de texto no lugar do numero, e sem ele a recusa poderia virar um
    500 sem ninguem notar.
    """
    resposta = api.cru.get("/api/peers", params={"asn": "abc"})
    assert resposta.status_code == 422
    assert "_corpo" in resposta.json()["erros"]


def test_o_base_txt_tambem_e_do_tenant(api):
    """O /base.txt e fetch cru no front, e nao do cliente tipado.

    Ele sai do schema como as outras rotas, mas o `?asn=` dele nao esta em
    chamada nenhuma do openapi-fetch: quem o busca e o fetch cru da Casca e
    da tela do bloco base. Sem esta prova, o parametro sumiria de la sem
    nenhum teste reclamar.
    """
    assert api.get("/base.txt").status_code == 200
    assert api.get("/base.txt", params={"asn": 999}).status_code == 404
```

O peer escrito no tenant de teste cai na pasta daquele ASN:

```python
# tests/test_api_peers.py — acrescentar
def test_o_bloco_do_peer_sai_na_pasta_do_tenant(api, tmp_path):
    _grava(tmp_path, peer_cliente())
    resposta = api.post("/api/peers", json=CLIENTE)
    assert resposta.status_code == 201
    assert (tmp_path / "out" / "64512" / "268127-cliente.txt").exists()
```

A prova de que **dois** tenants com o mesmo token não se atropelam precisa de dois tenants, e o segundo só nasce pelo `POST /api/asns`, que é a tarefa 4: o teste de verdade está lá, no passo 7.

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "A API passa a falar do tenant em toda rota de dados

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: `GET /api/asns` e `POST /api/asns`

**Files:**
- Modify: `app/modelos_api.py` (dois modelos)
- Modify: `app/api.py` (duas rotas)
- Create: `tests/test_api_asns.py`
- Modify: `web/src/api/schema.d.ts` (regerado)

**Interfaces:**
- Consumes: `tenants.listar()`, `tenants.criar(asn, politica)`, `form._asn_do_formulario` (tarefas 1 e 3).
- Produces: `GET /api/asns` → `list[str]`; `POST /api/asns` com `{"asn": str, "politica": str}` → 201 com `list[str]`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_api_asns.py
"""As duas rotas que listam e criam tenants."""

from dados_api import ASN_DE_TESTE


def test_a_lista_traz_o_tenant_de_teste(api):
    assert api.get("/api/asns").json() == [str(ASN_DE_TESTE)]


def test_a_lista_sai_ordenada_e_como_texto(api, tmp_path):
    from app import tenants

    tenants.criar(999)
    tenants.criar(264130, 65532)
    assert api.get("/api/asns").json() == ["999", "64512", "264130"]


def test_a_lista_nao_pede_asn(api):
    assert api.cru.get("/api/asns").status_code == 200


def test_criar_devolve_a_lista_nova(api):
    resposta = api.post("/api/asns", json={"asn": "64513", "politica": ""})
    assert resposta.status_code == 201
    assert resposta.json() == ["64512", "64513"]


def test_criar_grava_o_arquivo_do_tenant(api, tmp_path):
    api.post("/api/asns", json={"asn": "264130", "politica": "65532"})
    assert (tmp_path / "peers" / "264130.yaml").read_text(encoding="utf-8") == (
        "asn: 264130\nasn_politica: 65532\n")


def test_criar_o_que_ja_existe_e_422_no_campo(api):
    resposta = api.post("/api/asns", json={"asn": "64512", "politica": ""})
    assert resposta.status_code == 422
    assert "ja tem cadastro" in resposta.json()["erros"]["asn_rede"]


def test_criar_asn_de_32_bits_sem_namespace_e_422_no_campo(api):
    resposta = api.post("/api/asns", json={"asn": "264130", "politica": ""})
    assert resposta.status_code == 422
    assert "namespace" in resposta.json()["erros"]["asn_politica"]


def test_criar_asn_reservado_e_422(api):
    resposta = api.post("/api/asns", json={"asn": "23456", "politica": ""})
    assert resposta.status_code == 422
    assert "reservado" in resposta.json()["erros"]["asn_rede"]


def test_criar_asn_que_nao_e_numero_e_422(api):
    resposta = api.post("/api/asns", json={"asn": "abc", "politica": ""})
    assert resposta.status_code == 422
    assert "so digitos" in resposta.json()["erros"]["asn_rede"]


def test_criar_sem_asn_e_422_no_campo(api):
    """O campo vazio, que a tela nova manda quando ninguem digitou nada.

    E o caminho que os dois testes apagados na tarefa 3 deixaram sem
    cobertura: com o `asn` fora do RedeForm, o "informe o AS da rede" do
    _asn_do_formulario so tem esta rota para aparecer.
    """
    resposta = api.post("/api/asns", json={"asn": "", "politica": ""})
    assert resposta.status_code == 422
    assert "informe o AS da rede" in resposta.json()["erros"]["asn_rede"]


def test_criar_asn_de_16_bits_sem_namespace_usa_o_proprio(api, tmp_path):
    api.post("/api/asns", json={"asn": "64513", "politica": ""})
    assert (tmp_path / "peers" / "64513.yaml").read_text(encoding="utf-8") == (
        "asn: 64513\n")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_api_asns.py -v`
Expected: FAIL: 405 nas de POST, e a lista vazia nas de GET (a rota não existe, e o `ClienteComAsn` devolve 404 → o `test_a_lista_nao_pede_asn` passa por acidente; os outros não)

- [ ] **Step 3: Os modelos**

```python
# app/modelos_api.py — junto do RedeAtual
class AsnPedido(Modelo):
    """O par do formulario de um tenant novo.

    Os dois campos sao texto, como os do resto do app: quem converte e o
    _asn_do_formulario, que devolve o erro no campo que o causou. O par
    inteiro vem junto porque um ASN de 32 bits precisa do namespace para
    ter um arquivo que funcione: sem ele, o tenant nasceria estourando na
    primeira leitura e a tela nao teria como conserta-lo, porque o plano
    do tenant e justamente o que falha.
    """

    asn: str = ""
    politica: str = ""
```

A resposta da lista é `list[str]`, declarada na própria rota com `response_model=list[str]`.

- [ ] **Step 4: As rotas**

```python
# app/api.py — junto do ler_plano
@roteador.get("/asns", response_model=list[str])
def listar_asns():
    """Os ASNs com arquivo na pasta, para o seletor da tela.

    Esta e a unica rota de dados que nao pede o ?asn=: ela e quem diz
    quais existem, e nao ha o que resolver antes dela. O test que varre a
    tabela de rotas a dispensa pelo mesmo motivo.
    """
    return [str(asn) for asn in tenants_mod.listar()]


@roteador.post("/asns", response_model=list[str], status_code=201)
def criar_asn(pedido: AsnPedido):
    """Cria o arquivo de um tenant novo e devolve a lista com ele dentro.

    A resposta e a lista inteira, e nao o registro criado: o seletor que
    chamou precisa dela de qualquer jeito para desenhar as opcoes, e uma
    volta a menos e uma janela a menos com o ASN novo fora da lista.

    Nada e gravado antes de as duas conferencias passarem: a de faixa e de
    par, do _asn_do_formulario, e a de arquivo ja existente, do criar.
    """
    asn, politica, erros = form._asn_do_formulario(
        {"asn_rede": pedido.asn, "asn_politica": pedido.politica})
    if not erros:
        try:
            tenants_mod.criar(asn, politica)
        except ValueError as exc:
            # a chave e `asn_rede`, e nao `asn`, porque e o nome do campo que
            # o dialogo da tela desenha, o mesmo do fieldset das
            # Configuracoes. Um erro numa chave que campo nenhum tem seria
            # uma recusa invisivel: o 422 volta, o dialogo nao pinta nada e o
            # operador clica de novo no mesmo botao
            erros = [validate.Erro("asn_rede", str(exc))]
    if erros:
        return _falha(422, erros)
    return [str(n) for n in tenants_mod.listar()]
```

O import de `AsnPedido` entra na lista do `from app.modelos_api import (...)` (`app/api.py:21-26`).

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_api_asns.py -v`
Expected: PASS (10 testes)

- [ ] **Step 6: Rodar a suíte inteira e regerar o schema**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS

Run: `cd web && npm run api:tipos`
Expected: `schema.d.ts` ganha os dois caminhos novos.

- [ ] **Step 7: A prova de que dois tenants não se atropelam**

Agora existe o segundo tenant, que é o que faltava para fechar o risco do `out/`:

```python
# tests/test_api_asns.py — acrescentar
def test_dois_tenants_com_o_mesmo_token_nao_se_atropelam(api, tmp_path):
    """O mesmo peer cadastrado em duas redes escreve em duas pastas.

    E o motivo de o out/ ter subido para out/<asn>/: com o out/ plano, o
    bloco de uma rede escreveria por cima do da outra, e o diff da tela
    passaria a comparar contra o bloco de outra rede. O que se perde ali e
    o registro de que aquele bloco ja foi colado no equipamento.

    Os dois blocos nao sao iguais: o namespace das communities e o de cada
    rede, e o mesmo cadastro gera blocos diferentes em cada tenant. O que
    se prova aqui e que cada um saiu na pasta dele.
    """
    from test_render import peer_cliente

    from app import peers as mod

    api.post("/api/asns", json={"asn": "64513", "politica": ""})
    pasta = tmp_path / "peers"
    mod.gravar([peer_cliente()], pasta / "64512.yaml")
    mod.gravar([peer_cliente()], pasta / "64513.yaml")

    assert api.post("/api/peers", json=CLIENTE).status_code == 201
    assert api.post("/api/peers", json=CLIENTE,
                    params={"asn": 64513}).status_code == 201

    um = tmp_path / "out" / "64512" / "268127-cliente.txt"
    outro = tmp_path / "out" / "64513" / "268127-cliente.txt"
    assert um.exists() and outro.exists()
    assert um.read_text() != outro.read_text()
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()
```

O import de `CLIENTE` já está no topo do `tests/test_api_asns.py` depois deste passo: acrescente `from dados_api import CLIENTE` à lista.

Run: `.venv/bin/python -m pytest tests/test_api_asns.py -v`
Expected: PASS (11 testes)

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "A tela pode listar e criar tenants

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: O contexto do tenant e as consultas com o ASN

**Files:**
- Create: `web/src/app/tenant.ts`
- Modify: `web/src/app/provedores.tsx`
- Modify: `web/src/api/consultas.ts`, `web/src/api/inicial.ts`, `web/src/api/previa.ts`
- Modify: `web/src/telas/peers/PeerTela.tsx`, `web/src/telas/grupos/GrupoTela.tsx`, `web/src/telas/prefixos/PrefixosTela.tsx` (as 16 chamadas diretas)
- Modify: `web/src/teste/roteador.tsx` (a rota ambiente do `/api/asns`)
- Create: `web/src/app/tenant.test.tsx`

**Interfaces:**
- Consumes: `GET /api/asns` (tarefa 4).
- Produces: `ContextoTenant`, `useAsn()`, `useTenant()`, `lerAsn()`, `gravarAsn(asn)`, e o componente `ProvedorTenant`, que o `Provedores` monta.

- [ ] **Step 1: Escrever o teste que falha**

```tsx
// web/src/app/tenant.test.tsx
import { screen, waitFor } from "@testing-library/react"
import { useContext } from "react"
import { montarRota, mockFetch, peticoes } from "@/teste/roteador"
import { usePeers } from "@/api/consultas"
import { ContextoTenant } from "./tenant"

function Espiao() {
  const { asn, asns } = useContext(ContextoTenant)
  return <p>asn={asn} lista={asns.join(",")}</p>
}

function Peers() {
  usePeers()
  return <p>peers</p>
}

describe("o tenant da aba", () => {
  beforeEach(() => window.sessionStorage.clear())

  it("cai no primeiro da lista quando nao ha nada guardado", async () => {
    mockFetch({ "GET /api/asns": { corpo: ["64512", "264130"] } })
    montarRota([{ path: "/", element: <Espiao /> }])
    expect(await screen.findByText("asn=64512 lista=64512,264130")).toBeTruthy()
  })

  it("usa o que esta guardado quando ele esta na lista", async () => {
    window.sessionStorage.setItem("bgpgen.asn", "264130")
    mockFetch({ "GET /api/asns": { corpo: ["64512", "264130"] } })
    montarRota([{ path: "/", element: <Espiao /> }])
    expect(await screen.findByText("asn=264130 lista=64512,264130")).toBeTruthy()
  })

  it("cai no primeiro quando o guardado sumiu da lista", async () => {
    window.sessionStorage.setItem("bgpgen.asn", "999")
    mockFetch({ "GET /api/asns": { corpo: ["64512"] } })
    montarRota([{ path: "/", element: <Espiao /> }])
    expect(await screen.findByText("asn=64512 lista=64512")).toBeTruthy()
  })

  it("nao dispara consulta de dados antes de saber o ASN", async () => {
    mockFetch({ "GET /api/asns": { corpo: [] } })
    montarRota([{ path: "/", element: <Espiao /> }])
    await waitFor(() => expect(screen.getByText("asn=null lista=")).toBeTruthy())
    expect(peticoes().map((p) => p.caminho)).toEqual(["/api/asns"])
  })

  it("a consulta de peers leva o asn escolhido", async () => {
    window.sessionStorage.setItem("bgpgen.asn", "264130")
    mockFetch({
      "GET /api/asns": { corpo: ["64512", "264130"] },
      "GET /api/peers": { corpo: [] },
    })
    montarRota([{ path: "/", element: <Peers /> }])
    await waitFor(() => expect(peticoes().some((p) => p.caminho === "/api/peers")).toBe(true))
    const pedido = peticoes().find((p) => p.caminho === "/api/peers")!
    expect(pedido.query).toContain("asn=264130")
  })
})
```

O `query` do `Pedido` que o arnês guarda é o que deixa esta última prova existir: o dublê de fetch casa por método e caminho e ignora a query, então sem olhar o `pedido.query` um hook que esquecesse o ASN passaria.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd web && npx vitest run src/app/tenant.test.tsx`
Expected: FAIL: `Cannot find module './tenant'`

- [ ] **Step 3: O módulo do contexto**

`web/src/app/tenant.ts`, no molde do `web/src/app/tema.ts` (contexto e hook no próprio arquivo, porque o `provedores.tsx` exporta componente e misturar os dois quebra o fast refresh):

```ts
import { createContext, useContext } from "react"

const CHAVE = "bgpgen.asn"

/**
 * O ASN da aba, e nao do navegador.
 *
 * O sessionStorage e por aba e morre com ela: duas abas podem estar em
 * redes diferentes ao mesmo tempo, que e a propriedade que a API sem
 * estado com o ?asn= compra. O localStorage seria compartilhado entre as
 * abas da mesma origem e as duas brigariam pelo mesmo valor.
 *
 * Ler e gravar nunca pode derrubar a tela: em janela privada ou com o
 * storage bloqueado por politica, o acesso lanca. Sem ele a escolha vale
 * so enquanto a aba viver, e a tela segue no primeiro da lista.
 */
export function lerAsn(): string | null {
  try {
    return window.sessionStorage.getItem(CHAVE)
  } catch {
    return null
  }
}

export function gravarAsn(asn: string) {
  try {
    window.sessionStorage.setItem(CHAVE, asn)
  } catch {
    // sem storage a escolha nao sobrevive ao recarregamento, e so
  }
}

export type TenantAtual = {
  /** O ASN escolhido, ou null enquanto a lista nao chegou ou esta vazia. */
  asn: string | null
  asns: string[]
  trocar: (asn: string) => void
}

export const ContextoTenant = createContext<TenantAtual>({
  asn: null,
  asns: [],
  trocar: () => {},
})

/** O ASN escolhido. Null antes de a lista chegar, e sem nenhum tenant. */
export function useAsn() {
  return useContext(ContextoTenant).asn
}

export function useTenant() {
  return useContext(ContextoTenant)
}
```

- [ ] **Step 4: O provedor**

`web/src/app/provedores.tsx`, um `ProvedorTenant` no molde do `ProvedorTema`:

```tsx
function ProvedorTenant({ children }: { children: ReactNode }) {
  const lista = useAsns()
  const asns = lista.data ?? []
  const [escolhido, setEscolhido] = useState<string | null>(lerAsn)

  // O guardado vale enquanto estiver na lista, e o `?? asns[0]` e o
  // primeiro boot, a aba nova e o tenant apagado a mao: nos tres a escolha
  // anterior nao existe mais, e cair no primeiro e melhor que ficar sem
  // nenhuma. Nao ha efeito que copie a lista para o estado: o que manda e
  // a lista que chegou, e nao a que estava na tela quando o operador
  // escolheu.
  const asn = escolhido !== null && asns.includes(escolhido)
    ? escolhido
    : (asns[0] ?? null)

  const trocar = useCallback((novo: string) => {
    gravarAsn(novo)
    setEscolhido(novo)
  }, [])

  const valor = useMemo(() => ({ asn, asns, trocar }), [asn, asns, trocar])
  return <ContextoTenant.Provider value={valor}>{children}</ContextoTenant.Provider>
}
```

`Provedores` passa a montá-lo por dentro do `QueryClientProvider` (o provedor usa `useAsns`, que é uma consulta):

```tsx
    <QueryClientProvider client={consultas}>
      <ProvedorTenant>
        <ProvedorTema>
          {children}
          <Toaster position="bottom-right" />
        </ProvedorTema>
      </ProvedorTenant>
    </QueryClientProvider>
```

- [ ] **Step 5: O hook da lista e a chave nova**

Escrevendo o `useAsns`, que é o hook novo e o mais simples de todos:

```ts
export function useAsns() {
  return useQuery({
    queryKey: chaves.asns,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/asns")
      if (error) throw new Error("falha ao listar os ASNs")
      return data
    },
    ...comum,
  })
}
```

com `asns: ["asns"] as const` acrescentado ao objeto `chaves` (`web/src/api/consultas.ts:47-57`).

- [ ] **Step 6: As consultas levam o ASN**

Cada hook de dados passa a ler o ASN e a montá-lo na chave e no pedido. `usePlano` e `usePeers` como modelo:

```ts
export function usePlano() {
  const asn = useAsn()
  return useQuery({
    // o ASN entra na chave: sem ele, o react-query serviria a lista de um
    // tenant enquanto o outro esta selecionado, e a troca mostraria o
    // cadastro da rede errada ate o refetch chegar
    queryKey: [...chaves.plano, asn],
    // sem ASN nao ha o que perguntar: a janela entre a montagem e a lista
    // de ASNs chegando e curta, e uma consulta sem asn seria um 422
    enabled: asn !== null,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/plano", {
        // o `Number` e a conversao de borda: o contexto guarda texto (o que
        // o sessionStorage e a lista do /api/asns devolvem) e o schema tipa
        // o parametro como inteiro. O `enabled` acima garante que a consulta
        // so roda com o ASN na mao, entao o null nao chega aqui
        params: { query: { asn: Number(asn) } },
      })
      if (error) throw new Error("falha ao ler o plano")
      return data
    },
    ...comum,
  })
}
```

O mesmo em `usePeers`, `usePeer`, `useGrupos`, `useGrupo`, `useBlocos` e `useConfig`, com as chaves `[...chaves.peers, asn]` e assim por diante. As invalidações espalhadas pelas telas **não mudam**: `invalidateQueries({ queryKey: chaves.peers })` casa por prefixo e atinge todos os ASNs de uma vez, que é o que se quer depois de salvar.

As chaves que já são função ganham o ASN como último item: `[...chaves.peer(id ?? -1), asn]`.

`web/src/api/inicial.ts` e `web/src/api/previa.ts` seguem o mesmo: os dois recebem o ASN do `useAsn()`, acrescentam-no à chave e mandam `params: { query: { ...params.query, asn } }`. No `usePeerInicial`/`useGrupoInicial` as três chamadas de cada um ganham o `asn` na query; no `usePrevia`, o `params` montado na linha 47 passa a ser `{ params: { query: { id: id ?? undefined, asn: Number(asn) } } }`.

**O `?asn=` é `number`, e não texto.** O `asn: int = Query(...)` do FastAPI sai no schema como inteiro, e o `schema.d.ts` gerado tipa o parâmetro como `number`: um `asn as string` não compila. O contexto guarda texto, porque é o que o `sessionStorage` e a lista do `/api/asns` devolvem, e a conversão mora na borda, na hora da chamada.

- [ ] **Step 7: A rota ambiente no arnês de teste**

`web/src/teste/roteador.tsx`, no `mockFetch`:

```ts
// O provedor de tenant pergunta a lista em toda montagem, e nenhum caso
// monta isso a mao. A rota mora aqui, e quem quiser outra lista passa a
// propria chave no mapa do caso, que vence.
const AMBIENTE: Record<string, Resposta> = {
  "GET /api/asns": { corpo: ["64512"] },
}
```

e a linha do achado passa a ser `const achado = mapa[chave] ?? AMBIENTE[chave]`.

- [ ] **Step 8: As chamadas diretas das telas**

Os hooks (`consultas.ts`, `inicial.ts`, `previa.ts`) já levam o ASN desde o passo 6. O que falta são as chamadas diretas dentro das telas: são 16, e **todas** ganham o ASN, inclusive as de leitura, porque são rotas do mesmo contrato. Esta parte estava na tarefa 6 do plano e subiu para cá porque sem ela o `tsc -b` não fecha, e uma tarefa que termina com o front não compilando não tem como provar o próprio passo de build.

| Arquivo | Linha | Chamada |
| --- | --- | --- |
| `PeerTela.tsx` | 129, 272 | `GET /api/peers/{ident}/saida` |
| `PeerTela.tsx` | 184 | `POST /api/irr` |
| `PeerTela.tsx` | 212 | `POST /api/peers` |
| `PeerTela.tsx` | 213 | `PUT /api/peers/{ident}` |
| `PeerTela.tsx` | 282 | `DELETE /api/peers/{ident}` |
| `GrupoTela.tsx` | 111, 241 | `GET /api/grupos/{ident}/saida` |
| `GrupoTela.tsx` | 149 | `POST /api/irr` |
| `GrupoTela.tsx` | 177 | `POST /api/grupos` |
| `GrupoTela.tsx` | 178 | `PUT /api/grupos/{ident}` |
| `GrupoTela.tsx` | 211 | `GET /api/grupos/novo` |
| `GrupoTela.tsx` | 249 | `DELETE /api/grupos/{ident}` |
| `PrefixosTela.tsx` | 64 | `POST /api/blocos/previa` |
| `PrefixosTela.tsx` | 71 | `PUT /api/blocos` |
| `PrefixosTela.tsx` | 103 | `POST /api/blocos/irr` |

O `ConfiguracoesTela.tsx:38` (`PUT /api/rede`) também entra aqui, e não na tarefa 6: enquanto ele não tiver o `?asn=`, o `tsc -b` não fecha, e uma tarefa que termina com o front não compilando não tem como provar o próprio passo de build. A tarefa 6 fica com o que é de tela nesta mudança: o campo do AS virando leitura, a nota que aponta para o seletor e as asserções do teste que falam do campo.

Duas coisas que **não** são chamadas do cliente tipado, e por isso o `tsc` não cobra, mas quebram igual:

- **O `/base.txt`** é buscado com `fetch` cru em dois lugares (`casca.tsx:32`, no "baixar o bloco base" da paleta, e `BaseTela.tsx:16`): os dois passam a levar o `?asn=`. Sem isso os dois downloads batem numa rota que agora exige o parâmetro, e o sintoma é um 422 no meio de uma ação que não tem nada a ver com o ASN.
- **As chaves de consulta próprias das telas** (as do `saida` do peer e do grupo, e as da prévia dos blocos) são cache como as dos hooks, e sem o ASN na chave a troca de tenant serviria o bloco da rede anterior até o refetch chegar.

O padrão, para a que grava o peer:

```ts
const asn = useAsn()
...
        ? await cliente.POST("/api/peers", {
            params: { query: { asn: Number(asn) } }, body: corpo })
        : await cliente.PUT("/api/peers/{ident}", {
            params: { path: { ident }, query: { asn: Number(asn) } }, body: corpo })
```

As chamadas que já têm `params` só acrescentam o `query` (o `body`, o `signal` e o `path` ficam como estão). O `POST /api/irr` e o `POST /api/blocos/irr` entram na lista: são rotas de dados como as outras.

- [ ] **Step 9: Rodar**

Run: `cd web && npm test`
Expected: PASS. O vitest sozinho não cobra o `asn` — o dublê de fetch casa por método e caminho e ignora a query —, então o verde dele não prova este passo.

Run: `cd web && npm run build`
Expected: PASS (é o `tsc -b` que cobra o `asn` em cada chamada, e é ele que prova o passo 8)

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "O front escolhe o tenant e o leva em toda consulta

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: As escritas do front e o campo AS somente leitura

**Files:**
- Modify: `web/src/telas/configuracoes/ConfiguracoesTela.tsx`
- Modify: os testes dessa tela

**Interfaces:**
- Consumes: `useAsn()` (tarefa 5) e o `PUT /api/rede` sem o `asn` (tarefa 3).
- Produces: nada que outra tarefa consuma.

- [ ] **Step 1: A tela de Configurações**

O `?asn=` desta tela e o corpo do `PUT /api/rede` já foram tratados no passo 8 da tarefa 5: sem isso o `tsc -b` não fechava lá, e o passo de build de quem deixa a linha quebrada não prova nada. O que sobra aqui é o comportamento da tela, que é uma mudança de interface com o operador e merece o próprio gate: o campo do AS vira leitura, com a nota que aponta para o seletor, e as asserções do teste que falam dele acompanham.

`web/src/telas/configuracoes/ConfiguracoesTela.tsx`: o `Input` do AS (linhas 98-106) vira texto.

```tsx
          {/* O campo nao e editavel nesta rodada: quem troca de ASN e o
              seletor da barra lateral, que escolhe outro tenant ou cria um.
              Editar aqui renomearia o arquivo, e o rename fica para a
              rodada seguinte. Sem o rename, um campo que grava e nao muda
              nada seria o campo mentindo. */}
          <Campo nome="asn_rede" rotulo="AS da rede"
                 ajuda="quem troca e o seletor, na barra lateral">
            <Input id="asn_rede" className="dado" value={rede.asn} readOnly />
          </Campo>
```

O `rascunho` deixa de guardar o `asn` (só o `politica`): o `RedeAtual.asn` continua vindo do plano, que é o eco do tenant selecionado. O aviso do fim do fieldset ("Trocar o AS muda o nome de toda community...") passa a dizer o que a troca faz hoje: "Trocar o ASN no seletor muda o nome de toda community e o nome dos arquivos em `out/<ASN>/`."

- [ ] **Step 2: Rodar**

Run: `cd web && npm test && npm run build`
Expected: PASS. Os testes das telas que montam formulário leem a resposta do `PUT /api/rede`; se algum montar o corpo com `asn`, ele quebra aqui, e é o teste certo a mudar.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "As telas gravam no tenant escolhido e o campo do AS vira leitura

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: O seletor, o diálogo de novo ASN e o estado vazio

**Files:**
- Create: `web/src/components/SeletorAsn.tsx`, `web/src/components/DialogoNovoAsn.tsx`, `web/src/components/SemTenant.tsx`
- Modify: `web/src/components/BarraLateral.tsx`, `web/src/app/casca.tsx`
- Create: os testes dos três

**Interfaces:**
- Consumes: `useTenant()` (tarefa 5), `POST /api/asns` (tarefa 4), `chaves.asns` para invalidar.
- Produces: `SeletorAsn({ aoTrocar })`, `DialogoNovoAsn({ aberto, aoFechar, aoCriar })`, `SemTenant()`.

- [ ] **Step 1: O diálogo de novo ASN**

Um `Dialog` (o `web/src/components/ui/dialog.tsx` já existe, é o mesmo do excluir), com dois campos e as mesmas conferências do formulário do AS:

```tsx
export function DialogoNovoAsn({ aberto, aoFechar, aoCriar }: {
  aberto: boolean
  aoFechar: () => void
  aoCriar: (asn: string) => void
}) {
  const [asn, setAsn] = useState("")
  const [politica, setPolitica] = useState("")
  const [erros, setErros] = useState<Record<string, string>>({})
  const consultas = useQueryClient()

  const criar = useMutation({
    mutationFn: () => cliente.POST("/api/asns", {
      body: { asn, politica },
    }),
    onSuccess: (r) => {
      if (r.error) {
        if (falhaDoServidor(r.response.status)) avisarFalhaDeRede(() => criar.mutate())
        setErros(lerRecusa(r.error).erros)
        return
      }
      setErros({})
      setAsn("")
      setPolitica("")
      void consultas.invalidateQueries({ queryKey: chaves.asns })
      aoCriar(asn)
    },
    onError: () => avisarFalhaDeRede(() => criar.mutate()),
  })
```

Os dois campos são `Campo nome="asn_rede" rotulo="AS da rede"` e `Campo nome="asn_politica" rotulo="Namespace das standard"`, iguais aos das Configurações, com `inputMode="numeric"` e a mesma ajuda. Os nomes têm que ser exatamente estes: são as chaves com que o `POST /api/asns` devolve os erros, e um `nome` diferente faz a recusa voltar sem pintar campo nenhum. O `aoCriar` recebe o ASN que acabou de ser criado, para o seletor já trocar para ele.

- [ ] **Step 2: O seletor**

`web/src/components/SeletorAsn.tsx`: um `DropdownMenu` no molde do "novo" que já está na barra lateral (composição por `render`, `onClick`, e não `onSelect`):

```tsx
export function SeletorAsn() {
  const { asn, asns, trocar } = useTenant()
  const [novoAberto, setNovoAberto] = useState(false)
  const navegar = useNavigate()
  const { pathname } = useLocation()

  const escolher = (novo: string) => {
    if (novo === asn) return
    trocar(novo)
    // o registro aberto e do tenant antigo: /peers/3 nao existe do outro
    // lado, ou e outro peer. A lista da rede nova e o destino
    if (/^\/(peers|grupos)\//.test(pathname)) navegar("/peers")
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button variant="ghost" size="sm" className="dado px-1" />}>
          <span className="flex items-center gap-1">
            AS{asn ?? "..."}
            <ChevronDown className="size-3" />
          </span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {asns.map((outro) => (
            <DropdownMenuItem key={outro} onClick={() => escolher(outro)}
                              aria-current={outro === asn ? "true" : undefined}>
              AS{outro}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setNovoAberto(true)}>novo ASN</DropdownMenuItem>
          <DropdownMenuItem onClick={() => navegar("/configuracoes")}>
            configurações
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <DialogoNovoAsn aberto={novoAberto} aoFechar={() => setNovoAberto(false)}
                      aoCriar={(novo) => { setNovoAberto(false); escolher(novo) }} />
    </>
  )
}
```

O `DropdownMenuSeparator` já está exportado (`web/src/components/ui/dropdown-menu.tsx:260`), como as outras peças que este arquivo usa.

- [ ] **Step 3: A barra lateral usa o seletor**

`web/src/components/BarraLateral.tsx:50-55`: o `Link to="/configuracoes"` com `AS{asn}` dá lugar ao `<SeletorAsn />`, e a prop `asn` sai do componente (o seletor lê do contexto). `web/src/app/casca.tsx:42-49` deixa de passar `asn={plano.data?.rede.asn ?? ""}`.

- [ ] **Step 4: O estado vazio**

`web/src/components/SemTenant.tsx`: explica que `peers/` está vazia, mostra o caminho do checkout e um botão "criar o primeiro ASN" que abre o mesmo `DialogoNovoAsn`.

Em `web/src/app/casca.tsx`:

```tsx
export function Casca() {
  const { asn, asns } = useTenant()
  ...
  // Sem tenant nao ha o que listar nem o que consultar: as consultas abaixo
  // saem desabilitadas pelo proprio useAsn nulo, e a casca desenha a tela
  // que explica o que fazer. O `asns.length === 0` e o unico caso em que
  // isso acontece, porque com lista o `asn` nunca e nulo.
  if (asns.length === 0) return <SemTenant />
```

- [ ] **Step 5: Os testes**

```tsx
// web/src/components/SeletorAsn.test.tsx
it("troca de tenant e leva para a lista", async () => { ... })
it("criar um ASN novo ja o seleciona", async () => { ... })
it("o ASN sem cadastro recusa e mostra o erro no campo", async () => { ... })

// web/src/components/SemTenant.test.tsx
it("sem nenhum tenant, a casca explica e oferece criar o primeiro", async () => { ... })
```

O teste do criar confere a petição: `peticoes().find((p) => p.caminho === "/api/asns")` com `metodo === "POST"`.

- [ ] **Step 6: Rodar**

Run: `cd web && npm test && npm run build && npm run lint`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "A barra lateral escolhe e cria o tenant

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: A troca de tenant com rascunho sujo

**Files:**
- Create: `web/src/app/rascunho.ts`
- Modify: `web/src/app/casca.tsx`, `web/src/components/SeletorAsn.tsx`, `web/src/components/BarraLateral.tsx`
- Modify: `web/src/telas/peers/PeerTela.tsx`, `web/src/telas/grupos/GrupoTela.tsx`, `web/src/telas/prefixos/PrefixosTela.tsx`
- Create: `web/src/app/rascunho.test.tsx`

**Interfaces:**
- Consumes: o `sujo` que as três telas já calculam e passam para o `AvisoNaoSalvo`.
- Produces: `ContextoRascunho`, `usePublicarRascunho(sujo)`.

- [ ] **Step 1: Escrever o teste que falha**

```tsx
// web/src/app/rascunho.test.tsx
it("trocar de tenant com rascunho sujo pergunta antes", async () => { ... })
it("cancelar mantem o tenant e o rascunho", async () => { ... })
it("confirmar troca o tenant e sai para /peers", async () => { ... })
```

- [ ] **Step 2: O contexto do rascunho**

`web/src/app/rascunho.ts`: um contexto de escrita (a tela publica o `sujo`) e um de leitura (o seletor lê), no molde do `acoes-contexto.ts`. Diferente do `usePublicarAcoes`, aqui o valor é um booleano e **não** pode ser um objeto estável com funções: quem lê precisa re-renderizar quando ele muda. Então o caminho é um `useState` na casca:

```ts
export const ContextoDefinirRascunho = createContext<(sujo: boolean) => void>(() => {})
export const ContextoLerRascunho = createContext<boolean>(false)

/**
 * Publica se a tela aberta tem alteracao nao salva. Quem chama sao as telas
 * de formulario, no mesmo lugar em que ja publicam o `aoSalvar`.
 *
 * O valor e do render, e nao de um ref: a casca precisa re-renderizar
 * quando ele muda, e um objeto estavel com uma funcao dentro nao a faria
 * re-renderizar. O efeito com o cleanup devolve `false` na saida, para a
 * tela que sai nao deixar o rascunho dela valendo para a proxima.
 */
export function usePublicarRascunho(sujo: boolean) {
  const definir = useContext(ContextoDefinirRascunho)
  useEffect(() => {
    definir(sujo)
    return () => definir(false)
  }, [definir, sujo])
}
```

- [ ] **Step 3: Ligar na casca e nas telas**

`web/src/app/casca.tsx` guarda `const [sujo, setSujo] = useState(false)` e envolve a árvore nos dois contextos; passa `sujo` para a `BarraLateral` (e ela, para o `SeletorAsn`). `PeerTela.tsx`, `GrupoTela.tsx` e `PrefixosTela.tsx` chamam `usePublicarRascunho(sujo)` onde já calculam o `sujo` do `AvisoNaoSalvo`.

- [ ] **Step 4: A pergunta antes de trocar**

No `escolher` do `SeletorAsn`:

```tsx
  const [pendente, setPendente] = useState<string | null>(null)

  const escolher = (novo: string) => {
    if (novo === asn) return
    // A pergunta vem antes da troca, e nao da navegacao: o useBlocker do
    // AvisoNaoSalvo barraria a rota depois de o ASN ja ter mudado, e a tela
    // do peer antigo ficaria de pe consultando o tenant novo
    if (sujo) {
      setPendente(novo)
      return
    }
    aplicar(novo)
  }

  const aplicar = (novo: string) => {
    trocar(novo)
    if (/^\/(peers|grupos)\//.test(pathname)) navegar("/peers")
  }
```

e um diálogo com o mesmo texto do `AvisoNaoSalvo` ("Há alterações que ainda não foram para o `peers.yaml`.", "continuar editando" / "trocar sem salvar"), que no confirmar chama `aplicar(pendente)`.

- [ ] **Step 5: Rodar**

Run: `cd web && npm test && npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "A troca de tenant pergunta antes de perder o rascunho

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 9: O e2e, o `.gitignore` e a documentação

**Files:**
- Move: `web/e2e/peers.yaml` → `web/e2e/peers/64512.yaml`
- Modify: `web/e2e/global-setup.ts:30`
- Modify: `.gitignore`, `README.md`, `CLAUDE.md`, `compose.example.yaml`

**Interfaces:**
- Consumes: tudo.
- Produces: nada.

- [ ] **Step 1: O fixture do e2e**

```bash
mkdir -p web/e2e/peers && git mv web/e2e/peers.yaml web/e2e/peers/64512.yaml
```

`web/e2e/global-setup.ts:30`:

```ts
// o cadastro do e2e vai para a pasta de tenants, com o nome do ASN que ele
// declara dentro: e o nome do arquivo que manda, e um `peers.yaml` na raiz
// seria migrado pelo boot, com .bak e log, a cada subida do uvicorn
mkdirSync(`${temp}/peers`, { recursive: true })
cpSync(`${repo}/web/e2e/peers/64512.yaml`, `${temp}/peers/64512.yaml`)
```

- [ ] **Step 2: Rodar o e2e**

Run: `cd web && npm run e2e`
Expected: PASS nos 12 casos. O provedor cai no primeiro tenant da lista, que é o único, então nenhum fluxo muda. Se algum caso falhar por 404, é a lista de `/api/asns` não chegando: confira o `BGPGEN_WEB` e o log do uvicorn em `web/e2e/.tmp`.

- [ ] **Step 3: O `.gitignore`**

```gitignore
# saida gerada: derivada do tenant, nao e fonte. A pasta por ASN entra
# inteira: out/*.txt nao casa com out/264130/blocos.txt, e sem esta linha os
# blocos de producao aparecem como nao rastreados e entram num `git add .`
out/*/
out/.cache/

peers/
peers.yaml.bak

# excecao: o cadastro do e2e e fixture do repositorio; o peers/ ignorado
# acima e o do equipamento
!web/e2e/peers/

# o cadastro de antes da pasta dos tenants: quem migra e o boot, e o .bak
# fica para tras
peers.yaml
```

Confira com `git status --short` que `web/e2e/peers/64512.yaml` continua rastreado (`git check-ignore -v web/e2e/peers/64512.yaml` não pode acusar nada) e que um `out/64512/blocos.txt` de teste não aparece.

- [ ] **Step 4: A documentação**

- `README.md`: onde fala do `peers.yaml` como o estado do app (o mapa dos arquivos e o "Ordem de colagem no F1A"), passa a falar de `peers/<ASN>.yaml` e `out/<ASN>/`; a seção do e2e (linha 145) fala do `peers.yaml` temporário, que agora é uma pasta.
- `CLAUDE.md`: o "Repository overview" diz que o app serve "os blocos gerados em `out/`"; passa a `out/<ASN>/`, e a linha que descreve o `peers.yaml` vira a pasta. O "Document map" continua valendo: o `PLANO.md` não muda nesta etapa.
- `compose.example.yaml`: o comentário do bind mount fala do `peers.yaml` e do `out/`; passa a falar da pasta `peers/`.
- **Comentários que ficaram velhos nas tarefas anteriores**, apontados pela revisão da tarefa 3: `app/auth.py:68` cita "o `_yaml()` do api.py", que não existe mais; `app/app.py:5` diz que o estado é o `peers.yaml`; `app/app.py:109` fala de "como fazem com o PEERS_YAML"; e `app/api.py:360` diz que o `_ler` lê "o que esta salvo em out/", que agora é `out/<ASN>/`. Nenhum é erro de comportamento, e todos são o tipo de coisa que a próxima pessoa lê como verdade.

- [ ] **Step 5: A conferência final**

Run: `.venv/bin/python -m pytest -q && cd web && npm test && npm run build && npm run lint && npm run api:conferir`
Expected: tudo PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "O e2e, o gitignore e a documentacao sabem da pasta dos tenants

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Notas para quem executa

- **A ordem importa.** A tarefa 3 quebra o front de propósito (as chamadas passam a precisar do `?asn=`), e ele só volta a funcionar na tarefa 5. Quando o front fosse compilado entre a 3 e a 5, o `npm run build` reprova. Isso é esperado: quem guarda a tarefa 3 é o pytest.
- **O e2e é a única prova do conjunto**, e roda na tarefa 9. Se algo ficou inconsistente entre o contrato e o front, é lá que aparece.
- **Nada de renomear arquivo de tenant nesta rodada.** O campo do AS fica somente leitura na tarefa 6, e o rename (editar o ASN, mover o `.yaml` e o `out/`) é a rodada seguinte.
- **A chave `asn:` dentro do arquivo é cópia de leitura.** Se um teste seu precisar mudá-la, o teste está errado: quem manda é o nome.
