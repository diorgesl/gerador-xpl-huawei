"""A API dos grupos."""

from app import peers as peers_mod
from dados_api import GRUPO_PARCEIROS, GRUPO_UPSTREAM, arvore, membro_de


def test_criar_grupo_grava_o_yaml_e_o_bloco(api, tmp_path):
    r = api.post("/api/grupos", json=GRUPO_PARCEIROS)
    assert r.status_code == 201, r.text
    assert r.json()["arquivo"] == "grupo-PARCEIROS_CDN.txt"
    grupos = peers_mod.carregar_grupos(tmp_path / "peers.yaml")
    assert [g.nome for g in grupos] == ["PARCEIROS_CDN"]
    assert (tmp_path / "out" / "grupo-PARCEIROS_CDN.txt").exists()


def test_criar_com_id_de_outro_grupo_e_recusado(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    antes = arvore(tmp_path)
    r = api.post("/api/grupos", json=dict(GRUPO_UPSTREAM, id="0"))
    assert r.status_code == 422
    assert r.json()["erros"]["id"] == "ID ja usado pelo grupo PARCEIROS_CDN"
    assert arvore(tmp_path) == antes


def test_nome_repetido_e_recusado(api):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    r = api.post("/api/grupos", json=GRUPO_PARCEIROS)
    assert r.status_code == 422
    assert r.json()["erros"]["nome"] == "nome ja usado pelo grupo 0"


def test_a_lista_conta_os_membros(api):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    assert api.post("/api/peers", json=membro_de(0)).status_code == 201
    assert api.get("/api/grupos").json() == [
        {"id": 0, "nome": "PARCEIROS_CDN", "tipo": "parceiro", "membros": 1}]


def test_o_registro_lista_os_membros(api):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    api.post("/api/peers", json=membro_de(0))
    assert api.get("/api/grupos/0").json()["membros"] == [{"id": 1, "token": "268127"}]


def test_o_grupo_novo_de_ix_poe_o_aprendizado_no_campo_do_ix(api):
    f = api.get("/api/grupos/novo", params={"tipo": "ix"}).json()["formulario"]
    assert (f["aprendizado"], f["aprendizado_ix"], f["lp_base"]) == ("", "3010", "190")


def test_tipo_desconhecido_vira_parceiro(api):
    corpo = api.get("/api/grupos/novo", params={"tipo": "xyz"}).json()
    assert corpo["formulario"]["tipo"] == "parceiro"


def test_a_copia_do_grupo_troca_so_o_id(api):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    original = api.get("/api/grupos/0").json()["formulario"]
    copia = api.get("/api/grupos/0/copia").json()
    assert copia["id"] == 1 and copia["membros"] == []
    assert copia["formulario"] == dict(original, id="1")


def test_editar_mantem_o_id_da_url(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    r = api.put("/api/grupos/0", json=dict(GRUPO_PARCEIROS, id="5", lp_base="250"))
    assert r.status_code == 200, r.text
    grupos = peers_mod.carregar_grupos(tmp_path / "peers.yaml")
    assert [(g.id, g.lp_base) for g in grupos] == [(0, 250)]


def test_renomear_apaga_o_bloco_antigo(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    assert api.put("/api/grupos/0", json=dict(GRUPO_PARCEIROS, nome="CDNS")).status_code == 200
    assert not (tmp_path / "out" / "grupo-PARCEIROS_CDN.txt").exists()
    assert (tmp_path / "out" / "grupo-CDNS.txt").exists()


def test_salvar_o_que_o_get_do_grupo_devolveu_nao_muda_nada(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_UPSTREAM)
    antes = arvore(tmp_path)
    formulario = api.get("/api/grupos/0").json()["formulario"]
    assert api.put("/api/grupos/0", json=formulario).status_code == 200
    assert arvore(tmp_path) == antes


def test_excluir_grupo_com_membro_e_recusado_sem_mexer_em_nada(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    api.post("/api/peers", json=membro_de(0))
    antes = arvore(tmp_path)
    r = api.delete("/api/grupos/0")
    assert r.status_code == 409
    assert "268127" in r.json()["erros"]["membros"]
    assert arvore(tmp_path) == antes


def test_excluir_grupo_sem_membro(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    assert api.delete("/api/grupos/0").status_code == 204
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []
    assert not (tmp_path / "out" / "grupo-PARCEIROS_CDN.txt").exists()


def test_grupo_que_nao_existe_e_404(api):
    assert api.get("/api/grupos/7").status_code == 404
    assert api.get("/api/grupos/7/copia").status_code == 404
    assert api.put("/api/grupos/7", json=GRUPO_PARCEIROS).status_code == 404
    assert api.delete("/api/grupos/7").status_code == 404


def _salvo(tmp_path, nome):
    return (tmp_path / "out" / nome).read_text(encoding="ascii")


def test_a_previa_do_grupo_e_o_bloco_que_o_salvar_escreve(api, tmp_path):
    previa = api.post("/api/grupos/previa", json=GRUPO_UPSTREAM).json()
    assert previa["erros"] == {} and previa["salvo"] is None
    assert previa["arquivo"] == "grupo-OPERADORA.txt"
    assert "xpl route-filter APPLY-PEER-OPERADORA" in previa["criar_lista"]
    api.post("/api/grupos", json=GRUPO_UPSTREAM)
    assert _salvo(tmp_path, "grupo-OPERADORA.txt") == previa["bloco"]


def test_o_grupo_de_parceiro_nao_tem_quadro(api):
    assert api.post("/api/grupos/previa", json=GRUPO_PARCEIROS).json()["criar_lista"] is None


def test_a_previa_do_grupo_nao_grava_nada(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    antes = arvore(tmp_path)
    api.post("/api/grupos/previa", params={"id": 0},
             json=dict(GRUPO_PARCEIROS, lp_base="250"))
    api.post("/api/grupos/previa", json=GRUPO_UPSTREAM)
    assert arvore(tmp_path) == antes


def test_a_previa_de_grupo_salvo_traz_o_arquivo(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    previa = api.post("/api/grupos/previa", params={"id": 0},
                      json=GRUPO_PARCEIROS).json()
    assert previa["salvo"] == _salvo(tmp_path, "grupo-PARCEIROS_CDN.txt")
    assert previa["bloco"] == previa["salvo"]


def test_a_previa_de_grupo_novo_com_id_existente_mostra_o_erro(api):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    r = api.post("/api/grupos/previa", json=dict(GRUPO_UPSTREAM, id="0"))
    assert r.status_code == 200
    assert r.json()["erros"]["id"] == "ID ja usado pelo grupo PARCEIROS_CDN"
    assert r.json()["bloco"] is None


def test_a_saida_do_grupo(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_UPSTREAM)
    corpo = api.get("/api/grupos/0/saida").json()
    assert corpo["bloco"] == _salvo(tmp_path, "grupo-OPERADORA.txt")
    assert corpo["remover"] is None
    assert "xpl community-list CL-PEER-OPERADORA" in corpo["criar_lista"]
    assert corpo["arquivo"] == "grupo-OPERADORA.txt"


def test_a_saida_de_grupo_que_nao_existe_e_404(api):
    assert api.get("/api/grupos/3/saida").status_code == 404
