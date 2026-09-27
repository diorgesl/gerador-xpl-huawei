"""Fixtures que mais de um arquivo de teste usa.

O que mora aqui e o que dois arquivos precisam enxergar igual: o
`fake_bgpq4` nasceu no test_prefixes.py e veio para ca na task do bloco
proprio, quando o test_app.py passou a exercitar a reconsulta, que chama
o `coletar` de verdade.
"""

import pytest

from app import prefixes


@pytest.fixture
def fake_bgpq4(tmp_path, monkeypatch):
    """Um bgpq4 de mentira no PATH, que devolve prefixos fixos.

    A saida e uma linha so com os prefixos separados por espaco, que e o
    que o bgpq4 real devolve com -F '%n/%l '. Espelha o
    tests/reference/formated--4.txt do upstream, inclusive o espaco que
    sobra no fim.

    O `CACHE` sai do checkout junto: sem o patch, um teste que deixe o
    coletar rodar de verdade escreve out/.cache/ no repositorio.
    """
    binario = tmp_path / "bin" / "bgpq4"
    binario.parent.mkdir(parents=True, exist_ok=True)
    binario.write_text(
        "#!/bin/sh\n"
        'case " $* " in\n'
        "  *' -6 '*) echo '2001:db8::/32 '; exit 0;;\n"
        "  *) echo '45.169.232.0/22 45.169.236.0/23 '; exit 0;;\n"
        "esac\n",
        encoding="ascii",
    )
    binario.chmod(0o755)
    monkeypatch.setenv("PATH", str(binario.parent))
    monkeypatch.setattr(prefixes, "CACHE", tmp_path / ".cache")
    return binario


SENHA_DE_TESTE = "senha-de-teste"


@pytest.fixture
def usuarios_em_tmp(tmp_path_factory, monkeypatch):
    """O usuarios.yaml num tmp proprio, e a senha de teste no ambiente.

    O diretorio e outro, e nao o tmp_path do caso, de proposito: meia duzia
    de testes fotografa a arvore do tmp_path para provar que uma recusa nao
    deixou rastro (o `arvore` do dados_api.py), e o arquivo do login nao e
    rastro de requisicao nenhuma.

    Quem cria o admin e o lifespan do app, que e o caminho de verdade:
    esta fixture so diz onde o arquivo mora e qual e a senha. Ela existe
    separada do `api` porque quem testa a recusa precisa de um cliente
    que NAO entrou.
    """
    from app import auth

    pasta = tmp_path_factory.mktemp("auth")
    monkeypatch.setattr(auth, "USUARIOS_YAML", pasta / "usuarios.yaml")
    monkeypatch.setenv("BGPGEN_ADMIN_SENHA", SENHA_DE_TESTE)
    return pasta / "usuarios.yaml"


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
def api(api_anonimo, logar):
    """O api_anonimo que ja entrou: a maioria dos testes nao e sobre o login."""
    return logar(api_anonimo)
