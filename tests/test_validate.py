from app import plan, validate
from app.peers import Peer, Grupo, Bloco
from app.validate import validar, validar_grupo


def um_peer(**kw):
    base = dict(
        id=1, apelido="", nome="Cliente ACME", tipo="cliente",
        asn=268127, classe="residencial", descricao="CLIENTE-AS268127",
        lp_base=300, origem=1110, pop=2001, aprendizado=None, ix_id=None,
        prefixos={"v4": ["45.169.232.0/22"], "v6": []},
        te_prefixos={"v4": [], "v6": []},
        ap_block=[], ap_te=[], ap_allowed=[], ap_prefer=[],
        bfd=True, graceful_restart=True, timer_keepalive=None, timer_hold=None,
        prepend_base=0, route_limit=50,
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"},
                 "v6": {}},
    )
    # o peer externo valido carrega a origem do proprio tipo: a de cliente
    # do base e recusada fora do downstream
    if "origem" not in kw and kw.get("tipo") in plan.ORIGENS_POR_TIPO \
            and kw["tipo"] not in plan.TIPOS_DOWNSTREAM:
        base["origem"] = plan.ORIGENS_POR_TIPO[kw["tipo"]][0]
    base.update(kw)
    return Peer(**base)


def campos(erros):
    return {e.campo for e in erros}


def test_peer_valido_nao_tem_erro():
    assert validate.validar(um_peer(), []) == []


def test_default_route_so_no_cliente():
    # a default route e servico de downstream: nos outros tres tipos nao ha
    # formulario que a peca, e um POST a mao nao pode gravar a flag
    assert "default_route" not in campos(
        validate.validar(um_peer(default_route=True), []))
    for tipo, extra in (("upstream", {}),
                        ("ix", {"ix_id": 1}),
                        ("pni", {"ap_allowed": ["64500"]})):
        peer = um_peer(tipo=tipo, classe=None, aprendizado=3000,
                       default_route=True, **extra)
        assert "default_route" in campos(validate.validar(peer, [])), tipo


def test_asn_reservado_e_erro():
    for asn in (0, 23456, 4294967295):
        assert "asn" in campos(validate.validar(um_peer(asn=asn), [])), asn


def test_asn_privado_e_aviso_e_nao_erro():
    assert validate.validar(um_peer(asn=64512), []) == []
    assert "asn" in campos(validate.avisos(um_peer(asn=64512), []))


def test_id_fora_da_faixa_e_erro():
    assert "id" in campos(validate.validar(um_peer(id=100), []))


def test_id_repetido_e_erro():
    outro = um_peer(id=1, asn=9999)
    assert "id" in campos(validate.validar(um_peer(), [outro]))


def test_grupo_recusa_id_de_peer():
    grupo = Grupo(id=3, nome="G", tipo="cliente", classe="transito",
                  origem=1100, pop=2001)
    peer = um_peer()
    peer.id = 3
    erros = validar_grupo(grupo, [grupo], [peer], anterior=grupo)
    assert ("id", "ID 3 ja usado pelo peer %s" % peer.nome) in [
        (e.campo, e.mensagem) for e in erros]


def test_peer_recusa_id_de_grupo():
    grupo = Grupo(id=7, nome="PARCEIROS", tipo="parceiro")
    peer = um_peer()
    peer.id = 7
    erros = validar(peer, [peer], anterior=peer, grupos=[grupo])
    assert ("id", "ID ja usado pelo grupo PARCEIROS") in [
        (e.campo, e.mensagem) for e in erros]


def test_grupo_recusa_nome_igual_ao_token_de_peer():
    # o nome do grupo e o token do peer viram o mesmo <T> no nome dos
    # objetos (UP-<T>-IMPORT-V4, AP-CUST-<T>, CL-NOADV-<T>). Os dois arquivos
    # sao colados no mesmo equipamento e o ultimo colado vence, entao nome e
    # token tem que ser espacos disjuntos, como os ids ja eram.
    grupo = um_grupo(nome="14840", tipo="upstream", origem=1400)
    peer = um_peer(asn=14840, tipo="upstream", classe=None, pop=None,
                   aprendizado=3100)
    erros = validar_grupo(grupo, [grupo], [peer], anterior=grupo)
    assert ("nome",
            "nome ja usado pelo peer %s: o nome do grupo e o token do peer "
            "viram o mesmo nome de objeto" % peer.nome) in [
        (e.campo, e.mensagem) for e in erros]


def test_grupo_e_peer_com_nomes_diferentes_nao_colidem():
    grupo = um_grupo(nome="PROVEDOR", tipo="upstream", origem=1400)
    peer = um_peer(asn=14840, tipo="upstream", classe=None, pop=None,
                   aprendizado=3100)
    assert validar_grupo(grupo, [grupo], [peer], anterior=grupo) == []
    assert validar(peer, [peer], anterior=peer, grupos=[grupo]) == []


def test_peer_recusa_token_igual_ao_nome_de_grupo():
    grupo = um_grupo(nome="14840", tipo="upstream", origem=1400)
    peer = um_peer(asn=14840, tipo="upstream", classe=None, pop=None,
                   aprendizado=3100)
    erros = validar(peer, [peer], anterior=peer, grupos=[grupo])
    assert ("asn",
            "token 14840 ja e o nome do grupo 14840: o token do peer e o "
            "nome do grupo viram o mesmo nome de objeto") in [
        (e.campo, e.mensagem) for e in erros]


def test_peer_com_apelido_no_lugar_do_token_erra_no_apelido():
    # o campo do erro e o que o operador mexe no peer: com apelido, o token
    # e o apelido, e trocar o ASN nao tiraria a colisao
    grupo = um_grupo(nome="PROVEDOR", tipo="upstream", origem=1400)
    peer = um_peer(asn=14840, apelido="PROVEDOR", tipo="upstream", classe=None,
                   pop=None, aprendizado=3100)
    erros = validar(peer, [peer], anterior=peer, grupos=[grupo])
    assert ("apelido",
            "token PROVEDOR ja e o nome do grupo PROVEDOR: o token do peer e o nome "
            "do grupo viram o mesmo nome de objeto") in [
        (e.campo, e.mensagem) for e in erros]


def test_grupo_recusa_id_fora_da_faixa():
    # o %02d do plan.c5ppa trunca calado: um id 100 vira o 00 de outro
    for ident in (-1, 100):
        grupo = Grupo(id=ident, nome="G", tipo="cliente", classe="transito",
                      origem=1100, pop=2001)
        erros = validar_grupo(grupo, [grupo], [], anterior=grupo)
        assert "id" in [e.campo for e in erros], ident


def test_id_repetido_no_proprio_peer_editado_nao_e_erro():
    eu = um_peer()
    assert validate.validar(eu, [eu], anterior=eu) == []


def test_token_e_o_asn_quando_nao_ha_apelido():
    assert um_peer().token == "268127"
    assert um_peer(apelido="").token == "268127"
    assert um_peer(tipo="ix", asn=26162, apelido="IX-SP").token == "IX-SP"


def test_apelido_invalido_e_erro():
    # vazio deixou de ser erro: em branco o token e o ASN, que e o caso comum
    for apelido in ("ix sp", "-IX", "IX-", "TOKENMUITOLONGO", "ix"):
        assert "apelido" in campos(validate.validar(um_peer(apelido=apelido), [])), apelido


def test_apelido_com_hifen_no_meio_e_aceito():
    assert "apelido" not in campos(validate.validar(um_peer(apelido="IX-SP"), []))


def test_asn_repetido_e_erro():
    # sem apelido nos dois, o token dos dois e o ASN, e o campo do erro e o
    # apelido: e ele que desempata. Nao ha trava no ASN, dois peers do mesmo
    # cliente sao legitimos; o que nao pode e repetir o token
    outro = um_peer(id=2, asn=9999)
    assert "apelido" in campos(validate.validar(um_peer(asn=9999), [outro]))


def ix(asn, apelido, ident, remoto):
    return um_peer(id=ident, tipo="ix", asn=asn, apelido=apelido, classe=None,
                   ix_id=ident, aprendizado=3000,
                   sessoes={"v4": {"local": "187.16.192.1", "remoto": remoto},
                            "v6": {}})


def test_dois_ix_sem_apelido_colidem_no_token():
    # o ASN de uma sessao de IX e o do route server, o mesmo em todo IX.
    # Sem apelido os dois viram o token 26162 e um bloco sobrescreve o outro;
    # a colisao e a unica pista de que faltou o apelido
    outro = ix(26162, "", 2, "187.16.192.2")
    assert "apelido" in campos(validate.validar(
        ix(26162, "", 3, "187.16.192.3"), [outro]))


def test_ix_sem_apelido_convive_com_ix_que_tem_um():
    # o que tem apelido sai com token proprio, entao nao ha colisao nenhuma
    # e o segundo IX nao precisa de apelido so porque o primeiro tem
    outro = ix(26162, "IX-SP", 2, "187.16.192.2")
    assert validate.validar(ix(26162, "", 3, "187.16.192.3"), [outro]) == []


def test_segundo_ix_com_apelido_proprio_passa():
    outro = ix(26162, "IX-SP", 2, "187.16.192.2")
    assert validate.validar(ix(26162, "IX-CG", 3, "187.16.192.3"), [outro]) == []


def test_sessao_duplicada_entre_peers_e_erro():
    outro = um_peer(id=2, asn=9999,
                    sessoes={"v4": {"local": "10.0.0.1", "remoto": "198.51.100.2"},
                             "v6": {}})
    assert "sessoes.v4.remoto" in campos(validate.validar(um_peer(), [outro]))


def test_peer_sem_familia_nenhuma_e_erro():
    p = um_peer(sessoes={"v4": {}, "v6": {}})
    assert "sessoes" in campos(validate.validar(p, []))


def test_endereco_de_familia_errada_e_erro():
    p = um_peer(sessoes={"v4": {"local": "2001:db8::1", "remoto": "198.51.100.2"},
                         "v6": {}})
    assert "sessoes.v4.local" in campos(validate.validar(p, []))


def test_cliente_sem_prefix_list_e_erro():
    p = um_peer(prefixos={"v4": [], "v6": []})
    assert "prefixos" in campos(validate.validar(p, []))


def test_bloco_de_cliente_sobreposto_e_erro():
    outro = um_peer(id=2, asn=9999,
                    prefixos={"v4": ["45.169.232.0/23"], "v6": []})
    assert "prefixos" in campos(validate.validar(um_peer(), [outro]))


def test_dois_links_do_mesmo_cliente_podem_ter_o_mesmo_bloco():
    """Link principal e backup do mesmo cliente anunciam os mesmos prefixos.

    O caso ao lado, que e o que a regra existe para pegar, usa ASNs
    diferentes: dois clientes reivindicando o mesmo espaco. Com o mesmo ASN
    e o mesmo cliente, o bloco repetido e o desenho normal de multihoming.
    Sem a distincao, o segundo link do cliente nao tinha como ser
    cadastrado, e nao ha trava no ASN que o impedisse por outro caminho.
    """
    principal = um_peer(id=1, asn=270620, nome="NETMAC")
    backup = um_peer(id=12, asn=270620, apelido="NETMAC-2", nome="NETMAC-2",
                     sessoes={"v4": {"local": "198.51.100.9",
                                     "remoto": "198.51.100.10"}, "v6": {}})
    assert "prefixos" not in campos(validate.validar(backup, [principal]))


def test_cliente_diferente_com_o_mesmo_bloco_continua_erro():
    """A dispensa pelo mesmo ASN nao pode afrouxar a regra do caso oposto.

    Dois clientes, dois ASNs, o mesmo bloco: e conflito ou erro de
    cadastro, e o que a sobreposicao existe para acusar.
    """
    outro = um_peer(id=2, asn=9999, prefixos={"v4": ["45.169.232.0/22"], "v6": []})
    assert "prefixos" in campos(validate.validar(um_peer(), [outro]))


def test_bloco_de_cliente_adjacente_nao_sobrepoe():
    outro = um_peer(id=2, asn=9999,
                    prefixos={"v4": ["45.169.236.0/22"], "v6": []})
    assert "prefixos" not in campos(validate.validar(um_peer(), [outro]))


def test_lp_base_fora_da_faixa_e_erro():
    assert "lp_base" in campos(validate.validar(um_peer(lp_base=70000), []))


def test_route_limit_zero_e_erro():
    assert "route_limit" in campos(validate.validar(um_peer(route_limit=0), []))


def test_community_fora_da_faixa_e_erro():
    assert "origem" in campos(validate.validar(um_peer(origem=1700), []))


def test_pop_fora_da_faixa_e_erro():
    assert "pop" in campos(validate.validar(um_peer(pop=2000), []))
    assert "pop" in campos(validate.validar(um_peer(pop=3000), []))


def test_upstream_exige_ponto_de_aprendizado():
    p = um_peer(tipo="upstream", asn=14840, classe=None,
                aprendizado=None, prefixos={"v4": [], "v6": []})
    assert "aprendizado" in campos(validate.validar(p, []))


def test_ix_exige_id_do_peeringdb():
    p = um_peer(tipo="ix", apelido="IX-SP", asn=26162, classe=None, ix_id=None,
                aprendizado=3010, prefixos={"v4": [], "v6": []})
    assert "ix_id" in campos(validate.validar(p, []))


def test_cliente_exige_classe():
    assert "classe" in campos(validate.validar(um_peer(classe=None), []))


def test_pni_exige_allowlist():
    p = um_peer(tipo="pni", apelido="CDN-A", asn=64510, classe=None,
                prefixos={"v4": [], "v6": []}, ap_allowed=[])
    assert "ap_allowed" in campos(validate.validar(p, []))


def test_upstream_sem_prefixos_de_te_em_branco_e_valido():
    p = um_peer(tipo="upstream", asn=14840, classe=None,
                aprendizado=3100, prefixos={"v4": [], "v6": []})
    assert validate.validar(p, []) == []


def test_timer_pela_metade_e_erro():
    p = um_peer(timer_keepalive=10, timer_hold=None)
    assert "timer_hold" in campos(validate.validar(p, []))


def test_hold_menor_que_o_keepalive_e_erro():
    p = um_peer(timer_keepalive=30, timer_hold=10)
    assert "timer_hold" in campos(validate.validar(p, []))


def test_timer_par_valido():
    p = um_peer(timer_keepalive=10, timer_hold=30)
    assert "timer_hold" not in campos(validate.validar(p, []))


def test_community_valida():
    assert validate.community_valida("64512:1100")
    assert not validate.community_valida("14840:666")


def test_community_valida_com_a_rede_declarada():
    # o default continua o de fabrica: quem chama sem rede ve o plano de
    # sempre, e quem chama com a rede ve o namespace dela
    assert validate.community_valida("64512:1100") == validate.community_valida(
        "64512:1100", plan.Rede())
    rede = plan.Rede(asn=64500)
    assert validate.community_valida("64500:1100", rede)
    assert not validate.community_valida("64512:1100", rede)


# Regressoes do Ruling 8 e do Ruling 9: o modo edicao dispensa so a
# comparacao com a propria entrada, e prefixo malformado vira Erro em vez
# de excecao.


def test_id_repetido_de_outro_peer_continua_no_modo_edicao():
    # a propria entrada sai da comparacao, entao o conflito so aparece
    # quando outra entrada carrega o mesmo id
    eu = um_peer(id=1, asn=999)
    outro = um_peer(id=1, asn=888, nome="Outro")
    assert "id" in campos(validate.validar(um_peer(id=1), [eu, outro], anterior=eu))


def test_editar_o_asn_nao_acusa_conflito_com_a_propria_entrada():
    # o token e derivado do ASN, entao trocar o ASN renomeia o peer. Se a
    # propria entrada fosse reconhecida pelo token, ela deixaria de ser
    # reconhecida e o peer apontaria conflito contra ele mesmo
    eu = um_peer()
    assert validate.validar(um_peer(asn=264130), [eu], anterior=eu) == []


def test_bloco_sobreposto_entre_clientes_continua_no_modo_edicao():
    eu = um_peer()
    outro = um_peer(id=2, asn=9999,
                    prefixos={"v4": ["45.169.232.0/23"], "v6": []})
    assert "prefixos" in campos(validate.validar(um_peer(), [eu, outro], anterior=eu))


def test_prefixo_malformado_e_erro_e_nao_excecao():
    for cidr in ("45.169.232.0/33", "45.169.232.0/22 33", "45.169.232.0/22/24"):
        p = um_peer(prefixos={"v4": [cidr], "v6": []})
        assert "prefixos" in campos(validate.validar(p, [])), cidr


def test_prefixo_sem_mascara_e_erro_e_nao_excecao():
    # um endereco cru analisa no ip_network como /32, mas o cidr_para_xpl
    # exige a barra: sem esta checagem ele so estourava na escrita do XPL
    for cidr in ("45.169.232.0", "2001:db8::"):
        p = um_peer(prefixos={"v4": [cidr], "v6": []})
        assert "prefixos" in campos(validate.validar(p, [])), cidr


def test_prefixo_malformado_de_outro_peer_nao_derruba_nem_acusa():
    outro = um_peer(id=2, asn=9999,
                    prefixos={"v4": ["45.169.232.0/22/24"], "v6": []})
    assert "prefixos" not in campos(validate.validar(um_peer(), [outro]))


def test_asn_renomeado_para_um_ja_usado_e_erro_no_modo_edicao():
    # o peer editado tambem esta sem apelido, entao o token dele e o ASN novo e
    # o campo do erro e o apelido, como no asn repetido da criacao
    eu = um_peer(id=1, asn=268127)
    outro = um_peer(id=2, asn=9999)
    assert "apelido" in campos(
        validate.validar(um_peer(id=1, asn=9999), [eu, outro], anterior=eu))


# Ruling 14: nome e descricao sao texto livre digitado pelo operador, e a
# descricao vai inteira para o XPL gerado. Sem esta regra o acento passa no
# formulario e so estoura depois, como UnicodeEncodeError na escrita ASCII,
# longe do campo que o causou. O acento entra por chr() para este arquivo
# continuar ASCII puro como o resto do repositorio.


NOME_COM_ACENTO = "Cliente Jo" + chr(0xE3) + "o"
DESCRICAO_COM_ACENTO = "CLIENTE-ACME-EDI" + chr(0xC7) + chr(0xC3) + "O"


def test_descricao_com_acento_e_erro():
    p = um_peer(descricao=DESCRICAO_COM_ACENTO)
    assert "descricao" in campos(validate.validar(p, []))


def test_nome_com_acento_e_erro():
    p = um_peer(nome=NOME_COM_ACENTO)
    assert "nome" in campos(validate.validar(p, []))


def test_nome_e_descricao_ascii_nao_dao_erro():
    p = um_peer(nome="Cliente ACME", descricao="CLIENTE-ACM-01")
    nomes = campos(validate.validar(p, []))
    assert "nome" not in nomes and "descricao" not in nomes


def test_erro_de_ascii_nomeia_o_campo():
    erros = validate.validar(um_peer(descricao=DESCRICAO_COM_ACENTO), [])
    assert "descricao" in validate.erros_para_dict(erros)["descricao"]


# Fix round 2: o pop nao vem da classe, so a origem vem. Em branco ele
# passava pela faixa, que so confere quando ha valor, e estourava no render,
# no "%d" que escreve a community de POP no import. A metade "origem" da
# decisao anterior continua de pe e segue adiada para o T11.


def test_cliente_sem_pop_e_erro():
    assert "pop" in campos(validate.validar(um_peer(pop=None), []))


def test_cliente_com_pop_nao_da_erro():
    for pop in (2001, 2500, 2999):
        assert "pop" not in campos(validate.validar(um_peer(pop=pop), [])), pop


def test_erro_de_pop_nomeia_o_campo():
    erros = validate.validar(um_peer(pop=None), [])
    assert "pop" in validate.erros_para_dict(erros)["pop"]


# Fix final: a outra metade da decisao do pop, que ficou adiada ate aqui. A
# origem em branco passava pela faixa, que so confere quando ha valor, e
# estourava no render no "%d" que a escreve -- nos quatro tipos, porque os
# quatro templates formatam a origem. Como o peer e gravado antes do render,
# o estouro levava junto o estado ja salvo.


def test_cliente_sem_origem_e_erro():
    assert "origem" in campos(validate.validar(um_peer(origem=None), []))


def test_origem_em_branco_e_erro_nos_quatro_tipos():
    # um por tipo, porque um so nao cobre os outros tres: a faixa da origem e
    # do cliente, e era ela que escondia o buraco dos demais
    por_tipo = {
        "cliente": dict(classe="residencial",
                        prefixos={"v4": ["45.169.232.0/22"], "v6": []}),
        "upstream": dict(classe=None, aprendizado=3100,
                         prefixos={"v4": [], "v6": []}),
        "ix": dict(classe=None, aprendizado=3010, ix_id=9999,
                   prefixos={"v4": [], "v6": []}),
        "pni": dict(classe=None, ap_allowed=["64510"],
                    prefixos={"v4": [], "v6": []}),
    }
    for tipo, kw in por_tipo.items():
        p = um_peer(tipo=tipo, origem=None, **kw)
        assert "origem" in campos(validate.validar(p, [])), tipo


def test_erro_de_origem_nomeia_o_campo():
    erros = validate.validar(um_peer(origem=None), [])
    assert "origem" in validate.erros_para_dict(erros)["origem"]


def test_origem_preenchida_nao_da_erro():
    assert "origem" not in campos(validate.validar(um_peer(origem=1110), []))


# Fix final: o prefixo de TE do upstream tambem passa pelo plan.cidr_para_xpl.
# A checagem existia so no ramo do cliente, e so sobre `prefixos`: uma entrada
# sem barra no te_prefixos de um upstream validava limpa e estourava no
# render, depois do peer ja gravado.


def test_prefixo_de_te_malformado_e_erro_e_nao_excecao():
    for cidr in ("10.0.0.0", "198.51.100.0/33", "198.51.100.0/24/25"):
        p = um_peer(tipo="upstream", asn=14840, classe=None,
                    aprendizado=3100, prefixos={"v4": [], "v6": []},
                    te_prefixos={"v4": [cidr], "v6": []})
        assert "te_prefixos" in campos(validate.validar(p, [])), cidr


def test_prefixo_de_te_valido_nao_da_erro():
    p = um_peer(tipo="upstream", asn=14840, classe=None,
                aprendizado=3100, prefixos={"v4": [], "v6": []},
                te_prefixos={"v4": ["198.51.100.0/24"], "v6": []})
    assert validate.validar(p, []) == []


def test_prefixo_de_te_malformado_e_erro_tambem_no_cliente():
    # o campo existe no formulario de todos os tipos, e o cliente tambem tem
    # o seu: a checagem e do campo, nao do tipo
    p = um_peer(te_prefixos={"v4": ["10.0.0.0"], "v6": []})
    assert "te_prefixos" in campos(validate.validar(p, []))


# Round 2: o tipo. Ele escolhe o template e as tabelas do plano, e o caminho
# do POST nao tinha o portao que o GET /api/peers/novo tem: um tipo fora de
# plan.TIPOS validava limpo, gravava o peer e so estourava no render, com
# TemplateNotFound.
# E antes disso o avisos ja estourava, com KeyError, no ROUTE_LIMIT[peer.tipo]
# depois do .get devolver None.


def test_tipo_desconhecido_e_erro():
    assert "tipo" in campos(validate.validar(um_peer(tipo="xyz"), []))


def test_o_erro_de_tipo_nomeia_o_valor_que_chegou():
    erros = validate.validar(um_peer(tipo="xyz"), [])
    assert "xyz" in validate.erros_para_dict(erros)["tipo"]


def test_tipo_conhecido_nao_da_erro_de_tipo():
    for tipo in plan.TIPOS:
        assert "tipo" not in campos(validate.validar(um_peer(tipo=tipo), [])), tipo


def test_avisos_nao_estoura_com_tipo_desconhecido():
    # o avisos roda no ramo de erro do salvar: se ele estoura, o 500 que o
    # erro de tipo tirou do render volta por outro caminho, e a tela nao
    # chega a mostrar o erro
    assert validate.avisos(um_peer(tipo="xyz"), []) == []


def test_avisos_nao_avisa_route_limit_de_tipo_desconhecido():
    # a tabela nao tem sugestao para um tipo que nao esta nela: nao ha o que
    # sugerir, e o aviso so existia como estouro
    p = um_peer(tipo="xyz", route_limit=999)
    assert "route_limit" not in campos(validate.avisos(p, []))


def test_avisos_continua_avisando_o_route_limit_dos_quatro_tipos():
    # o portao novo nao pode silenciar o aviso dos tipos que estao na tabela
    for tipo in plan.TIPOS:
        p = um_peer(tipo=tipo, route_limit=plan.ROUTE_LIMIT[tipo] + 1)
        assert "route_limit" in campos(validate.avisos(p, [])), tipo


# A CL-PEER-<T>: as communities que a operadora aplica na sessao do peer. O
# valor vem de contrato e o plano nao o enumera, entao a sintaxe barra e a
# faixa so avisa.


def test_communities_no_plano_nao_dao_erro_nem_aviso():
    p = um_peer(communities=["64512:1500"],
                large_communities=["64512:4:264130"])
    assert validate.validar(p, []) == []
    assert validate.avisos(p, []) == []


def test_community_fora_da_sintaxe_e_erro():
    for valor in ("64512", "abc:1", "64512:1:2", "64512:", ":1500",
                  "64512:1500 x", "64512:65536"):
        p = um_peer(communities=[valor])
        assert "communities" in campos(validate.validar(p, [])), valor


def test_large_community_fora_da_sintaxe_e_erro():
    # a large tem tres campos (RFC 8092): uma standard com dois, ou uma com
    # quatro, vai para um large-community-list e o equipamento recusa
    for valor in ("64512:4", "64512:4:264130:1", "abc:1:2",
                  "64512:4294967296:1"):
        p = um_peer(large_communities=[valor])
        assert "large_communities" in campos(validate.validar(p, [])), valor


def test_community_valida_mas_fora_da_faixa_do_plano_e_aviso():
    # 50 e uma community de 16 bits como outra qualquer, e esta fora das duas
    # faixas do plano. Barrar aqui seria o gerador decidindo contrato, e a
    # faixa nao descreve o que o cliente pediu.
    p = um_peer(communities=["64512:50"])
    assert validate.validar(p, []) == []
    assert "communities" in campos(validate.avisos(p, []))


def test_large_community_de_outro_namespace_e_aviso():
    p = um_peer(large_communities=["64500:4:1"])
    assert validate.validar(p, []) == []
    assert "large_communities" in campos(validate.avisos(p, []))


def test_o_aviso_da_cl_peer_ja_sabe_da_rede_declarada():
    # com o ASN declarado no peers.yaml, 64500:1100 esta na faixa do plano e
    # 64512:1100 nao: o aviso segue o namespace da rede e nao o de fabrica
    rede = plan.Rede(asn=64500)
    da_rede = um_peer(communities=["64500:1100"], large_communities=["64500:4:1"])
    da_fabrica = um_peer(communities=["64512:1100"],
                         large_communities=["64512:4:1"])
    assert validate.avisos(da_rede, [], rede) == []
    assert validate.avisos(da_rede, []) == validate.avisos(da_rede, [], None)
    assert "communities" in campos(validate.avisos(da_fabrica, [], rede))
    assert "large_communities" in campos(validate.avisos(da_fabrica, [], rede))


def test_o_aviso_da_large_com_asn_de_32_bits_le_o_namespace_da_politica():
    # a large carrega o namespace no primeiro campo e o ASN no terceiro: com
    # a rede de 32 bits o primeiro campo continua sendo o da politica
    rede = plan.Rede(asn=264130, politica=64500)
    p = um_peer(large_communities=["64500:4:264130"])
    assert validate.avisos(p, [], rede) == []
    assert validate.large_no_plano("64500:4:264130", rede)
    assert not validate.large_no_plano("264130:4:264130", rede)


def test_o_erro_de_community_nomeia_o_valor():
    erros = validate.erros_para_dict(
        validate.validar(um_peer(communities=["oi"]), []))
    assert "oi" in erros["communities"]


def test_ix_com_community_guardada_avisa_que_nao_vai_sair():
    # o par CL-PEER-<T> / APPLY-PEER-<T> e de cliente e upstream: no IX e no
    # PNI o quadro nao existe, e o valor guardado nunca chega ao equipamento
    for tipo, extra in (("ix", {"ix_id": 1, "apelido": "RS"}),
                        ("pni", {"ap_allowed": ["64500"]})):
        p = um_peer(tipo=tipo, classe=None, aprendizado=3000,
                    communities=["64512:1500"], **extra)
        assert validate.validar(p, []) == [], tipo
        assert "communities" in campos(validate.avisos(p, [])), tipo


def test_no_ix_a_lista_vazia_nao_avisa():
    p = um_peer(tipo="ix", classe=None, aprendizado=3000, ix_id=1, apelido="RS")
    assert "communities" not in campos(validate.avisos(p, []))


def test_o_valor_sem_sintaxe_nao_ganha_aviso_em_cima_do_erro():
    # o aviso e sobre o valor que o equipamento aceita e o plano nao
    # descreve: um valor que o equipamento nao aceita ja saiu como erro, e
    # o aviso em cima dele so enche a tela
    p = um_peer(communities=["oi"], large_communities=["oi"])
    assert "communities" in campos(validate.validar(p, []))
    assert validate.avisos(p, []) == []


# Grupo BGP (VRP `group`): validacao do proprio grupo e do peer que aponta
# para um, ver spec e plano de 2026-09-22.


def um_grupo(**over):
    # os campos dos tres tipos novos entram no fixture na T8, junto com o
    # gate que os aceita. No ramo de downstream, que e o tipo default daqui,
    # eles ficam inertes: quem os checa e o outro ramo.
    base = dict(id=0, nome="PARCEIROS_CDN", tipo="parceiro", lp_base=300,
               classe="transito", origem=1100, pop=2001,
               asn=14840, aprendizado=3100, ix_id=1, ap_allowed=[64500])
    base.update(over)
    return Grupo(**base)


def test_grupo_valido_sem_erro():
    assert validate.validar_grupo(um_grupo(), [], []) == []


def test_grupo_nome_invalido():
    assert "nome" in campos(validate.validar_grupo(um_grupo(nome="minusculo"), [], []))
    assert "nome" in campos(validate.validar_grupo(um_grupo(nome="A B"), [], []))


def test_grupo_nome_duplicado():
    outro = um_grupo(id=1, nome="PARCEIROS_CDN")
    assert "nome" in campos(validate.validar_grupo(um_grupo(id=0), [outro], []))


def test_grupo_downstream_exige_classe_origem_pop():
    assert "classe" in campos(validate.validar_grupo(um_grupo(classe=None), [], []))
    assert "origem" in campos(validate.validar_grupo(um_grupo(origem=None), [], []))
    assert "pop" in campos(validate.validar_grupo(um_grupo(pop=None), [], []))


def test_grupo_com_prefixo_exige_asn():
    g = um_grupo(asn=None, prefixos={"v4": ["203.0.113.0/24"], "v6": []})
    assert "prefixos" in campos(validate.validar_grupo(g, [], []))


def test_grupo_sem_asn_e_sem_prefixo_passa():
    assert validate.validar_grupo(um_grupo(asn=None), [], []) == []


def test_grupo_prefixo_malformado_e_erro():
    # o prefixo do grupo vai para o plan.cidr_para_xpl como o do peer. Sem
    # esta checagem o grupo era gravado assim mesmo e o GET
    # /api/grupos/{ident}/saida estourava para sempre, sem a tela oferecer
    # como consertar.
    g = um_grupo(asn=64500,
                 prefixos={"v4": ["203.0.113.0", "lixo"], "v6": []})
    erros = validate.validar_grupo(g, [], [])
    assert campos(erros) == {"prefixos"}
    assert [e.mensagem for e in erros] == [
        "prefixo invalido: 203.0.113.0", "prefixo invalido: lixo"]


def test_grupo_prefixo_valido_passa():
    g = um_grupo(asn=64500, prefixos={"v4": ["203.0.113.0/24"], "v6": []})
    assert validate.validar_grupo(g, [], []) == []


def test_grupo_asn_fora_da_faixa_ou_reservado_e_erro():
    # o ASN do grupo faneia para o as-number de toda sessao membro, para o
    # AP-CUST e para as large-communities: vale a mesma faixa do peer
    for asn in (-5, 0, 23456, 4294967295, 4294967296):
        erros = validate.validar_grupo(um_grupo(asn=asn), [], [])
        assert "asn" in campos(erros), asn
        assert "ASN reservado pela IANA" in [e.mensagem for e in erros], asn


def test_grupo_asn_valido_nao_e_erro():
    assert "asn" not in campos(validate.validar_grupo(um_grupo(asn=64500), [], []))


def test_grupo_timer_pela_metade_e_erro():
    assert "timer_hold" in campos(validate.validar_grupo(
        um_grupo(timer_keepalive=10, timer_hold=None), [], []))
    assert "timer_keepalive" in campos(validate.validar_grupo(
        um_grupo(timer_keepalive=None, timer_hold=30), [], []))


def test_grupo_hold_menor_que_o_keepalive_e_erro():
    # o par do grupo sai na sessao que todo membro herda: um hold curto aqui
    # derruba a sessao de todos eles, nao a de um so
    assert "timer_hold" in campos(validate.validar_grupo(
        um_grupo(timer_keepalive=30, timer_hold=10), [], []))


def test_grupo_timer_par_valido_nao_e_erro():
    assert "timer_hold" not in campos(validate.validar_grupo(
        um_grupo(timer_keepalive=10, timer_hold=30), [], []))


def test_peer_agrupado_dispensa_classe_origem_pop_prefixo():
    # o grupo e o 2 porque o id 1 e do peer do um_peer: peer e grupo no
    # mesmo numero agora colidem
    grupo = Grupo(id=2, nome="PARCEIROS_CDN", tipo="parceiro", lp_base=300,
                 classe="transito", origem=1100, pop=2001)
    p = um_peer(tipo="parceiro", classe=None, origem=None, pop=None,
               prefixos={"v4": [], "v6": []}, grupo_id=2)
    assert validate.validar(p, [], grupos=[grupo]) == []


def test_peer_agrupado_com_prefixo_proprio_exige_classe_origem_pop():
    grupo = Grupo(id=1, nome="PARCEIROS_CDN", tipo="parceiro")
    p = um_peer(tipo="parceiro", classe=None, origem=None, pop=None,
               prefixos={"v4": ["203.0.113.0/24"], "v6": []}, grupo_id=1)
    erros = campos(validate.validar(p, [], grupos=[grupo]))
    assert "classe" in erros and "origem" in erros and "pop" in erros


def test_peer_com_grupo_inexistente_e_erro():
    p = um_peer(tipo="parceiro", grupo_id=99)
    assert "grupo_id" in campos(validate.validar(p, [], grupos=[]))


def test_peer_com_tipo_diferente_do_grupo_e_erro():
    grupo = Grupo(id=1, nome="X", tipo="cliente")
    p = um_peer(tipo="parceiro", grupo_id=1)
    assert "grupo_id" in campos(validate.validar(p, [], grupos=[grupo]))


def test_membro_com_asn_diferente_do_grupo_e_erro():
    # o bloco do membro omite o as-number porque quem o declara e o grupo:
    # um ASN diferente aqui abriria a sessao com o ASN do grupo enquanto a
    # pagina e o cabecalho do arquivo mostram outro
    grupo = Grupo(id=1, nome="UP-REDUNDANTE", tipo="parceiro", asn=64500)
    p = um_peer(tipo="parceiro", asn=64501, grupo_id=1)
    erros = validate.validar(p, [], grupos=[grupo])
    assert [e.mensagem for e in erros if e.campo == "asn"] == [
        "ASN 64501 do membro difere do ASN 64500 do grupo UP-REDUNDANTE"]


def test_membro_com_o_mesmo_asn_do_grupo_passa():
    # id 2 no grupo pelo mesmo motivo do teste de cima: o 1 e do peer
    grupo = Grupo(id=2, nome="UP-REDUNDANTE", tipo="parceiro", asn=64500)
    p = um_peer(tipo="parceiro", asn=64500, grupo_id=2)
    assert validate.validar(p, [], grupos=[grupo]) == []


def test_membro_sem_asn_nao_ganha_acusacao_de_conflito():
    # o conflito e entre o ASN do membro e o do grupo: sem ASN no membro nao
    # ha o que comparar. O ASN 0 em si o validar do peer ja recusa pela regra
    # de sempre, que nao e deste achado.
    grupo = Grupo(id=1, nome="UP-REDUNDANTE", tipo="parceiro", asn=64500)
    p = um_peer(tipo="parceiro", asn=0, grupo_id=1)
    mensagens = [e.mensagem for e in validate.validar(p, [], grupos=[grupo])]
    assert not any("difere do ASN" in m for m in mensagens)


def test_editar_grupo_sem_renomear_nao_acusa_duplicata():
    # grupo_salvar monta um Grupo novo a cada POST, e a lista `grupos` ainda
    # carrega o objeto antigo com o mesmo nome: sem excluir `anterior` da
    # checagem, editar sem trocar o nome batia contra si mesmo
    g = um_grupo(id=0, nome="PARCEIROS_CDN")
    editado = um_grupo(id=0, nome="PARCEIROS_CDN", lp_base=250)
    assert validate.validar_grupo(editado, [g], [], anterior=g) == []


# R4 da T8: o gate de membro do `validar` abre para plan.TIPOS. Ate aqui um
# peer de upstream, ix ou pni nunca era aceito como membro, e o ramo de fora
# de downstream exigia aprendizado/ix_id/ap_allowed sem consultar o `exige`:
# com o gate aberto, o membro que herda tudo do grupo seria recusado por nao
# trazer campos que sao do grupo. O teste fixa os dois sentidos.


def um_grupo_do_tipo(tipo, **over):
    base = dict(id=2, nome="G", tipo=tipo, classe=None, pop=None,
                origem=plan.ORIGENS_POR_TIPO[tipo][0],
                aprendizado=3100, ix_id=1, ap_allowed=[64500])
    base.update(over)
    return um_grupo(**base)


def test_membro_dos_tres_tipos_novos_nao_traz_os_campos_do_tipo():
    for tipo in ("upstream", "ix", "pni"):
        grupo = um_grupo_do_tipo(tipo)
        p = um_peer(id=1, tipo=tipo, asn=grupo.asn, classe=None, pop=None,
                    origem=None, aprendizado=None, ix_id=None, ap_allowed=[],
                    prefixos={"v4": [], "v6": []}, grupo_id=grupo.id)
        erros = validar(p, [], grupos=[grupo])
        assert erros == [], (tipo, [e.mensagem for e in erros])


def test_membro_dos_tres_tipos_novos_com_filtro_proprio_exige_os_campos_do_tipo():
    # a outra direcao: uma CL-PEER no membro ja o tira da heranca (o mesmo
    # tem_filtro_proprio que decide o ramo do render), e ai os campos do tipo
    # voltam a ser dele. Sem isto o operador preencheria os campos no membro
    # so para passar na validacao, e o membro herdaria do grupo do mesmo jeito.
    for tipo, esperados in (("upstream", ("aprendizado",)),
                            ("ix", ("aprendizado", "ix_id")),
                            ("pni", ("ap_allowed",))):
        grupo = um_grupo_do_tipo(tipo)
        p = um_peer(id=1, tipo=tipo, asn=grupo.asn, classe=None, pop=None,
                    origem=None, aprendizado=None, ix_id=None, ap_allowed=[],
                    prefixos={"v4": [], "v6": []}, grupo_id=grupo.id,
                    communities=["14840:9133"])
        campos = [e.campo for e in validar(p, [], grupos=[grupo])]
        for campo in esperados:
            assert campo in campos, (tipo, campo)
        # e a origem volta junto, pelo mesmo exige: o membro deixou de herdar
        assert "origem" in campos, tipo


# T8: o grupo valida os cinco tipos. O portao que so aceitava cliente e
# parceiro sai, e cada tipo passa a ser conferido pelos campos que o render
# dele formata (o ruling (n) do plano): quem escolhe o ramo e o tipo, nao
# uma lista fixa de dois. O fixture um_grupo ja carrega os campos dos tres
# tipos novos, entao cada teste so mexe no que esta sob teste.


def test_grupo_aceita_os_cinco_tipos():
    # a origem sai da tabela do proprio tipo: nao existe uma so que sirva
    # para os cinco, e o grupo de cada tipo carrega so as dele
    for tipo in plan.TIPOS:
        g = um_grupo(tipo=tipo, classe="transito",
                     origem=plan.ORIGENS_POR_TIPO[tipo][0], pop=2001,
                     aprendizado=3100, ix_id=1, ap_allowed=[64500])
        erros = validar_grupo(g, [g], [], anterior=g)
        assert [e.campo for e in erros] == [], (tipo, [e.mensagem for e in erros])


def test_grupo_recusa_tipo_desconhecido():
    # o formulario so oferece os cinco, mas o POST nao passa por ele: um
    # tipo fora de plan.TIPOS gravava o grupo para estourar depois, no
    # TemplateNotFound do render, com o grupo ja no arquivo
    g = um_grupo(tipo="peer-fantasma")
    erros = validar_grupo(g, [g], [], anterior=g)
    assert "tipo" in [e.campo for e in erros]
    assert "tipo desconhecido: peer-fantasma" in [e.mensagem for e in erros]


def test_a_faixa_de_origem_do_grupo_depende_do_tipo():
    # upstream nao carrega origem de cliente: o carimbo mentiria sobre a
    # procedencia da rota. Aqui o grupo e mais estrito que o peer, que fora
    # de downstream so confere que a origem existe (ver o ruling da spec)
    g = um_grupo(tipo="upstream", origem=1110)
    erros = validar_grupo(g, [g], [], anterior=g)
    assert ("origem", "origem do upstream tem que ser uma de 1400, 1900") in [
        (e.campo, e.mensagem) for e in erros]
    assert validar_grupo(um_grupo(tipo="upstream", origem=1400),
                         [], [], anterior=None) == []


def test_grupo_de_upstream_e_ix_exige_aprendizado():
    for tipo in ("upstream", "ix"):
        g = um_grupo(tipo=tipo, aprendizado=None, ix_id=1)
        campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
        assert "aprendizado" in campos, tipo


def test_grupo_de_ix_exige_o_id_do_peeringdb():
    g = um_grupo(tipo="ix", aprendizado=3200, ix_id=None)
    campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
    assert "ix_id" in campos


def test_grupo_de_pni_exige_a_allowlist():
    g = um_grupo(tipo="pni", ap_allowed=[])
    campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
    assert "ap_allowed" in campos


def test_grupo_fora_de_downstream_recusa_default_route():
    # a default route e servico de downstream, e o comando sai dos macros que
    # os cinco tipos usam: sem esta checagem um POST a mao ligaria o anuncio
    # da default para quem nao a recebe
    for tipo in ("upstream", "ix", "pni"):
        g = um_grupo(tipo=tipo, default_route=True, ix_id=1,
                     ap_allowed=[64500], aprendizado=3100)
        campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
        assert "default_route" in campos, tipo


def test_grupo_de_upstream_nao_exige_classe_nem_pop():
    g = um_grupo(tipo="upstream", classe=None, pop=None, origem=1400)
    erros = validar_grupo(g, [g], [], anterior=g)
    assert [e.campo for e in erros] == [], [e.mensagem for e in erros]


def test_grupo_fora_de_downstream_exige_asn():
    # o ASN e formatado nos tres caminhos novos (_macros.j2, sempre por
    # c_large, que faz "%d"): com o campo vazio isso e TypeError na hora de
    # gerar, depois do grupo ja gravado. Downstream fica de fora de
    # proposito: ali o ASN e opcional, porque cada membro pode declarar o
    # proprio.
    for tipo in ("upstream", "ix", "pni"):
        g = um_grupo(tipo=tipo, asn=None, aprendizado=3100, ix_id=1,
                     ap_allowed=[64500], origem=plan.ORIGENS_POR_TIPO[tipo][0])
        erros = validar_grupo(g, [g], [], anterior=g)
        assert [e.mensagem for e in erros if e.campo == "asn"] == [
            "grupo de %s exige o ASN" % tipo], tipo


def test_grupo_com_community_malformada_e_recusado():
    # o campo tem o mesmo destino do campo do peer (a CL-PEER-<G>) e o mesmo
    # risco: malformada, ela passa pelo cadastro e so estoura no equipamento
    g = um_grupo(communities=["14840:9133", "nao-e-community"])
    campos = [e.campo for e in validar_grupo(g, [g], [], anterior=g)]
    assert "communities" in campos


def bloco(prefixo="38.252.64.0/22", communities=None):
    return Bloco(prefixo=prefixo, communities=list(communities or []))


def erros_de(communities):
    return validate.validar_blocos({"v4": [bloco(communities=communities)],
                                    "v6": []})


def test_bloco_sem_communities_nao_tem_erro():
    assert erros_de([]) == []


def test_o_673_do_exemplo_do_plano_e_recusado():
    """A classe 7 nao tem ramo em filtro nenhum, e o PLANO a publica na
    tabela do 6CA: CLASSE_6CA so tem upstream, ix e pni."""
    (erro,) = erros_de(["64512:673"])
    assert erro.campo == "blocos_v4"
    assert "classe 7" in erro.mensagem


def test_a_large_4_e_recusada():
    """Anunciar somente para um ASN nao tem ramo: o egress implementa as
    funcoes 0, 1, 2 e 3."""
    (erro,) = erros_de(["64512:4:14840"])
    assert "funcao 4" in erro.mensagem


def test_a_informativa_de_large_acima_da_faixa_e_recusada():
    """As informativas de large do PLANO sao 1000 (origem), 1001 (IX) e
    1002 (POP): o teto e o mesmo eixo do padrao, e o que passa dele nao
    esta no plano."""
    for valor in ("64512:10001:64510", "64512:1003:64510"):
        (erro,) = erros_de([valor])
        assert "sem dono" in erro.mensagem, valor
    assert erros_de(["64512:1000:64510", "64512:1001:2010",
                     "64512:1002:2001"]) == []


def test_o_1xx_e_recusado_porque_o_consumidor_e_o_import_de_cliente():
    (erro,) = erros_de(["64512:104"])
    assert "1xx" in erro.mensagem


def test_faixa_sem_dono_e_recusada():
    for valor in ("64512:301", "64512:401", "64512:711", "64512:812"):
        (erro,) = erros_de([valor])
        assert "sem dono" in erro.mensagem, valor


def test_escopo_que_o_egress_le_passa():
    assert erros_de(["64512:200", "64512:204", "64512:211", "64512:213"]) == []


def test_escopo_fora_da_tabela_e_recusado():
    (erro,) = erros_de(["64512:205"])
    assert "2xx" in erro.mensagem


def test_6ca_das_classes_implementadas_passa():
    """O 1 e o 9 caem fora da cadeia e nao prependam nada, mas os dois sao
    publicados no PLANO como P1 e como default explicito."""
    assert erros_de(["64512:613", "64512:622", "64512:644",
                     "64512:611", "64512:619"]) == []


def test_6ca_com_digito_sem_ramo_e_recusado():
    (erro,) = erros_de(["64512:615"])
    assert "digito 5" in erro.mensagem


def test_6ca_com_o_digito_0_e_recusado():
    """O PLANO da o 0 do 6CA como escopo, e nenhum ramo o le. No 5PPA o 0 e
    outra historia: la ele entra no CL-NOADV do peer."""
    (erro,) = erros_de(["64512:610"])
    assert "digito 0" in erro.mensagem


def test_5ppa_com_digito_0_a_4_passa():
    assert erros_de(["64512:5130", "64512:5131", "64512:5134"]) == []


def test_5ppa_com_digito_5_e_recusado():
    (erro,) = erros_de(["64512:5135"])
    assert "digito 5" in erro.mensagem


def test_blackhole_e_manutencao_passam():
    assert erros_de(["64512:666", "64512:667", "64512:9666"]) == []


def test_informativa_de_geografia_passa():
    assert erros_de(["64512:2101", "64512:2001"]) == []


def test_informativa_acima_da_faixa_do_plano_e_recusada():
    """plan.FAIXAS fecha a informativa em 9999, e nenhum filtro le acima."""
    for valor in ("64512:10001", "64512:65535"):
        (erro,) = erros_de([valor])
        assert "sem dono" in erro.mensagem, valor


def test_o_2000_que_desliga_o_anuncio_externo_e_recusado():
    """O 2000 e a marca de rota aprendida de fora, e o egress de upstream,
    IX e PNI recusam a rota que o carrega: escrito num bloco proprio, o
    prefixo para de sair para os tres em silencio. O 200 faz o mesmo de
    proposito, e o motivo aponta para ele."""
    (erro,) = erros_de(["64512:2000"])
    assert erro.campo == "blocos_v4"
    assert "2000" in erro.mensagem
    assert "200" in erro.mensagem
    assert erros_de(["64512:200", "64512:2001", "64512:2101"]) == []


def test_community_de_outro_as_passa():
    """O vocabulario do mundo nao da para conferir, e o bloco existe
    justamente para carregar a tag da operadora."""
    assert erros_de(["15169:12100", "14840:9133"]) == []


def test_o_intervalo_no_bloco_proprio_e_recusado():
    """O `-24` e da clausula por prefixo do cliente, e o bloco proprio nao
    tem clausula nenhuma: aceitar aqui seria guardar um alcance que nao sai
    em configuracao."""
    erros = validate.validar_blocos({"v4": [
        Bloco(prefixo="38.252.64.0/22", ate=24)], "v6": []})
    assert erros[0].campo == "blocos_v4"
    assert "-24" in erros[0].mensagem


def test_cada_familia_marca_o_proprio_campo():
    erros = validate.validar_blocos(
        {"v4": [], "v6": [bloco(prefixo="2804:36b4::/32",
                                communities=["64512:673"])]})
    assert erros[0].campo == "blocos_v6"


def test_o_namespace_da_rede_vale_para_o_bloco_como_para_o_peer():
    """Com asn_politica declarado, o que vale e 65532:673, e nao 64512:673."""
    rede = plan.Rede(asn=264130, politica=65532)
    assert validate.validar_blocos({"v4": [], "v6": []}, rede) == []
    erros = validate.validar_blocos(
        {"v4": [bloco(communities=["65532:673"])], "v6": []}, rede)
    assert "classe 7" in erros[0].mensagem


def test_prefixo_invalido_e_erro_no_campo_da_familia():
    erros = validate.validar_blocos(
        {"v4": [bloco(prefixo="nao-e-cidr")], "v6": []})
    assert erros[0].campo == "blocos_v4"
    assert "CIDR" in erros[0].mensagem


def test_valor_com_tres_dois_pontos_e_recusado_pela_forma():
    """A tabela de faixas le so o primeiro campo, entao um valor torto
    passaria por ela, cairia na lista de standard e viraria uma linha de
    apply community que o equipamento recusa na hora de colar."""
    for valor in ("64512:1:2:3", "64512", "64512:", "a:b"):
        (erro,) = erros_de([valor])
        assert "invalida" in erro.mensagem, valor


def test_prefixo_repetido_na_mesma_familia_e_recusado():
    """Dois blocos iguais geram dois route-filter e duas linhas network do
    mesmo prefixo, que o equipamento recusa ao colar."""
    erros = validate.validar_blocos(
        {"v4": [bloco(), bloco()], "v6": []})
    assert erros[0].campo == "blocos_v4"
    assert "repetido" in erros[0].mensagem


def test_origem_fora_da_tabela_do_tipo_e_aviso_nos_tipos_sem_conferencia():
    """O peer de upstream/ix/pni nao confere a origem contra a tabela do tipo.

    O grupo confere (validar_grupo), e o peer so olha a faixa 1xxx, e so nos
    tipos downstream. A assimetria esta registrada no proprio codigo como
    mudanca separada, e esta e ela: aviso, e nao erro, porque fechar trancaria
    cadastro que ja existe (tres upstreams do peers.yaml real).
    """
    for tipo, permitidas in (("upstream", (1400, 1900)),
                             ("ix", (1300, 1200, 1900)),
                             ("pni", (1500, 1200, 1900))):
        # o route_limit do um_peer e o do cliente (50), e nao o da tabela do
        # tipo: sem alinhar, o aviso do route_limit entra na lista e o assert
        # de lista exata deixa de falar so da origem
        limite = plan.ROUTE_LIMIT[tipo]
        fora = validate.avisos(um_peer(tipo=tipo, origem=1100,
                                       route_limit=limite), [])
        assert [e.campo for e in fora] == ["origem"], tipo
        assert "nao esta na tabela do %s" % tipo in fora[0].mensagem
        assert str(permitidas[0]) in fora[0].mensagem

        dentro = validate.avisos(um_peer(tipo=tipo, origem=permitidas[0],
                                         route_limit=limite), [])
        assert dentro == [], (tipo, "origem da tabela nao pode avisar")


def test_origem_no_downstream_nao_ganha_aviso_novo():
    """Nos downstream a faixa 1xxx ja e erro no validar, e nao aviso aqui.

    O valor e o 1400, e nao um dos que a tabela do cliente usa (1100, 1110,
    1120, 1130): com um valor de dentro da tabela o caso passava com a guarda
    do `avisos` e sem ela, porque o que a guarda decide e sobre o TIPO do
    peer, e nao sobre o valor. O 1400 e o que prova: ele esta fora da tabela
    do cliente, entao sem a guarda sairia o aviso ambar ("origem 1400 nao
    esta na tabela do cliente") por cima do erro vermelho que o validar ja
    da no downstream.
    """
    assert validate.avisos(um_peer(tipo="cliente", origem=1400), []) == []


def test_a_colisao_de_token_aponta_o_campo_onde_o_token_nasce():
    """Token repetido: o erro aponta o campo que resolve, e nao o ASN sempre.

    O token e `apelido or str(asn)`. Com apelido, e ele que colide: apontar o
    ASN mandava o operador trocar um campo que nao resolve, e o erro continuava
    depois da troca, culpando o ASN de novo. Sem apelido, o token e o ASN, e
    quem resolve e dar um apelido: o campo do erro e o apelido, e a mensagem
    diz isso, em vez de mandar mexer num ASN que pode muito bem repetir (um
    mesmo cliente em dois POPs e dois peers legitimos).
    """
    com_apelido = um_peer(id=1, apelido="ALT", nome="ALT", tipo="upstream",
                          asn=53062)
    copia = um_peer(id=2, apelido="ALT", nome="ALT", tipo="upstream", asn=64500)
    erros = validate.validar(copia, [com_apelido], grupos=[])
    assert [(e.campo, e.mensagem) for e in erros if "token" in e.mensagem] == [
        ("apelido", "o apelido ALT ja e o token do peer ALT")]

    sem_apelido = um_peer(id=3, apelido="", nome="UP A", tipo="upstream",
                          asn=53062)
    repetido = um_peer(id=4, apelido="", nome="UP B", tipo="upstream",
                       asn=53062)
    erros = validate.validar(repetido, [sem_apelido], grupos=[])
    assert [(e.campo, e.mensagem) for e in erros if e.campo == "apelido"] == [
        ("apelido",
         "o ASN 53062 ja e o token do peer UP A: de um apelido a este peer")]


def test_politica_de_apontando_para_peer_inexistente_e_erro():
    p = um_peer(politica_de=99)
    assert "politica_de" in campos(validate.validar(p, []))


def test_politica_de_exige_o_mesmo_tipo():
    outro = um_peer(id=2, tipo="upstream", asn=268127, classe=None,
                    aprendizado=3100, prefixos={"v4": [], "v6": []})
    p = um_peer(politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [outro]))


def test_politica_de_exige_o_mesmo_asn():
    outro = um_peer(id=2, asn=9999)
    p = um_peer(politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [outro]))


def test_a_origem_tem_que_ser_dona_da_propria_politica():
    # corrente: a origem nao pode reaproveitar de ninguem. Sem isto o nome
    # do objeto vira uma cadeia para resolver, e o render teria que seguir
    # o ponteiro ate o fim
    meio = um_peer(id=2, politica_de=3)
    fim = um_peer(id=3)
    p = um_peer(politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [meio, fim]))


def test_a_origem_nao_pode_ser_membro_de_grupo():
    # membro de grupo nao tem os filtros no proprio bloco: eles sao do
    # grupo, e o bloco do membro so referencia o group
    grupo = Grupo(id=1, nome="CLIENTES", tipo="cliente", asn=268127,
                  classe="residencial", origem=1110, pop=2001)
    origem = um_peer(id=2, grupo_id=1, prefixos={"v4": [], "v6": []})
    p = um_peer(politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [origem], grupos=[grupo]))


def test_o_peer_nao_pode_reaproveitar_de_si_mesmo():
    p = um_peer(id=2, politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [p]))


def test_a_autoreferencia_e_recusada_no_caminho_da_api():
    """A API manda dois objetos: `anterior` e o registro da lista, e `peer`
    e o novo, construido do formulario. Comparar por identidade so com o
    `peer` deixava a regra inerte: o id do formulario casa com o
    `anterior`, e `origem is peer` nunca e verdade. O teste passa a forma
    que o validar recebe de verdade, e nao o mesmo objeto duas vezes.
    """
    anterior = um_peer(id=2, nome="NETMAC")
    peer = um_peer(id=2, nome="NETMAC", politica_de=2)
    assert "politica_de" in campos(validate.validar(peer, [anterior],
                                                    anterior=anterior))


def test_a_origem_com_asn_em_branco_da_erro_e_nao_estoura():
    # o de_dict nao converte nada, entao um registro editado a mao com o asn
    # em branco chega aqui como None: com o "%d" na mensagem, o None saia como
    # TypeError no lugar do 422
    origem = um_peer(id=2, asn=None)
    p = um_peer(politica_de=2)
    assert "politica_de" in campos(validate.validar(p, [origem]))


def test_nao_pode_reaproveitar_e_estar_em_grupo_ao_mesmo_tempo():
    grupo = Grupo(id=1, nome="CLIENTES", tipo="cliente", asn=268127,
                  classe="residencial", origem=1110, pop=2001)
    p = um_peer(id=2, grupo_id=1, politica_de=3)
    origem = um_peer(id=3)
    assert "politica_de" in campos(validate.validar(p, [origem], grupos=[grupo]))


def test_o_caso_bom_nao_acusa_nada():
    origem = um_peer(id=1, nome="NETMAC")
    backup = um_peer(id=2, nome="NETMAC-BKP", politica_de=1,
                     sessoes={"v4": {"local": "198.51.100.9",
                                     "remoto": "198.51.100.10"}, "v6": {}})
    assert "politica_de" not in campos(validate.validar(backup, [origem]))


# --- a community na linha do prefixo do peer ----------------------------


def com_prefixo(*blocos):
    return um_peer(prefixos={"v4": list(blocos), "v6": []})


def erros_do_prefixo(communities):
    return validar(
        com_prefixo(Bloco(prefixo="45.169.232.0/22", communities=communities)),
        [])


def test_o_1xx_vale_no_prefixo_do_peer():
    """O APPLY-CUSTOMER-LP le o 1xx no import da sessao, e e por isso que
    ele entra aqui e nao no bloco proprio."""
    assert erros_do_prefixo(["64512:104"]) == []


def test_a_mesma_tabela_do_bloco_proprio_vale_no_prefixo_do_peer():
    for valor in ("64512:673", "64512:4:14840", "64512:301", "64512:2000"):
        erros = erros_do_prefixo([valor])
        assert [e.campo for e in erros] == ["prefixos"], valor
    assert erros_do_prefixo(["64512:200", "64512:211", "64512:5070",
                             "64512:613"]) == []


def test_o_intervalo_antes_do_prefixo_e_recusado():
    """`138.97.60.0/22-21` nao alcanca nada: o intervalo comeca no proprio
    prefixo."""
    peer = com_prefixo(Bloco(prefixo="138.97.60.0/22", ate=21,
                             communities=["64512:210"]))
    (erro,) = validar(peer, [])
    assert erro.campo == "prefixos"
    assert "-21" in erro.mensagem


def test_o_intervalo_acima_do_teto_avisa_sem_recusar():
    peer = com_prefixo(Bloco(prefixo="138.97.60.0/22", ate=25,
                             communities=["64512:210"]))
    assert validar(peer, []) == []
    (aviso,) = validate.avisos(peer, [])
    assert aviso.campo == "prefixos"
    assert "-25" in aviso.mensagem


def test_o_mesmo_prefixo_com_intervalos_diferentes_nao_e_repetido():
    """Exato e com intervalo sao dois alcances, e por isso dois
    tratamentos."""
    peer = com_prefixo(
        Bloco(prefixo="138.97.60.0/22", communities=["64512:210"]),
        Bloco(prefixo="138.97.60.0/22", ate=24, communities=["64512:211"]))
    assert validar(peer, []) == []


def test_o_prefixo_repetido_com_o_mesmo_intervalo_e_recusado():
    peer = com_prefixo(
        Bloco(prefixo="45.169.232.0/22", communities=[]),
        Bloco(prefixo="45.169.232.0/22", communities=["64512:210"]))
    (erro,) = validar(peer, [])
    assert erro.campo == "prefixos"
    assert "prefixo repetido" in erro.mensagem


def test_o_prefixo_mais_longo_que_o_teto_avisa_sem_recusar():
    peer = com_prefixo(Bloco(prefixo="45.169.232.0/25", communities=[]))
    assert validar(peer, []) == []
    (aviso,) = validate.avisos(peer, [])
    assert aviso.campo == "prefixos"
    assert "/25" in aviso.mensagem


def test_o_prefixo_no_teto_nao_avisa():
    peer = com_prefixo(Bloco(prefixo="45.169.232.0/24", communities=[]))
    assert validate.avisos(peer, []) == []


def test_o_grupo_recusa_a_linha_com_community():
    grupo = um_grupo(prefixos={"v4": ["45.169.232.0/22 64512:210"], "v6": []})
    (erro,) = validar_grupo(grupo, [grupo], [], anterior=grupo)
    assert erro.campo == "prefixos"
    assert "peer avulso" in erro.mensagem


def test_o_prefixo_do_peer_usa_o_namespace_da_rede():
    """Com asn_politica declarado, o que vale e 65532:673, e nao 64512:673."""
    rede = plan.Rede(asn=264130, politica=65532)
    peer = com_prefixo(Bloco(prefixo="45.169.232.0/22",
                             communities=["65532:673"]))
    (erro,) = validar(peer, [], rede=rede)
    assert "classe 7" in erro.mensagem
    assert validar(peer, [], rede=plan.Rede()) == []


def test_o_grupo_aceita_a_linha_marcada_pela_consulta():
    """A marca do ausente e escrita pela consulta ao IRR, e o salvamento
    ignora o que vem depois dela: manter o prefixo que saiu do IRR e a linha
    continuar, e a decisao e do operador. O que a recusa do grupo barra e a
    community de verdade, nao a marca."""
    grupo = um_grupo(prefixos={
        "v4": ["45.169.240.0/24  !- nao veio na consulta ao IRR"], "v6": []})
    assert validar_grupo(grupo, [grupo], [], anterior=grupo) == []


def test_tabela_fora_da_lista_e_erro_no_downstream():
    for valor in ("", "PARCIAL", "transito"):
        assert "tabela" in campos(validar(um_peer(tabela=valor), [])), valor
    for valor in plan.TABELAS:
        assert "tabela" not in campos(validar(um_peer(tabela=valor), [])), valor


def test_tabela_fora_da_lista_e_erro_no_grupo_de_downstream():
    g = um_grupo(tabela="tudo")
    assert "tabela" in campos(validar_grupo(g, [g], [], anterior=g))
    g = um_grupo(tabela="parcial")
    assert "tabela" not in campos(validar_grupo(g, [g], [], anterior=g))


def test_tabela_e_ignorada_fora_do_downstream():
    # o campo so e lido no export de downstream; o formulario nem o grava
    # nos outros tipos, mas um yaml editado a mao nao pode travar o upstream
    peer = um_peer(tipo="upstream", classe=None, aprendizado=3000, tabela="xyz")
    assert "tabela" not in campos(validar(peer, []))


def test_sessao_sem_rota_nenhuma_e_aviso_e_nao_erro():
    peer = um_peer(default_route=False, tabela="nenhuma")
    assert "tabela" not in campos(validar(peer, []))
    assert "tabela" in campos(validate.avisos(peer, []))


def test_sem_aviso_quando_a_sessao_recebe_alguma_coisa():
    assert "tabela" not in campos(validate.avisos(
        um_peer(default_route=True, tabela="nenhuma"), []))
    assert "tabela" not in campos(validate.avisos(
        um_peer(default_route=False, tabela="parcial"), []))


def test_membro_e_quem_reaproveita_nao_avisam_sessao_sem_rota():
    # a tabela deles vem do grupo ou da origem; a gravada no proprio peer
    # nao chega a filtro nenhum
    membro = um_peer(default_route=False, tabela="nenhuma", grupo_id=3)
    copia = um_peer(default_route=False, tabela="nenhuma", politica_de=0)
    assert "tabela" not in campos(validate.avisos(membro, []))
    assert "tabela" not in campos(validate.avisos(copia, []))


def test_peer_externo_nao_carimba_origem_anunciavel():
    # a parcial e o EXPORT-SANITY selecionam pela marca de origem: um upstream
    # carimbando 1000 ou 11xx sairia como rota propria ou de cliente
    for tipo, extra in (("upstream", {}), ("ix", {"ix_id": 1}),
                        ("pni", {"ap_allowed": ["64500"]})):
        for origem in (1000, 1100, 1130):
            peer = um_peer(tipo=tipo, classe=None, aprendizado=3000,
                           origem=origem, **extra)
            assert "origem" in campos(validar(peer, [])), (tipo, origem)


def test_peer_externo_com_a_origem_do_tipo_passa():
    for tipo, origem, extra in (("upstream", 1400, {}), ("ix", 1300, {"ix_id": 1}),
                                ("pni", 1500, {"ap_allowed": ["64500"]})):
        peer = um_peer(tipo=tipo, classe=None, aprendizado=3000,
                       origem=origem, **extra)
        assert "origem" not in campos(validar(peer, [])), tipo


def test_membro_com_default_gravada_e_grupo_sem_default_avisa():
    grupo = um_grupo(id=3, default_route=False)
    membro = um_peer(grupo_id=3, default_route=True)
    assert "default_route" in campos(validate.avisos(membro, [], grupos=[grupo]))
    grupo.default_route = True
    assert "default_route" not in campos(validate.avisos(membro, [], grupos=[grupo]))
