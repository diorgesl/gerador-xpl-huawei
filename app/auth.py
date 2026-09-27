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


def _caminho(caminho=None):
    """O caminho do arquivo, resolvido na hora da chamada.

    O padrao e None, e nao USUARIOS_YAML, de proposito: um default no
    argumento congela o valor que a constante tinha no import, e quem
    troca a constante depois disso (os testes, com monkeypatch) continuaria
    falando com o arquivo de sempre. Quem le a constante no momento da
    chamada e este helper, como o _yaml() do api.py faz com o PEERS_YAML.
    """
    return Path(caminho or USUARIOS_YAML)


def carregar(caminho=None):
    """O dicionario do arquivo, ou {} quando ele nao existe."""
    caminho = _caminho(caminho)
    if not caminho.exists():
        return {}
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def escrever(dados, caminho=None):
    """Grava o arquivo com permissao 0600.

    O modo vai no open, e nao num chmod depois: entre um e outro o
    arquivo existiria legivel para todo mundo. O 0600 e o que segura o
    hash da senha e o segredo do cookie.
    """
    caminho = _caminho(caminho)
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
    caminho = _caminho(caminho)
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


def criar_admin(senha, caminho=None):
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


def bootstrap(caminho=None, senha=None):
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


def conferir(usuario, senha, caminho=None):
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
