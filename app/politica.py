"""As policies da rede como documento, para o ISP entregar ao cliente.

O PLANO.md tem uma secao escrita para o cliente, mas o app nao le o
documento em tempo de execucao - o README promete isso. O que este modulo
faz e montar aquele texto de novo a partir do mesmo plan.py que gera os
filtros, e no namespace do tenant: um texto copiado do PLANO envelheceria
em silencio, e o cliente mandaria uma community que nenhum filtro consome.

O conteudo sai daqui como dados, e nao como texto pronto: quem imprime e o
app/pdf.py. E o que deixa a tabela publicada ser conferida por teste sem
abrir PDF nenhum.

A prosa tem acento, ao contrario do resto do codigo: ela nao passa pelo
TFTP nem pelo diff do equipamento, que sao quem exige ASCII, e sim pela
mesa do cliente. Os rotulos que vem do plan.py (ORIGEM_NOME) chegam sem
acento, porque a mesma tabela serve a pagina XPL, que tem teste de isascii.
"""

from dataclasses import dataclass

from app import plan

# O vocabulario das communities vem do plan.py: os valores, os rotulos do
# efeito e os destinos do prepend sao os mesmos que o formulario oferece na
# busca e que o operador le na tela. Duas copias divergem na primeira vez que
# alguem corrigir uma so.
#
# O que este modulo faz a mais e escrever a frase que o cliente le: o
# plan.FUNCOES_LARGE diz "Prepend 1x", e a tabela daqui diz "Prepend 1x para
# o `<ASN>`", porque no documento o destino e um marcador.
DESTINOS_6CA = plan.DESTINOS_6CA
RESTRINGE = plan.RESTRINGE
SOMENTE = plan.SOMENTE
ESCALA_LP = plan.ESCALA_LP
ACOES_5PPA = plan.ACOES_5PPA


def _funcoes_large():
    """As funcoes da large com o `<ASN>` escrito no lugar do destino."""
    return tuple((funcao, "%s para o `<ASN>`" % nome)
                 for funcao, nome in plan.FUNCOES_LARGE)


FUNCOES_LARGE = _funcoes_large()

TITULO_ALIAS = "Controle por upstream (alias em standard)"


@dataclass(frozen=True)
class Tabela:
    colunas: tuple

    # uma tupla de linhas, cada uma com o mesmo numero de celulas das
    # colunas. Sem dicionario: a ordem e a da tabela impressa, e o cabecalho
    # ja diz o que e cada coluna
    linhas: tuple


@dataclass(frozen=True)
class Secao:
    titulo: str
    textos: tuple
    tabelas: tuple


@dataclass(frozen=True)
class Documento:
    titulo: str
    subtitulo: str
    emitido_em: str

    # o pe de toda folha. Ele mora aqui, e nao no pdf.py, porque e do
    # documento e nao da folha: com o namespace saindo de um `rede` que o
    # gerador recebia a parte, quem o chamasse sem passar o da rede imprimia
    # 64512 embaixo de uma tabela 65532
    rodape: str

    secoes: tuple


def _tabela(colunas, linhas):
    return Tabela(colunas=tuple(colunas),
                  linhas=tuple(tuple(linha) for linha in linhas))


def _preferencia(rede):
    # o zip e com o LP_CLIENTE, e nao com uma lista de numeros escrita aqui:
    # se a escada ganhar um degrau, o numero novo aparece no documento e a
    # prosa e que fica devendo. O teste cobra os dois lados
    linhas = [(community, efeito)
              for (community, _lp), efeito in zip(rede.LP_CLIENTE, ESCALA_LP)]
    return Secao(
        titulo="Controle de preferência",
        textos=(
            "Envie estas communities junto com os seus anúncios. Elas decidem "
            "com que preferência as suas rotas competem com as demais rotas "
            "do AS%s." % rede.ASN,
            "Sem nenhuma delas, as suas rotas entram com a preferência padrão "
            "de cliente: abaixo do nosso trânsito e do nosso peering, e acima "
            "dos clientes que pediram preferência menor.",
        ),
        tabelas=(_tabela(("Envie", "Efeito"), linhas),),
    )


def _anuncio(rede):
    restringe = _tabela(
        ("Envie", "Efeito"),
        [(rede.c(valor), efeito) for valor, efeito in RESTRINGE],
    )
    somente = _tabela(
        ("Envie", "Efeito"),
        [(rede.c(valor), efeito) for valor, efeito in SOMENTE],
    )
    return Secao(
        titulo="Controle de anúncio",
        textos=(
            "O bloco abaixo restringe: a rota sai para todos os destinos, "
            "menos para o indicado.",
            "Não misture os dois blocos na mesma rota: com um destino "
            "proibido e outro exclusivo, o resultado é ambíguo de ler e "
            "difícil de depurar.",
            "O %s vale para todos os clientes, inclusive você. Na prática não "
            "faz diferença: um anúncio que volta para a origem é descartado "
            "pelo seu próprio AS no AS-path." % rede.c(204),
            "O segundo bloco faz o inverso: a rota sai somente para o destino "
            "indicado, e para mais nenhum.",
        ),
        tabelas=(restringe, somente),
    )


def _prepend(rede):
    linhas = []
    for classe in (7, 1, 2, 3, 4, 5):
        digitos = sorted(plan.DIGITO_PREPEND)
        communities = " / ".join(rede.c6ca(classe, d) for d in digitos)
        quantos = ", ".join("%dx" % plan.DIGITO_PREPEND[d] for d in digitos)
        linhas.append((communities,
                       "Prepend %s para %s" % (quantos, DESTINOS_6CA[classe])))
    return Secao(
        titulo="Prepend",
        textos=(
            "O prepend repete o seu AS no AS-path e deixa a rota menos "
            "atrativa para quem a recebe.",
            "O valor terminado em 1 é o P1 explícito: anuncia sem prepend "
            "nenhum, mesmo que outra community tenha pedido prepend. Ele "
            "cobre o caso mais comum, que é prependar para todos os destinos "
            "menos um.",
            "A escala vai até P4, que são %d prepends e é onde os nossos "
            "filtros param. De P5 a P7 não há nada implementado." % (
                plan.PREPEND_IMPLEMENTADO,),
        ),
        tabelas=(_tabela(("Envie", "Efeito"), linhas),),
    )


def _por_asn(rede):
    linhas = [("%s:%d:<ASN>" % (rede.ns, funcao), efeito)
              for funcao, efeito in FUNCOES_LARGE]
    return Secao(
        titulo="Controle por ASN específico",
        textos=(
            "Estas são large communities (RFC 8195), com o ASN de destino no "
            "último campo. Você não precisa avisar ninguém quando a sua lista "
            "muda: trocou de upstream, entrou num IX novo ou fechou um PNI, o "
            "ASN é o mesmo e a community também.",
            "O `4:<ASN>`, anunciar somente para um ASN, existe apenas no "
            "formato large. Não há equivalente em standard community.",
        ),
        tabelas=(_tabela(("Envie", "Efeito"), linhas),),
    )


def fontes_5ppa(peers, grupos):
    """Os identificadores que emitem 5PPA, com os ASNs de cada um.

    Quem emite nao e o cadastro do upstream e sim o bloco de filtro que
    carrega o CL-5PPA, e num upstream agrupado esse bloco e o do grupo: o
    membro nao tem 5PPA nenhum. Por isso o ID publicado e o do grupo, e os
    membros dele nao entram um a um - o equipamento nao tem onde consumir o
    ID deles, e a tabela mostraria destinos que nao existem.

    O ASN do grupo vence o do membro quando o grupo declara um; sem ele, o
    grupo herda dos membros. Os ASNs saem em lista, e nao num texto so,
    porque os dois consumidores os querem de formas diferentes: a tabela do
    PDF junta os de um identificador na mesma celula, e a busca do
    formulario abre uma entrada por ASN, para o numero sair escrito por
    inteiro em cada uma.
    """
    por_id = {g.id: g for g in grupos}
    fontes = {}
    for p in peers:
        if p.tipo != "upstream":
            continue
        g = por_id.get(p.grupo_id) if p.grupo_id is not None else None
        # um grupo que nao seja de upstream nao tem ramo de 5PPA: o numero
        # dele e reservado na faixa, e reservar nao e publicar
        if p.grupo_id is not None and (g is None or g.tipo != "upstream"):
            continue
        ident = p.id if g is None else g.id
        asn = g.asn if g is not None and g.asn else p.asn
        fontes.setdefault(ident, set()).add(asn)
    return [(ident, sorted(asns)) for ident, asns in sorted(fontes.items())]


def _alias(rede, peers, grupos):
    """O alias em standard, com o identificador de cada upstream.

    O identificador e do nosso cadastro, e nao do cliente: sem a tabela a
    secao manda quem le procurar um numero que ele nao tem como descobrir.
    So o upstream entra, porque so o export dele tem ramo de 5PPA - no IX o
    route server repassa o mesmo AS-path a todos os membros, e no PNI o
    alias esta na lista de pendencias do PLANO. Publicar o ID dos dois
    ensinaria o cliente a mandar community que o filtro descarta.
    """
    fontes = fontes_5ppa(peers, grupos)
    textos = [
        "Se o seu equipamento não envia large community, use o alias em "
        "standard: `%s:5` mais os dois dígitos do identificador do upstream "
        "e um dígito da escala." % rede.ns,
    ]
    if not fontes:
        # uma rede sem upstream cadastrado nao tem ID nenhum a publicar, e a
        # secao nao pode sair com uma tabela vazia
        textos.append(
            "O exemplo `%s` é P3, dois prepends, no identificador 01; `%s` é "
            "P1, sem prepend, no identificador 10." % (
                rede.c5ppa(1, 3), rede.c5ppa(10, 1)))
        # sem cadastro a secao nao explica o motivo ao cliente: "a rede nao
        # tem upstream cadastrado" e problema do operador, e a folha que vai
        # para a mesa dele so precisa dizer onde a lista esta
        textos.append(
            "A lista dos identificadores dos nossos upstreams acompanha o "
            "anexo técnico do contrato.")
        return Secao(titulo=TITULO_ALIAS, textos=tuple(textos), tabelas=())
    textos.append(
        "O identificador não é o ASN, e é o da tabela abaixo. Os links de um "
        "mesmo upstream dividem um identificador só, porque dividem o "
        "filtro: a community vale para o conjunto deles. O `4:<ASN>` não tem "
        "equivalente neste eixo.")
    linhas = [["%02d" % ident, ", ".join(str(a) for a in asns)]
              + [rede.c5ppa(ident, digito) for digito, _ in ACOES_5PPA]
              for ident, asns in fontes]
    colunas = ("ID", "ASN") + tuple(rotulo for _digito, rotulo in ACOES_5PPA)
    return Secao(titulo=TITULO_ALIAS, textos=tuple(textos),
                 tabelas=(_tabela(colunas, linhas),))


def _blackhole(rede):
    return Secao(
        titulo="Blackhole",
        textos=(
            "Envie `65535:666` (RFC 7999) num /32, ou num /128 em IPv6, "
            "dentro do seu bloco autorizado. O prefixo é descartado na nossa "
            "borda.",
            "Para que o descarte chegue também aos nossos upstreams, some "
            "`%s` ao anúncio. Sem ela o descarte fica só na nossa borda, que "
            "é o que você quer quando o ataque é local." % rede.BLACKHOLE_PROPAGATE,
            "O descarte não derruba a sessão e não afeta os outros prefixos: "
            "vale para o /32 anunciado.",
        ),
        tabelas=(),
    )


def _manutencao(rede):
    return Secao(
        titulo="Manutenção programada",
        textos=(
            "Envie `%s` (RFC 8326, GSHUT) para drenar as suas rotas antes de "
            "uma janela de manutenção, sem derrubar a sessão BGP. Retire a "
            "community quando a janela terminar, e o tráfego volta." % plan.GSHUT,
        ),
        tabelas=(),
    )


def _informativas(rede):
    origens = _tabela(
        ("Faixa", "Significado"),
        [(rede.c(valor), nome)
         for valor, nome in sorted(rede.ORIGEM_NOME.items())],
    )
    # O 1200 (o GEO_PNI do plan.py) nao entra aqui: ele e valor de origem,
    # o mesmo de `peer bilateral / PNI` na tabela de cima, e publicado nas
    # duas tabelas diria ao cliente que uma community significa duas coisas.
    # A geografia comeca em 2000, e e a faixa que separa as duas.
    numeros = _tabela(
        ("Faixa", "Significado"),
        (
            (rede.c(2000), "Rota aprendida fora do nosso AS"),
            ("%s:%d-%d" % (rede.ns, plan.POP_MIN, plan.POP_MAX),
             "POP de entrada e região"),
            ("%s:%d" % (rede.ns, plan.APRENDIZADO_BASE["ix"]),
             "Rota aprendida num route server de IX"),
            ("%s:%d" % (rede.ns, plan.APRENDIZADO_BASE["upstream"]),
             "Rota aprendida de um upstream"),
            ("%s:%d-%d" % (rede.ns, plan.APRENDIZADO_MIN,
                           plan.APRENDIZADO_MAX),
             "Ponto de aprendizado da rota"),
        ),
    )
    return Secao(
        titulo="Informativas que você recebe de nós",
        textos=(
            "As rotas que você aprende de nós chegam marcadas, e as marcações "
            "atravessam o anúncio: use-as nas suas próprias decisões de "
            "engenharia de tráfego.",
            "A marca de origem diz de que tipo de vizinho nós aprendemos a "
            "rota, e não de onde ela veio originalmente.",
        ),
        tabelas=(origens, numeros),
    )


def _limitacoes(rede):
    return Secao(
        titulo="Limitações conhecidas",
        textos=(
            "Prepend por membro individual de IX não é possível por route "
            "server: o RS repassa o mesmo AS-path a todos os membros. Prepend "
            "por ASN só funciona onde existe sessão bilateral.",
            "Estas communities controlam o que nós anunciamos; rota que você "
            "não nos anunciou não tem o que controlar.",
        ),
        tabelas=(),
    )


def documento(rede=None, peers=(), grupos=(), emitido_em=""):
    """O documento da rede, pronto para imprimir.

    O `rede` e um plan.Rede, como nos templates: o namespace das standard,
    o ASN do `bgp` e os rotulos de origem saem todos dele. Sem argumento o
    documento e o da rede de fabrica.

    O `peers` e o `grupos` sao o cadastro da rede, que so a tabela do alias
    consulta: e dali que saem os identificadores que o cliente digita, e
    eles sao do grupo quando o upstream esta num. Sem cadastro o documento
    continua valendo, e a secao do alias manda para o anexo.

    O `emitido_em` entra por parametro em vez de sair de um `date.today()`
    daqui: um documento que o cliente guarda precisa da data, e um modulo
    que le o relogio nao tem como ser testado sem congelar o tempo.
    """
    rede = rede if rede is not None else plan.Rede()
    return Documento(
        titulo="Política de BGP Communities — AS%s" % rede.ASN,
        subtitulo=("Como controlar a propagação dos seus anúncios no AS%s, e "
                   "o que você recebe de volta." % rede.ASN),
        emitido_em=emitido_em,
        # o namespace entra no pe porque e ele que o cliente digita no
        # equipamento: uma folha solta, sem ele, nao diz de que rede e a
        # tabela
        rodape="AS%s · communities em %s:<valor>" % (rede.ASN, rede.ns),
        secoes=(
            _preferencia(rede),
            _anuncio(rede),
            _prepend(rede),
            _por_asn(rede),
            _alias(rede, peers, grupos),
            _blackhole(rede),
            _manutencao(rede),
            _informativas(rede),
            _limitacoes(rede),
        ),
    )
