"""O peers.yaml: ler, gravar e alocar ID.

O arquivo e o estado do app. Ele guarda o cadastro de cada peer, o que
inclui o conteudo da CL-PEER-<T>: a lista e escrita uma vez no
equipamento, pelo quadro "ao criar o peer", e o cadastro aqui e o que
permite reescreve-la igual quando ela muda.

O campo se chama `id` e nao `ident` porque ele aparece no nome de objeto
do XPL (CL-5PPA-01) e no formulario com esse nome. Sombra o builtin
dentro da dataclass, e isso e inofensivo.

O `token` nao e campo: ele e derivado, o ASN ou o apelido que o
substitui. Guardar os dois seria guardar a mesma coisa duas vezes, e o
token gravado ficaria para tras quando o ASN mudasse.
"""

import ipaddress
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.plan import FAMILIAS, Rede, comprimento

RAIZ = Path(__file__).resolve().parent.parent
PEERS_YAML = RAIZ / "peers.yaml"

MAX_IDS = 100

# o AS da rede no topo do arquivo, antes de peers: e grupos:. Ele e do
# arquivo, e nao de um peer: o namespace das communities e o mesmo em todo
# filtro gerado, e por isso o valor mora fora das listas.
CHAVE_ASN = "asn"
CHAVE_POLITICA = "asn_politica"

# a secao dos prefixos do proprio AS, no fim do arquivo. Ela e da rede e
# nao de um peer, como o asn e o asn_politica: o prefixo proprio nao tem
# sessao e nao disputa o espaco de identificadores do 5PPA.
CHAVE_BLOCOS = "blocos"


def _listas_por_familia():
    return {fam: [] for fam in FAMILIAS}


def _sessoes_vazias():
    return {fam: {} for fam in FAMILIAS}


@dataclass
class Peer:
    id: int = 0
    # so ix e pni: substitui o ASN no token
    apelido: str = ""
    nome: str = ""
    tipo: str = "cliente"
    asn: int = 0
    classe: str | None = None
    descricao: str = ""

    lp_base: int = 300
    origem: int | None = None
    pop: int | None = None
    aprendizado: int | None = None
    ix_id: int | None = None

    # prefixos anunciados pelo peer (bgpq4 ou mao)
    prefixos: dict = field(default_factory=_listas_por_familia)
    # excecoes de TE: prefixos que se alcanca melhor pela borda do upstream
    te_prefixos: dict = field(default_factory=_listas_por_familia)
    # ASNs que este upstream nao pode anunciar
    ap_block: list = field(default_factory=list)
    # ASNs alcancados melhor pela borda do upstream
    ap_te: list = field(default_factory=list)
    # PNI: ASNs que a CDN pode anunciar
    ap_allowed: list = field(default_factory=list)
    # IX: membros que recebem LP 195 em vez de 190
    ap_prefer: list = field(default_factory=list)

    # a CL-PEER-<T>: as communities que a operadora aplica na sessao deste
    # peer, escritas quando o cliente pede. Vao inteiras para o quadro "ao
    # criar o peer"; o bloco do peer so chama o filtro e nunca reescreve a
    # lista.
    communities: list = field(default_factory=list)
    large_communities: list = field(default_factory=list)

    # knobs de sessao do bloco bgp
    bfd: bool = True
    graceful_restart: bool = True
    timer_keepalive: int | None = None
    timer_hold: int | None = None

    prepend_base: int = 0
    route_limit: int = 50

    sessoes: dict = field(default_factory=_sessoes_vazias)
    # community de blackhole DESTE upstream; vazia desliga o ramo
    bh_upstream: str = ""
    # cliente: anuncia a default route (0.0.0.0/0 e ::/0) a esta sessao
    default_route: bool = False

    # grupo BGP (VRP `group`) a que este peer pertence, ou None fora de
    # grupo. Vale nos cinco tipos - o membro herda do grupo o mesmo objeto em
    # qualquer um deles -, e quem confere o par e o validate: grupo que nao
    # existe, grupo de outro tipo, ou ASN divergente do grupo e erro la, com
    # mensagem propria.
    grupo_id: int | None = None

    # o peer cuja politica este vale. A referencia e por id e nao por token:
    # o token muda quando o apelido muda, e a referencia nao pode se
    # desfazer por causa de uma renomeacao. O efeito colateral - o bloco de
    # quem reaproveita fica apontando para nomes velhos ate ser gerado de
    # novo - esta tratado no aviso do formulario da origem.
    politica_de: int | None = None

    def __post_init__(self):
        """Todo item de `prefixos` e um Bloco, sem excecao.

        A normalizacao mora aqui, e nao no `de_dict`, porque o Peer nasce em
        tres caminhos: do yaml, do formulario e dos testes, que montam a
        lista de CIDR em texto. Um lugar so cobre os tres, e a lista de
        strings dos fixtures continua valendo.
        """
        self.prefixos = {
            fam: [_bloco(i) for i in (self.prefixos or {}).get(fam) or []]
            for fam in FAMILIAS}

    def cidrs(self, fam):
        """Os prefixos em servico da familia, para as duas prefix-lists."""
        return [b.prefixo for b in self.prefixos.get(fam) or [] if b.ativo]

    def tratamentos(self, fam):
        """(prefixo, communities) de cada linha com tratamento, na ordem da cadeia.

        Do mais longo para o mais curto: a cadeia do filtro e if/elseif, e
        um /24 escrito dentro de um /22 tem que vencer o /22. O empate fica
        na ordem do cadastro, porque o sorted do Python e estavel.
        """
        com_community = [b for b in self.prefixos.get(fam) or []
                         if b.ativo and b.communities]
        return sorted(((b.prefixo, list(b.communities)) for b in com_community),
                      key=lambda par: -comprimento(par[0]))

    @property
    def token(self):
        """O nome curto do peer: o ASN, ou o apelido quando o ASN nao serve.

        O ASN identifica a sessao sozinho em quase todo caso, e e o que o
        operador le no equipamento. Numa sessao de IX quem aparece e o ASN
        do route server, o mesmo em todo IX, entao ali o operador da um
        apelido que entra no lugar do ASN.
        """
        return self.apelido or str(self.asn)

    def familias(self):
        return [f for f in FAMILIAS if self.sessoes.get(f)]

    def tem_filtro_proprio(self):
        """Membro de grupo com politica propria: prefixo, CL-PEER ou ap/te.

        Fora de grupo isso nao significa nada - todo peer avulso ja tem
        filtro proprio. Dentro de um grupo, e o que decide se o membro
        recebe o filtro dele (igual ao peer avulso) ou so herda do grupo.

        A lista cobre os campos que nascem ausentes e o operador preenche no
        membro, sem se prender ao que e "filtro" no nome:
        filtro_upstream_import le te_prefixos e ap_te,
        listas_upstream le ap_block e ap_te, listas_ix le ap_prefer e
        listas_pni le ap_allowed, e filtro_upstream_export le prepend_base e
        bh_upstream. Sem eles, um membro cujo unico override seja uma
        excecao de TE (ou o prepend base, ou a community de blackhole do
        upstream) saia sem ramo proprio e herdava a politica inteira do
        grupo em silencio.

        A lista so enumera campos com estado "ausente" (vazio, None ou
        false), que e o que separa o membro que traz politica propria do que
        so herda. lp_base, origem e aprendizado ficam de fora: podem ter
        valor no membro, mas o grupo carrega os tres por padrao e o lp_base
        nunca e vazio (default 300), entao contar qualquer um deles deixaria
        o predicado sempre verdadeiro e nao haveria mais heranca.

        Quem acrescentar numa macro a leitura de um campo de override do
        membro acrescenta o campo aqui tambem: o predicado e o unico lugar
        que decide entre o ramo proprio e a heranca.
        """
        tem_prefixo = any(self.prefixos.get(f) for f in FAMILIAS)
        tem_te = any(self.te_prefixos.get(f) for f in FAMILIAS)
        return bool(tem_prefixo or tem_te or self.communities
                    or self.large_communities or self.ap_block or self.ap_te
                    or self.ap_allowed or self.ap_prefer
                    or self.prepend_base or self.bh_upstream)

    def arquivo(self, saida):
        """O caminho do bloco deste peer na pasta de saida do tenant dele.

        A pasta vem por parametro e nao tem padrao: um default para a raiz
        do out/ deixaria uma chamada esquecida escrever em
        out/<token>-<tipo>.txt, que e o nome que a etapa dos tenants
        elimina. O nome do arquivo continua saindo do token, que e unico
        dentro de um tenant.
        """
        return Path(saida) / ("%s-%s.txt" % (self.token, self.tipo))

    def para_dict(self):
        return {
            "id": self.id, "apelido": self.apelido, "nome": self.nome,
            "tipo": self.tipo, "asn": self.asn, "classe": self.classe,
            "descricao": self.descricao, "lp_base": self.lp_base,
            "origem": self.origem, "pop": self.pop,
            "aprendizado": self.aprendizado, "ix_id": self.ix_id,
            "prefixos": {fam: [_prefixo_gravado(b)
                               for b in self.prefixos.get(fam) or []]
                         for fam in FAMILIAS},
            "te_prefixos": self.te_prefixos,
            "ap_block": self.ap_block, "ap_te": self.ap_te,
            "ap_allowed": self.ap_allowed, "ap_prefer": self.ap_prefer,
            "communities": self.communities,
            "large_communities": self.large_communities,
            "bfd": self.bfd, "graceful_restart": self.graceful_restart,
            "timer_keepalive": self.timer_keepalive,
            "timer_hold": self.timer_hold,
            "prepend_base": self.prepend_base, "route_limit": self.route_limit,
            "sessoes": self.sessoes, "bh_upstream": self.bh_upstream,
            "default_route": self.default_route, "grupo_id": self.grupo_id,
            "politica_de": self.politica_de,
        }

    @classmethod
    def de_dict(cls, d):
        """Le uma entrada do yaml, ignorando o que nao e campo.

        E aqui que o `token` gravado pelas versoes antigas some: ele nao e
        campo, entao a chave e descartada e o token sai derivado do ASN (ou
        do apelido, quando houver). Um peers.yaml com `token: GIS` num peer
        de ASN 264130 carrega como 264130, sem migracao a parte.
        """
        conhecidos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in conhecidos})


def _ler_bruto(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def _escrever_bruto(dados, caminho):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        yaml.safe_dump(dados, allow_unicode=False, sort_keys=False),
        encoding="utf-8")


def carregar(caminho=PEERS_YAML):
    dados = _ler_bruto(caminho)
    return [Peer.de_dict(d) for d in dados.get("peers", [])]


def gravar(peers, caminho=PEERS_YAML):
    dados = _ler_bruto(caminho)
    dados["peers"] = [p.para_dict() for p in peers]
    _escrever_bruto(dados, caminho)


def carregar_asn(caminho=PEERS_YAML):
    """O AS declarado no topo do arquivo, como plan.Rede.

    Sem a chave, vale o AS de fabrica: e o que faz um peers.yaml que nunca
    declarou nada gerar a config de antes, byte a byte. Sem o
    `asn_politica`, o namespace das standard e o proprio ASN, que serve
    todo ASN de ate 16 bits.

    ASN de 32 bits sem `asn_politica` nao tem como virar community standard
    nenhuma, e o ValueError daqui nomeia o arquivo e a chave. A mensagem e o
    caminho de conserto de quem editar o yaml a mao: o app nao escreve esse
    estado (o gravar_asn recusa antes), entao ele so nasce de fora.
    """
    dados = _ler_bruto(caminho)
    bruto = dados.get(CHAVE_ASN)
    if bruto is None:
        return Rede()
    try:
        return Rede(asn=bruto, politica=dados.get(CHAVE_POLITICA))
    except ValueError as erro:
        raise ValueError("%s: %s" % (caminho, erro)) from erro


def carregar_rede(caminho, asn):
    """O plan.Rede do tenant: o ASN do nome do arquivo, o namespace de dentro.

    O namespace so existe dentro do arquivo, e e de la que ele sai. O ASN,
    nao: um arquivo editado a mao que diga outro numero na chave `asn`
    geraria a config de outra rede em silencio, enquanto o seletor e a pasta
    de saida seguem o nome. O nome ganha, e essa e a unica forma de o ganho
    valer de verdade.

    O ValueError do plan.Rede sai nomeando o arquivo, como no carregar_asn:
    e a mensagem que a tela mostra no toast quando o par nao fecha (ASN de
    32 bits sem namespace).
    """
    bruto = _ler_bruto(caminho).get(CHAVE_POLITICA)
    try:
        return Rede(asn=asn, politica=bruto)
    except ValueError as erro:
        raise ValueError("%s: %s" % (caminho, erro)) from erro


def gravar_asn(asn, politica=None, caminho=PEERS_YAML):
    """Grava o AS no topo do arquivo e devolve o Rede que ele descreve.

    O Rede sai daqui construido para o erro de ASN de 32 bits sem namespace
    ser recusado antes da escrita: um POST que nao fecha nao tem por que
    estragar o arquivo que estava bom. Depois dele, a chave `asn` fica
    primeiro e o resto do arquivo atravessa inteiro, peers e grupos
    inclusive.

    `politica` em None nao grava a chave, e apaga a que estiver la: sem
    ela o namespace e o proprio ASN, e uma chave velha no arquivo diria
    outra coisa que nao a que a tela mostra.
    """
    rede = Rede(asn=asn, politica=politica)
    dados = _ler_bruto(caminho)
    novo = {CHAVE_ASN: rede.asn}
    if politica is not None:
        novo[CHAVE_POLITICA] = rede.politica
    novo.update({k: v for k, v in dados.items()
                 if k not in (CHAVE_ASN, CHAVE_POLITICA)})
    _escrever_bruto(novo, caminho)
    return rede


def proximo_id(peers, grupos=()):
    """O primeiro identificador livre nas duas listas.

    O eixo 64512:5PPA tem dois digitos de identificador e um de papel
    (plan.c5ppa), entao sao 100 numeros e peer e grupo disputam os mesmos:
    alocar cada um sobre o proprio conjunto dava o mesmo numero aos dois, e
    a partir dai duas politicas escrevem a mesma community.
    """
    usados = {p.id for p in peers} | {g.id for g in grupos}
    for i in range(MAX_IDS):
        if i not in usados:
            return i
    raise ValueError("sem ID livre: a faixa 0-99 esta cheia")


def achar(peers, token):
    """Acha pelo token, que e o que as URLs carregam."""
    for p in peers:
        if p.token == token:
            return p
    return None


def achar_id(peers, ident):
    """Acha pelo id, que e a identidade do registro.

    O token muda quando o ASN muda, entao quem esta sendo editado se
    reconhece pelo id: e o unico campo que nao se mexe sozinho.
    """
    for p in peers:
        if p.id == ident:
            return p
    return None


@dataclass
class Grupo:
    id: int = 0
    nome: str = ""
    tipo: str = "cliente"
    # None: cada peer membro declara o proprio ASN. Setado: os membros
    # herdam, so precisam do proprio quando o grupo nao tem (ver spec,
    # "Modelo de dados").
    asn: int | None = None
    classe: str | None = None
    lp_base: int = 300
    origem: int | None = None
    pop: int | None = None
    # so upstream e ix: o 3xxx do ponto de aprendizado, que o import carimba
    # na rota. O design anterior ja o listava na tabela do Grupo; a
    # implementacao nao o criou.
    aprendizado: int | None = None
    # so ix: o id do IX no PeeringDB, que vira a large-community 1001:<ix_id>
    ix_id: int | None = None
    ap_block: list = field(default_factory=list)
    ap_te: list = field(default_factory=list)
    ap_allowed: list = field(default_factory=list)
    ap_prefer: list = field(default_factory=list)
    prepend_base: int = 0
    bh_upstream: str = ""
    default_route: bool = False
    bfd: bool = True
    graceful_restart: bool = True
    timer_keepalive: int | None = None
    timer_hold: int | None = None
    # so cliente/parceiro; vazio = grupo sem confinamento de prefixo (o caso
    # "varios parceiros distintos"), preenchido = mesmo cliente redundante
    prefixos: dict = field(default_factory=_listas_por_familia)
    # excecoes de TE do upstream: prefixos que se alcanca melhor pela borda
    # deste transito
    te_prefixos: dict = field(default_factory=_listas_por_familia)
    # o conteudo da CL-PEER-<G> / LC-PEER-<G>. Para um upstream a community
    # descreve a REDE REMOTA, nao o link: dois links para o mesmo transito
    # levam a mesma, e repeti-la por membro e a duplicacao que o grupo
    # existe para eliminar (ver "Modelo de dados" da spec).
    communities: list = field(default_factory=list)
    large_communities: list = field(default_factory=list)

    @property
    def token(self):
        return self.nome

    def cidrs(self, fam):
        """Os CIDR do grupo, que nao tem tratamento por prefixo.

        O metodo existe porque as macros do import sao de alvo duplo: o
        StrictUndefined do render estoura no teste quando o alvo nao tem o
        que a macro pede.
        """
        return list(self.prefixos.get(fam) or [])

    def tratamentos(self, fam):
        """O grupo nao tem community por prefixo: a linha dele e CIDR puro."""
        return []

    def arquivo(self, saida):
        """O caminho do bloco deste grupo na pasta de saida do tenant dele.

        Sem default pelo mesmo motivo do peer: uma chamada esquecida
        escreveria na raiz do out/, que e o nome que a etapa dos tenants
        elimina.
        """
        return Path(saida) / ("grupo-%s.txt" % self.nome)

    def para_dict(self):
        return {
            "id": self.id, "nome": self.nome, "tipo": self.tipo,
            "asn": self.asn, "classe": self.classe, "lp_base": self.lp_base,
            "origem": self.origem, "pop": self.pop,
            "aprendizado": self.aprendizado, "ix_id": self.ix_id,
            "ap_block": self.ap_block, "ap_te": self.ap_te,
            "ap_allowed": self.ap_allowed, "ap_prefer": self.ap_prefer,
            "prepend_base": self.prepend_base, "bh_upstream": self.bh_upstream,
            "default_route": self.default_route, "bfd": self.bfd,
            "graceful_restart": self.graceful_restart,
            "timer_keepalive": self.timer_keepalive,
            "timer_hold": self.timer_hold, "prefixos": self.prefixos,
            "te_prefixos": self.te_prefixos,
            "communities": self.communities,
            "large_communities": self.large_communities,
        }

    @classmethod
    def de_dict(cls, d):
        conhecidos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in conhecidos})


def carregar_grupos(caminho=PEERS_YAML):
    dados = _ler_bruto(caminho)
    return [Grupo.de_dict(d) for d in dados.get("grupos", [])]


def gravar_grupos(grupos, caminho=PEERS_YAML):
    dados = _ler_bruto(caminho)
    dados["grupos"] = [g.para_dict() for g in grupos]
    _escrever_bruto(dados, caminho)


def achar_grupo(grupos, nome):
    for g in grupos:
        if g.nome == nome:
            return g
    return None


def achar_grupo_id(grupos, ident):
    for g in grupos:
        if g.id == ident:
            return g
    return None


@dataclass
class Bloco:
    """Um prefixo do proprio AS e o que ele leva alem da marca de origem.

    O `1000` nao e campo: ele e escrito pelo filtro gerado, sempre, e nao
    ha valor aqui que o substitua. O que o operador escreve nesta lista e
    o que vem junto dele.
    """

    prefixo: str = ""
    communities: list = field(default_factory=list)
    # fora de servico: a linha fica no cadastro com o tratamento, e o
    # prefixo nao sai em configuracao nenhuma. E o que a linha comecada
    # por `!-` na tela quer dizer.
    ativo: bool = True

    def para_dict(self):
        d = {"prefixo": self.prefixo, "communities": self.communities}
        if not self.ativo:
            d["ativo"] = False
        return d

    @classmethod
    def de_dict(cls, d):
        conhecidos = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in conhecidos})


def canoniza(cidr):
    """O CIDR canonico, ou o texto como veio quando nao analisa.

    O mesclar_blocos casa por prefixo canonico, e o formulario entrega o
    que o operador digitou ou colou. Sem esta passagem, um v6 em caixa
    alta nao casa com o que a consulta devolve em caixa baixa, o tratamento
    se solta do prefixo e o bloco sai duplicado na configuracao.

    A barra e exigida antes de analisar: o ip_network aceita um endereco
    cru e devolve /32, e sem esta linha o validate nunca veria o texto
    original e o prefixo sairia anunciado como host route. O que nao
    analisa fica como veio, para o validate recusar e o operador ler a
    mensagem.
    """
    if not isinstance(cidr, str):
        # campo vazio no yaml (`- prefixo:`) chega aqui como None, e o
        # validate e quem tem que recusar, com o campo e o texto
        return "" if cidr is None else str(cidr)
    if "/" not in cidr:
        return cidr
    try:
        return str(ipaddress.ip_network(cidr, strict=False))
    except ValueError:
        return cidr


def sem_marca(linha):
    """A linha sem o que vier depois do `!-` do fim.

    A marca do ausente e escrita pela consulta ao IRR, e o salvamento ignora
    o que vem depois dela. Vale para o peer, que ainda tem o `!-` do comeco
    como estado proprio, e para o grupo, que so conhece esta ponta.
    """
    return linha.split("!-")[0].strip()


def _bloco(item):
    """Um item de `prefixos`: a string de hoje, o dicionario, ou o Bloco.

    O dicionario passa pelo `Bloco.de_dict`, que e a mesma leitura da secao
    `blocos` do arquivo: chave desconhecida e ignorada, e o prefixo que
    vier torto fica como veio para o validate recusar.
    """
    if isinstance(item, Bloco):
        return item
    if isinstance(item, dict):
        bloco = Bloco.de_dict(item)
        bloco.prefixo = canoniza(bloco.prefixo)
        return bloco
    return Bloco(prefixo=canoniza(str(item)))


def _prefixo_gravado(bloco):
    """O item como ele vai para o yaml: string quando nao ha o que guardar.

    Um `peers.yaml` que nunca usou o tratamento continua com a lista de CIDR
    de sempre, e o primeiro salvamento de qualquer peer nao vira um diff de
    forma em todos os outros.
    """
    if bloco.ativo and not bloco.communities:
        return bloco.prefixo
    return bloco.para_dict()


def carregar_blocos(caminho=PEERS_YAML):
    """As duas listas do arquivo, com o prefixo ja canonico.

    A canonicalizacao e na leitura e nao na gravacao de proposito: o nome
    do filtro e o casamento da reconsulta saem os dois do prefixo, e um
    CIDR torto escrito a mao no yaml chegaria ate la sem que nada
    reclamasse. Canonico aqui, o resto do app so ve uma forma.
    """
    bruto = _ler_bruto(caminho).get(CHAVE_BLOCOS) or {}
    saida = {}
    for fam in FAMILIAS:
        saida[fam] = []
        for d in bruto.get(fam) or []:
            bloco = Bloco.de_dict(d)
            try:
                bloco.prefixo = str(ipaddress.ip_network(bloco.prefixo,
                                                         strict=False))
            except ValueError as erro:
                raise ValueError(
                    "%s: prefixo invalido em blocos.%s: %r"
                    % (caminho, fam, bloco.prefixo)) from erro
            saida[fam].append(bloco)
    return saida


def gravar_blocos(blocos, caminho=PEERS_YAML):
    """Grava as duas listas, e nao cria a chave quando as duas estao vazias.

    E o mesmo cuidado do gravar_asn: a ausencia da chave e o estado de
    quem nunca usou a tela, e gravar de volta nao tem por que transformar
    isso num diff.
    """
    dados = _ler_bruto(caminho)
    cheio = {fam: [b.para_dict() for b in blocos.get(fam) or []]
             for fam in FAMILIAS}
    if any(cheio.values()):
        dados[CHAVE_BLOCOS] = cheio
    else:
        dados.pop(CHAVE_BLOCOS, None)
    _escrever_bruto(dados, caminho)


def mesclar_blocos(salvos, consultados):
    """A lista da tela depois da consulta: (visiveis, ausentes).

    Casa por prefixo canonico, que e chave estavel: o tratamento escrito a
    mao sobrevive a reconsulta, o prefixo novo entra sem tratamento, e o
    que estava salvo e a consulta nao devolveu volta no fim da lista e
    tambem separado em `ausentes`, para a tela marcar. A decisao de manter
    ou remover e do operador, e por isso o ausente continua na lista.
    """
    por_prefixo = {b.prefixo: b for b in salvos}
    visiveis = []
    for cidr in consultados:
        chave = str(ipaddress.ip_network(cidr, strict=False))
        antigo = por_prefixo.pop(chave, None)
        visiveis.append(antigo if antigo is not None
                        else Bloco(prefixo=chave, communities=[]))
    ausentes = list(por_prefixo.values())
    return visiveis + ausentes, ausentes
