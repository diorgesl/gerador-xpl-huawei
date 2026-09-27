"""A API JSON: formato de erro, plano e AS da rede."""

from fastapi.testclient import TestClient

from app import app as mod
from app import formulario, plan
from app import peers as peers_mod
from dados_api import CLIENTE, UPSTREAM
from test_render import peer_cliente, peer_upstream


def test_o_plano_traz_as_tabelas_do_plan_sem_copia(api):
    r = api.get("/api/plano")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["rede"] == {"asn": plan.ASN, "politica": ""}
    assert corpo["tipos"] == list(plan.TIPOS)
    assert corpo["lp_base"] == plan.LP_BASE
    assert corpo["route_limit"] == plan.ROUTE_LIMIT
    assert corpo["classes_cliente"] == list(plan.CLASSES_CLIENTE)
    assert corpo["tipos_com_criar_lista"] == list(plan.TIPOS_COM_APPLY_PEER)
    assert corpo["padroes"] == formulario._padroes(plan.Rede())
    assert corpo["campos_por_tipo"] == {
        c: list(t) for c, t in formulario.CAMPOS_POR_TIPO.items()}
    assert corpo["campos_por_tipo_grupo"]["aprendizado_ix"] == ["ix"]
    assert corpo["pop_usados"] == [] and corpo["aprendizado_usados"] == []


def test_o_plano_sugere_o_que_ja_foi_cadastrado(api, tmp_path):
    peers_mod.gravar([peer_cliente(), peer_upstream(id=2)], tmp_path / "peers.yaml")
    corpo = api.get("/api/plano").json()
    assert corpo["pop_usados"] == [2001]
    assert corpo["aprendizado_usados"] == [3100]


def test_gravar_o_as_da_rede(api, tmp_path):
    # 16 bits: o namespace e o proprio ASN e fica em branco
    r = api.put("/api/rede", json={"asn": "53062"})
    assert r.status_code == 200
    assert r.json() == {"asn": "53062", "politica": ""}
    assert peers_mod.carregar_asn(tmp_path / "peers.yaml").asn == 53062
    assert api.get("/api/plano").json()["rede"]["asn"] == "53062"


def test_asn_de_32_bits_pede_o_namespace_no_campo_dele(api, tmp_path):
    r = api.put("/api/rede", json={"asn": "4200000000"})
    assert r.status_code == 422
    assert set(r.json()["erros"]) == {"asn_politica"}
    assert not (tmp_path / "peers.yaml").exists()


def test_asn_de_32_bits_com_namespace_grava(api):
    r = api.put("/api/rede", json={"asn": "4200000000", "politica": "65000"})
    assert r.status_code == 200
    assert r.json() == {"asn": "4200000000", "politica": "65000"}


def test_asn_torto_e_recusado_no_campo(api):
    r = api.put("/api/rede", json={"asn": "abc"})
    assert r.status_code == 422
    assert r.json() == {"erros": {"asn_rede": "so digitos: abc"}, "avisos": []}


def test_corpo_fora_do_modelo_volta_no_formato_da_api(api):
    r = api.put("/api/rede", json={"asn": "53062", "xpto": "1"})
    assert r.status_code == 422
    assert "xpto" in r.json()["erros"]["_corpo"]


def test_fora_da_api_a_falha_inesperada_continua_texto_puro(api, monkeypatch):
    """O envelope JSON da API nao vaza para uma rota que nao e dela.

    O par deste caso era o `/bgpq4?forcar=abc`, que saiu no corte das telas:
    nao ha mais rota fora de /api que receba entrada tipada, entao o ramo de
    fora do _pedido_invalido ficou inalcancavel. O do _falha_inesperada nao
    ficou, e e o que este caso usa: um peers.yaml torto derruba o /base.txt.

    O que ele pega e o vazamento (tirar a guarda do prefixo e o envelope JSON
    aparece no /base.txt); o que ele NAO pega e a remocao do ramo, porque o
    texto puro que o ramo devolve e o mesmo do padrao do Starlette.
    """
    def quebrado(caminho):
        raise ValueError("peers.yaml: ASN 4200000000 nao cabe nos 16 bits")
    monkeypatch.setattr(peers_mod, "carregar_asn", quebrado)
    cliente = TestClient(mod.app, raise_server_exceptions=False)

    r = cliente.get("/base.txt")

    assert r.status_code == 500
    assert r.text == "Internal Server Error"


def test_yaml_quebrado_vira_500_em_json(api, monkeypatch):
    def quebrado(caminho):
        raise ValueError("peers.yaml: ASN 4200000000 nao cabe nos 16 bits")
    monkeypatch.setattr(peers_mod, "carregar_asn", quebrado)
    cliente = TestClient(mod.app, raise_server_exceptions=False)
    r = cliente.get("/api/plano")
    assert r.status_code == 500
    assert "nao cabe nos 16 bits" in r.json()["erros"]["_"]


def test_o_irr_devolve_os_prefixos_sem_gravar(api, tmp_path, fake_bgpq4):
    r = api.post("/api/irr", json={"asn": "268127"})
    assert r.status_code == 200, r.text
    assert r.json() == {"v4": ["45.169.232.0/22", "45.169.236.0/23"],
                        "v6": ["2001:db8::/32"]}
    assert not (tmp_path / "peers.yaml").exists()


def test_irr_sem_asn_e_recusado_no_campo(api):
    r = api.post("/api/irr", json={"asn": ""})
    assert r.status_code == 422
    assert r.json()["erros"] == {"asn": "informe o ASN antes de consultar o IRR"}


def test_irr_com_asn_torto_e_recusado_no_campo(api):
    r = api.post("/api/irr", json={"asn": "12a"})
    assert r.status_code == 422
    assert r.json()["erros"] == {"asn": "valor numerico invalido"}


def test_irr_sem_bgpq4_volta_502(api, tmp_path, monkeypatch):
    vazio = tmp_path / "sem-bgpq4"
    vazio.mkdir()
    monkeypatch.setenv("PATH", str(vazio))
    r = api.post("/api/irr", json={"asn": "268127"})
    assert r.status_code == 502
    assert "bgpq4 nao esta no PATH" in r.json()["erros"]["bgpq4"]


def test_irr_com_bgpq4_sem_permissao_volta_502(api, tmp_path, monkeypatch):
    # um bgpq4 no PATH sem permissao de execucao: o subprocess levanta
    # PermissionError, que o _rodar nao converte
    pasta = tmp_path / "bgpq4-travado"
    pasta.mkdir()
    binario = pasta / "bgpq4"
    binario.write_text("#!/bin/sh\n", encoding="ascii")
    binario.chmod(0o644)
    monkeypatch.setenv("PATH", str(pasta))
    r = api.post("/api/irr", json={"asn": "268127"})
    assert r.status_code == 502
    assert "bgpq4" in r.json()["erros"]


def test_o_as_gravado_chega_no_bloco_do_peer(api, tmp_path):
    """O AS do topo do yaml entra na config gerada, e nao so na resposta.

    test_gravar_o_as_da_rede ve a gravacao; quem via a ponta - o bloco saindo
    com o AS novo e as communities no namespace novo - era o test_app.py. O
    render tem os testes dele com um Rede montado a mao
    (test_o_bloco_do_peer_segue_o_asn_declarado); o que faltava era o caminho
    HTTP inteiro.
    """
    assert api.put("/api/rede", json={"asn": "64500", "politica": ""}).status_code == 200

    r = api.post("/api/peers", json=CLIENTE)

    assert r.status_code == 201, r.text
    bloco = (tmp_path / "out" / r.json()["arquivo"]).read_text(encoding="ascii")
    assert "bgp 64500" in bloco
    assert "64500:1110" in bloco
    assert "64512" not in bloco


def test_o_as_de_32_bits_com_namespace_chega_no_bloco(api, tmp_path):
    """As duas chaves: o ASN no bgp e no as-path, o namespace nas communities."""
    assert api.put("/api/rede", json={"asn": "264130", "politica": "64500"}).status_code == 200
    corpo = dict(CLIENTE, asn="264130", nome="Cliente 32", apelido="C32",
                 prefixos_v4=["198.51.100.0/24"],
                 sessao_v4_remoto="198.51.100.9")

    r = api.post("/api/peers", json=corpo)

    assert r.status_code == 201, r.text
    bloco = (tmp_path / "out" / r.json()["arquivo"]).read_text(encoding="ascii")
    assert "bgp 264130" in bloco
    assert "apply as-path 264130" in bloco
    assert "64500:1110" in bloco
    assert "264130:1110" not in bloco


def test_o_namespace_em_branco_apaga_a_chave(api, tmp_path):
    """Voltar para um AS de 16 bits limpa o asn_politica do yaml.

    A funcao tem teste (test_gravar_asn_limpa_o_namespace_que_a_tela_nao_mandou,
    em test_peers.py); a rota nao tinha.
    """
    arquivo = tmp_path / "peers.yaml"
    api.put("/api/rede", json={"asn": "264130", "politica": "64500"})
    assert "asn_politica" in arquivo.read_text(encoding="utf-8")

    r = api.put("/api/rede", json={"asn": "64500", "politica": ""})

    assert r.status_code == 200, r.text
    assert "asn_politica" not in arquivo.read_text(encoding="utf-8")


def test_o_as_fora_da_faixa_do_asn_e_erro_de_campo(api, tmp_path):
    """AS_TRANS e o que passa do teto de 32 bits caem no campo asn_rede.

    O ASN que nao e digito tem teste (test_asn_torto_e_recusado_no_campo); as
    duas faixas de valor, nao.
    """
    r = api.put("/api/rede", json={"asn": "23456", "politica": ""})
    assert r.status_code == 422
    assert r.json()["erros"]["asn_rede"] == "ASN reservado pela IANA: 23456"

    r = api.put("/api/rede", json={"asn": "99999999999", "politica": ""})
    assert r.status_code == 422
    assert r.json()["erros"]["asn_rede"] == "ASN de 1 a 4294967294: 99999999999"

    # a recusa e antes da escrita: o arquivo fica com o AS de fabrica
    assert peers_mod.carregar_asn(tmp_path / "peers.yaml").asn == plan.ASN_PADRAO


def test_o_as_em_branco_e_erro_de_campo(api, tmp_path):
    """Sem o AS nao ha o que gravar, e o namespace sozinho nao salva o campo."""
    for corpo in ({"asn": "", "politica": ""}, {"asn": "", "politica": "64500"}):
        r = api.put("/api/rede", json=corpo)
        assert r.status_code == 422, corpo
        assert r.json()["erros"]["asn_rede"] == "informe o AS da rede"

    assert not (tmp_path / "peers.yaml").exists()


def test_o_aviso_de_origem_fora_da_tabela_chega_no_upstream(api, tmp_path):
    """O aviso de origem sai no envelope, e o peer grava assim mesmo.

    O peer de upstream do cadastro real carrega origem de downstream; o que
    esta leva faz e o operador ver isso, e nao impedir o salvar.
    """
    r = api.post("/api/peers", json=dict(UPSTREAM, origem="1100"))

    assert r.status_code == 201, r.text
    assert [a["campo"] for a in r.json()["avisos"]] == ["origem"]
    assert "nao esta na tabela do upstream" in r.json()["avisos"][0]["mensagem"]
    assert [p.origem for p in peers_mod.carregar(tmp_path / "peers.yaml")] == [1100]


def test_a_origem_da_tabela_nao_avisa(api):
    # o peer em branco e a copia nascem com a origem do default, que esta
    # dentro da tabela: quem ve o aviso e o cadastro antigo, e nao o novo
    corpo = api.get("/api/peers/novo", params={"tipo": "upstream"}).json()
    r = api.post("/api/peers", json=dict(UPSTREAM, origem=corpo["formulario"]["origem"]))

    assert r.status_code == 201, r.text
    assert r.json()["avisos"] == []
