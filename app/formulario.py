"""O formulario da tela: o texto do POST vira Peer, Grupo, blocos e AS.

Mora fora do app.py para a API JSON (app/api.py) usar os mesmos helpers sem
importar o app.py, que e quem monta a API. O corpo das funcoes e o mesmo de
quando moravam la.
"""

import ipaddress

from app import plan, validate
from app import peers as peers_mod
from app.peers import Bloco, Grupo, Peer


CAMPOS_INT = ("asn", "id", "lp_base", "origem", "pop", "aprendizado",
              "ix_id", "prepend_base", "route_limit",
              "timer_keepalive", "timer_hold", "grupo_id")


CAMPOS_INT_GRUPO = ("id", "asn", "lp_base", "origem", "pop", "aprendizado",
                    "aprendizado_ix", "ix_id", "prepend_base",
                    "timer_keepalive", "timer_hold")


def _id_do_grupo_no_formulario(dados):
    """O id do grupo que o formulario mandou, ou None se veio vazio ou torto.

    Mesmo padrao do _id_do_formulario do peer: um POST a mao com um id que
    nao e numero nao pode estourar, so cair no caminho de "cria novo".
    """
    bruto = _texto(dados, "id")
    try:
        return int(bruto) if bruto else None
    except ValueError:
        return None


def _texto(dados, nome, padrao=""):
    return (dados.get(nome) or padrao).strip()


def _linhas(dados, nome):
    return [l.strip() for l in _texto(dados, nome).splitlines() if l.strip()]


def _sessoes(dados):
    sessoes = {}
    for fam in plan.FAMILIAS:
        local = _texto(dados, "sessao_%s_local" % fam)
        remoto = _texto(dados, "sessao_%s_remoto" % fam)
        sessoes[fam] = {"local": local, "remoto": remoto} if (local or remoto) else {}
    return sessoes


def _usados(registros, campo):
    """Os valores de um campo que ja aparecem em algum registro, ordenados.

    O POP e o ponto de aprendizado sao inventario do operador: o plano da a
    faixa, nao a lista. Entao o formulario nao inventa opcao nenhuma - ele
    sugere o que ja foi cadastrado, e o campo continua aceitando valor novo.
    Na primeira vez a lista sai vazia e o campo e um input comum.

    O helper nao soma lado nenhum: ele varre a lista que recebe. Quem monta a
    lista e quem chama: o /api/plano passa peers + grupos juntos para o
    aprendizado (o 3xxx e um espaco so) e so os peers para o POP.
    """
    vistos = set()
    for registro in registros:
        valor = getattr(registro, campo, None)
        if valor:
            vistos.add(valor)
    return sorted(vistos)


def _canoniza(cidr):
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
    if "/" not in cidr:
        return cidr
    try:
        return str(ipaddress.ip_network(cidr, strict=False))
    except ValueError:
        return cidr


def _blocos_do_formulario(dados):
    """As duas listas do bloco proprio: uma linha por prefixo.

    O formato e `<cidr> community community ...`. Linha que comeca com
    `!-` e um prefixo fora de servico: ele continua no cadastro com o
    tratamento dele e nao sai em configuracao nenhuma. O `!-` no fim da
    linha e a marca do que sumiu da consulta, e o salvamento ignora.
    """
    blocos = {}
    for fam in plan.FAMILIAS:
        blocos[fam] = []
        for linha in _linhas(dados, "blocos_%s" % fam):
            ativo = not linha.startswith("!-")
            corpo = linha[2:] if not ativo else linha
            pedacos = corpo.split("!-")[0].split()
            if not pedacos:
                continue
            blocos[fam].append(Bloco(prefixo=_canoniza(pedacos[0]),
                                     communities=pedacos[1:],
                                     ativo=ativo))
    return blocos


def _texto_blocos(blocos, ausentes=()):
    """O texto das duas textareas, com a marca de quem sumiu da consulta."""
    marcados = {b.prefixo for b in ausentes}
    saida = {}
    for fam in plan.FAMILIAS:
        linhas = []
        for b in blocos.get(fam) or []:
            corpo = " ".join([b.prefixo] + list(b.communities))
            if not b.ativo:
                corpo = "!- " + corpo
            elif b.prefixo in marcados:
                corpo += "  !- nao veio na consulta ao IRR"
            linhas.append(corpo)
        saida[fam] = "\n".join(linhas)
    return saida


def _aprendizado_padrao(tipo, peers, grupos):
    """O primeiro valor livre do bloco 3xxx do tipo, para o campo nascer cheio.

    O ponto de aprendizado continua sendo inventario do operador, e o campo
    aceita qualquer 3xxx: o que a tela faz aqui e so nao obrigar o operador a
    inventar um numero no meio do cadastro, num campo que a validacao exige.
    O bloco sai da tabela do PLANO (30xx para IX, 31xx para upstream) e
    termina no fim dele: bloco cheio devolve None, em branco, em vez de
    invadir a faixa do outro tipo.
    """
    base = plan.APRENDIZADO_BASE.get(tipo)
    if base is None:
        return None
    usados = {r.aprendizado for r in list(peers) + list(grupos)}
    usados.discard(None)
    limite = base + 99
    valor = base
    while valor in usados and valor < limite:
        valor += 1
    return valor if valor not in usados else None


def _padroes(rede=None):
    """As tabelas que o formulario usa para se preencher sozinho.

    O formulario em branco ja nasce preenchido pelo GET /api/peers/novo; este
    bloco existe para o operador que troca o tipo (ou a classe) dentro do
    proprio formulario, que ate agora nao mexia em campo nenhum. O JS le estas
    tabelas em vez de repetir os valores, entao a politica continua morando
    so no plan.py.

    O `origem_nome` e o unico item daqui que carrega o ASN: o nome do 1000 e
    "prefixo proprio do AS<ns>", entao ele sai do Rede da rede e nao da
    tabela do modulo.
    """
    rede = rede if rede is not None else plan.Rede()
    return {
        "tipos": {
            t: {
                "lp_base": plan.LP_BASE.get(t),
                "route_limit": plan.ROUTE_LIMIT.get(t),
                "timer_keepalive": plan.TIMER_PADRAO.get(t, (None, None))[0],
                "timer_hold": plan.TIMER_PADRAO.get(t, (None, None))[1],
            }
            for t in plan.TIPOS
        },
        "origem_tipo": dict(plan.ORIGEM),
        "origem_classe": dict(plan.ORIGEM_CLASSE),
        # os tipos em que a classe carrega a origem junto, para o JS nao
        # repetir a lista de tipos que o plan.py ja tem
        "downstream": list(plan.TIPOS_DOWNSTREAM),
        "origens_por_tipo": {t: list(v) for t, v in plan.ORIGENS_POR_TIPO.items()},
        # chave de JSON e string, entao o codigo vira texto aqui
        "origem_nome": {str(c): n for c, n in rede.ORIGEM_NOME.items()},
    }


def _origem_padrao(tipo, classe=None):
    """A origem que a tabela do plano da para o tipo (e para a classe).

    No cliente e no parceiro quem manda e a classe: o PLANO da 1100 ao
    transito e 1110, 1120 e 1130 as outras tres. Nos demais tipos e uma
    origem por tipo, que nao depende de campo nenhum. O formulario em branco
    mostra este valor, e o salvar cai nele quando o campo chega vazio - em
    branco a origem estourava o "%d" do render, depois do peer ja gravado.
    """
    if tipo in plan.TIPOS_DOWNSTREAM and classe in plan.ORIGEM_CLASSE:
        return plan.ORIGEM_CLASSE[classe]
    return plan.ORIGEM.get(tipo, plan.ORIGEM["cliente"])


def _id_do_formulario(dados):
    """O id que o formulario mandou, ou None se veio vazio ou torto."""
    bruto = _texto(dados, "id_original")
    try:
        return int(bruto) if bruto else None
    except ValueError:
        return None


def _anterior(peers, dados):
    """A entrada que este POST substitui, ou None quando ele cria uma nova.

    A identidade do registro e o id do campo escondido, e so ele: o token
    nao serve, porque e derivado do ASN e muda junto com ele. Um POST sem
    o campo cria entrada nova, e o validar recusa a que repetir um ASN ja
    cadastrado. Procurar a entrada pelo token, quando o campo faltasse,
    era o caminho por onde um ASN ja usado sobrescrevia em silencio o peer
    que ja estava la.
    """
    ident = _id_do_formulario(dados)
    if ident is None:
        return None
    return peers_mod.achar_id(peers, ident)


def peer_do_formulario(dados, peers, anterior=None, grupos=()):
    """Formulario achatado -> Peer. Devolve (peer, erros_de_campo).

    O formulario usa nomes planos (prefixos_v4, sessao_v4_remoto)
    porque e isso que o formulario manda; o Peer e aninhado por
    familia.
    """
    tipo = _texto(dados, "tipo", "cliente")
    apelido = _texto(dados, "apelido")
    classe = _texto(dados, "classe") or None

    erros = []
    if tipo not in plan.TIPOS:
        # o mesmo portao do GET /api/peers/novo, com o erro junto: o formulario
        # so oferece os quatro, e o peer nao pode ser gravado com um tipo que
        # nao tem template nem tabela no plano. Sem isto o POST gravava o
        # peer e o render estourava, com TemplateNotFound, depois da
        # gravacao - o mesmo estrago da origem em branco.
        erros.append(validate.Erro("tipo", "tipo desconhecido: %s" % tipo))
        tipo = "cliente"

    valores = {}
    for nome in CAMPOS_INT:
        bruto = _texto(dados, nome)
        if not bruto:
            valores[nome] = None
            continue
        try:
            valores[nome] = int(bruto)
        except ValueError:
            erros.append(validate.Erro(nome, "valor numerico invalido"))
            valores[nome] = None

    k, h = plan.TIMER_PADRAO.get(tipo, (None, None))
    # id, lp_base, route_limit e origem caem no default da tabela quando em
    # branco
    ident = valores.get("id")
    if ident is None:
        ident = anterior.id if anterior else peers_mod.proximo_id(peers, grupos)
    lp = valores.get("lp_base")
    if lp is None:
        lp = plan.LP_BASE.get(tipo, 300)
    limite = valores.get("route_limit")
    if limite is None:
        limite = plan.ROUTE_LIMIT.get(tipo, 50)
    origem = valores.get("origem")
    if origem is None:
        origem = _origem_padrao(tipo, classe)

    peer = Peer(
        id=ident,
        apelido=apelido,
        nome=_texto(dados, "nome"),
        tipo=tipo,
        asn=valores.get("asn") or 0,
        classe=classe,
        descricao=_texto(dados, "descricao"),
        lp_base=lp,
        origem=origem,
        pop=valores.get("pop"),
        aprendizado=valores.get("aprendizado"),
        ix_id=valores.get("ix_id"),
        prefixos={f: _linhas(dados, "prefixos_%s" % f) for f in plan.FAMILIAS},
        te_prefixos={f: _linhas(dados, "te_prefixos_%s" % f) for f in plan.FAMILIAS},
        ap_block=_linhas(dados, "ap_block"),
        ap_te=_linhas(dados, "ap_te"),
        ap_allowed=_linhas(dados, "ap_allowed"),
        ap_prefer=_linhas(dados, "ap_prefer"),
        communities=_linhas(dados, "communities"),
        large_communities=_linhas(dados, "large_communities"),
        bfd=dados.get("bfd") == "on",
        graceful_restart=dados.get("graceful_restart") == "on",
        timer_keepalive=valores.get("timer_keepalive") or k,
        timer_hold=valores.get("timer_hold") or h,
        prepend_base=valores.get("prepend_base") or 0,
        route_limit=limite,
        sessoes=_sessoes(dados),
        bh_upstream=_texto(dados, "bh_upstream"),
        default_route=dados.get("default_route") == "on",
        # o grupo_id vale nos cinco tipos: o membro herda do grupo o mesmo
        # objeto em qualquer um deles. Quem recusa o par errado - grupo que
        # nao existe, de outro tipo, ou ASN divergente - e o validate, com
        # mensagem propria; um portao de tipo aqui seria uma segunda regra
        # para divergir da primeira, e era ele que deixava um peer de
        # upstream com grupo escolhido na tela salvar grupo_id nulo, sem erro
        # nenhum, com o grupo ficando vazio.
        grupo_id=valores.get("grupo_id"),
    )
    return peer, erros


def _aprendizado_do_grupo(valores, tipo):
    """O ponto de aprendizado do bloco do tipo escolhido.

    Os blocos de upstream e de IX ficam lado a lado na mesma tela e cada um
    tem o seu campo. O bloco que nao e do tipo escolhido fica escondido, mas
    continua no formulario e chega em branco no POST. Com um nome so para os
    dois, o dict(form) guardava o ultimo: o branco do bloco escondido apagava
    o que o operador digitou no visivel, e o salvar recusava o campo dizendo
    que ele estava vazio, com o numero escrito na frente dele. Ler o campo do
    bloco do tipo resolve os dois lados - nem o vazio nem um valor do outro
    tipo passam por cima do que o operador escolheu.
    """
    if tipo == "ix":
        return valores.get("aprendizado_ix")
    return valores.get("aprendizado")


def grupo_do_formulario(dados, grupos, anterior=None, peers=()):
    """Formulario achatado -> Grupo. Devolve (grupo, erros_de_campo).

    Mesmo esquema do peer_do_formulario, sem os campos que so o peer avulso
    tem (apelido, communities, sessoes)."""
    tipo = _texto(dados, "tipo", "parceiro")

    erros = []
    valores = {}
    for nome in CAMPOS_INT_GRUPO:
        bruto = _texto(dados, nome)
        if not bruto:
            valores[nome] = None
            continue
        try:
            valores[nome] = int(bruto)
        except ValueError:
            # sem isto o campo torto virava None e o grupo era gravado com o
            # valor da tabela, como se o operador nao tivesse digitado nada:
            # o peer ja devolvia este erro, o grupo nao
            #
            # o id fica de fora porque ele nao e campo que o operador digita no
            # grupo: quem diz qual grupo este POST substitui e a URL, e o id
            # torto ou em branco vira None e cai no `valores.get("id")` de
            # baixo, que devolve o do registro anterior quando ha um e o
            # proximo livre quando nao ha.
            if nome != "id":
                erros.append(validate.Erro(nome, "valor numerico invalido"))
            valores[nome] = None

    ident = valores.get("id")
    if ident is None:
        ident = anterior.id if anterior else peers_mod.proximo_id(peers, grupos)

    # o lp_base em branco cai no default do tipo, como no peer, mas o zero
    # digitado vale: ele e da faixa do validar (0 a 65535) e no `or 300` o
    # operador so descobria que perdeu o zero depois de gravar
    lp = valores.get("lp_base")
    if lp is None:
        lp = plan.LP_BASE.get(tipo, 300)

    grupo = Grupo(
        id=ident,
        nome=_texto(dados, "nome").upper(),
        tipo=tipo,
        asn=valores.get("asn"),
        # o campo so aparece em cliente/parceiro. Num tipo que nao o usa, o
        # hidden nao existe e o form manda vazio: guardar None e o que a
        # validacao cobra depois, sem classe orfa num grupo de upstream
        classe=(_texto(dados, "classe") or None
                if tipo in plan.TIPOS_DOWNSTREAM else None),
        lp_base=lp,
        origem=valores.get("origem"),
        pop=valores.get("pop") if tipo in plan.TIPOS_DOWNSTREAM else None,
        aprendizado=_aprendizado_do_grupo(valores, tipo),
        ix_id=valores.get("ix_id"),
        ap_block=_linhas(dados, "ap_block"),
        ap_te=_linhas(dados, "ap_te"),
        ap_allowed=_linhas(dados, "ap_allowed"),
        ap_prefer=_linhas(dados, "ap_prefer"),
        # o prepend_base fica no `or 0` do peer: zero e o valor de repouso
        # dele, entao em branco e "0" dao no mesmo, sem perda nenhuma
        prepend_base=valores.get("prepend_base") or 0,
        bh_upstream=_texto(dados, "bh_upstream"),
        default_route=dados.get("default_route") == "on",
        bfd=dados.get("bfd") == "on",
        graceful_restart=dados.get("graceful_restart") == "on",
        timer_keepalive=valores.get("timer_keepalive"),
        timer_hold=valores.get("timer_hold"),
        prefixos={f: _linhas(dados, "prefixos_%s" % f) for f in plan.FAMILIAS},
        te_prefixos={f: _linhas(dados, "te_prefixos_%s" % f) for f in plan.FAMILIAS},
        communities=_linhas(dados, "communities"),
        large_communities=_linhas(dados, "large_communities"),
    )
    return grupo, erros


def _ativos(blocos):
    """So os prefixos em servico vao para a configuracao."""
    return {fam: [b for b in blocos.get(fam) or [] if b.ativo]
            for fam in plan.FAMILIAS}


def _asn_do_formulario(dados):
    """(asn, politica, erros) do formulario do topo.

    O namespace em branco e o estado "nao declarado", e nao o zero: e o que
    todo ASN de ate 16 bits usa, e e o que faz o gravar_asn apagar a chave
    em vez de deixar no arquivo uma que diria outra coisa que nao a que a
    tela mostra.

    O campo aceita o que o operador cola: espaco nas pontas sai no _texto, e
    o que sobra tem que ser digito ascii. Um valor torto vira erro de campo
    no lugar de estourar no int().

    Passando os digitos, as faixas sao conferidas aqui e nao so no
    plan.Rede, que as confere de novo ao montar. O Rede nao sabe de
    formulario: o ValueError dele nao diz em que campo o operador errou nem
    o que fazer, e a tela antiga ancorava os dois no campo do AS. Como as
    duas faixas sao de campos diferentes - o AS e um ASN, o namespace e um
    16 bits -, a conferencia daqui e o que poe cada erro no campo que o
    causou.
    """
    erros = []
    valores = {}
    for campo, chave in (("asn_rede", "asn"), ("asn_politica", "politica")):
        bruto = _texto(dados, campo)
        if not bruto:
            valores[chave] = None
        elif not (bruto.isascii() and bruto.isdigit()):
            erros.append(validate.Erro(campo, "so digitos: %s" % bruto))
        else:
            valores[chave] = int(bruto)
    if not erros:
        if valores.get("asn") is None:
            erros.append(validate.Erro("asn_rede", "informe o AS da rede"))
        erros.extend(_conferir_faixas(valores))
    return valores.get("asn"), valores.get("politica"), erros


def _conferir_faixas(valores):
    """O limite de cada campo, no campo a que ele pertence.

    O AS da rede e um ASN de verdade e segue a faixa que o validate ja exige
    dos peers e dos grupos. O namespace das standard e outra coisa: um
    numero de 16 bits, que e o que a RFC 1997 sabe escrever na community.
    Sao dois numeros do mesmo tamanho na tela e de larguras diferentes na
    regra, entao a mensagem de cada um diz qual dos dois entra ali.
    """
    erros = []
    asn = valores.get("asn")
    politica = valores.get("politica")
    if asn is not None:
        if not validate.ASN_MIN <= asn <= validate.ASN_MAX:
            erros.append(validate.Erro(
                "asn_rede", "ASN de %d a %d: %d"
                % (validate.ASN_MIN, validate.ASN_MAX, asn)))
        elif asn in validate.ASN_RESERVADOS:
            erros.append(validate.Erro(
                "asn_rede", "ASN reservado pela IANA: %d" % asn))
    if politica is not None and not plan.NS_MIN <= politica <= plan.NS_MAX:
        erros.append(validate.Erro(
            "asn_politica",
            "namespace das standard vai de %d a %d: o ASN de 32 bits fica no "
            "campo ao lado" % (plan.NS_MIN, plan.NS_MAX)))
    elif asn is not None and asn > plan.NS_MAX and politica is None:
        erros.append(validate.Erro(
            "asn_politica",
            "ASN de 32 bits: informe o namespace das standard (%d a %d), que "
            "e o numero que entra nas communities"
            % (plan.NS_MIN, plan.NS_MAX)))
    return erros


def peer_em_branco(tipo, peers, grupos):
    """O peer novo do tipo: os defaults da tabela do plano e o proximo ID livre.

    E o formulario em branco do GET /api/peers/novo. Tipo fora do plano vira
    cliente.
    """
    if tipo not in plan.TIPOS:
        tipo = "cliente"
    k, h = plan.TIMER_PADRAO.get(tipo, (None, None))
    return Peer(tipo=tipo, id=peers_mod.proximo_id(peers, grupos),
                lp_base=plan.LP_BASE.get(tipo, 300),
                origem=_origem_padrao(tipo),
                route_limit=plan.ROUTE_LIMIT.get(tipo, 50),
                timer_keepalive=k, timer_hold=h,
                aprendizado=_aprendizado_padrao(tipo, peers, grupos))


def grupo_em_branco(tipo, peers, grupos):
    """O grupo novo do tipo: os defaults da tabela e o proximo ID livre.

    E o formulario em branco do GET /api/grupos/novo. Tipo fora do plano vira
    parceiro.
    """
    if tipo not in plan.TIPOS:
        tipo = "parceiro"
    k, h = plan.TIMER_PADRAO.get(tipo, (None, None))
    return Grupo(tipo=tipo, id=peers_mod.proximo_id(peers, grupos),
                 lp_base=plan.LP_BASE.get(tipo, 300),
                 origem=_origem_padrao(tipo),
                 timer_keepalive=k, timer_hold=h,
                 aprendizado=_aprendizado_padrao(tipo, peers, grupos))


# Os campos que so valem para alguns tipos, pelo nome de campo do formulario.
# Campo fora da tabela vale para todos. A tela nova le as duas tabelas pelo
# GET /api/plano e esconde o campo nos outros tipos, a menos que ele tenha
# valor ou erro: esconder um campo com valor deixaria um dado gravado sem
# ninguem ver.
#
# A tabela vem do render e da validacao, e nao da tela: um campo pertence a um
# tipo quando muda a saida daquele tipo ou quando a validacao o exige ali. O
# test_formulario.py refaz essa conferencia a cada execucao. O
# default_route muda a saida de todo tipo (o macro e comum), mas o validate so
# o aceita em cliente e parceiro. O apelido nao esta aqui: a tag dizia "IX e
# PNI", mas ele muda o token de qualquer tipo, e o cadastro tem upstream com
# apelido.
CAMPOS_POR_TIPO = {
    "classe": ("cliente", "parceiro"),
    "pop": ("cliente", "parceiro"),
    "default_route": ("cliente", "parceiro"),
    "aprendizado": ("upstream", "ix"),
    "prepend_base": ("upstream",),
    "bh_upstream": ("upstream",),
    "ap_block": ("upstream",),
    "ap_te": ("upstream",),
    "te_prefixos_v4": ("upstream",),
    "te_prefixos_v6": ("upstream",),
    "ix_id": ("ix",),
    "ap_prefer": ("ix",),
    "ap_allowed": ("pni",),
    "communities": ("cliente", "parceiro", "upstream"),
    "large_communities": ("cliente", "parceiro", "upstream"),
}

# No grupo o quadro "ao criar" e so do upstream (plan.quadro_ao_criar), entao
# as communities sao so dele, e o aprendizado do IX tem campo proprio.
CAMPOS_POR_TIPO_GRUPO = {
    "classe": ("cliente", "parceiro"),
    "pop": ("cliente", "parceiro"),
    "default_route": ("cliente", "parceiro"),
    "aprendizado": ("upstream",),
    "aprendizado_ix": ("ix",),
    "prepend_base": ("upstream",),
    "bh_upstream": ("upstream",),
    "ap_block": ("upstream",),
    "ap_te": ("upstream",),
    "te_prefixos_v4": ("upstream",),
    "te_prefixos_v6": ("upstream",),
    "communities": ("upstream",),
    "large_communities": ("upstream",),
    "ix_id": ("ix",),
    "ap_prefer": ("ix",),
    "ap_allowed": ("pni",),
}
