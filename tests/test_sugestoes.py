"""O catalogo de communities que o formulario oferece como botao.

O que estes casos protegem e a origem do catalogo. Uma segunda lista de
numeros, escrita a mao no meio do caminho, insere no campo um valor que
parece conferido e que nenhum filtro le: e o mesmo defeito que a tabela do
PDF evita, so que digitado pelo operador em vez de impresso.
"""

import re

from app import formulario, plan

REDE = plan.Rede(64512)
# uma rede com ASN de 32 bits e namespace proprio: o catalogo tem que sair
# nos dois numeros certos, e nao no AS de fabrica
REDE_32 = plan.Rede(264130, 65532)


def upstream(ident, asn, grupo=None, politica_de=None):
    from app import peers

    return peers.Peer(id=ident, tipo="upstream", asn=asn, grupo_id=grupo,
                      politica_de=politica_de)


def valores(catalogo, qual):
    return {s["valor"] for s in catalogo[qual]}


def test_a_preferencia_cobre_a_escada_do_plano():
    catalogo = formulario.sugestoes(REDE)
    assert {c for c, _lp in plan.LP_CLIENTE} <= valores(catalogo, "communities")


def test_o_escopo_de_anuncio_cobre_o_que_o_plano_le():
    """As duas metades do escopo: proibir um destino e so ir para um.

    Sai das tabelas que os filtros consomem, e nao de uma lista de numeros
    escrita aqui: um valor que ganhe ramo no plan.py entra no catalogo
    sozinho.
    """
    catalogo = formulario.sugestoes(REDE)
    lidas = (set(plan.noadv_cust(REDE.ns))
             | set(plan.only_not("cliente", REDE.ns)))
    assert lidas <= valores(catalogo, "communities")


def test_o_prepend_sai_do_c6ca():
    catalogo = formulario.sugestoes(REDE)
    for classe in plan.CLASSE_6CA.values():
        for digito in plan.DIGITO_PREPEND:
            assert plan.c6ca(classe, digito, REDE.ns) in valores(
                catalogo, "communities")


def test_as_por_upstream_usam_o_identificador_do_cadastro():
    """O botao traz o numero, e nao um marcador para o operador preencher.

    Quem escolhe "nao anunciar para o upstream" nao tem que lembrar do
    identificador dele: ele sai do cadastro, pelo mesmo `_fontes_5ppa` que
    a tabela do PDF usa.
    """
    catalogo = formulario.sugestoes(REDE, peers=[upstream(1, 14840)])
    assert plan.c5ppa(1, 0, REDE.ns) in valores(catalogo, "communities")
    assert plan.c5ppa(1, 4, REDE.ns) in valores(catalogo, "communities")


def test_as_large_por_asn_usam_o_asn_do_cadastro():
    catalogo = formulario.sugestoes(REDE, peers=[upstream(1, 14840)])
    grandes = valores(catalogo, "large_communities")
    for funcao, _rotulo in plan.FUNCOES_LARGE:
        assert plan.c_large(funcao, 14840, REDE.ns) in grandes


def test_o_upstream_agrupado_oferece_o_do_grupo():
    # a mesma regra da tabela do PDF: quem emite o 5PPA de um upstream
    # agrupado e o grupo, e o identificador do membro nao tem ramo
    from app import peers

    catalogo = formulario.sugestoes(
        REDE,
        peers=[upstream(3, 53062, grupo=2)],
        grupos=[peers.Grupo(id=2, tipo="upstream", asn=53062, nome="ALT")],
    )
    valores_std = valores(catalogo, "communities")
    assert plan.c5ppa(2, 0, REDE.ns) in valores_std
    assert plan.c5ppa(3, 0, REDE.ns) not in valores_std


def test_o_upstream_que_reaproveita_nao_oferece_o_identificador_dele():
    # a mesma regra da tabela do PDF, pelo mesmo `fontes_5ppa`: quem
    # reaproveita nao tem CL-5PPA propria, entao o botao do identificador
    # dele poria no campo uma community que o filtro da origem nao le
    catalogo = formulario.sugestoes(
        REDE, peers=[upstream(5, 14840), upstream(6, 14840, politica_de=5)])
    valores_std = valores(catalogo, "communities")
    assert plan.c5ppa(5, 0, REDE.ns) in valores_std
    assert plan.c5ppa(6, 0, REDE.ns) not in valores_std


def test_nenhuma_sugestao_sai_com_marcador_para_preencher():
    """`<ASN>` e coisa de documento, nao de campo.

    O que entra no textarea tem que passar na validacao da API; um marcador
    entre parenteses viraria erro no salvar, e o operador so descobriria
    depois de clicar.
    """
    catalogo = formulario.sugestoes(REDE, peers=[upstream(1, 14840)])
    for qual in ("communities", "large_communities"):
        for sugestao in catalogo[qual]:
            assert not re.search(r"[<>\[\]{}]", sugestao["valor"]), sugestao


def test_toda_sugestao_tem_valor_rotulo_e_grupo():
    # o valor e o que entra no campo, o rotulo e o que o operador le na
    # busca, e o grupo e o cabecalho da lista
    catalogo = formulario.sugestoes(REDE, peers=[upstream(1, 14840)])
    for qual in ("communities", "large_communities"):
        assert catalogo[qual], "catalogo vazio: %s" % qual
        for sugestao in catalogo[qual]:
            assert set(sugestao) == {"valor", "rotulo", "grupo"}
            assert all(sugestao[k] for k in sugestao)


def test_o_catalogo_sai_no_namespace_da_rede():
    """O mesmo contrato do resto: dois numeros, e nao o AS de fabrica.

    Um catalogo montado no plan.py do modulo ofereceria 64512 numa rede
    cujo namespace e 65532, e o valor recusado na validacao.
    """
    catalogo = formulario.sugestoes(REDE_32)
    tudo = valores(catalogo, "communities") | valores(catalogo,
                                                       "large_communities")
    assert any(v.startswith("65532:") for v in tudo)
    assert not any(v.startswith("64512:") for v in tudo)


def test_o_rotulo_da_preferencia_e_o_efeito_e_nao_o_numero():
    # o botao tem que dizer o que a community faz: o operador procura por
    # "ultimo recurso", e nao por 101
    catalogo = formulario.sugestoes(REDE)
    por_valor = {s["valor"]: s["rotulo"] for s in catalogo["communities"]}
    assert "último recurso" in por_valor[REDE.c(101)].lower()


def test_o_plano_da_api_traz_as_sugestoes_da_rede(api):
    """O caminho de ponta a ponta: cadastro, API, formulario.

    O ASN do rotulo e o do upstream que o operador acabou de cadastrar, e
    nao um exemplo do plano: e o `?asn=` que escolhe a rede, como em toda
    leitura.
    """
    from dados_api import UPSTREAM

    assert api.post("/api/peers", json=UPSTREAM).status_code == 201

    sugestoes = api.get("/api/plano").json()["sugestoes"]

    grandes = {s["valor"] for s in sugestoes["large_communities"]}
    assert "64512:0:14840" in grandes
    assert "64512:4:14840" in grandes
    assert any(s["valor"].startswith("64512:5")
               for s in sugestoes["communities"])


def test_a_busca_por_prepend_acha_as_de_prepend():
    """O caso de uso que motivou o catalogo: digitar "prepend" e ver as dele.

    O filtro do cmdk casa no texto do item, e o rotulo e o que ele ve.
    """
    catalogo = formulario.sugestoes(REDE)
    de_prepend = [s for s in catalogo["communities"]
                  if "prepend" in s["rotulo"].lower()]
    assert {s["valor"] for s in de_prepend} >= {
        plan.c6ca(7, 2, REDE.ns), plan.c6ca(7, 3, REDE.ns),
        plan.c6ca(7, 4, REDE.ns)}
