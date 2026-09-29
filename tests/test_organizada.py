"""A config inteira organizada por tipo de objeto.

O texto que chega aqui e o mesmo que o render ja escreve em out/; o que estes
casos prendem e o corte desse texto por objeto e a remontagem por tipo, para o
arquivo do "baixar tudo" sair na ordem de um backup do equipamento: os sets, os
route-filters, as estaticas e um `bgp` so com todas as sessoes.
"""

from app.modelos_api import SecaoConfig
from app.organizada import organizar


def secao(texto, chave="base", titulo="Bloco base"):
    return SecaoConfig(chave=chave, titulo=titulo, texto=texto)


BASE = """\
# gerado por bgpgen - nao editar a mao
# bloco base: sets e filtros compartilhados do AS64512
# cole isto no F1A antes do bloco de qualquer peer

xpl ip-prefix-list PL-BOGONS-V4
 0.0.0.0 8 le 32
end-list

# PLANO.md / Bogons de AS
xpl as-path-list AP-BOGON-ASN
 0,
 64512
end-list

xpl route-filter IMPORT-SANITY-V4
 call route-filter AP-BOGON-ASN
 finish
end-filter

xpl route-filter EXPORT-SANITY
 if as-path in AP-BOGON-ASN then
  refuse
 endif
 finish
end-filter
"""

PEER = """\
# gerado por bgpgen - nao editar a mao
# peer 0 - cliente - AS268127 - token 268127
# pressupoe o bloco base ja aplicado neste equipamento

xpl ip-prefix-list PL-CUST-268127-V4
 45.169.232.0 22 le 24
end-list

xpl route-filter CUST-268127-IMPORT-V4
 call route-filter IMPORT-SANITY-V4
 finish
end-filter

bgp 64512
 peer 198.51.100.2 description CLIENTE-AS268127
 peer 198.51.100.2 as-number 268127

 ipv4-family unicast
  peer 198.51.100.2 enable
  peer 198.51.100.2 route-filter CUST-268127-IMPORT-V4 import
 ipv6-family unicast
  peer 198.51.100.2 enable
"""

IRMAO = PEER.replace("0 - cliente", "1 - cliente").replace(
    "268127", "269173").replace("198.51.100.2", "198.51.100.6")

BLOCOS = """\
# gerado por bgpgen - nao editar a mao
# blocos proprios do AS64512

ip route-static 38.252.64.0 255.255.252.0 NULL0 preference 250

xpl route-filter ORIGEM-38-252-64-0_22
 apply local-preference 900
 break
end-filter

# --- dentro de ipv4-family unicast ---
 network 38.252.64.0 255.255.252.0 route-filter ORIGEM-38-252-64-0_22
"""


def test_o_base_vira_sets_e_filtros():
    secoes = organizar([secao(BASE)], "64512")

    assert [s.chave for s in secoes] == ["sets", "filtros"]
    assert [s.titulo for s in secoes] == ["Sets e listas", "Route-filters"]
    # o cabecalho do render aparece uma vez, e e na primeira secao: o arquivo
    # e a juncao delas, entao ele fica no topo do que o navegador salva
    assert secoes[0].texto == """\
# gerado por bgpgen - nao editar a mao

# ==== sets e listas ====

# bloco base: sets e filtros compartilhados do AS64512
# cole isto no F1A antes do bloco de qualquer peer
xpl ip-prefix-list PL-BOGONS-V4
 0.0.0.0 8 le 32
end-list

# PLANO.md / Bogons de AS
xpl as-path-list AP-BOGON-ASN
 0,
 64512
end-list"""
    assert secoes[1].texto == """\
# ==== route-filters ====

xpl route-filter IMPORT-SANITY-V4
 call route-filter AP-BOGON-ASN
 finish
end-filter

xpl route-filter EXPORT-SANITY
 if as-path in AP-BOGON-ASN then
  refuse
 endif
 finish
end-filter"""


def test_o_peer_manda_o_bgp_dele_para_o_bgp():
    secoes = organizar([secao(PEER, "peer-0", "Cliente ACME (cliente, AS268127)")],
                       "64512")

    assert [s.chave for s in secoes] == ["sets", "filtros", "bgp"]
    assert secoes[2].titulo == "bgp 64512"
    assert secoes[0].texto == """\
# gerado por bgpgen - nao editar a mao

# ==== sets e listas ====

# peer 0 - cliente - AS268127 - token 268127
# pressupoe o bloco base ja aplicado neste equipamento
xpl ip-prefix-list PL-CUST-268127-V4
 45.169.232.0 22 le 24
end-list"""
    assert secoes[2].texto == """\
# ==== bgp 64512 ====

bgp 64512
 peer 198.51.100.2 description CLIENTE-AS268127
 peer 198.51.100.2 as-number 268127

 ipv4-family unicast
  peer 198.51.100.2 enable
  peer 198.51.100.2 route-filter CUST-268127-IMPORT-V4 import

 ipv6-family unicast
  peer 198.51.100.2 enable"""


def test_as_familias_de_dois_peers_viram_um_bgp_so():
    """O que o arquivo tem hoje e um `bgp` por secao, com a familia repetida
    dentro de cada um. Aqui eles viram um so, e as linhas de cada familia
    saem na ordem das secoes - e por isso o grupo vem antes dos membros."""
    secoes = organizar([secao(PEER, "peer-0", "Cliente ACME"),
                        secao(IRMAO, "peer-1", "Cliente IRMAO")], "64512")

    texto = [s for s in secoes if s.chave == "bgp"][0].texto
    assert texto.splitlines().count("bgp 64512") == 1
    assert texto.count(" ipv4-family unicast") == 1
    assert texto.count(" ipv6-family unicast") == 1
    assert texto.index("198.51.100.2 description") < texto.index("198.51.100.6 description")
    assert texto.index("198.51.100.6 description") < texto.index("ipv4-family unicast")
    assert texto.index("198.51.100.2 enable") < texto.index("198.51.100.6 enable")


def test_o_cabecalho_do_peer_sem_filtro_proprio_vai_com_a_sessao_dele():
    """O membro de grupo e o peer que reaproveita nao tem `xpl` nenhum: o
    cabecalho do bloco chega colado no `bgp`, e e dele - nao do arquivo."""
    texto = """\
# gerado por bgpgen - nao editar a mao
# peer 12 - cliente - AS270620 - token NETMAC-2
# a default route vai para este cliente: confirme que ha um default na tabela

bgp 64512
 peer 100.110.0.78 as-number 270620

 ipv4-family unicast
  peer 100.110.0.78 enable
"""
    secoes = organizar([secao(texto, "peer-12", "NETMAC-2")], "64512")

    assert [s.chave for s in secoes] == ["bgp"]
    assert secoes[0].texto == """\
# gerado por bgpgen - nao editar a mao

# ==== bgp 64512 ====

bgp 64512
 # peer 12 - cliente - AS270620 - token NETMAC-2
 # a default route vai para este cliente: confirme que ha um default na tabela
 peer 100.110.0.78 as-number 270620

 ipv4-family unicast
  peer 100.110.0.78 enable"""


def test_a_estatica_tem_secao_propria_e_o_network_vai_para_a_familia():
    """O `# --- dentro de ipv4-family unicast ---` do blocos.txt e o unico
    lugar que abre uma familia sem passar por um `bgp`; ele vira o proprio
    cabecalho da familia, e nao um comentario solto."""
    secoes = organizar([secao(BLOCOS, "originacao", "Originacao")], "64512")

    assert [s.chave for s in secoes] == ["filtros", "estaticas", "bgp"]
    assert secoes[1].texto == """\
# ==== estaticas ====

# blocos proprios do AS64512
ip route-static 38.252.64.0 255.255.252.0 NULL0 preference 250"""
    assert secoes[2].texto == """\
# ==== bgp 64512 ====

bgp 64512

 ipv4-family unicast
  network 38.252.64.0 255.255.252.0 route-filter ORIGEM-38-252-64-0_22"""
    assert "--- dentro de" not in secoes[2].texto


def test_o_comentario_sem_branco_antes_e_do_objeto_de_baixo():
    """O `# Filtro XPL Import` que o cliente.txt.j2 escreve encosta no
    `end-filter` de cima: sem branco nenhum entre os dois. Ele e do filtro que
    vem depois, e nao do que acabou."""
    texto = """\
xpl route-filter CUST-269173-EXPORT-V4
 finish
end-filter
# Filtro XPL Import
xpl route-filter CUST-269173-IMPORT-V4
 finish
end-filter
"""
    assert organizar([secao(texto)], "64512")[0].texto == """\
# gerado por bgpgen - nao editar a mao

# ==== route-filters ====

xpl route-filter CUST-269173-EXPORT-V4
 finish
end-filter

# Filtro XPL Import
xpl route-filter CUST-269173-IMPORT-V4
 finish
end-filter"""


def test_comentario_no_meio_de_um_objeto_fica_onde_estava():
    """Nenhum template de hoje escreve comentario dentro de um filtro, mas se
    escrever, ele nao pode sumir: o corte nao e licenca para perder linha."""
    texto = """\
xpl route-filter X
# nota de quem mantem o plano
 finish
end-filter
"""
    secoes = organizar([secao(texto)], "64512")
    assert secoes[0].texto == """\
# gerado por bgpgen - nao editar a mao

# ==== route-filters ====

xpl route-filter X
# nota de quem mantem o plano
 finish
end-filter"""


def test_o_cabecalho_repetido_do_render_aparece_uma_vez():
    secoes = organizar([secao(BASE, "base"), secao(PEER, "peer-0"),
                        secao(BLOCOS, "originacao")], "64512")
    texto = "\n\n".join(s.texto for s in secoes)
    assert texto.count("# gerado por bgpgen - nao editar a mao") == 1
    assert texto.startswith("# gerado por bgpgen - nao editar a mao")


def test_sem_objeto_do_tipo_nao_ha_secao():
    """A secao vazia so faria volume num arquivo que ja e longo."""
    secoes = organizar([secao(BASE)], "64512")
    assert "estaticas" not in [s.chave for s in secoes]
    assert "bgp" not in [s.chave for s in secoes]


def test_o_arquivo_todo_e_ascii():
    """Ele vai para o mesmo pipeline do resto do que se cola no equipamento."""
    secoes = organizar([secao(BASE), secao(PEER), secao(BLOCOS)], "64512")
    for s in secoes:
        assert s.texto.isascii(), s.chave
