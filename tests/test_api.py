"""A API JSON: formato de erro, plano e AS da rede."""

from fastapi.testclient import TestClient

from app import app as mod
from app import formulario, plan, tenants
from app import peers as peers_mod
from dados_api import ASN_DE_TESTE, CLIENTE, UPSTREAM, caminho_tenant
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
    peers_mod.gravar([peer_cliente(), peer_upstream(id=2)], caminho_tenant(tmp_path))
    corpo = api.get("/api/plano").json()
    assert corpo["pop_usados"] == [2001]
    assert corpo["aprendizado_usados"] == [3100]


def test_o_put_da_rede_grava_no_arquivo_do_tenant(api, tmp_path):
    """O ASN do corpo nao existe mais: ele e o nome do arquivo, e o eco sai dele.

    16 bits: o namespace e o proprio ASN e fica em branco.
    """
    r = api.put("/api/rede", json={"politica": ""})
    assert r.status_code == 200
    assert r.json() == {"asn": str(ASN_DE_TESTE), "politica": ""}
    assert peers_mod.carregar_asn(caminho_tenant(tmp_path)).asn == ASN_DE_TESTE
    assert api.get("/api/plano").json()["rede"]["asn"] == str(ASN_DE_TESTE)


def test_o_tenant_de_32_bits_nao_perde_o_namespace(api):
    """O par ASN/namespace e do arquivo mais o corpo, e so o corpo se edita.

    Um ASN de 32 bits sem namespace nao tem como virar community standard
    nenhuma, e o namespace em branco e o caminho de conserto de quem
    declarou o AS errado. Como o AS vem do nome do arquivo, o par so
    desfecha por aqui, e a recusa vem no campo que a tela mostra.
    """
    tenants.criar(264130, 65532)
    r = api.put("/api/rede", params={"asn": 264130}, json={"politica": ""})
    assert r.status_code == 422
    assert set(r.json()["erros"]) == {"asn_politica"}
    assert "informe o namespace" in r.json()["erros"]["asn_politica"]


def test_o_namespace_do_tenant_de_32_bits_grava(api):
    tenants.criar(264130, 65532)
    r = api.put("/api/rede", params={"asn": 264130}, json={"politica": "65000"})
    assert r.status_code == 200
    assert r.json() == {"asn": "264130", "politica": "65000"}


def test_corpo_fora_do_modelo_volta_no_formato_da_api(api):
    r = api.put("/api/rede", json={"politica": "", "xpto": "1"})
    assert r.status_code == 422
    assert "xpto" in r.json()["erros"]["_corpo"]


def test_fora_da_api_a_falha_inesperada_continua_texto_puro(api, logar, monkeypatch):
    """O envelope JSON da API nao vaza para uma rota que nao e dela.

    O par deste caso era o `/bgpq4?forcar=abc`, que saiu no corte das telas:
    nao ha mais rota fora de /api que receba entrada tipada, entao o ramo de
    fora do _pedido_invalido ficou inalcancavel. O do _falha_inesperada nao
    ficou, e e o que este caso usa: um peers.yaml torto derruba o /base.txt.

    O que ele pega e o vazamento (tirar a guarda do prefixo e o envelope JSON
    aparece no /base.txt); o que ele NAO pega e a remocao do ramo, porque o
    texto puro que o ramo devolve e o mesmo do padrao do Starlette.
    """
    # o patch agora e no carregar_rede: e ele que o /base.txt chama desde que
    # o Rede do tenant sai do nome do arquivo e do namespace de dentro. Com o
    # nome velho o caso continuaria passando por acidente, porque o yaml
    # torto dele nao e lido por rota nenhuma.
    def quebrado(caminho, asn):
        raise ValueError("peers/64512.yaml: ASN 4200000000 nao cabe nos 16 bits")
    monkeypatch.setattr(peers_mod, "carregar_rede", quebrado)
    cliente = logar(TestClient(mod.app, raise_server_exceptions=False))

    r = cliente.get("/base.txt", params={"asn": ASN_DE_TESTE})

    assert r.status_code == 500
    assert r.text == "Internal Server Error"


def test_yaml_quebrado_vira_500_em_json(api, logar, monkeypatch):
    def quebrado(caminho, asn):
        raise ValueError("peers/64512.yaml: ASN 4200000000 nao cabe nos 16 bits")
    monkeypatch.setattr(peers_mod, "carregar_rede", quebrado)
    cliente = logar(TestClient(mod.app, raise_server_exceptions=False))
    r = cliente.get("/api/plano", params={"asn": ASN_DE_TESTE})
    assert r.status_code == 500
    assert "nao cabe nos 16 bits" in r.json()["erros"]["_"]


def test_o_irr_devolve_os_prefixos_sem_gravar(api, tmp_path, fake_bgpq4):
    # a consulta escreve o cache do bgpq4, e isso e dela; o que ela nao toca
    # e o cadastro do tenant
    cadastro = caminho_tenant(tmp_path)
    antes = cadastro.read_bytes()
    r = api.post("/api/irr", json={"asn": "268127"})
    assert r.status_code == 200, r.text
    assert r.json() == {"v4": ["45.169.232.0/22", "45.169.236.0/23"],
                        "v6": ["2001:db8::/32"]}
    assert cadastro.read_bytes() == antes


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


def test_o_asn_do_tenant_chega_no_bloco_do_peer(api, tmp_path):
    """O ASN do nome do arquivo entra na config gerada, e nao so na resposta.

    O render tem os testes dele com um Rede montado a mao
    (test_o_bloco_do_peer_segue_o_asn_declarado); o que faltava era o
    caminho HTTP inteiro: o tenant do ASN 64500, e o bloco saindo com o AS
    dele e as communities no namespace dele.
    """
    tenants.criar(64500)

    r = api.post("/api/peers", json=CLIENTE, params={"asn": 64500})

    assert r.status_code == 201, r.text
    bloco = (tmp_path / "out" / "64500" / r.json()["arquivo"]).read_text(
        encoding="ascii")
    assert "bgp 64500" in bloco
    assert "64500:1110" in bloco
    assert "64512" not in bloco


def test_o_as_de_32_bits_com_namespace_chega_no_bloco(api, tmp_path):
    """As duas chaves: o ASN no bgp e no as-path, o namespace nas communities."""
    tenants.criar(264130, 64500)
    # full: o `apply as-path` do ASN sai do prepend do export, que o modo
    # nenhuma (o do POST sem tabela) nao tem
    corpo = dict(CLIENTE, asn="264130", nome="Cliente 32", apelido="C32",
                 prefixos_v4=["198.51.100.0/24"],
                 sessao_v4_remoto="198.51.100.9", tabela="full")

    r = api.post("/api/peers", json=corpo, params={"asn": 264130})

    assert r.status_code == 201, r.text
    bloco = (tmp_path / "out" / "264130" / r.json()["arquivo"]).read_text(
        encoding="ascii")
    assert "bgp 264130" in bloco
    assert "apply as-path 264130" in bloco
    assert "64500:1110" in bloco
    assert "264130:1110" not in bloco


def test_o_namespace_em_branco_apaga_a_chave(api, tmp_path):
    """O namespace volta a ser o proprio ASN, e a chave sai do arquivo.

    A funcao tem teste (test_gravar_asn_limpa_o_namespace_que_a_tela_nao_mandou,
    em test_peers.py); a rota nao tinha.
    """
    arquivo = caminho_tenant(tmp_path)
    api.put("/api/rede", json={"politica": "64500"})
    assert "asn_politica" in arquivo.read_text(encoding="utf-8")

    r = api.put("/api/rede", json={"politica": ""})

    assert r.status_code == 200, r.text
    assert "asn_politica" not in arquivo.read_text(encoding="utf-8")


def test_o_namespace_fora_da_faixa_e_erro_de_campo(api, tmp_path):
    """O namespace fora dos 16 bits da RFC 1997 cai no campo asn_politica.

    E o que sobrou do formulario do topo agora que o ASN e o nome do
    arquivo: o unico campo que a rota ainda le do corpo.
    """
    r = api.put("/api/rede", json={"politica": "999999"})
    assert r.status_code == 422
    assert r.json()["erros"]["asn_politica"] == (
        "namespace das standard vai de 1 a 65535: o ASN de 32 bits fica no "
        "campo ao lado")

    # a recusa e antes da escrita: o arquivo fica com o AS do tenant
    assert peers_mod.carregar_asn(caminho_tenant(tmp_path)).asn == ASN_DE_TESTE


def test_o_aviso_de_origem_fora_da_tabela_chega_no_upstream(api, tmp_path):
    """O aviso de origem sai no envelope, e o peer grava assim mesmo.

    Vale para a origem fora da tabela do tipo que nao e anunciavel (aqui a do
    PNI num upstream). A anunciavel, 1000 e 11xx, e erro fora do downstream:
    a tabela parcial e o EXPORT-SANITY leem a marca.
    """
    r = api.post("/api/peers", json=dict(UPSTREAM, origem="1500"))

    assert r.status_code == 201, r.text
    assert [a["campo"] for a in r.json()["avisos"]] == ["origem"]
    assert "nao esta na tabela do upstream" in r.json()["avisos"][0]["mensagem"]
    assert [p.origem for p in peers_mod.carregar(caminho_tenant(tmp_path))] == [1500]


def test_upstream_com_origem_de_cliente_e_recusado(api):
    r = api.post("/api/peers", json=dict(UPSTREAM, origem="1100"))
    assert r.status_code == 422
    assert "origem" in r.json()["erros"]


def test_a_origem_da_tabela_nao_avisa(api):
    # o peer em branco e a copia nascem com a origem do default, que esta
    # dentro da tabela: quem ve o aviso e o cadastro antigo, e nao o novo
    corpo = api.get("/api/peers/novo", params={"tipo": "upstream"}).json()
    r = api.post("/api/peers", json=dict(UPSTREAM, origem=corpo["formulario"]["origem"]))

    assert r.status_code == 201, r.text
    assert r.json()["avisos"] == []


def test_toda_rota_de_dados_pede_o_asn():
    """Uma rota nova sem o Depends(tenant) leria o tenant errado em silencio.

    O /api/asns fica de fora: ele e quem lista os tenants, e nao ha o que
    resolver antes dele. As tres rotas de sessao estao no outro roteador e
    nao entram nesta varredura.

    O get_flat_dependant e o que achata as dependencias: o ?asn= mora no
    `tenant`, e nao na assinatura da rota, entao o rota.dependant.query_params
    sozinho so enxerga os parametros declarados ali.
    """
    from fastapi.dependencies.utils import get_flat_dependant

    from app import api as api_mod

    sem_asn = [rota.path for rota in api_mod.roteador.routes
               if rota.path != "/api/asns"
               and "asn" not in {p.name
                                 for p in get_flat_dependant(
                                     rota.dependant).query_params}]
    assert sem_asn == []


def test_o_irr_do_peer_preserva_o_tratamento_e_marca_o_ausente(
        api, fake_bgpq4):
    # a consulta devolve 45.169.232.0/22 e 45.169.236.0/23 em v4, e o
    # 45.169.240.0/24 que estava na tela nao veio mais
    r = api.post("/api/irr", json={
        "asn": "268127",
        "v4": ["45.169.232.0/22 64512:210", "45.169.240.0/24 64512:211"],
        "v6": []})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "v4": ["45.169.232.0/22 64512:210",
               "45.169.236.0/23",
               "45.169.240.0/24 64512:211  !- nao veio na consulta ao IRR"],
        "v6": ["2001:db8::/32"]}
