"""O modelo JSON do formulario e a conversao nos dois sentidos."""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from app import plan
from app.api import dados_do_formulario, modelo_do_grupo, modelo_do_peer
from app.formulario import grupo_do_formulario, peer_do_formulario
from app.modelos_api import GrupoForm, PeerForm
from app.peers import Peer
# um peer e um grupo de cada tipo, os mesmos que os golden conferem. O pytest
# poe tests/ no sys.path, e por isso o test_render importa pelo nome.
from test_render import (grupo_do_tipo, peer_cliente, peer_ix, peer_parceiro,
                         peer_pni, peer_upstream)

PEERS = [peer_cliente, peer_parceiro, peer_upstream, peer_ix, peer_pni]


@pytest.mark.parametrize("fabrica", PEERS)
def test_o_peer_volta_igual_pelo_formulario(fabrica):
    # timers explicitos: em branco, o peer_do_formulario cai no default do tipo
    peer = replace(fabrica(), timer_keepalive=10, timer_hold=30)
    dados = dados_do_formulario(modelo_do_peer(peer))
    volta, erros = peer_do_formulario(dados, [], None, ())
    assert erros == []
    assert volta == peer


@pytest.mark.parametrize("tipo", plan.TIPOS)
def test_o_grupo_volta_igual_pelo_formulario(tipo):
    grupo = grupo_do_tipo(tipo)
    dados = dados_do_formulario(modelo_do_grupo(grupo))
    volta, erros = grupo_do_formulario(dados, [], None, ())
    assert erros == []
    # os fixtures guardam o ASN das listas de AS-path como numero, e o
    # formulario devolve texto: a comparacao e pelo que a tela ve
    assert modelo_do_grupo(volta) == modelo_do_grupo(grupo)


def test_o_aprendizado_do_grupo_de_ix_vai_no_campo_do_ix():
    modelo = modelo_do_grupo(replace(grupo_do_tipo("ix"), aprendizado=3010))
    assert (modelo.aprendizado, modelo.aprendizado_ix) == ("", "3010")


def test_caixa_desmarcada_fica_fora_do_dicionario():
    dados = dados_do_formulario(PeerForm(bfd=False, graceful_restart=True))
    assert "bfd" not in dados
    assert dados["graceful_restart"] == "on"


def test_lista_vira_uma_linha_por_item():
    dados = dados_do_formulario(PeerForm(prefixos_v4=["10.0.0.0/8", "192.0.2.0/24"]))
    assert dados["prefixos_v4"] == "10.0.0.0/8\n192.0.2.0/24"


def test_numero_de_lista_do_yaml_vira_texto():
    assert modelo_do_peer(Peer(ap_block=[64500])).ap_block == ["64500"]


def test_peer_novo_mostra_o_asn_em_branco():
    assert modelo_do_peer(Peer()).asn == ""


def test_campo_desconhecido_e_recusado():
    with pytest.raises(ValidationError):
        PeerForm(xpto="1")
    with pytest.raises(ValidationError):
        GrupoForm(sessao_v4_local="10.0.0.1")
