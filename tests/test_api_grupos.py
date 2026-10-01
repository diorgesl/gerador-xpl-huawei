"""A API dos grupos."""

from app import peers as peers_mod
from app import plan
from dados_api import (ASN_DE_TESTE, CLIENTE, GRUPO_PARCEIROS,
                       GRUPO_UPSTREAM, arvore, caminho_tenant, membro_de)


def test_criar_grupo_grava_o_yaml_e_o_bloco(api, tmp_path):
    r = api.post("/api/grupos", json=GRUPO_PARCEIROS)
    assert r.status_code == 201, r.text
    assert r.json()["arquivo"] == "grupo-PARCEIROS_CDN.txt"
    grupos = peers_mod.carregar_grupos(caminho_tenant(tmp_path))
    assert [g.nome for g in grupos] == ["PARCEIROS_CDN"]
    assert (tmp_path / "out" / str(ASN_DE_TESTE) / "grupo-PARCEIROS_CDN.txt").exists()


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
        {"id": 0, "nome": "PARCEIROS_CDN", "tipo": "parceiro",
         "tabela": "nenhuma", "membros": 1}]


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
    grupos = peers_mod.carregar_grupos(caminho_tenant(tmp_path))
    assert [(g.id, g.lp_base) for g in grupos] == [(0, 250)]


def test_renomear_apaga_o_bloco_antigo(api, tmp_path):
    api.post("/api/grupos", json=GRUPO_PARCEIROS)
    assert api.put("/api/grupos/0", json=dict(GRUPO_PARCEIROS, nome="CDNS")).status_code == 200
    assert not (tmp_path / "out" / str(ASN_DE_TESTE) / "grupo-PARCEIROS_CDN.txt").exists()
    assert (tmp_path / "out" / str(ASN_DE_TESTE) / "grupo-CDNS.txt").exists()


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
    assert peers_mod.carregar_grupos(caminho_tenant(tmp_path)) == []
    assert not (tmp_path / "out" / str(ASN_DE_TESTE) / "grupo-PARCEIROS_CDN.txt").exists()


def test_grupo_que_nao_existe_e_404(api):
    assert api.get("/api/grupos/7").status_code == 404
    assert api.get("/api/grupos/7/copia").status_code == 404
    assert api.put("/api/grupos/7", json=GRUPO_PARCEIROS).status_code == 404
    assert api.delete("/api/grupos/7").status_code == 404


def _salvo(tmp_path, nome):
    return (tmp_path / "out" / str(ASN_DE_TESTE) / nome).read_text(encoding="ascii")


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


def test_o_grupo_novo_pula_o_id_do_peer(api, tmp_path):
    """Peer e grupo dividem o espaco de ids, e o grupo novo desvia do peer.

    O proximo_id puro tem teste (test_proximo_id_desvia_do_peer_e_do_grupo_juntos,
    em test_peers.py); a rota que o operador usa nao tinha, e era o caso que o
    test_app.py pegava no formulario em branco do grupo.
    """
    assert api.post("/api/peers", json=CLIENTE).status_code == 201

    assert api.get("/api/grupos/novo").json()["id"] == 1


def test_criar_grupo_com_id_de_peer_e_recusado(api, tmp_path):
    """A recusa por id olha as duas listas.

    O id ja usado por outro GRUPO tem teste
    (test_criar_com_id_de_outro_grupo_e_recusado); o id de um PEER nao tinha, e
    e o caso em que a mensagem nomeia o outro tipo de registro.
    """
    api.post("/api/peers", json=CLIENTE)

    r = api.post("/api/grupos", json=dict(GRUPO_UPSTREAM, id="0", nome="OUTRO"))

    assert r.status_code == 422
    assert r.json()["erros"]["id"] == "ID 0 ja usado pelo peer Cliente ACME"
    assert peers_mod.carregar_grupos(caminho_tenant(tmp_path)) == []


def test_o_default_do_grupo_nao_engole_o_valor_zero(api, tmp_path):
    """Campo em branco cai na tabela do tipo; zero e zero; id torto nao derruba.

    Os tres sao o mesmo portao do grupo_do_formulario, e o test_app.py provava
    cada um num teste separado (o lp_base zero, o lp_base em branco e o id que
    nao e numero). O que separa os dois primeiros e o `is None` do helper: com
    `or`, o zero viraria o default do tipo em silencio.
    """
    assert api.post("/api/grupos", json=dict(GRUPO_PARCEIROS, lp_base="0")).status_code == 201
    assert api.post("/api/grupos", json=dict(GRUPO_PARCEIROS, nome="SEM_LP",
                                             lp_base="")).status_code == 201
    assert api.post("/api/grupos", json=dict(GRUPO_PARCEIROS, nome="ID_TORTO",
                                             id="abc")).status_code == 201

    grupos = peers_mod.carregar_grupos(caminho_tenant(tmp_path))
    assert [(g.nome, g.lp_base) for g in grupos] == [
        ("PARCEIROS_CDN", 0),
        ("SEM_LP", plan.LP_BASE["parceiro"]),
        ("ID_TORTO", plan.LP_BASE["parceiro"]),
    ]
    # o id torto nao virou um segundo registro no lugar de outro: os tres ids
    # sao tres e o grupo do id ilegivel entrou como registro novo
    assert len({g.id for g in grupos}) == 3


def test_valor_numerico_torto_no_grupo_e_erro_no_campo(api, tmp_path):
    """O lp_base que nao e numero nao vira default em silencio.

    A mensagem e a mesma do peer, e do lado do peer ela tem teste
    (test_api_peers.py::test_erro_de_campo_volta_422_e_nao_grava); do lado do
    grupo nao tinha depois que o test_app.py sair, apesar de serem listas de
    campos diferentes (CAMPOS_INT e CAMPOS_INT_GRUPO).
    """
    r = api.post("/api/grupos", json=dict(GRUPO_PARCEIROS, lp_base="trezentos"))

    assert r.status_code == 422
    assert r.json()["erros"]["lp_base"] == "valor numerico invalido"
    assert peers_mod.carregar_grupos(caminho_tenant(tmp_path)) == []


def test_o_irr_do_grupo_mescla_e_o_salvar_guarda_o_prefixo_limpo(
        api, tmp_path, fake_bgpq4):
    """O ciclo que o operador faz: consulta, decide manter o que saiu do IRR
    e salva. A marca e da tela, e o cadastro guarda o CIDR limpo."""
    # o grupo com prefixo proprio exige ASN: o filtro usa o ASN para o
    # blackhole e o confinamento de as-path
    grupo = dict(GRUPO_PARCEIROS, asn="64500",
                 prefixos_v4=["45.169.232.0/22", "45.169.240.0/24"])
    assert api.post("/api/grupos", json=grupo).status_code == 201
    # o 45.169.240.0/24 estava na tela e nao veio mais na consulta
    consulta = api.post("/api/irr", json={
        "asn": "14840", "v4": grupo["prefixos_v4"], "v6": []})
    assert consulta.status_code == 200, consulta.text
    linhas = consulta.json()["v4"]
    assert linhas == [
        "45.169.232.0/22",
        "45.169.236.0/23",
        "45.169.240.0/24  !- nao veio na consulta ao IRR"]
    salvo = api.put("/api/grupos/0", json=dict(grupo, prefixos_v4=linhas))
    assert salvo.status_code == 200, salvo.text
    (grupo,) = peers_mod.carregar_grupos(caminho_tenant(tmp_path))
    assert grupo.prefixos["v4"] == [
        "45.169.232.0/22", "45.169.236.0/23", "45.169.240.0/24"]


def test_o_grupo_novo_de_downstream_recebe_so_a_default(api):
    f = api.get("/api/grupos/novo", params={"tipo": "cliente"}).json()["formulario"]
    assert (f["default_route"], f["tabela"]) == (True, "nenhuma")


def test_a_lista_de_grupos_traz_a_tabela(api, tmp_path):
    peers_mod.gravar_grupos(
        [peers_mod.Grupo(id=3, nome="CLIENTES", tipo="cliente", classe="transito",
                         origem=1100, pop=2001, tabela="parcial")],
        caminho_tenant(tmp_path))
    assert api.get("/api/grupos").json()[0]["tabela"] == "parcial"


def test_o_plano_publica_as_tabelas(api):
    assert api.get("/api/plano").json()["tabelas"] == list(plan.TABELAS)


def test_a_saida_do_grupo_recusa_tabela_invalida(api, tmp_path):
    peers_mod.gravar_grupos(
        [peers_mod.Grupo(id=3, nome="CLIENTES", tipo="cliente", classe="transito",
                         origem=1100, pop=2001, tabela="tudo")],
        caminho_tenant(tmp_path))
    r = api.get("/api/grupos/3/saida")
    assert r.status_code == 422
    assert "tabela" in r.json()["erros"]
