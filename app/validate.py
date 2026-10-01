"""O que o app recusa antes de gerar.

Toda regra devolve um Erro com o nome do campo, para o formulario marcar
o campo certo em vez de mostrar um aviso solto no topo.
"""

import ipaddress
import re
from dataclasses import dataclass

from app import plan
from app.peers import achar_grupo_id, sem_marca

TOKEN_RE = re.compile(r"^[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?$")
TOKEN_MAX = 12
ASN_MIN, ASN_MAX = 1, 4294967294
ASN_RESERVADOS = (0, 23456, 4294967295)
ASN_PRIVADOS = ((64496, 64511), (64512, 65534),
                (65536, 65551), (4200000000, 4294967294))
# as quatro origens que o PLANO define para cliente: 1100 (transito) mais
# as classes 1110/1120/1130. O CL-ORIGEM-ANUNCIAVEL so casa essas, entao
# um 1xxx fora delas some do anuncio sem erro nenhum no equipamento.
ORIGENS_CLIENTE = tuple(plan.ORIGEM_CLASSE.values())


@dataclass
class Erro:
    campo: str
    mensagem: str


def erros_para_dict(erros):
    """Um erro por campo, e o primeiro que apareceu para aquele campo.

    A ordem da lista e a ordem das checagens, e o primeiro erro e o mais
    perto do valor que o operador digitou: os erros de campo do formulario.py
    vem antes dos do validar, que so ve o que sobrou do int(). Com o dict
    deixando o ultimo vencer, um "abc" no aprendizado de um grupo de
    upstream mostrava "ponto de aprendizado 3xxx obrigatorio" no lugar do
    "valor numerico invalido" do proprio campo.
    """
    saida = {}
    for e in erros:
        saida.setdefault(e.campo, e.mensagem)
    return saida


def erro_de_tabela(alvo):
    """O Erro da tabela fora da lista, para quem le o yaml sem o validar.

    O /saida e a config inteira renderizam o que esta gravado; o salvar ja
    recusa a tabela invalida, mas o arquivo editado a mao nao passa por ele.
    """
    if alvo.tipo in plan.TIPOS_DOWNSTREAM and alvo.tabela not in plan.TABELAS:
        nome = getattr(alvo, "token", None) or alvo.nome
        return Erro("tabela", "tabela recebida invalida em %s: %r"
                    % (nome, alvo.tabela))
    return None


def avisos(peer, peers, rede=None, grupos=(), anterior=None):
    """Coisas que o usuario precisa saber mas que nao impedem gerar."""
    # o Rede so chega ate aqui e nao ate o validar: o que depende do
    # namespace sao os avisos das listas da CL-PEER, e a forma delas e
    # conferida no _valida_communities, que e do plano fixo
    rede = rede if rede is not None else plan.Rede()
    saida = []
    if any(lo <= peer.asn <= hi for lo, hi in ASN_PRIVADOS):
        saida.append(Erro("asn", "ASN privado: confirme que o peer tambem o usa"))
    # a tabela e a unica fonte da sugestao, entao um tipo que nao esta nela
    # nao tem valor a sugerir e o aviso nao sai. Antes o .get vinha seguido de
    # um subscrito no mesmo tipo, e o tipo desconhecido virava KeyError: como
    # o avisos roda no ramo de erro do salvar, o 500 que o erro de tipo tira
    # do render voltava por aqui, sem a tela chegar a mostrar o erro.
    # o teto do confinamento: a linha mais longa que ele nao casa rota
    # nenhuma, porque o PL-CUST para no teto. Aviso e nao erro porque o
    # peers.yaml de hoje aceita essa linha, e virar erro travaria o
    # salvamento de um cadastro que sempre funcionou.
    for fam in plan.FAMILIAS:
        for bloco in peer.prefixos.get(fam) or []:
            if plan.comprimento(bloco.prefixo) > plan.TETO_PREFIXO[fam]:
                saida.append(Erro(
                    "prefixos",
                    "%s e mais longo que o teto /%d do confinamento: a linha "
                    "nao alcanca rota nenhuma"
                    % (bloco.prefixo, plan.TETO_PREFIXO[fam])))
            elif bloco.ate is not None and bloco.ate > plan.TETO_PREFIXO[fam]:
                saida.append(Erro(
                    "prefixos",
                    "%s passa do teto /%d do confinamento: a clausula nao "
                    "alcanca rota nenhuma"
                    % (_linha_do_prefixo(bloco), plan.TETO_PREFIXO[fam])))
    sugerido = plan.ROUTE_LIMIT.get(peer.tipo)
    if sugerido is not None and peer.route_limit != sugerido:
        saida.append(Erro(
            "route_limit",
            "a tabela do plano sugere %d para %s" % (sugerido, peer.tipo)))
    # O grupo confere a origem contra a tabela do proprio tipo e o peer nao
    # (o peer so olha a faixa 1xxx, e so nos tipos downstream). O resultado e
    # um upstream com origem de cliente, que carimba a rota mentindo sobre a
    # procedencia. Aqui e aviso, e nao erro: fechar isso trancaria cadastro
    # que ja existe no peers.yaml, e trocar a origem desses peers e decisao de
    # rede, nao de app (spec 2026-09-27, "Por que a origem vira aviso").
    if peer.tipo not in plan.TIPOS_DOWNSTREAM:
        permitidas = plan.ORIGENS_POR_TIPO.get(peer.tipo, ())
        if peer.origem is not None and permitidas and peer.origem not in permitidas:
            saida.append(Erro(
                "origem",
                "origem %d nao esta na tabela do %s: o plano usa %s"
                % (peer.origem, peer.tipo,
                   ", ".join(str(o) for o in permitidas))))
    # sem default e sem tabela a sessao sobe e nao recebe rota nenhuma. E
    # legitimo para quem so anuncia, e por isso aviso, mas costuma ser a caixa
    # da default desmarcada sem querer. Vale a politica efetiva, e nao o que
    # esta gravado no peer: o membro recebe a default e a tabela do grupo, e
    # quem reaproveita recebe a tabela da origem com a default da propria
    # sessao.
    if peer.tipo in plan.TIPOS_DOWNSTREAM:
        default, tabela = peer.default_route, peer.tabela
        grupo = (achar_grupo_id(list(grupos), peer.grupo_id)
                 if peer.grupo_id is not None else None)
        origem = (next((o for o in peers if o.id == peer.politica_de), None)
                  if peer.politica_de is not None else None)
        if grupo is not None:
            default, tabela = grupo.default_route, grupo.tabela
        elif origem is not None:
            tabela = origem.tabela
        if not default and tabela == "nenhuma":
            saida.append(Erro(
                "tabela", "sem default route e sem tabela, a sessao nao "
                "recebe rota nenhuma"))
    # a default do membro e a do grupo. A caixa gravada no membro vem de
    # antes desta regra; se o grupo nao anuncia, a sessao perde a default
    # na proxima colagem, e o operador precisa saber antes. A tela carrega o
    # membro com a caixa desmarcada, entao quem diz o que estava gravado e o
    # registro anterior, e nao o formulario
    gravada = peer.default_route or (anterior is not None
                                     and anterior.default_route)
    if peer.grupo_id is not None and gravada:
        grupo = achar_grupo_id(list(grupos), peer.grupo_id)
        if grupo is not None and not grupo.default_route:
            saida.append(Erro(
                "default_route", "a default route deste membro vem do grupo "
                "%s, que nao a anuncia: ligue no grupo para manter" % grupo.nome))
    _avisa_communities(peer, saida, rede)
    return saida


def community_valida(community, rede=None):
    """A community esta na faixa do plano, com o namespace da rede."""
    return (rede if rede is not None else plan.Rede()).faixa_ok(community)


# os valores da CL-PEER-<T> vem de contrato e o plano nao os enumera, entao
# o que da para exigir e a forma: aqui so a sintaxe barra, e a faixa fica
# como aviso. fullmatch e nao match com "$": o "$" do re aceita a quebra de
# linha no fim, e um valor colado com \n passaria como valido.
_COMMUNITY_RE = re.compile(r"[0-9]{1,5}:[0-9]{1,5}")
_LARGE_RE = re.compile(r"[0-9]{1,10}(?::[0-9]{1,10}){2}")
# 16 bits por campo na standard, 32 na large (RFC 8092)
_LIMITE_COMMUNITY = 65535
_LIMITE_LARGE = 4294967295


def community_ok(valor):
    """Asn:valor, os dois numericos e cada um dentro de 16 bits."""
    return bool(_COMMUNITY_RE.fullmatch(valor)) and all(
        int(p) <= _LIMITE_COMMUNITY for p in valor.split(":"))


def large_community_ok(valor):
    """Asn:v1:v2, os tres numericos e cada um dentro de 32 bits."""
    return bool(_LARGE_RE.fullmatch(valor)) and all(
        int(p) <= _LIMITE_LARGE for p in valor.split(":"))


def large_no_plano(valor, rede=None):
    """O primeiro campo da large e o namespace da rede.

    E o mesmo campo do alias em standard community, e por isso o `ns` e nao
    o ASN: num plano de 32 bits a large carrega o namespace da politica no
    primeiro campo, e o ASN de verdade no terceiro.
    """
    return valor.split(":")[0] == (rede if rede is not None else plan.Rede()).ns


def _valida_communities(peer, erros):
    """A forma das duas listas da CL-PEER-<T>.

    O valor de dentro vem de contrato, entao o que se exige aqui e so a
    sintaxe. Um valor fora das faixas do plano continua sendo gerado, com
    aviso: barrar seria o gerador decidindo contrato.
    """
    for campo, valores, confere, forma in (
            ("communities", peer.communities, community_ok, "ASN:VALOR"),
            ("large_communities", peer.large_communities,
             large_community_ok, "ASN:V1:V2")):
        for valor in valores or []:
            if not confere(valor):
                erros.append(Erro(campo, "community invalida: %s (esperado %s)"
                                  % (valor, forma)))


# --- blocos proprios --------------------------------------------------

# as acoes do plano que tem ramo em filtro de egress. Sai das tabelas do
# plan.py de proposito: uma acao que ganhe ramo entra aqui sozinha, e nao
# ha segunda lista de verdade para manter em sincronia.
ACOES_LIDAS = frozenset(
    [v for par in plan.NOADV.values() for v in par]
    + list(plan.NOADV_CUST)
    + [v for par in plan.ONLY_NOT.values() for v in par])
CLASSES_6CA_LIDAS = frozenset(plan.CLASSE_6CA.values())
# Os digitos 1 e 9 caem fora da cadeia if/elseif e nao prependam nada, que e
# o mesmo efeito de nao ter community nenhuma. Os dois ficam aceitos porque
# o PLANO publica os dois: o 1 e o P1 explicito, e o 9 e o "default
# explicito, cai no fim da cadeia". O que o documento marca como "ainda sem
# ramo nos filtros de egress" e de 5 a 8, e esses sao recusados.
#
# O digito 0 do 6CA e o caso que sobra, e ele e recusado: o documento o da
# como escopo ("nao anunciar para este destino") e nenhum ramo o le, que e
# a mesma forma do 673 e do large 4:<ASN>. No 5PPA o 0 e outra historia: ali
# ele entra no CL-NOADV do peer e e lido.
DIGITOS_6CA_LIDOS = frozenset((1, 2, 3, 4, 9))
DIGITOS_5PPA_LIDOS = frozenset(range(5))


def _motivo_da_recusa(valor, rede, lido_no_import=False):
    """Por que a community nao serve, ou None se serve.

    So opina sobre o namespace da rede: community de outro AS passa, porque
    o vocabulario do mundo nao da para conferir e o bloco existe justamente
    para carregar a tag da operadora. Dentro do namespace, a pergunta e uma
    so: algum filtro do gerado le este valor? O que nenhum le vira erro
    aqui, e nao um prefixo que anuncia e nao se comporta como pedido.

    `lido_no_import=True` e o prefixo do downstream: ali a rota passa pelo
    import da sessao e o APPLY-CUSTOMER-LP le o 1xx, que e justamente o
    valor que o bloco proprio recusa por nao passar por import nenhum.
    """
    if not valor.startswith(rede.ns + ":"):
        return None
    corpo = valor.split(":", 1)[1]
    if not corpo.isdigit():
        return None
    n = int(corpo)

    # quatro digitos: informativa, ou o alias 5PPA, que e o unico de
    # quatro digitos que carrega acao. A faixa da informativa termina onde o
    # plan.FAIXAS termina, em 9999: o que passa disso nao esta no plano e
    # nenhum filtro le.
    if n >= 1000:
        if not 1000 <= n <= 9999:
            return "faixa sem dono no plano"
        if n == 2000:
            # o 2000 e a marca de "aprendida de fora", e os tres egress
            # externos tem rede de seguranca contra ela: a rota propria para
            # de sair para upstream, IX e PNI, e continua saindo so para
            # cliente, sem nada aparecer na tela. O 200 diz a mesma coisa de
            # proposito, e e lido: o prefixo fica local porque o operador
            # pediu, e nao porque o egress confundiu a rota com full table.
            return ("o 2000 marca rota aprendida de fora, e o egress de "
                    "upstream, IX e PNI recusam a rota que o carrega: use o "
                    "200, que mantem o prefixo local de proposito")
        if not 5000 <= n <= 5999:
            return None
        if n % 10 not in DIGITOS_5PPA_LIDOS:
            return "digito %d sem ramo no egress" % (n % 10)
        return None

    if 100 <= n <= 199:
        if lido_no_import:
            return None
        return ("o 1xx e lido pelo import de cliente, e a rota propria "
                "nao passa por import nenhum: use o local-preference da "
                "propria filtragem de originacao")
    if 200 <= n <= 299:
        if n not in ACOES_LIDAS:
            return "nenhum egress le este 2xx de escopo"
        return None
    if n in (666, 667):
        return None
    if 600 <= n <= 699:
        classe, digito = (n - 600) // 10, n % 10
        if classe not in CLASSES_6CA_LIDAS:
            return ("classe %d sem ramo no egress: o gerado implementa %s"
                    % (classe, ", ".join(str(c) for c in
                                         sorted(CLASSES_6CA_LIDAS))))
        if digito not in DIGITOS_6CA_LIDOS:
            return "digito %d sem ramo no egress" % digito
        return None
    return "faixa sem dono no plano"


def _motivo_da_recusa_large(valor, rede):
    """O mesmo para a large community, que tem tres campos."""
    partes = valor.split(":")
    if len(partes) != 3 or partes[0] != rede.ns or not partes[1].isdigit():
        return None
    n = int(partes[1])
    if n >= 1000:
        # o teto da informativa de large e o mesmo eixo do padrao: o PLANO
        # publica 1000 (origem), 1001 (IX) e 1002 (POP), e o que passa disso
        # nao esta no plano e nenhum filtro le.
        if n > 1002:
            return "faixa sem dono no plano"
        return None
    if n <= 3:
        return None
    if n == 4:
        return ("funcao 4 sem ramo no egress: anunciar somente para um ASN "
                "nao esta implementado, so as funcoes 0, 1, 2 e 3")
    return "funcao %d sem ramo no egress" % n


def _motivo_da_community(valor, rede, lido_no_import=False):
    """A forma da large tem tres campos, e a da standard tem dois."""
    if len(valor.split(":")) == 3:
        return _motivo_da_recusa_large(valor, rede)
    return _motivo_da_recusa(valor, rede, lido_no_import)


def _valida_lista_de_communities(communities, campo, rede, lido_no_import,
                                 erros):
    """A tabela de recusa, para o bloco proprio e para o prefixo do peer."""
    for valor in communities or []:
        if not _forma_ok(valor):
            erros.append(Erro(
                campo, "community invalida: %s (esperado ASN:VALOR ou "
                "ASN:V1:V2)" % valor))
            continue
        motivo = _motivo_da_community(valor, rede, lido_no_import)
        if motivo:
            erros.append(Erro(campo, "%s: %s" % (valor, motivo)))


def _forma_ok(valor):
    """A forma da community: ASN:VALOR ou ASN:V1:V2, com campo numerico.

    Sem esta checagem um valor com tres dois-pontos passa pela tabela de
    faixas, que le so o primeiro campo, chega ao separa_communities, cai na
    lista de standard e vira uma linha de `apply community` que o
    equipamento recusa na hora de colar. As duas funcoes de forma ja
    existem para a CL-PEER do peer, e a checagem aqui e a mesma.
    """
    return community_ok(valor) or large_community_ok(valor)


def validar_blocos(blocos, rede=None):
    """Os erros das duas listas de prefixos do proprio AS.

    O campo do erro e o da familia, que e o nome da textarea no
    formulario, para a tela marcar a caixa certa em vez de avisar solto.
    """
    rede = rede if rede is not None else plan.Rede()
    erros = []
    for fam in plan.FAMILIAS:
        campo = "blocos_%s" % fam
        vistos = set()
        for bloco in blocos.get(fam) or []:
            if bloco.prefixo in vistos:
                erros.append(Erro(campo, "prefixo repetido: %s" % bloco.prefixo))
            vistos.add(bloco.prefixo)
            if not _cidr_ok(bloco.prefixo):
                erros.append(Erro(campo, "prefixo invalido: %s (esperado CIDR)"
                                  % bloco.prefixo))
            if bloco.ate is not None:
                erros.append(Erro(
                    campo, "%s-%d: o intervalo e do prefixo do cliente, e o "
                    "bloco proprio origina o prefixo inteiro"
                    % (bloco.prefixo, bloco.ate)))
            _valida_lista_de_communities(bloco.communities, campo, rede,
                                         False, erros)
    return erros


def _avisa_communities(peer, saida, rede=None):
    rede = rede if rede is not None else plan.Rede()
    if peer.tipo not in plan.TIPOS_COM_APPLY_PEER:
        # o par CL-PEER-<T> / APPLY-PEER-<T> e de cliente, parceiro e
        # upstream. Nos outros dois o quadro nao existe, e um valor guardado
        # aqui nunca chega ao equipamento: sem o aviso ele some sem deixar
        # rastro.
        if peer.communities or peer.large_communities:
            saida.append(Erro(
                "communities",
                "o %s nao usa CL-PEER: a lista nao vai ser emitida" % peer.tipo))
        return
    # o aviso e sobre o valor que o equipamento aceita e o plano nao
    # descreve; o que nao tem sintaxe nenhuma ja saiu como erro acima, e
    # avisar duas vezes pelo mesmo valor so enche a tela.
    #
    # Na standard as duas metades tem faixa conhecida (100-699 e 1000-9999).
    # Na large o campo do meio e codigo de funcao e o ultimo e ASN, entao o
    # que da para conferir e o namespace.
    for valor in peer.communities or []:
        if community_ok(valor) and not community_valida(valor, rede):
            saida.append(Erro(
                "communities",
                "fora do namespace e das faixas do plano: %s" % valor))
    for valor in peer.large_communities or []:
        if large_community_ok(valor) and not large_no_plano(valor, rede):
            saida.append(Erro(
                "large_communities",
                "fora do namespace do plano: %s" % valor))


def _sobrepoe(a, b):
    # CIDR que nao analisa nao sobrepoe nada. Prefixo malformado do
    # proprio peer sai como Erro antes daqui; o do outro peer pertence ao
    # formulario dele, e acusar sobreposicao sem poder comparar seria
    # acusacao falsa.
    try:
        ra = ipaddress.ip_network(a, strict=False)
        rb = ipaddress.ip_network(b, strict=False)
    except ValueError:
        return False
    if ra.version != rb.version:
        return False
    return ra.overlaps(rb)


def _blocos(peer):
    for fam in plan.FAMILIAS:
        for bloco in peer.prefixos.get(fam) or []:
            yield fam, bloco.prefixo


def _cidr_ok(cidr):
    # o cidr_para_xpl exige a barra, e o ip_network sozinho nao exige: um
    # "10.0.0.0" cru analisa como /32 e so estoura na hora de escrever o
    # XPL. A barra e o contrato do formatador, entao a checagem e a mesma.
    if "/" not in cidr:
        return False
    try:
        ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        return False
    return True


def _linha_do_prefixo(bloco):
    """O prefixo como o operador o escreve: `cidr` ou `cidr-ate`.

    E so para as mensagens de erro: quem escreve a linha da tela e o
    formulario, e quem monta a clausula e o plan.
    """
    if bloco.ate is None:
        return bloco.prefixo
    return "%s-%d" % (bloco.prefixo, bloco.ate)


def _valida_prefixos(alvo, erros, rede=None, tratado=False):
    # as duas listas vao para o plan.cidr_para_xpl: o cliente escreve
    # `prefixos`, o upstream escreve `te_prefixos`. A varredura e a mesma
    # para as duas; o campo do erro e que muda. Antes isto valia so no ramo
    # do cliente e so sobre a primeira lista, e um prefixo de TE malformado
    # validava limpo para estourar no render, depois do peer ja gravado.
    #
    # O Grupo herda a varredura pelo `prefixos` e nao tem TE: o getattr
    # deixa a mesma funcao servir os dois, com o campo do erro igual ao do
    # peer.
    #
    # `tratado=True` e o Peer: os itens do `prefixos` sao Bloco, com
    # community e `!-`, e a lista passa pela tabela de recusa com o
    # `lido_no_import`, porque a rota do downstream passa pelo import da
    # sessao. O `te_prefixos` e CIDR em texto nos dois alvos, e continua so
    # com a varredura de CIDR.
    rede = rede if rede is not None else plan.Rede()
    for campo, listas in (("prefixos", alvo.prefixos),
                          ("te_prefixos", getattr(alvo, "te_prefixos", None) or {})):
        for fam in plan.FAMILIAS:
            itens = listas.get(fam) or []
            if tratado and campo == "prefixos":
                vistos = set()
                for bloco in itens:
                    # o alcance e parte da identidade da linha: o prefixo
                    # exato e o com intervalo sao dois tratamentos
                    chave = (bloco.prefixo, bloco.ate)
                    if chave in vistos:
                        erros.append(Erro(campo, "prefixo repetido: %s"
                                          % _linha_do_prefixo(bloco)))
                    vistos.add(chave)
                    if not _cidr_ok(bloco.prefixo):
                        erros.append(Erro(
                            campo, "prefixo invalido: %s" % bloco.prefixo))
                    elif (bloco.ate is not None
                          and bloco.ate < plan.comprimento(bloco.prefixo)):
                        erros.append(Erro(
                            campo, "intervalo antes do prefixo: %s"
                            % _linha_do_prefixo(bloco)))
                    _valida_lista_de_communities(bloco.communities, campo,
                                                 rede, True, erros)
                continue
            for texto in itens:
                if not tratado and campo == "prefixos":
                    # a marca do ausente e da consulta, e o salvamento
                    # ignora: o que a recusa do grupo barra e a community
                    # de verdade, nao o comentario
                    texto = sem_marca(texto)
                    if len(texto.split()) > 1:
                        erros.append(Erro(
                            campo, "o grupo nao aceita community por prefixo: "
                            "o tratamento por prefixo e do peer avulso"))
                        continue
                if not _cidr_ok(texto):
                    erros.append(Erro(campo, "prefixo invalido: %s" % texto))


def _valida_timer(peer, erros):
    k, h = peer.timer_keepalive, peer.timer_hold
    if k is None and h is None:
        return
    if k is None or h is None:
        faltando = "timer_keepalive" if k is None else "timer_hold"
        erros.append(Erro(faltando, "os dois valores do timer andam juntos"))
        return
    if h <= k:
        erros.append(Erro("timer_hold", "hold tem que ser maior que keepalive"))


def _valida_ascii(peer, erros):
    # nome e descricao sao texto livre. A descricao vai inteira para o XPL
    # gerado, e o XPL e escrito em ASCII: um acento que passa aqui so
    # estoura depois, na escrita, longe do campo que o causou.
    for campo in ("nome", "descricao"):
        if not (getattr(peer, campo) or "").isascii():
            erros.append(Erro(campo, "%s so aceita ASCII puro, sem acento" % campo))


NOME_GRUPO_RE = re.compile(r"^[A-Z0-9_]{1,32}$")


def validar_grupo(grupo, grupos, peers, anterior=None):
    erros = []

    if not NOME_GRUPO_RE.match(grupo.nome or ""):
        erros.append(Erro("nome", "nome do grupo: A-Z, 0-9 e _, ate 32 caracteres"))

    if not (0 <= grupo.id <= 99):
        erros.append(Erro("id", "o ID do grupo tem que ficar entre 0 e 99"))
    for outro in peers:
        if outro.id == grupo.id:
            # o espaco e um so: um grupo e um peer no mesmo numero escrevem
            # a mesma community do eixo 5PPA
            erros.append(Erro(
                "id", "ID %d ja usado pelo peer %s" % (grupo.id, outro.nome)))
        if outro.token == grupo.nome:
            # o nome do grupo entra no mesmo lugar do nome de objeto em que
            # entra o token do peer: CUST/UP/IX/PNI-<T>-IMPORT-V4, AP-CUST-<T>,
            # AP-BLOCK-<T>, AP-IX-<T>, CL/LC-NOADV-<T>, CL-PEER-<T>, e o
            # <T> do bloco do grupo e o nome dele. Os dois arquivos sao
            # colados no mesmo equipamento e o ultimo colado vence, entao o
            # nome e o token tem que ser espacos disjuntos, como os ids.
            erros.append(Erro(
                "nome",
                "nome ja usado pelo peer %s: o nome do grupo e o token do "
                "peer viram o mesmo nome de objeto" % outro.nome))

    # o tipo escolhe o template do render, como no peer: um tipo fora de
    # plan.TIPOS grava o grupo para estourar depois, no TemplateNotFound.
    # O formulario so oferece os cinco, mas o POST nao passa por ele.
    if grupo.tipo not in plan.TIPOS:
        erros.append(Erro("tipo", "tipo desconhecido: %s" % grupo.tipo))

    if grupo.tipo in plan.TIPOS_DOWNSTREAM:
        if grupo.classe not in plan.CLASSES_CLIENTE:
            erros.append(Erro("classe", "grupo de %s exige uma classe" % grupo.tipo))
        if grupo.origem is None or grupo.origem not in ORIGENS_CLIENTE:
            erros.append(Erro("origem", "origem obrigatoria, faixa 1xxx do plano"))
        if grupo.pop is None:
            erros.append(Erro("pop", "pop em branco: informe o POP do plano, de 2001 a 2999"))
        elif not (plan.POP_MIN <= grupo.pop <= plan.POP_MAX):
            erros.append(Erro("pop", "POP entre 2001 e 2999"))
        if grupo.tabela not in plan.TABELAS:
            erros.append(Erro(
                "tabela", "tabela recebida: escolha entre %s"
                % ", ".join(plan.TABELAS)))
    else:
        # a default route e servico de downstream, e o comando sai dos
        # macro que os cinco tipos usam: sem esta checagem um POST a mao
        # ligaria o anuncio da default para quem nao pediu.
        if grupo.default_route:
            erros.append(Erro(
                "default_route",
                "default route so em cliente ou parceiro: o %s nao a recebe"
                % grupo.tipo))
        # mais estrito que o caminho do peer de proposito: ORIGENS_POR_TIPO
        # diz quais origens cada tipo carrega, e um grupo de upstream com
        # origem de cliente carimba a rota mentindo sobre a procedencia. O
        # grupo recusa isso; o peer avisa, pela mesma tabela, no avisos().
        permitidas = plan.ORIGENS_POR_TIPO.get(grupo.tipo, ())
        if grupo.origem is None or grupo.origem not in permitidas:
            erros.append(Erro(
                "origem",
                "origem do %s tem que ser uma de %s"
                % (grupo.tipo, ", ".join(str(o) for o in permitidas))))

    if not (0 <= grupo.lp_base <= 65535):
        erros.append(Erro("lp_base", "local preference entre 0 e 65535"))

    if grupo.tipo in ("upstream", "ix"):
        if grupo.aprendizado is None:
            erros.append(Erro("aprendizado", "ponto de aprendizado 3xxx obrigatorio"))
        elif not (plan.APRENDIZADO_MIN <= grupo.aprendizado <= plan.APRENDIZADO_MAX):
            erros.append(Erro("aprendizado", "ponto de aprendizado entre 3000 e 3999"))
    if grupo.tipo == "ix" and not grupo.ix_id:
        erros.append(Erro("ix_id", "sessao de IX exige o ID do IX no PeeringDB"))
    if grupo.tipo == "pni" and not grupo.ap_allowed:
        erros.append(Erro("ap_allowed", "PNI sem allowlist de AS-path nao sobe"))

    # o campo aparece nos cinco tipos nas duas telas - na do grupo o bloco
    # nao tem data-para, e o da tela do peer mostra todos os campos para
    # todos os tipos -, mas na saida quem le o valor e so o filtro de
    # cliente/parceiro. A checagem de formato fica de pe para os cinco: lista
    # vazia passa, e um POST a mao com prefixo torto nao pode chegar ao render
    _valida_prefixos(grupo, erros)
    # a tabela da spec lista as regras POR TIPO; esta e compartilhada, como a
    # faixa do lp_base e o timer. O campo tem o mesmo destino do campo do
    # peer (a CL-PEER-<G>) e o mesmo risco: community malformada passa pelo
    # cadastro e so estoura no equipamento.
    _valida_communities(grupo, erros)
    # o par keepalive/hold sai na sessao do grupo (_macros.j2, sessao_do_grupo),
    # que todo membro herda: um hold menor que o keepalive aqui nao derruba a
    # sessao de um peer, derruba a de todos eles de uma vez. Vale a mesma
    # checagem do peer, inclusive a que exige os dois valores juntos.
    _valida_timer(grupo, erros)

    # o ASN do grupo e opcional - sem ele cada membro declara o proprio -,
    # mas preenchido vale a mesma faixa do peer: ele e o as-number de toda
    # sessao membro, o AP-CUST que confina o as-path do import e o endereco
    # das large-communities dos dois lados. Um ASN fora da faixa aqui nao
    # fica no arquivo do grupo: faneia para tudo isso.
    if grupo.asn is not None and (
            not (ASN_MIN <= grupo.asn <= ASN_MAX)
            or grupo.asn in ASN_RESERVADOS):
        erros.append(Erro("asn", "ASN reservado pela IANA"))

    # nos tres tipos novos ele nao e opcional: o render o formata nos dois
    # sentidos da large-community do tipo (c_large, que faz "64512:%d:%d"),
    # e com o campo vazio isso e TypeError na hora de gerar, depois do grupo
    # ja gravado. Downstream fica de fora de proposito: ali cada membro pode
    # declarar o proprio.
    if grupo.tipo not in plan.TIPOS_DOWNSTREAM and not grupo.asn:
        erros.append(Erro("asn", "grupo de %s exige o ASN" % grupo.tipo))

    tem_prefixo = any(grupo.prefixos.get(f) for f in plan.FAMILIAS)
    if tem_prefixo and not grupo.asn:
        erros.append(Erro(
            "prefixos",
            "grupo com prefixo proprio exige ASN: o filtro usa o ASN do "
            "grupo para o blackhole e o confinamento de as-path"))

    for outro in grupos:
        if outro is anterior:
            continue
        if outro.nome == grupo.nome:
            erros.append(Erro("nome", "nome ja usado pelo grupo %s" % outro.id))

    return _sem_duplicata(erros)


def dono_da_politica(peer):
    """O peer carrega a propria politica no proprio bloco?

    Nao carrega quando esta num grupo (os filtros sao do grupo e o bloco do
    membro so referencia o group) nem quando reaproveita de outro (o bloco
    dele nao define objeto nenhum). E o predicado que a validacao usa para
    saber quem pode ser origem.
    """
    return peer.grupo_id is None and peer.politica_de is None


def validar(peer, peers, anterior=None, grupos=None, rede=None):
    """Os erros que impedem gerar. `anterior` e a entrada que este POST
    substitui, ou None quando ele cria uma nova.

    O `rede` desce ate a tabela de recusa das communities, que compara com
    o namespace da rede e nao com o de fabrica.
    """
    erros = []

    # o tipo escolhe o template do render e as tabelas do plano. O formulario
    # so oferece os quatro, mas o POST nao passa pelo portao do
    # GET /api/peers/novo: um tipo fora da lista gravava o peer para estourar
    # depois, com TemplateNotFound: o mesmo estrago da origem em branco, com o
    # mesmo caminho de gravacao antes do render. O peer_do_formulario ja cai no
    # cliente; esta checagem e o que barra um Peer montado por fora.
    if peer.tipo not in plan.TIPOS:
        erros.append(Erro("tipo", "tipo desconhecido: %s" % peer.tipo))

    if not (ASN_MIN <= peer.asn <= ASN_MAX) or peer.asn in ASN_RESERVADOS:
        erros.append(Erro("asn", "ASN reservado pela IANA"))

    if not (0 <= peer.id <= 99):
        erros.append(Erro("id", "o ID tem que ficar entre 0 e 99"))

    # o token derivado do ASN e so digito, entao nunca desrescreve a regra;
    # quem precisa ser conferido e o apelido que entra no lugar dele
    if peer.apelido and (len(peer.apelido) > TOKEN_MAX
                         or not TOKEN_RE.match(peer.apelido)):
        erros.append(Erro("apelido", "apelido: A-Z, 0-9 e hifen no meio, ate 12 caracteres"))

    _valida_ascii(peer, erros)

    # --- reaproveitamento de politica ---------------------------------
    if peer.politica_de is not None:
        origem = next((o for o in peers if o.id == peer.politica_de), None)
        if origem is None:
            erros.append(Erro("politica_de", "peer de origem nao encontrado"))
        elif origem is anterior or origem is peer:
            # a origem e o registro que este save substitui (ou o proprio
            # peer, quando os dois sao o mesmo objeto). A identidade so com o
            # `peer` deixava a regra inerte no caminho da API: o `peer` e
            # construido do formulario, entao o id do formulario casa com o
            # `anterior`, e `origem is peer` nunca era verdade.
            erros.append(Erro("politica_de", "o peer nao pode reaproveitar de si mesmo"))
        elif origem.tipo != peer.tipo:
            erros.append(Erro(
                "politica_de",
                "o peer %s e de %s, e este e de %s" % (origem.nome, origem.tipo, peer.tipo)))
        elif origem.asn != peer.asn:
            # %s e nao %d por causa do asn da origem: o de_dict nao converte
            # nada, entao um registro carregado a mao com o asn em branco
            # chega aqui como None, e o %d transformaria o 422 em 500
            erros.append(Erro(
                "politica_de",
                "o peer %s e do ASN %s, e este e do ASN %d"
                % (origem.nome, origem.asn, peer.asn)))
        elif not dono_da_politica(origem):
            erros.append(Erro(
                "politica_de",
                "o peer %s nao tem politica propria para ceder: ele %s"
                % (origem.nome,
                   "esta num grupo" if origem.grupo_id is not None
                   else "reaproveita de outro")))
        if peer.grupo_id is not None:
            erros.append(Erro(
                "politica_de",
                "um membro de grupo ja herda a politica do grupo: escolha um "
                "caminho so"))

    if not (0 <= peer.lp_base <= 65535):
        erros.append(Erro("lp_base", "local preference entre 0 e 65535"))

    if peer.route_limit <= 0:
        erros.append(Erro("route_limit", "route-limit tem que ser maior que zero"))

    _valida_timer(peer, erros)
    _valida_prefixos(peer, erros, rede, tratado=True)
    _valida_communities(peer, erros)

    # o parceiro entra aqui junto com o cliente: por baixo da marca de 2091
    # ele e um downstream com prefix-list, e o que o validar cobra e o
    # mesmo. grupo/exige saem calculados antes da checagem de origem
    # abaixo, porque um peer agrupado sem filtro proprio tambem dispensa a
    # origem: ela vem do grupo, igual classe/prefixos/pop.
    grupos = grupos or []
    grupo = None
    exige = True
    # o gate de membro vale para os cinco tipos: fora de downstream o grupo
    # e o mesmo objeto, mudam os campos que ele carrega. Sem ele um peer de
    # upstream, ix ou pni com grupo_id era validado como se estivesse
    # sozinho, e o grupo nunca era encontrado nem conferido.
    if peer.tipo in plan.TIPOS and peer.grupo_id is not None:
        grupo = achar_grupo_id(grupos, peer.grupo_id)
        if grupo is None:
            erros.append(Erro("grupo_id", "grupo nao encontrado"))
        elif grupo.tipo != peer.tipo:
            erros.append(Erro(
                "grupo_id",
                "grupo %s e de %s, nao de %s" % (grupo.nome, grupo.tipo, peer.tipo)))
        elif grupo.asn and peer.asn and peer.asn != grupo.asn:
            # o membro de um grupo com ASN proprio nao escolhe outro: o bloco
            # enxuto do membro omite o as-number porque quem o declara e o
            # grupo, entao um ASN diferente abriria a sessao com o ASN do
            # grupo enquanto a pagina e o cabecalho do arquivo mostram o do
            # membro - e o AP-CUST e as large-communities do grupo ficariam
            # enderecados a um ASN que o cadastro nao reivindica. Vazio
            # segue valendo sempre; ver "Modelo de dados" da spec.
            erros.append(Erro(
                "asn",
                "ASN %d do membro difere do ASN %d do grupo %s"
                % (peer.asn, grupo.asn, grupo.nome)))

        # fora de grupo, ou dentro de um grupo mas com filtro proprio
        # (prefixo ou CL-PEER): as mesmas regras do peer avulso de sempre.
        # Dentro de um grupo sem filtro proprio, esses campos sao do grupo
        # e o peer nao precisa deles.
        exige = peer.tem_filtro_proprio()

    # a origem entra no community de import de todo tipo, sempre por "%d":
    # em branco ela passava pela faixa, que so confere quando ha valor, e
    # estourava no render - depois do peer ja gravado, porque a gravacao vem
    # antes. O formulario preenche o campo com a tabela do plano; esta
    # checagem e o que barra um POST a mao. Um peer agrupado sem filtro
    # proprio fica dispensado, pelo mesmo `exige` de cima.
    if peer.origem is None and exige:
        erros.append(Erro(
            "origem", "origem em branco: informe a origem do plano (1xxx)"))

    if peer.tipo in plan.TIPOS_DOWNSTREAM:
        if exige:
            if peer.classe not in plan.CLASSES_CLIENTE:
                erros.append(Erro("classe", "%s exige uma classe" % peer.tipo))
            if not any(peer.prefixos.get(f) for f in plan.FAMILIAS):
                erros.append(Erro("prefixos", "%s sem prefix-list nao sobe" % peer.tipo))
            if peer.pop is None:
                # o pop nao vem da classe, so a origem vem. Em branco ele
                # passa na faixa, que so confere quando ha valor, e estoura
                # depois, no "%d" que escreve a community de POP no import
                # do downstream.
                erros.append(Erro("pop", "pop em branco: informe o POP do plano, de 2001 a 2999"))
        if peer.origem is not None and peer.origem not in ORIGENS_CLIENTE:
            erros.append(Erro("origem", "origem fora da faixa 1xxx"))
        if peer.pop is not None and not (plan.POP_MIN <= peer.pop <= plan.POP_MAX):
            erros.append(Erro("pop", "POP entre 2001 e 2999"))
        # o portao do export escolhe o ramo pelo valor: fora da lista o
        # filtro sairia sem portao, igual ao full, sem ninguem ter pedido
        if peer.tabela not in plan.TABELAS:
            erros.append(Erro(
                "tabela", "tabela recebida: escolha entre %s"
                % ", ".join(plan.TABELAS)))
    else:
        # a parcial e o EXPORT-SANITY selecionam pela marca de origem: um
        # tipo externo com origem anunciavel sairia como rota propria ou de
        # cliente para outro upstream e para o cliente da parcial
        anunciaveis = {int(c.split(":")[1]) for c in plan.ORIGEM_ANUNCIAVEL}
        if peer.origem in anunciaveis:
            erros.append(Erro(
                "origem", "origem %d e de rota propria ou de cliente: o %s "
                "nao pode usa-la" % (peer.origem, peer.tipo)))
        # a default route e servico de downstream, e o comando sai de um
        # macro que todos os tipos usam: sem esta checagem, um POST a mao
        # ligaria a flag em upstream, IX e PNI, e o bloco sairia anunciando
        # a default para quem nao pediu.
        if peer.default_route:
            erros.append(Erro(
                "default_route",
                "default route so em cliente ou parceiro: o %s nao a recebe"
                % peer.tipo))
        # os tres campos do tipo sao do grupo quando o membro herda tudo:
        # sem o exige, um membro de grupo de ix que nao traz ix_id proprio
        # era recusado por causa de um campo que esta no grupo, e o
        # operador so passava preenchendo no membro o que o grupo ja tem.
        if exige:
            if peer.tipo in ("upstream", "ix") and peer.aprendizado is None:
                erros.append(Erro("aprendizado", "ponto de aprendizado 3xxx obrigatorio"))
            if peer.tipo == "ix" and not peer.ix_id:
                erros.append(Erro("ix_id", "sessao de IX exige o ID do IX no PeeringDB"))
            if peer.tipo == "pni" and not peer.ap_allowed:
                erros.append(Erro("ap_allowed", "PNI sem allowlist de AS-path nao sobe"))
        # a faixa fica fora do exige de proposito: valor presente e fora da
        # faixa e erro do membro tambem, porque o campo e dele quando tem
        # valor. O que o grupo dispensa e o campo em branco, nao o valor torto.
        if peer.aprendizado is not None and not (
                plan.APRENDIZADO_MIN <= peer.aprendizado <= plan.APRENDIZADO_MAX):
            erros.append(Erro("aprendizado", "ponto de aprendizado entre 3000 e 3999"))

    familias = [f for f in plan.FAMILIAS if peer.sessoes.get(f)]
    if not familias:
        erros.append(Erro("sessoes", "configure pelo menos uma familia"))

    for fam in familias:
        sessao = peer.sessoes[fam]
        esperado = 4 if fam == "v4" else 6
        for lado in ("local", "remoto"):
            campo = "sessoes.%s.%s" % (fam, lado)
            valor = sessao.get(lado)
            if not valor:
                erros.append(Erro(campo, "endereco obrigatorio"))
                continue
            try:
                end = ipaddress.ip_address(valor)
            except ValueError:
                erros.append(Erro(campo, "endereco invalido"))
                continue
            if end.version != esperado:
                erros.append(Erro(campo, "endereco nao bate com a familia"))

    # o grupo nao tem "propria entrada" a dispensar aqui: quem esta na frente
    # do operador e o peer, e a colisao e entre as duas listas
    for outro in grupos or []:
        if outro.id == peer.id:
            erros.append(Erro("id", "ID ja usado pelo grupo %s" % outro.nome))
        if outro.nome == peer.token:
            # o mesmo espaco de nomes de objeto que o validar_grupo confere
            # do outro lado: o nome de um grupo e o token de um peer viram o
            # mesmo <T> no nome dos objetos, e o campo do erro e o que o
            # operador pode mudar no peer - o apelido quando ele e o token,
            # o ASN quando o token sai dele.
            erros.append(Erro(
                "apelido" if peer.apelido else "asn",
                "token %s ja e o nome do grupo %s: o token do peer e o nome "
                "do grupo viram o mesmo nome de objeto"
                % (peer.token, outro.nome)))

    # so a propria entrada sai da comparacao; as demais continuam valendo.
    # A propria entrada e o registro que este POST substitui, comparado por
    # identidade, e nao todo mundo que carregue o mesmo id: por id, uma
    # segunda entrada gravada com o mesmo id passaria batido. E o token
    # tambem nao serve: ele e derivado do ASN, entao trocar o ASN o troca
    # junto, a entrada renomeada deixa de ser reconhecida como a propria e o
    # peer aponta conflito contra ele mesmo.
    for outro in peers:
        if outro is anterior:
            continue
        if outro.id == peer.id:
            erros.append(Erro("id", "ID ja usado pelo peer %s" % outro.nome))
        if outro.token == peer.token:
            # O token e `apelido or str(asn)`, e o campo do erro segue de onde
            # ele nasce: com apelido, e o apelido que o operador tem que mexer,
            # e apontar o ASN mandava trocar um campo que nao resolve (a copia
            # do ALT recebeu "ASN ja usado", trocou o ASN e o erro continuou).
            # O ix/pni sem apelido continua no apelido, porque ali o ASN e o
            # do route server e o apelido e a saida.
            if peer.apelido:
                erros.append(Erro(
                    "apelido",
                    "o apelido %s ja e o token do peer %s"
                    % (peer.apelido, outro.nome)))
            elif peer.tipo in ("ix", "pni"):
                erros.append(Erro(
                    "apelido",
                    "apelido obrigatorio: o ASN %d e o do route server e ja "
                    "esta no peer %s" % (peer.asn, outro.nome)))
            else:
                # Sem apelido o token E o ASN, e por isso ele colide: nao ha
                # trava no ASN (dois peers do mesmo cliente sao legitimos), o
                # que nao pode e repetir o token, que e o nome do peer no
                # equipamento e nos arquivos de out/. O campo e o apelido
                # porque e ele que resolve
                erros.append(Erro(
                    "apelido",
                    "o ASN %d ja e o token do peer %s: de um apelido a este "
                    "peer" % (peer.asn, outro.nome)))
        for fam in familias:
            remoto = (peer.sessoes[fam] or {}).get("remoto")
            outro_remoto = (outro.sessoes.get(fam) or {}).get("remoto")
            if remoto and remoto == outro_remoto:
                erros.append(Erro("sessoes.%s.remoto" % fam,
                                  "endereco ja usado pelo peer %s" % outro.nome))
        # Dois clientes diferentes com o mesmo bloco sao conflito ou erro de
        # cadastro. O mesmo cliente em dois links nao: o principal e o backup
        # anunciam os mesmos prefixos por definicao, e ali o bloco repetido e
        # o desenho, nao o defeito. Sem a comparacao do ASN, o segundo link
        # do cliente nao tinha como ser cadastrado.
        #
        # O ASN cru basta como chave: um peer salvo sempre tem ASN de
        # verdade, porque o zero e recusado acima, e o membro de grupo com o
        # campo em branco nao chega a ser gravado.
        if (peer.tipo in plan.TIPOS_DOWNSTREAM
                and outro.tipo in plan.TIPOS_DOWNSTREAM
                and peer.asn != outro.asn):
            for fam_a, a in _blocos(peer):
                for fam_b, b in _blocos(outro):
                    if fam_a == fam_b and _sobrepoe(a, b):
                        erros.append(Erro(
                            "prefixos",
                            "%s sobrepoe %s do peer %s" % (a, b, outro.nome)))

    return _sem_duplicata(erros)


def _sem_duplicata(erros):
    vistos, saida = set(), []
    for e in erros:
        chave = (e.campo, e.mensagem)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(e)
    return saida
