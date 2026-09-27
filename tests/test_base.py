"""O bloco base, servido em /base.txt.

Estes quatro casos vieram do tests/test_app.py, que sai no corte das telas
Jinja: /base.txt nao e HTML, nao muda com o corte, e era o unico lugar onde
ela tinha prova.
"""

from app import render


def test_download_do_bloco_base(api):
    r = api.get("/base.txt")
    assert r.status_code == 200
    assert "IMPORT-SANITY-V4" in r.text
    assert r.text.isascii()


def test_baixar_o_base_nao_grava_arquivo(api, tmp_path):
    # e o que o README promete: o corpo e montado na hora do download, entao
    # nao ha arquivo em out/ guardando uma versao antiga para o operador
    # conferir se esta desatualizada
    api.get("/base.txt")
    assert not (tmp_path / "out" / "_base.txt").exists()


def test_o_base_baixado_e_o_render_de_agora(api):
    # sem AS no peers.yaml o Rede e o de fabrica, e as duas pontas saem do
    # mesmo plan.py
    assert api.get("/base.txt").text == render.render_base()


def test_o_base_segue_o_as_gravado(api):
    # o caminho de ponta a ponta do PUT /api/rede: o AS vai para o topo do
    # yaml, e a proxima leitura do base ja sai com ele, sem reiniciar o app
    assert api.put("/api/rede",
                   json={"asn": "64500", "politica": ""}).status_code == 200
    texto = api.get("/base.txt").text
    assert "64500:1000" in texto
    assert "64512:" not in texto
