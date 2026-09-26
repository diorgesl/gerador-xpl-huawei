"""A API dos peers."""

from app import peers as peers_mod
from app.api import modelo_do_peer
from dados_api import CLIENTE, UPSTREAM, IX, arvore
from test_render import peer_cliente, peer_ix


def _grava(tmp_path, *peers):
    peers_mod.gravar(list(peers), tmp_path / "peers.yaml")


def test_a_lista_comeca_vazia(api):
    assert api.get("/api/peers").json() == []


def test_a_lista_resume_cada_peer(api, tmp_path):
    _grava(tmp_path, peer_cliente(), peer_ix())
    assert api.get("/api/peers").json() == [
        {"id": 1, "token": "268127", "tipo": "cliente", "asn": 268127,
         "apelido": "", "nome": "Cliente ACME", "grupo_id": None},
        {"id": 10, "token": "IX-SP", "tipo": "ix", "asn": 26162,
         "apelido": "IX-SP", "nome": "IX.br Sao Paulo", "grupo_id": None},
    ]


def test_o_peer_novo_traz_os_defaults_do_tipo(api):
    corpo = api.get("/api/peers/novo", params={"tipo": "upstream"}).json()
    f = corpo["formulario"]
    assert (corpo["id"], corpo["token"]) == (0, "")
    assert (f["tipo"], f["lp_base"], f["route_limit"]) == ("upstream", "100", "1500000")
    assert (f["timer_keepalive"], f["timer_hold"]) == ("10", "30")
    assert (f["aprendizado"], f["origem"], f["asn"]) == ("3100", "1400", "")


def test_o_peer_novo_pula_o_id_ocupado(api, tmp_path):
    _grava(tmp_path, peer_cliente(id=0))
    assert api.get("/api/peers/novo").json()["id"] == 1


def test_tipo_desconhecido_vira_cliente(api):
    corpo = api.get("/api/peers/novo", params={"tipo": "xyz"}).json()
    assert corpo["formulario"]["tipo"] == "cliente"


def test_o_registro_traz_o_formulario_do_peer(api, tmp_path):
    peer = peer_ix()
    _grava(tmp_path, peer)
    corpo = api.get("/api/peers/10").json()
    assert corpo["token"] == "IX-SP"
    assert corpo["formulario"] == modelo_do_peer(peer).model_dump()


def test_id_que_nao_existe_e_404(api):
    r = api.get("/api/peers/42")
    assert r.status_code == 404
    assert r.json() == {"erros": {"_": "peer nao encontrado"}, "avisos": []}


def test_id_que_nao_e_numero_volta_422_no_formato_da_api(api):
    r = api.get("/api/peers/abc")
    assert r.status_code == 422
    assert "ident" in r.json()["erros"]["_corpo"]


def test_a_copia_troca_so_o_id(api, tmp_path):
    _grava(tmp_path, peer_cliente(id=0), peer_ix())
    corpo = api.get("/api/peers/0/copia").json()
    original = modelo_do_peer(peer_cliente(id=0)).model_dump()
    assert corpo["id"] == 1
    assert corpo["token"] == "268127"
    assert corpo["formulario"] == dict(original, id="1")


def test_a_copia_nao_grava_nada(api, tmp_path):
    _grava(tmp_path, peer_cliente())
    antes = arvore(tmp_path)
    assert api.get("/api/peers/1/copia").status_code == 200
    assert arvore(tmp_path) == antes


def test_a_copia_de_id_que_nao_existe_e_404(api):
    assert api.get("/api/peers/3/copia").status_code == 404


def test_criar_grava_o_yaml_e_o_bloco(api, tmp_path):
    r = api.post("/api/peers", json=CLIENTE)
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["arquivo"] == "268127-cliente.txt"
    assert (corpo["registro"]["id"], corpo["registro"]["token"]) == (0, "268127")
    assert [p.asn for p in peers_mod.carregar(tmp_path / "peers.yaml")] == [268127]
    assert (tmp_path / "out" / "268127-cliente.txt").exists()


def test_erro_de_campo_volta_422_e_nao_grava(api, tmp_path):
    r = api.post("/api/peers", json=dict(CLIENTE, asn="abc"))
    assert r.status_code == 422
    assert r.json()["erros"]["asn"] == "valor numerico invalido"
    assert arvore(tmp_path) == {}


def test_asn_repetido_e_recusado_no_campo(api):
    api.post("/api/peers", json=CLIENTE)
    r = api.post("/api/peers", json=dict(
        CLIENTE, sessao_v4_remoto="198.51.100.3", prefixos_v4=["45.169.240.0/22"]))
    assert r.status_code == 422
    assert r.json()["erros"]["asn"] == "ASN ja usado pelo peer Cliente ACME"


def test_nome_com_acento_volta_422_no_campo(api, tmp_path):
    r = api.post("/api/peers", json=dict(CLIENTE, nome="Cliente S" + chr(0xE3) + "o Paulo"))
    assert r.status_code == 422
    assert r.json()["erros"]["nome"] == "nome so aceita ASCII puro, sem acento"
    assert arvore(tmp_path) == {}


def test_campo_desconhecido_volta_422_nomeando_o_campo(api, tmp_path):
    r = api.post("/api/peers", json=dict(CLIENTE, xpto="1"))
    assert r.status_code == 422
    assert "xpto" in r.json()["erros"]["_corpo"]
    assert arvore(tmp_path) == {}


def test_asn_privado_salva_com_aviso(api):
    r = api.post("/api/peers", json=dict(CLIENTE, asn="64500",
                                          descricao="CLIENTE-AS64500"))
    assert r.status_code == 201, r.text
    assert {"campo": "asn",
            "mensagem": "ASN privado: confirme que o peer tambem o usa"} in r.json()["avisos"]


def test_trocar_o_asn_apaga_o_bloco_antigo(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    r = api.put("/api/peers/0", json=dict(CLIENTE, asn="268128"))
    assert r.status_code == 200, r.text
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()
    assert (tmp_path / "out" / "268128-cliente.txt").exists()


def test_trocar_o_id_no_corpo_move_o_registro_da_url(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    r = api.put("/api/peers/0", json=dict(CLIENTE, id="7"))
    assert r.status_code == 200, r.text
    assert r.json()["registro"]["id"] == 7
    assert [p.id for p in peers_mod.carregar(tmp_path / "peers.yaml")] == [7]
    assert api.get("/api/peers/0").status_code == 404


def test_atualizar_id_que_nao_existe_e_404(api):
    assert api.put("/api/peers/5", json=CLIENTE).status_code == 404


def test_salvar_o_que_o_get_devolveu_nao_muda_nada(api, tmp_path):
    api.post("/api/peers", json=UPSTREAM)
    antes = arvore(tmp_path)
    formulario = api.get("/api/peers/0").json()["formulario"]
    assert api.put("/api/peers/0", json=formulario).status_code == 200
    assert arvore(tmp_path) == antes


def test_excluir_apaga_o_registro_e_o_bloco(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    assert api.delete("/api/peers/0").status_code == 204
    assert peers_mod.carregar(tmp_path / "peers.yaml") == []
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()
    assert api.delete("/api/peers/0").status_code == 404


def _salvo(tmp_path, nome="268127-cliente.txt"):
    return (tmp_path / "out" / nome).read_text(encoding="ascii")


def test_a_previa_do_peer_novo_e_o_bloco_que_o_salvar_escreve(api, tmp_path):
    previa = api.post("/api/peers/previa", json=CLIENTE).json()
    assert previa["erros"] == {} and previa["salvo"] is None
    assert previa["arquivo"] == "268127-cliente.txt"
    api.post("/api/peers", json=CLIENTE)
    assert _salvo(tmp_path) == previa["bloco"]


def test_a_previa_nao_grava_nada(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    antes = arvore(tmp_path)
    api.post("/api/peers/previa", params={"id": 0}, json=dict(CLIENTE, lp_base="250"))
    api.post("/api/peers/previa", json=UPSTREAM)
    assert arvore(tmp_path) == antes


def test_a_previa_com_erro_volta_200_sem_bloco(api):
    r = api.post("/api/peers/previa", json=dict(CLIENTE, asn="abc"))
    assert r.status_code == 200
    assert r.json()["erros"]["asn"] == "valor numerico invalido"
    assert r.json()["bloco"] is None


def test_a_previa_de_um_peer_salvo_traz_o_arquivo_de_out(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    previa = api.post("/api/peers/previa", params={"id": 0}, json=CLIENTE).json()
    assert previa["salvo"] == _salvo(tmp_path)
    assert previa["bloco"] == previa["salvo"]


def test_arquivo_apagado_de_out_vira_salvo_nulo(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    (tmp_path / "out" / "268127-cliente.txt").unlink()
    previa = api.post("/api/peers/previa", params={"id": 0}, json=CLIENTE).json()
    assert previa["salvo"] is None


def test_o_quadro_ao_criar_so_sai_nos_tipos_com_cl_peer(api):
    cliente = api.post("/api/peers/previa", json=CLIENTE).json()
    assert "xpl community-list CL-PEER-268127" in cliente["criar_lista"]
    assert api.post("/api/peers/previa", json=IX).json()["criar_lista"] is None


def test_a_previa_com_grupo_que_nao_existe_aponta_o_campo(api):
    r = api.post("/api/peers/previa", json=dict(CLIENTE, grupo_id="9"))
    assert r.json()["erros"]["grupo_id"] == "grupo nao encontrado"
    assert r.json()["bloco"] is None


def test_a_saida_traz_bloco_remocao_e_quadro(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    corpo = api.get("/api/peers/0/saida").json()
    assert corpo["bloco"] == _salvo(tmp_path)
    assert "undo peer 198.51.100.2" in corpo["remover"]
    assert "APPLY-PEER-268127" in corpo["criar_lista"]
    assert corpo["arquivo"] == "268127-cliente.txt"


def test_a_saida_de_membro_de_grupo_que_saiu_e_recusada(api, tmp_path):
    peers_mod.gravar([peer_cliente(id=0, grupo_id=9)], tmp_path / "peers.yaml")
    r = api.get("/api/peers/0/saida")
    assert r.status_code == 422
    assert r.json()["erros"]["grupo_id"] == "grupo nao encontrado"


def test_a_saida_de_id_que_nao_existe_e_404(api):
    assert api.get("/api/peers/3/saida").status_code == 404
