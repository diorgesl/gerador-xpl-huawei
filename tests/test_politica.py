"""O documento que o ISP entrega ao cliente: as policies como dados.

O que estes casos protegem e a ligacao com o plan.py. O texto sozinho nao
tem como errar sozinho; o que erra e o numero publicado divergir do numero
que os filtros consomem, e o cliente mandar uma community que nao faz nada.
"""

import re

from app import plan, politica

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


def test_o_exemplo_do_alias_e_montado_pelo_c5ppa():
    # o 5013 do PLANO e P3 (dois prepends) no peer de ID 01, e sai da mesma
    # funcao que o filtro usa para escrever a community
    assert plan.c5ppa(1, 3, REDE.ns) in communities(politica.documento(REDE))


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
