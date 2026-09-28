"""As tabelas do PLANO.md como dados.

Nao ha texto de template aqui. O que este modulo guarda e o que os
templates de tipo consultam para decidir valor e para validar faixa.

Nenhum valor de operadora terceira: os ASNs e as IDs que aparecem na
saida vem do formulario. As funcoes de formatacao sao as unicas que
sabem montar o numero da community.

O prefixo dessas communities nao e constante de fabrica. O topo do
peers.yaml declara o AS da rede, e o Rede, no fim do modulo, carrega o
valor declarado: os templates recebem um Rede no lugar deste modulo e
seguem escrevendo plan.c5ppa, sem saber que ha um objeto ali. O que
depende do ASN sao sete valores e nove funcoes, e todos aparecem no Rede;
o resto (TIPOS, LP_BASE, ORIGEM, as faixas) e tabela fixa do plano e o
objeto delega de volta para o modulo.
"""

import functools
import ipaddress

TIPOS = ("cliente", "parceiro", "upstream", "ix", "pni")
FAMILIAS = ("v4", "v6")

# O AS de fabrica, que e o de todo peers.yaml que nao declara nada. O
# ASN e o namespace em texto: e assim que ele entra no nome, "64512:%d", e
# a grafia estava repetida em cada funcao que monta community e no
# faixa_ok. Os dois sao o default das funcoes deste modulo.
#
# Este bloco vem antes de tudo que monta community de proposito: o modulo
# calcula as constantes na ordem em que o arquivo e lido, e um PARCEIRO
# que chamasse c antes daqui nao existiria ainda.
ASN_PADRAO = 64512
ASN = str(ASN_PADRAO)

# A largura do namespace das standard: a RFC 1997 escreve o valor em dois
# campos de 16 bits, entao o numero que entra na community vai de 1 a
# 65535. Vale para o `politica` declarado e para o ASN de ate 16 bits que
# faz as vezes dele; o AS de 32 bits nao cabe em nenhum dos dois e mora so
# no `asn`. O formulario do topo confere esta mesma faixa para o erro
# nascer no campo certo.
NS_MIN, NS_MAX = 1, 65535


def c(valor, ns=ASN):
    """Uma community do plano: o namespace da rede, dois pontos, o valor.

    E por aqui que toda community do plano e montada, inclusive as que o
    template escreve com o numero da tabela na mao: plan.c(1900). O valor
    vem primeiro porque e ele que a tabela do PLANO diz, e o namespace vem
    do topo do peers.yaml.
    """
    return "%s:%d" % (ns, valor)


# o parceiro e um cliente que fica no roteador onde as CDNs tem sessao. A
# regra e a mesma do cliente, import e export; o que muda e esta marca, que
# diz de qual sessao a rota veio. A dezena 2091-2099 ja esta reservada no
# PLANO ao ecossistema de CDN, entao a marca nao abre faixa nova.
def _parceiro(ns=ASN):
    return c(2091, ns)


PARCEIRO = _parceiro()

# os tipos que sao downstream com prefix-list: o validar cobra deles a
# classe, o POP, o bloco autorizado e a sobreposicao com outro downstream, e
# so eles podem pedir a default route.
TIPOS_DOWNSTREAM = ("cliente", "parceiro")

# --- local preference -------------------------------------------------

LP_BASE = {"cliente": 300, "parceiro": 300, "upstream": 100, "ix": 190, "pni": 200}
LP_IX_CDN = 195          # membro de IX marcado no AP-IX-<T>
LP_TE_PREFER = 250       # excecao de TE no import de upstream
LP_BLACKHOLE = 400       # ramo de blackhole do import de cliente

# escada do APPLY-CUSTOMER-LP, na ordem em que os ramos saem no filtro. O
# valor da community e o da local preference que ele aplica: 101 e o menor
# LP da escada, 105 o maior.
_ESCADA_LP = ((101, 50), (102, 80), (103, 150), (104, 250), (105, 350))
LP_CLIENTE_DEFAULT = 300


def _lp_cliente(ns):
    return tuple((c(valor, ns), lp) for valor, lp in _ESCADA_LP)


LP_CLIENTE = _lp_cliente(ASN)

# --- origem -----------------------------------------------------------

ORIGEM = {"cliente": 1100, "parceiro": 1100, "upstream": 1400, "ix": 1300,
          "pni": 1500}
ORIGEM_CLASSE = {
    "transito": 1100,
    "residencial": 1110,
    "corporativo": 1120,
    "cgnat": 1130,
}
CLASSES_CLIENTE = tuple(ORIGEM_CLASSE)

# rotulos da tabela "Origem da rota" do PLANO.md, na ordem do documento. O
# texto do documento tem acento e a pagina tem teste de isascii, entao o
# rotulo foi reescrito sem. E o vocabulario e fixo do plano, nao inventario
# do operador: por isso estes viram select, e nao datalist.
#
# Quem le estes rotulos e a tela e, desde o PDF do cliente, o
# politica.documento: os dois mostram a mesma palavra sem acento, e uma
# versao so para o PDF seria duas listas divergindo com o tempo.
#
# O 1000 fica de fora: o rotulo dele cita o AS, e por isso quem o monta e o
# _origem_nome. As outras nove linhas nao citam AS nenhum.
_ORIGEM_NOME = {
    1100: "cliente de transito (ISP downstream)",
    1110: "cliente residencial / FTTH",
    1120: "cliente corporativo / link dedicado",
    1130: "pool CGNAT / IP dinamico",
    1200: "peer bilateral / PNI",
    1300: "peer via route server em IX",
    1400: "upstream (transito pago)",
    1500: "CDN / conteudo (cache ou peering direto)",
    1900: "infra interna - nunca sai do AS",
}


def _origem_nome(ns=ASN, asn=None):
    # o 1000 entra primeiro, e nao por update depois: a ordem e a do
    # documento, e e ela que a tela segue no select de origem
    #
    # O rotulo cita o AS da sessao, e nao o namespace. Os dois numeros
    # coincidem em todo ASN de 16 bits, que e por que a diferenca passou
    # despercebida ate um tenant declarar asn_politica: ali o rotulo dizia
    # "prefixo proprio do AS65532", o prefixo de uma rede que nao existe
    nomes = {1000: "prefixo proprio do AS%s" % (ns if asn is None else asn)}
    nomes.update(_ORIGEM_NOME)
    return nomes


ORIGEM_NOME = _origem_nome()

# quais dessas origens o formulario oferece em cada tipo. O cliente tem as
# quatro da classe - que e o que o validar cobra dele - e o parceiro tem as
# mesmas, porque por baixo da marca de 2091 ele e cliente. Os outros tem a
# marca do proprio tipo, mais 1200 (bilateral, que IX e PNI compartilham),
# 1000 e 1900, as duas que o PLANO define sem depender de peer nenhum.
# Nenhum tipo recebe a marca de cliente de outro, que seria a combinacao sem
# sentido.
ORIGENS_POR_TIPO = {
    "cliente": (1100, 1110, 1120, 1130),
    "parceiro": (1100, 1110, 1120, 1130),
    "upstream": (1400, 1000, 1900),
    "ix": (1300, 1200, 1000, 1900),
    "pni": (1500, 1200, 1000, 1900),
}

# o par CL-PEER-<T> / APPLY-PEER-<T> existe so nestes tipos: e o que da
# community propria de sessao ao cliente, ao parceiro e ao upstream. O IX
# nao tem (o route server repassa o mesmo path a todos) e o PNI tambem nao -
# o egress dos dois nao chama APPLY-PEER nenhum. O quadro "ao criar o peer",
# o bloco de remocao e o painel de saida seguem esta tabela.
TIPOS_COM_APPLY_PEER = ("cliente", "parceiro", "upstream")


def quadro_ao_criar(alvo, de_grupo):
    """O quadro "ao criar" existe para este alvo?

    Para o peer o criterio e TIPOS_COM_APPLY_PEER, que e quem tem CL-PEER
    propria de sessao. Para o grupo e outro, e por isso ele nao mora na
    mesma tupla: quem define o APPLY-PEER-<G> e o proprio quadro, e so o
    export do grupo de upstream chama esse filtro - a CL-PEER de um upstream
    descreve a rede remota, entao ela mora no grupo e vale para os dois
    links. Num grupo de cliente ou de parceiro a community descreve o link,
    cada membro tem a sua, e o quadro criaria dois objetos que nenhum filtro
    do grupo chama; num grupo de IX e num de PNI nao ha APPLY-PEER nenhum.
    O `de_grupo` e o que diz qual dos dois alvos esta na frente, para o
    criterio certo valer: o criar_lista.txt.j2 serve os dois. Ele nao tem
    default de proposito: com um default, uma chamada de grupo que esquecesse
    o argumento cairia no criterio do peer avulso em silencio, e o grupo de
    cliente e de parceiro sairia com o quadro que a secao C tirou de la. Sem
    default o erro e na hora da chamada, e nao no arquivo gerado.
    """
    if de_grupo:
        return alvo.tipo == "upstream"
    return alvo.tipo in TIPOS_COM_APPLY_PEER

# o export so libera o que carrega marca de origem propria ou de cliente.
# 1000 e "prefixo proprio do AS64512" e as quatro classes de cliente sao
# 1100-1130 (PLANO.md, secao "Origem da rota"). O 1100 coincide com a
# classe de transito, entao o proprio entra literal, e nao repetido.
def _origem_anunciavel(ns=ASN):
    return (c(1000, ns),) + tuple(c(ORIGEM_CLASSE[cl], ns)
                                  for cl in CLASSES_CLIENTE)


ORIGEM_ANUNCIAVEL = _origem_anunciavel()

# --- originacao dos prefixos proprios ---------------------------------

# a preferencia da estatica para NULL0 que ancora o `network`. Ela ganha
# do BGP, que e o que impede a rota de um cliente com sub-alocacao dentro
# do bloco de virar a origem do `network`, e perde do IGP e da estatica de
# preferencia default, para um agregado que exista de verdade na tabela
# sair com o next-hop de verdade em vez de ir para o NULL0.
PREFERENCE_ORIGEM = 250
# o LP de toda rota originada. E o valor do exemplo do PLANO.md e o do
# BGP_EXEMPLO.txt, e nao depende do tipo de peer nem do prefixo.
LP_ORIGEM = 900

# geografia fixa do PNI, PLANO.md secao "Communities informativas"
GEO_PNI = 1200
# 2xxx e geografia/POP. 2000 fica de fora: e "aprendida de fora".
POP_MIN, POP_MAX = 2001, 2999
# 3xxx e ponto de aprendizado, por peer
APRENDIZADO_MIN, APRENDIZADO_MAX = 3000, 3999
# A tabela do PLANO mostra o desenho da faixa: os IXs andam em 30xx (3010,
# 3011) e os upstreams em 31xx (3100, 3101, 3102), cada bloco do tamanho do
# espaco de IDs. O formulario em branco propoe o primeiro valor livre do
# bloco do tipo; o campo continua aceitando qualquer 3xxx. PNI nao tem ponto
# de aprendizado nenhum, e por isso nao aparece aqui.
APRENDIZADO_BASE = {"upstream": 3100, "ix": 3010}

# --- sessao -----------------------------------------------------------

ROUTE_LIMIT = {
    "cliente": 50,
    "parceiro": 50,
    "upstream": 1500000,
    "ix": 500000,
    "pni": 10000,
}
# o exemplo de aplicacao do PLANO usa outros valores; ficam como nota no
# formulario, nao como default. O da tabela acima e que vale.
ROUTE_LIMIT_EXEMPLO = {"cliente": 50, "parceiro": 50, "upstream": 1100000,
                       "ix": 500000, "pni": 10000}

ACAO_LIMITE = "alert-only"
AS_ONLY = "public-as-only force"

# keepalive e hold. O PLANO so poe timer explicito no upstream; nos
# outros tipos o equipamento usa o default. None = nao emitir a linha.
TIMER_PADRAO = {
    "cliente": (None, None),
    "parceiro": (None, None),
    "upstream": (10, 30),
    "ix": (None, None),
    "pni": (None, None),
}

# --- escopo de anuncio ------------------------------------------------

NOADV = {"upstream": (200, 201), "ix": (200, 203), "pni": (200, 202)}
NOADV_CUST = (200, 204)
ONLY_NOT = {
    "cliente": (210, 211, 212),
    "upstream": (211, 212, 213),
    "ix": (210, 212, 213),
    "pni": (210, 211, 213),
}

# --- prepend por classe (6CA) -----------------------------------------

# classe C do 64512:6CA. A tabela do PLANO da 3 a "IX privado e PNI" e 4
# a CDN; o unico exemplo de PNI do documento e de CDN e usa 4.
CLASSE_6CA = {"upstream": 1, "ix": 2, "pni": 4}
# digito do 5PPA/6CA -> numero de prepends. O digito 1 nao tem ramo:
# ele existe para barrar a classe, e por isso o aninhamento e if/elseif.
DIGITO_PREPEND = {4: 3, 3: 2, 2: 1}

# a escala publicada no PLANO vai de P1 a P7, onde P1 e anunciar sem prepend
# e P7 sao seis prepends. Ou seja: o numero de prepends vai de 0 a 6. Os
# filtros deste plano so implementam ate P4 (3 prepends) - de 4 a 6 fica
# reservado, e o formulario mostra o valor dizendo isso em vez de esconder.
PREPEND_MAX = 6
PREPEND_IMPLEMENTADO = 3

# --- blackhole e manutencao -------------------------------------------

# 65535:666 e a blackhole bem-conhecida da RFC 7999 e o GSHUT e a da RFC
# 8326: as duas nao sao do plano e nao seguem o AS da rede.
GSHUT = "65535:0"


def _blackhole(ns=ASN):
    return ("65535:666", c(666, ns))


def _blackhole_propagate(ns=ASN):
    return c(667, ns)


def _blackhole_info(ns=ASN):
    return c(9666, ns)


BLACKHOLE = _blackhole()
BLACKHOLE_PROPAGATE = _blackhole_propagate()
BLACKHOLE_INFO = _blackhole_info()

# uma community e action (3 digitos, 100-699) ou informativa (4, 1000-9999)
FAIXAS = ((100, 699), (1000, 9999))


def c4pp0(peer_id, ns=ASN):
    """Informativa 4PP0: de qual peer a rota veio."""
    return "%s:4%02d0" % (ns, peer_id)


def c5ppa(peer_id, digito, ns=ASN):
    """Alias em standard do prepend e do escopo por peer."""
    return "%s:5%02d%d" % (ns, peer_id, digito)


def c6ca(classe, digito, ns=ASN):
    """Prepend por classe de peer."""
    return "%s:6%d%d" % (ns, classe, digito)


def c_large(funcao, asn, ns=ASN):
    """Large community no formato <ns>:<funcao>:<ASN> (RFC 8195).

    O `asn` e o do peer e o `ns` e o namespace do plano, e os dois campos
    aguentam coisas diferentes: a large tem 32 bits por campo, entao um
    peer de ASN de 32 bits cabe aqui, e o namespace de 16 bits da standard
    e que nao caberia.
    """
    return "%s:%d:%d" % (ns, funcao, asn)


def conjunto(*itens):
    """Monta o literal de conjunto do XPL.

    Existe porque escrever "{" num template colado a "{{" faz o Jinja
    ler o delimitador de expressao e o texto sai truncado.
    """
    return "{%s}" % ", ".join(str(i) for i in itens)


def _rede_do_cidr(cidr):
    """O ip_network do CIDR, sem exigir que ele venha canonico."""
    return ipaddress.ip_network(cidr, strict=False)


def nome_origem(cidr):
    """O nome do filtro de originacao: ORIGEM-<endereco>_<mascara>.

    O ponto vira traco, e em v6 os dois-pontos viram traco pelo mesmo
    motivo. A forma com ponto se leria como o prefixo e seria melhor, mas
    o que o F1A verificou foi a palavra-chave `route-filter`, com um nome
    escolhido na hora: se o nome de objeto aceita ponto e item aberto de
    hardware, entao a de traco e a escolhida enquanto a outra nao for
    confirmada no equipamento. O `::` some junto com os hextetos vazios
    que ele abrevia, entao o corpo do nome carrega so os hextetos que
    existem de verdade. O `_` antes da mascara le como mascara, que e o
    que o `m` da convencao antiga nao fazia.
    """
    rede = _rede_do_cidr(cidr)
    if rede.version == 4:
        corpo = str(rede.network_address).replace(".", "-")
    else:
        corpo = "-".join(p for p in str(rede.network_address).split(":") if p)
    return "ORIGEM-%s_%d" % (corpo, rede.prefixlen)


def endereco(cidr):
    """O endereco na forma que o comando pede: 38.252.64.0 ou 2804:36b4::."""
    return str(_rede_do_cidr(cidr).network_address)


def mascara(cidr):
    """A mascara na forma que o comando pede.

    Em v4 e pontuada, que e o que o `ip route-static` e o `network` de
    `ipv4-family` esperam. Em v6 e o comprimento direto, sem pontuacao,
    como no `network 2804:36B4:: 32` do BGP_EXEMPLO.txt.
    """
    rede = _rede_do_cidr(cidr)
    return str(rede.netmask) if rede.version == 4 else str(rede.prefixlen)


def separa_communities(valores):
    """(standard, large) na ordem em que vieram.

    A lista do cadastro do bloco e uma so, porque o operador escreve a
    community e nao a forma dela, e o VRP pede `apply community` e
    `apply large-community` em linhas separadas. Quem separa e a contagem
    de dois-pontos: dois e large (RFC 8195), um e standard (RFC 1997).
    """
    standard, large = [], []
    for valor in valores or []:
        (large if valor.count(":") == 2 else standard).append(valor)
    return standard, large


def conjunto_de(lista):
    """O mesmo conjunto do `conjunto`, para uma lista que ja veio pronta.

    O `conjunto` recebe os itens soltos e nao serve quando a lista foi
    montada no template por concatenacao, que e o caso do `1000` gerado
    mais o que o operador escreveu.
    """
    return conjunto(*lista)


def noadv(tipo, peer_id, ns=ASN):
    """Composicao do CL-NOADV-<T>: proibicao absoluta e do tipo, mais este peer."""
    um, dois = NOADV[tipo]
    return [c(um, ns), c(dois, ns), c5ppa(peer_id, 0, ns)]


def noadv_cust(ns=ASN):
    """O egress de cliente nao tem eixo por peer."""
    return [c(v, ns) for v in NOADV_CUST]


def c_downstream(tipo, origem, pop, ns=ASN):
    """As informativas que o import de um downstream carimba.

    Origem e POP valem para os dois tipos; a marca de 2091 so no parceiro,
    que e o que diz que esta sessao fica no roteador das CDNs.
    """
    itens = [c(origem, ns), c(pop, ns)]
    if tipo == "parceiro":
        itens.append(_parceiro(ns))
    return conjunto(*itens)


def only_not(tipo, ns=ASN):
    return [c(v, ns) for v in ONLY_NOT[tipo]]


def cidr_para_xpl(cidr):
    """`45.169.232.0/22` -> `45.169.232.0 22`. O VRP nao usa barra aqui."""
    if "/" not in cidr:
        raise ValueError("prefixo sem mascara: %s" % cidr)
    addr, mascara = cidr.split("/", 1)
    return "%s %d" % (addr.strip(), int(mascara))


def faixa_ok(community, ns=ASN):
    """A community esta numa das faixas do plano, no namespace da rede?"""
    partes = community.split(":")
    if len(partes) != 2 or partes[0] != ns:
        return False
    try:
        valor = int(partes[1])
    except ValueError:
        return False
    return any(lo <= valor <= hi for lo, hi in FAIXAS)


class Rede:
    """O plano com o AS declarado no topo do peers.yaml.

    Os templates recebem um destes no lugar do modulo e continuam escrevendo
    plan.c5ppa e plan.BLACKHOLE: o que nao depende do ASN e delegado de volta
    para o modulo, e o que depende sai daqui ja no namespace declarado.

    Sao dois numeros, e nao um, porque as duas familias de community tem
    larguras diferentes. A standard da RFC 1997 escreve o valor em dois campos
    de 16 bits, entao um ASN de 32 bits nao cabe nela - e o 5PPA, o 6CA, o
    4PP0 e as informativas sao todos standard. A large da RFC 8195 tem 32 bits
    por campo e leva o ASN inteiro.

    Por isso `asn` e o AS de verdade, o que entra no `bgp` e no `apply
    as-path`: asplain de 32 bits e aceito nos dois, conferido no equipamento.
    `politica` e o namespace das standard, um 16 bits a parte; nao declarado,
    vale o proprio ASN, que e o caso de todo ASN de 16 bits. Com ASN de 32
    bits esse default nao existe, e a falta vira ValueError em vez de um
    namespace trocado pela metade.

    A faixa do ASN em si - reservado, privado - e do validate.py, nao daqui.
    """

    def __init__(self, asn=ASN_PADRAO, politica=None):
        asn = int(asn)
        if politica is None:
            if asn > NS_MAX:
                raise ValueError(
                    "ASN %d nao cabe nos 16 bits da standard da RFC 1997: "
                    "declare asn_politica com o namespace das communities "
                    "do plano" % asn)
            politica = asn
        politica = int(politica)
        if not NS_MIN <= politica <= NS_MAX:
            raise ValueError(
                "namespace das standard fora de %d-%d: %d"
                % (NS_MIN, NS_MAX, politica))
        self.asn = asn
        self.politica = politica
        self.ns = str(politica)
        # o ASN em texto, que e a forma em que ele entra no `bgp` e no
        # `apply as-path`
        self.ASN = str(asn)

        # os sete valores que o modulo calcula no import, recalculados aqui
        self.PARCEIRO = _parceiro(self.ns)
        self.ORIGEM_ANUNCIAVEL = _origem_anunciavel(self.ns)
        self.LP_CLIENTE = _lp_cliente(self.ns)
        self.ORIGEM_NOME = _origem_nome(self.ns, self.asn)
        self.BLACKHOLE = _blackhole(self.ns)
        self.BLACKHOLE_PROPAGATE = _blackhole_propagate(self.ns)
        self.BLACKHOLE_INFO = _blackhole_info(self.ns)

        # as dez funcoes com o namespace ja fixado: o template chama
        # plan.c5ppa(peer, 0) e recebe o que c5ppa(peer, 0, ns) devolveria.
        # partial e a biblioteca padrao dizendo exatamente isso; um metodo
        # por funcao so repetiria a assinatura de cada uma.
        #
        # O `c` entra junto porque e por ele que o template escreve a
        # community cujo numero esta so na tabela do PLANO: plan.c(1900).
        self.c = functools.partial(c, ns=self.ns)
        self.c4pp0 = functools.partial(c4pp0, ns=self.ns)
        self.c5ppa = functools.partial(c5ppa, ns=self.ns)
        self.c6ca = functools.partial(c6ca, ns=self.ns)
        self.c_large = functools.partial(c_large, ns=self.ns)
        self.noadv = functools.partial(noadv, ns=self.ns)
        self.noadv_cust = functools.partial(noadv_cust, ns=self.ns)
        self.c_downstream = functools.partial(c_downstream, ns=self.ns)
        self.only_not = functools.partial(only_not, ns=self.ns)
        self.faixa_ok = functools.partial(faixa_ok, ns=self.ns)

    def __getattr__(self, nome):
        """O que nao depende do ASN sai do modulo.

        O guarda e o _NOMES_COM_O_ASN: um nome que carrega o AS de fabrica e
        que ninguem recalculou aqui nao pode sair pela delegacao, senao ele
        sai com 64512 no meio de um namespace trocado - o que nao aparece num
        diff de config e so aparece na sessao derrubada. Melhor estourar no
        acesso.
        """
        if nome in _NOMES_COM_O_ASN:
            raise AttributeError(
                "%r carrega o AS e o Rede nao responde por ele" % nome)
        try:
            return globals()[nome]
        except KeyError:
            raise AttributeError("o plano nao tem %r" % nome)


# Os nomes do modulo cujo valor carrega o AS de fabrica. O Rede recalcula
# todos os sete, e o __getattr__ usa esta lista para nao servir nenhum deles
# pela delegacao. A varredura e do proprio modulo de proposito: uma constante
# nova com "64512" dentro entra na lista sozinha, e quem acrescentar uma sem
# expor no Rede descobre no primeiro acesso, e nao na sessao BGP com meio
# namespace trocado.
#
# Ela roda depois do modulo inteiro, e por isso mora no fim do arquivo: uma
# constante declarada depois daqui nao entra na lista.
_NOMES_COM_O_ASN = frozenset(
    nome for nome, valor in globals().items()
    if not nome.startswith("_") and ASN in str(valor)
)
