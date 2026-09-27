# Autenticação do bgpgen: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pôr um login na frente do bgpgen, com um admin criado no primeiro boot e senha aleatória impressa uma vez no log.

**Architecture:** Um módulo novo, `app/auth.py`, guarda o `usuarios.yaml` (hash scrypt da senha e o segredo que assina o cookie), roda o bootstrap no `lifespan` do FastAPI e expõe a dependência `exigir_login`. A sessão é um cookie `httpOnly` assinado com HMAC, sem estado no processo. Em `/api` entram três rotas públicas (login, logout e sessão) e o resto do roteador passa a exigir cookie; `/base.txt`, `/docs` e `/openapi.json` entram junto. No front, uma tela de login fora da casca, uma guarda que consulta `/api/sessao` e um middleware no cliente que reage ao 401.

**Tech Stack:** Python 3.14 + FastAPI (stdlib apenas: `hashlib.scrypt`, `hmac`, `secrets`, `base64`), React 19 + react-router 7 + TanStack Query + openapi-fetch, pytest, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-27-autenticacao-design.md`

## Constraints globais

- **Sem dependência nova.** O `requirements.txt` e o `web/package.json` não ganham linha. Todo o hash e toda a assinatura saem da stdlib.
- **ASCII no Python.** Comentários e mensagens do `app/` são sem acento, como o resto do pacote: a saída de log e as mensagens de erro viajam por terminal e por container.
- **Estado é arquivo YAML na raiz, lido do disco a cada uso, nunca no import.** O caminho mora numa constante de módulo patchável (`auth.USUARIOS_YAML`, como `peers.PEERS_YAML`), e é isso que os testes trocam.
- **Uma forma de erro só:** toda recusa da API é `{"erros": {campo: mensagem}, "avisos": []}` (`ErroResposta`). O 401 entra nesse formato, e não no `{"detail": ...}` do FastAPI.
- **Nada de segredo no repositório:** `usuarios.yaml` entra no `.gitignore` e no `.dockerignore` na mesma tarefa que cria o arquivo.
- **Nunca commitar direto na branch de trabalho compartilhada.** A implementação roda numa worktree (superpowers:using-git-worktrees), uma por plano.

## Review Focus

O que a spec implica e nenhum teste de tarefa cobre sozinho, na ordem em que é mais provável morder quem usa:

1. **Login com senha errada não pode disparar o "sessão caiu".** O 401 do `/api/login` é senha errada, e não sessão expirada. Se o middleware do cliente tratar os dois igual, a tela de login recarrega a cada tentativa e apaga a mensagem e a senha digitada. Teste na Task 5.
2. **F5 na tela de login.** `/login` precisa estar na lista de rotas da SPA em `app/app.py`, senão o servidor responde 404 antes de o React existir. Passa no `npm run dev` e quebra em produção. Teste na Task 4.
3. **`usuarios.yaml` apagado com o app de pé.** Vira 401 em tudo, inclusive no login, e não 500 nem app aberto: o bootstrap só roda no boot. Teste na Task 4.
4. **`usuarios.yaml` com a chave faltando** (editado à mão). O login precisa dar 500 com a mensagem nomeando o arquivo, e não um 401 enganoso que faz o operador procurar a senha errada. Teste na Task 4.
5. **Cookie de outro segredo, ou de um arquivo anterior.** Trocar o `usuarios.yaml` tem que derrubar toda sessão aberta, que é o único jeito de revogar uma. Teste na Task 2.

## Antes da Task 1: a worktree

A implementação roda numa worktree isolada, criada com a skill **superpowers:using-git-worktrees** a partir da `main` (que já tem o spec em `9e05d06`). Nada de implementar no checkout principal.

Dentro da worktree, o `.venv/` e o `web/node_modules/` não existem (os dois são ignorados pelo git). Duas saídas:

```bash
# a completa: instala tudo de novo na worktree
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd web && npm ci

# a rapida: empresta o que ja esta instalado no checkout principal
ln -s /Users/diorgera/Projetos/POLITICA_BGP/.venv .venv
ln -s /Users/diorgera/Projetos/POLITICA_BGP/web/node_modules web/node_modules
```

Com o último comando, `.venv/bin/python -m pytest` roda da worktree com o Python do checkout principal, e o `import app` resolve para os arquivos da worktree porque o `python -m` põe o diretório corrente no começo do `sys.path`. O `bgpq4` não é preciso: a suíte o substitui por um duble (`tests/conftest.py:15`).

Os comandos deste plano:

| O quê | Comando |
| --- | --- |
| Suíte do Python | `.venv/bin/python -m pytest tests/test_auth.py -v` (ou sem o arquivo, para tudo) |
| Testes do front | `cd web && npm test` |
| Tipos do front | `cd web && npm run api:tipos` |
| e2e | `cd web && npm run e2e` |

---

### Task 1: `app/auth.py`, o arquivo de usuários e a senha

**Files:**
- Create: `app/auth.py`
- Create: `tests/test_auth.py`
- Modify: `.gitignore` (junto da linha `peers.yaml`, que está na 34)
- Modify: `.dockerignore` (junto da linha `out/`, que está na 16)

**Interfaces:**
- Consumes: nada. É o primeiro módulo da etapa.
- Produces:
  - `auth.USUARIOS_YAML: Path` (patchável), `auth.COOKIE: str = "bgpgen_sessao"`, `auth.NOME_ADMIN: str = "admin"`, `auth.VALIDADE: int` (segundos), `auth.SCRYPT_N/R/P: int`, `auth.DKLEN: int = 32`
  - `auth.carregar(caminho=USUARIOS_YAML) -> dict`
  - `auth.escrever(dados: dict, caminho=USUARIOS_YAML) -> None`
  - `auth.gerar_senha() -> str`
  - `auth.criar_admin(senha: str, caminho=USUARIOS_YAML) -> dict`
  - `auth.bootstrap(caminho=USUARIOS_YAML, senha: str | None = None) -> str | None`
  - `auth.conferir(usuario: str, senha: str, caminho=USUARIOS_YAML) -> bool`
  - `auth.NaoAutenticado(Exception)` (declarada aqui, usada na Task 2)

- [ ] **Step 1: Escrever os testes que falham**

Cria `tests/test_auth.py`:

```python
"""O login: o arquivo de usuarios, a senha e a sessao.

O bootstrap e o caminho de verdade do admin, entao os testes o chamam
direto (e nao pelo lifespan do app): quem exercita o lifespan e a fixture
`api` do conftest.
"""

import stat

import pytest

from app import auth

SENHA = "senha-de-teste"


@pytest.fixture
def caminho(tmp_path, monkeypatch):
    """O usuarios.yaml em tmp_path, com a senha de teste no ambiente."""
    monkeypatch.setattr(auth, "USUARIOS_YAML", tmp_path / "usuarios.yaml")
    monkeypatch.setenv("BGPGEN_ADMIN_SENHA", SENHA)
    return tmp_path / "usuarios.yaml"


def test_o_boot_cria_o_admin_e_imprime_a_senha(caminho, capsys):
    senha = auth.bootstrap()

    assert senha == SENHA
    assert "senha: %s" % SENHA in capsys.readouterr().out
    assert auth.conferir(auth.NOME_ADMIN, SENHA)


def test_o_boot_sem_a_variavel_sorteia_a_senha(caminho, monkeypatch, capsys):
    monkeypatch.delenv("BGPGEN_ADMIN_SENHA")

    senha = auth.bootstrap()

    assert len(senha) >= 16
    assert senha in capsys.readouterr().out
    assert auth.conferir(auth.NOME_ADMIN, senha)


def test_o_boot_com_usuario_nao_toca_no_arquivo(caminho, capsys):
    auth.bootstrap()
    antes = caminho.read_bytes()
    capsys.readouterr()

    assert auth.bootstrap() is None
    assert caminho.read_bytes() == antes
    assert capsys.readouterr().out == ""


def test_o_boot_com_arquivo_vazio_cria_o_admin(caminho):
    # arquivo de zero byte e o mesmo caso do arquivo ausente: nao ha usuario
    caminho.write_text("")

    assert auth.bootstrap() == SENHA
    assert auth.conferir(auth.NOME_ADMIN, SENHA)


def test_o_arquivo_nasce_so_para_o_dono(caminho):
    auth.bootstrap()

    modo = stat.S_IMODE(caminho.stat().st_mode)
    assert modo == 0o600, oct(modo)


def test_a_senha_certa_confere_e_a_errada_nao(caminho):
    auth.bootstrap()

    assert auth.conferir(auth.NOME_ADMIN, SENHA)
    assert not auth.conferir(auth.NOME_ADMIN, "outra")
    assert not auth.conferir(auth.NOME_ADMIN, "")


def test_usuario_que_nao_existe_nao_confere(caminho):
    auth.bootstrap()

    assert not auth.conferir("ninguem", SENHA)


def test_o_hash_nao_guarda_a_senha(caminho):
    auth.bootstrap()

    assert SENHA not in caminho.read_text(encoding="utf-8")


def test_o_boot_de_um_segundo_app_acha_o_admin_do_primeiro(caminho):
    auth.bootstrap()
    dados = auth.carregar()

    assert dados["segredo"]
    assert set(dados["usuarios"]) == {auth.NOME_ADMIN}
    assert dados["usuarios"][auth.NOME_ADMIN]["n"] == auth.SCRYPT_N


def test_o_boot_sem_poder_gravar_falha(tmp_path, monkeypatch):
    """Volume somente leitura: um app que sobe aberto e pior que um que nao sobe.
    """
    travado = tmp_path / "travado"
    travado.mkdir()
    monkeypatch.setattr(auth, "USUARIOS_YAML", travado / "usuarios.yaml")
    monkeypatch.setenv("BGPGEN_ADMIN_SENHA", SENHA)
    travado.chmod(0o500)
    try:
        with pytest.raises(OSError):
            auth.bootstrap()
    finally:
        # sem devolver a permissao, o tmp_path nao pode ser limpo no fim do caso
        travado.chmod(0o700)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: erro de coleta, `ModuleNotFoundError: No module named 'app.auth'`.

- [ ] **Step 3: Escrever o módulo**

Cria `app/auth.py`:

```python
"""O login do bgpgen: o usuarios.yaml, a senha e a sessao.

O arquivo tem dois papeis, e os dois nascem no mesmo boot. `usuarios`
guarda o hash da senha de cada usuario; `segredo` assina o cookie de
sessao. Perder um sem o outro nao serve para nada: sem usuario nao ha
quem entre, e sem segredo nao ha cookie que valha.

O arquivo e lido do disco a cada login e a cada requisicao protegida, como
o peers.yaml e lido a cada requisicao. O operador que quiser outra senha
apaga o arquivo e reinicia, e nada fica preso no processo.

Nao ha dependencia de fora: o scrypt, o hmac e o secrets sao da stdlib, e
o requirements.txt nao ganha linha.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
USUARIOS_YAML = RAIZ / "usuarios.yaml"

COOKIE = "bgpgen_sessao"
NOME_ADMIN = "admin"

# O custo do scrypt, medido em 27ms por conferencia no venv do checkout.
# Ele fica gravado em cada usuario, e nao so fixo aqui, para que aumentar
# estes numeros depois nao invalide o hash que ja esta no arquivo: quem
# confere usa os numeros que leu de la.
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
DKLEN = 32

# sete dias, desde o login. Nao ha renovacao deslizante: a validade e a
# mesma do primeiro ao ultimo pedido da sessao
VALIDADE = 7 * 24 * 60 * 60


class NaoAutenticado(Exception):
    """A recusa das rotas protegidas.

    Quem a transforma em 401 e o handler registrado no instalar() do
    api.py, no mesmo formato das outras recusas da API.
    """


def carregar(caminho=USUARIOS_YAML):
    """O dicionario do arquivo, ou {} quando ele nao existe."""
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def escrever(dados, caminho=USUARIOS_YAML):
    """Grava o arquivo com permissao 0600.

    O modo vai no open, e nao num chmod depois: entre um e outro o
    arquivo existiria legivel para todo mundo. O 0600 e o que segura o
    hash da senha e o segredo do cookie.
    """
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = yaml.safe_dump(dados, allow_unicode=False, sort_keys=False)
    descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto)


def _b64(bruto):
    return base64.urlsafe_b64encode(bruto).decode("ascii").rstrip("=")


def _de_b64(texto):
    # o padding sai na escrita e volta aqui: sem ele o base64url nao fecha
    # o ultimo grupo, e o b64decode recusa
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _hash(senha, salt, n=None, r=None, p=None):
    return hashlib.scrypt(senha.encode("utf-8"), salt=salt,
                          n=n or SCRYPT_N, r=r or SCRYPT_R,
                          p=p or SCRYPT_P, dklen=DKLEN)


def _registro(caminho, usuario):
    """O usuario do arquivo, ou None. Chave faltando e erro com nome.

    Um arquivo editado a mao pode perder uma das chaves do hash, e o
    KeyError cru nao diria nem qual arquivo nem qual usuario.
    """
    registro = (carregar(caminho).get("usuarios") or {}).get(usuario)
    if registro is None:
        return None
    for chave in ("salt", "hash", "n", "r", "p"):
        if chave not in registro:
            raise ValueError("%s: usuario %s sem a chave %s"
                             % (caminho, usuario, chave))
    return registro


def gerar_senha():
    """A senha do admin novo: 12 bytes sorteados, 16 caracteres."""
    return secrets.token_urlsafe(12)


def criar_admin(senha, caminho=USUARIOS_YAML):
    """Grava um arquivo novo, com o admin e um segredo de sessao.

    O arquivo inteiro e reescrito: e o primeiro boot, nao ha nada para
    preservar.
    """
    salt = secrets.token_bytes(16)
    dados = {
        "segredo": _b64(secrets.token_bytes(32)),
        "usuarios": {
            NOME_ADMIN: {"salt": _b64(salt), "hash": _b64(_hash(senha, salt)),
                         "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P},
        },
    }
    escrever(dados, caminho)
    return dados


def _anunciar(senha):
    """A senha sai no log e nao vai para arquivo nenhum.

    E print, e nao logging: o app nao configura logger nenhum, e o root
    logger nao imprime INFO por padrao. O flush entrega a linha na hora
    do boot, e nao no proximo buffer do uvicorn.
    """
    print("\n".join([
        "==================== bgpgen ====================",
        " admin criado. usuario: %s" % NOME_ADMIN,
        " senha: %s" % senha,
        " esta senha nao aparece de novo. Para trocar,",
        " apague usuarios.yaml e reinicie o app.",
        "================================================",
    ]), flush=True)


def bootstrap(caminho=USUARIOS_YAML, senha=None):
    """Cria o admin quando nao ha nenhum, e devolve a senha criada.

    Roda no lifespan do FastAPI: uma vez por processo, antes da primeira
    requisicao. Com usuario no arquivo nao faz nada e nao imprime nada,
    que e o caso de todo boot depois do primeiro.

    A senha vem do BGPGEN_ADMIN_SENHA quando a variavel esta no ambiente
    (o e2e e uma subida automatizada usam isso) e do secrets quando nao
    esta.
    """
    if carregar(caminho).get("usuarios"):
        return None
    senha = senha or os.environ.get("BGPGEN_ADMIN_SENHA") or gerar_senha()
    criar_admin(senha, caminho)
    _anunciar(senha)
    return senha


def conferir(usuario, senha, caminho=USUARIOS_YAML):
    """A senha confere? A comparacao final e em tempo constante.

    O usuario que nao existe nao gasta scrypt nenhum. O nome do admin nao
    e segredo: ele sai impresso no boot e a tela o preenche sozinho, entao
    nao ha o que esconder no tempo de resposta.
    """
    registro = _registro(caminho, usuario)
    if registro is None:
        return False
    obtido = _hash(senha, _de_b64(registro["salt"]),
                   registro["n"], registro["r"], registro["p"])
    return hmac.compare_digest(obtido, _de_b64(registro["hash"]))
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: 10 passed.

- [ ] **Step 5: Guardar o arquivo do git e da imagem**

Em `.gitignore`, logo depois da linha `peers.yaml` (linha 34):

```gitignore
# o login: hash da senha e o segredo que assina o cookie. O arquivo nasce
# no primeiro boot do app, e nao vem do repositorio
usuarios.yaml
```

Em `.dockerignore`, depois de `out/` (linha 16):

```dockerignore
# o login: hash da senha e o segredo do cookie, que sao do disco de quem roda
usuarios.yaml
```

- [ ] **Step 6: Conferir que os dois ignoram de verdade**

```bash
touch usuarios.yaml
git status --short          # nao pode listar usuarios.yaml
git check-ignore -v usuarios.yaml
rm usuarios.yaml
```

Expected: `git check-ignore` imprime a linha do `.gitignore` que casou.

- [ ] **Step 7: Commit**

```bash
git add app/auth.py tests/test_auth.py .gitignore .dockerignore
git commit -m "O auth.py guarda a senha do admin e cria o primeiro no boot

scrypt da stdlib no hash, arquivo 0600, e a senha sorteada sai no log
uma vez. Sem dependencia nova, e o usuarios.yaml fica fora do git e da
imagem."
```

---

### Task 2: a sessão em cookie assinado

**Files:**
- Modify: `app/auth.py` (acrescenta o bloco da sessão no fim)
- Modify: `tests/test_auth.py`

**Interfaces:**
- Consumes: `auth.carregar`, `auth._b64`, `auth._de_b64`, `auth.NaoAutenticado`, `auth.VALIDADE`, `auth.COOKIE`.
- Produces:
  - `auth.seguro() -> bool`
  - `auth.assinatura(usuario: str, expira: int, segredo: str) -> str`
  - `auth.abrir_sessao(resposta: Response, usuario: str, caminho=USUARIOS_YAML) -> None`
  - `auth.fechar_sessao(resposta: Response) -> None`
  - `auth.da_requisicao(request: Request, caminho=USUARIOS_YAML) -> str | None`
  - `auth.exigir_login(request: Request) -> str` (levanta `NaoAutenticado`)

- [ ] **Step 1: Escrever os testes que falham**

Os imports do bloco abaixo vão para o topo do arquivo, que passa a ficar assim:

```python
import stat
import time
from types import SimpleNamespace

import pytest
from fastapi import Response

from app import auth
```

E os casos novos vão ao fim do arquivo:

```python
def _resposta():
    """Uma Response solta, que e onde o cookie e escrito."""
    return Response()


def _pedido(cookie=None):
    """O minimo que o da_requisicao le de um Request."""
    return SimpleNamespace(cookies={} if cookie is None else {auth.COOKIE: cookie})


def test_o_cookie_aberto_volta_com_o_usuario(caminho):
    auth.bootstrap()
    resposta = _resposta()

    auth.abrir_sessao(resposta, auth.NOME_ADMIN)
    cookie = resposta.headers["set-cookie"]

    assert auth.COOKIE in cookie
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    valor = cookie.split("%s=" % auth.COOKIE, 1)[1].split(";", 1)[0]
    assert auth.da_requisicao(_pedido(valor)) == auth.NOME_ADMIN


def test_o_cookie_de_outro_segredo_nao_vale(caminho):
    auth.bootstrap()
    resposta = _resposta()
    auth.abrir_sessao(resposta, auth.NOME_ADMIN)
    valor = resposta.headers["set-cookie"].split("%s=" % auth.COOKIE, 1)[1].split(";", 1)[0]

    # o operador apagou o usuarios.yaml e o app criou outro, com outro segredo:
    # e assim que se revoga uma sessao aberta
    caminho.unlink()
    auth.criar_admin("outra-senha", caminho)

    assert auth.da_requisicao(_pedido(valor)) is None


def test_o_cookie_com_a_assinatura_torta_nao_vale(caminho):
    auth.bootstrap()
    expira = int(time.time()) + 60
    valor = "%s.%d.%s" % (auth.NOME_ADMIN, expira, "0" * 64)

    assert auth.da_requisicao(_pedido(valor)) is None


def test_o_cookie_vencido_nao_vale(caminho):
    auth.bootstrap()
    dados = auth.carregar()
    expira = int(time.time()) - 1
    valor = "%s.%d.%s" % (auth.NOME_ADMIN, expira,
                          auth.assinatura(auth.NOME_ADMIN, expira, dados["segredo"]))

    assert auth.da_requisicao(_pedido(valor)) is None


def test_o_cookie_sem_os_tres_pedacos_nao_vale(caminho):
    auth.bootstrap()

    assert auth.da_requisicao(_pedido("admin")) is None
    assert auth.da_requisicao(_pedido("admin.123")) is None
    assert auth.da_requisicao(_pedido("")) is None


def test_usuario_com_ponto_no_nome_nao_vira_outro_usuario(caminho):
    auth.bootstrap()
    dados = auth.carregar()
    # um nome com ponto so sobrevive ao rsplit: com um split cru, o usuario
    # lido seria o pedaco errado, e a sessao de "a.b" viraria a de "a"
    expira = int(time.time()) + 60
    valor = "a.b.%d.%s" % (expira, auth.assinatura("a.b", expira, dados["segredo"]))

    assert auth.da_requisicao(_pedido(valor)) == "a.b"


def test_sem_usuarios_yaml_nao_ha_sessao(caminho):
    auth.bootstrap()
    resposta = _resposta()
    auth.abrir_sessao(resposta, auth.NOME_ADMIN)
    valor = resposta.headers["set-cookie"].split("%s=" % auth.COOKIE, 1)[1].split(";", 1)[0]

    caminho.unlink()

    # arquivo ausente e o estado "ninguem entrou ainda", e nao erro de
    # leitura: a sessao antiga nao vale mais, e nada estoura
    assert auth.da_requisicao(_pedido(valor)) is None


def test_usuarios_yaml_sem_segredo_e_erro_com_nome(caminho):
    auth.escrever({"usuarios": {}}, caminho)

    with pytest.raises(ValueError) as erro:
        auth.da_requisicao(_pedido("admin.1.x"))

    assert str(caminho) in str(erro.value)


def test_fechar_sessao_zera_o_cookie(caminho):
    resposta = _resposta()

    auth.fechar_sessao(resposta)

    cookie = resposta.headers["set-cookie"]
    assert "%s=" % auth.COOKIE in cookie
    assert "Max-Age=0" in cookie or "expires" in cookie.lower()


def test_exigir_login_devolve_o_usuario_e_recusa_sem_cookie(caminho):
    auth.bootstrap()
    resposta = _resposta()
    auth.abrir_sessao(resposta, auth.NOME_ADMIN)
    valor = resposta.headers["set-cookie"].split("%s=" % auth.COOKIE, 1)[1].split(";", 1)[0]

    assert auth.exigir_login(_pedido(valor)) == auth.NOME_ADMIN
    with pytest.raises(auth.NaoAutenticado):
        auth.exigir_login(_pedido())


def test_o_cookie_so_vai_com_secure_quando_a_variavel_pede(caminho, monkeypatch):
    auth.bootstrap()

    monkeypatch.delenv("BGPGEN_COOKIE_SEGURO", raising=False)
    sem_variavel = _resposta()
    auth.abrir_sessao(sem_variavel, auth.NOME_ADMIN)
    assert "Secure" not in sem_variavel.headers["set-cookie"]

    monkeypatch.setenv("BGPGEN_COOKIE_SEGURO", "1")
    com_variavel = _resposta()
    auth.abrir_sessao(com_variavel, auth.NOME_ADMIN)
    assert "Secure" in com_variavel.headers["set-cookie"]
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: `AttributeError: module 'app.auth' has no attribute 'abrir_sessao'`.

- [ ] **Step 3: Escrever a sessão**

Acrescenta ao fim de `app/auth.py`:

```python
def _segredo(caminho):
    """O segredo do arquivo, ou None quando o arquivo nao existe.

    Arquivo ausente e o estado "ninguem entrou ainda", e nao arquivo
    torto: quem chama decide o que fazer (hoje, recusar a sessao). Arquivo
    presente sem a chave e outra coisa, e o erro diz qual arquivo.
    """
    dados = carregar(caminho)
    if not dados:
        return None
    if not dados.get("segredo"):
        raise ValueError("%s: sem a chave segredo" % caminho)
    return dados["segredo"]


def seguro():
    """O atributo Secure do cookie, desligado por padrao.

    O app fala http em 127.0.0.1, e um cookie Secure nao volta por http.
    Quem puser o app atras de um TLS liga BGPGEN_COOKIE_SEGURO=1.
    """
    return os.environ.get("BGPGEN_COOKIE_SEGURO") == "1"


def assinatura(usuario, expira, segredo):
    """O HMAC de "usuario.expira" com o segredo do arquivo."""
    mensagem = ("%s.%d" % (usuario, expira)).encode("utf-8")
    return hmac.new(_de_b64(segredo), mensagem, hashlib.sha256).hexdigest()


def abrir_sessao(resposta, usuario, caminho=USUARIOS_YAML):
    """Po o cookie de sessao na resposta do login."""
    expira = int(time.time()) + VALIDADE
    valor = "%s.%d.%s" % (usuario, expira,
                          assinatura(usuario, expira, _segredo(caminho)))
    resposta.set_cookie(COOKIE, valor, max_age=VALIDADE, httponly=True,
                        samesite="lax", secure=seguro(), path="/")


def fechar_sessao(resposta):
    resposta.delete_cookie(COOKIE, path="/", httponly=True, samesite="lax",
                           secure=seguro())


def da_requisicao(request, caminho=USUARIOS_YAML):
    """O usuario do cookie, ou None quando o cookie nao vale.

    Vale o cookie com os tres pedacos, com o prazo no futuro e com a
    assinatura que fecha com o segredo do arquivo. Trocar o segredo
    (apagando o arquivo e deixando o app recriar) derruba toda sessao
    aberta, que e o unico jeito de revogar uma.
    """
    valor = request.cookies.get(COOKIE)
    if not valor:
        return None
    partes = valor.rsplit(".", 2)
    if len(partes) != 3:
        return None
    usuario, expira, recebida = partes
    segredo = _segredo(caminho)
    if not segredo or not expira.isdigit():
        return None
    if int(expira) < time.time():
        return None
    if not hmac.compare_digest(recebida, assinatura(usuario, int(expira), segredo)):
        return None
    return usuario


def exigir_login(request):
    """A dependencia das rotas protegidas: devolve o usuario ou recusa.

    A recusa e NaoAutenticado, e nao HTTPException: o corpo do 401 e o
    mesmo das outras recusas da API, e nao o {"detail": ...} do FastAPI.
    """
    usuario = da_requisicao(request)
    if usuario is None:
        raise NaoAutenticado("sessao expirada ou ausente")
    return usuario
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: 21 passed.

- [ ] **Step 5: Commit**

```bash
git add app/auth.py tests/test_auth.py
git commit -m "A sessao e um cookie assinado com o segredo do arquivo

Sem estado no processo: reiniciar o uvicorn nao desloga ninguem, e
trocar o segredo derruba toda sessao aberta. Sete dias, httpOnly e
SameSite=Lax, com o Secure atras de BGPGEN_COOKIE_SEGURO."
```

---

### Task 3: as rotas de login, logout e sessão

**Files:**
- Modify: `app/modelos_api.py` (acrescenta dois modelos no fim)
- Modify: `app/api.py` (imports, o roteador público, três rotas, o handler do 401)
- Modify: `tests/test_auth.py`
- Modify: `web/src/api/schema.d.ts` (regerado, não escrito à mão)

**Interfaces:**
- Consumes: `auth.conferir`, `auth.abrir_sessao`, `auth.fechar_sessao`, `auth.da_requisicao`, `auth.NaoAutenticado`, `auth.NOME_ADMIN`.
- Produces:
  - `modelos_api.LoginPedido` (`usuario: str`, `senha: str`)
  - `modelos_api.SessaoResposta` (`logado: bool`, `usuario: str | None`)
  - `api.publico` (o `APIRouter` das três rotas)
  - `POST /api/login`, `POST /api/logout`, `GET /api/sessao`

- [ ] **Step 1: Escrever os testes que falham**

Acrescenta ao fim de `tests/test_auth.py`:

```python
def test_o_login_com_a_senha_certa_devolve_a_sessao(api_anonimo):
    r = api_anonimo.post("/api/login",
                         json={"usuario": auth.NOME_ADMIN, "senha": SENHA})

    assert r.status_code == 200
    assert r.json() == {"logado": True, "usuario": auth.NOME_ADMIN}
    assert auth.COOKIE in r.headers["set-cookie"]


def test_o_login_com_a_senha_errada_recusa_no_formato_da_api(api_anonimo):
    r = api_anonimo.post("/api/login",
                         json={"usuario": auth.NOME_ADMIN, "senha": "chute"})

    assert r.status_code == 401
    assert r.json() == {"erros": {"_": "usuario ou senha invalidos"},
                        "avisos": []}
    assert "set-cookie" not in r.headers


def test_o_login_com_o_corpo_fora_do_modelo_volta_no_formato_da_api(api_anonimo):
    r = api_anonimo.post("/api/login", json={"usuario": "admin", "xpto": "1"})

    assert r.status_code == 422
    assert "xpto" in r.json()["erros"]["_corpo"]


def test_a_sessao_sem_cookie_diz_que_nao_esta_logado(api_anonimo):
    r = api_anonimo.get("/api/sessao")

    assert r.status_code == 200
    assert r.json() == {"logado": False, "usuario": None}


def test_a_sessao_com_cookie_diz_quem_entrou(api_anonimo):
    api_anonimo.post("/api/login", json={"usuario": auth.NOME_ADMIN, "senha": SENHA})

    assert api_anonimo.get("/api/sessao").json() == {"logado": True,
                                                     "usuario": auth.NOME_ADMIN}


def test_o_logout_apaga_o_cookie(api_anonimo):
    api_anonimo.post("/api/login", json={"usuario": auth.NOME_ADMIN, "senha": SENHA})

    r = api_anonimo.post("/api/logout")

    assert r.status_code == 200
    assert r.json() == {"logado": False, "usuario": None}
    assert api_anonimo.get("/api/sessao").json()["logado"] is False
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: 404 nos POSTs, porque as rotas não existem.

- [ ] **Step 3: Os modelos**

Acrescenta ao fim de `app/modelos_api.py`:

```python
class LoginPedido(Modelo):
    """Usuario e senha do POST /api/login.

    Modelo com o extra="forbid" do resto: um nome de campo trocado no
    front nao pode passar em silencio e virar um login vazio.
    """

    usuario: str = ""
    senha: str = ""


class SessaoResposta(BaseModel):
    """Quem esta logado. E a resposta do login, do logout e do /sessao."""

    logado: bool
    usuario: str | None = None
```

- [ ] **Step 4: As rotas e o handler do 401**

Em `app/api.py`, o import do `auth` entra junto dos outros:

```python
from fastapi import APIRouter, Depends, FastAPI, Query, Request
```

```python
from app import auth
from app import formulario as form
```

Troca a definição do `roteador` (linha 112) por dois roteadores:

```python
# As tres rotas de sessao sao as unicas de /api que respondem sem cookie:
# o /login precisa entrar antes de haver sessao, e o /sessao e o que a SPA
# consulta para saber se mostra a casca. O roteador de baixo e o protegido,
# e a dependencia fica nele inteiro, e nao rota a rota.
publico = APIRouter(prefix="/api", responses={
    404: {"model": ErroResposta}, 422: {"model": ErroResposta}})

roteador = APIRouter(prefix="/api", dependencies=[Depends(auth.exigir_login)],
                     responses={
                         401: {"model": ErroResposta},
                         404: {"model": ErroResposta},
                         422: {"model": ErroResposta}})
```

No fim do arquivo, junto das outras rotas públicas, entram as três:

```python
@publico.post("/login", response_model=SessaoResposta)
def entrar(pedido: LoginPedido, resposta: Response):
    """Confere a senha e abre a sessao no cookie.

    Usuario errado e senha errada devolvem a mesma mensagem de proposito:
    quem tenta adivinhar nao descobre qual dos dois acertou.
    """
    if not auth.conferir(pedido.usuario, pedido.senha):
        return _falha(401, [validate.Erro("_", "usuario ou senha invalidos")])
    auth.abrir_sessao(resposta, pedido.usuario)
    return SessaoResposta(logado=True, usuario=pedido.usuario)


@publico.post("/logout", response_model=SessaoResposta)
def sair(resposta: Response):
    """Apaga o cookie. Sem estado no servidor, nao ha mais o que apagar."""
    auth.fechar_sessao(resposta)
    return SessaoResposta(logado=False, usuario=None)


@publico.get("/sessao", response_model=SessaoResposta)
def ler_sessao(request: Request):
    """Quem esta logado agora, sem exigir cookie.

    E o que a SPA pergunta ao abrir a pagina: um 401 aqui obrigaria a
    tela a adivinhar pelo erro de outra consulta.
    """
    usuario = auth.da_requisicao(request)
    return SessaoResposta(logado=usuario is not None, usuario=usuario)
```

O `SessaoResposta` e o `LoginPedido` entram no import dos modelos:

```python
from app.modelos_api import (Aviso, Blocos, BlocosIrrPedido, BlocosTexto,
                             ErroResposta, GrupoForm, GrupoRegistro,
                             GrupoResumo, GrupoSalvo, IrrPedido, LoginPedido,
                             Membro, PeerForm, PeerRegistro, PeerResumo,
                             PeerSalvo, Plano, Prefixos, Previa, RedeAtual,
                             RedeForm, Saida, SessaoResposta)
```

E o `instalar` passa a incluir os dois, junto do handler novo:

```python
async def _sem_sessao(request: Request, exc: auth.NaoAutenticado):
    """O 401 das rotas protegidas, no formato das outras recusas.

    Um HTTPException daria {"detail": ...}, que e o formato que a SPA leria
    como resposta fora do modelo.
    """
    return _falha(401, [validate.Erro("_", str(exc))])


def instalar(app: FastAPI):
    """Monta as rotas /api e os tres tratadores de erro no app."""
    app.include_router(publico)
    app.include_router(roteador)
    app.add_exception_handler(RequestValidationError, _pedido_invalido)
    app.add_exception_handler(auth.NaoAutenticado, _sem_sessao)
    app.add_exception_handler(Exception, _falha_inesperada)
```

- [ ] **Step 5: Rodar para ver passar**

Run: `.venv/bin/python -m pytest tests/test_auth.py -v`
Expected: 27 passed.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest`
Expected: tudo passa. Nada foi protegido ainda, então os testes que já existiam não sentem a mudança.

- [ ] **Step 7: Regerar os tipos do front**

```bash
cd web && npm run api:tipos && cd ..
```

O `openapi-typescript` escreve `web/src/api/schema.d.ts` com `LoginPedido`,
`SessaoResposta`, `/api/login`, `/api/logout` e `/api/sessao`. O
`test_tipos_api.py` compara o arquivo com o `app.openapi()` e falha se este passo
for esquecido.

- [ ] **Step 8: Commit**

```bash
git add app/api.py app/modelos_api.py tests/test_auth.py web/src/api/schema.d.ts
git commit -m "O /api ganha login, logout e sessao

As tres rotas ficam fora do roteador protegido, e o 401 delas e
resposta no mesmo formato das outras recusas."
```

---

### Task 4: a superfície protegida (e o conftest que entra logado)

**Files:**
- Modify: `app/app.py`
- Modify: `app/api.py` (só o `instalar`, se o import dos dois roteadores ainda não estiver lá)
- Modify: `tests/conftest.py`
- Modify: `tests/test_api.py` (linhas 85 e 97)
- Modify: `tests/test_isolamento.py` (a fixture `cliente`, linha 263)
- Modify: `tests/test_web.py` (o teste das rotas da SPA)
- Modify: `tests/test_auth.py`
- Modify: `web/src/api/schema.d.ts` (regerado)

**Interfaces:**
- Consumes: `auth.bootstrap`, `auth.exigir_login`, `api.publico`, `api.roteador`, `auth.NOME_ADMIN`.
- Produces:
  - `tests/conftest.py`: a fixture `usuarios_em_tmp` (o caminho do arquivo e a senha de teste no ambiente), a fixture `api_anonimo` (cliente sem login), a fixture `api` (cliente logado) e a fixture `logar` (a função que loga um `TestClient` avulso).
  - `app.app.ciclo` (o lifespan) e as rotas `/docs` e `/openapi.json`.

- [ ] **Step 1: Escrever os testes que falham**

O `test_auth.py` ganha dois imports no topo para os casos que montam cliente
próprio:

```python
from fastapi.testclient import TestClient

from app import app as mod
```

E os casos novos vão ao fim do arquivo:

```python
def test_sem_cookie_o_api_recusa_no_formato_da_api(api_anonimo):
    r = api_anonimo.get("/api/plano")

    assert r.status_code == 401
    assert r.json()["erros"]["_"] == "sessao expirada ou ausente"
    assert r.json()["avisos"] == []


def test_com_cookie_o_api_responde_normal(api):
    assert api.get("/api/plano").status_code == 200


def test_o_base_txt_exige_sessao(api_anonimo, api):
    assert api_anonimo.get("/base.txt").status_code == 401
    assert api.get("/base.txt").status_code == 200


def test_o_docs_e_o_openapi_exigem_sessao(api_anonimo, api):
    assert api_anonimo.get("/docs").status_code == 401
    assert api_anonimo.get("/openapi.json").status_code == 401
    assert api.get("/docs").status_code == 200
    assert api.get("/openapi.json").status_code == 200


def test_o_openapi_fora_da_sessao_nao_vaza_o_schema(api_anonimo):
    assert "LoginPedido" not in api_anonimo.get("/openapi.json").text


def test_os_assets_e_as_rotas_da_spa_seguem_abertos(api_anonimo):
    # sem cookie: a tela de login precisa carregar antes de existir sessao
    for rota in ("/peers", "/grupos", "/prefixos", "/base", "/configuracoes",
                 "/login"):
        assert api_anonimo.get(rota).status_code in (200, 503), rota


def test_o_cookie_adulterado_nao_abre_nada(api_anonimo):
    api_anonimo.cookies.set(auth.COOKIE, "admin.9999999999." + "0" * 64)

    assert api_anonimo.get("/api/plano").status_code == 401


def test_usuarios_yaml_apagado_com_o_app_de_pe_tranca_tudo(api_anonimo, caminho):
    api_anonimo.post("/api/login", json={"usuario": auth.NOME_ADMIN, "senha": SENHA})
    caminho.unlink()

    # o bootstrap so roda no boot: sem arquivo, nao ha segredo para conferir
    # nem usuario para autenticar, e o login tambem recusa
    assert api_anonimo.get("/api/plano").status_code == 401
    assert api_anonimo.post(
        "/api/login",
        json={"usuario": auth.NOME_ADMIN, "senha": SENHA}).status_code == 401


def test_usuarios_yaml_torto_vira_500_com_o_nome_do_arquivo(api, logar, caminho):
    # o cliente da fixture `api` patcheia os caminhos; este aqui so precisa do
    # raise_server_exceptions=False, porque o ServerErrorMiddleware do
    # Starlette responde e depois levanta de novo
    cliente = logar(TestClient(mod.app, raise_server_exceptions=False))
    caminho.write_text("usuarios:\n  admin:\n    salt: x\n")

    r = cliente.post("/api/login", json={"usuario": auth.NOME_ADMIN, "senha": SENHA})

    assert r.status_code == 500
    assert "usuarios.yaml" in r.json()["erros"]["_"]


def test_o_lifespan_cria_o_admin(api_anonimo, usuarios_em_tmp):
    # ninguem chamou o bootstrap a mao: quem criou o arquivo foi o lifespan,
    # que e o caminho de verdade do boot
    assert usuarios_em_tmp.exists()
    assert auth.conferir(auth.NOME_ADMIN, SENHA)
```

Acrescenta em `tests/test_web.py`:

```python
def test_a_tela_de_login_tambem_e_servida_pelo_build(web):
    """O F5 na tela de login cai no servidor: sem a rota, da 404 antes do React.
    """
    r = web.get("/login")

    assert r.status_code == 200
    assert "root" in r.text
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/bin/python -m pytest tests/test_auth.py tests/test_web.py -v`
Expected: o `/api/plano` responde 200 sem cookie (nada protegido ainda), e o `/login` responde 404.

- [ ] **Step 3: O lifespan e a superfície no `app.py`**

Cabeçalho e imports de `app/app.py`:

```python
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import (FileResponse, HTMLResponse, PlainTextResponse,
                               RedirectResponse)

from app import api, auth, render
from app import peers as peers_mod

RAIZ = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def ciclo(app: FastAPI):
    """O que roda uma vez por processo, antes da primeira requisicao.

    Hoje e o bootstrap do admin: o app nasce com login, e sem usuario
    nenhum nao haveria como entrar. A senha criada sai no log, e o boot
    seguinte nao imprime nada.
    """
    auth.bootstrap()
    yield


# docs_url, openapi_url e redoc_url desligados: as duas rotas do docs
# voltam logo abaixo, atras do login. O app.openapi() continua valendo
# dentro do processo, que e de onde o npm run api:tipos o le.
app = FastAPI(title="bgpgen", lifespan=ciclo,
              docs_url=None, openapi_url=None, redoc_url=None)

# a API JSON em /api, que a SPA consome
api.instalar(app)


@app.get("/openapi.json", include_in_schema=False,
         dependencies=[Depends(auth.exigir_login)])
def schema_do_app():
    return app.openapi()


@app.get("/docs", include_in_schema=False,
         dependencies=[Depends(auth.exigir_login)])
def docs_do_app():
    """O Swagger, que so carrega o schema com o cookie no navegador."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="bgpgen")
```

O `/base.txt` ganha a dependência:

```python
@app.get("/base.txt", response_class=HTMLResponse,
         dependencies=[Depends(auth.exigir_login)])
def baixar_base():
```

E a lista das rotas da SPA ganha o `/login`:

```python
# As rotas da SPA. O /login entra aqui: o servidor e quem responde o
# index.html de um F5 na tela de login, e sem a linha o recarregamento da
# 404 antes de o React existir.
#
# Fora do openapi(): elas devolvem o index.html, nao JSON, e nao acrescentam
# nada ao contrato que o front consome. Como o web/src/api/schema.d.ts e
# gerado do app.openapi(), deixa-las dentro mexeria no schema por uma rota que
# nao e da API - o test_tipos_api.py pega isso na hora.
for _rota in ("/peers", "/grupos", "/prefixos", "/base", "/configuracoes",
              "/login"):
    app.add_api_route(_rota, pagina_spa, methods=["GET"],
                      include_in_schema=False)
```

- [ ] **Step 4: O conftest que entra logado**

`tests/conftest.py` passa a ter, no lugar da fixture `api` atual:

```python
SENHA_DE_TESTE = "senha-de-teste"


@pytest.fixture
def usuarios_em_tmp(tmp_path, monkeypatch):
    """O usuarios.yaml em tmp_path, e a senha de teste no ambiente.

    Quem cria o admin e o lifespan do app, que e o caminho de verdade:
    esta fixture so diz onde o arquivo mora e qual e a senha. Ela existe
    separada do `api` porque quem testa a recusa precisa de um cliente
    que NAO entrou.
    """
    from app import auth

    monkeypatch.setattr(auth, "USUARIOS_YAML", tmp_path / "usuarios.yaml")
    monkeypatch.setenv("BGPGEN_ADMIN_SENHA", SENHA_DE_TESTE)
    return tmp_path / "usuarios.yaml"


@pytest.fixture
def logar():
    """A funcao que loga um TestClient avulso, para quem monta o proprio.

    O TestClient guarda cookie entre chamadas, entao o login vale para o
    resto do caso. O assert com o corpo evita um 401 silencioso virar
    "a rota nao existe" tres linhas depois.
    """
    from app import auth

    def _logar(cliente):
        resposta = cliente.post("/api/login",
                                json={"usuario": auth.NOME_ADMIN,
                                      "senha": SENHA_DE_TESTE})
        assert resposta.status_code == 200, resposta.text
        return cliente

    return _logar


@pytest.fixture
def api_anonimo(tmp_path, monkeypatch, usuarios_em_tmp):
    """Um TestClient com o peers.yaml, o out/ e o cache do bgpq4 em tmp_path.

    A API e o app leem o peers_mod.PEERS_YAML na hora de cada chamada, entao
    trocar o caminho aqui basta: o app.app nao guarda mais copia nenhuma. O
    `with` roda o lifespan, e e ele que cria o admin no arquivo de
    usuarios_em_tmp.
    """
    from fastapi.testclient import TestClient

    from app import app as mod
    from app import peers as peers_mod
    from app import prefixes, render

    monkeypatch.setattr(peers_mod, "PEERS_YAML", tmp_path / "peers.yaml")
    monkeypatch.setattr(peers_mod, "OUT", tmp_path / "out")
    monkeypatch.setattr(render, "OUT", tmp_path / "out")
    monkeypatch.setattr(prefixes, "CACHE", tmp_path / "out" / ".cache")
    with TestClient(mod.app) as cliente:
        yield cliente


@pytest.fixture
def api(api_anonimo, logar):
    """O api_anonimo que ja entrou: a maioria dos testes nao e sobre o login."""
    return logar(api_anonimo)
```

- [ ] **Step 5: Os três `TestClient` avulsos**

Em `tests/test_api.py`, os dois testes das linhas 85 e 97 trocam a construção do
cliente. O primeiro vira:

```python
def test_fora_da_api_a_falha_inesperada_continua_texto_puro(api, logar, monkeypatch):
    """... (o docstring atual fica como esta) ..."""
    def quebrado(caminho):
        raise ValueError("peers.yaml: ASN 4200000000 nao cabe nos 16 bits")
    monkeypatch.setattr(peers_mod, "carregar_asn", quebrado)
    cliente = logar(TestClient(mod.app, raise_server_exceptions=False))

    r = cliente.get("/base.txt")

    assert r.status_code == 500
    assert r.text == "Internal Server Error"
```

O segundo (`test_yaml_quebrado_vira_500_em_json`) muda igual:

```python
def test_yaml_quebrado_vira_500_em_json(api, logar, monkeypatch):
    def quebrado(caminho):
        raise ValueError("peers.yaml: ASN 4200000000 nao cabe nos 16 bits")
    monkeypatch.setattr(peers_mod, "carregar_asn", quebrado)
    cliente = logar(TestClient(mod.app, raise_server_exceptions=False))
    r = cliente.get("/api/plano")
    assert r.status_code == 500
    assert "nao cabe nos 16 bits" in r.json()["erros"]["_"]
```

O `peers_mod` e o `mod` já estão importados no topo de `test_api.py`. Os dois
testes continuam pedindo a fixture `api` mesmo sem usar o cliente dela: é ela que
patcheia o `PEERS_YAML` e o `usuarios.yaml` para o `tmp_path` e roda o lifespan,
que cria o admin com a senha de teste. Sem a fixture, o `logar` encontraria o
`usuarios.yaml` do repositório (ou nenhum) e o login voltaria 401.

Em `tests/test_isolamento.py`, a fixture `cliente` (linha 263) vira:

```python
@pytest.fixture
def cliente(out, usuarios_em_tmp, logar, monkeypatch):
    """O app apontando para o mesmo tmp_path que o `out` ja patcheia, logado.

    A exclusao passa pela rota, entao o peers.yaml tambem tem que sair do
    checkout: sem o patch, a rota leria o arquivo de verdade e o teste
    apagaria o grupo do repositorio. O CACHE do bgpq4 entra junto pelo
    mesmo motivo. O admin nasce do bootstrap, e este cliente nao roda o
    lifespan (nao ha context manager): por isso a chamada explicita.
    """
    auth.bootstrap()
    monkeypatch.setattr(mod, "PEERS_YAML", out / "peers.yaml")
    monkeypatch.setattr(prefixes, "CACHE", out / ".cache")
    return logar(TestClient(servidor.app))
```

O import do `auth` entra no topo do arquivo:

```python
from app import app as servidor
from app import auth
from app import peers as mod
```

- [ ] **Step 6: Rodar a suíte inteira**

Run: `.venv/bin/python -m pytest`
Expected: tudo passa. Se algum arquivo esquecido usar um cliente sem login, ele aparece como 401 na hora.

- [ ] **Step 7: Regerar os tipos do front**

```bash
cd web && npm run api:tipos && cd ..
```

O `responses={401: {"model": ErroResposta}}` do roteador muda o schema de todas
as rotas protegidas.

- [ ] **Step 8: Commit**

```bash
git add app/app.py app/api.py tests/conftest.py tests/test_api.py \
        tests/test_isolamento.py tests/test_web.py tests/test_auth.py \
        web/src/api/schema.d.ts
git commit -m "O app inteiro passa a exigir a sessao

O /api, o /base.txt e as duas rotas do docs ficam atras do cookie; a
SPA e os assets seguem abertos, senao nao haveria tela de login. A
fixture do conftest entra logada, e os tres TestClient avulsos usam o
helper."
```

---

### Task 5: o cliente do front, o 401 e o "sair"

**Files:**
- Modify: `web/src/api/cliente.ts`
- Modify: `web/src/api/cliente.test.ts`
- Modify: `web/src/api/consultas.ts` (a chave `sessao`)
- Create: `web/src/api/sessao.ts`
- Modify: `web/src/app/main.tsx`
- Modify: `web/src/components/BarraLateral.tsx`
- Modify: `web/src/components/BarraLateral.test.tsx`

**Interfaces:**
- Consumes: `chaves` e `lerRecusa` de `consultas.ts`; `SessaoResposta` do `schema.d.ts` regerado.
- Produces:
  - `cliente.ts`: `quandoPerderSessao(fn: () => void) -> void` e o cliente com `credentials: "same-origin"`.
  - `consultas.ts`: `chaves.sessao` e o tipo `Sessao`.
  - `sessao.ts`: `useSessao()`, `useEntrar()`, `useSair()`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescenta ao fim de `web/src/api/cliente.test.ts`:

```ts
describe("o cliente avisa quando a sessao caiu", () => {
  // o chamador escolhe a requisicao: e o caminho dela que decide se o 401
  // significa "sessao caiu" ou "senha errada"
  async function comResposta(
    status: number,
    chamada: (cliente: typeof import("./cliente").cliente) => Promise<unknown>,
  ) {
    vi.stubGlobal("Request", Requisicao)
    vi.stubGlobal("fetch", () =>
      Promise.resolve(new Response("{}", { status, headers: { "content-type": "application/json" } })),
    )
    vi.resetModules()
    const modulo = await import("./cliente")
    let avisos = 0
    modulo.quandoPerderSessao(() => { avisos += 1 })
    await chamada(modulo.cliente)
    return avisos
  }

  it("avisa no 401 de uma consulta qualquer", async () => {
    const avisos = await comResposta(401, (c) => c.GET("/api/plano"))

    expect(avisos).toBe(1)
  })

  it("nao avisa no 422 nem no 500", async () => {
    expect(await comResposta(422, (c) => c.GET("/api/plano"))).toBe(0)
    expect(await comResposta(500, (c) => c.GET("/api/plano"))).toBe(0)
  })

  it("nao avisa no 401 do login, que e senha errada", async () => {
    // se avisasse, a tela de login recarregaria a cada chute e apagaria a
    // mensagem de erro e a senha digitada
    const avisos = await comResposta(401, (c) =>
      c.POST("/api/login", { body: { usuario: "admin", senha: "chute" } }),
    )

    expect(avisos).toBe(0)
  })
})
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `cd web && npm test -- src/api/cliente.test.ts`
Expected: `quandoPerderSessao is not a function`.

- [ ] **Step 3: O cliente**

`web/src/api/cliente.ts` fica assim:

```ts
import createClient from "openapi-fetch"
import type { paths } from "./schema"

/** O que fazer quando o servidor recusa a sessao. */
let aoPerderSessao: (() => void) | null = null

/**
 * Registra quem trata a sessao perdida. Quem chama e o main.tsx, e o
 * callback leva para a tela de login.
 *
 * O aviso e um callback, e nao um `navigate` daqui, porque este modulo
 * nao esta dentro do router: quem sabe navegar e quem monta a arvore.
 */
export function quandoPerderSessao(fn: () => void) {
  aoPerderSessao = fn
}

// baseUrl vazio de proposito: o caminho do schema ja comeca com /api, e a
// mesma build roda pelo proxy do Vite (5173) e pelo uvicorn (8000). Com host
// no codigo, um dos dois quebra.
// O `createClient` guarda o `globalThis.fetch` de quando o modulo carrega, e o
// teste troca o fetch depois disso. Este indireto le o global na hora da
// chamada, que e o que deixa o `mockFetch` do arnes valer para as telas: em
// producao e o mesmo fetch do browser.
// O `credentials` e o padrao do fetch para o mesmo host, e esta escrito aqui
// para que a intencao nao dependa da lembranca de ninguem.
export const cliente = createClient<paths>({
  baseUrl: "",
  credentials: "same-origin",
  fetch: (entrada: Request, init?: RequestInit) => (globalThis.fetch as typeof fetch)(entrada, init),
})

// O 401 do /api/login fica de fora: ali ele quer dizer "senha errada", e
// nao "sessao caiu". Quem trata e a tela de login, que mostra a mensagem e
// mantem o que foi digitado.
cliente.use({
  onResponse({ request, response }) {
    if (response.status !== 401) return
    const caminho = new URL(request.url, "http://localhost").pathname
    if (caminho === "/api/login") return
    aoPerderSessao?.()
  },
})
```

- [ ] **Step 4: Rodar para ver passar**

Run: `cd web && npm test -- src/api/cliente.test.ts`
Expected: 6 passed.

- [ ] **Step 5: A chave e o módulo da sessão**

Em `web/src/api/consultas.ts`, o `chaves` ganha a linha:

```ts
  blocos: ["blocos"] as const,
  sessao: ["sessao"] as const,
```

E o tipo, junto dos outros:

```ts
export type Sessao = components["schemas"]["SessaoResposta"]
```

Cria `web/src/api/sessao.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { cliente } from "./cliente"
import { chaves, lerRecusa, type Sessao } from "./consultas"

/**
 * Quem esta logado agora. E a pergunta que a guarda faz antes de montar a
 * casca, e por isso ela nao tem retry: um servidor fora do ar nao melhora
 * na segunda tentativa, e a tela ficaria parada esperando.
 */
export function useSessao() {
  return useQuery({
    queryKey: chaves.sessao,
    queryFn: async () => {
      const { data, error } = await cliente.GET("/api/sessao")
      if (error) throw new Error("falha ao ler a sessao")
      return data as Sessao
    },
    retry: false,
    staleTime: 0,
  })
}

/** A primeira mensagem da recusa, que e o que a tela de login mostra. */
export function mensagemDaRecusa(corpo: unknown): string {
  return Object.values(lerRecusa(corpo).erros)[0] ?? "nao foi possivel entrar"
}

export function useEntrar() {
  const consultas = useQueryClient()
  const navegar = useNavigate()
  return useMutation({
    mutationFn: async (credenciais: { usuario: string; senha: string }) => {
      const { data, error } = await cliente.POST("/api/login", { body: credenciais })
      if (error) throw new Error(mensagemDaRecusa(error))
      return data
    },
    onSuccess: async () => {
      // a guarda le a sessao pela chave: sem o invalidate ela continuaria
      // com o "logado: false" do primeiro render e devolveria para o login
      await consultas.invalidateQueries({ queryKey: chaves.sessao })
      navegar("/peers", { replace: true })
    },
  })
}

export function useSair() {
  const consultas = useQueryClient()
  const navegar = useNavigate()
  return useMutation({
    mutationFn: async () => {
      const { error } = await cliente.POST("/api/logout")
      if (error) throw new Error("falha ao sair")
    },
    // o onSettled, e nao o onSuccess: o cookie pode ter ido embora com uma
    // resposta que falhou, e ficar na casca mostrando o dado do cadastro e
    // pior do que sair e pedir a senha de novo
    onSettled: () => {
      consultas.clear()
      navegar("/login", { replace: true })
    },
  })
}
```

- [ ] **Step 6: O registro no boot e o botão de sair**

`web/src/app/main.tsx`:

```tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "@/estilo/tokens.css"
import { quandoPerderSessao } from "./api/cliente"
import { Provedores } from "./provedores"
import { Roteador } from "./roteador"

// A sessao vencida no meio de um salvamento vira um 401 em qualquer
// chamada. O replace recarrega a pagina, e e isso que descarta o
// formulario em edicao: com um navigate do router ele sobreviveria a
// troca de tela e perderia o estado no primeiro refetch.
quandoPerderSessao(() => window.location.replace("/login"))

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provedores>
      <Roteador />
    </Provedores>
  </StrictMode>,
)
```

Em `web/src/components/BarraLateral.tsx`, o import e o rodapé:

```tsx
import { useSair } from "@/api/sessao"
```

```tsx
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
        {/* ... as tres secoes como estao ... */}
      </div>

      <div className="border-t pt-2">
        <Button variant="ghost" size="sm" onClick={() => sair.mutate()}
                disabled={sair.isPending}>
          sair
        </Button>
      </div>

    </nav>
```

com a linha do hook junto das outras, no topo do componente:

```tsx
  const { pathname } = useLocation()
  const sair = useSair()
```

- [ ] **Step 7: O teste do botão**

Acrescenta em `web/src/components/BarraLateral.test.tsx`. O caso não usa o
`MemoryRouter` dos outros: o `useSair` precisa do `QueryClient`, que o
`montarRota` do harness já traz. Os imports do harness entram no topo do
arquivo:

```tsx
import { montarRota, mockFetch, peticoes } from "@/teste/roteador"
```

```tsx
it("sair chama o logout e volta para o login", async () => {
  mockFetch({ "POST /api/logout": { corpo: { logado: false, usuario: null } } })
  montarRota([
    { path: "/peers", element: <BarraLateral peers={[]} grupos={[]} asn="64512" aoNovo={() => {}} /> },
    { path: "/login", element: <h1>entrou na tela de login</h1> },
  ], "/peers")

  await userEvent.click(screen.getByRole("button", { name: /sair/i }))

  await screen.findByText("entrou na tela de login")
  const pedido = peticoes().find((p) => p.caminho === "/api/logout")
  expect(pedido?.metodo).toBe("POST")
})
```

- [ ] **Step 8: Rodar os testes do front e o lint**

Run: `cd web && npm test && npm run lint`
Expected: tudo passa, sem aviso novo de lint.

- [ ] **Step 9: Commit**

```bash
git add web/src/api/cliente.ts web/src/api/cliente.test.ts web/src/api/consultas.ts \
        web/src/api/sessao.ts web/src/app/main.tsx \
        web/src/components/BarraLateral.tsx web/src/components/BarraLateral.test.tsx
git commit -m "O cliente manda o cookie e reage ao 401

O 401 do login fica de fora do aviso de sessao perdida: ali ele e senha
errada. O sair limpa o cache e volta para a tela de entrada."
```

---

### Task 6: a tela de login e a guarda

**Files:**
- Create: `web/src/telas/login/LoginTela.tsx`
- Create: `web/src/telas/login/LoginTela.test.tsx`
- Create: `web/src/app/ExigeLogin.tsx`
- Create: `web/src/app/ExigeLogin.test.tsx`
- Modify: `web/src/app/roteador.tsx`

**Interfaces:**
- Consumes: `useSessao`, `useEntrar` de `@/api/sessao`; `montarRota`, `mockFetch` do harness.
- Produces: `LoginTela` (componente) e `ExigeLogin` (componente que recebe `children`).

- [ ] **Step 1: Escrever os testes que falham**

Cria `web/src/telas/login/LoginTela.test.tsx`:

```tsx
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { montarRota, mockFetch, peticoes } from "@/teste/roteador"
import { LoginTela } from "./LoginTela"

const ROTAS = [
  { path: "/login", element: <LoginTela /> },
  { path: "/peers", element: <h1>a casca</h1> },
]

describe("a tela de login", () => {
  it("com a senha errada mostra a mensagem e nao sai da tela", async () => {
    mockFetch({
      "POST /api/login": {
        status: 401,
        corpo: { erros: { _: "usuario ou senha invalidos" }, avisos: [] },
      },
    })
    montarRota(ROTAS, "/login")

    await userEvent.type(screen.getByLabelText("Senha"), "chute")
    await userEvent.click(screen.getByRole("button", { name: /^entrar$/ }))

    expect(await screen.findByRole("alert")).toHaveTextContent("usuario ou senha invalidos")
    // a senha digitada fica: quem errou uma tecla nao digita tudo de novo
    expect(screen.getByLabelText("Senha")).toHaveValue("chute")
  })

  it("com a senha certa vai para os peers", async () => {
    mockFetch({
      "POST /api/login": { corpo: { logado: true, usuario: "admin" } },
      "GET /api/sessao": { corpo: { logado: true, usuario: "admin" } },
    })
    montarRota(ROTAS, "/login")

    await userEvent.type(screen.getByLabelText("Senha"), "certa")
    await userEvent.click(screen.getByRole("button", { name: /^entrar$/ }))

    await screen.findByText("a casca")
    const pedido = peticoes().find((p) => p.caminho === "/api/login")
    expect(pedido?.corpo).toEqual({ usuario: "admin", senha: "certa" })
  })
})
```

Cria `web/src/app/ExigeLogin.test.tsx`:

```tsx
import { screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { ExigeLogin } from "./ExigeLogin"
import { montarRota, mockFetch } from "@/teste/roteador"

const ROTAS = [
  { path: "/login", element: <h1>a tela de login</h1> },
  { path: "/peers", element: <ExigeLogin><h1>a casca</h1></ExigeLogin> },
]

describe("a guarda", () => {
  it("sem sessao leva para o login", async () => {
    mockFetch({ "GET /api/sessao": { corpo: { logado: false, usuario: null } } })
    montarRota(ROTAS, "/peers")

    await screen.findByText("a tela de login")
  })

  it("com sessao desenha a casca", async () => {
    mockFetch({ "GET /api/sessao": { corpo: { logado: true, usuario: "admin" } } })
    montarRota(ROTAS, "/peers")

    await screen.findByText("a casca")
  })
})
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `cd web && npm test -- src/telas/login src/app/ExigeLogin`
Expected: erro de import, os dois módulos não existem.

- [ ] **Step 3: A guarda**

Cria `web/src/app/ExigeLogin.tsx`:

```tsx
import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useSessao } from "@/api/sessao"

/**
 * O que separa a casca da tela de login.
 *
 * Enquanto a consulta esta em voo nao desenha nada: meia casca piscando
 * antes do redirecionamento e pior do que meio segundo parado, e a casca
 * ja dispara tres consultas proprias que voltariam 401.
 */
export function ExigeLogin({ children }: { children: ReactNode }) {
  const sessao = useSessao()

  if (sessao.isPending) return null
  if (!sessao.data?.logado) return <Navigate to="/login" replace />
  return <>{children}</>
}
```

- [ ] **Step 4: A tela**

Cria `web/src/telas/login/LoginTela.tsx`:

```tsx
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useEntrar } from "@/api/sessao"

/**
 * A entrada do app, fora da casca: quem ainda nao entrou nao tem lista de
 * peers para ver, e a barra lateral mostraria justamente o que o login
 * esconde.
 *
 * O campo do usuario ja vem preenchido com "admin" porque e o unico que o
 * boot cria. A senha fica no estado da tela ate a resposta, e nao vai para
 * lugar nenhum alem do POST.
 */
export function LoginTela() {
  const [usuario, setUsuario] = useState("admin")
  const [senha, setSenha] = useState("")
  const entrar = useEntrar()

  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <form
        className="w-full max-w-sm rounded border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault()
          entrar.mutate({ usuario, senha })
        }}
      >
        <h1 className="text-lg font-semibold">bgpgen</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          o cadastro e os blocos gerados ficam atrás do login
        </p>

        <div className="mt-4 flex flex-col gap-1">
          <Label htmlFor="usuario">Usuário</Label>
          <Input id="usuario" value={usuario} autoComplete="username"
                 onChange={(e) => setUsuario(e.target.value)} />
        </div>

        <div className="mt-3 flex flex-col gap-1">
          <Label htmlFor="senha">Senha</Label>
          <Input id="senha" type="password" value={senha}
                 autoComplete="current-password"
                 onChange={(e) => setSenha(e.target.value)} />
        </div>

        {entrar.isError ? (
          <p role="alert" className="mt-3 text-sm text-erro-texto">
            {entrar.error.message}
          </p>
        ) : null}

        <Button type="submit" className="mt-4 w-full" disabled={entrar.isPending}>
          entrar
        </Button>
      </form>
    </div>
  )
}
```

Os três primitivos são os mesmos que as outras telas usam (`@/components/ui/input`,
`.../label` e `.../button`), e o `Button` do projeto aceita children, como em
`Falha.tsx:16`.

- [ ] **Step 5: A rota**

Em `web/src/app/roteador.tsx` entram o import, a rota e a guarda:

```tsx
import { ExigeLogin } from "./ExigeLogin"
import { LoginTela } from "@/telas/login/LoginTela"
```

```tsx
const roteador = createBrowserRouter([
  // A tela de login fica fora da casca, e fora da guarda: ela e o destino
  // de quem nao entrou, e a guarda a mandaria para si mesma
  { path: "/login", element: <LoginTela /> },
  {
    path: "/",
    element: (
      <ExigeLogin>
        <Casca />
      </ExigeLogin>
    ),
    children: [
```

- [ ] **Step 6: Rodar os testes do front e o lint**

Run: `cd web && npm test && npm run lint`
Expected: tudo passa.

- [ ] **Step 7: Build e conferida na mão**

```bash
cd web && npm run build && cd ..
.venv/bin/uvicorn app.app:app --port 8000
```

Abre `http://127.0.0.1:8000/peers`: tem que cair na tela de login. A senha está
no log do uvicorn, na linha que o bootstrap imprimiu. Depois de entrar, o F5 em
`/peers` tem que continuar logado, e `/docs` tem que abrir o Swagger.

- [ ] **Step 8: Commit**

```bash
git add web/src/telas/login web/src/app/ExigeLogin.tsx web/src/app/ExigeLogin.test.tsx \
        web/src/app/roteador.tsx
git commit -m "A SPA ganha a tela de login e a guarda de sessao

A tela fica fora da casca e o F5 nela cai no index.html servido pelo
uvicorn. A guarda pergunta /api/sessao antes de montar a casca."
```

---

### Task 7: o e2e

**Files:**
- Modify: `web/playwright.config.ts`
- Create: `web/e2e/senha.ts`
- Create: `web/e2e/entrar.setup.ts`
- Create: `web/e2e/login.spec.ts`

**Interfaces:**
- Consumes: `POST /api/login`, `POST /api/logout`, `GET /api/sessao` e a tela de login da Task 6.
- Produces: o projeto `setup` do Playwright e o `storageState` em `web/e2e/.tmp/sessao.json`.

- [ ] **Step 1: A config**

Primeiro a constante compartilhada. Cria `web/e2e/senha.ts`:

```ts
/**
 * A senha que o bootstrap do e2e cria.
 *
 * A arvore de web/e2e/.tmp nasce vazia a cada rodada, entao o usuarios.yaml
 * do e2e e sempre novo e este e o admin dele. A constante mora aqui para que
 * a config, que a poe no ambiente do uvicorn, e o setup, que a digita na
 * tela, nao possam divergir.
 */
export const SENHA = "senha-do-e2e"
```

Em `web/playwright.config.ts`, entra o import no topo, junto dos outros:

```ts
import { SENHA } from "./e2e/senha"
```

O `webServer` ganha o `env` (o Playwright mescla o que vem aqui sobre o
`process.env`, então o `PATH` continua valendo) e um projeto de setup entra na
frente dos outros:

```ts
const PORTA = 8099
const SESSAO = fileURLToPath(new URL("./e2e/.tmp/sessao.json", import.meta.url))
```

```ts
  webServer: {
    // O uvicorn roda de dentro da copia, e serve o build de verdade: o e2e
    // exercita o FastAPI servindo a SPA, e nao o Vite.
    //
    // A copia sai aqui, no proprio comando, e nao num `globalSetup` da config:
    // medido nesta versao (1.63), o webServer sobe antes do globalSetup, e o
    // `cd` da copia falhava com "No such file or directory" antes de o
    // globalSetup ter chance de rodar.
    command: `node ${repo}web/e2e/global-setup.ts && cd ${temp} && BGPGEN_WEB=${repo}web/dist ${repo}.venv/bin/python -m uvicorn app.app:app --port ${PORTA}`,
    url: `http://127.0.0.1:${PORTA}/api/plano`,
    reuseExistingServer: false,
    // a senha do admin que o bootstrap cria na copia de .tmp. O Playwright
    // mescla isto sobre o process.env, entao o PATH continua valendo
    env: { BGPGEN_ADMIN_SENHA: SENHA },
    stdout: "pipe",
  },
```

O `url` continua `/api/plano` mesmo respondendo 401 sem cookie: o Playwright dá
o servidor por pronto em qualquer status abaixo de 404 (`isURLAvailable`, no
playwright-core).

Os projetos viram três:

```ts
  projects: [
    // o setup loga uma vez pela tela e guarda o cookie; os outros projetos
    // entram com ele, e seguem sem saber que existe login
    { name: "setup", testMatch: /entrar\.setup\.ts/ },
    // o chromium roda tudo, incluindo a copia; o webkit roda so a copia, que e
    // onde o Safari pode recusar o writeText depois da requisicao do salvar
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], storageState: SESSAO },
      dependencies: ["setup"],
    },
    {
      name: "webkit",
      testMatch: /copiar\.spec\.ts/,
      use: { ...devices["Desktop Safari"], storageState: SESSAO },
      dependencies: ["setup"],
    },
  ],
```

- [ ] **Step 2: O setup que entra**

Cria `web/e2e/entrar.setup.ts`:

```ts
import { expect, test as setup } from "@playwright/test"
import { fileURLToPath } from "node:url"
import { SENHA } from "./senha"

const ARQUIVO = fileURLToPath(new URL("./.tmp/sessao.json", import.meta.url))

/**
 * O login de uma vez so, guardado no storageState.
 *
 * Ele e um projeto, e nao um globalSetup, porque o globalSetup do Playwright
 * roda antes do webServer nesta versao: na hora dele nao ha servidor para
 * responder o POST.
 */
setup("entra e guarda a sessao", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("Senha").fill(SENHA)
  await page.getByRole("button", { name: /^entrar$/ }).click()
  await expect(page).toHaveURL(/\/peers/)
  await page.context().storageState({ path: ARQUIVO })
})
```

- [ ] **Step 3: O caso da tela de login**

Cria `web/e2e/login.spec.ts`:

```ts
import { expect, test } from "@playwright/test"
import { SENHA } from "./senha"

// sem o cookie do setup: este arquivo testa justamente a entrada
test.use({ storageState: { cookies: [], origins: [] } })

test("a senha errada nao entra e a certa entra", async ({ page }) => {
  await page.goto("/peers")
  await expect(page).toHaveURL(/\/login/)

  await page.getByLabel("Senha").fill("chute")
  await page.getByRole("button", { name: /^entrar$/ }).click()
  await expect(page.getByRole("alert")).toContainText("usuario ou senha invalidos")
  await expect(page).toHaveURL(/\/login/)

  await page.getByLabel("Senha").fill(SENHA)
  await page.getByRole("button", { name: /^entrar$/ }).click()
  await expect(page).toHaveURL(/\/peers/)
})

test("o sair volta para a tela de login", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("Senha").fill(SENHA)
  await page.getByRole("button", { name: /^entrar$/ }).click()
  await expect(page).toHaveURL(/\/peers/)

  await page.getByRole("button", { name: /^sair$/ }).click()

  await expect(page).toHaveURL(/\/login/)
  await page.goto("/peers")
  await expect(page).toHaveURL(/\/login/)
})
```

- [ ] **Step 4: Rodar o e2e**

Run: `cd web && npm run e2e`
Expected: 14 passed (os 12 de antes, mais os dois novos). Se o `setup` falhar, o
`web/e2e/.tmp` guarda o rastro da rodada anterior: apaga a pasta e roda de novo.

- [ ] **Step 5: Commit**

```bash
git add web/playwright.config.ts web/e2e/senha.ts web/e2e/entrar.setup.ts \
        web/e2e/login.spec.ts
git commit -m "O e2e entra pela tela e guarda a sessao

O projeto de setup loga uma vez e grava o storageState, entao os 12 casos
que ja existiam seguem sem saber que existe login. Dois casos novos
exercitam a entrada e o sair."
```

---

### Task 8: o README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: tudo o que as tarefas anteriores entregaram.
- Produces: nada de código.

- [ ] **Step 1: A seção do login**

Em `README.md`, uma seção nova depois de "Como subir" e antes de "O front (SPA)":

```markdown
### O login

O app sobe com um admin e uma senha sorteada. A senha sai uma vez, no log do
primeiro boot, e não é gravada em lugar nenhum: quem não guardou precisa apagar
o `usuarios.yaml` e reiniciar para gerar outra.

```bash
docker compose logs bgpgen | grep -A3 "admin criado"   # a senha do primeiro boot
```

O que fica atrás do login é o `/api` inteiro, o `/base.txt` e as duas rotas do
docs; a SPA e os arquivos do build continuam abertos, senão a própria tela de
login não carregaria. A sessão é um cookie de sete dias, e reiniciar o app não
desloga ninguém: o que derruba as sessões abertas é trocar o segredo, que
acontece quando o `usuarios.yaml` é recriado.

Duas variáveis mexem nisso:

| Variável | Para quê |
| --- | --- |
| `BGPGEN_ADMIN_SENHA` | A senha do admin criado no boot, no lugar da sorteada. É o que o e2e usa |
| `BGPGEN_COOKIE_SEGURO=1` | Liga o atributo `Secure` do cookie, para quem põe o app atrás de um TLS |
```

- [ ] **Step 2: Ajustar o "O que não faz"**

Na lista do "O que não faz", a primeira linha ("Não fala com o equipamento")
continua, e uma linha nova entra no fim:

```markdown
- **Não tem gestão de usuários.** É um admin só, criado no boot, e sem papéis.
  Trocar a senha é apagar o `usuarios.yaml` e reiniciar; não há tela para isso.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "O README conta do login e das duas variaveis

O caminho da senha esquecida, o que fica atras do cookie e o que a
imagem nao leva junto."
```

---

## Depois da última tarefa

O merge na `main` e o push são do operador, como nas etapas anteriores. Antes de
entregar, a lista do que conferir à mão:

- [ ] `.venv/bin/python -m pytest` verde, com o `test_tipos_api.py` rodando (ele é pulado sem `npm` no `PATH`).
- [ ] `cd web && npm test && npm run lint && npm run api:conferir` verdes.
- [ ] `cd web && npm run e2e` verde, com os 14 casos.
- [ ] `docker compose up --build` sobe, e o `docker compose logs bgpgen` mostra a senha uma vez só. Um segundo `up` não mostra senha nenhuma.
- [ ] `git status` limpo depois de subir o app: o `usuarios.yaml` do container não aparece.
- [ ] O healthcheck do Docker fica `healthy` (ele bate em `/`, que responde 200 pelo redirect para a SPA).
