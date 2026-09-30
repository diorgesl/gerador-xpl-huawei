import pytest

from app import plan
from test_render import peer_cliente

# nomes locais so para as assercoes ficarem legiveis na horizontal
C200, C201, C202, C203, C204 = ("64512:%d" % v for v in (200, 201, 202, 203, 204))
C210, C211, C212, C213 = ("64512:%d" % v for v in (210, 211, 212, 213))


def test_lp_base_por_tipo():
    assert plan.LP_BASE == {"cliente": 300, "parceiro": 300, "upstream": 100,
                            "ix": 190, "pni": 200}


def test_origem_por_tipo():
    assert plan.ORIGEM == {"cliente": 1100, "parceiro": 1100, "upstream": 1400,
                           "ix": 1300, "pni": 1500}
    # o parceiro carrega a mesma origem do cliente, e e isso que mantem as
    # rotas dele em CL-ORIGEM-ANUNCIAVEL: a marca de 2091 vai por cima, nao
    # no lugar
    assert plan.ORIGEM["parceiro"] == plan.ORIGEM["cliente"] == 1100


def test_classe_do_cliente_troca_a_origem():
    assert plan.ORIGEM_CLASSE == {
        "transito": 1100,
        "residencial": 1110,
        "corporativo": 1120,
        "cgnat": 1130,
    }


def test_escada_de_local_preference():
    # GSHUT antes da escada, escada em ordem crescente, default no fim
    assert plan.LP_BASE["cliente"] == plan.LP_CLIENTE_DEFAULT == 300
    assert plan.LP_CLIENTE == (
        ("64512:101", 50),
        ("64512:102", 80),
        ("64512:103", 150),
        ("64512:104", 250),
        ("64512:105", 350),
    )
    assert plan.LP_IX_CDN == 195
    assert plan.LP_TE_PREFER == 250
    assert plan.LP_BLACKHOLE == 400


def test_route_limit_por_tipo():
    assert plan.ROUTE_LIMIT == {
        "cliente": 50,
        "parceiro": 50,
        "upstream": 1500000,
        "ix": 500000,
        "pni": 10000,
    }
    # o exemplo de aplicacao do PLANO usa um valor diferente do da tabela
    assert plan.ROUTE_LIMIT_EXEMPLO["upstream"] == 1100000


def test_timer_por_tipo():
    # o PLANO so poe timer explicito no upstream
    assert plan.TIMER_PADRAO["upstream"] == (10, 30)
    assert plan.TIMER_PADRAO["cliente"] == (None, None)
    assert set(plan.TIMER_PADRAO) == set(plan.TIPOS)


def test_escala_do_prepend():
    assert plan.DIGITO_PREPEND == {4: 3, 3: 2, 2: 1}
    # o digito 1 (P1 explicito) nao tem ramo: existe para barrar a classe
    assert 1 not in plan.DIGITO_PREPEND


def test_classe_6ca_por_tipo():
    # a tabela do PLANO tem 3 para "IX privado e PNI" e 4 para CDN; o
    # exemplo de PNI e de CDN e usa 4, e e ele que o gerador segue
    assert plan.CLASSE_6CA == {"upstream": 1, "ix": 2, "pni": 4}
    assert set(plan.CLASSE_6CA) == {"upstream", "ix", "pni"}


def test_noadv_por_tipo():
    # o terceiro valor e o 5PPA com digito 0: "nao anunciar para este peer"
    assert plan.noadv("upstream", 1) == [C200, C201, "64512:5010"]
    assert plan.noadv("ix", 10) == [C200, C203, "64512:5100"]
    assert plan.noadv("pni", 20) == [C200, C202, "64512:5200"]


def test_noadv_do_cliente_nao_tem_eixo_por_peer():
    assert plan.noadv_cust() == [C200, C204]


def test_os_tipos_de_downstream():
    # o parceiro e um cliente que fica no roteador das CDNs: as tabelas do
    # tipo sao as mesmas, e o que o separa e a marca de 2091
    assert plan.TIPOS_DOWNSTREAM == ("cliente", "parceiro")
    assert set(plan.TIPOS_DOWNSTREAM) < set(plan.TIPOS)
    for tipo in plan.TIPOS_DOWNSTREAM:
        assert plan.ORIGENS_POR_TIPO[tipo] == tuple(plan.ORIGEM_CLASSE.values())
        assert plan.LP_BASE[tipo] == plan.LP_CLIENTE_DEFAULT
        assert plan.ROUTE_LIMIT[tipo] == plan.ROUTE_LIMIT["cliente"]
        assert plan.TIMER_PADRAO[tipo] == (None, None)


def test_a_marca_do_parceiro_esta_na_dezena_do_ecossistema_de_cdn():
    # 2091 abre a dezena que o PLANO reserva ao ecossistema de CDN, entao a
    # marca nao abre faixa nova nem sai do namespace
    assert plan.PARCEIRO == "64512:2091"
    assert plan.faixa_ok(plan.PARCEIRO)


def test_o_carimbo_do_import_do_downstream():
    # o cliente leva origem e POP; o parceiro leva a marca junto, e so ele
    assert plan.c_downstream("cliente", 1120, 2001) == "{64512:1120, 64512:2001}"
    assert plan.c_downstream("parceiro", 1120, 2001) == (
        "{64512:1120, 64512:2001, 64512:2091}")


def test_only_not_por_tipo():
    # 213 fica de fora de ONLY-NOT-CLIENT: ele E o "somente cliente"
    assert plan.only_not("cliente") == [C210, C211, C212]
    assert plan.only_not("upstream") == [C211, C212, C213]
    assert plan.only_not("ix") == [C210, C212, C213]
    assert plan.only_not("pni") == [C210, C211, C213]


def test_blackhole_e_manutencao():
    assert plan.BLACKHOLE == ("65535:666", "64512:666")
    assert plan.BLACKHOLE_PROPAGATE == "64512:667"
    assert plan.BLACKHOLE_INFO == "64512:9666"
    assert plan.GSHUT == "65535:0"


def test_origem_anunciavel():
    assert plan.ORIGEM_ANUNCIAVEL == (
        "64512:1000", "64512:1100", "64512:1110",
        "64512:1120", "64512:1130",
    )
    # e exatamente a origem propria mais as quatro classes de cliente
    assert plan.ORIGEM_ANUNCIAVEL[0] == "64512:1000"
    assert plan.ORIGEM_ANUNCIAVEL[1:] == tuple(
        "64512:%d" % plan.ORIGEM_CLASSE[c] for c in plan.CLASSES_CLIENTE)


def test_formatos_de_community():
    assert plan.c4pp0(1) == "64512:4010"
    assert plan.c4pp0(10) == "64512:4100"
    assert plan.c5ppa(1, 0) == "64512:5010"
    assert plan.c5ppa(1, 4) == "64512:5014"
    assert plan.c5ppa(10, 1) == "64512:5101"
    assert plan.c6ca(1, 4) == "64512:614"
    assert plan.c6ca(2, 2) == "64512:622"
    assert plan.c6ca(4, 4) == "64512:644"
    assert plan.c_large(3, 14840) == "64512:3:14840"


def test_5ppa_e_o_large_equivalente_andam_juntos():
    # digito 2 -> 1 prepend -> 64512:1:<ASN>; digito 4 -> 3 -> 64512:3:<ASN>
    for digito, asn in ((2, 64500), (3, 64500), (4, 64500)):
        assert plan.c5ppa(1, digito)[-1] == str(digito)
        assert plan.c_large(digito - 1, asn) == "64512:%d:%d" % (digito - 1, asn)
    # digito 0 -> nao anunciar -> 64512:0:<ASN>
    assert plan.c5ppa(1, 0) == "64512:5010"
    assert plan.c_large(0, 64500) == "64512:0:64500"


def test_conjunto():
    assert plan.conjunto("64512:200") == "{64512:200}"
    assert plan.conjunto("64512:1", "64512:2") == "{64512:1, 64512:2}"


def test_c4pp0_nao_colide_com_o_regex_de_informativa():
    # quatro digitos, mas nao comeca com 1, 2, 3 nem 9
    assert plan.c4pp0(1)[6] == "4"


def test_cidr_para_xpl():
    assert plan.cidr_para_xpl("45.169.232.0/22") == "45.169.232.0 22"
    assert plan.cidr_para_xpl("2001:db8::/32") == "2001:db8:: 32"


def test_cidr_para_xpl_recusa_entrada_sem_mascara():
    with pytest.raises(ValueError):
        plan.cidr_para_xpl("45.169.232.0")


# --- o ASN configuravel -------------------------------------------------
#
# O prefixo das communities nao e constante: o topo do peers.yaml pode
# trocar o AS, e a partir dai todo "64512:" vira o ASN novo. O modulo
# continua respondendo pelo de fabrica quando ninguem passa nada, e e isso
# que faz um peers.yaml sem "asn:" gerar a config byte a byte de antes.

# os nomes que carregam o ASN. A lista existe para o teste de varredura
# poder ser exaustivo em vez de citar dois ou tres.
CAMPOS_DO_ASN = ("PARCEIRO", "ORIGEM_ANUNCIAVEL", "LP_CLIENTE", "BLACKHOLE",
                 "BLACKHOLE_PROPAGATE", "BLACKHOLE_INFO", "ORIGEM_NOME")


def test_a_rede_de_fabrica_e_a_de_sempre():
    r = plan.Rede()
    assert r.asn == 64512
    assert r.politica == 64512
    assert r.c5ppa(1, 0) == "64512:5010"
    assert r.BLACKHOLE == ("65535:666", "64512:666")


def test_a_rede_troca_o_prefixo_de_tudo_que_e_do_plano():
    r = plan.Rede(asn=64500)
    # ASN de 16 bits: o namespace das standards e o proprio ASN
    assert r.politica == 64500
    assert r.c4pp0(1) == "64500:4010"
    assert r.c5ppa(1, 0) == "64500:5010"
    assert r.c6ca(1, 4) == "64500:614"
    assert r.c_large(3, 14840) == "64500:3:14840"
    assert r.noadv("upstream", 1) == ["64500:200", "64500:201", "64500:5010"]
    assert r.noadv_cust() == ["64500:200", "64500:204"]
    assert r.only_not("pni") == ["64500:210", "64500:211", "64500:213"]
    assert r.c_downstream("parceiro", 1120, 2001) == (
        "{64500:1120, 64500:2001, 64500:2091}")
    assert r.PARCEIRO == "64500:2091"
    assert r.ORIGEM_ANUNCIAVEL == ("64500:1000", "64500:1100", "64500:1110",
                                   "64500:1120", "64500:1130")
    assert r.LP_CLIENTE == (("64500:101", 50), ("64500:102", 80),
                            ("64500:103", 150), ("64500:104", 250),
                            ("64500:105", 350))
    assert r.BLACKHOLE == ("65535:666", "64500:666")
    assert r.BLACKHOLE_PROPAGATE == "64500:667"
    assert r.BLACKHOLE_INFO == "64500:9666"
    assert r.faixa_ok("64500:100") and not r.faixa_ok("64512:100")


def test_o_rotulo_da_origem_propria_acompanha_o_asn():
    # o 1000 e "prefixo proprio do AS<asn>", e a tela le este rotulo
    assert plan.ORIGEM_NOME[1000] == "prefixo proprio do AS64512"
    assert plan.Rede(asn=64500).ORIGEM_NOME[1000] == (
        "prefixo proprio do AS64500")
    # com asn_politica declarado os dois numeros divergem, e o rotulo e do AS
    # da sessao: 264130 e quem tem o prefixo, 65532 e so o namespace das
    # standard. O caso acima nao pega isto porque la os dois coincidem
    assert plan.Rede(264130, 65532).ORIGEM_NOME[1000] == (
        "prefixo proprio do AS264130")
    # as outras nove linhas nao citam AS nenhum e nao tem por que mudar
    assert {k: v for k, v in plan.Rede(asn=64500).ORIGEM_NOME.items()
            if k != 1000} == {k: v for k, v in plan.ORIGEM_NOME.items()
                              if k != 1000}


def test_o_que_nao_carrega_o_asn_e_o_mesmo_objeto():
    # o template escreve plan.TIPOS e plan.c5ppa no mesmo "plan": quem
    # responde pelo que nao depende do ASN e o modulo
    r = plan.Rede(asn=64500)
    assert r.TIPOS == plan.TIPOS
    assert r.LP_BASE == plan.LP_BASE
    assert r.ROUTE_LIMIT == plan.ROUTE_LIMIT
    assert r.DIGITO_PREPEND == plan.DIGITO_PREPEND
    assert r.quadro_ao_criar == plan.quadro_ao_criar
    assert r.conjunto("64500:200") == "{64500:200}"


def test_nenhum_campo_do_asn_fica_no_64512():
    # a falha que este teste existe para pegar: um nome que ficou de fora do
    # objeto cai na delegacao do modulo e serve o 64512 calado. Meio
    # namespace trocado nao aparece num diff de config; aparece aqui.
    r = plan.Rede(asn=64500)
    for nome in CAMPOS_DO_ASN:
        assert "64512" not in str(getattr(r, nome)), nome


def test_um_campo_do_asn_esquecido_e_erro_na_hora_e_nao_64512_calado():
    r = plan.Rede(asn=64500)
    with pytest.raises(AttributeError):
        r.PARCEIRO_ESQUECIDO


def test_o_asn_de_32_bits_exige_o_namespace_de_16():
    # a standard da RFC 1997 tem 16 bits por campo: um ASN de 32 bits nao
    # cabe, e por isso ele so entra com um namespace declarado
    with pytest.raises(ValueError):
        plan.Rede(asn=264130)
    r = plan.Rede(asn=264130, politica=64512)
    assert r.asn == 264130
    assert r.politica == 64512
    assert r.c5ppa(1, 0) == "64512:5010"
    assert r.faixa_ok("64512:100") and not r.faixa_ok("264130:100")


def test_namespace_fora_da_faixa_de_16_bits_e_erro():
    for politica in (0, 65536, 4294967294):
        with pytest.raises(ValueError):
            plan.Rede(asn=64500, politica=politica)


def test_faixa_ok():
    assert plan.faixa_ok("64512:100")
    assert plan.faixa_ok("64512:699")
    assert plan.faixa_ok("64512:1000")
    assert plan.faixa_ok("64512:9999")
    assert not plan.faixa_ok("64512:99")
    assert not plan.faixa_ok("64512:10000")
    assert not plan.faixa_ok("14840:100")
    assert not plan.faixa_ok("64512:6:1")
    assert not plan.faixa_ok("64512:abc")


def test_nome_origem_v4():
    assert plan.nome_origem("38.252.64.0/22") == "ORIGEM-38-252-64-0_22"


def test_nome_origem_v6_come_o_abreviador():
    """O `::` some junto com os hextetos que ele abrevia, e o que sobra e
    o prefixo escrito com os hextetos que existem."""
    assert plan.nome_origem("2804:36b4:8000::/34") == "ORIGEM-2804-36b4-8000_34"
    assert plan.nome_origem("2804:36b4::/32") == "ORIGEM-2804-36b4_32"


def test_nome_origem_normaliza_o_prefixo():
    assert plan.nome_origem("38.252.64.7/22") == plan.nome_origem("38.252.64.0/22")


def test_dois_prefixos_distintos_nao_colidem_no_nome():
    """Colisao de nome de objeto no VRP e uma linha derrubando a outra."""
    prefixos = ["38.252.64.0/22", "38.252.64.0/23", "38.252.64.0/24",
                "38.252.66.0/23", "38.252.66.0/24", "170.80.32.0/22",
                "2804:36b4::/32", "2804:36b4:8000::/34",
                "2804:36b4:8000::/33", "2804:36b4:c000::/34"]
    nomes = [plan.nome_origem(c) for c in prefixos]
    assert len(set(nomes)) == len(nomes)


def test_endereco_e_mascara_do_v4():
    assert plan.endereco("38.252.64.0/22") == "38.252.64.0"
    assert plan.mascara("38.252.64.0/22") == "255.255.252.0"


def test_endereco_e_mascara_do_v6():
    """Em v6 a mascara e o comprimento direto: e o que o `ipv6
    route-static` e o `network` da view da familia pedem."""
    assert plan.endereco("2804:36b4:8000::/34") == "2804:36b4:8000::"
    assert plan.mascara("2804:36b4:8000::/34") == "34"


def test_separa_communities_pela_contagem_de_dois_pontos():
    std, lg = plan.separa_communities(
        ["64512:613", "64512:0:14840", "15169:12100", "64512:4:14840"])
    assert std == ["64512:613", "15169:12100"]
    assert lg == ["64512:0:14840", "64512:4:14840"]


def test_conjunto_de_monta_o_literal_com_a_lista_pronta():
    assert plan.conjunto_de(["64512:1000", "64512:613"]) == "{64512:1000, 64512:613}"
    assert plan.conjunto_de([]) == "{}"


def test_o_rede_responde_pelos_nomes_novos():
    """Os templates falam com o Rede, nunca com o modulo."""
    assert plan.Rede().nome_origem("38.252.64.0/22") == "ORIGEM-38-252-64-0_22"
    assert plan.Rede(asn=264130, politica=65532).nome_origem(
        "38.252.64.0/22") == "ORIGEM-38-252-64-0_22"


# --- o quadro "ao criar" e da origem ------------------------------------


def test_o_quadro_ao_criar_nao_existe_para_quem_reaproveita():
    # o par CL-PEER/APPLY-PEER e da origem: criar um aqui daria dois
    # objetos para o mesmo papel
    assert not plan.quadro_ao_criar(peer_cliente(politica_de=1), False)


def test_a_entrada_do_prefixo_na_lista():
    # sem alcance a entrada e o prefixo exato; com ele, alcanca os mais
    # especificos ate o comprimento escrito
    assert plan.entrada_do_prefixo("45.169.232.0/22") == "45.169.232.0 22"
    assert plan.entrada_do_prefixo("45.169.232.0/22", 24) == (
        "45.169.232.0 22 le 24")


def test_o_conjunto_do_prefixo():
    # sem intervalo, o casamento e o prefixo exato
    assert plan.conjunto_do_prefixo("45.169.232.0/22", None) == (
        "{45.169.232.0 22}")
    assert plan.conjunto_do_prefixo("45.169.232.0/22", 24) == (
        "{45.169.232.0 22 le 24}")
    assert plan.conjunto_do_prefixo("2804:36b4::/32", 48) == (
        "{2804:36b4:: 32 le 48}")


def test_o_comprimento_do_cidr():
    assert plan.comprimento("45.169.232.0/22") == 22
    assert plan.comprimento("2804:36b4::/32") == 32
    # o torto devolve 0 em vez de estourar: quem recusa e o validate, e a
    # ordenacao nao pode ser mais um lugar que morre no mesmo dado
    assert plan.comprimento("nao-e-cidr") == 0
