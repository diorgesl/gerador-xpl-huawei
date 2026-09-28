"""A API dos prefixos proprios do AS."""

from app import peers as peers_mod
from dados_api import ASN_DE_TESTE, BLOCOS, arvore, caminho_tenant


def _salvo(tmp_path):
    return (tmp_path / "out" / str(ASN_DE_TESTE)
            / "blocos.txt").read_text(encoding="ascii")


def test_sem_blocos_o_texto_e_vazio_e_nao_ha_saida(api):
    assert api.get("/api/blocos").json() == {
        "texto": {"v4": "", "v6": ""}, "originacao": None, "remover": None}


def test_salvar_grava_o_yaml_e_o_out(api, tmp_path):
    r = api.put("/api/blocos", json=BLOCOS)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["texto"]["v4"] == ("38.252.64.0/22 64512:613 64512:621\n"
                                    "38.252.64.0/24 64512:211")
    assert _salvo(tmp_path) == corpo["originacao"]
    assert "undo xpl route-filter ORIGEM-38-252-64-0_22" in corpo["remover"]
    blocos = peers_mod.carregar_blocos(caminho_tenant(tmp_path))
    assert [b.prefixo for b in blocos["v4"]] == ["38.252.64.0/22", "38.252.64.0/24"]
    assert api.get("/api/blocos").json() == corpo


def test_prefixo_torto_e_recusado_sem_gravar(api, tmp_path):
    antes = arvore(tmp_path)
    r = api.put("/api/blocos", json={"v4": "torto", "v6": ""})
    assert r.status_code == 422
    assert r.json()["erros"]["blocos_v4"] == "prefixo invalido: torto (esperado CIDR)"
    assert arvore(tmp_path) == antes


def test_fora_de_servico_fica_no_texto_e_so_sai_na_remocao(api):
    corpo = api.put("/api/blocos", json={
        "v4": "38.252.64.0/22 64512:613\n!- 38.252.64.0/24 64512:211",
        "v6": ""}).json()
    assert "!- 38.252.64.0/24 64512:211" in corpo["texto"]["v4"]
    assert "ORIGEM-38-252-64-0_24" not in corpo["originacao"]
    assert "ORIGEM-38-252-64-0_24" in corpo["remover"]


def test_a_previa_dos_blocos_nao_grava_e_bate_com_o_salvar(api, tmp_path):
    antes = arvore(tmp_path)
    previa = api.post("/api/blocos/previa", json=BLOCOS).json()
    assert previa["salvo"] is None and previa["arquivo"] == "blocos.txt"
    assert arvore(tmp_path) == antes
    api.put("/api/blocos", json=BLOCOS)
    assert previa["bloco"] == _salvo(tmp_path)
    assert api.post("/api/blocos/previa", json=BLOCOS).json()["salvo"] == _salvo(tmp_path)


def test_a_previa_com_prefixo_torto_volta_o_erro(api):
    r = api.post("/api/blocos/previa", json={"v4": "torto", "v6": ""})
    assert r.status_code == 200
    assert r.json()["erros"]["blocos_v4"] == "prefixo invalido: torto (esperado CIDR)"
    assert r.json()["bloco"] is None


def test_o_irr_mescla_e_marca_o_ausente_sem_gravar(api, tmp_path, fake_bgpq4):
    # a consulta escreve o cache do bgpq4, e isso e dela; o que ela nao toca
    # e o cadastro, que e o que o "sem gravar" deste caso sempre quis dizer
    cadastro = caminho_tenant(tmp_path)
    antes = cadastro.read_bytes()
    r = api.post("/api/blocos/irr", json=BLOCOS)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "v4": ("45.169.232.0/22\n45.169.236.0/23\n"
               "38.252.64.0/22 64512:613 64512:621  !- nao veio na consulta ao IRR\n"
               "38.252.64.0/24 64512:211  !- nao veio na consulta ao IRR"),
        "v6": "2001:db8::/32"}
    assert cadastro.read_bytes() == antes


def test_o_irr_com_prefixo_torto_recusa_antes_de_consultar(api):
    r = api.post("/api/blocos/irr", json={"v4": "torto", "v6": ""})
    assert r.status_code == 422
    assert "blocos_v4" in r.json()["erros"]


def test_o_irr_dos_blocos_sem_bgpq4_volta_502(api, tmp_path, monkeypatch):
    vazio = tmp_path / "sem-bgpq4"
    vazio.mkdir()
    monkeypatch.setenv("PATH", str(vazio))
    r = api.post("/api/blocos/irr", json=BLOCOS)
    assert r.status_code == 502
    assert "bgpq4 nao esta no PATH" in r.json()["erros"]["bgpq4"]


def test_o_irr_dos_blocos_com_bgpq4_sem_permissao_volta_502(api, tmp_path, monkeypatch):
    # um bgpq4 no PATH sem permissao de execucao: o subprocess levanta
    # PermissionError, que o _rodar nao converte
    pasta = tmp_path / "bgpq4-travado"
    pasta.mkdir()
    binario = pasta / "bgpq4"
    binario.write_text("#!/bin/sh\n", encoding="ascii")
    binario.chmod(0o644)
    monkeypatch.setenv("PATH", str(pasta))
    r = api.post("/api/blocos/irr", json=BLOCOS)
    assert r.status_code == 502
    assert "bgpq4" in r.json()["erros"]
