"""O formulario.py: os helpers que a API usa."""

from dataclasses import replace

import pytest

from app import formulario, plan, render, validate
from app.api import dados_do_formulario, modelo_do_grupo, modelo_do_peer
from app.formulario import grupo_do_formulario, peer_do_formulario
from test_render import (grupo_do_tipo, peer_cliente, peer_ix, peer_parceiro,
                         peer_pni, peer_upstream)


# O valor "preenchido" de cada campo restrito, em texto de formulario. O
# "vazio" e o branco do tipo do campo.
CHEIO = {
    "classe": "residencial", "pop": "2001", "default_route": True,
    "tabela": "parcial",
    "aprendizado": "3100", "aprendizado_ix": "3010", "prepend_base": "2",
    "bh_upstream": "14840:666", "ap_block": ["270814"], "ap_te": ["264381"],
    "te_prefixos_v4": ["198.51.100.0/24"],
    "te_prefixos_v6": ["2001:db8:900::/48"],
    "ix_id": "9999", "ap_prefer": ["15169"], "ap_allowed": ["64510"],
    "communities": ["64512:1500"], "large_communities": ["64512:4:264130"],
}
PEER_DO_TIPO = {"cliente": peer_cliente, "parceiro": peer_parceiro,
                "upstream": peer_upstream, "ix": peer_ix, "pni": peer_pni}
# dual-stack: a excecao de TE em v6 so aparece na saida de sessao com v6
V6 = {"local": "2001:db8:1::1", "remoto": "2001:db8:1::2"}


def _vazio(valor):
    if isinstance(valor, bool):
        return False
    return [] if isinstance(valor, list) else ""


def _chave_de_erro(campo):
    # o validate nomeia o erro pelo atributo: te_prefixos, e o aprendizado do
    # IX do grupo e o mesmo atributo aprendizado
    if campo.startswith("te_prefixos"):
        return "te_prefixos"
    return {"aprendizado_ix": "aprendizado"}.get(campo, campo)


def _saida(monta):
    try:
        return monta()
    except Exception as exc:  # campo obrigatorio em branco estoura no render
        return "estourou: %s" % type(exc).__name__


def _peer(tipo, campo, valor):
    base = PEER_DO_TIPO[tipo]()
    base = replace(base, sessoes={"v4": base.sessoes["v4"], "v6": V6})
    modelo = modelo_do_peer(base).model_copy(update={campo: valor})
    peer, erros = peer_do_formulario(dados_do_formulario(modelo), [], None, ())
    erros = erros + validate.validar(peer, [], grupos=[])
    return (_saida(lambda: render.render_peer(peer) + render.render_remove(peer)
                   + render.render_criar_lista(peer)),
            {e.campo for e in erros})


def _grupo(tipo, campo, valor):
    modelo = modelo_do_grupo(grupo_do_tipo(tipo)).model_copy(update={campo: valor})
    grupo, erros = grupo_do_formulario(dados_do_formulario(modelo), [], None, ())
    erros = erros + validate.validar_grupo(grupo, [], [])
    return (_saida(lambda: render.render_grupo(grupo)
                   + render.render_criar_lista(grupo=grupo)),
            {e.campo for e in erros})


def _efeito(monta, tipo, campo):
    """(muda a saida, a validacao olha o campo) ao preencher o campo."""
    saida_vazia, erros_vazio = monta(tipo, campo, _vazio(CHEIO[campo]))
    saida_cheia, erros_cheio = monta(tipo, campo, CHEIO[campo])
    return (saida_vazia != saida_cheia,
            _chave_de_erro(campo) in (erros_vazio ^ erros_cheio))


TABELAS = [("peer", formulario.CAMPOS_POR_TIPO, _peer),
           ("grupo", formulario.CAMPOS_POR_TIPO_GRUPO, _grupo)]


@pytest.mark.parametrize("nome,tabela,monta", TABELAS)
def test_fora_da_tabela_o_campo_nao_muda_nada_ou_e_recusado(nome, tabela, monta):
    # esconder o campo num tipo so e seguro se, nesse tipo, ele nao muda a
    # saida ou a validacao o recusa
    for campo, tipos in tabela.items():
        for tipo in plan.TIPOS:
            if tipo in tipos:
                continue
            muda, olha = _efeito(monta, tipo, campo)
            assert not muda or olha, (nome, campo, tipo)


@pytest.mark.parametrize("nome,tabela,monta", TABELAS)
def test_dentro_da_tabela_o_campo_faz_diferenca(nome, tabela, monta):
    for campo, tipos in tabela.items():
        for tipo in tipos:
            muda, olha = _efeito(monta, tipo, campo)
            assert muda or olha, (nome, campo, tipo)


def test_as_tabelas_so_citam_tipos_do_plano():
    for tabela in (formulario.CAMPOS_POR_TIPO, formulario.CAMPOS_POR_TIPO_GRUPO):
        for tipos in tabela.values():
            assert set(tipos) <= set(plan.TIPOS)


def test_o_bloco_da_cascata_e_a_tabela_do_plano():
    """O que a SPA le para se preencher sozinha bate com o plan.py.

    Este caso veio do test_app.py, onde lia o `<script id="padroes">` da tela.
    O que ele protege nunca foi a marcacao: e a sincronia entre o bloco que o
    formulario consome e as tabelas da politica. Se um valor mudar no plan.py e
    nao aqui, o formulario passa a se preencher com a politica antiga, em
    silencio. O test_api.py compara o padroes do plano com o proprio _padroes,
    e isso nao pega: as duas pontas mudam juntas.
    """
    p = formulario._padroes()

    assert p["origem_tipo"] == dict(plan.ORIGEM)
    assert p["origem_classe"] == dict(plan.ORIGEM_CLASSE)
    assert p["downstream"] == list(plan.TIPOS_DOWNSTREAM)
    assert p["origens_por_tipo"] == {t: list(v)
                                     for t, v in plan.ORIGENS_POR_TIPO.items()}
    assert p["origem_nome"] == {str(c): n
                                for c, n in plan.Rede().ORIGEM_NOME.items()}
    for tipo in plan.TIPOS:
        assert p["tipos"][tipo] == {
            "lp_base": plan.LP_BASE.get(tipo),
            "route_limit": plan.ROUTE_LIMIT.get(tipo),
            "timer_keepalive": plan.TIMER_PADRAO.get(tipo, (None, None))[0],
            "timer_hold": plan.TIMER_PADRAO.get(tipo, (None, None))[1],
            "default_route": tipo in plan.TIPOS_DOWNSTREAM,
            "tabela": "nenhuma" if tipo in plan.TIPOS_DOWNSTREAM else "",
        }, tipo


# --- a linha do prefixo com tratamento ----------------------------------


def test_a_linha_com_community_vira_bloco_com_ela():
    (bloco,) = formulario._blocos_das_linhas(["45.169.232.0/22 64512:210"])
    assert bloco.prefixo == "45.169.232.0/22"
    assert bloco.communities == ["64512:210"]
    assert bloco.ativo is True


def test_a_linha_fora_de_servico_guarda_o_tratamento():
    (bloco,) = formulario._blocos_das_linhas(["!- 45.169.232.0/22 64512:210"])
    assert bloco.ativo is False
    assert bloco.communities == ["64512:210"]


def test_a_marca_do_irr_no_fim_da_linha_e_ignorada():
    """As duas pontas do `!-` valendo na mesma linha: fora de servico, com o
    tratamento guardado e a marca do ausente descartada."""
    (bloco,) = formulario._blocos_das_linhas(
        ["!- 45.169.232.0/22 64512:210  !- nao veio na consulta ao IRR"])
    assert bloco.ativo is False
    assert bloco.communities == ["64512:210"]


def test_a_linha_com_intervalo_guarda_o_ate():
    (bloco,) = formulario._blocos_das_linhas(["138.97.60.0/22-24 64512:210"])
    assert bloco.prefixo == "138.97.60.0/22"
    assert bloco.ate == 24
    assert bloco.communities == ["64512:210"]


def test_a_linha_sem_sufixo_fica_sem_ate():
    (bloco,) = formulario._blocos_das_linhas(["138.97.60.0/22"])
    assert bloco.ate is None


def test_o_intervalo_igual_ao_comprimento_vira_a_forma_sem_sufixo():
    """Duas escritas do mesmo alcance sao uma so: o `-22` de um /22 e o
    proprio /22."""
    (bloco,) = formulario._blocos_das_linhas(["138.97.60.0/22-22"])
    assert bloco.ate is None


def test_o_texto_da_linha_leva_o_intervalo():
    assert formulario._linhas_de_blocos([
        formulario.Bloco(prefixo="138.97.60.0/22", ate=24)]) == [
        "138.97.60.0/22-24"]


def test_o_texto_do_bloco_marca_o_ausente_e_o_fora_de_servico():
    ativos = [formulario.Bloco(prefixo="45.169.232.0/22",
                               communities=["64512:210"])]
    fora = formulario.Bloco(prefixo="45.169.236.0/23", communities=[],
                            ativo=False)
    ausente = formulario.Bloco(prefixo="45.169.240.0/24",
                               communities=["64512:211"])
    assert formulario._linhas_de_blocos(ativos + [fora]) == [
        "45.169.232.0/22 64512:210", "!- 45.169.236.0/23"]
    assert formulario._linhas_de_blocos(ativos + [ausente],
                                        ausentes=[ausente]) == [
        "45.169.232.0/22 64512:210",
        "45.169.240.0/24 64512:211  !- nao veio na consulta ao IRR"]
    assert formulario._texto_blocos({"v4": ativos + [ausente], "v6": []},
                                    ausentes=[ausente])["v4"] == (
        "45.169.232.0/22 64512:210\n"
        "45.169.240.0/24 64512:211  !- nao veio na consulta ao IRR")


def test_tabela_em_branco_no_downstream_vira_nenhuma():
    modelo = modelo_do_peer(peer_cliente()).model_copy(update={"tabela": ""})
    peer, _ = peer_do_formulario(dados_do_formulario(modelo), [], None, ())
    assert peer.tabela == "nenhuma"


def test_tabela_fora_do_downstream_fica_no_default():
    modelo = modelo_do_peer(peer_upstream()).model_copy(update={"tabela": "parcial"})
    peer, _ = peer_do_formulario(dados_do_formulario(modelo), [], None, ())
    assert peer.tabela == "full"


def test_o_modelo_so_mostra_a_tabela_de_quem_a_usa():
    # valor guardado aparece na tela mesmo fora do tipo: o upstream e o
    # membro de grupo teriam um select que nao faz nada
    assert modelo_do_peer(peer_cliente(tabela="parcial")).tabela == "parcial"
    assert modelo_do_peer(peer_upstream()).tabela == ""
    assert modelo_do_peer(peer_cliente(tabela="parcial", grupo_id=3)).tabela == ""


def test_o_peer_em_branco_de_downstream_recebe_so_a_default():
    for tipo in plan.TIPOS:
        p = formulario.peer_em_branco(tipo, [], [])
        g = formulario.grupo_em_branco(tipo, [], [])
        down = tipo in plan.TIPOS_DOWNSTREAM
        assert (p.default_route, g.default_route) == (down, down), tipo
        if down:
            assert (p.tabela, g.tabela) == ("nenhuma", "nenhuma"), tipo
