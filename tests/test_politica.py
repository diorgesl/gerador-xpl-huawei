"""O documento que o ISP entrega ao cliente: as policies como dados.

O que estes casos protegem e a ligacao com o plan.py. O texto sozinho nao
tem como errar sozinho; o que erra e o numero publicado divergir do numero
que os filtros consomem, e o cliente mandar uma community que nao faz nada.
"""

import re

from app import peers, plan, politica


def upstream(ident, asn, apelido="", grupo=None):
    return peers.Peer(id=ident, tipo="upstream", asn=asn, apelido=apelido,
                      nome=apelido or "UPSTREAM-%d" % asn, grupo_id=grupo)


def grupo(ident, tipo="upstream", asn=None, nome=""):
    return peers.Grupo(id=ident, tipo=tipo, asn=asn, nome=nome or "G%d" % ident)

# A rede do teste tem os dois numeros diferentes de proposito: um documento
# que escrevesse o ASN no lugar do namespace passaria num caso em que os
# dois coincidem
REDE = plan.Rede(264130, 65532)


def texto(doc):
    """Todo o texto do documento, na ordem, para as buscas abaixo."""
    partes = [doc.titulo, doc.subtitulo]
    for secao in doc.secoes:
        partes.append(secao.titulo)
        partes.extend(secao.textos)
        for tabela in secao.tabelas:
            partes.extend(tabela.colunas)
            for linha in tabela.linhas:
                partes.extend(linha)
    return "\n".join(partes)


def communities(doc):
    """As communities que aparecem no documento, standard e large."""
    return set(re.findall(r"\b\d+:\d+(?::\d+)?\b", texto(doc)))


def test_as_communities_saem_no_namespace_da_rede():
    # o mesmo contrato do /base.txt: quem manda no prefixo das standard e o
    # asn_politica do peers.yaml, e nao o 64512 de fabrica
    doc = politica.documento(REDE)
    tudo = texto(doc)
    assert "65532:101" in tudo
    assert "64512:" not in tudo


def test_a_escada_de_preferencia_sai_inteira():
    """Todo degrau do LP_CLIENTE vira uma linha, e nenhum rotulo sobra.

    A prosa dos efeitos e uma lista fixa de cinco, e o zip com a escada do
    plan.py cala quando os dois comprimentos divergem: a linha some do PDF
    sem erro nenhum. Este caso e o que faz o silencio virar falha.
    """
    documento = politica.documento(REDE)
    publicadas = communities(documento)
    escada = {community for community, _lp in REDE.LP_CLIENTE}
    assert escada <= publicadas
    assert len(REDE.LP_CLIENTE) == len(politica.ESCALA_LP)


def test_o_documento_publica_o_que_o_plano_implementa_para_o_cliente():
    """A tabela de anuncio e a lista de egress que o import de cliente usa.

    Se o plano passar a consumir uma community de escopo que o documento nao
    publica, o cliente nao tem como descobrir que ela existe: este caso e o
    que faz a tabela do PDF e a lista do plan.py andarem juntas.
    """
    doc = politica.documento(REDE)
    publicadas = communities(doc)
    implementadas = set(plan.noadv_cust(REDE.ns)) | set(plan.only_not("cliente", REDE.ns))
    assert implementadas <= publicadas


def test_o_prepend_publicado_bate_com_o_c6ca_do_plano():
    """As linhas de prepend sao as que o c6ca monta, classe a classe.

    O que este caso pega e a tabela copiada a mao: um digito trocado aqui
    vira prepend de menos no equipamento, e o cliente nao tem como saber.
    """
    doc = politica.documento(REDE)
    publicadas = communities(doc)
    for classe in plan.CLASSE_6CA.values():
        for digito in plan.DIGITO_PREPEND:
            assert plan.c6ca(classe, digito, REDE.ns) in publicadas


def test_a_large_sai_no_namespace_da_rede():
    """O `<ASN>` do ultimo campo e o do destino, e nao o nosso.

    O cliente escolhe para quem nao anunciar, entao o campo nao tem como
    sair preenchido: o que a rede decide e o namespace, e e ele que o caso
    cobra. A community inteira, com ASN de verdade, e a do alias abaixo.
    """
    assert "65532:4:<ASN>" in texto(politica.documento(REDE))


def test_o_id_publicado_e_o_do_grupo_quando_o_upstream_esta_num_grupo():
    """Quem emite o 5PPA de um upstream agrupado e o bloco do grupo.

    O filtro do membro e o do grupo, e o CL-5PPA que existe no equipamento
    e o do ID do grupo (CL-5PPA-02, no cadastro do ALT_53062). O ID do
    membro nao aparece em configuracao nenhuma: publicado, ensinaria o
    cliente a mandar uma community que morre no filtro.
    """
    doc = politica.documento(
        REDE,
        peers=[upstream(3, 53062, "ALT-PEER1", grupo=2)],
        grupos=[grupo(2, asn=53062, nome="ALT_53062")],
    )
    publicadas = communities(doc)
    for digito in range(5):
        assert plan.c5ppa(2, digito, REDE.ns) in publicadas
        assert plan.c5ppa(3, digito, REDE.ns) not in publicadas
    assert "53062" in texto(doc)


def test_dois_membros_do_mesmo_grupo_viram_uma_linha_so():
    # o grupo e um so, e o equipamento tem um CL-5PPA para ele: duas linhas
    # com o mesmo ID dariam a impressao de dois destinos diferentes
    doc = politica.documento(
        REDE,
        peers=[upstream(3, 53062, "ALT-PEER1", grupo=2),
               upstream(6, 53062, "ALT-PEER2", grupo=2)],
        grupos=[grupo(2, asn=53062, nome="ALT_53062")],
    )
    assert texto(doc).count(plan.c5ppa(2, 0, REDE.ns)) == 1


def test_o_upstream_sem_grupo_continua_publicando_o_proprio_id():
    # o caso do BRDIGITAL: sem grupo, o filtro e o dele e o 5PPA tambem
    doc = politica.documento(REDE, peers=[upstream(0, 14840)])
    assert plan.c5ppa(0, 2, REDE.ns) in communities(doc)


def test_grupo_que_nao_e_de_upstream_nao_entra_na_tabela():
    """Um grupo de cliente ou de parceiro nao emite 5PPA nenhum.

    O numero dele e reservado na mesma faixa de 0 a 99 (a do PLANO, secao
    "Identificador compartilhado entre peer e grupo"), e reservar nao e
    publicar: sem ramo de 5PPA no filtro, o ID dele nao tem o que fazer na
    folha do cliente.
    """
    doc = politica.documento(
        REDE,
        peers=[peers.Peer(id=10, tipo="parceiro", asn=264130, grupo_id=1)],
        grupos=[grupo(1, tipo="parceiro", nome="PARCEIROS")],
    )
    assert plan.c5ppa(1, 2, REDE.ns) not in communities(doc)


def test_sem_tabela_o_exemplo_ensina_o_formato_pelo_c5ppa():
    """Sem upstream cadastrado, o exemplo e a unica coisa que explica o formato.

    Ele sai do c5ppa, que e quem escreve a community no filtro: um exemplo
    digitado a mao ensinaria um numero que o equipamento nao consome.
    """
    assert plan.c5ppa(1, 3, REDE.ns) in communities(politica.documento(REDE))


def test_com_tabela_o_exemplo_sai_de_cena():
    """Com a tabela, o exemplo de ID 01 passaria a mentir.

    O identificador 01 pode nao existir na rede, e a tabela ja traz os de
    verdade: dois numeros na mesma secao, um deles inventado, e o que faz o
    cliente digitar o errado.
    """
    doc = politica.documento(REDE, peers=[upstream(7, 14840)])
    assert plan.c5ppa(1, 3, REDE.ns) not in communities(doc)
    assert plan.c5ppa(7, 3, REDE.ns) in communities(doc)


def test_a_tabela_do_alias_traz_os_upstreams_do_cadastro():
    """O leitor do PDF nao tem como descobrir o ID de um upstream sozinho.

    O alias e `<ns>:5` mais o ID do nosso cadastro mais o digito, e o ID so
    existe aqui dentro: sem a tabela a secao manda o cliente procurar um
    numero que ele nao tem como achar. As cinco acoes saem do c5ppa, que e
    quem escreve a community no filtro do upstream.
    """
    doc = politica.documento(REDE, peers=[upstream(1, 14840)])
    publicadas = communities(doc)
    for digito in range(5):
        assert plan.c5ppa(1, digito, REDE.ns) in publicadas
    # o ASN e o que diz ao cliente qual linha e qual upstream
    assert "14840" in texto(doc)


def test_a_tabela_do_alias_nao_promete_o_que_o_filtro_nao_faz():
    """IX e PNI ficam de fora, ainda que o cadastro tenha os dois.

    O alias so tem ramo no export do upstream: no IX o route server repassa
    o mesmo AS-path a todos os membros, e o PNI ainda nao implementa. Com o
    ID deles publicado, o cliente mandaria uma community que morre no filtro
    e nao teria como saber.
    """
    doc = politica.documento(REDE, peers=[
        upstream(1, 14840),
        peers.Peer(id=2, tipo="ix", asn=26162, nome="IX-SP"),
        peers.Peer(id=3, tipo="pni", asn=22548, nome="CDN"),
    ])
    publicadas = communities(doc)
    assert plan.c5ppa(1, 4, REDE.ns) in publicadas
    assert plan.c5ppa(2, 4, REDE.ns) not in publicadas
    assert plan.c5ppa(3, 4, REDE.ns) not in publicadas


def test_sem_upstream_a_secao_do_alias_vira_a_do_anexo():
    # uma rede que ainda nao cadastrou upstream nao tem o que publicar, e a
    # secao nao pode sair com a tabela vazia nem calada
    assert "anexo" in texto(politica.documento(REDE, peers=[])).lower()


def test_o_id_do_upstream_sai_com_dois_digitos():
    """O ID 10 e o 5101, e nao o 510: o c5ppa e quem sabe o formato.

    Uma coluna montada com "%d" daria `65532:5101` para o ID 1 e `65532:5101`
    para o 10, que sao a mesma community para dois upstreams diferentes.
    """
    doc = politica.documento(REDE, peers=[upstream(10, 61622)])
    publicadas = communities(doc)
    assert plan.c5ppa(10, 1, REDE.ns) == "%s:5101" % REDE.ns
    assert plan.c5ppa(10, 1, REDE.ns) in publicadas
    assert "%s:510" % REDE.ns not in publicadas


def test_o_blackhole_e_o_gshut_nao_seguem_o_namespace():
    """As duas communities de terceiros, que a RFC fixa e o plano nao escolhe.

    O 667 e do plano e sai no namespace da rede; o 666 e o GSHUT sao
    literais, e um documento que os namespaceasse estaria inventando
    community que nenhum filtro consome.
    """
    documento = politica.documento(REDE)
    publicadas = communities(documento)
    assert {"65535:666", "65535:0"} <= publicadas
    assert plan.c(667, REDE.ns) in publicadas


def secao(doc, titulo):
    return next(s for s in doc.secoes if s.titulo == titulo)


def test_a_tabela_de_geografia_e_so_da_faixa_2xxx_e_3xxx():
    """O 1200 e origem, e nao geografia, apesar do nome GEO_PNI no plan.py.

    Ele e o mesmo valor de ORIGEM_NOME para peer bilateral: publicado na
    tabela de geografia, diria ao cliente que a mesma community significa
    duas coisas. A faixa e que separa as duas - 1xxx e origem, 2xxx e 3xxx
    sao o que vem depois dela.
    """
    tabela = secao(politica.documento(REDE),
                   "Informativas que você recebe de nós").tabelas[1]
    for faixa, _significado in tabela.linhas:
        inicio = int(faixa.split(":")[1].split("-")[0])
        assert 2000 <= inicio <= 3999, faixa


def test_o_titulo_traz_o_as_da_rede():
    # o ASN de verdade, e nao o namespace: e ele que o cliente ve no bgp
    assert "264130" in politica.documento(REDE).titulo


def test_o_rotulo_da_origem_propria_cita_o_as_da_rede():
    """E o AS do `bgp`, e nao o namespace das communities.

    Com asn_politica declarado os dois numeros sao diferentes, e o rotulo do
    plan.py dizia o namespace: o cliente leria que o prefixo proprio e do
    AS65532, que nao existe como rede dele.
    """
    documento = politica.documento(REDE)
    assert "AS264130" in texto(documento)
    assert "AS65532" not in texto(documento)


def test_o_documento_avisa_para_nao_misturar_os_dois_blocos():
    # a unica ambiguidade que o PLANO marca como erro de leitura: os dois
    # blocos de escopo na mesma rota
    assert "misture" in texto(politica.documento(REDE)).lower()


def test_o_documento_diz_o_que_o_cliente_pode_receber():
    doc = politica.documento(REDE)
    secao = next(s for s in doc.secoes if s.titulo == "O que você recebe de nós")
    corpo = " ".join(secao.textos)
    for trecho in ("default", "parcial", "IX", "full table"):
        assert trecho in corpo, trecho
    # a default combina com qualquer tabela, e e o que o cadastro novo recebe
    assert "junto com qualquer" in corpo
    # a parcial com IX leva a rota selecionada, e nao todo prefixo do IX
    assert "fica de fora" in corpo
