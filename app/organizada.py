"""A config inteira organizada por tipo de objeto.

O texto de cada secao ja vem pronto do render.py; o que mora aqui e o corte
desse texto por objeto e a remontagem por tipo, para o arquivo do "baixar
tudo" sair na ordem de um backup do equipamento: os sets, os route-filters,
as estaticas e um `bgp` so com todas as sessoes.

Nada disto encosta no que o render grava em out/ nem nas secoes da tela: os
arquivos de la continuam sendo o bloco de cada registro, inteiro e colavel
sozinho.
"""

import re

from app.modelos_api import SecaoConfig

# O cabecalho que todo bloco do render repete. Aqui ele sai uma vez, no topo:
# repetido quarenta e oito vezes ele nao diz nada sobre o objeto de baixo. A
# constante casa com o texto dos templates/*.j2, e nao e uma copia deles - um
# cabecalho novo la faz este parar de casar, e o teste do cabecalho unico e
# quem avisa.
CABECALHO = "# gerado por bgpgen - nao editar a mao"

# As listas do PLANO: o que o render abre com `xpl <isto> <nome>` e fecha com
# `end-list`
SETS = ("ip-prefix-list", "ipv6-prefix-list", "as-path-list",
        "community-list", "large-community-list")

# O marcador do blocos.txt, o unico lugar que abre uma familia sem passar por
# um `bgp`: as linhas `network` de cada familia saem embaixo dele
MARCA_FAMILIA = re.compile(r"^# --- dentro de (ipv4|ipv6)-family unicast ---$")

# O rotulo de cada grupo: o que vai no comentario que o abre, e o titulo da
# secao. O do bgp sai do ASN, e por isso nao esta aqui
ROTULOS = {
    "sets": ("sets e listas", "Sets e listas"),
    "filtros": ("route-filters", "Route-filters"),
    "estaticas": ("estaticas", "Estaticas"),
}


def organizar(secoes, asn):
    """As secoes da config inteira, reagrupadas por tipo de objeto.

    A ordem dos grupos e a das dependencias: as listas primeiro, que os
    filtros citam; os filtros depois; as estaticas, que nao dependem de
    ninguem; e o `bgp` por ultimo, que cita os filtros. Dentro de cada grupo a
    ordem e a das secoes, e e ela que mantem o grupo antes dos membros que
    herdam dele e a base antes de tudo.
    """
    grupos = {chave: [] for chave in ROTULOS}
    nivel, v4, v6 = [], [], []
    for secao in secoes:
        for tipo, linhas in _objetos(secao.texto):
            if tipo == "bgp":
                # o `bgp` chega com o cabecalho do peer colado nele quando o
                # bloco nao tem filtro proprio, que e o caso do membro de grupo
                # e do peer que reaproveita: o corte procura a linha do bgp, e
                # nao a posicao zero
                inicio = next(i for i, linha in enumerate(linhas)
                              if linha.startswith("bgp "))
                partes = _reparte_bgp(linhas[inicio + 1:])
                # os comentarios ficam onde estavam: junto das linhas de nivel
                # do dono deles
                nivel.extend(linhas[:inicio])
                nivel.extend(partes[0])
                v4.extend(partes[1])
                v6.extend(partes[2])
            elif tipo in ("familia-v4", "familia-v6"):
                (v4 if tipo == "familia-v4" else v6).extend(
                    linha.strip() for linha in linhas)
            else:
                grupos[tipo].append("\n".join(linhas))

    montadas = []
    for chave, (rotulo, titulo) in ROTULOS.items():
        if grupos[chave]:
            montadas.append(_secao(chave, rotulo, titulo,
                                   "\n\n".join(grupos[chave])))
    if nivel or v4 or v6:
        montadas.append(_secao("bgp", "bgp %s" % asn, "bgp %s" % asn,
                               _texto_bgp(asn, nivel, v4, v6)))
    if montadas:
        # o cabecalho do render e do arquivo, e nao de uma secao: ele abre o
        # que o navegador salva, que e a juncao de todas
        primeira = montadas[0]
        montadas[0] = SecaoConfig(
            chave=primeira.chave, titulo=primeira.titulo,
            texto=CABECALHO + "\n\n" + primeira.texto)
    return montadas


def _secao(chave, rotulo, titulo, corpo):
    return SecaoConfig(chave=chave, titulo=titulo,
                       texto="# ==== %s ====\n\n%s" % (rotulo, corpo))


def _grupo_da_linha(linha):
    """O grupo do objeto que comeca nesta linha, ou None se ela e corpo do
    objeto de cima."""
    if linha.startswith("xpl route-filter "):
        return "filtros"
    if linha.startswith("xpl ") and linha.split()[1] in SETS:
        return "sets"
    if linha.startswith(("ip route-static ", "ipv6 route-static ")):
        return "estaticas"
    if linha.startswith("bgp "):
        return "bgp"
    return None


def _objetos(texto):
    """Os objetos do texto, na ordem, cada um com os comentarios que o
    antecedem.

    O corte e pelo comeco do objeto, e nao pelo fim: `end-list` e `end-filter`
    fecham os dois tipos de lista e de filtro, mas quem diz o que comeca sao as
    linhas da coluna 0 - o corpo de um filtro tem linha de tudo quanto e jeito,
    e so o objeto de fora comeca sem espaco na frente.
    """
    objetos = []
    comentarios = []
    for linha in texto.splitlines():
        if not linha.strip():
            continue
        marca = MARCA_FAMILIA.match(linha)
        if marca:
            objetos.append(("familia-v%s" % marca.group(1)[-1], []))
            comentarios = []
            continue
        if linha.startswith("#"):
            # o cabecalho repetido fica de fora; quem o poe de volta e o
            # organizar, uma vez so
            if linha != CABECALHO:
                comentarios.append(linha)
            continue
        grupo = _grupo_da_linha(linha)
        if grupo is None:
            # linha de corpo: o que estava pendente e comentario de dentro
            # deste objeto, e fica com ele, e nao com o proximo
            if objetos:
                objetos[-1][1].extend(comentarios + [linha])
            comentarios = []
            continue
        objetos.append((grupo, comentarios + [linha]))
        comentarios = []
    return objetos


def _reparte_bgp(corpo):
    """O corpo de um `bgp <ASN>`, depois da linha dele, em (nivel, v4, v6).

    O que separa as partes sao as linhas de familia do proprio texto, e nao a
    indentacao: o bloco do peer abre a familia no meio dele, e o do blocos.txt
    abre sem `bgp` nenhum na frente - por isso o marcador de familia do
    blocos.txt tambem cai aqui.
    """
    nivel, v4, v6 = [], [], []
    destino = nivel
    for linha in corpo:
        texto = linha.lstrip()
        if texto == "ipv4-family unicast":
            destino = v4
        elif texto == "ipv6-family unicast":
            destino = v6
        else:
            destino.append(texto)
    return nivel, v4, v6


def _texto_bgp(asn, nivel, v4, v6):
    """O `bgp` unico, com as sessoes de todo mundo dentro.

    A indentacao e a do arquivo de hoje - um espaco no nivel do bgp, dois
    dentro da familia - e sai daqui normalizada, porque o `network` do
    blocos.txt vem com um espaco so e ficaria torto ao lado dos `peer`.
    """
    partes = ["bgp %s" % asn]
    partes.extend(" %s" % linha for linha in nivel)
    for rotulo, linhas in (("ipv4-family unicast", v4),
                           ("ipv6-family unicast", v6)):
        if not linhas:
            continue
        partes.append("")
        partes.append(" %s" % rotulo)
        partes.extend("  %s" % linha for linha in linhas)
    return "\n".join(partes)
