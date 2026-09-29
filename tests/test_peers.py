import pytest

from app import peers as mod
from app import plan


def test_proximo_id_comeca_em_zero_com_a_lista_vazia():
    assert mod.proximo_id([]) == 0


def test_proximo_id_pula_os_ocupados():
    a = mod.Peer(id=0, nome="a", tipo="cliente", asn=1)
    b = mod.Peer(id=2, nome="b", tipo="cliente", asn=2)
    assert mod.proximo_id([a, b]) == 1


def test_proximo_id_estoura_quando_nao_ha_vaga():
    cheio = [mod.Peer(id=i, nome="x", tipo="cliente", asn=i)
             for i in range(100)]
    with pytest.raises(ValueError):
        mod.proximo_id(cheio)


def test_round_trip_do_yaml(tmp_path):
    caminho = tmp_path / "peers.yaml"
    original = mod.Peer(
        id=1, apelido="", nome="Cliente ACME", tipo="cliente",
        asn=268127, classe="residencial", descricao="CLIENTE-AS268127",
        lp_base=300, origem=1110, pop=2001, aprendizado=None, ix_id=None,
        prefixos={"v4": ["45.169.232.0/22"], "v6": []},
        te_prefixos={"v4": [], "v6": []},
        ap_block=[], ap_te=[], ap_allowed=[], ap_prefer=[],
        bfd=True, graceful_restart=True, timer_keepalive=None, timer_hold=None,
        prepend_base=0, route_limit=50,
        sessoes={"v4": {"local": "198.51.100.1", "remoto": "198.51.100.2"}, "v6": {}},
    )
    mod.gravar([original], caminho)
    assert mod.carregar(caminho) == [original]


def test_default_route_atravessa_o_yaml(tmp_path):
    caminho = tmp_path / "peers.yaml"
    mod.gravar([mod.Peer(id=0, nome="Cliente ACME", tipo="cliente",
                         asn=268127, default_route=True)], caminho)
    assert mod.carregar(caminho)[0].default_route is True


def test_o_reaproveitamento_sobrevive_ao_gravar_e_carregar(tmp_path):
    """O `para_dict` lista os campos um a um, entao um campo novo que ele
    nao liste some na gravacao sem erro nenhum: o operador escolhe a origem,
    salva, e o vinculo nao esta mais la. O teste cobre o caminho inteiro, que
    e o unico que pega um campo esquecido na lista."""
    caminho = tmp_path / "peers.yaml"
    mod.gravar([mod.Peer(id=1, tipo="cliente", asn=270620, politica_de=1)],
               caminho)
    assert mod.carregar(caminho)[0].politica_de == 1


def test_default_route_ausente_no_yaml_antigo_e_false():
    # o campo nasceu depois: quem ja tinha peers.yaml fica sem a default
    assert mod.Peer.de_dict({"id": 0, "nome": "x", "asn": 1}).default_route is False


def test_gravar_reescreve_a_lista_inteira(tmp_path):
    caminho = tmp_path / "peers.yaml"
    a = mod.Peer(id=0, nome="a", tipo="cliente", asn=1)
    b = mod.Peer(id=1, nome="b", tipo="cliente", asn=2)
    mod.gravar([a, b], caminho)
    b.nome = "b editado"
    mod.gravar([a, b], caminho)
    lido = mod.carregar(caminho)
    assert lido[1].nome == "b editado"
    assert lido[0].nome == "a"


def test_carregar_de_arquivo_ausente_devolve_lista_vazia(tmp_path):
    assert mod.carregar(tmp_path / "nao_existe.yaml") == []


def test_de_dict_ignora_chave_desconhecida():
    p = mod.Peer.de_dict({"id": 3, "nome": "x", "tipo": "pni",
                          "asn": 64510, "campo_que_nao_existe": 9})
    assert p.id == 3 and p.token == "64510"


def test_de_dict_descarta_o_token_gravado_pela_versao_antiga():
    # o peers.yaml antigo guardava o token na mao, e `token` deixou de ser
    # campo. A chave cai no filtro do de_dict e o token sai derivado do ASN:
    # e assim que o peer de token EXEMPLO com ASN 264130 vira 264130 sem
    # precisar de migracao a parte
    p = mod.Peer.de_dict({"id": 1, "token": "EXEMPLO", "nome": "EXEMPLO-INTERNET",
                          "tipo": "cliente", "asn": 264130})
    assert p.token == "264130"
    assert p.apelido == ""


def test_token_sai_do_apelido_quando_ha_um():
    p = mod.Peer(id=1, apelido="IX-SP", nome="x", tipo="ix", asn=26162)
    assert p.token == "IX-SP"


def test_token_sai_do_asn_quando_o_apelido_esta_vazio():
    p = mod.Peer(id=1, nome="x", tipo="cliente", asn=268127)
    assert p.token == "268127"


def test_arquivo_do_peer(tmp_path):
    # a pasta de saida vem por parametro: o nome continua saindo do token, e
    # o peer nao tem mais um out/ de modulo de onde tirar o resto do caminho
    p = mod.Peer(id=1, nome="x", tipo="cliente", asn=268127)
    assert p.arquivo(tmp_path) == tmp_path / "268127-cliente.txt"


def test_familias_so_as_preenchidas():
    p = mod.Peer(id=1, nome="x", tipo="cliente", asn=1,
                 sessoes={"v4": {"local": "1.1.1.1", "remoto": "1.1.1.2"}, "v6": {}})
    assert p.familias() == ["v4"]


def test_achar_por_token():
    a = mod.Peer(id=0, nome="a", tipo="cliente", asn=1)
    assert mod.achar([a], "1") is a
    assert mod.achar([a], "Z") is None


def test_achar_id_acha_mesmo_com_o_token_trocado():
    # o token muda quando o ASN muda; o id nao
    a = mod.Peer(id=7, nome="a", tipo="cliente", asn=264130)
    assert mod.achar([a], "268127") is None
    assert mod.achar_id([a], 7) is a
    assert mod.achar_id([a], 8) is None


def test_defaults_da_sessao():
    p = mod.Peer()
    assert p.bfd is True
    assert p.graceful_restart is True
    assert p.timer_keepalive is None
    assert p.timer_hold is None


def test_listas_por_familia_nao_sao_compartilhadas_entre_instancias():
    # default_factory, nao um dict no corpo da classe
    a, b = mod.Peer(), mod.Peer()
    a.prefixos["v4"].append("10.0.0.0/8")
    assert b.prefixos["v4"] == []
    assert a.sessoes is not b.sessoes


def test_as_communities_da_cl_peer_atravessam_o_yaml(tmp_path):
    # a lista vive no cadastro agora: se ela nao voltar do arquivo, o quadro
    # "ao criar o peer" sai vazio e re-colar apaga a lista do equipamento
    caminho = tmp_path / "peers.yaml"
    original = mod.Peer(id=1, nome="Cliente ACME", tipo="cliente", asn=268127,
                        communities=["64512:1500", "64512:1501"],
                        large_communities=["64512:4:264130"])
    mod.gravar([original], caminho)
    lido = mod.carregar(caminho)[0]
    assert lido.communities == ["64512:1500", "64512:1501"]
    assert lido.large_communities == ["64512:4:264130"]
    assert lido == original


def test_communities_ausentes_no_yaml_antigo_sao_listas_vazias():
    # o campo nasceu depois: quem ja tinha peers.yaml fica sem CL-PEER
    p = mod.Peer.de_dict({"id": 0, "nome": "x", "asn": 1})
    assert p.communities == []
    assert p.large_communities == []


def test_as_duas_listas_de_communities_nao_sao_compartilhadas():
    a, b = mod.Peer(), mod.Peer()
    a.communities.append("64512:1500")
    a.large_communities.append("64512:4:1")
    assert b.communities == []
    assert b.large_communities == []


def test_grupo_grava_e_relê_igual(tmp_path):
    caminho = tmp_path / "peers.yaml"
    g = mod.Grupo(id=0, nome="PARCEIROS_CDN", tipo="parceiro", lp_base=300,
                  origem=1100, pop=2001, classe="transito")
    mod.gravar_grupos([g], caminho)
    assert mod.carregar_grupos(caminho) == [g]


def test_round_trip_do_grupo_leva_os_campos_dos_cinco_tipos(tmp_path):
    # o de_dict filtra por __dataclass_fields__, entao campo novo no
    # dataclass entra no round-trip sozinho - o que este teste trava e o
    # para_dict, que e escrito a mao
    caminho = tmp_path / "peers.yaml"
    g = mod.Grupo(
        id=3, nome="TRANSITO", tipo="upstream", asn=14840,
        aprendizado=3100, te_prefixos={"v4": ["1.1.1.0/24"], "v6": []},
        ap_block=[64500], ap_te=[64501], bh_upstream="14840:666",
        communities=["14840:9133"], large_communities=["14840:1:3333"])
    mod.gravar_grupos([g], caminho)
    assert mod.carregar_grupos(caminho) == [g]
    assert mod.carregar_grupos(caminho)[0].te_prefixos == {
        "v4": ["1.1.1.0/24"], "v6": []}


def test_grupo_antigo_no_yaml_carrega_com_os_defaults_novos(tmp_path):
    # o peers.yaml gravado antes desta mudanca nao tem os campos novos
    caminho = tmp_path / "peers.yaml"
    caminho.write_text(
        "grupos:\n- id: 1\n  nome: VELHO\n  tipo: parceiro\n", encoding="ascii")
    g = mod.carregar_grupos(caminho)[0]
    assert (g.aprendizado, g.ix_id, g.communities, g.large_communities) == (
        None, None, [], [])
    assert g.te_prefixos == {"v4": [], "v6": []}


def test_gravar_peers_nao_apaga_grupos_existentes(tmp_path):
    caminho = tmp_path / "peers.yaml"
    g = mod.Grupo(id=0, nome="PARCEIROS_CDN", tipo="parceiro")
    mod.gravar_grupos([g], caminho)
    mod.gravar([mod.Peer(id=0, nome="Cliente", tipo="cliente", asn=64500)], caminho)
    assert mod.carregar_grupos(caminho) == [g]


def test_gravar_grupos_nao_apaga_peers_existentes(tmp_path):
    caminho = tmp_path / "peers.yaml"
    p = mod.Peer(id=0, nome="Cliente", tipo="cliente", asn=64500)
    mod.gravar([p], caminho)
    mod.gravar_grupos([mod.Grupo(id=0, nome="X", tipo="parceiro")], caminho)
    assert mod.carregar(caminho) == [p]


def test_proximo_id_desvia_do_grupo():
    # o eixo 5PPA tem dois digitos (plan.c5ppa), entao peer e grupo
    # disputam os mesmos 100 numeros
    grupos = [mod.Grupo(id=0, nome="A"), mod.Grupo(id=2, nome="B")]
    assert mod.proximo_id([], grupos) == 1


def test_proximo_id_desvia_do_peer_e_do_grupo_juntos():
    a = mod.Peer(id=1, nome="a", tipo="cliente", asn=1)
    g = mod.Grupo(id=2, nome="G")
    assert mod.proximo_id([a], [g]) == 0


def test_proximo_id_sem_grupo_continua_do_zero():
    # chamada de um argumento tem que seguir valendo: os testes de peer
    # que ja existem chamam assim
    assert mod.proximo_id([]) == 0


def test_proximo_id_grupo_estoura_quando_nao_ha_vaga():
    cheio = [mod.Grupo(id=i, nome="G%d" % i) for i in range(100)]
    with pytest.raises(ValueError):
        mod.proximo_id([], cheio)


def test_achar_grupo_por_nome_e_por_id():
    g = mod.Grupo(id=5, nome="PARCEIROS_CDN")
    assert mod.achar_grupo([g], "PARCEIROS_CDN") is g
    assert mod.achar_grupo_id([g], 5) is g
    assert mod.achar_grupo([g], "NADA") is None


def test_grupo_id_grava_e_rele():
    caminho_tmp = "grupo_id_roundtrip.yaml"
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        caminho = pathlib.Path(d) / caminho_tmp
        p = mod.Peer(id=0, nome="X", tipo="parceiro", asn=64500, grupo_id=3)
        mod.gravar([p], caminho)
        assert mod.carregar(caminho)[0].grupo_id == 3


def test_o_peers_yaml_do_repositorio_nao_tem_membro_orfao():
    # leitura do arquivo de verdade, e so leitura: o vinculo do membro com o
    # grupo e pelo id do grupo, entao renumerar um grupo quebra o membro em
    # silencio - foi o que aconteceu quando o PARCEIROS saiu do id 0 e o
    # EXEMPLO-INTERNET ficou apontando para o 0.
    #
    # sem caminho de proposito: o default de carregar/carregar_grupos esta
    # preso ao PEERS_YAML do import, entao o monkeypatch de outro teste nao
    # desvia esta leitura do arquivo do repositorio.
    ids = {g.id for g in mod.carregar_grupos()}
    peers = mod.carregar()
    for peer in peers:
        if peer.grupo_id is not None:
            assert peer.grupo_id in ids, (
                "%s aponta para o grupo %d, que nao existe em %s"
                % (peer.nome, peer.grupo_id, mod.PEERS_YAML))
    # peer e grupo disputam os mesmos 100 ids (MAX_IDS): id repetido nos dois
    # conjuntos faz duas politicas escreverem a mesma community 5PPA
    colisoes = ids & {p.id for p in peers}
    assert not colisoes, (
        "id de peer igual ao de grupo: %s em %s"
        % (sorted(colisoes), mod.PEERS_YAML))


# --- o AS declarado no topo do yaml -------------------------------------
#
# O AS da rede mora no topo do peers.yaml, antes de peers: e grupos:, e o
# carregar_asn devolve o plan.Rede que o resto do app usa no lugar do
# modulo. Ausente, vale o AS de fabrica, e e isso que faz o peers.yaml de
# quem nunca preencheu o campo gerar a config de antes.


def test_sem_asn_no_topo_a_rede_e_a_de_fabrica(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text("peers:\n- id: 0\n  nome: x\n  asn: 64500\n",
                       encoding="ascii")
    rede = mod.carregar_asn(caminho)
    assert rede.asn == plan.ASN_PADRAO
    assert rede.c5ppa(1, 0) == "64512:5010"


def test_arquivo_ausente_carrega_a_rede_de_fabrica(tmp_path):
    assert mod.carregar_asn(tmp_path / "nao_existe.yaml").asn == plan.ASN_PADRAO


def test_o_asn_do_topo_vira_o_namespace_das_communities(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text("asn: 64500\npeers: []\n", encoding="ascii")
    rede = mod.carregar_asn(caminho)
    assert rede.asn == 64500
    # ASN de 16 bits: o namespace das standard e o proprio ASN
    assert rede.politica == 64500
    assert rede.BLACKHOLE == ("65535:666", "64500:666")


def test_o_asn_de_32_bits_carrega_com_o_namespace_declarado(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text("asn: 264130\nasn_politica: 64512\n", encoding="ascii")
    rede = mod.carregar_asn(caminho)
    assert rede.asn == 264130 and rede.politica == 64512
    # o ASN de verdade entra no `bgp` e no `apply as-path`; o namespace fica
    # nas standard, que so tem 16 bits por campo
    assert rede.ASN == "264130"
    assert rede.c5ppa(1, 0) == "64512:5010"
    assert rede.c_large(4, 64500) == "64512:4:64500"


def test_o_asn_de_32_bits_sem_namespace_nomeia_o_arquivo(tmp_path):
    # o arquivo torto e saida do app: quem editar o yaml a mao precisa saber
    # qual arquivo e qual chave
    caminho = tmp_path / "peers.yaml"
    caminho.write_text("asn: 264130\n", encoding="ascii")
    with pytest.raises(ValueError) as erro:
        mod.carregar_asn(caminho)
    assert "asn_politica" in str(erro.value)
    assert str(caminho) in str(erro.value)


def test_gravar_asn_poe_a_chave_no_topo_sem_mexer_no_resto(tmp_path):
    caminho = tmp_path / "peers.yaml"
    mod.gravar([mod.Peer(id=0, nome="Cliente", tipo="cliente", asn=64500)],
               caminho)
    mod.gravar_grupos([mod.Grupo(id=1, nome="G", tipo="cliente")], caminho)

    mod.gravar_asn(64501, caminho=caminho)

    texto = caminho.read_text(encoding="ascii")
    assert texto.startswith("asn: 64501\n")
    # o namespace nao foi declarado, entao vale o proprio ASN e a chave nao
    # existe: um `asn_politica` velho no arquivo seria a tela dizendo uma
    # coisa e o filtro fazendo outra
    assert "asn_politica" not in texto
    assert [p.asn for p in mod.carregar(caminho)] == [64500]
    assert [g.nome for g in mod.carregar_grupos(caminho)] == ["G"]
    assert mod.carregar_asn(caminho).politica == 64501


def test_o_asn_sobrevive_a_gravacao_de_peer_e_de_grupo(tmp_path):
    # o caminho do dia a dia: o AS e declarado uma vez e o cadastro muda
    # muitas. O gravar parte do arquivo lido, entao as chaves do topo que
    # ele nao conhece tem que atravessar
    caminho = tmp_path / "peers.yaml"
    mod.gravar_asn(264130, 64512, caminho)
    mod.gravar([mod.Peer(id=0, nome="Cliente", tipo="cliente", asn=64500)],
               caminho)
    mod.gravar_grupos([mod.Grupo(id=1, nome="G", tipo="cliente")], caminho)
    rede = mod.carregar_asn(caminho)
    assert (rede.asn, rede.politica) == (264130, 64512)
    assert caminho.read_text(encoding="ascii").startswith("asn: 264130\n")


def test_gravar_asn_de_32_bits_grava_o_namespace_junto(tmp_path):
    caminho = tmp_path / "peers.yaml"
    mod.gravar_asn(264130, 64512, caminho)
    texto = caminho.read_text(encoding="ascii")
    assert "asn: 264130" in texto
    assert "asn_politica: 64512" in texto
    assert mod.carregar_asn(caminho).c5ppa(2, 1) == "64512:5021"


def test_gravar_asn_limpa_o_namespace_que_a_tela_nao_mandou(tmp_path):
    caminho = tmp_path / "peers.yaml"
    mod.gravar_asn(264130, 64512, caminho)
    mod.gravar_asn(64500, caminho=caminho)
    texto = caminho.read_text(encoding="ascii")
    assert "asn_politica" not in texto
    assert mod.carregar_asn(caminho).politica == 64500


def test_gravar_asn_de_32_bits_sem_namespace_recusa_antes_de_escrever(tmp_path):
    # o arquivo bom nao pode ser estragado por um POST que nao fecha
    caminho = tmp_path / "peers.yaml"
    mod.gravar_asn(64512, caminho=caminho)
    with pytest.raises(ValueError):
        mod.gravar_asn(264130, caminho=caminho)
    assert mod.carregar_asn(caminho).asn == 64512


def test_tem_filtro_proprio():
    base = dict(id=0, tipo="parceiro", asn=1, grupo_id=1)
    sem_nada = mod.Peer(**base)
    com_prefixo = mod.Peer(**base, prefixos={"v4": ["203.0.113.0/24"], "v6": []})
    com_community = mod.Peer(**base, communities=["64500:100"])
    # os campos que as macros do membro usam contam igual: um membro cujo
    # unico override e uma excecao de TE (ou um ap/ap do tipo) saia sem ramo
    # proprio e herdava a politica inteira do grupo, com o override junto.
    com_te = mod.Peer(**base, te_prefixos={"v4": ["198.51.100.0/24"], "v6": []})
    com_ap_block = mod.Peer(**base, ap_block=["270814"])
    com_ap_te = mod.Peer(**base, ap_te=["264381"])
    com_ap_allowed = mod.Peer(**base, ap_allowed=["64500"])
    com_ap_prefer = mod.Peer(**base, ap_prefer=["15169"])
    # o filtro de export do membro (filtro_upstream_export, chamado por
    # upstream.txt.j2) le prepend_base e bh_upstream alem dos campos de
    # import/lista. Um membro cujo unico override seja um dos dois saia sem
    # ramo proprio e perdia o override em silencio, igual aos de cima.
    com_prepend = mod.Peer(**base, prepend_base=2)
    com_bh = mod.Peer(**base, bh_upstream="14840:666")
    assert sem_nada.tem_filtro_proprio() is False
    assert com_prefixo.tem_filtro_proprio() is True
    assert com_community.tem_filtro_proprio() is True
    assert com_te.tem_filtro_proprio() is True
    assert com_ap_block.tem_filtro_proprio() is True
    assert com_ap_te.tem_filtro_proprio() is True
    assert com_ap_allowed.tem_filtro_proprio() is True
    assert com_ap_prefer.tem_filtro_proprio() is True
    assert com_prepend.tem_filtro_proprio() is True
    assert com_bh.tem_filtro_proprio() is True


def test_blocos_ausentes_no_yaml_carregam_vazios(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text("asn: 264130\npeers: []\n", encoding="utf-8")
    assert mod.carregar_blocos(caminho) == {"v4": [], "v6": []}


def test_gravar_blocos_vazios_nao_cria_a_chave(tmp_path):
    """Quem nunca usou a tela nao pode ganhar um diff no peers.yaml."""
    caminho = tmp_path / "peers.yaml"
    caminho.write_text("asn: 264130\npeers: []\n", encoding="utf-8")
    mod.gravar_blocos({"v4": [], "v6": []}, caminho)
    assert "blocos" not in caminho.read_text(encoding="utf-8")


def test_round_trip_dos_blocos(tmp_path):
    caminho = tmp_path / "peers.yaml"
    blocos = {"v4": [mod.Bloco(prefixo="38.252.64.0/22",
                               communities=["64512:613", "64512:621"])],
              "v6": [mod.Bloco(prefixo="2804:36b4::/32", communities=[])]}
    mod.gravar_blocos(blocos, caminho)
    lido = mod.carregar_blocos(caminho)
    assert lido["v4"][0].prefixo == "38.252.64.0/22"
    assert lido["v4"][0].communities == ["64512:613", "64512:621"]
    assert lido["v6"][0].prefixo == "2804:36b4::/32"
    assert lido["v6"][0].communities == []


def test_o_prefixo_e_normalizado_na_leitura(tmp_path):
    """O nome do filtro e o casamento da reconsulta saem do prefixo
    canonico, entao um CIDR torto no yaml nao pode chegar ate la."""
    caminho = tmp_path / "peers.yaml"
    caminho.write_text(
        "blocos:\n  v4:\n  - prefixo: 38.252.64.7/22\n    communities: []\n",
        encoding="utf-8")
    assert mod.carregar_blocos(caminho)["v4"][0].prefixo == "38.252.64.0/22"


def test_prefixo_invalido_no_yaml_nomeia_o_arquivo(tmp_path):
    caminho = tmp_path / "peers.yaml"
    caminho.write_text(
        "blocos:\n  v4:\n  - prefixo: nao-e-cidr\n    communities: []\n",
        encoding="utf-8")
    with pytest.raises(ValueError) as erro:
        mod.carregar_blocos(caminho)
    assert "blocos.v4" in str(erro.value)


def test_de_dict_do_bloco_ignora_chave_desconhecida():
    b = mod.Bloco.de_dict({"prefixo": "10.0.0.0/8", "acoes": [1]})
    assert b.prefixo == "10.0.0.0/8"
    assert b.communities == []


def test_mesclar_preserva_o_tratamento_do_prefixo_que_ficou():
    salvo = mod.Bloco(prefixo="38.252.64.0/22", communities=["64512:621"])
    visiveis, ausentes = mod.mesclar_blocos([salvo], ["38.252.64.0/22"])
    assert visiveis == [salvo]
    assert visiveis[0].communities == ["64512:621"]
    assert ausentes == []


def test_mesclar_poe_o_prefixo_novo_sem_tratamento():
    visiveis, _ = mod.mesclar_blocos([], ["38.252.64.0/24"])
    assert [(b.prefixo, b.communities) for b in visiveis] == [
        ("38.252.64.0/24", [])]


def test_mesclar_devolve_o_ausente_no_fim_e_marcado():
    salvo = mod.Bloco(prefixo="38.252.66.0/24", communities=["64512:211"])
    visiveis, ausentes = mod.mesclar_blocos([salvo], ["38.252.64.0/22"])
    assert [b.prefixo for b in visiveis] == ["38.252.64.0/22", "38.252.66.0/24"]
    assert ausentes == [salvo]
