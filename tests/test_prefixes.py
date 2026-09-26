import json
import shutil
import time

import pytest

from app import prefixes


def test_coletar_le_a_saida_do_bgpq4(fake_bgpq4):
    r = prefixes.coletar(268127, "TESTOK")
    assert r["v4"] == ["45.169.232.0/22", "45.169.236.0/23"]
    assert r["v6"] == ["2001:db8::/32"]


def test_coletar_grava_o_cache(fake_bgpq4):
    prefixes.coletar(268127, "TESTOK")
    assert (prefixes.CACHE / "268127.json").exists()


def test_a_segunda_coleta_usa_o_cache(fake_bgpq4):
    prefixes.coletar(268127, "TESTOK")
    shutil.rmtree(str(fake_bgpq4.parent))       # sem bgpq4 no PATH
    assert prefixes.coletar(268127, "TESTOK")["v4"] == [
        "45.169.232.0/22", "45.169.236.0/23"]


def test_forcar_ignora_o_cache(fake_bgpq4):
    prefixes.coletar(268127, "TESTOK")
    caminho = prefixes.CACHE / "268127.json"
    dados = json.loads(caminho.read_text())
    dados["prefixos"]["v4"] = ["10.0.0.0/8"]
    caminho.write_text(json.dumps(dados))
    r = prefixes.coletar(268127, "TESTOK", forcar=True)
    assert r["v4"] == ["45.169.232.0/22", "45.169.236.0/23"]


def test_cache_vencido_e_ignorado(fake_bgpq4):
    prefixes.coletar(268127, "TESTOK")
    caminho = prefixes.CACHE / "268127.json"
    dados = json.loads(caminho.read_text())
    dados["coletado_em"] = time.time() - 25 * 3600
    caminho.write_text(json.dumps(dados))
    assert prefixes.idade_horas(268127) > 24
    assert prefixes.do_cache(268127) is None


def test_ttl_e_24_horas():
    assert prefixes.TTL_HORAS == 24


def test_cache_de_versao_antiga_e_ignorado(fake_bgpq4):
    """O cache gravado antes do -A guarda a lista sem agregar. Servir essa
    lista depois da mudanca faria a consulta nova parecer que nao pegou."""
    prefixes.coletar(268127, "TESTOK")
    caminho = prefixes.CACHE / "268127.json"
    dados = json.loads(caminho.read_text())
    del dados["versao"]
    caminho.write_text(json.dumps(dados))
    assert prefixes.do_cache(268127) is None
    assert prefixes.idade_horas(268127) is None


def test_o_cache_grava_a_versao(fake_bgpq4):
    prefixes.coletar(268127, "TESTOK")
    dados = json.loads((prefixes.CACHE / "268127.json").read_text())
    assert dados["versao"] == prefixes.CACHE_VERSAO


def test_o_comando_monta_os_argumentos(fake_bgpq4, monkeypatch):
    vistos = []
    monkeypatch.setattr(prefixes, "_rodar", lambda cmd: vistos.append(cmd) or [])
    prefixes.coletar(268127, "TESTOK", forcar=True)
    assert vistos == [
        ["bgpq4", "-4", "-A", "-F", "%n/%l ", "-h", "whois.radb.net",
         "-l", "PL-CUST-TESTOK-V4", "AS268127"],
        ["bgpq4", "-6", "-A", "-F", "%n/%l ", "-h", "whois.radb.net",
         "-l", "PL-CUST-TESTOK-V6", "AS268127"],
    ]


def test_bgpq4_ausente_e_erro_com_mensagem():
    with pytest.raises(RuntimeError):
        prefixes._rodar(["bgpq4-que-nao-existe"])


def test_normalizar_le_uma_linha_com_varios_cidrs():
    """Com -F '%n/%l ' o bgpq4 devolve tudo numa linha, separado por espaco."""
    assert prefixes._normalizar(["45.169.232.0/22 45.169.236.0/23 "]) == [
        "45.169.232.0/22", "45.169.236.0/23"]


def test_normalizar_tira_repeticao():
    """O -A repete a entrada quando o agregado tambem e um objeto
    registrado: em AS264130 o /32 v6 saiu duas vezes."""
    assert prefixes._normalizar(["2804:22e8::/32 2804:22e8::/32 "]) == [
        "2804:22e8::/32"]


def test_normalizar_aceita_um_prefixo_por_linha():
    """Se o bgpq4 sair com um prefixo por linha, tambem funciona."""
    assert prefixes._normalizar(["45.169.232.0/22\n", "45.169.236.0/23\n"]) == [
        "45.169.232.0/22", "45.169.236.0/23"]


def test_o_comando_aceita_etiqueta_propria(fake_bgpq4, monkeypatch):
    """O bloco proprio nao e lista de cliente: o rotulo da consulta diz o
    que ela e, e o cache continua sendo o mesmo, porque a consulta ao IRR
    nao depende do rotulo."""
    vistos = []
    monkeypatch.setattr(prefixes, "_rodar", lambda cmd: vistos.append(cmd) or [])
    prefixes.coletar(264130, "264130", forcar=True, etiqueta="ORIGEM")
    assert vistos[0][vistos[0].index("-l") + 1] == "ORIGEM-V4"
    assert vistos[1][vistos[1].index("-l") + 1] == "ORIGEM-V6"


def test_a_etiqueta_nao_muda_a_chave_do_cache(fake_bgpq4):
    prefixes.coletar(264130, "264130", etiqueta="ORIGEM")
    assert (prefixes.CACHE / "264130.json").exists()
