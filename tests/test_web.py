"""O FastAPI servindo o build do front.

O uvicorn e o unico processo em producao: ele serve a API em /api, os arquivos
do build em /assets e o index.html da SPA nas rotas dela. As telas HTML antigas
continuam em /, /peer/... e /grupo/... ate o corte.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def dist(tmp_path, monkeypatch):
    """Um build de mentira, com o index.html e um asset."""
    pasta = tmp_path / "dist"
    (pasta / "assets").mkdir(parents=True)
    (pasta / "index.html").write_text("<html><body><div id=root></div></body></html>")
    (pasta / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setenv("BGPGEN_WEB", str(pasta))
    return pasta


@pytest.fixture
def web(dist, api):
    """O cliente da API, que e o mesmo TestClient do app inteiro."""
    return api


ROTAS_DA_SPA = ["/peers", "/peers/7", "/peers/novo", "/grupos", "/grupos/2",
                "/prefixos", "/base", "/configuracoes"]


@pytest.mark.parametrize("rota", ROTAS_DA_SPA)
def test_as_rotas_da_spa_servem_o_index_do_build(web, rota):
    r = web.get(rota)
    assert r.status_code == 200
    assert "<div id=root>" in r.text


def test_o_asset_sai_do_build(web):
    r = web.get("/assets/app.js")
    assert r.status_code == 200
    assert r.text == "console.log(1)"


def test_o_favicon_sai_da_raiz_do_build(web, dist):
    """O favicon sai na raiz do dist, e nao em /assets.

    O index.html que o Vite gera linka /favicon.svg, entao sem esta rota o
    navegador pede um arquivo que ninguem serve, com o build inteiro no lugar.
    A rota e deste arquivo, e nao um curinga da raiz: um curinga engoliria as
    telas antigas do singular, que moram em /peer/... e /grupo/...
    """
    (dist / "favicon.svg").write_text("<svg>icone</svg>")
    r = web.get("/favicon.svg")
    assert r.status_code == 200
    assert r.text == "<svg>icone</svg>"


def test_sem_favicon_no_build_a_rota_responde_404(web, dist):
    """A outra direcao, e o que a guarda do `is_file()` esta segurando.

    Sem ela o FileResponse do Starlette estoura na hora de mandar o arquivo, e
    um build que nao gerou o favicon derruba a requisicao em vez de dizer que
    nao tem. Medido com a guarda fora: 500. Os dois casos sao precisos juntos:
    este sozinho passa com a rota nem existindo, porque o 404 da rota nao
    mapeada e igual, e o de cima sozinho passa sem guarda nenhuma.
    """
    assert not (dist / "favicon.svg").exists()
    assert web.get("/favicon.svg").status_code == 404


def test_o_asset_nao_sai_do_diretorio_do_build(web, dist):
    """O `..` percent-encoded tem que parar na conferencia do caminho resolvido.

    O `..` vai PERCENT-ENCODED de proposito: o httpx normaliza um `..` literal
    antes de mandar (RFC 3986), entao a requisicao chegaria em /etc/passwd,
    numa rota que nao existe, e o teste passaria sem tocar na conferencia do
    caminho resolvido.

    O alvo precisa EXISTIR, e e por isso que este /etc/passwd e de mentira e
    mora em tmp_path: a partir de dist/assets os dois `..` chegam em tmp_path,
    e nao na raiz do sistema. Sem o arquivo, quem responde o 404 e o
    `is_file()`, e a conferencia do diretorio - a linha que este teste existe
    para cobrir - nao chega a ser avaliada.
    """
    (dist.parent / "etc").mkdir()
    (dist.parent / "etc" / "passwd").write_text("nao pode sair daqui")
    r = web.get("/assets/%2e%2e%2f%2e%2e%2fetc%2fpasswd")
    assert r.status_code in (404, 400)
    assert "nao pode sair daqui" not in r.text


def test_a_guarda_do_caminho_segue_o_symlink_antes_de_conferir(web, dist):
    """Um link dentro dos assets apontando para fora do build.

    E o que justifica a conferencia ser feita no caminho resolvido e nao no
    texto que veio na URL: `assets/solto.js` parece um asset legitimo, e so o
    `resolve()` mostra que ele entrega o peers.yaml.
    """
    cadastro = dist.parent / "peers.yaml"
    cadastro.write_text("nao pode sair daqui")
    (dist / "assets" / "solto.js").symlink_to(cadastro)
    r = web.get("/assets/solto.js")
    assert r.status_code in (404, 400)
    assert "nao pode sair daqui" not in r.text


def test_sem_build_as_rotas_da_spa_respondem_503(tmp_path, monkeypatch, api):
    monkeypatch.setenv("BGPGEN_WEB", str(tmp_path / "nao-existe"))
    r = api.get("/peers")
    assert r.status_code == 503
    assert "npm run build" in r.text


def test_sem_build_a_api_continua_funcionando(tmp_path, monkeypatch, api):
    monkeypatch.setenv("BGPGEN_WEB", str(tmp_path / "nao-existe"))
    r = api.get("/api/plano")
    assert r.status_code == 200


def test_as_telas_antigas_continuam_no_ar(web):
    # o HEALTHCHECK do Dockerfile bate em / esperando 200
    assert web.get("/").status_code == 200
    assert web.get("/peer/novo").status_code == 200
    assert web.get("/grupo/novo").status_code == 200


def test_o_base_txt_continua_sendo_o_texto_e_nao_o_index(web):
    r = web.get("/base.txt")
    assert r.status_code == 200
    assert "<div id=root>" not in r.text


def test_a_rota_da_spa_nao_engole_a_do_peer_de_verdade(web):
    # /peer/novo e a tela HTML antiga, e nao /peers/novo
    assert web.get("/peer/novo").status_code == 200
    assert "id=root" not in web.get("/peer/novo").text
