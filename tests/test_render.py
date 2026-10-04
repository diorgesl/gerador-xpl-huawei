import re
from pathlib import Path

import pytest

from app import render
from app.peers import Bloco

GOLDEN = Path(__file__).resolve().parent / "golden"


def test_base_e_ascii():
    assert render.render_base().isascii()


def test_base_tem_os_objetos_compartilhados():
    texto = render.render_base()
    for nome in (
        "xpl ip-prefix-list PL-BOGONS-V4",
        "xpl ipv6-prefix-list PL-BOGONS-V6",
        "xpl as-path-list AP-BOGON-ASN",
        "xpl as-path-list AP-LOCAL-ORIGIN",
        "xpl as-path-list AP-PATH-TOO-LONG",
        "xpl community-list CL-BLACKHOLE",
        "xpl community-list CL-BLACKHOLE-PROPAGATE",
        "xpl community-list CL-GSHUT",
        "xpl community-list CL-ORIGEM-ANUNCIAVEL",
        "xpl community-list CL-ORIGEM-PARCIAL-IX",
        "xpl community-list CL-NOADV-CUST",
        "xpl community-list CL-ONLY-NOT-UP",
        "xpl community-list CL-ONLY-NOT-IX",
        "xpl community-list CL-ONLY-NOT-PNI",
        "xpl community-list CL-ONLY-NOT-CLIENT",
        "xpl community-list CL-OWN-ALL",
        "xpl route-filter IMPORT-SANITY-V4",
        "xpl route-filter IMPORT-SANITY-V6",
        "xpl route-filter EXPORT-SANITY",
        "xpl route-filter APPLY-CUSTOMER-LP",
        "ip route-static 192.0.2.1 255.255.255.255 NULL0 tag 666",
        "ipv6 route-static 100:: 64 NULL0 tag 666",
    ):
        assert nome in texto, nome


def test_base_nao_emite_o_strip_external():
    # existe no PLANO so como registro do que nao funciona
    assert "STRIP-EXTERNAL" not in render.render_base()


def test_base_nao_emite_nada_por_peer():
    # nenhum objeto com o nome de um peer: o bloco base e igual para todos.
    # CL-NOADV-CUST sai antes da varredura: ele e o set compartilhado de
    # egress de cliente, e o prefixo do nome coincide com o dos CL-NOADV-<T>
    # por peer, entao a varredura crua acusaria um objeto que e do bloco base.
    texto = render.render_base().replace("CL-NOADV-CUST", "")
    for nome in ("CL-PEER-", "APPLY-PEER-", "CL-NOADV-", "LC-NOADV-",
                 "PL-CUST-", "AP-CUST-", "AP-BLOCK-", "CL-5PPA-", "LC-5PPA-"):
        assert nome not in texto, nome


def test_import_sanity_fecha_em_break_nas_duas_familias():
    texto = render.render_base()
    for fam in ("V4", "V6"):
        corpo = texto.split("xpl route-filter IMPORT-SANITY-%s" % fam)[1].split("end-filter")[0]
        assert corpo.strip().endswith("break")
        assert "finish" not in corpo
        assert "approve" not in corpo
        assert "refuse" in corpo


def test_cada_import_sanity_usa_os_bogons_da_propria_familia():
    texto = render.render_base()
    v4 = texto.split("xpl route-filter IMPORT-SANITY-V4")[1].split("end-filter")[0]
    v6 = texto.split("xpl route-filter IMPORT-SANITY-V6")[1].split("end-filter")[0]
    assert "PL-BOGONS-V4" in v4 and "PL-BOGONS-V6" not in v4
    assert "PL-BOGONS-V6" in v6 and "PL-BOGONS-V4" not in v6


def test_export_sanity_fecha_em_break():
    texto = render.render_base()
    corpo = texto.split("xpl route-filter EXPORT-SANITY")[1].split("end-filter")[0]
    assert corpo.strip().endswith("break")
    assert "finish" not in corpo


def test_export_sanity_barra_a_infra_interna_antes_de_tudo():
    """O 1900 e o 1901 nunca saem do AS. A unica recusa da marca era a do
    export de cliente, e ela nao alcanca os outros tres: nos egress de
    upstream, IX e PNI quem a barrava era a ausencia de marca de origem,
    que nao pega a rota que carrega o 1000 proprio nem o 1100 que o import
    do cliente carimba."""
    corpo = render.render_base().split(
        "xpl route-filter EXPORT-SANITY")[1].split("end-filter")[0]
    assert "64512:1900" in corpo
    assert "64512:1901" in corpo
    assert corpo.index("64512:1900") < corpo.index("AP-LOCAL-ORIGIN")


def test_export_sanity_dispensa_a_marca_da_rota_originada_aqui():
    corpo = render.render_base().split(
        "xpl route-filter EXPORT-SANITY")[1].split("end-filter")[0]
    assert "if not as-path in AP-LOCAL-ORIGIN" in corpo
    assert "if not community matches-any CL-ORIGEM-ANUNCIAVEL" in corpo


def test_a_dispensa_do_path_vazio_usa_a_lista_que_ja_existe():
    """AP-LOCAL-ORIGIN ja e a definicao de "rota originada localmente" no
    IMPORT-SANITY. Uma segunda lista com o mesmo conteudo seria duas
    verdades sobre a mesma coisa."""
    base = render.render_base()
    assert base.count("xpl as-path-list AP-LOCAL-ORIGIN") == 1


def test_apply_customer_lp_fecha_em_break_em_todos_os_ramos():
    texto = render.render_base()
    corpo = texto.split("xpl route-filter APPLY-CUSTOMER-LP")[1].split("end-filter")[0]
    # cinco ramos da escada, o GSHUT e o default
    assert corpo.count("break") == 7
    assert "finish" not in corpo
    assert "apply local-preference 300" in corpo


def test_apply_customer_lp_ordena_o_gshut_antes_da_escada():
    texto = render.render_base()
    corpo = texto.split("xpl route-filter APPLY-CUSTOMER-LP")[1].split("end-filter")[0]
    assert corpo.index("CL-GSHUT") < corpo.index("64512:101")


def test_bogons_v4_usa_a_forma_sem_barra():
    texto = render.render_base()
    corpo = texto.split("xpl ip-prefix-list PL-BOGONS-V4")[1].split("end-list")[0]
    assert "0.0.0.0 8 le 32" in corpo
    assert "224.0.0.0 3 le 32" in corpo
    assert "/" not in corpo


def test_base_nao_carimba_community():
    # o bloco base nao carimba community: quem carimba e o import de cada
    # sessao. A varredura e pela operacao, que e o que a regra proibe: um
    # "apply community additive" aqui violaria a regra e passaria numa
    # varredura pela palavra "overwrite", que nomeia so a outra operacao.
    assert "apply community" not in render.render_base()


def test_base_nao_tem_parametro():
    # o $ de "regular ^$" e ancora de regex e fica. O que nao pode existir e
    # o parametro ($nome ou $(...)), que o xpl simulate rejeita.
    assert not re.search(r"\$[\w(]", render.render_base())


def test_golden_do_bloco_base():
    assert render.render_base() == (GOLDEN / "_base.txt").read_text(encoding="ascii")


from app.peers import Bloco, Peer


def peer_cliente(**kw):
    base = dict(
        id=1, nome="Cliente ACME", tipo="cliente", asn=268127,
        classe="residencial", descricao="CLIENTE-AS268127",
        lp_base=300, origem=1110, pop=2001,
        prefixos={"v4": ["45.169.232.0/22"], "v6": []},
        prepend_base=0, route_limit=50,
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"}, "v6": {}},
    )
    base.update(kw)
    return Peer(**base)


def test_cliente_e_ascii():
    assert render.render_peer(peer_cliente()).isascii()


def test_cliente_emite_os_objetos_do_tipo():
    texto = render.render_peer(peer_cliente())
    for nome in (
        "xpl ip-prefix-list PL-CUST-268127-V4",
        "xpl ip-prefix-list PL-CUST-268127-BH-V4",
        "xpl as-path-list AP-CUST-268127",
        "xpl route-filter CUST-268127-IMPORT-V4",
        "xpl route-filter CUST-268127-EXPORT-V4",
        "xpl route-filter APPLY-PEER-268127",
        "bgp 64512",
    ):
        assert nome in texto, nome


def test_cliente_nao_emite_a_community_list_do_peer():
    # o bloco do peer nao pode zerar a lista editada a mao
    assert "xpl community-list CL-PEER-268127" not in render.render_peer(peer_cliente())


def test_apply_peer_e_a_ultima_linha_do_import():
    texto = render.render_peer(peer_cliente())
    trecho = texto.split("xpl route-filter CUST-268127-IMPORT-V4")[1].split("end-filter")[0]
    corpo = [l.strip() for l in trecho.splitlines() if l.strip()]
    assert corpo[-2] == "call route-filter APPLY-PEER-268127"
    assert corpo[-1] == "finish"


def test_apply_peer_fecha_em_break():
    texto = render.render_peer(peer_cliente())
    corpo = texto.split("xpl route-filter APPLY-PEER-268127")[1].split("end-filter")[0]
    assert corpo.strip().endswith("break")
    assert "finish" not in corpo
    assert "apply community CL-PEER-268127 additive" in corpo


def test_import_do_cliente_ordena_sanidade_blackhole_e_prefixo():
    texto = render.render_peer(peer_cliente())
    trecho = texto.split("xpl route-filter CUST-268127-IMPORT-V4")[1].split("end-filter")[0]
    assert trecho.index("call route-filter IMPORT-SANITY-V4") < trecho.index("PL-CUST-268127-BH-V4")
    assert trecho.index("PL-CUST-268127-BH-V4") < trecho.index("if not ip route-destination in PL-CUST-268127-V4")


def test_cliente_usa_additive_e_nunca_overwrite():
    # a varredura e sobre o XPL, nao sobre a prosa: o comentario do 1901
    # cita o overwrite de egress como historia, e comentario nao carimba.
    texto = render.render_peer(peer_cliente())
    trecho = texto[texto.index("xpl route-filter CUST-268127-IMPORT-V4"):]
    codigo = "\n".join(l for l in trecho.splitlines() if not l.strip().startswith("!-"))
    assert "overwrite" not in codigo
    assert "additive" in codigo


def test_export_do_cliente_nao_leva_export_sanity():
    assert "call route-filter EXPORT-SANITY" not in render.render_peer(peer_cliente())


def test_export_do_cliente_escada_de_prepend():
    texto = render.render_peer(peer_cliente())
    export = texto.split("xpl route-filter CUST-268127-EXPORT-V4")[1].split("end-filter")[0]
    assert "if large-community matches-any {64512:3:268127} then" in export
    assert "if large-community matches-any {64512:2:268127} then" in export
    assert "if large-community matches-any {64512:1:268127} then" in export
    assert "if large-community matches-any {64512:0:268127} then" in export


def test_prefixo_sai_sem_barra():
    texto = render.render_peer(peer_cliente())
    assert "45.169.232.0 22" in texto
    assert "45.169.232.0/22" not in texto


def test_bloco_bgp_do_cliente():
    texto = render.render_peer(peer_cliente())
    assert "peer 198.51.100.2 as-number 268127" in texto
    assert "peer 198.51.100.2 description CLIENTE-AS268127" in texto
    assert "peer 198.51.100.2 route-limit 50 alert-only" in texto
    assert "peer 198.51.100.2 public-as-only force" in texto
    assert "peer 198.51.100.2 route-filter CUST-268127-IMPORT-V4 import" in texto
    assert "peer 198.51.100.2 route-filter CUST-268127-EXPORT-V4 export" in texto
    assert "peer 198.51.100.2 advertise-community" in texto
    assert "peer 198.51.100.2 advertise-large-community" in texto


def test_bloco_bgp_traz_bfd_e_graceful_restart():
    texto = render.render_peer(peer_cliente())
    assert "peer 198.51.100.2 bfd enable" in texto
    assert "peer 198.51.100.2 capability-advertise graceful-restart" in texto


def test_bgp_sem_bfd_nao_emite_a_linha():
    texto = render.render_peer(peer_cliente(bfd=False))
    assert "bfd enable" not in texto


def test_bgp_sem_graceful_restart_nao_emite_a_linha():
    texto = render.render_peer(peer_cliente(graceful_restart=False))
    assert "graceful-restart" not in texto


def test_cliente_sem_timer_nao_emite_linha_de_timer():
    # o PLANO so poe timer explicito no upstream
    assert "timer keepalive" not in render.render_peer(peer_cliente())


def test_default_route_desligada_nao_emite_nada():
    # o servico existe, mas nao e o default: quem nao pede nao recebe
    assert "default-route-advertise" not in render.render_peer(peer_cliente())


def test_default_route_ligada_sai_na_familia():
    texto = render.render_peer(peer_cliente(default_route=True))
    familia = texto.split("ipv4-family unicast")[1]
    assert "peer 198.51.100.2 default-route-advertise" in familia


def test_default_route_sai_nas_duas_familias():
    texto = render.render_peer(peer_cliente(
        default_route=True,
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"},
                 "v6": {"local": "2001:db8::1", "remoto": "2001:db8::2"}}))
    assert texto.count("default-route-advertise") == 2


def test_default_route_avisa_no_cabecalho():
    # o VRP origina a default nesta sessao mesmo sem default na tabela, e o
    # filtro de export nao a ve: o aviso diz isso antes da colagem
    texto = render.render_peer(peer_cliente(default_route=True))
    cabecalho = [l for l in texto.splitlines()[:8] if l.startswith("#")]
    assert ("# default route: o VRP origina 0/0 e ::/0 nesta sessao mesmo "
            "sem default na tabela") in cabecalho


def test_filtro_com_asn_falsy_pula_confinamento_por_as_path():
    # asn=0 so e alcancavel construindo Peer(...) direto, como aqui: o
    # fluxo real trava em app/validate.py (ASN_MIN=1), entao nenhum Peer de
    # producao chega nas macros de _macros.j2 sem ASN. O guard "if
    # alvo.asn" existe porque o GRUPO (task 5) tem um caso legitimo de asn
    # ausente (parceiros de ASNs distintos, sem ASN compartilhado para
    # confinar ou enderecar); este teste trava o comportamento hoje
    # dormente do Peer, para nao ser confundido com regressao mais tarde.
    # Sem asn explicito o token cai para str(asn), entao vira "0".
    texto = render.render_peer(peer_cliente(asn=0))

    importe = texto.split("xpl route-filter CUST-0-IMPORT-V4")[1].split("end-filter")[0]
    assert "as-path in AP-CUST-0" not in importe
    assert importe.count("apply large-community") == 1  # so a do blackhole, que nao depende do asn
    assert "call route-filter IMPORT-SANITY-V4" in importe
    assert "call route-filter APPLY-CUSTOMER-LP" in importe
    assert "apply community {64512:1110, 64512:2001} additive" in importe

    assert "xpl as-path-list AP-CUST-0" not in texto

    exporte = texto.split("xpl route-filter CUST-0-EXPORT-V4")[1].split("end-filter")[0]
    assert "large-community matches-any" not in exporte
    assert "apply as-path 64512" not in exporte
    assert "community matches-any CL-NOADV-CUST" in exporte


def test_golden_do_cliente():
    assert render.render_peer(peer_cliente()) == (GOLDEN / "cliente.txt").read_text(encoding="ascii")


# O parceiro: um cliente no roteador onde as CDNs tem sessao. Mesma regra e
# mesmo template; a marca de 2091 no import diz de qual sessao a rota veio.


def peer_parceiro(**kw):
    base = dict(
        id=9, nome="Parceiro CDN-X", tipo="parceiro", asn=64500,
        classe="corporativo", descricao="PARCEIRO-AS64500",
        lp_base=300, origem=1120, pop=2001,
        prefixos={"v4": ["45.169.236.0/22"], "v6": []},
        prepend_base=0, route_limit=50,
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"}, "v6": {}},
    )
    base.update(kw)
    return Peer(**base)


def test_parceiro_e_ascii():
    assert render.render_peer(peer_parceiro()).isascii()


def test_o_parceiro_difere_do_cliente_so_no_cabecalho_e_na_marca():
    # o bloco do parceiro sai do mesmo template do cliente, e este teste e o
    # que sustenta isso: qualquer linha que ficasse so num dos dois quebra
    # aqui, e o que resta de diferente e exatamente a marca
    cliente = render.render_peer(peer_cliente()).splitlines()
    parceiro = render.render_peer(peer_cliente(tipo="parceiro")).splitlines()
    assert len(cliente) == len(parceiro)
    diferentes = [(a, b) for a, b in zip(cliente, parceiro) if a != b]
    assert [a for a, _ in diferentes] == [
        "# peer 1 - cliente - AS268127 - token 268127",
        " apply community {64512:1110, 64512:2001} additive",
    ]
    assert [b for _, b in diferentes] == [
        "# peer 1 - parceiro - AS268127 - token 268127",
        " apply community {64512:1110, 64512:2001, 64512:2091} additive",
    ]


def test_a_marca_do_parceiro_so_entra_no_import():
    # a marca e nossa: diz de qual sessao a rota veio, e nao tem o que dizer
    # ao parceiro
    texto = render.render_peer(peer_parceiro())
    importacao = texto.split("xpl route-filter CUST-64500-IMPORT-V4")[1].split("end-filter")[0]
    exportacao = texto.split("xpl route-filter CUST-64500-EXPORT-V4")[1].split("end-filter")[0]
    assert "64512:2091" in importacao
    assert "64512:2091" not in exportacao


def test_o_cliente_nao_leva_a_marca_do_parceiro():
    assert "64512:2091" not in render.render_peer(peer_cliente())


def test_o_parceiro_emite_os_mesmos_objetos_do_cliente():
    texto = render.render_peer(peer_parceiro())
    for nome in (
        "xpl ip-prefix-list PL-CUST-64500-V4",
        "xpl ip-prefix-list PL-CUST-64500-BH-V4",
        "xpl as-path-list AP-CUST-64500",
        "xpl route-filter CUST-64500-IMPORT-V4",
        "xpl route-filter CUST-64500-EXPORT-V4",
        "xpl route-filter APPLY-PEER-64500",
        "bgp 64512",
    ):
        assert nome in texto, nome


def test_golden_do_parceiro():
    assert render.render_peer(peer_parceiro()) == (
        GOLDEN / "parceiro.txt").read_text(encoding="ascii")


def _export(texto, token="268127", fam="V4"):
    return texto.split("xpl route-filter CUST-%s-EXPORT-%s" % (token, fam))[1] \
        .split("end-filter")[0]


def test_tabela_full_nao_tem_portao():
    export = _export(render.render_peer(peer_cliente(tabela="full")))
    assert "CL-ORIGEM-ANUNCIAVEL" not in export
    assert "CL-ORIGEM-PARCIAL-IX" not in export
    assert export.strip().endswith("finish")


def test_tabela_nenhuma_recusa_tudo():
    # a default nao passa por este filtro: o VRP a origina por fora dele
    export = _export(render.render_peer(peer_cliente(tabela="nenhuma")))
    linhas = [l.strip() for l in export.splitlines()
              if l.strip() and not l.strip().startswith("#")]
    assert linhas == ["refuse"]


def test_tabela_parcial_so_libera_propria_e_de_cliente():
    export = _export(render.render_peer(peer_cliente(tabela="parcial")))
    assert ("if not community matches-any CL-ORIGEM-ANUNCIAVEL then\n"
            "  refuse\n endif") in export
    assert "CL-ORIGEM-PARCIAL-IX" not in export


def test_tabela_parcial_ix_usa_a_lista_com_o_ix():
    export = _export(render.render_peer(peer_cliente(tabela="parcial_ix")))
    assert ("if not community matches-any CL-ORIGEM-PARCIAL-IX then\n"
            "  refuse\n endif") in export


def test_o_portao_vem_depois_dos_vetos_e_antes_do_prepend():
    export = _export(render.render_peer(peer_cliente(tabela="parcial")))
    assert export.index("CL-RESTRICAO") < export.index("CL-ORIGEM-ANUNCIAVEL")
    assert export.index("64512:1901") < export.index("CL-ORIGEM-ANUNCIAVEL")
    assert export.index("CL-ORIGEM-ANUNCIAVEL") < export.index("{64512:3:268127}")


def test_o_cabecalho_do_downstream_diz_a_tabela():
    texto = render.render_peer(peer_cliente(tabela="parcial"))
    assert "# tabela recebida: parcial" in texto.splitlines()[:8]


def test_o_cabecalho_do_upstream_nao_fala_de_tabela():
    assert "tabela recebida" not in render.render_peer(peer_upstream())


def test_o_membro_mostra_a_tabela_do_grupo_e_nao_a_dele():
    # o export do membro chama o do grupo: a tabela gravada no membro nao
    # vale, e o cabecalho nao pode dizer que vale
    grupo = grupo_cliente_sem_asn()
    grupo.tabela = "parcial"
    membro = peer_membro_sem_override(grupo.id)
    membro.tipo = "cliente"
    membro.tabela = "full"
    texto = render.render_peer(membro, grupo=grupo)
    assert ("# tabela recebida: parcial (a do grupo %s)" % grupo.nome
            in texto.splitlines()[:8])
    assert "CL-ORIGEM" not in texto


def test_o_grupo_de_cliente_aplica_o_portao():
    grupo = grupo_cliente_sem_asn()
    grupo.tabela = "parcial"
    texto = render.render_grupo(grupo)
    assert "# tabela recebida: parcial" in texto
    assert "if not community matches-any CL-ORIGEM-ANUNCIAVEL then" in texto


def test_quem_reaproveita_mostra_a_tabela_da_origem():
    origem = peer_cliente(tabela="parcial_ix")
    copia = peer_cliente(id=2, apelido="ACME-BKP", tabela="nenhuma",
                         politica_de=origem.id)
    texto = render.render_peer(copia, origem=origem)
    assert any(l.startswith("# tabela recebida: parcial_ix")
               for l in texto.splitlines()[:8])


@pytest.mark.parametrize("arquivo,tabela", [
    ("cliente-nenhuma.txt", "nenhuma"),
    ("cliente-parcial.txt", "parcial"),
    ("cliente-parcial-ix.txt", "parcial_ix"),
])
def test_golden_do_cliente_por_tabela(arquivo, tabela):
    assert render.render_peer(peer_cliente(tabela=tabela, default_route=True)) == (
        GOLDEN / arquivo).read_text(encoding="ascii")


def test_golden_do_grupo_de_cliente_parcial():
    grupo = grupo_cliente_sem_asn()
    grupo.tabela = "parcial"
    assert render.render_grupo(grupo) == (
        GOLDEN / "grupo-cliente-parcial.txt").read_text(encoding="ascii")


# Fix round 2: o golden nao pega esta. Ele cobre so um peer v4-only, entao o
# laco de familia roda uma vez e a duplicata nao aparece; num peer dual-stack
# a lista, que nao tem eixo de familia, saia definida duas vezes.


def test_ap_cust_e_emitida_uma_vez_so():
    # a lista nao tem eixo de familia: dentro do laco ela sai duas vezes
    # para um peer dual-stack, e o objeto fica definido em dobro
    texto = render.render_peer(peer_cliente(
        prefixos={"v4": ["45.169.232.0/22"], "v6": ["2001:db8::/32"]},
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"},
                 "v6": {"local": "2001:db8::1", "remoto": "2001:db8::2"}},
    ))
    assert texto.count("xpl as-path-list AP-CUST-268127") == 1


# Task 6: o template de upstream. Mesmas listas por peer do cliente, mais
# as excecoes de TE e o blackhole que define o anuncio do host.


def peer_upstream(**kw):
    base = dict(
        id=1, nome="Upstream #1", tipo="upstream", asn=14840,
        classe=None, descricao="UPSTREAM-01-AS14840",
        lp_base=100, origem=1400, aprendizado=3100,
        prefixos={"v4": [], "v6": []},
        te_prefixos={"v4": ["198.51.100.0/24"], "v6": []},
        ap_block=["270814"], ap_te=["264381"],
        timer_keepalive=10, timer_hold=30,
        prepend_base=1, route_limit=1500000,
        sessoes={"v4": {"local": "203.0.113.2", "remoto": "203.0.113.1"}, "v6": {}},
        bh_upstream="14840:666",
    )
    base.update(kw)
    return Peer(**base)


def test_upstream_emite_os_objetos_do_tipo():
    texto = render.render_peer(peer_upstream())
    for nome in (
        "xpl as-path-list AP-BLOCK-14840",
        "xpl as-path-list AP-TE-PREFER-14840",
        "xpl ip-prefix-list PL-TE-PREFER-14840-V4",
        "xpl community-list CL-NOADV-14840",
        "xpl large-community-list LC-NOADV-14840",
        "xpl community-list CL-5PPA-01",
        "xpl large-community-list LC-5PPA-14840",
        "xpl large-community-list LC-PREP1-14840",
        "xpl large-community-list LC-PREP2-14840",
        "xpl large-community-list LC-PREP3-14840",
        "xpl route-filter UP-14840-IMPORT-V4",
        "xpl route-filter UP-14840-EXPORT-V4",
        "xpl route-filter APPLY-PEER-14840",
    ):
        assert nome in texto, nome


def test_upstream_nao_emite_a_community_list_do_peer():
    assert "xpl community-list CL-PEER-14840" not in render.render_peer(peer_upstream())


def test_noadv_do_upstream_leva_absoluta_do_tipo_e_deste_peer():
    texto = render.render_peer(peer_upstream())
    corpo = texto.split("xpl community-list CL-NOADV-14840")[1].split("end-list")[0]
    assert "64512:200" in corpo and "64512:201" in corpo and "64512:5010" in corpo


def test_cl_5ppa_tem_os_cinco_digitos():
    texto = render.render_peer(peer_upstream())
    corpo = texto.split("xpl community-list CL-5PPA-01")[1].split("end-list")[0]
    for d in range(5):
        assert "64512:501%d" % d in corpo


def test_ap_te_prefer_usa_origin():
    # PLANO.md: "AP-TE-PREFER-14840 / origin '264381'"
    texto = render.render_peer(peer_upstream())
    corpo = texto.split("xpl as-path-list AP-TE-PREFER-14840")[1].split("end-list")[0]
    assert "origin '264381'" in corpo
    assert "pass" not in corpo


def test_import_do_upstream_carimba_com_overwrite_antes_da_excecao_de_te():
    # a varredura e sobre o XPL, nao sobre a prosa: o comentario do carimbo
    # cita o overwrite, e comentario nao carimba. Sem isso o index acha a
    # prosa antes da operacao e a ordem passa a valer seja qual for o lugar
    # do apply community.
    texto = render.render_peer(peer_upstream())
    import_ = texto.split("xpl route-filter UP-14840-IMPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in import_.splitlines() if not l.strip().startswith("!-"))
    assert "apply community {64512:1400, 64512:3100, 64512:2000} overwrite" in codigo
    assert "apply large-community {64512:1000:14840} overwrite" in codigo
    assert "apply local-preference 100" in codigo
    # os dois lados do index saem do mesmo texto. Medir um lado no corpo cru
    # e o outro no codigo nao compara ordem: os comentarios que precedem o
    # LP 250 empurram o indice cru, e o teste passa a aceitar o overwrite
    # depois da excecao. Movido o overwrite para la, so a forma simetrica
    # reprova; a assimetrica aprova.
    assert "apply local-preference 250" in codigo
    assert codigo.index("overwrite") < codigo.index("apply local-preference 250")
    assert [l.strip() for l in codigo.splitlines() if l.strip()][-1] == "approve"


def test_import_do_upstream_recusa_o_ap_block():
    # a varredura e sobre o XPL, nao sobre a prosa: a assercao e sobre a
    # clausula que o filtro aplica, e um comentario que viesse a cita-la
    # satisfaria o teste sem a operacao existir. Hoje nenhum !- cita a
    # clausula.
    texto = render.render_peer(peer_upstream())
    import_ = texto.split("xpl route-filter UP-14840-IMPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in import_.splitlines() if not l.strip().startswith("!-"))
    assert "if as-path in AP-BLOCK-14840 then" in codigo


def test_te_em_branco_nao_emite_o_ramo_nem_a_lista():
    # a varredura de "apply local-preference 250" e sobre o XPL, nao sobre a
    # prosa: a assercao e negativa, e um comentario que viesse a citar o LP a
    # quebraria sem a operacao voltar. Hoje nenhum !- do render cita o LP.
    p = peer_upstream(te_prefixos={"v4": [], "v6": []}, ap_te=[])
    texto = render.render_peer(p)
    import_ = texto.split("xpl route-filter UP-14840-IMPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in import_.splitlines() if not l.strip().startswith("!-"))
    assert "PL-TE-PREFER-14840-V4" not in import_
    assert "AP-TE-PREFER-14840" not in import_
    assert "apply local-preference 250" not in codigo
    assert "xpl ip-prefix-list PL-TE-PREFER-14840-V4" not in texto
    assert "xpl as-path-list AP-TE-PREFER-14840" not in texto


def test_te_so_com_prefixo_de_uma_familia_nao_emite_o_ramo_da_outra():
    # v4 tem prefixo, v6 nao: o ramo de TE so sai no filtro v4.
    # ap_te fica vazio aqui porque a as-path-list nao tem eixo de familia:
    # com ela preenchida o ramo as-path sai nas duas, de proposito (o teste
    # seguinte e o que fixa isso).
    p = peer_upstream(
        te_prefixos={"v4": ["198.51.100.0/24"], "v6": []}, ap_te=[],
        sessoes={"v4": {"local": "203.0.113.2", "remoto": "203.0.113.1"},
                 "v6": {"local": "2001:db8::2", "remoto": "2001:db8::1"}})
    texto = render.render_peer(p)
    v6 = texto.split("xpl route-filter UP-14840-IMPORT-V6")[1].split("end-filter")[0]
    v4 = texto.split("xpl route-filter UP-14840-IMPORT-V4")[1].split("end-filter")[0]
    # a varredura e sobre o XPL, nao sobre a prosa: os dois filtros carregam
    # o mesmo comentario do ramo de TE, e e a negativa do v6 que a prosa
    # quebraria se viesse a citar o LP.
    codigo_v6 = "\n".join(l for l in v6.splitlines() if not l.strip().startswith("!-"))
    codigo_v4 = "\n".join(l for l in v4.splitlines() if not l.strip().startswith("!-"))
    assert "apply local-preference 250" not in codigo_v6
    assert "apply local-preference 250" in codigo_v4


def test_ap_te_sozinho_sai_nas_duas_familias():
    # o AP-TE-PREFER e um set de ASN, sem eixo de familia: preenchido so
    # ele, a excecao vale para v4 e v6. A alternativa, exigir prefixo de TE
    # na familia, deixaria um ap_te preenchido sem efeito nenhum.
    p = peer_upstream(
        te_prefixos={"v4": [], "v6": []},
        sessoes={"v4": {"local": "203.0.113.2", "remoto": "203.0.113.1"},
                 "v6": {"local": "2001:db8::2", "remoto": "2001:db8::1"}})
    texto = render.render_peer(p)
    for fam in ("V4", "V6"):
        corpo = texto.split("xpl route-filter UP-14840-IMPORT-%s" % fam)[1].split("end-filter")[0]
        # a varredura e sobre o XPL, nao sobre a prosa: um comentario que
        # viesse a citar a lista ou o LP satisfaria a positiva e quebraria a
        # negativa sem a operacao mudar. Hoje nenhum !- cita os dois.
        codigo = "\n".join(l for l in corpo.splitlines() if not l.strip().startswith("!-"))
        assert "if as-path in AP-TE-PREFER-14840 then" in codigo
        assert "apply local-preference 250" in codigo
    assert "xpl ip-prefix-list PL-TE-PREFER-14840-V4" not in texto


def test_export_do_upstream_chama_o_apply_peer_por_ultimo():
    # a varredura e sobre o XPL, nao sobre a prosa: um comentario no fim do
    # filtro passaria a ser a ultima linha sem mexer na operacao. Hoje o
    # filtro ja termina em codigo, entao as duas formas concordam.
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in export.splitlines() if not l.strip().startswith("!-"))
    corpo = [l.strip() for l in codigo.splitlines() if l.strip()]
    assert corpo[-2] == "call route-filter APPLY-PEER-14840"
    assert corpo[-1] == "finish"


def test_export_do_upstream_tem_exatamente_um_overwrite():
    # a varredura e sobre o XPL, nao sobre a prosa: o comentario do passo 1
    # cita o overwrite, e comentario nao carimba.
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in export.splitlines() if not l.strip().startswith("!-"))
    assert codigo.count("overwrite") == 1
    assert "apply community {14840:666} overwrite" in codigo


def test_blackhole_do_upstream_usa_a_community_do_campo():
    # a varredura e sobre o XPL, nao sobre a prosa, pelo mesmo motivo.
    texto = render.render_peer(peer_upstream(bh_upstream="64500:666"))
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in export.splitlines() if not l.strip().startswith("!-"))
    assert "apply community {64500:666} overwrite" in codigo


def test_blackhole_sem_community_nao_emite_overwrite():
    # a varredura e sobre o XPL, nao sobre a prosa: sem community de campo a
    # operacao nao sai, mesmo com o comentario do passo 1 citando o nome.
    texto = render.render_peer(peer_upstream(bh_upstream=""))
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in export.splitlines() if not l.strip().startswith("!-"))
    assert "overwrite" not in codigo
    # o ramo continua existindo: o /32 que nao propaga e recusado
    assert "refuse" in codigo


def test_blackhole_do_upstream_precede_o_export_sanity():
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert export.index("CL-BLACKHOLE-PROPAGATE") < export.index("call route-filter EXPORT-SANITY")


def test_ramo_5ppa_aninha_e_a_classe_6ca_fica_no_else():
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "if community matches-any CL-5PPA-01 or large-community matches-any LC-5PPA-14840 then" in export
    assert "{64512:5014}" in export and "{64512:5013}" in export and "{64512:5012}" in export
    assert "{64512:5011}" not in export      # P1 explicito so barra a classe
    assert "if community matches-any {64512:614} then" in export
    assert export.index("CL-5PPA-01") < export.index("64512:614")


def test_prepend_base_zero_nao_emite_linha():
    texto = render.render_peer(peer_upstream(prepend_base=0))
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "apply as-path 64512 0 additive" not in export


def test_prepend_base_maior_que_zero_emite_linha_literal():
    # 4 e de proposito: a escada dos passos 6 e 7 so emite 1, 2 e 3, entao um
    # valor que ela nao alcanca isola o passo 8. Com prepend_base=1 o teste
    # passava sem o passo 8 existir, porque a escada ja emite "64512 1".
    texto = render.render_peer(peer_upstream(prepend_base=4))
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "apply as-path 64512 4 additive" in export


def test_export_do_upstream_med_zero_e_rede_do_2000():
    texto = render.render_peer(peer_upstream())
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert "apply med 0" in export
    assert "if community matches-any {64512:2000} then" in export


def test_bloco_bgp_do_upstream_traz_o_timer():
    texto = render.render_peer(peer_upstream())
    assert "peer 203.0.113.1 timer keepalive 10 hold 30" in texto
    assert "peer 203.0.113.1 route-limit 1500000 alert-only" in texto
    assert "peer 203.0.113.1 bfd enable" in texto
    assert "peer 203.0.113.1 capability-advertise graceful-restart" in texto


def test_golden_do_upstream():
    assert render.render_peer(peer_upstream()) == (GOLDEN / "upstream.txt").read_text(encoding="ascii")


# Fix round: o golden e single-family, entao o laco de familia roda uma vez
# e uma lista sem eixo de familia nao duplica. So um peer dual-stack pega.


def test_ap_block_e_ap_te_prefer_saem_uma_vez_so():
    # nem AP-BLOCK nem AP-TE-PREFER carregam familia no nome: dentro do laco
    # as duas sairiam definidas em dobro num peer dual-stack
    texto = render.render_peer(peer_upstream(
        sessoes={"v4": {"local": "203.0.113.2", "remoto": "203.0.113.1"},
                 "v6": {"local": "2001:db8::2", "remoto": "2001:db8::1"}},
    ))
    assert texto.count("xpl as-path-list AP-BLOCK-14840") == 1
    assert texto.count("xpl as-path-list AP-TE-PREFER-14840") == 1


def test_nenhum_objeto_sem_eixo_de_familia_sai_definido_duas_vezes():
    # a varredura e por classe, nao por objeto: num peer dual-stack o laco de
    # familia roda duas vezes, e todo objeto definido dentro dele que nao
    # carrega a familia no nome sai em dobro. Pega os sete sets de uma vez, e
    # e a varredura que os tipos seguintes vao precisar.
    texto = render.render_peer(peer_upstream(
        sessoes={"v4": {"local": "203.0.113.2", "remoto": "203.0.113.1"},
                 "v6": {"local": "2001:db8::2", "remoto": "2001:db8::1"}},
    ))
    definicoes = re.findall(r"^xpl \S+ \S+$", texto, flags=re.MULTILINE)
    repetidas = sorted({d for d in definicoes if definicoes.count(d) > 1})
    assert not repetidas, "definido duas vezes: %s" % ", ".join(repetidas)
    # o inventario do dual-stack: os 7 sets sem eixo, a prefix-list do v4 (a
    # do v6 nao sai, o fixture nao tem prefixo de TE em v6), os 4 filtros, a
    # AP-BLOCK, a AP-TE-PREFER, a AP-OWN e a APPLY-PEER
    assert len(definicoes) == 16


def test_ap_block_em_branco_nao_emite_a_lista_nem_o_ramo():
    # ap_block vazio e o default do modelo, e sem block list a excecao nao
    # existe: a definicao acompanha a referencia, que ja era condicional
    texto = render.render_peer(peer_upstream(ap_block=[]))
    # a varredura da clausula e sobre o XPL, nao sobre a prosa: e operacao,
    # e prosa pode cita-la.
    codigo = "\n".join(l for l in texto.splitlines() if not l.strip().startswith("!-"))
    assert "xpl as-path-list AP-BLOCK-14840" not in texto
    assert "if as-path in AP-BLOCK-14840" not in codigo
    # o portao do ap_te e independente: a lista de TE continua saindo
    assert "xpl as-path-list AP-TE-PREFER-14840" in texto


def test_bloco_bgp_do_upstream_tem_uma_linha_em_branco_antes_da_familia():
    # a emenda do grupo de sessao com o primeiro ipv4-family: uma linha em
    # branco so, como no golden do cliente
    texto = render.render_peer(peer_upstream())
    assert "peer 203.0.113.1 bfd enable\n\n ipv4-family unicast\n" in texto


# Task 7: o template de IX. Mesmos sets por peer do cliente e do upstream,
# mas sem nada de prepend por membro: o route server repassa o mesmo
# AS-path a todos, entao o egress da sessao com o RS e o mesmo para todo
# mundo. O que da politica por membro e o ingress, com peer-is.
#
# O fixture da um apelido IX-SP porque numa sessao de IX o ASN e o do route
# server e se repetiria em todo IX. O apelido vira o token, e o nome de
# objeto carrega o token cru, como no AP-CUST-<T> e no AP-BLOCK-<T>: os
# objetos com escopo por token saem com o IX duplicado (IX-IX-SP-IMPORT-V4,
# AP-IX-IX-SP). E a divergencia de nome registrada no brief, nao um defeito
# a consertar.


def peer_ix(**kw):
    base = dict(
        id=10, apelido="IX-SP", nome="IX.br Sao Paulo", tipo="ix",
        asn=26162, classe=None, descricao="IX-SP-AS26162",
        lp_base=190, origem=1300, aprendizado=3010, ix_id=9999,
        prefixos={"v4": [], "v6": []}, ap_prefer=["15169"],
        prepend_base=0, route_limit=500000,
        sessoes={"v4": {"local": "187.16.192.1", "remoto": "187.16.192.2"}, "v6": {}},
    )
    base.update(kw)
    return Peer(**base)


def test_ix_emite_os_objetos_do_tipo():
    texto = render.render_peer(peer_ix())
    for nome in (
        "xpl community-list CL-NOADV-IX-SP",
        "xpl large-community-list LC-NOADV-IX-SP",
        "xpl as-path-list AP-IX-IX-SP",
        "xpl route-filter IX-IX-SP-IMPORT-V4",
        "xpl route-filter IX-IX-SP-EXPORT-V4",
    ):
        assert nome in texto, nome


def test_ix_nao_emite_o_par_do_peer():
    texto = render.render_peer(peer_ix())
    assert "CL-PEER-IX-SP" not in texto
    assert "APPLY-PEER-IX-SP" not in texto
    assert "apply community CL-PEER" not in texto


def test_noadv_do_ix_leva_absoluta_do_tipo_e_deste_peer():
    texto = render.render_peer(peer_ix())
    corpo = texto.split("xpl community-list CL-NOADV-IX-SP")[1].split("end-list")[0]
    assert "64512:200" in corpo and "64512:203" in corpo and "64512:5100" in corpo


def test_ap_prefer_usa_peer_is():
    # PLANO.md: "AP-IX-CDN-A / peer-is '64510'"
    texto = render.render_peer(peer_ix())
    corpo = texto.split("xpl as-path-list AP-IX-IX-SP")[1].split("end-list")[0]
    assert "peer-is '15169'" in corpo
    assert "pass" not in corpo


def test_ix_import_nao_limita_comprimento_de_path():
    """O limite `length ge 4` saiu: comprimento mede tamanho, nao autorizacao,
    e a regra recusava prepend de membro e cone legitimo. Quem autoriza no IX
    e o IMPORT-SANITY, com o AP-LOCAL-ORIGIN."""
    texto = render.render_peer(peer_ix())
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert "length" not in import_
    assert "refuse" not in import_
    assert import_.lstrip().startswith("call route-filter IMPORT-SANITY-V4")


def test_ix_import_carimba_com_overwrite_e_a_informativa_do_ix():
    texto = render.render_peer(peer_ix())
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert "apply community {64512:1300, 64512:3010, 64512:2000} overwrite" in import_
    assert "apply large-community {64512:1001:9999} overwrite" in import_


def test_ix_import_sobe_lp_para_membro_preferido():
    texto = render.render_peer(peer_ix())
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert "if as-path in AP-IX-IX-SP then" in import_
    assert "apply local-preference 195" in import_
    assert "apply local-preference 190" in import_


def test_ix_sem_membro_preferido_nao_emite_o_ramo_de_195():
    texto = render.render_peer(peer_ix(ap_prefer=[]))
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert "apply local-preference 190" in import_
    assert "apply local-preference 195" not in import_
    # o nome sai do token cru, como no AP-CUST-<T> e no AP-BLOCK-<T>. Com o
    # apelido IX-SP a lista e AP-IX-IX-SP: o mesmo IX duplicado do nome do
    # filtro, que e a divergencia registrada.
    assert "xpl as-path-list AP-IX-IX-SP" not in texto


def test_ix_import_fecha_em_finish():
    texto = render.render_peer(peer_ix())
    import_ = texto.split("xpl route-filter IX-IX-SP-IMPORT-V4")[1].split("end-filter")[0]
    assert [l.strip() for l in import_.splitlines() if l.strip()][-1] == "finish"


def test_ix_export_nao_tem_prepend_por_peer():
    # a varredura e sobre o XPL, nao sobre a prosa: o comentario do ramo 6CA
    # explica justamente por que nao existe prepend por membro aqui.
    texto = render.render_peer(peer_ix())
    export = texto.split("xpl route-filter IX-IX-SP-EXPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in export.splitlines() if not l.strip().startswith("!-"))
    assert "5PPA" not in codigo


def test_ix_export_usa_a_classe_2():
    texto = render.render_peer(peer_ix())
    export = texto.split("xpl route-filter IX-IX-SP-EXPORT-V4")[1].split("end-filter")[0]
    assert "64512:624" in export and "64512:623" in export and "64512:622" in export


def test_ix_export_nao_limpa_e_nao_chama_apply_peer():
    # a varredura e sobre o XPL, nao sobre a prosa, pelo mesmo motivo: o
    # comentario de fecho cita o que o filtro nao faz.
    texto = render.render_peer(peer_ix())
    export = texto.split("xpl route-filter IX-IX-SP-EXPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in export.splitlines() if not l.strip().startswith("!-"))
    assert "overwrite" not in codigo
    assert "APPLY-PEER" not in codigo


def test_ix_export_chama_export_sanity():
    texto = render.render_peer(peer_ix())
    export = texto.split("xpl route-filter IX-IX-SP-EXPORT-V4")[1].split("end-filter")[0]
    assert "call route-filter EXPORT-SANITY" in export


def test_golden_do_ix():
    assert render.render_peer(peer_ix()) == (GOLDEN / "ix.txt").read_text(encoding="ascii")


def test_nenhum_objeto_do_ix_sem_eixo_de_familia_sai_definido_duas_vezes():
    # a varredura e por classe, nao por objeto: num peer dual-stack o laco de
    # familia roda duas vezes, e todo objeto definido dentro dele que nao
    # carrega a familia no nome sai em dobro. Pega os tres sets sem eixo do
    # IX de uma vez, e e a varredura que o PNI (Task 8) vai reaproveitar.
    texto = render.render_peer(peer_ix(
        sessoes={"v4": {"local": "187.16.192.1", "remoto": "187.16.192.2"},
                 "v6": {"local": "2001:db8::1", "remoto": "2001:db8::2"}},
    ))
    definicoes = re.findall(r"^xpl \S+ \S+$", texto, flags=re.MULTILINE)
    repetidas = sorted({d for d in definicoes if definicoes.count(d) > 1})
    assert not repetidas, "definido duas vezes: %s" % ", ".join(repetidas)


def test_bloco_bgp_do_ix_tem_uma_linha_em_branco_antes_da_familia():
    # a emenda do grupo de sessao com o primeiro ipv4-family: uma linha em
    # branco so, como no golden do cliente
    texto = render.render_peer(peer_ix())
    assert "peer 187.16.192.2 bfd enable\n\n ipv4-family unicast\n" in texto


# Incremento: o check-first-as desligado na sessao de IX. O route server e
# transparente e nao insere o proprio ASN no path, entao o peer cujo path
# chega nao tem o ASN do vizinho na frente e o VRP descarta a rota antes de
# ela alcancar o filtro. O que o undo abre e o path vazio, e quem o barra e
# o AP-LOCAL-ORIGIN do IMPORT-SANITY, que o import de IX chama primeiro.


def test_ix_desliga_o_check_first_as():
    # a forma e a positiva depois do undo, como o VRP escreve, e a linha fica
    # colada na da descricao. A assercao e de vizinhanca, entao pega tambem a
    # linha em branco que um comentario mal fechado no template deixaria
    # entre as duas.
    texto = render.render_peer(peer_ix())
    assert (" peer 187.16.192.2 description IX-SP-AS26162\n"
            " undo peer 187.16.192.2 check-first-as enable\n") in texto


def test_ix_dual_stack_desliga_o_check_first_as_nas_duas_sessoes():
    # cada familia tem o proprio endereco de remoto, e o gate e por tipo,
    # nao por familia: a linha sai uma vez por sessao
    texto = render.render_peer(peer_ix(
        sessoes={"v4": {"local": "187.16.192.1", "remoto": "187.16.192.2"},
                 "v6": {"local": "2001:db8::1", "remoto": "2001:db8::2"}},
    ))
    assert " undo peer 187.16.192.2 check-first-as enable\n" in texto
    assert " undo peer 2001:db8::2 check-first-as enable\n" in texto
    assert texto.count("check-first-as") == 2


def test_membro_de_grupo_de_ix_tambem_desliga_o_check_first_as():
    """O membro de grupo nao passa pelo sessao_do_peer: ele escreve as linhas
    da sessao dele no proprio bloco, e por isso o undo ficava so no caminho do
    peer avulso. Dentro do grupo o route server continua transparente, e a
    sessao sem o undo nao sobe com trafego nenhum."""
    grupo = grupo_ix(nome="IXBR", id=4)
    membro = membro_com_override_do_tipo("ix", grupo)
    texto = render.render_peer(membro, grupo=grupo)
    assert " undo peer 192.0.2.3 check-first-as enable\n" in texto
    assert " undo peer 2001:db8:100::2 check-first-as enable\n" in texto
    assert texto.count("check-first-as") == 2


def test_o_import_de_cada_tipo_externo_responde_ao_gshut_do_vizinho():
    """O GSHUT (RFC 8326) e o vizinho pedindo para sair da preferencia sem
    derrubar a sessao. Duas coisas precisam estar na ordem certa: a leitura da
    community, que so existe ate o overwrite, e o LP 0, que tem que ser a
    ultima escrita de local-preference - antes das outras, a drenagem pedida
    pelo vizinho seria sobrescrita. O ponto em aberto do PLANO fica fechado
    nos tres tipos, que antes so o cliente respondia."""
    # `finish` nos tres: `approve` nao encerra o processamento, so reencaminha
    # para o proximo `if`, e o LP 100/500 de baixo passaria por cima do zero
    for nome, peer, marca, fim in (
            ("upstream", peer_upstream(), "UP-14840-IMPORT-V4", "finish"),
            ("ix", peer_ix(), "IX-IX-SP-IMPORT-V4", "finish"),
            ("pni", peer_pni(), "PNI-CDN-A-IMPORT-V4", "finish")):
        texto = render.render_peer(peer)
        filtro = texto[texto.index("xpl route-filter %s" % marca):]
        filtro = filtro[:filtro.index("end-filter")]

        assert "if community matches-any CL-GSHUT then" in filtro, nome
        # o ramo vem antes do carimbo, que e quem apaga a community
        assert (filtro.index("if community matches-any CL-GSHUT")
                < filtro.index("apply community")), nome
        # o corpo do ramo e o que esta indentado um nivel a mais que o corpo
        # do filtro: o carimbo de dentro dele tem if/else proprio, entao cortar
        # no primeiro endif pegaria o de dentro
        linhas = []
        for linha in filtro.split("if community matches-any CL-GSHUT then\n")[1].splitlines():
            if not linha.strip():
                continue
            if not linha.startswith("  "):
                break
            linhas.append(linha.strip())
        assert "if community matches-any CL-RESTRICAO then" in linhas, (nome, linhas)
        # o ramo carimba (sem isso a rota drenada sai sem classificacao e o
        # EXPORT-SANITY a recusa no egress), drena com LP 0 e encerra o
        # filtro, para o 250, o 500 e o LP do CDN preferido nao passarem por
        # cima da drenagem
        assert any("overwrite" in l for l in linhas), (nome, linhas)
        assert "apply local-preference 0" in linhas, (nome, linhas)
        assert linhas[-1] == fim, (nome, linhas)


def test_o_base_recusa_o_prefixo_proprio_vindo_de_fora():
    """Nem o agregado nem os mais especificos dele voltam de upstream, IX ou
    PNI. A ancora NULL0 nao impede o desvio: no encaminhamento, o mais
    especifico ganha."""
    blocos = {"v4": [Bloco(prefixo="45.169.232.0/22"),
                     Bloco(prefixo="45.169.236.0/23", ativo=False),
                     Bloco(prefixo="45.169.237.0/24")],
              "v6": [Bloco(prefixo="2804:3300::/32")]}
    texto = render.render_base(blocos=blocos)

    v4 = texto.split("xpl route-filter REJEITA-BLOCO-PROPRIO-V4")[1].split("end-filter")[0]
    assert "if ip route-destination in {45.169.232.0 22 le 32} then" in v4
    assert "refuse" in v4
    # o bloco fora de servico nao entra: e o mesmo portao da originacao
    assert "45.169.236.0" not in v4
    # o pedaco dentro do agregado tambem nao: o `le 32` do /22 ja o alcanca,
    # e o filtro roda no import de toda sessao externa
    assert "45.169.237.0" not in v4
    v6 = texto.split("xpl route-filter REJEITA-BLOCO-PROPRIO-V6")[1].split("end-filter")[0]
    assert "if ipv6 route-destination in {2804:3300:: 32 le 128} then" in v6


def test_o_filtro_do_bloco_proprio_sai_vazio_sem_bloco_cadastrado():
    """Ele sai sempre, para os imports externos poderem chama-lo sem depender
    do cadastro; sem bloco, so fecha em break e nao decide nada."""
    v4 = render.render_base().split("xpl route-filter REJEITA-BLOCO-PROPRIO-V4")[1]
    v4 = v4.split("end-filter")[0]
    assert "refuse" not in v4
    assert v4.strip() == "break"


def test_os_imports_externos_chamam_o_filtro_do_bloco_proprio():
    """O filtro entra em upstream, IX e PNI, onde nao ha whitelist. No import
    de cliente nao: quem confina la e o PL-CUST do cadastro dele, e um bloco
    alocado dentro do nosso agregado e rota legitima da sessao."""
    for peer in (peer_upstream(), peer_ix(), peer_pni()):
        assert ("call route-filter REJEITA-BLOCO-PROPRIO-V4"
                in render.render_peer(peer))
    for peer in (peer_cliente(), peer_parceiro()):
        assert "REJEITA-BLOCO-PROPRIO" not in render.render_peer(peer)


def test_o_rtbh_do_export_de_upstream_respeita_bloqueio_e_escopo():
    """O ramo de blackhole termina em finish, entao o bloqueio do proprio
    destino e o escopo precisam ser checados dentro dele: sem isso um /32
    marcado com "nao anunciar para este peer" ou "somente IX" sai para o
    upstream assim mesmo. O 200 fica fora, e e o ponto delicado: ele e a marca
    que todo blackhole importado carrega, e bani-lo ali mataria a propagacao
    inteira em vez de so a do destino bloqueado."""
    from app import plan
    peer = peer_upstream()
    texto = render.render_peer(peer)
    filtro = texto[texto.index("xpl route-filter UP-14840-EXPORT-V4"):]
    filtro = filtro[:filtro.index("end-filter")]
    ramo = filtro.split("if community matches-any CL-BLACKHOLE-PROPAGATE then")[1]
    ramo = ramo.split("else")[0]

    for valor in plan.bloqueio_do_destino("upstream", peer.id):
        assert valor in ramo, valor
    assert plan.c_large(0, 14840) in ramo
    assert "if community matches-any CL-ONLY-NOT-UP then" in ramo
    # so o veto do destino e o escopo entram na checagem: nada de 200
    checagem = ramo.split("if community matches-any")[1].split(" then")[0]
    assert plan.c(200) not in checagem
    # e as checagens vem antes do finish que aceita
    assert ramo.index("CL-ONLY-NOT-UP") < ramo.index("finish")


def test_o_import_externo_preserva_a_restricao_padronizada():
    """NO_EXPORT, NO_ADVERTISE e NO_EXPORT_SUBCONFED dizem "nao anunciar", e o
    carimbo do import apaga a community recebida. A restricao e relida dentro
    do ramo que carimba, que e a unica janela em que ela existe, e volta como
    a marca propria: o egresso recusa rota marcada em qualquer destino. O
    `matches-any` de uma lista so le as tres de uma vez, entao duas restricoes
    juntas nao tem como uma apagar a outra antes de ser vista."""
    from app import plan
    base = render.render_base()
    assert [l.strip() for l in base.split("xpl community-list CL-RESTRICAO")[1].split("end-list")[0].splitlines() if l.strip()] == [
        "%s," % plan.RESTRICOES[0], "%s," % plan.RESTRICOES[1],
        "%s," % plan.RESTRICOES[2], plan.RESTRICAO]

    for nome, peer, marca in (("upstream", peer_upstream(), "UP-14840-IMPORT-V4"),
                              ("ix", peer_ix(), "IX-IX-SP-IMPORT-V4"),
                              ("pni", peer_pni(), "PNI-CDN-A-IMPORT-V4")):
        filtro = render.render_peer(peer)
        filtro = filtro[filtro.index("xpl route-filter %s" % marca):]
        filtro = filtro[:filtro.index("end-filter")]
        # duas vezes: o ramo de GSHUT e o caminho normal carimbam os dois
        assert filtro.count("if community matches-any CL-RESTRICAO then") == 2, nome
        # o ramo de cima carimba com a marca, o de baixo sem ela
        assert "apply community {64512:1400, 64512:3100, 64512:2000, 64512:9020} overwrite" in filtro or \
               "64512:9020} overwrite" in filtro, nome


def test_o_egresso_recusa_rota_com_restricao_padronizada():
    """Em destino nenhum: o EXPORT-SANITY cobre upstream, IX e PNI; o egresso
    de cliente nao passa por ele e tem a checagem propria; e o ramo de RTBH do
    upstream termina em finish antes dos dois, entao tem a dele."""
    assert "if community matches-any CL-RESTRICAO then" in render.render_base()
    for peer in (peer_cliente(), peer_parceiro()):
        assert "if community matches-any CL-RESTRICAO then" in render.render_peer(peer)

    texto = render.render_peer(peer_upstream())
    ramo = texto.split("if community matches-any CL-BLACKHOLE-PROPAGATE then")[1]
    ramo = ramo.split("else")[0]
    assert "if community matches-any CL-RESTRICAO then" in ramo


# com a quebra e o recuo de antes: o veto tem que abrir linha propria, e um
# comentario de template com `-` cola o `if` no `endif` de cima
VETO_BH = ("\n if community matches-any CL-BLACKHOLE or tag eq 666 then\n"
           "  refuse\n"
           " endif\n")


def test_o_import_de_cliente_recusa_blackhole_fora_do_ramo_de_host():
    """A auditoria v5, secao 3: o ramo de blackhole so casa o /32 ou /128 do
    PL-CUST-<T>-BH, e um /24 marcado com 65535:666 caia na whitelist normal.
    O additive preservava a community, e o /24 saia para upstream e IX
    pedindo descarte do bloco inteiro, sem o 667. O veto vem logo depois do
    ramo valido, que ja terminou em finish, e antes da whitelist."""
    for nome, texto, filtro in (
            ("cliente", render.render_peer(peer_cliente()), "CUST-268127-IMPORT-V4"),
            ("grupo", render.render_grupo(grupo_com_asn()), "CUST-UP-REDUNDANTE-IMPORT-V4")):
        trecho = texto.split("xpl route-filter %s" % filtro)[1].split("end-filter")[0]
        assert VETO_BH in trecho, nome
        assert trecho.index("PL-%s-BH-V4" % filtro[:-10]) < trecho.index(VETO_BH), nome
        assert trecho.index(VETO_BH) < trecho.index("if not ip route-destination in PL-"), nome


def test_nenhum_filtro_tem_condicao_com_parenteses_depois_de_call():
    """No NE40 (rt-tecmais-ne40-downstream), um `if (A or B) and C` depois de
    qualquer `call route-filter` faz o commit falhar quando o filtro e
    pendurado num peer; o objeto solto entra sem erro. A mesma condicao antes
    do call passa, e o if aninhado depois dele tambem."""
    textos = [render.render_peer(p()) for p in
              (peer_cliente, peer_parceiro, peer_upstream, peer_ix, peer_pni)]
    textos += [render.render_grupo(g) for g in
               (grupo_com_asn(), grupo_upstream(), grupo_ix(), grupo_pni())]
    textos.append(render.render_base())
    for texto in textos:
        for filtro in texto.split("xpl route-filter ")[1:]:
            corpo = filtro.split("end-filter")[0]
            if "call route-filter" not in corpo:
                continue
            depois = corpo[corpo.index("call route-filter"):]
            assert not re.search(r"^\s*(if|elseif) \(", depois, re.M), filtro.split("\n")[0]


def test_o_egresso_recusa_blackhole_que_chega_ao_caminho_normal():
    """A segunda barreira do mesmo achado. No upstream o ramo de host ja
    terminou em finish antes do EXPORT-SANITY, entao o veto ali so alcanca o
    que nao e host. IX e PNI passam pelo EXPORT-SANITY; o egresso de cliente
    nao, e leva o veto proprio."""
    base = render.render_base()
    sanity = base.split("xpl route-filter EXPORT-SANITY")[1].split("end-filter")[0]
    assert VETO_BH in sanity
    for peer in (peer_cliente(), peer_parceiro()):
        texto = render.render_peer(peer)
        export = texto.split("-EXPORT-V4")[1].split("end-filter")[0]
        assert VETO_BH in export, peer.tipo

    texto = render.render_peer(peer_upstream())
    filtro = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    assert filtro.index("CL-BLACKHOLE-PROPAGATE") < filtro.index("call route-filter EXPORT-SANITY")


def test_o_carimbo_do_pni_nao_repete_a_origem_bilateral():
    """O PNI cadastrado com origem 1200 carimbava `{..:1200, ..:1200, ..}`:
    a origem e a geografia fixa do PNI tem o mesmo valor."""
    texto = render.render_peer(peer_pni(origem=1200))
    assert "64512:1200, 64512:1200" not in texto
    assert "apply community {64512:1200, 64512:2000} overwrite" in texto


def test_peer_sem_descricao_nao_emite_a_linha_do_description():
    """`peer X description` sem argumento e linha incompleta de CLI, e o campo
    e livre no cadastro. Sem descricao, o comando nao sai."""
    assert "description" not in render.render_peer(peer_upstream(descricao=""))
    assert "description" not in render.render_peer(peer_cliente(descricao=""))


def test_membro_sem_descricao_nao_emite_a_linha_do_description():
    for tipo in ("cliente", "upstream", "ix", "pni"):
        grupo = grupo_do_tipo(tipo)
        membro = membro_com_override_do_tipo(tipo, grupo)
        membro.descricao = ""
        assert "description" not in render.render_peer(membro, grupo=grupo), tipo


def test_cliente_e_upstream_nao_desligam_o_check_first_as():
    # o gate e por tipo, e so a sessao de IX desliga. Nos dois outros tipos o
    # default fica, e o golden deles e igualdade byte a byte: se a linha
    # vazasse, ele reprovava sozinho. O teste nomeia a regra.
    assert "check-first-as" not in render.render_peer(peer_cliente())
    assert "check-first-as" not in render.render_peer(peer_upstream())


# Task 8: o template de PNI. Sessao bilateral, e a unica das tres que
# carrega allowlist de AS-path: o route server do IX nao permite confinar
# por ASN, e o upstream aceita a tabela inteira. O prepend por peer nao
# entra, e o par CL-PEER-<T> / APPLY-PEER-<T> tambem nao: a CDN nao tem
# community propria hoje (PLANO.md, "Tabela de peers e IDs").
#
# O apelido do fixture e CDN-A, e o nome de objeto carrega o token cru: o
# filtro sai PNI-CDN-A-IMPORT-V4 onde o PLANO escreve PNI-IMPORT-CDNA. E a
# divergencia de nome ja registrada no brief, nao um defeito a consertar.


def peer_pni(**kw):
    base = dict(
        id=20, apelido="CDN-A", nome="PNI CDN A", tipo="pni",
        asn=64510, classe=None, descricao="PNI-CDN-A-AS64510",
        lp_base=200, origem=1500, aprendizado=None,
        prefixos={"v4": [], "v6": []}, ap_allowed=["64510"],
        prepend_base=0, route_limit=10000,
        sessoes={"v4": {"local": "10.0.0.1", "remoto": "10.0.0.2"}, "v6": {}},
    )
    base.update(kw)
    return Peer(**base)


def test_pni_emite_os_objetos_do_tipo():
    texto = render.render_peer(peer_pni())
    for nome in (
        "xpl as-path-list AP-CDN-A-ALLOWED",
        "xpl community-list CL-NOADV-CDN-A",
        "xpl large-community-list LC-NOADV-CDN-A",
        "xpl route-filter PNI-CDN-A-IMPORT-V4",
        "xpl route-filter PNI-CDN-A-EXPORT-V4",
    ):
        assert nome in texto, nome


def test_pni_nao_emite_o_par_do_peer():
    texto = render.render_peer(peer_pni())
    assert "CL-PEER-CDN-A" not in texto
    assert "APPLY-PEER-CDN-A" not in texto
    assert "apply community CL-PEER" not in texto


def test_pni_nao_carrega_ponto_de_aprendizado():
    # 3xxx e ponto de aprendizado, e so upstream e IX o tem
    assert "64512:30" not in render.render_peer(peer_pni())


def test_noadv_do_pni_leva_absoluta_do_tipo_e_deste_peer():
    texto = render.render_peer(peer_pni())
    corpo = texto.split("xpl community-list CL-NOADV-CDN-A")[1].split("end-list")[0]
    assert "64512:200" in corpo and "64512:202" in corpo and "64512:5200" in corpo


def test_allowlist_usa_pass():
    # PLANO.md: "AP-CDNA-ALLOWED / pass '64510'"
    texto = render.render_peer(peer_pni())
    corpo = texto.split("xpl as-path-list AP-CDN-A-ALLOWED")[1].split("end-list")[0]
    assert "pass '64510'" in corpo


def test_pni_import_recusa_quem_nao_esta_na_allowlist():
    texto = render.render_peer(peer_pni())
    import_ = texto.split("xpl route-filter PNI-CDN-A-IMPORT-V4")[1].split("end-filter")[0]
    assert "if not as-path in AP-CDN-A-ALLOWED then" in import_
    assert "refuse" in import_


def test_pni_import_carimba_geografia_fixa_e_lp_200():
    texto = render.render_peer(peer_pni())
    import_ = texto.split("xpl route-filter PNI-CDN-A-IMPORT-V4")[1].split("end-filter")[0]
    assert "apply community {64512:1500, 64512:1200, 64512:2000} overwrite" in import_
    assert "apply large-community {64512:1000:64510} overwrite" in import_
    assert "apply local-preference 200" in import_
    assert [l.strip() for l in import_.splitlines() if l.strip()][-1] == "finish"


def test_pni_export_usa_a_classe_cdn():
    texto = render.render_peer(peer_pni())
    export = texto.split("xpl route-filter PNI-CDN-A-EXPORT-V4")[1].split("end-filter")[0]
    assert "64512:644" in export and "64512:643" in export and "64512:642" in export


def test_pni_export_nao_limpa_e_nao_prepende_por_peer():
    # a varredura e sobre o XPL, nao sobre a prosa: o comentario do ramo 6CA
    # cita o 5PPA como pendencia do plano, e o de fecho cita o APPLY-PEER-<T>
    # como o caminho no dia em que a CDN tiver community propria. As duas
    # prosas ficam; quem mede operacao e o codigo sem os comentarios.
    texto = render.render_peer(peer_pni())
    export = texto.split("xpl route-filter PNI-CDN-A-EXPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in export.splitlines() if not l.strip().startswith("!-"))
    assert "overwrite" not in codigo
    assert "5PPA" not in codigo
    assert "APPLY-PEER" not in codigo


def test_pni_export_chama_export_sanity():
    texto = render.render_peer(peer_pni())
    export = texto.split("xpl route-filter PNI-CDN-A-EXPORT-V4")[1].split("end-filter")[0]
    assert "call route-filter EXPORT-SANITY" in export


def test_golden_do_pni():
    assert render.render_peer(peer_pni()) == (GOLDEN / "pni.txt").read_text(encoding="ascii")


def test_nenhum_objeto_do_pni_sem_eixo_de_familia_sai_definido_duas_vezes():
    # a varredura e por classe, nao por objeto: num peer dual-stack o laco de
    # familia roda duas vezes, e todo objeto definido dentro dele que nao
    # carrega a familia no nome sai em dobro. No PNI sao os tres sets que
    # ficam fora do laco: a allowlist, o CL-NOADV e o LC-NOADV.
    texto = render.render_peer(peer_pni(
        sessoes={"v4": {"local": "10.0.0.1", "remoto": "10.0.0.2"},
                 "v6": {"local": "2001:db8::1", "remoto": "2001:db8::2"}},
    ))
    definicoes = re.findall(r"^xpl \S+ \S+$", texto, flags=re.MULTILINE)
    repetidas = sorted({d for d in definicoes if definicoes.count(d) > 1})
    assert not repetidas, "definido duas vezes: %s" % ", ".join(repetidas)


def test_bloco_bgp_do_pni_tem_uma_linha_em_branco_antes_da_familia():
    # a emenda do grupo de sessao com o primeiro ipv4-family: uma linha em
    # branco so, como no golden do cliente
    texto = render.render_peer(peer_pni())
    assert "peer 10.0.0.2 bfd enable\n\n ipv4-family unicast\n" in texto


# Task 12 (fix final): o quadro "ao criar o peer". O par CL-PEER-<T> /
# APPLY-PEER-<T> e de cliente e upstream - o IX e o PNI nao tem community
# propria de sessao, e nenhum dos dois egress chama APPLY-PEER.


def test_o_quadro_ao_criar_o_peer_so_existe_para_cliente_e_upstream():
    for peer in (peer_ix(), peer_pni()):
        assert render.render_criar_lista(peer) == "", peer.tipo
    for peer in (peer_cliente(), peer_upstream()):
        texto = render.render_criar_lista(peer)
        assert "xpl community-list CL-PEER-%s" % peer.token in texto, peer.tipo
        assert "xpl route-filter APPLY-PEER-%s" % peer.token in texto, peer.tipo


# Task 12 (fix final): o bloco de remocao. E o script que o operador cola
# para descomissionar a sessao, e era o unico dos blocos sem golden e sem
# teste. O laco de familia derrubava duas vezes todo objeto sem eixo de
# familia, e derrubava objeto que o bloco do peer so emite as vezes: no
# equipamento, undo de objeto que nao existe e erro.


def _definicoes(texto):
    return re.findall(r"^xpl (\S+) (\S+)$", texto, flags=re.MULTILINE)


def _undefinicoes(texto):
    return re.findall(r"^undo xpl (\S+) (\S+)$", texto, flags=re.MULTILINE)


def peer_cliente_remocao():
    return peer_cliente(sessoes={
        "v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"},
        "v6": {"local": "2001:db8:100::1", "remoto": "2001:db8:100::2"},
    })


def peer_parceiro_remocao():
    return peer_parceiro(sessoes={
        "v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"},
        "v6": {"local": "2001:db8:500::1", "remoto": "2001:db8:500::2"},
    })


def peer_upstream_remocao():
    # TE so no v4 de proposito: o nome do PL-TE-PREFER carrega a familia,
    # mas o do undo tem que seguir o portao do bloco do peer, familia a
    # familia. O ap_te fica vazio para o AP-TE-PREFER nao existir.
    return peer_upstream(
        te_prefixos={"v4": ["198.51.100.0/24"], "v6": []}, ap_te=[],
        sessoes={"v4": {"local": "203.0.113.2", "remoto": "203.0.113.1"},
                 "v6": {"local": "2001:db8:200::2",
                        "remoto": "2001:db8:200::1"}})


def peer_ix_remocao():
    # sem membro preferido: o AP-IX-<T> nao existe, e o undo nao pode sair
    return peer_ix(ap_prefer=[], sessoes={
        "v4": {"local": "187.16.192.1", "remoto": "187.16.192.2"},
        "v6": {"local": "2001:db8:300::1", "remoto": "2001:db8:300::2"},
    })


def peer_pni_remocao():
    return peer_pni(sessoes={
        "v4": {"local": "10.0.0.1", "remoto": "10.0.0.2"},
        "v6": {"local": "2001:db8:400::1", "remoto": "2001:db8:400::2"},
    })


def test_golden_da_remocao_do_cliente():
    assert render.render_remove(peer_cliente_remocao()) == (
        GOLDEN / "remover-cliente.txt").read_text(encoding="ascii")


def test_golden_da_remocao_do_parceiro():
    assert render.render_remove(peer_parceiro_remocao()) == (
        GOLDEN / "remover-parceiro.txt").read_text(encoding="ascii")


def test_golden_da_remocao_do_upstream():
    assert render.render_remove(peer_upstream_remocao()) == (
        GOLDEN / "remover-upstream.txt").read_text(encoding="ascii")


def test_golden_da_remocao_do_ix():
    assert render.render_remove(peer_ix_remocao()) == (
        GOLDEN / "remover-ix.txt").read_text(encoding="ascii")


def test_golden_da_remocao_do_pni():
    assert render.render_remove(peer_pni_remocao()) == (
        GOLDEN / "remover-pni.txt").read_text(encoding="ascii")


def peer_membro_com_override_remocao():
    # o membro com override cria so o que e dele: IMPORT, PL-CUST, AP-CUST,
    # APPLY-PEER e, no grupo sem ASN, o export por ASN. O IMPORT e o EXPORT do
    # GRUPO nao entram aqui: derrubar um objeto do grupo levaria a sessao dos
    # outros membros junto. Dual-stack como os outros goldens de remocao, para
    # o laco de familia aparecer no arquivo (a fabrica do membro esta no fim
    # deste arquivo).
    membro = peer_membro_sem_override(1)
    membro.prefixos = {"v4": [Bloco(prefixo="198.51.100.0/24")],
                       "v6": [Bloco(prefixo="2001:db8:100::/48")]}
    membro.classe = "transito"
    membro.origem = 1100
    membro.pop = 2001
    membro.sessoes = {
        "v4": {"local": "192.0.2.2", "remoto": "192.0.2.3"},
        "v6": {"local": "2001:db8:100::1", "remoto": "2001:db8:100::2"},
    }
    return membro


def test_golden_da_remocao_do_membro_com_override():
    assert render.render_remove(peer_membro_com_override_remocao(),
                                grupo=grupo_sem_asn()) == (
        GOLDEN / "remover-membro-override.txt").read_text(encoding="ascii")


def grupo_do_tipo(tipo):
    """O grupo de um dos cinco tipos, pelos fixtures que ja existem."""
    if tipo == "cliente":
        return grupo_cliente_sem_asn()
    if tipo == "parceiro":
        return grupo_sem_asn()
    if tipo == "upstream":
        return grupo_upstream(nome="OPERADORA", id=3)
    if tipo == "ix":
        return grupo_ix(nome="IXBR", id=4)
    return grupo_pni(nome="CDN", id=5)


def membro_com_override_do_tipo(tipo, grupo):
    """O membro do grupo nos cinco tipos, cada um com o override do seu.

    O que cada tipo le e diferente - o downstream confina pelo prefixo do
    cliente, o upstream pela excecao de TE, o IX pelo membro preferido e o
    PNI pela allowlist -, e e o override que da ao membro objetos so dele:
    sem ele o bloco do membro nao define nada, e a varredura de simetria
    compararia dois conjuntos vazios. Sessao dual-stack, como os membros dos
    goldens de remocao.
    """
    p = peer_membro_sem_override(grupo.id)
    p.tipo = tipo
    p.sessoes = {
        "v4": {"local": "192.0.2.2", "remoto": "192.0.2.3"},
        "v6": {"local": "2001:db8:100::1", "remoto": "2001:db8:100::2"},
    }
    if tipo in ("cliente", "parceiro"):
        p.prefixos = {"v4": [Bloco(prefixo="198.51.100.0/24")],
                  "v6": [Bloco(prefixo="2001:db8:100::/48")]}
        p.classe = "transito"
        p.origem = 1100
        p.pop = 2001
    elif tipo == "upstream":
        # origem e ponto de aprendizado 3xxx entram no carimbo das rotas
        # aprendidas (filtro_upstream_import), e sem eles o render do membro
        # nem completa
        p.origem = 1400
        p.aprendizado = 3100
        p.te_prefixos = {"v4": ["198.51.100.0/24"], "v6": []}
    elif tipo == "ix":
        p.origem = 1300
        p.aprendizado = 3200
        p.ix_id = 1234
        p.ap_prefer = [264130]
    else:
        p.origem = 1500
        p.ap_allowed = ["264130"]
    return p


def test_a_remocao_do_membro_derruba_exatamente_o_que_o_membro_cria():
    # mesma varredura por definicao do peer avulso, agora do outro lado do
    # portao e nos cinco tipos: o membro com override derruba os objetos dele
    # e mais nada. Nem a mais (undo de objeto que nao existe e erro no
    # equipamento), nem a menos (objeto orfao). O export por ASN, que o membro
    # do grupo sem ASN cria junto com os outros, entra na conta pelo lado dos
    # criados; os objetos do grupo nao, que esses nao sao dele.
    for tipo in ("cliente", "parceiro", "upstream", "ix", "pni"):
        grupo = grupo_do_tipo(tipo)
        membro = membro_com_override_do_tipo(tipo, grupo)
        assert membro.tem_filtro_proprio(), tipo
        criados = set(_definicoes(render.render_peer(membro, grupo=grupo)))
        derrubados = set(_undefinicoes(render.render_remove(membro, grupo=grupo)))
        assert derrubados == criados, (
            "%s: sobrando %s, faltando %s"
            % (tipo, sorted(derrubados - criados), sorted(criados - derrubados)))


def test_a_remocao_e_ascii_em_todos_os_tipos():
    for peer in (peer_cliente_remocao(), peer_parceiro_remocao(),
                 peer_upstream_remocao(), peer_ix_remocao(), peer_pni_remocao()):
        assert render.render_remove(peer).isascii(), peer.tipo


def test_a_saida_do_grupo_e_do_membro_e_ascii_nos_cinco_tipos():
    # no BASE o ASCII era cobrado do bloco base e do peer avulso - o render e a
    # remocao, aqui no test_render - e do grupo so na rota que serve o quadro
    # "ao criar", no test_app: o render do grupo, o do membro dentro dele e a
    # remocao do membro nao tinham assercao de ASCII nenhuma
    for tipo in ("cliente", "parceiro", "upstream", "ix", "pni"):
        grupo = grupo_do_tipo(tipo)
        membro = membro_com_override_do_tipo(tipo, grupo)
        assert render.render_grupo(grupo).isascii(), tipo
        assert render.render_peer(membro, grupo=grupo).isascii(), tipo
        assert render.render_remove(membro, grupo=grupo).isascii(), tipo
        # o quadro "ao criar" so tem conteudo no grupo de upstream: nos outros
        # quatro o render devolve vazio, e o isascii de uma string vazia nao
        # prova nada. O conteudo entra na assercao para o isascii ter o que
        # olhar onde o quadro existe, e o vazio para nao passar um quadro que
        # vazasse para onde ele nao existe.
        quadro = render.render_criar_lista(grupo=grupo)
        assert quadro.isascii(), tipo
        if tipo == "upstream":
            assert "xpl community-list CL-PEER-OPERADORA" in quadro, tipo
        else:
            assert quadro == "", tipo


def test_nenhum_undo_sai_duas_vezes():
    # a varredura e por classe, nao por objeto: num peer dual-stack o laco
    # de familia roda duas vezes, e tudo que sai dentro dele sem a familia
    # no nome viraria dois undos identicos na config
    for peer in (peer_cliente_remocao(), peer_parceiro_remocao(),
                 peer_upstream_remocao(), peer_ix_remocao(), peer_pni_remocao()):
        linhas = [l for l in render.render_remove(peer).splitlines() if l.strip()]
        repetidas = sorted({l for l in linhas if linhas.count(l) > 1})
        assert not repetidas, "%s: %s" % (peer.tipo, ", ".join(repetidas))


def test_o_bloco_de_remocao_derruba_exatamente_o_que_o_peer_cria():
    # a varredura e por definicao, nao por nome: o que o bloco do peer cria
    # tem que ser o que a remocao derruba, nem a mais (undo de objeto que
    # nao existe e erro no equipamento) nem a menos (objeto orfao). Vale
    # para as quatro combinacoes de opcionais, porque o bloco do peer so
    # emite alguns deles quando o campo tem conteudo.
    gente = [
        peer_cliente(), peer_cliente_remocao(),
        peer_parceiro(), peer_parceiro_remocao(),
        peer_upstream(), peer_upstream_remocao(),
        peer_upstream(te_prefixos={"v4": [], "v6": []}, ap_te=[], ap_block=[]),
        peer_ix(), peer_ix_remocao(),
        peer_pni(), peer_pni_remocao(),
    ]
    for peer in gente:
        criados = set(_definicoes(render.render_peer(peer)))
        derrubados = set(_undefinicoes(render.render_remove(peer)))
        assert derrubados == criados, (
            "%s: sobrando %s, faltando %s"
            % (peer.tipo, sorted(derrubados - criados), sorted(criados - derrubados)))


def test_a_remocao_do_ix_e_do_pni_nao_menciona_o_par_do_peer():
    # nem o undo, nem o comentario da lista que esses dois tipos nunca criam
    for peer in (peer_ix(), peer_pni()):
        texto = render.render_remove(peer)
        assert "CL-PEER-" not in texto, peer.tipo
        assert "APPLY-PEER-" not in texto, peer.tipo
    for peer in (peer_cliente(), peer_parceiro(), peer_upstream()):
        texto = render.render_remove(peer)
        assert "APPLY-PEER-%s" % peer.token in texto, peer.tipo
        assert "!- undo xpl community-list CL-PEER-%s" % peer.token in texto, peer.tipo


def test_a_remocao_nao_derruba_a_community_list_do_peer():
    # derrubar a sessao nao exige apagar a lista, e um undo descomentado sem
    # querer leva embora o que esta no equipamento. O cadastro permite
    # recriar pelo quadro "ao criar o peer", entao o undo sai comentado.
    for peer in (peer_cliente(), peer_parceiro(), peer_upstream()):
        texto = render.render_remove(peer)
        assert "\nundo xpl community-list CL-PEER-" not in texto, peer.tipo


# A CL-PEER-<T> saiu do equipamento e passou a viver no cadastro do peer. O
# bloco do peer so chama o filtro; quem escreve o conteudo da lista e o
# quadro "ao criar o peer". Reaplicar o bloco do peer nunca reescreve a
# lista, e era essa a razao de a lista nunca ter sido emitida no bloco.


def _apply_peer(texto, token):
    """O trecho do filtro APPLY-PEER-<T>, de `xpl` ate `end-filter`."""
    return texto.split("xpl route-filter APPLY-PEER-%s" % token)[1].split("end-filter")[0]


def _com_communities(peer, communities, large=None):
    return peer(communities=list(communities),
                large_communities=list(large or []))


def test_o_quadro_do_cliente_lista_as_communities_do_cadastro():
    texto = render.render_criar_lista(
        _com_communities(peer_cliente, ["64512:1500", "64512:1501"]))
    corpo = texto.split("xpl community-list CL-PEER-268127")[1].split("end-list")[0]
    assert [l.strip() for l in corpo.splitlines() if l.strip()] == [
        "64512:1500,", "64512:1501"]


def test_o_quadro_do_parceiro_lista_as_communities_do_cadastro():
    # o parceiro tem o par CL-PEER / APPLY-PEER como o cliente, e o quadro
    # dele sai do mesmo lugar
    texto = render.render_criar_lista(_com_communities(peer_parceiro, ["64512:1500"]))
    corpo = texto.split("xpl community-list CL-PEER-64500")[1].split("end-list")[0]
    assert [l.strip() for l in corpo.splitlines() if l.strip()] == ["64512:1500"]
    assert "xpl route-filter APPLY-PEER-64500" in texto


def test_o_quadro_do_upstream_lista_as_communities_do_cadastro():
    texto = render.render_criar_lista(
        _com_communities(peer_upstream, ["64512:1500"]))
    corpo = texto.split("xpl community-list CL-PEER-14840")[1].split("end-list")[0]
    assert [l.strip() for l in corpo.splitlines() if l.strip()] == ["64512:1500"]


def test_o_quadro_lista_as_large_communities_quando_ha():
    texto = render.render_criar_lista(
        _com_communities(peer_cliente, ["64512:1500"], ["64512:4:264130"]))
    assert "xpl large-community-list LC-PEER-268127" in texto
    corpo = texto.split("xpl large-community-list LC-PEER-268127")[1].split("end-list")[0]
    assert [l.strip() for l in corpo.splitlines() if l.strip()] == ["64512:4:264130"]


def test_o_quadro_omite_a_large_list_quando_ela_esta_vazia():
    # objeto vazio no equipamento e objeto que nao existe, e o undo do bloco
    # de remocao segue o mesmo portao: definir aqui seria criar o que o
    # outro bloco nao derruba
    texto = render.render_criar_lista(_com_communities(peer_cliente, ["64512:1500"]))
    assert "LC-PEER-" not in texto
    assert "apply large-community" not in texto


def test_o_bloco_do_peer_nao_escreve_os_membros_da_lista():
    # a propriedade que a lista guardada no cadastro nao pode perder: colar
    # o bloco do peer de novo nao pode zerar o que esta no equipamento
    for peer_fab, valor in ((peer_cliente, "268127"), (peer_parceiro, "64500"),
                            (peer_upstream, "14840")):
        peer = _com_communities(peer_fab, ["64512:1500"], ["64512:4:264130"])
        texto = render.render_peer(peer)
        assert "xpl community-list CL-PEER-%s" % valor not in texto, valor
        assert "xpl large-community-list LC-PEER-%s" % valor not in texto, valor
        assert "64512:1500" not in texto, valor
        assert "64512:4:264130" not in texto, valor


def test_o_apply_peer_sai_igual_no_bloco_e_no_quadro():
    # os dois blocos definem o mesmo objeto, e o segundo a ser colado
    # sobrescreve o primeiro. Divergir aqui e o filtro mudar de
    # comportamento conforme a ordem da colagem.
    for peer_fab in (peer_cliente, peer_parceiro, peer_upstream):
        peer = _com_communities(peer_fab, ["64512:1500"], ["64512:4:264130"])
        no_bloco = _apply_peer(render.render_peer(peer), peer.token)
        no_quadro = _apply_peer(render.render_criar_lista(peer), peer.token)
        assert no_bloco == no_quadro, peer.tipo


def test_o_apply_peer_so_ganha_a_linha_de_large_com_large_no_cadastro():
    # a linha a mais muda o objeto APPLY-PEER, que e o mesmo nos dois
    # blocos: ela nao pode sair por um cadastro que nao tem large
    sem = _apply_peer(render.render_peer(peer_cliente()), "268127")
    assert "large-community" not in sem
    com = _apply_peer(
        render.render_peer(_com_communities(peer_cliente, [], ["64512:4:1"])),
        "268127")
    assert "apply large-community LC-PEER-268127 additive" in com


def test_o_quadro_do_peer_com_o_cadastro_novo_e_ascii():
    for peer_fab in (peer_cliente, peer_parceiro, peer_upstream):
        peer = _com_communities(peer_fab, ["64512:1500"], ["64512:4:264130"])
        assert render.render_criar_lista(peer).isascii(), peer.tipo


# Task 5: o bloco do grupo. Ao contrario do peer, o grupo nao tem sessao IP
# (nao ha .familias() para derivar): o loop de familia e sempre v4+v6.


from app import peers


def grupo_com_asn(**kw):
    base = dict(
        id=0, nome="UP-REDUNDANTE", tipo="parceiro", asn=64500,
        classe="transito", lp_base=300, origem=1100, pop=2001,
        prefixos={"v4": ["203.0.113.0/24"], "v6": []},
    )
    base.update(kw)
    return peers.Grupo(**base)


def grupo_sem_asn():
    return peers.Grupo(id=1, nome="PARCEIROS_CDN", tipo="parceiro",
                       classe="transito", lp_base=300, origem=1100, pop=2001)


def test_bloco_do_grupo_com_asn_confina_prefixo_e_as_path():
    texto = render.render_grupo(grupo_com_asn())
    assert "group UP-REDUNDANTE external" in texto
    assert "peer UP-REDUNDANTE as-number 64500" in texto
    assert "peer UP-REDUNDANTE public-as-only force" in texto
    assert "xpl ip-prefix-list PL-CUST-UP-REDUNDANTE-V4" in texto
    assert "xpl as-path-list AP-CUST-UP-REDUNDANTE" in texto
    assert "if not ip route-destination in PL-CUST-UP-REDUNDANTE-V4 then" in texto
    assert "if not as-path in AP-CUST-UP-REDUNDANTE then" in texto
    assert "peer UP-REDUNDANTE route-filter CUST-UP-REDUNDANTE-IMPORT-V4 import" in texto
    assert "peer UP-REDUNDANTE route-filter CUST-UP-REDUNDANTE-EXPORT-V4 export" in texto


def test_bloco_do_grupo_sem_asn_nao_confina_e_nega_por_padrao():
    """O grupo sem prefixo proprio nao tem whitelist para confinar, e o import
    dele e o que um membro sem override herda: sem a recusa final, esse membro
    aceitaria qualquer prefixo que passasse pelo sanity e o carimbaria como de
    cliente, que e rota anunciável. Quem precisa de import traz o dele."""
    texto = render.render_grupo(grupo_sem_asn())
    assert "group PARCEIROS_CDN external" in texto
    assert "as-number" not in texto
    assert "peer PARCEIROS_CDN public-as-only force" in texto
    assert "PL-CUST-PARCEIROS_CDN" not in texto
    assert "AP-CUST-PARCEIROS_CDN" not in texto
    assert "apply large-community" not in texto
    assert "peer PARCEIROS_CDN route-filter CUST-PARCEIROS_CDN-IMPORT-V4 import" in texto
    for fam in ("V4", "V6"):
        filtro = texto[texto.index("xpl route-filter CUST-PARCEIROS_CDN-IMPORT-%s" % fam):]
        filtro = filtro[:filtro.index("end-filter")]
        # `refuse` e terminal: nao ha `finish` depois dele
        assert [l.strip() for l in filtro.splitlines() if l.strip()][-1] == "refuse", filtro


def test_bloco_do_grupo_com_default_route_avisa_e_anuncia():
    texto = render.render_grupo(grupo_com_asn(default_route=True))
    assert "default route: o VRP origina 0/0 e ::/0" in texto
    assert "peer UP-REDUNDANTE default-route-advertise" in texto


def test_bloco_do_grupo_sem_default_route_nao_avisa_nem_anuncia():
    texto = render.render_grupo(grupo_com_asn())
    assert "default route: o VRP origina 0/0 e ::/0" not in texto
    assert "default-route-advertise" not in texto


def test_o_bloco_do_grupo_de_downstream_nao_chama_apply_peer():
    # num grupo de cliente ou de parceiro a CL-PEER e por sessao, nao por
    # grupo - ver task 3/spec. O nome diz "de downstream" de proposito: a
    # frase sem o qualificador deixou de valer na task 5, quando o grupo de
    # upstream passou a CHAMAR o APPLY-PEER-<G> (a community de um upstream
    # descreve a rede remota, um objeto so vale para os dois links - ver
    # test_o_grupo_de_upstream_aplica_a_cl_peer)
    texto = render.render_grupo(grupo_com_asn())
    assert "APPLY-PEER" not in texto
    assert "CL-PEER" not in texto


def test_escrever_grupo_grava_no_arquivo_certo(tmp_path):
    # a pasta de saida vem por parametro, e e ela que o mkdir cria: nao ha
    # mais um OUT de modulo para os testes trocarem
    destino = render.escrever_grupo(grupo_com_asn(), saida=tmp_path)
    assert destino == tmp_path / "grupo-UP-REDUNDANTE.txt"
    assert destino.exists()


# Task 5: o bloco do grupo de upstream. O miolo e o mesmo do peer avulso,
# pelas macros de alvo duplo, com duas diferencas: as duas familias saem
# sempre (o grupo nao tem sessao de onde derivar) e o bloco so CHAMA o
# APPLY-PEER - quem define o objeto e o quadro "ao criar o grupo", entao
# reaplicar o bloco nunca mexe na CL-PEER que o operador escreveu.


def grupo_upstream(**kw):
    base = dict(
        id=3, nome="OPERADORA", tipo="upstream", asn=14840,
        lp_base=100, origem=1400, aprendizado=3100,
        te_prefixos={"v4": ["1.1.1.0/24"], "v6": []},
        ap_block=[64500], ap_te=[64501],
        bh_upstream="14840:666", prepend_base=2,
        communities=["14840:9133"], large_communities=["14840:1:3333"],
    )
    base.update(kw)
    return peers.Grupo(**base)


def test_render_do_grupo_de_upstream():
    texto = render.render_grupo(grupo_upstream())
    assert "group OPERADORA external" in texto
    assert "xpl route-filter UP-OPERADORA-IMPORT-V4" in texto
    assert "xpl route-filter UP-OPERADORA-EXPORT-V4" in texto
    # o par PL-TE-PREFER sai dentro do laco de familia, com o sufixo da
    # familia; o resto das listas sai fora dele
    assert "xpl ip-prefix-list PL-TE-PREFER-OPERADORA-V4" in texto
    assert "xpl ipv6-prefix-list PL-TE-PREFER-OPERADORA-V6" not in texto
    assert "xpl community-list CL-5PPA-03" in texto
    assert "xpl as-path-list AP-BLOCK-OPERADORA" in texto


def test_o_grupo_de_upstream_aplica_a_cl_peer():
    # a community de um upstream descreve a rede remota, nao o link: ela
    # mora no grupo e o bloco chama o filtro, igual ao peer avulso
    texto = render.render_grupo(grupo_upstream())
    assert "call route-filter APPLY-PEER-OPERADORA" in texto
    assert "xpl route-filter APPLY-PEER-OPERADORA" not in texto


def test_o_grupo_de_upstream_declara_as_duas_familias():
    # grupo nao tem sessao, entao nao ha peer.familias() para consultar: o
    # template declara as duas sempre, como o de downstream ja faz
    texto = render.render_grupo(grupo_upstream(te_prefixos={"v4": [], "v6": []}))
    assert "ipv4-family unicast" in texto
    assert "ipv6-family unicast" in texto


def test_o_grupo_de_upstream_sem_te_nao_define_a_lista():
    texto = render.render_grupo(grupo_upstream(te_prefixos={"v4": [], "v6": []}))
    assert "PL-TE-PREFER" not in texto


def test_o_grupo_de_upstream_sem_te_nao_deixa_branco_sobrando():
    # o if do template repete a guarda de dentro da macro: sem ele o newline da
    # chamada vira um branco a mais, um depois do cabecalho e outro antes do
    # IMPORT de cada familia. Grupo sem excecao de TE e o caso comum, e o teste
    # da lista acima nao pega isto: com o branco no lugar ele continua passando,
    # porque o branco nao e texto da lista.
    texto = render.render_grupo(grupo_upstream(te_prefixos={"v4": [], "v6": []}))
    assert "aplicado neste equipamento\n\nxpl route-filter UP-OPERADORA-IMPORT-V4\n" in texto
    assert "end-filter\nxpl route-filter UP-OPERADORA-IMPORT-V6\n" in texto
    # a invariante declarada direto, sem depender de o branco sobrar num lugar
    # que as duas assercoes acima alcancem: o branco a mais e exatamente um
    # "\n\n\n" onde deveria haver um "\n\n"
    assert "\n\n\n" not in texto


def test_o_grupo_de_upstream_sem_ap_nao_define_as_listas_de_as_path():
    texto = render.render_grupo(grupo_upstream(ap_block=[], ap_te=[]))
    assert "AP-BLOCK-OPERADORA" not in texto
    assert "AP-TE-PREFER-OPERADORA" not in texto


# Task 6 (multitipo): os blocos do grupo de IX e do grupo de PNI. Mesma forma
# do upstream, sem te_prefix_list e sem apply_peer: nenhum dos dois define a
# CL-PEER nem chama o APPLY-PEER, como plan.TIPOS_COM_APPLY_PEER ja diz.


def grupo_ix(**kw):
    base = dict(
        id=4, nome="IXBR", tipo="ix", asn=26162,
        lp_base=190, origem=1300, aprendizado=3200, ix_id=1234,
        ap_prefer=[264130],
    )
    base.update(kw)
    return peers.Grupo(**base)


def grupo_pni(**kw):
    base = dict(
        id=5, nome="CDN", tipo="pni", asn=264130,
        lp_base=200, origem=1500, ap_allowed=[264130, 64500],
    )
    base.update(kw)
    return peers.Grupo(**base)


def test_render_do_grupo_de_ix():
    texto = render.render_grupo(grupo_ix())
    assert "group IXBR external" in texto
    assert "xpl route-filter IX-IXBR-IMPORT-V4" in texto
    assert "xpl route-filter IX-IXBR-EXPORT-V4" in texto
    assert "xpl as-path-list AP-IX-IXBR" in texto
    # o IX nao tem APPLY-PEER nem 5PPA: o route server repassa o mesmo
    # AS-path a todos os membros
    assert "APPLY-PEER" not in texto
    assert "5PPA" not in texto


def test_a_emenda_de_branco_do_grupo_de_ix():
    # mesma varredura do grupo de upstream, nas duas pontas de fora do laco
    # de familia: um branco entre o cabecalho e o primeiro filtro, nenhum
    # entre o fim de um filtro e a declaracao do seguinte, e o branco entre a
    # ultima lista e o bgp. O caso com ap_prefer e o do teste da guarda
    # abaixo, porque nele a ultima lista e outra
    for g in (grupo_ix(), grupo_ix(ap_prefer=[])):
        texto = render.render_grupo(g)
        assert "aplicado neste equipamento\n\nxpl route-filter IX-IXBR-IMPORT-V4\n" in texto
        assert "end-filter\nxpl route-filter IX-IXBR-IMPORT-V6\n" in texto
        assert " end-list\n\nbgp 64512\n" in texto
        assert "\n\n\n" not in texto, g.ap_prefer


def test_o_grupo_de_ix_sem_ap_prefer_nao_define_a_lista():
    texto = render.render_grupo(grupo_ix(ap_prefer=[]))
    assert "AP-IX-IXBR" not in texto


def test_o_grupo_de_ix_com_ap_prefer_define_a_lista_na_emenda():
    # o teste acima prende so o caso vazio da guarda; falta o outro lado, que
    # e o que a guarda existe para proteger: com ap_prefer a lista sai, e a
    # emenda em volta dela fica inteira. O branco que separa a LC-NOADV da
    # lista nova e o {{ "\n" }} que abre o bloco opcional - o `-` dos tags
    # come o newline da lista de cima -, e a lista termina sem newline
    # proprio, porque quem abre o bgp com uma linha em branco e o template.
    # As duas pontas numa assercao so: o branco no comeco do bloco opcional
    # nao pode virar newline no fim dele
    texto = render.render_grupo(grupo_ix())
    assert (" end-list\n\nxpl as-path-list AP-IX-IXBR\n peer-is '264130'\n"
            " end-list\n\nbgp 64512\n") in texto


def test_render_do_grupo_de_pni():
    texto = render.render_grupo(grupo_pni())
    assert "group CDN external" in texto
    assert "xpl route-filter PNI-CDN-IMPORT-V4" in texto
    assert "xpl route-filter PNI-CDN-EXPORT-V4" in texto
    assert "xpl as-path-list AP-CDN-ALLOWED" in texto
    assert "APPLY-PEER" not in texto


def test_a_emenda_de_branco_do_grupo_de_pni():
    # as mesmas quatro pontas do grupo de IX. O caso vazio entra porque aqui a
    # macro listas_pni nao tem guarda: a lista sai so com o header, e nenhum
    # bloco do arquivo fica sem a emenda por causa disso
    for g in (grupo_pni(), grupo_pni(ap_allowed=[])):
        texto = render.render_grupo(g)
        assert "aplicado neste equipamento\n\nxpl route-filter PNI-CDN-IMPORT-V4\n" in texto
        assert "end-filter\nxpl route-filter PNI-CDN-IMPORT-V6\n" in texto
        assert " end-list\n\nbgp 64512\n" in texto
        assert "\n\n\n" not in texto, g.ap_allowed
        if not g.ap_allowed:
            assert "xpl as-path-list AP-CDN-ALLOWED\n end-list\n" in texto


def test_o_grupo_de_pni_com_allowlist_vazia_ainda_emite_o_header():
    # a macro listas_pni nao tem guarda, igual ao caminho do peer, que chama a
    # mesma macro em pni.txt.j2: o header sai mesmo sem nenhum pass. Quem
    # impede a lista vazia de existir na pratica e a validacao da Task 8, nao
    # o template. O end-list sozinho nao prova isto - o CL-NOADV e o LC-NOADV
    # do mesmo bloco emitem o deles incondicionalmente -, entao quem
    # discrimina e a ausencia de pass
    texto = render.render_grupo(grupo_pni(ap_allowed=[]))
    assert "xpl as-path-list AP-CDN-ALLOWED" in texto
    assert "pass '" not in texto


def test_o_grupo_de_pni_com_allowlist_emite_a_lista_na_emenda():
    # o outro lado do teste acima: com conteudo a lista sai cheia, e a emenda
    # com o filtro de cima e com o CL-NOADV de baixo fica inteira. O branco
    # entre o end-filter e o header da lista e o mesmo da macro do IX - o
    # newline do comentario mais a linha em branco do corpo -, e o de baixo e
    # o newline da chamada no grupo_pni.txt.j2
    texto = render.render_grupo(grupo_pni())
    assert (" end-filter\n\nxpl as-path-list AP-CDN-ALLOWED\n pass '264130',\n"
            " pass '64500'\n end-list\n\nxpl community-list CL-NOADV-CDN\n") in texto


# Task 10 (multitipo): o quadro "ao criar" do grupo. Com `communities` no grupo
# de upstream o grupo virou dono da CL-PEER da rede remota, e o quadro sai uma
# vez para os dois links em vez de uma por membro. IX e PNI continuam sem: o
# egress dos dois nao chama APPLY-PEER.


def test_o_quadro_ao_criar_do_grupo_de_upstream():
    # grupo= nomeado, que e o caminho da producao (a rota do grupo chama
    # render_criar_lista(grupo=grupo)): na posicional o Grupo entra por
    # `peer=` e o template o serve como se fosse peer avulso, com o outro
    # criterio do quadro_ao_criar
    g = grupo_upstream(nome="OPERADORA", id=3,
                       communities=["14840:9133", "14840:9134"])
    texto = render.render_criar_lista(grupo=g)
    assert "xpl community-list CL-PEER-OPERADORA" in texto
    assert " 14840:9133," in texto
    assert " 14840:9134" in texto
    assert "xpl large-community-list LC-PEER-OPERADORA" in texto
    assert "xpl route-filter APPLY-PEER-OPERADORA" in texto


def test_o_quadro_ao_criar_do_grupo_sem_large_community():
    g = grupo_upstream(nome="OPERADORA", id=3, communities=["14840:9133"],
                       large_communities=[])
    assert "LC-PEER" not in render.render_criar_lista(grupo=g)


def test_o_quadro_ao_criar_do_grupo_de_ix_e_de_pni_nao_sai():
    # IX e PNI nao tem APPLY-PEER: o route server repassa o mesmo AS-path a
    # todos os membros, e o egress do PNI nao chama filtro nenhum
    for g in (grupo_ix(nome="IXBR", id=4), grupo_pni(nome="CDN", id=5)):
        assert render.render_criar_lista(grupo=g).strip() == ""


def test_o_quadro_ao_criar_do_grupo_diz_grupo_e_nao_peer():
    # o alvo do quadro e o grupo: o cabecalho nomeia grupo e nao peer, e nao
    # repete o ASN, que ja esta no `group` do VRP. Sem o `alvo` o template le
    # o grupo pelo nome `peer` e o cabecalho sairia mentindo
    texto = render.render_criar_lista(
        grupo=grupo_upstream(nome="OPERADORA", id=3,
                             communities=["14840:9133"]))
    assert "# ao criar o grupo 3 - upstream" in texto
    assert "- AS14840" not in texto
    # e o caminho do peer avulso continua igual ao de antes do alvo duplo
    p = peer_upstream()
    texto_peer = render.render_criar_lista(p)
    assert "# ao criar o peer %s - upstream - AS%s" % (p.id, p.asn) in texto_peer


# Task 6: o bloco do peer membro - enxuto, so referenciando o grupo, com
# override opcional quando o membro tem filtro proprio (prefixo ou CL-PEER).


def peer_membro_sem_override(grupo_id=1):
    return Peer(id=2, nome="EXEMPLO TELECOM", tipo="parceiro", asn=264130,
                grupo_id=grupo_id,
                sessoes={"v4": {"local": "192.0.2.2",
                                "remoto": "192.0.2.3"}, "v6": {}},
                descricao="EXEMPLO TELECOM")


def peer_membro_com_override(grupo_id=1):
    p = peer_membro_sem_override(grupo_id)
    p.prefixos = {"v4": [Bloco(prefixo="198.51.100.0/24")], "v6": []}
    p.classe = "transito"
    p.origem = 1100
    p.pop = 2001
    return p


def test_membro_sem_override_referencia_o_grupo_e_leva_o_export_por_asn():
    """A sessao do membro so referencia o group, e o que ele acrescenta e o
    export com os controles do ASN dele: o grupo sem ASN nao tem como avaliar
    `64512:0:<asn>`, que olha o ASN do destinatario."""
    grupo = grupo_sem_asn()
    texto = render.render_peer(peer_membro_sem_override(grupo.id), grupo=grupo)
    assert "peer 192.0.2.3 as-number 264130" in texto
    assert "peer 192.0.2.3 group PARCEIROS_CDN" in texto
    # sem filtro proprio nao ha import nem prefix-list do membro
    assert "IMPORT" not in texto
    assert "PL-CUST" not in texto
    assert "default-route-advertise" not in texto
    assert "xpl route-filter CUST-264130-EXPORT-V4" in texto
    assert "call route-filter CUST-PARCEIROS_CDN-EXPORT-V4" in texto
    # e a sessao chama o filtro: sem esta linha o membro sem override fica com
    # o export criado e nao aplicado, e o defeito auditado volta em silencio
    assert "peer 192.0.2.3 route-filter CUST-264130-EXPORT-V4 export" in texto


def test_membro_com_asn_no_grupo_nao_repete_as_number():
    grupo = grupo_com_asn()
    membro = peer_membro_sem_override(grupo.id)
    membro.asn = grupo.asn
    texto = render.render_peer(membro, grupo=grupo)
    assert "as-number" not in texto
    assert "peer 192.0.2.3 group UP-REDUNDANTE" in texto


def test_membro_com_override_tem_filtro_proprio_ao_lado_do_grupo():
    grupo = grupo_sem_asn()
    texto = render.render_peer(peer_membro_com_override(grupo.id), grupo=grupo)
    assert "xpl route-filter CUST-264130-IMPORT-V4" in texto
    assert "peer 192.0.2.3 group PARCEIROS_CDN" in texto
    assert "peer 192.0.2.3 route-filter CUST-264130-IMPORT-V4 import" in texto
    # o export do membro e fino: os controles do ASN dele e a chamada do
    # export do grupo, que carrega a politica comum do downstream
    assert "peer 192.0.2.3 route-filter CUST-264130-EXPORT-V4 export" in texto
    assert "call route-filter CUST-PARCEIROS_CDN-EXPORT-V4" in texto


def test_grupo_com_asn_nao_gera_export_por_membro():
    """O grupo com ASN carrega os controles por ASN no proprio export, e o
    validar recusa membro de ASN diferente: o membro nao tem o que
    acrescentar. Os dois juntos prependariam duas vezes."""
    grupo = grupo_com_asn()
    membro = peer_membro_sem_override(grupo.id)
    membro.asn = grupo.asn
    texto = render.render_peer(membro, grupo=grupo)
    assert "CUST-64500-EXPORT" not in texto
    assert "call route-filter" not in texto
    assert "large-community matches-any {64512:0:64500}" in render.render_grupo(grupo)


def test_o_export_do_membro_do_grupo_sem_asn_leva_os_controles_do_asn_dele():
    """`64512:0:<asn>` recusa o anuncio ao ASN e `1/2/3:<asn>` prependa para
    ele. Os dois olham o ASN do destinatario, entao num grupo sem ASN eles so
    existem no filtro do membro: sem ele, o pedido do cliente era ignorado em
    silencio."""
    from app import plan
    grupo = grupo_sem_asn()
    texto = render.render_peer(peer_membro_sem_override(grupo.id), grupo=grupo)
    assert ("if large-community matches-any {%s} then"
            % plan.c_large(0, 264130)) in texto
    for prepends in (1, 2, 3):
        assert ("apply as-path %s %d additive"
                % (plan.ASN, prepends)) in texto


def test_membro_com_asn_em_branco_no_yaml_nao_derruba_o_render():
    """O cadastro editado a mao pode deixar o ASN do membro em branco. Sem a
    guarda, o `c_large(0, None)` estourava no render e levava junto a pagina
    da config inteira; com ela o filtro sai so com a chamada do grupo, que e
    o que o membro herdaria de qualquer jeito."""
    grupo = grupo_sem_asn()
    membro = peer_membro_sem_override(grupo.id)
    membro.asn = None
    texto = render.render_peer(membro, grupo=grupo)
    # o token sai do ASN, entao o nome do objeto carrega o None junto - o
    # cadastro ja estava torto antes de chegar aqui
    assert "xpl route-filter CUST-%s-EXPORT-V4" % membro.token in texto
    assert "large-community matches-any" not in texto
    assert "call route-filter CUST-PARCEIROS_CDN-EXPORT-V4" in texto


def test_a_remocao_do_membro_derruba_o_export_por_asn():
    """O que o bloco do membro cria, o bloco de remocao derruba: o filtro do
    export por ASN sai no undo do grupo sem ASN, e nao sai no grupo com ASN,
    onde ele nunca existiu."""
    sem_asn = render.render_remove(peer_membro_sem_override(1),
                                   grupo=grupo_sem_asn())
    assert "undo xpl route-filter CUST-264130-EXPORT-V4" in sem_asn
    com_asn = render.render_remove(peer_membro_sem_override(0),
                                   grupo=grupo_com_asn())
    assert "CUST-264130-EXPORT" not in com_asn


def test_peer_sem_grupo_continua_igual_a_antes():
    # nenhuma mudanca de comportamento fora de grupo - mesma asserção do
    # golden, so que direto, para nao depender do arquivo golden aqui
    texto_com_none = render.render_peer(peer_cliente())
    texto_com_grupo_none = render.render_peer(peer_cliente(), grupo=None)
    assert texto_com_none == texto_com_grupo_none


def grupo_cliente_sem_asn():
    return peers.Grupo(id=3, nome="CLIENTES_REDUNDANTES", tipo="cliente",
                       classe="transito", lp_base=300, origem=1100, pop=2001)


def test_membro_cliente_nao_perde_o_route_limit():
    # route-limit e da sessao: a spec o deixa no Peer mesmo dentro de um
    # grupo, e o PLANO o exige em toda sessao, sem excecao, inclusive
    # cliente pequeno. O bloco enxuto do membro nao pode sumir com ele.
    grupo = grupo_cliente_sem_asn()
    membro = peer_membro_sem_override(grupo.id)
    membro.tipo = "cliente"
    membro.route_limit = 50
    texto = render.render_peer(membro, grupo=grupo)
    assert "peer 192.0.2.3 route-limit 50 alert-only" in texto


# Task 7 (grupos multitipo): o membro de grupo nos tres tipos novos. O ramo
# {% if grupo %} dos templates de upstream, ix e pni espelha o do cliente:
# quem carrega a politica de sessao e o arquivo do grupo, e o membro so
# referencia o group. Aqui mora tambem a volta do route-limit ao membro
# parceiro: o ramo de membro do cliente.txt.j2 condicionava a linha a
# "cliente", e o plano deixa o route_limit no Peer mesmo dentro de um grupo -
# um membro parceiro saia sem limite nenhum.


def test_membro_de_grupo_de_upstream_herda_a_politica():
    # o membro so referencia o group: quem carrega AS_ONLY, timers, bfd e
    # advertise-community e o arquivo do grupo, uma vez so. Os campos de
    # ap/te, o prepend base e o bh do upstream saem vazios porque o membro
    # sem politica propria e o caso deste teste: preenchidos, ele passa a ter
    # ramo proprio e nao herda nada.
    p = peer_upstream(te_prefixos={"v4": [], "v6": []}, ap_block=[], ap_te=[],
                      prepend_base=0, bh_upstream="")
    g = grupo_upstream(nome="OPERADORA", id=3)
    texto = render.render_peer(p, grupo=g)
    assert " peer 203.0.113.1 group OPERADORA" in texto
    assert "ipv4-family unicast" in texto
    # o membro NAO reemite os knobs de sessao
    for cmd in ("public-as-only force", "capability-advertise graceful-restart",
                "bfd enable", "timer keepalive"):
        assert cmd not in texto, cmd
    # nem refaz os filtros do grupo
    assert "xpl route-filter UP-" not in texto
    assert "\n\n\n" not in texto


def test_membro_com_so_excecao_de_te_tem_filtro_proprio():
    # o override e so de TE: sem prefixo de cliente e sem CL-PEER. As macros
    # do membro leem te_prefixos/ap_te (filtro_upstream_import) e ap_block
    # (listas_upstream), entao um membro assim precisa do ramo proprio - sem
    # ele a excecao de TE era jogada fora em silencio e o membro herdava a
    # politica inteira do grupo.
    p = peer_upstream(te_prefixos={"v4": ["198.51.100.0/24"], "v6": []},
                      ap_block=[], ap_te=[],
                      prepend_base=0, bh_upstream="")
    g = grupo_upstream(nome="OPERADORA", id=3)
    texto = render.render_peer(p, grupo=g)
    assert "xpl route-filter UP-14840-IMPORT-V4" in texto


def test_membro_com_so_prepend_base_tem_filtro_proprio():
    # o override e so o prepend base de engenharia. Quem o le e o filtro de
    # export do membro (passo 8 da macro), entao o membro precisa do ramo
    # proprio pelo mesmo motivo do TE. O 4 nao aparece no passo 6 (que so
    # escreve 1, 2 ou 3), entao a linha so pode vir do prepend base.
    p = peer_upstream(te_prefixos={"v4": [], "v6": []}, ap_block=[], ap_te=[],
                      prepend_base=4, bh_upstream="")
    g = grupo_upstream(nome="OPERADORA", id=3)
    texto = render.render_peer(p, grupo=g)
    assert "xpl route-filter UP-14840-EXPORT-V4" in texto
    assert "apply as-path 64512 4 additive" in texto


def test_membro_com_so_bh_upstream_tem_filtro_proprio():
    # o override e so a community de blackhole do upstream. Quem a le e o
    # ramo do blackhole do filtro de export do membro (passo 1 da macro),
    # entao vale o mesmo motivo do prepend base: sem o ramo proprio o membro
    # herdava a politica do grupo e a community do campo ia embora junto.
    # A varredura e sobre o XPL: o comentario do passo 1 cita a operacao.
    p = peer_upstream(te_prefixos={"v4": [], "v6": []}, ap_block=[], ap_te=[],
                      prepend_base=0, bh_upstream="64500:666")
    g = grupo_upstream(nome="OPERADORA", id=3)
    texto = render.render_peer(p, grupo=g)
    assert "xpl route-filter UP-14840-EXPORT-V4" in texto
    export = texto.split("xpl route-filter UP-14840-EXPORT-V4")[1].split("end-filter")[0]
    codigo = "\n".join(l for l in export.splitlines() if not l.strip().startswith("!-"))
    assert "apply community {64500:666} overwrite" in codigo


def test_membro_de_grupo_de_upstream_emite_o_route_limit():
    p = peer_upstream(te_prefixos={"v4": [], "v6": []}, ap_block=[], ap_te=[],
                      prepend_base=0, bh_upstream="")
    g = grupo_upstream(nome="OPERADORA", id=3)
    texto = render.render_peer(p, grupo=g)
    assert " peer 203.0.113.1 route-limit 1500000 alert-only" in texto
    assert "\n\n\n" not in texto


def test_membro_parceiro_emite_o_route_limit():
    # o ramo de membro do cliente.txt.j2 emitia o limite so para "cliente",
    # entao um membro parceiro saia sem limite nenhum. O limite e da sessao,
    # nao do grupo, e o avulso ja o traz pelo sessao_do_peer (golden do
    # parceiro): o membro nao pode ser o unico a perder a linha.
    texto = render.render_peer(peer_parceiro(), grupo=grupo_sem_asn())
    assert "route-limit 50 alert-only" in texto
    assert "\n\n\n" not in texto


def test_membro_de_grupo_de_ix_referencia_o_group():
    # ap_prefer vazio: sem ele o membro tem filtro proprio e o teste da
    # heranca deixaria de testar a heranca (ver o predicado da T8)
    p = peer_ix(ap_prefer=[])
    g = grupo_ix(nome="IXBR", id=4)
    texto = render.render_peer(p, grupo=g)
    assert " peer 187.16.192.2 group IXBR" in texto
    assert "xpl route-filter IX-" not in texto
    assert "\n\n\n" not in texto


def test_membro_de_grupo_de_pni_referencia_o_group():
    # ap_allowed vazio pelo mesmo motivo do ix: e a allowlist do grupo que
    # vale, e um valor aqui da ao membro um ramo proprio
    p = peer_pni(ap_allowed=[])
    g = grupo_pni(nome="CDN", id=5)
    texto = render.render_peer(p, grupo=g)
    assert " peer 10.0.0.2 group CDN" in texto
    assert "xpl route-filter PNI-" not in texto
    assert "\n\n\n" not in texto


def test_membro_sem_asn_do_grupo_declara_o_proprio():
    # o as-number do membro so sai quando o grupo nao tem o dele, como no
    # ramo de downstream
    p = peer_upstream(te_prefixos={"v4": [], "v6": []}, ap_block=[], ap_te=[],
                      prepend_base=0, bh_upstream="")
    com_asn = render.render_peer(p, grupo=grupo_upstream(nome="X", id=3, asn=14840))
    sem_asn = render.render_peer(p, grupo=grupo_upstream(nome="X", id=3, asn=None))
    assert "as-number 14840" not in com_asn
    assert "as-number 14840" in sem_asn
    assert "\n\n\n" not in com_asn
    assert "\n\n\n" not in sem_asn


def test_a_remocao_do_membro_de_upstream_nao_derruba_o_bloco_do_grupo():
    # o membro sem filtro proprio nao tem objeto nenhum para derrubar alem
    # da sessao
    p = peer_upstream(te_prefixos={"v4": [], "v6": []}, ap_block=[], ap_te=[],
                      prepend_base=0, bh_upstream="")
    g = grupo_upstream(nome="OPERADORA", id=3)
    texto = render.render_remove(p, grupo=g)
    assert "undo xpl route-filter UP-" not in texto
    assert "undo xpl community-list CL-NOADV-" not in texto
    assert "undo peer 203.0.113.1" in texto
    assert "\n\n\n" not in texto


def test_a_remocao_do_membro_de_upstream_com_filtro_proprio_derruba_o_dele():
    p = peer_upstream(communities=["14840:9133"])
    g = grupo_upstream(nome="OPERADORA", id=3)
    texto = render.render_remove(p, grupo=g)
    assert "undo xpl route-filter UP-14840-IMPORT-V4" in texto
    assert "\n\n\n" not in texto


# Fix final (secao C): o quadro "ao criar" so sai no grupo de upstream. O
# bloco do grupo de cliente e de parceiro nao define nem chama APPLY-PEER
# nenhum - a CL-PEER deles e por membro -, entao o quadro criava uma
# CL-PEER-<G> e um APPLY-PEER-<G> que filtro nenhum do grupo chama.


def test_o_quadro_ao_criar_do_grupo_de_downstream_nao_sai():
    # o alvo grupo tem criterio proprio, e nao o TIPOS_COM_APPLY_PEER do
    # peer avulso: quem define APPLY-PEER-<G> e o export do grupo de
    # upstream, e so ele
    for g in (grupo_com_asn(nome="PARCEIROS_CDN", id=2),
              grupo_cliente_sem_asn()):
        assert render.render_criar_lista(grupo=g).strip() == "", g.tipo


def test_o_bloco_do_grupo_de_downstream_nao_tem_apply_peer_nem_cl_peer():
    # e o orfao nao e so o quadro: o bloco do grupo tambem nao tem o objeto
    # que o quadro preencheria
    for g in (grupo_com_asn(nome="PARCEIROS_CDN", id=2),
              grupo_cliente_sem_asn()):
        texto = render.render_grupo(g)
        assert "APPLY-PEER" not in texto, g.tipo
        assert "CL-PEER" not in texto, g.tipo


def test_o_grupo_de_upstream_continua_saindo_com_o_quadro():
    # controle do caminho de producao, que e o nomeado: o app chama
    # render_criar_lista(grupo=grupo), e nao a posicional
    g = grupo_upstream(nome="OPERADORA", id=3, communities=["14840:9133"])
    assert "xpl route-filter APPLY-PEER-OPERADORA" in render.render_criar_lista(
        grupo=g)


# F5 da revisao final: a propriedade que a revisao conferiu a mao virou teste
# - todo `call route-filter` de um texto gerado tem a definicao daquele filtro
# em algum texto gerado. Ela e entre textos, nao dentro de um: o bloco do
# alvo chama o IMPORT-SANITY-V4 que mora no bloco base, e o export do grupo de
# upstream chama o APPLY-PEER-<G> que mora no quadro "ao criar o grupo". As
# duas pontas saem ancoradas no comeco da linha, senao o bloco de remocao
# entra na conta pelo avesso (ele traz `undo xpl route-filter <nome>`, que e o
# contrario de definir) e os comentarios do _macros.j2 entram por citar nomes
# de filtro sem definir nada.

CHAMADA_DE_FILTRO = re.compile(r"^\s*call route-filter (\S+)\s*$", re.M)
DEFINICAO_DE_FILTRO = re.compile(r"^\s*xpl route-filter (\S+)\s*$", re.M)


def _membro_sem_filtro(p):
    # o membro puro: o tem_filtro_proprio() da False, entao o bloco dele so
    # referencia o grupo. Zera o que o predicado conta, um por um, para o
    # teste nao depender dos defaults da fabrica de cada tipo - da fabrica do
    # upstream, por exemplo, vem te_prefixos, ap_block, ap_te, prepend_base e
    # bh_upstream, e qualquer um deles sozinho ja da ramo proprio ao membro
    p.prefixos = {"v4": [], "v6": []}
    p.te_prefixos = {"v4": [], "v6": []}
    p.communities = []
    p.large_communities = []
    p.ap_block = []
    p.ap_te = []
    p.ap_allowed = []
    p.ap_prefer = []
    p.prepend_base = 0
    p.bh_upstream = ""
    assert not p.tem_filtro_proprio(), p.tipo
    return p


def _textos_gerados():
    """(os blocos que o app escreve, os grupos que eles usam), por nome.

    Os alvos sao os cinco tipos, em duas formas: o avulso e o membro de
    grupo (o segundo com e sem filtro proprio), cada um com o proprio bloco,
    com o que a remocao derruba e com o quadro "ao criar". Os grupos passam
    pelo mesmo render_grupo - o de parceiro pelo template do cliente, como no
    TEMPLATE_POR_TIPO_GRUPO -, e o de upstream esta la porque e o unico cujo
    bloco chama o filtro do grupo.
    """
    grupos = {
        "cliente": grupo_cliente_sem_asn(),
        "parceiro": grupo_sem_asn(),
        "upstream": grupo_upstream(nome="GUPSTREAM", id=3),
        "ix": grupo_ix(nome="GIX", id=4),
        "pni": grupo_pni(nome="GPNI", id=5),
    }
    fabrica = {"cliente": peer_cliente, "parceiro": peer_parceiro,
               "upstream": peer_upstream, "ix": peer_ix, "pni": peer_pni}
    textos = [("base", render.render_base())]
    for tipo, g in grupos.items():
        textos.append(("grupo-%s" % tipo, render.render_grupo(g)))
        textos.append(("quadro-do-grupo-%s" % tipo,
                       render.render_criar_lista(grupo=g)))
        avulso = fabrica[tipo]()
        membro = _membro_sem_filtro(fabrica[tipo](grupo_id=g.id))
        # o membro que traz filtro proprio: e o ramo de override do mesmo
        # template, aquele que o operador preenche sem sair do membro
        membro_com_filtro = fabrica[tipo](
            grupo_id=g.id, prefixos={"v4": ["198.51.100.0/24"], "v6": []})
        # o avulso e o caso em que o template nao recebe grupo nenhum: o
        # bloco dele e quem carrega a politica toda, sem group de quem
        # herdar. No membro o bloco enxuto referencia o group, e o ramo
        # proprio, quando ha um, sai ao lado dele
        for nome, p, grupo_do_bloco in (
                ("avulso", avulso, None),
                ("membro", membro, g),
                ("membro-com-filtro", membro_com_filtro, g)):
            textos.append(("%s-%s" % (nome, tipo),
                           render.render_peer(p, grupo=grupo_do_bloco)))
            textos.append(("remocao-do-%s-%s" % (nome, tipo),
                           render.render_remove(p, grupo=grupo_do_bloco)))
            textos.append(("quadro-do-%s-%s" % (nome, tipo),
                           render.render_criar_lista(p)))
    return textos, grupos


def test_todo_call_route_filter_tem_a_definicao_em_algum_texto_gerado():
    textos, grupos = _textos_gerados()
    # a ancora esta fazendo trabalho, e nao so decorando a regex: o bloco de
    # remocao nomeia filtro em `undo xpl route-filter <nome>` - o contrario
    # de definir - e a contagem ancorada nao pega nenhum deles
    remocoes = [texto for nome, texto in textos
                if nome.startswith("remocao-do-")]
    assert any("undo xpl route-filter" in texto for texto in remocoes)
    for texto in remocoes:
        assert DEFINICAO_DE_FILTRO.findall(texto) == []
    chamadas, definicoes = set(), set()
    sem_definicao_aqui = {}
    for nome, texto in textos:
        chamadas_daqui = set(CHAMADA_DE_FILTRO.findall(texto))
        definicoes_daqui = set(DEFINICAO_DE_FILTRO.findall(texto))
        chamadas |= chamadas_daqui
        definicoes |= definicoes_daqui
        if chamadas_daqui - definicoes_daqui:
            sem_definicao_aqui[nome] = chamadas_daqui - definicoes_daqui
    # a propriedade declarada: nenhum texto chama o que texto nenhum define.
    # Se um template novo chamar um filtro que ninguem define, e aqui que cai,
    # e a mensagem nomeia o filtro
    orfas = chamadas - definicoes
    assert orfas == set(), sorted(orfas)
    # e o conjunto local e declarado, nao o que o momento atual mostra: as
    # quatro do reuso moram no bloco base (templates/base.txt.j2) e o
    # APPLY-PEER-<G> quem define e o quadro "ao criar o grupo", que so sai
    # com CL-PEER no cadastro do grupo. Qualquer outro nome aqui e um typo ou
    # um bloco que perdeu a definicao pelo caminho
    esperado = {"IMPORT-SANITY-V4", "IMPORT-SANITY-V6", "EXPORT-SANITY",
                "APPLY-CUSTOMER-LP",
                # o anti-leak do prefixo proprio mora no base e e chamado
                # pelos imports externos, como o IMPORT-SANITY
                "REJEITA-BLOCO-PROPRIO-V4", "REJEITA-BLOCO-PROPRIO-V6",
                "APPLY-PEER-%s" % grupos["upstream"].token,
                # o export do membro de grupo de downstream sem ASN chama o
                # export do grupo, que mora no bloco do grupo - o mesmo caso
                # do APPLY-PEER-<G> do upstream, um texto adiante
                "CUST-%s-EXPORT-V4" % grupos["cliente"].token,
                "CUST-%s-EXPORT-V4" % grupos["parceiro"].token}
    fora_do_esperado = set().union(*sem_definicao_aqui.values())
    assert fora_do_esperado == esperado, sorted(fora_do_esperado ^ esperado)


# ---------------------------------------------------------------------
# O ASN declarado no peers.yaml
#
# O que os testes de golden acima travam e a outra metade: com o Rede de
# fabrica, a config sai igual a de antes. Estes aqui travam a troca, e sao
# os dois lados que fazem a mudanca ser de fato opcional.
# ---------------------------------------------------------------------

from app import plan


def test_o_bloco_base_de_fabrica_e_o_da_classe_rede():
    # sem argumento e com o Rede de fabrica o mesmo texto: quem nao tem a
    # chave no peers.yaml nao ve diferenca nenhuma
    assert render.render_base() == render.render_base(rede=plan.Rede())


def test_o_bloco_base_segue_o_namespace_do_asn_declarado():
    texto = render.render_base(rede=plan.Rede(asn=64500))
    # 64512 sem dois pontos aparece no texto de qualquer jeito: e o comeco
    # da faixa privada de AP-BOGON-ASN, que e do desenho e nao do namespace.
    # O que nao pode sobrar e o namespace de fabrica carimbando community
    assert "64512:" not in texto
    assert "64500:666" in texto
    assert "64500:*" in texto
    assert render.render_base(rede=plan.Rede(asn=64500)).isascii()


def test_o_bloco_do_peer_segue_o_asn_declarado():
    texto = render.render_peer(peer_cliente(), rede=plan.Rede(asn=64500))
    assert "64512" not in texto
    assert "bgp 64500" in texto
    # o as-number da sessao e o ASN do cliente e nao o da rede: o Rede
    # desloca o namespace do plano, nao o que e do outro lado do cabo
    assert "268127" in texto


def test_o_prepend_usa_o_asn_e_nao_o_namespace():
    # num ASN de 16 bits os dois coincidem; num de 32 nao, e o as-path
    # carrega o ASN de verdade. A verificacao no rt-exemplo-ne8k mostrou
    # que este VRP aceita o inteiro de 32 bits em asplain
    texto = render.render_peer(peer_cliente(), rede=plan.Rede(asn=264130, politica=64500))
    assert "apply as-path 264130 3 additive" in texto


def test_o_asn_de_32_bits_escreve_o_namespace_nas_communities():
    texto = render.render_peer(peer_cliente(), rede=plan.Rede(asn=264130, politica=64500))
    assert "64512" not in texto
    assert "64500:1900" in texto
    assert "bgp 264130" in texto


def test_o_bloco_do_grupo_segue_o_asn_declarado():
    grupo = grupo_upstream(nome="GUPSTREAM", id=3)
    texto = render.render_grupo(grupo, rede=plan.Rede(asn=64500))
    assert "64512" not in texto
    assert "bgp 64500" in texto


def bloco(prefixo, communities=None):
    return Bloco(prefixo=prefixo, communities=list(communities or []))


def dois_blocos():
    return {"v4": [bloco("38.252.64.0/22", ["64512:613", "64512:621",
                                            "15169:12100"]),
                   bloco("38.252.64.0/24", ["64512:211"])],
            "v6": [bloco("2804:36b4::/32")]}


def test_blocos_e_ascii():
    assert render.render_blocos(dois_blocos()).isascii()


def test_a_estatica_ancora_com_preference_250():
    texto = render.render_blocos(dois_blocos())
    assert ("ip route-static 38.252.64.0 255.255.252.0 NULL0 "
            "preference 250") in texto
    assert "ipv6 route-static 2804:36b4:: 32 NULL0 preference 250" in texto


def test_o_filtro_leva_o_lp_e_o_1000_gerado():
    texto = render.render_blocos(dois_blocos())
    assert "xpl route-filter ORIGEM-38-252-64-0_22" in texto
    assert " apply local-preference 900" in texto
    assert (" apply community {64512:1000, 64512:613, 64512:621, "
            "15169:12100} overwrite") in texto


def test_a_comunidade_de_outro_as_viaja_com_a_lista():
    assert "15169:12100" in render.render_blocos(dois_blocos())


def test_lista_vazia_sai_com_o_1000_e_sem_large():
    texto = render.render_blocos({"v4": [bloco("38.252.64.0/22")], "v6": []})
    assert " apply community {64512:1000} overwrite" in texto
    assert "apply large-community" not in texto


def test_a_large_sai_em_linha_propria():
    texto = render.render_blocos(
        {"v4": [bloco("38.252.64.0/22", ["64512:613", "64512:0:14840"])],
         "v6": []})
    assert " apply community {64512:1000, 64512:613} overwrite" in texto
    assert " apply large-community {64512:0:14840} overwrite" in texto


def test_o_filtro_fecha_em_break():
    texto = render.render_blocos(dois_blocos())
    corpo = texto.split("xpl route-filter ORIGEM-38-252-64-0_22")[1].split(
        "end-filter")[0]
    assert corpo.strip().endswith("break")
    assert "finish" not in corpo


def test_as_linhas_network_vao_no_fim_de_cada_familia():
    texto = render.render_blocos(dois_blocos())
    assert (" network 38.252.64.0 255.255.252.0 route-filter "
            "ORIGEM-38-252-64-0_22") in texto
    assert (" network 38.252.64.0 255.255.255.0 route-filter "
            "ORIGEM-38-252-64-0_24") in texto
    assert " network 2804:36b4:: 32 route-filter ORIGEM-2804-36b4_32" in texto


def test_sem_bloco_nao_sai_estatica_nem_filtro():
    """A varredura e pelos comandos, e nao pelas palavras: o cabecalho do
    arquivo cita "network" na frase que diz onde as linhas dele vao."""
    texto = render.render_blocos({"v4": [], "v6": []})
    assert "ip route-static" not in texto
    assert "ipv6 route-static" not in texto
    assert "xpl route-filter ORIGEM-" not in texto
    assert " route-filter ORIGEM-" not in texto


def test_o_bloco_traz_a_estatica_o_filtro_e_o_network_do_mesmo_prefixo():
    texto = render.render_blocos({"v4": [bloco("38.252.64.0/24")], "v6": []})
    for pedaco in ("ip route-static 38.252.64.0 255.255.255.0 NULL0",
                   "xpl route-filter ORIGEM-38-252-64-0_24",
                   "network 38.252.64.0 255.255.255.0 route-filter "
                   "ORIGEM-38-252-64-0_24"):
        assert pedaco in texto, pedaco


def test_o_bloco_do_asn_declarado_usa_o_namespace_dele():
    texto = render.render_blocos({"v4": [bloco("38.252.64.0/22")], "v6": []},
                                 rede=plan.Rede(asn=264130, politica=65532))
    assert "65532:1000" in texto
    assert "64512:1000" not in texto


def test_escrever_blocos_grava_em_out(tmp_path):
    destino = render.escrever_blocos(dois_blocos(), saida=tmp_path)
    assert destino == tmp_path / "blocos.txt"
    assert destino.read_text(encoding="ascii") == render.render_blocos(
        dois_blocos())


def test_remover_traz_o_undo_na_ordem_que_o_vrp_aceita():
    """O `undo network` vem antes do `undo xpl route-filter`: objeto em uso
    nao e apagavel, e a referencia sai primeiro."""
    texto = render.render_remove_blocos({"v4": [bloco("38.252.64.0/22")],
                                         "v6": []})
    ordem = [texto.index("undo network 38.252.64.0 255.255.252.0"),
             texto.index("undo xpl route-filter ORIGEM-38-252-64-0_22"),
             texto.index("undo ip route-static 38.252.64.0 255.255.252.0")]
    assert ordem == sorted(ordem)


def test_remover_avisa_que_o_caminho_de_tirar_so_o_tratamento_e_outro():
    texto = render.render_remove_blocos({"v4": [bloco("38.252.64.0/22")],
                                         "v6": []})
    assert "esvazie" in texto.lower()


def test_remover_do_v6_usa_os_comandos_de_v6():
    texto = render.render_remove_blocos({"v4": [],
                                         "v6": [bloco("2804:36b4::/32")]})
    assert "undo network 2804:36b4:: 32" in texto
    assert "undo ipv6 route-static 2804:36b4:: 32 NULL0" in texto


def test_remover_sem_bloco_nao_traz_undo():
    assert "undo " not in render.render_remove_blocos({"v4": [], "v6": []})


def test_golden_dos_blocos():
    """A saida exata dos dois templates que se colam no roteador sem
    golden. As assercoes de substring acima nao veem o branco entre as
    secoes de familia nem dois filtros colados: so a igualdade ve."""
    assert render.render_blocos(dois_blocos()) == (
        GOLDEN / "blocos.txt").read_text(encoding="ascii")


def test_golden_da_remocao_dos_blocos():
    assert render.render_remove_blocos(dois_blocos()) == (
        GOLDEN / "remover_blocos.txt").read_text(encoding="ascii")


def test_nenhum_bloco_redistribui_rota_local():
    """O invariante de que a dispensa da marca depende: nao haver
    `import-route` nem `aggregate` em bloco nenhum.

    A dispensa do EXPORT-SANITY vale para tudo que a redistribuicao
    colocar na RIB: qualquer um dos dois poem uma rota local com path
    vazio e sem marca de origem, e ela passa a ser anunciavel em todo
    lugar, sem LP 900, sem escopo e sem prepend, em silencio. A varredura
    e sobre os quatro blocos, e nao so o base: e o bloco do peer que
    quebraria no dia de uma redistribuicao.
    """
    textos = {
        "o bloco base": render.render_base(),
        "o bloco do peer": render.render_peer(peer_cliente()),
        "o bloco do grupo": render.render_grupo(grupo_upstream()),
        "o bloco dos prefixos proprios": render.render_blocos(dois_blocos()),
    }
    for nome, texto in textos.items():
        for linha in texto.splitlines():
            assert not re.match(r"\s*(import-route|aggregate)\b", linha), (
                nome, linha)



def test_nenhum_filtro_usa_matches_any_em_as_path():
    """O operador de as-path e o `in`; `matches-any` nao existe nessa clausula.

    `community` e `large-community` tem o `matches-any`, e e dai que vem a
    confusao: o que o equipamento recusa e so a clausula de as-path. Ela
    sobreviveu em tres filtros quando o resto migrou para o `in`, os dois do
    upstream (AP-BLOCK e AP-TE-PREFER) e o do cliente (AP-CUST).

    O caso varre os cinco tipos e os dois alvos porque a clausula mora em
    macro compartilhada: conferir um tipo so deixaria os outros passarem.
    """
    do_tipo = {"cliente": peer_cliente, "parceiro": peer_parceiro,
               "upstream": peer_upstream, "ix": peer_ix, "pni": peer_pni}
    for tipo, monta in do_tipo.items():
        for alvo, renderiza in ((monta(), render.render_peer),
                                (grupo_do_tipo(tipo), render.render_grupo)):
            linhas = [l for l in renderiza(alvo).splitlines()
                      if "as-path matches-any" in l]
            assert not linhas, (tipo, linhas)


# --- a preferencia dos blocos do proprio upstream ----------------------
#
# O peer anuncia os blocos dele, e a rota que vem por ele mesmo e o melhor
# caminho para esses prefixos. A clausula marca isso com local-preference,
# para que a rota nao perca para um caminho mais longo aprendido alhures.


def test_o_upstream_prefere_os_blocos_dele_mesmo():
    """`origin` e nao `pass`: a pergunta e quem originou o prefixo.

    O peer pode prependar o proprio bloco, e o path sai "14840 14840": um
    `pass` deixaria de casar justamente na rota prependada, e a preferencia
    sumiria sem aviso. `origin` olha o ultimo AS do path e sobrevive ao
    prepend. E a mesma escolha, pelo mesmo motivo, do AP-CUST.
    """
    texto = render.render_peer(peer_upstream())
    assert "xpl as-path-list AP-OWN-14840" in texto
    assert " origin '14840'" in texto

    import_ = texto.split("xpl route-filter UP-14840-IMPORT-V4")[1].split("end-filter")[0]
    assert "if as-path in AP-OWN-14840 then" in import_
    assert "apply local-preference 500" in import_


def test_a_preferencia_do_bloco_vence_a_excecao_de_te():
    """A ordem das duas clausulas e a regra, e nao um detalhe de leitura.

    As duas escrevem local-preference no import, e a ultima vence. A lista
    de excecao de TE e de prefixos alcancados melhor pela borda do
    upstream, que e onde os blocos dele costumam estar: com a clausula nova
    antes, o 250 do TE passaria por cima do 500 nos prefixos que ela existe
    para marcar, e a preferencia nao apareceria em lugar nenhum.
    """
    import_ = (render.render_peer(peer_upstream())
               .split("xpl route-filter UP-14840-IMPORT-V4")[1]
               .split("end-filter")[0])
    assert import_.index("apply local-preference 500") > import_.index(
        "apply local-preference 250")


def test_so_o_upstream_ganha_a_preferencia_do_bloco_do_peer():
    # a sessao de cliente anuncia os prefixos que ele comprou, e nao tem
    # "bloco proprio" para preferir: a lista e a clausula sao do upstream
    for monta in (peer_cliente, peer_parceiro, peer_ix, peer_pni):
        texto = render.render_peer(monta())
        assert "AP-OWN" not in texto, monta.__name__


# --- o peer que reaproveita a politica de outro ------------------------


def par_de_reaproveitamento(**kw):
    """O par principal/backup: o segundo reaproveita a politica do primeiro."""
    # o apelido da origem e o que da o token dela, e e com esse token que o
    # bloco de quem reaproveita nomeia os filtros que chama: sem ele o token
    # seria o ASN, e o par de nomes que o teste procura nao existiria
    origem = peer_cliente(id=1, asn=270620, apelido="NETMAC", nome="NETMAC",
                          descricao="NETMAC")
    backup = peer_cliente(
        id=2, asn=270620, apelido="NETMAC-BKP", nome="NETMAC-BKP",
        descricao="NETMAC-BKP", politica_de=1,
        sessoes={"v4": {"local": "198.51.100.9", "remoto": "198.51.100.10"},
                 "v6": {}},
        **kw)
    return origem, backup


def test_o_bloco_de_quem_reaproveita_nao_define_objeto_nenhum():
    # a razao de existir do recurso: dois links do mesmo cliente sem a
    # politica escrita duas vezes
    origem, backup = par_de_reaproveitamento()
    texto = render.render_peer(backup, origem=origem)
    assert "xpl " not in texto


def test_o_bloco_de_quem_reaproveita_chama_os_filtros_da_origem():
    origem, backup = par_de_reaproveitamento()
    texto = render.render_peer(backup, origem=origem)
    assert ("peer 198.51.100.10 route-filter CUST-NETMAC-IMPORT-V4 import"
            in texto)
    assert ("peer 198.51.100.10 route-filter CUST-NETMAC-EXPORT-V4 export"
            in texto)
    # o token de quem reaproveita aparece no comentario de cabecalho, que e o
    # nome do registro; o que nao pode e ele nomear filtro nenhum
    assert "CUST-NETMAC-BKP" not in texto


def test_o_bloco_de_quem_reaproveita_traz_a_sessao_dele():
    # nao ha grupo do VRP carregando a sessao: timers, bfd, route-limit e
    # advertise-community sao deste link, com os valores dele
    _, backup = par_de_reaproveitamento(
        route_limit=99, timer_keepalive=30, timer_hold=90, bfd=True)
    texto = render.render_peer(backup, origem=par_de_reaproveitamento()[0])
    assert "peer 198.51.100.10 route-limit 99 alert-only" in texto
    assert "peer 198.51.100.10 timer keepalive 30 hold 90" in texto
    assert "peer 198.51.100.10 bfd enable" in texto
    assert "peer 198.51.100.10 advertise-community" in texto


def test_golden_de_quem_reaproveita():
    """O caso cliente inteiro, arquivo a arquivo.

    O bloco de quem reaproveita e curto, e o que ele tem e o que ele nao tem
    sao a mesma coisa vista de dois lados: a sessao deste link, com os
    valores dele, e os filtros da origem chamados pelo token dela. O golden
    prende as duas coisas de uma vez, inclusive o branco entre elas.
    """
    origem, backup = par_de_reaproveitamento()
    assert render.render_peer(backup, origem=origem) == (
        GOLDEN / "cliente-reaproveita.txt").read_text(encoding="ascii")


def test_o_filtro_sai_com_o_prefixo_do_tipo():
    # o prefixo do nome do filtro e do tipo, e nao do token: um upstream que
    # reaproveita chama UP-, e nao CUST-
    origem = peer_upstream(id=1, asn=14840, apelido="OP", descricao="OP")
    outro = peer_upstream(id=2, asn=14840, apelido="OP-BKP", nome="OP-BKP",
                          descricao="OP-BKP", politica_de=1)
    texto = render.render_peer(outro, origem=origem)
    assert "route-filter UP-OP-IMPORT-V4 import" in texto
    assert "CUST-" not in texto


def test_o_campo_de_politica_de_quem_reaproveita_e_ignorado():
    # a tela mostra os campos e o operador pode digitar neles. O que vale e
    # a origem, e o render nao pode consultar nenhum deles
    origem, backup = par_de_reaproveitamento(
        lp_base=999, origem=1999, pop=2222, prepend_base=3, bh_upstream="1:666",
        communities=["64512:1900"], ap_block=["65000"])
    texto = render.render_peer(backup, origem=origem)
    assert "999" not in texto
    assert "64512:1900" not in texto
    assert "65000" not in texto
    assert "xpl " not in texto


def test_gerar_quem_reaproveita_nao_muda_a_saida_da_origem():
    # o requisito de sempre: gerar um nao mexe na saida do outro
    origem, backup = par_de_reaproveitamento()
    antes = render.render_peer(origem)
    render.render_peer(backup, origem=origem)
    assert render.render_peer(origem) == antes


def test_a_remocao_de_quem_reaproveita_nao_derruba_objeto_da_origem():
    # derrubar o filtro da origem apagaria a politica dos dois links. A
    # remocao nao precisa da origem: o bloco de quem reaproveita nao nomeia
    # filtro nenhum
    _, backup = par_de_reaproveitamento()
    texto = render.render_remove(backup)
    assert "undo xpl" not in texto
    assert "undo peer 198.51.100.10" in texto


# O id 0 e uma origem legitima: e o primeiro peer de um tenant novo. Os
# templates decidiam pelo valor (`{% if peer.politica_de %}` no bloco, e o
# `not` no da remocao), e 0 e falso em Jinja - quem reaproveitasse dele saia
# com a politica escrita inteira no proprio bloco, em silencio, e a remocao
# derrubava objetos que ele nem cria. O par de reaproveitamento do teste de
# cima usa politica_de=1, entao este caso passa por fora dele.
QUEM_MONTA_PEER = [peer_cliente, peer_parceiro, peer_upstream, peer_ix,
                   peer_pni]


@pytest.mark.parametrize("monta", QUEM_MONTA_PEER)
def test_o_id_zero_de_origem_e_uma_origem(monta):
    origem = monta(id=0, apelido="ORIGEM", nome="ORIGEM", descricao="ORIGEM")
    alvo = monta(id=7, apelido="BKP", nome="BKP", descricao="BKP", politica_de=0)

    bloco = render.render_peer(alvo, origem=origem)
    remocao = render.render_remove(alvo)

    # o ramo de quem reaproveita, e nao o do peer avulso
    assert "-ORIGEM-IMPORT-V4" in bloco
    assert "xpl " not in bloco
    assert "undo xpl" not in remocao


@pytest.mark.parametrize("monta", QUEM_MONTA_PEER)
def test_a_sessao_de_quem_reaproveita_sai_inteira_em_todo_tipo(monta):
    """A outra metade do bloco, tipo a tipo.

    A politica e da origem, mas a sessao e deste link, e ela sai inteira nos
    cinco tipos: aqui nao ha group do VRP carregando nada, entao timer, bfd
    e graceful-restart que faltassem sairiam com o default do equipamento.

    O caso que muda por tipo e o do IX: sem o `undo ... check-first-as` o
    route server nao insere o proprio ASN no path, e o check de default
    descarta a rota antes de ela alcancar filtro nenhum. O bloco de quem
    reaproveita nao tem os objetos do tipo, mas ele tem a sessao - e a
    sessao do IX e a unica que carrega essa linha.
    """
    origem = monta(id=0, apelido="ORIGEM", nome="ORIGEM", descricao="ORIGEM")
    alvo = monta(id=7, apelido="BKP", nome="BKP", descricao="BKP",
                 politica_de=0, timer_keepalive=30, timer_hold=90, bfd=True,
                 graceful_restart=True)

    texto = render.render_peer(alvo, origem=origem)
    remoto = alvo.sessoes["v4"]["remoto"]

    assert "peer %s as-number %s" % (remoto, alvo.asn) in texto
    assert "peer %s description %s" % (remoto, alvo.descricao) in texto
    assert "peer %s route-limit %d %s" % (remoto, alvo.route_limit,
                                          plan.ACAO_LIMITE) in texto
    assert "peer %s %s" % (remoto, plan.AS_ONLY) in texto
    assert "peer %s timer keepalive 30 hold 90" % remoto in texto
    assert "peer %s capability-advertise graceful-restart" % remoto in texto
    assert "peer %s bfd enable" % remoto in texto

    assert ("undo peer %s check-first-as enable" % remoto in texto) == (
        alvo.tipo == "ix")


# --- a cadeia por prefixo no import do downstream -----------------------


def test_o_tratamento_por_prefixo_vem_depois_do_apply_peer():
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", communities=["64512:210"])], "v6": []}))
    trecho = texto.split("xpl route-filter CUST-268127-IMPORT-V4")[1]
    corpo = [l.strip() for l in trecho.split("end-filter")[0].splitlines()
             if l.strip()]
    assert corpo[-1] == "finish"
    assert corpo[-2] == "endif"
    assert corpo.index("call route-filter APPLY-PEER-268127") < corpo.index(
        "if ip route-destination in {45.169.232.0 22} then")
    assert "apply community {64512:210} additive" in corpo


def test_o_mais_especifico_vence_e_os_dois_nao_somam():
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", communities=["64512:210"]),
        Bloco(prefixo="45.169.232.0/24", communities=["64512:211"])], "v6": []}))
    trecho = texto.split("xpl route-filter CUST-268127-IMPORT-V4")[1]
    corpo = [l.strip() for l in trecho.split("end-filter")[0].splitlines()
             if l.strip()]
    # um `elseif` so, e o /24 na frente: e o if/elseif que impede as duas
    # linhas de somarem numa rota so
    assert sum(1 for l in corpo if l.startswith("elseif")) == 1
    assert corpo.index("if ip route-destination in {45.169.232.0 24} then") \
        < corpo.index("elseif ip route-destination in {45.169.232.0 22} then")


def test_o_intervalo_estende_o_casamento_e_vem_depois_do_exato():
    """O `-24` e o que faz a clausula alcancar os mais especificos, e no
    mesmo prefixo o exato vence: a rota do proprio /22 fica com o
    tratamento da linha sem sufixo."""
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", ate=24, communities=["64512:210"]),
        Bloco(prefixo="45.169.232.0/22", communities=["64512:211"])], "v6": []}))
    trecho = texto.split("xpl route-filter CUST-268127-IMPORT-V4")[1]
    corpo = [l.strip() for l in trecho.split("end-filter")[0].splitlines()
             if l.strip()]
    assert corpo.index("if ip route-destination in {45.169.232.0 22} then") \
        < corpo.index(
            "elseif ip route-destination in {45.169.232.0 22 le 24} then")


def test_a_lista_do_confinamento_segue_o_alcance_da_linha():
    """A linha sem sufixo confina no prefixo exato e o `-24` e o que libera
    os mais especificos: a lista e a clausula do import dizem a mesma coisa
    sobre o mesmo prefixo."""
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", communities=["64512:210"]),
        Bloco(prefixo="45.169.236.0/23", ate=24,
              communities=["64512:211"])], "v6": []}))
    lista = texto.split("xpl ip-prefix-list PL-CUST-268127-V4")[1].split(
        "end-list")[0]
    corpo = [l.strip() for l in lista.splitlines() if l.strip()]
    assert corpo == ["45.169.232.0 22,", "45.169.236.0 23 le 24"]


def test_o_intervalo_em_v6_usa_o_comprimento_da_linha():
    texto = render.render_peer(peer_cliente(
        prefixos={"v4": [], "v6": [
            Bloco(prefixo="2804:3300::/32", ate=48,
                  communities=["64512:210"])]},
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"},
                 "v6": {"local": "2001:db8::1", "remoto": "2001:db8::2"}}))
    assert "if ipv6 route-destination in {2804:3300:: 32 le 48} then" in texto


def test_o_parceiro_ganha_a_cadeia_depois_do_carimbo_do_tipo():
    texto = render.render_peer(peer_parceiro(prefixos={"v4": [
        Bloco(prefixo="45.169.236.0/22", communities=["64512:210"])], "v6": []}))
    trecho = texto.split("xpl route-filter CUST-64500-IMPORT-V4")[1]
    corpo = trecho.split("end-filter")[0]
    assert corpo.index("64512:2091") < corpo.index(
        "if ip route-destination in {45.169.236.0 22} then")


def test_o_peer_sem_tratamento_nao_ganha_clausula():
    # o resto do bloco deste peer ja esta coberto pelo golden do cliente, que
    # nao pode mudar uma linha nesta feature
    texto = render.render_peer(peer_cliente())
    assert "elseif ip route-destination" not in texto
    assert "tratamento por prefixo" not in texto


def test_golden_do_cliente_tratado():
    # as duas formas na mesma cadeia: o /22 exato e o /23 que alcanca o /24
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", communities=["64512:210", "64512:5070"]),
        Bloco(prefixo="45.169.236.0/23", ate=24,
              communities=["64512:211"])], "v6": []}))
    assert texto == (GOLDEN / "cliente-tratado.txt").read_text(encoding="ascii")


def test_a_linha_coberta_pela_mais_larga_sai_das_duas_listas():
    """A linha do /23 com community continua no cadastro, porque e ela que
    carrega o tratamento, mas nao repete nas listas o que o `22 le 24` do
    /22 ja alcanca. No BH a poda e so pelo bloco, porque ali o alcance e
    sempre `ge 32 le 32`."""
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", ate=24),
        Bloco(prefixo="45.169.232.0/23", communities=["64512:5000"]),
        Bloco(prefixo="45.169.236.0/22", ate=24),
        Bloco(prefixo="45.169.238.0/23", communities=["64512:5000"])],
        "v6": []}))
    cust = texto.split("xpl ip-prefix-list PL-CUST-268127-V4")[1].split(
        "end-list")[0]
    bh = texto.split("xpl ip-prefix-list PL-CUST-268127-BH-V4")[1].split(
        "end-list")[0]
    assert [l.strip() for l in cust.splitlines() if l.strip()] == [
        "45.169.232.0 22 le 24,", "45.169.236.0 22 le 24"]
    assert [l.strip() for l in bh.splitlines() if l.strip()] == [
        "45.169.232.0 22 ge 32 le 32,", "45.169.236.0 22 ge 32 le 32"]
    # o tratamento sai inteiro: e a clausula por prefixo que leva a community
    assert "if ip route-destination in {45.169.232.0 23} then" in texto
    assert "elseif ip route-destination in {45.169.238.0 23} then" in texto


def test_o_blackhole_poda_o_que_o_confinamento_mantem():
    """O /22 exato libera so o proprio /22 no confinamento, e a linha do /23
    fica; no BH as duas alcancam os mesmos /32, e so o /22 sai."""
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", ate=22, communities=["64512:210"]),
        Bloco(prefixo="45.169.232.0/23", communities=["64512:211"])],
        "v6": []}))
    cust = texto.split("xpl ip-prefix-list PL-CUST-268127-V4")[1].split(
        "end-list")[0]
    bh = texto.split("xpl ip-prefix-list PL-CUST-268127-BH-V4")[1].split(
        "end-list")[0]
    assert [l.strip() for l in cust.splitlines() if l.strip()] == [
        "45.169.232.0 22 le 22,", "45.169.232.0 23"]
    assert [l.strip() for l in bh.splitlines() if l.strip()] == [
        "45.169.232.0 22 ge 32 le 32"]


def test_o_grupo_tambem_nao_repete_a_linha_coberta():
    # as listas do grupo tem a mesma forma (o teto no lugar do intervalo),
    # entao a poda vale igual
    grupo = grupo_com_asn(prefixos={"v4": ["203.0.113.0/22", "203.0.113.0/23"],
                                    "v6": []})
    texto = render.render_grupo(grupo)
    cust = texto.split("xpl ip-prefix-list PL-CUST-UP-REDUNDANTE-V4")[1].split(
        "end-list")[0]
    bh = texto.split(
        "xpl ip-prefix-list PL-CUST-UP-REDUNDANTE-BH-V4")[1].split(
        "end-list")[0]
    assert [l.strip() for l in cust.splitlines() if l.strip()] == [
        "203.0.113.0 22 le 24"]
    assert [l.strip() for l in bh.splitlines() if l.strip()] == [
        "203.0.113.0 22 ge 32 le 32"]


def test_golden_do_cliente_com_a_linha_coberta():
    texto = render.render_peer(peer_cliente(prefixos={"v4": [
        Bloco(prefixo="45.169.232.0/22", ate=24),
        Bloco(prefixo="45.169.232.0/23", communities=["64512:5000"]),
        Bloco(prefixo="45.169.236.0/22", ate=24),
        Bloco(prefixo="45.169.238.0/23", communities=["64512:5000"])],
        "v6": []}))
    assert texto == (GOLDEN / "cliente-coberto.txt").read_text(encoding="ascii")


@pytest.mark.parametrize("valor", ["", "PARCIAL", "tudo", None])
def test_tabela_invalida_nao_vira_full_no_render(valor):
    # so o full explicito cai no ramo sem portao; o resto nao gera nada
    with pytest.raises(ValueError):
        render.render_peer(peer_cliente(tabela=valor))


@pytest.mark.parametrize("tipo", ["cliente", "parceiro"])
@pytest.mark.parametrize("tabela", ["nenhuma", "parcial", "parcial_ix", "full"])
def test_matriz_dos_modos_nas_duas_familias(tipo, tabela):
    peer = peer_cliente(tipo=tipo, tabela=tabela, sessoes={
        "v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"},
        "v6": {"local": "2001:db8::1", "remoto": "2001:db8::2"}},
        prefixos={"v4": ["45.169.232.0/22"], "v6": ["2001:db8:100::/48"]})
    texto = render.render_peer(peer)
    for fam in ("V4", "V6"):
        export = _export(texto, fam=fam)
        if tabela == "nenhuma":
            assert [l.strip() for l in export.splitlines()
                    if l.strip()] == ["refuse"], fam
            continue
        for veto in ("CL-RESTRICAO", "CL-BLACKHOLE", "CL-NOADV-CUST",
                     "CL-ONLY-NOT-CLIENT", "{64512:0:268127}",
                     "64512:1900"):
            assert veto in export, (fam, veto)
        assert ("CL-ORIGEM-ANUNCIAVEL" in export) == (tabela == "parcial")
        assert ("CL-ORIGEM-PARCIAL-IX" in export) == (tabela == "parcial_ix")
        assert export.strip().endswith("finish"), fam


def test_o_membro_nao_emite_a_default_propria():
    # quem emite e o grupo; o membro com a caixa gravada nao muda nada
    grupo = grupo_cliente_sem_asn()
    membro = peer_membro_sem_override(grupo.id)
    membro.tipo = "cliente"
    membro.default_route = True
    texto = render.render_peer(membro, grupo=grupo)
    assert "default-route-advertise" not in texto
    assert "default route" not in texto


def test_o_cabecalho_do_membro_mostra_a_default_do_grupo():
    grupo = grupo_cliente_sem_asn()
    grupo.default_route = True
    membro = peer_membro_sem_override(grupo.id)
    membro.tipo = "cliente"
    cabecalho = render.render_peer(membro, grupo=grupo).splitlines()[:8]
    assert any(l.startswith("# default route: a do grupo %s" % grupo.nome)
               for l in cabecalho)


# route-limit e public-as-only sao da familia no VRP: na sessao, o equipamento
# os poe na ipv4-family, e no peer IPv6 a linha nem e aceita. O multihop e o
# contrario, da sessao, com o TTL fixo do plano.

def _sessao_e_familias(texto):
    bgp = texto[texto.index("bgp %s\n" % plan.ASN):]
    corte = bgp.index("-family unicast")
    corte = bgp.rindex("\n", 0, corte) + 1
    return bgp[:corte], bgp[corte:]


def _familia(familias, nome):
    bloco = familias[familias.index(" %s unicast" % nome):]
    fim = bloco.find("-family unicast", len(nome) + 2)
    return bloco if fim < 0 else bloco[:bloco.rindex("\n", 0, fim)]


def _dual_stack(peer):
    peer.sessoes = {
        "v4": {"local": "192.0.2.2", "remoto": "192.0.2.3"},
        "v6": {"local": "2001:db8:100::1", "remoto": "2001:db8:100::2"},
    }
    return peer


@pytest.mark.parametrize("monta", [peer_cliente, peer_upstream, peer_ix, peer_pni])
def test_route_limit_e_public_as_only_saem_dentro_da_familia(monta):
    peer = _dual_stack(monta())
    sessao, familias = _sessao_e_familias(render.render_peer(peer))
    assert "route-limit" not in sessao
    assert "public-as-only" not in sessao
    for nome, remoto in (("ipv4-family", "192.0.2.3"),
                         ("ipv6-family", "2001:db8:100::2")):
        familia = _familia(familias, nome)
        assert ("  peer %s enable\n"
                "  y\n"
                "  peer %s route-limit %d %s\n"
                "  peer %s %s\n" % (remoto, remoto, peer.route_limit,
                                      plan.ACAO_LIMITE, remoto, plan.AS_ONLY)
                ) in familia


@pytest.mark.parametrize("tipo", ["cliente", "parceiro", "upstream", "ix", "pni"])
def test_route_limit_do_membro_sai_dentro_da_familia(tipo):
    grupo = grupo_do_tipo(tipo)
    membro = membro_com_override_do_tipo(tipo, grupo)
    sessao, familias = _sessao_e_familias(render.render_peer(membro, grupo=grupo))
    assert "route-limit" not in sessao
    for nome, remoto in (("ipv4-family", "192.0.2.3"),
                         ("ipv6-family", "2001:db8:100::2")):
        assert ("  peer %s group %s\n"
                "  peer %s route-limit %d %s\n" % (
                    remoto, grupo.nome, remoto, membro.route_limit,
                    plan.ACAO_LIMITE)) in _familia(familias, nome)


def test_public_as_only_do_grupo_sai_dentro_da_familia():
    grupo = grupo_cliente_sem_asn()
    sessao, familias = _sessao_e_familias(render.render_grupo(grupo))
    assert "public-as-only" not in sessao
    for nome in ("ipv4-family", "ipv6-family"):
        assert ("  peer %s enable\n  y\n  peer %s %s\n" % (
            grupo.nome, grupo.nome, plan.AS_ONLY)) in _familia(familias, nome)


@pytest.mark.parametrize("monta", [peer_cliente, peer_upstream, peer_ix, peer_pni])
def test_multihop_sai_na_sessao_com_o_ttl_do_plano(monta):
    peer = _dual_stack(monta(multihop=True))
    sessao, familias = _sessao_e_familias(render.render_peer(peer))
    for remoto in ("192.0.2.3", "2001:db8:100::2"):
        assert " peer %s ebgp-max-hop %d\n" % (remoto, plan.MULTIHOP_TTL) in sessao
    assert "ebgp-max-hop" not in familias
    assert plan.MULTIHOP_TTL == 64


@pytest.mark.parametrize("monta", [peer_cliente, peer_upstream, peer_ix, peer_pni])
def test_sem_multihop_nao_sai_ebgp_max_hop(monta):
    assert "ebgp-max-hop" not in render.render_peer(monta())


@pytest.mark.parametrize("tipo", ["cliente", "parceiro", "upstream", "ix", "pni"])
def test_multihop_do_membro_sai_na_sessao_dele(tipo):
    # o grupo nao carrega o multihop: e do peer, e o ramo de membro nao passa
    # pelo sessao_do_peer
    grupo = grupo_do_tipo(tipo)
    membro = membro_com_override_do_tipo(tipo, grupo)
    membro.multihop = True
    sessao, _ = _sessao_e_familias(render.render_peer(membro, grupo=grupo))
    for remoto in ("192.0.2.3", "2001:db8:100::2"):
        assert " peer %s ebgp-max-hop %d\n" % (remoto, plan.MULTIHOP_TTL) in sessao
    membro.multihop = False
    assert "ebgp-max-hop" not in render.render_peer(membro, grupo=grupo)


def test_reaproveita_leva_o_multihop_do_proprio_peer():
    origem = peer_cliente()
    alvo = peer_cliente(id=7, apelido="BKP", nome="BKP", politica_de=0,
                        multihop=True,
                        sessoes={"v4": {"local": "198.51.100.9",
                                        "remoto": "198.51.100.10"}})
    texto = render.render_peer(alvo, origem=origem)
    assert " peer 198.51.100.10 ebgp-max-hop 64\n" in texto
