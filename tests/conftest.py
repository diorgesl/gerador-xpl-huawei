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


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Um TestClient com o peers.yaml, o out/ e o cache do bgpq4 em tmp_path.

    A API le o peers_mod.PEERS_YAML na hora de cada chamada, e o app.app
    guardou uma copia do caminho no import: os dois sao trocados, como na
    fixture `cliente` do test_app.py.
    """
    from fastapi.testclient import TestClient

    from app import app as mod
    from app import peers as peers_mod
    from app import render

    monkeypatch.setattr(peers_mod, "PEERS_YAML", tmp_path / "peers.yaml")
    monkeypatch.setattr(peers_mod, "OUT", tmp_path / "out")
    monkeypatch.setattr(render, "OUT", tmp_path / "out")
    monkeypatch.setattr(mod, "PEERS_YAML", tmp_path / "peers.yaml")
    monkeypatch.setattr(mod, "OUT", tmp_path / "out")
    monkeypatch.setattr(prefixes, "CACHE", tmp_path / "out" / ".cache")
    return TestClient(mod.app)
