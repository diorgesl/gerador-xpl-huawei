"""API JSON do bgpgen, montada em /api.

A regra continua no formulario.py, no validate.py e no render.py. As rotas
daqui convertem o JSON no dicionario de texto do POST e chamam os helpers
desses tres modulos, entao a mensagem de erro, o default de cada campo e o
bloco gerado saem do mesmo lugar: o formulario em texto do POST/PUT vira Peer,
e o Peer vira JSON de volta.
"""

from dataclasses import replace

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from app import auth
from app import formulario as form
from app import peers as peers_mod
from app import plan, prefixes, render, validate
from app.modelos_api import (Aviso, Blocos, BlocosIrrPedido, BlocosTexto,
                             Config, ErroResposta, GrupoForm, GrupoRegistro,
                             GrupoResumo, GrupoSalvo, IrrPedido, LoginPedido,
                             Membro, PeerForm, PeerRegistro, PeerResumo,
                             PeerSalvo, Plano, Prefixos, Previa, RedeAtual,
                             RedeForm, Saida, SecaoConfig, SessaoResposta)


def _texto(valor):
    return "" if valor is None else str(valor)


def _lista(valores):
    # o yaml escrito a mao pode trazer o ASN de uma lista de AS-path como
    # numero; o formulario so conhece texto
    return [str(v) for v in valores or []]


def dados_do_formulario(modelo):
    """Modelo -> o dicionario de texto que o formulario.py le.

    Caixa marcada vira "on" e desmarcada fica fora, como no POST do
    navegador; lista vira uma linha por item, como na textarea.
    """
    dados = {}
    for nome, valor in modelo.model_dump().items():
        if isinstance(valor, bool):
            if valor:
                dados[nome] = "on"
        elif isinstance(valor, list):
            dados[nome] = "\n".join(valor)
        else:
            dados[nome] = valor
    return dados


def modelo_do_peer(peer):
    """Peer -> o formulario em JSON que o PeerRegistro carrega."""
    campos = dict(
        id=_texto(peer.id), apelido=peer.apelido, nome=peer.nome,
        tipo=peer.tipo, grupo_id=_texto(peer.grupo_id),
        # o peer novo nasce com asn 0, e o que a tela mostra e o campo vazio
        asn=_texto(peer.asn or None),
        descricao=peer.descricao, classe=peer.classe or "",
        lp_base=_texto(peer.lp_base), origem=_texto(peer.origem),
        pop=_texto(peer.pop), aprendizado=_texto(peer.aprendizado),
        ix_id=_texto(peer.ix_id), route_limit=_texto(peer.route_limit),
        prepend_base=_texto(peer.prepend_base),
        timer_keepalive=_texto(peer.timer_keepalive),
        timer_hold=_texto(peer.timer_hold),
        bfd=peer.bfd, graceful_restart=peer.graceful_restart,
        default_route=peer.default_route, bh_upstream=peer.bh_upstream,
        ap_block=_lista(peer.ap_block), ap_te=_lista(peer.ap_te),
        ap_allowed=_lista(peer.ap_allowed), ap_prefer=_lista(peer.ap_prefer),
        communities=_lista(peer.communities),
        large_communities=_lista(peer.large_communities),
    )
    for fam in plan.FAMILIAS:
        sessao = peer.sessoes.get(fam) or {}
        campos["prefixos_%s" % fam] = _lista(peer.prefixos.get(fam))
        campos["te_prefixos_%s" % fam] = _lista(peer.te_prefixos.get(fam))
        campos["sessao_%s_local" % fam] = sessao.get("local", "")
        campos["sessao_%s_remoto" % fam] = sessao.get("remoto", "")
    return PeerForm(**campos)


def modelo_do_grupo(grupo):
    """Grupo -> o formulario em JSON que o GrupoRegistro carrega."""
    ix = grupo.tipo == "ix"
    campos = dict(
        id=_texto(grupo.id), nome=grupo.nome, tipo=grupo.tipo,
        asn=_texto(grupo.asn), classe=grupo.classe or "",
        lp_base=_texto(grupo.lp_base), origem=_texto(grupo.origem),
        pop=_texto(grupo.pop),
        # o aprendizado do IX mora no campo do bloco do IX, o dos outros no
        # campo comum: e o que o _aprendizado_do_grupo le de volta
        aprendizado="" if ix else _texto(grupo.aprendizado),
        aprendizado_ix=_texto(grupo.aprendizado) if ix else "",
        ix_id=_texto(grupo.ix_id), prepend_base=_texto(grupo.prepend_base),
        timer_keepalive=_texto(grupo.timer_keepalive),
        timer_hold=_texto(grupo.timer_hold),
        bfd=grupo.bfd, graceful_restart=grupo.graceful_restart,
        default_route=grupo.default_route, bh_upstream=grupo.bh_upstream,
        ap_block=_lista(grupo.ap_block), ap_te=_lista(grupo.ap_te),
        ap_allowed=_lista(grupo.ap_allowed), ap_prefer=_lista(grupo.ap_prefer),
        communities=_lista(grupo.communities),
        large_communities=_lista(grupo.large_communities),
    )
    for fam in plan.FAMILIAS:
        campos["prefixos_%s" % fam] = _lista(grupo.prefixos.get(fam))
        campos["te_prefixos_%s" % fam] = _lista(grupo.te_prefixos.get(fam))
    return GrupoForm(**campos)


# As tres rotas de sessao sao as unicas de /api que respondem sem cookie:
# o /login precisa entrar antes de haver sessao, e o /sessao e o que a SPA
# consulta para saber se mostra a casca. O roteador de baixo e o protegido,
# e a dependencia fica nele inteiro, e nao rota a rota.
publico = APIRouter(prefix="/api", responses={
    404: {"model": ErroResposta}, 422: {"model": ErroResposta}})

roteador = APIRouter(prefix="/api", dependencies=[Depends(auth.exigir_login)],
                     responses={
                         401: {"model": ErroResposta},
                         404: {"model": ErroResposta},
                         422: {"model": ErroResposta}})


def _yaml():
    # lido na hora, e nao no import: os testes trocam o peers_mod.PEERS_YAML
    # por um arquivo temporario depois que este modulo ja foi importado
    return peers_mod.PEERS_YAML


def _rede():
    return peers_mod.carregar_asn(_yaml())


def _peers():
    return peers_mod.carregar(_yaml())


def _grupos():
    return peers_mod.carregar_grupos(_yaml())


def _avisos(avisos):
    return [Aviso(campo=a.campo, mensagem=a.mensagem) for a in avisos]


def _falha(status, erros, avisos=()):
    """A recusa de toda rota: {"erros": {campo: mensagem}, "avisos": [...]}.

    O erros_para_dict deixa o primeiro erro de cada campo vencer: o erro de
    conversao do formulario vem antes do da validacao.
    """
    corpo = ErroResposta(erros=validate.erros_para_dict(erros),
                         avisos=_avisos(avisos))
    return JSONResponse(status_code=status, content=corpo.model_dump())


def _modelo_rede(rede):
    # o namespace em branco e o estado "nao declarado": o ASN de 16 bits usa
    # o proprio numero
    politica = "" if rede.politica == rede.asn else str(rede.politica)
    return RedeAtual(asn=rede.ASN, politica=politica)


@roteador.get("/plano", response_model=Plano)
def ler_plano():
    """A rede e as tabelas do plano que o formulario usa para se preencher."""
    rede, peers, grupos = _rede(), _peers(), _grupos()
    return Plano(
        rede=_modelo_rede(rede),
        padroes=form._padroes(rede),
        tipos=list(plan.TIPOS),
        tipos_com_criar_lista=list(plan.TIPOS_COM_APPLY_PEER),
        classes_cliente=list(plan.CLASSES_CLIENTE),
        lp_base=dict(plan.LP_BASE),
        route_limit=dict(plan.ROUTE_LIMIT),
        route_limit_exemplo=dict(plan.ROUTE_LIMIT_EXEMPLO),
        prepend_max=plan.PREPEND_MAX,
        prepend_implementado=plan.PREPEND_IMPLEMENTADO,
        pop_min=plan.POP_MIN, pop_max=plan.POP_MAX,
        aprendizado_min=plan.APRENDIZADO_MIN,
        aprendizado_max=plan.APRENDIZADO_MAX,
        # o 3xxx e um espaco so: o que foi cadastrado num grupo tambem e
        # sugerido no peer
        pop_usados=form._usados(peers, "pop"),
        aprendizado_usados=form._usados(peers + grupos, "aprendizado"),
        campos_por_tipo={c: list(t) for c, t in form.CAMPOS_POR_TIPO.items()},
        campos_por_tipo_grupo={c: list(t)
                               for c, t in form.CAMPOS_POR_TIPO_GRUPO.items()},
    )


@roteador.put("/rede", response_model=RedeAtual)
def gravar_rede(pedido: RedeForm):
    """O AS da rede no topo do peers.yaml, pelas conferencias do
    _asn_do_formulario."""
    asn, politica, erros = form._asn_do_formulario(
        {"asn_rede": pedido.asn, "asn_politica": pedido.politica})
    if not erros:
        try:
            peers_mod.gravar_asn(asn, politica, _yaml())
        except ValueError as exc:
            # as faixas ja foram conferidas; o que chega aqui e o que escapou
            # delas, e a mensagem do plan e a que nomeia
            erros = [validate.Erro("asn_rede", str(exc))]
    if erros:
        return _falha(422, erros)
    return _modelo_rede(_rede())


def _nao_encontrado(o_que):
    return _falha(404, [validate.Erro("_", "%s nao encontrado" % o_que)])


def _registro_peer(peer):
    # o peer novo ainda nao tem token: sem ASN nem apelido, o token seria "0"
    token = peer.token if (peer.apelido or peer.asn) else ""
    return PeerRegistro(id=peer.id, token=token, formulario=modelo_do_peer(peer))


@roteador.get("/peers", response_model=list[PeerResumo])
def listar_peers():
    return [PeerResumo(id=p.id, token=p.token, tipo=p.tipo, asn=p.asn,
                       apelido=p.apelido, nome=p.nome, grupo_id=p.grupo_id)
            for p in _peers()]


# /peers/novo vem antes de /peers/{ident}: na ordem inversa o "novo" cairia
# no {ident} e voltaria 422 por nao ser numero
@roteador.get("/peers/novo", response_model=PeerRegistro)
def novo_peer(tipo: str = "cliente"):
    return _registro_peer(form.peer_em_branco(tipo, _peers(), _grupos()))


@roteador.get("/peers/{ident}", response_model=PeerRegistro)
def ler_peer(ident: int):
    peer = peers_mod.achar_id(_peers(), ident)
    if peer is None:
        return _nao_encontrado("peer")
    return _registro_peer(peer)


@roteador.get("/peers/{ident}/copia", response_model=PeerRegistro)
def copiar_peer(ident: int):
    """O peer inteiro com o proximo ID livre, para abrir como peer novo.

    Nao grava nada. O salvar recusa o que a copia repetir (token, IP remoto,
    prefixo de downstream) e aponta o campo, e o operador corrige ali.
    """
    peers, grupos = _peers(), _grupos()
    peer = peers_mod.achar_id(peers, ident)
    if peer is None:
        return _nao_encontrado("peer")
    return _registro_peer(replace(peer, id=peers_mod.proximo_id(peers, grupos)))


def _peer_do_pedido(formulario, peers, grupos, anterior):
    """(peer, erros) do formulario, pelo mesmo caminho do POST /api/peers.

    A propria entrada fica na lista: quem a dispensa e o validar, pelo
    registro `anterior`, que por isso tem que ser o objeto desta mesma lista.
    """
    peer, erros = form.peer_do_formulario(
        dados_do_formulario(formulario), peers, anterior, grupos=grupos)
    erros = erros + validate.validar(peer, peers, anterior=anterior, grupos=grupos)
    return peer, erros


def _grupo_do_peer(peer, grupos):
    if peer.grupo_id is None:
        return None
    return peers_mod.achar_grupo_id(grupos, peer.grupo_id)


def _salvar_peer(formulario, peers, anterior):
    grupos, rede = _grupos(), _rede()
    peer, erros = _peer_do_pedido(formulario, peers, grupos, anterior)
    avisos = validate.avisos(peer, peers, rede=rede)
    if erros:
        return _falha(422, erros, avisos)
    if anterior is None:
        peers.append(peer)
    else:
        peers[peers.index(anterior)] = peer
        if anterior.arquivo() != peer.arquivo():
            # trocou o token ou o tipo: o bloco com o nome velho sai de out/,
            # senao fica um orfao que o operador pode colar por engano
            anterior.arquivo().unlink(missing_ok=True)
    peers_mod.gravar(peers, _yaml())
    destino = render.escrever_peer(peer, grupo=_grupo_do_peer(peer, grupos),
                                   rede=rede)
    return PeerSalvo(registro=_registro_peer(peer), arquivo=destino.name,
                     avisos=_avisos(avisos))


@roteador.post("/peers", response_model=PeerSalvo, status_code=201)
def criar_peer(formulario: PeerForm):
    return _salvar_peer(formulario, _peers(), None)


@roteador.put("/peers/{ident}", response_model=PeerSalvo)
def atualizar_peer(ident: int, formulario: PeerForm):
    """Atualiza o registro do ID da URL.

    O ID do corpo e editavel: se o operador o trocou, o registro da URL passa
    ao ID novo, e o validar recusa o que ja for de outro peer ou grupo.
    """
    peers = _peers()
    anterior = peers_mod.achar_id(peers, ident)
    if anterior is None:
        return _nao_encontrado("peer")
    return _salvar_peer(formulario, peers, anterior)


@roteador.delete("/peers/{ident}", status_code=204)
def excluir_peer(ident: int):
    # a confirmacao e um dialogo na tela nova, e nao um campo do pedido
    peers = _peers()
    peer = peers_mod.achar_id(peers, ident)
    if peer is None:
        return _nao_encontrado("peer")
    peer.arquivo().unlink(missing_ok=True)
    peers.remove(peer)
    peers_mod.gravar(peers, _yaml())
    return Response(status_code=204)


def _ler(caminho):
    """O que esta salvo em out/, ou None quando o arquivo nao existe.

    O errors="replace" e para o arquivo editado a mao com acento: o diff da
    tela mostra a linha estranha em vez de a previa inteira cair.
    """
    if not caminho.exists():
        return None
    return caminho.read_text(encoding="ascii", errors="replace")


def _criar_lista_do_peer(peer, rede):
    # o par CL-PEER-<T> / APPLY-PEER-<T> e de cliente, parceiro e upstream;
    # nos outros tipos o quadro nao tem o que criar
    if peer.tipo not in plan.TIPOS_COM_APPLY_PEER:
        return None
    return render.render_criar_lista(peer, rede=rede)


@roteador.post("/peers/previa", response_model=Previa)
def previa_peer(formulario: PeerForm,
                ident: int | None = Query(default=None, alias="id")):
    """Valida e monta os blocos do formulario sem gravar nada.

    O `id` e o do registro que a tela esta editando, e falta no peer novo. O
    erro de validacao volta em 200 e sem bloco. A remocao fica de fora: ela
    desfaz o que esta no equipamento, e o que esta no equipamento e o registro
    salvo, que o GET /api/peers/{ident}/saida devolve.
    """
    peers, grupos, rede = _peers(), _grupos(), _rede()
    anterior = peers_mod.achar_id(peers, ident) if ident is not None else None
    peer, erros = _peer_do_pedido(formulario, peers, grupos, anterior)
    avisos = _avisos(validate.avisos(peer, peers, rede=rede))
    salvo = _ler(anterior.arquivo()) if anterior is not None else None
    if erros:
        return Previa(erros=validate.erros_para_dict(erros), avisos=avisos,
                      salvo=salvo)
    return Previa(
        bloco=render.render_peer(peer, grupo=_grupo_do_peer(peer, grupos),
                                 rede=rede),
        criar_lista=_criar_lista_do_peer(peer, rede),
        arquivo=peer.arquivo().name, salvo=salvo, avisos=avisos)


@roteador.get("/peers/{ident}/saida", response_model=Saida)
def saida_peer(ident: int):
    peer = peers_mod.achar_id(_peers(), ident)
    if peer is None:
        return _nao_encontrado("peer")
    grupo = _grupo_do_peer(peer, _grupos())
    if peer.grupo_id is not None and grupo is None:
        # o yaml aponta para um grupo que saiu (edicao a mao, gravacao pela
        # metade): sem ele o membro perde o que herdava, e a rota recusa com
        # 422 no lugar da Saida
        return _falha(422, [validate.Erro("grupo_id", "grupo nao encontrado")])
    rede = _rede()
    return Saida(bloco=render.render_peer(peer, grupo=grupo, rede=rede),
                 remover=render.render_remove(peer, grupo=grupo, rede=rede),
                 criar_lista=_criar_lista_do_peer(peer, rede),
                 arquivo=peer.arquivo().name)


@roteador.post("/irr", response_model=Prefixos,
               responses={502: {"model": ErroResposta}})
def consultar_irr(pedido: IrrPedido):
    """Os prefixos do ASN no IRR, pelo bgpq4, sem gravar nada.

    A consulta precisa so do ASN e do apelido: o resultado vai para os campos
    de prefixo da tela, que o operador ainda edita antes de salvar.
    """
    bruto = pedido.asn.strip()
    if bruto and not (bruto.isascii() and bruto.isdigit()):
        return _falha(422, [validate.Erro("asn", "valor numerico invalido")])
    if not bruto or int(bruto) <= 0:
        return _falha(422, [validate.Erro(
            "asn", "informe o ASN antes de consultar o IRR")])
    asn = int(bruto)
    try:
        coleta = prefixes.coletar(asn, pedido.apelido.strip() or str(asn),
                                  forcar=pedido.forcar)
    except (OSError, RuntimeError, ValueError) as exc:
        return _falha(502, [validate.Erro("bgpq4", str(exc))])
    return Prefixos(v4=coleta.get("v4") or [], v6=coleta.get("v6") or [])


def _membros(grupo, peers):
    return [Membro(id=p.id, token=p.token) for p in peers if p.grupo_id == grupo.id]


def _registro_grupo(grupo, peers):
    return GrupoRegistro(id=grupo.id, nome=grupo.nome,
                         formulario=modelo_do_grupo(grupo),
                         membros=_membros(grupo, peers))


def _grupo_do_pedido(formulario, grupos, peers, anterior):
    """(grupo, erros) do formulario, pelo mesmo caminho do POST /api/grupos.

    Duas regras do ID, as duas porque quem diz qual grupo se edita e a URL:
    - editando, vale o ID da URL e o do corpo e ignorado;
    - criando, ID que ja e de outro grupo e erro. O validar_grupo so confere o
      ID contra os peers, que dividem o mesmo espaco do eixo 5PPA.
    """
    dados = dados_do_formulario(formulario)
    if anterior is not None:
        dados["id"] = str(anterior.id)
    grupo, erros = form.grupo_do_formulario(dados, grupos, anterior, peers=peers)
    if anterior is None:
        outro = peers_mod.achar_grupo_id(grupos, grupo.id)
        if outro is not None:
            erros.append(validate.Erro(
                "id", "ID ja usado pelo grupo %s" % outro.nome))
    # os erros de campo vem na frente, como no salvar do peer
    erros = erros + validate.validar_grupo(grupo, grupos, peers, anterior=anterior)
    return grupo, erros


def _salvar_grupo(formulario, grupos, anterior):
    peers = _peers()
    grupo, erros = _grupo_do_pedido(formulario, grupos, peers, anterior)
    if erros:
        return _falha(422, erros)
    if anterior is None:
        grupos.append(grupo)
    else:
        grupos[grupos.index(anterior)] = grupo
        if anterior.nome != grupo.nome:
            anterior.arquivo().unlink(missing_ok=True)
    peers_mod.gravar_grupos(grupos, _yaml())
    destino = render.escrever_grupo(grupo, rede=_rede())
    return GrupoSalvo(registro=_registro_grupo(grupo, peers), arquivo=destino.name)


@roteador.get("/grupos", response_model=list[GrupoResumo])
def listar_grupos():
    peers = _peers()
    return [GrupoResumo(id=g.id, nome=g.nome, tipo=g.tipo,
                        membros=len(_membros(g, peers)))
            for g in _grupos()]


# /grupos/novo antes de /grupos/{ident}, pelo mesmo motivo do peer
@roteador.get("/grupos/novo", response_model=GrupoRegistro)
def novo_grupo(tipo: str = "parceiro"):
    peers = _peers()
    return _registro_grupo(form.grupo_em_branco(tipo, peers, _grupos()), peers)


@roteador.get("/grupos/{ident}", response_model=GrupoRegistro)
def ler_grupo(ident: int):
    grupo = peers_mod.achar_grupo_id(_grupos(), ident)
    if grupo is None:
        return _nao_encontrado("grupo")
    return _registro_grupo(grupo, _peers())


@roteador.get("/grupos/{ident}/copia", response_model=GrupoRegistro)
def copiar_grupo(ident: int):
    """O grupo inteiro com o proximo ID livre. O nome repetido e o que o
    salvar recusa. A copia nasce sem membro: os peers seguem no original."""
    peers, grupos = _peers(), _grupos()
    grupo = peers_mod.achar_grupo_id(grupos, ident)
    if grupo is None:
        return _nao_encontrado("grupo")
    copia = replace(grupo, id=peers_mod.proximo_id(peers, grupos))
    return _registro_grupo(copia, peers)


@roteador.post("/grupos", response_model=GrupoSalvo, status_code=201)
def criar_grupo(formulario: GrupoForm):
    return _salvar_grupo(formulario, _grupos(), None)


@roteador.put("/grupos/{ident}", response_model=GrupoSalvo)
def atualizar_grupo(ident: int, formulario: GrupoForm):
    grupos = _grupos()
    anterior = peers_mod.achar_grupo_id(grupos, ident)
    if anterior is None:
        return _nao_encontrado("grupo")
    return _salvar_grupo(formulario, grupos, anterior)


@roteador.delete("/grupos/{ident}", status_code=204,
                 responses={409: {"model": ErroResposta}})
def excluir_grupo(ident: int):
    grupos = _grupos()
    grupo = peers_mod.achar_grupo_id(grupos, ident)
    if grupo is None:
        return _nao_encontrado("grupo")
    membros = [m.token for m in _membros(grupo, _peers())]
    if membros:
        # o membro sem filtro proprio herda a politica do grupo: apagar o
        # grupo por baixo dele deixa a saida dele estourando, e por isso a
        # recusa vem antes de a lista ser gravada
        return _falha(409, [validate.Erro(
            "membros", "o grupo ainda tem peers membros: %s. Tire-os do grupo "
                       "antes de excluir." % ", ".join(membros))])
    grupo.arquivo().unlink(missing_ok=True)
    grupos.remove(grupo)
    peers_mod.gravar_grupos(grupos, _yaml())
    return Response(status_code=204)


def _criar_lista_do_grupo(grupo, rede):
    # so o grupo de upstream tem o quadro: ver plan.quadro_ao_criar
    if not plan.quadro_ao_criar(grupo, de_grupo=True):
        return None
    return render.render_criar_lista(grupo=grupo, rede=rede)


@roteador.post("/grupos/previa", response_model=Previa)
def previa_grupo(formulario: GrupoForm,
                 ident: int | None = Query(default=None, alias="id")):
    """A previa do grupo, com o mesmo contrato da do peer."""
    grupos, peers, rede = _grupos(), _peers(), _rede()
    anterior = peers_mod.achar_grupo_id(grupos, ident) if ident is not None else None
    grupo, erros = _grupo_do_pedido(formulario, grupos, peers, anterior)
    salvo = _ler(anterior.arquivo()) if anterior is not None else None
    if erros:
        return Previa(erros=validate.erros_para_dict(erros), salvo=salvo)
    return Previa(bloco=render.render_grupo(grupo, rede=rede),
                  criar_lista=_criar_lista_do_grupo(grupo, rede),
                  arquivo=grupo.arquivo().name, salvo=salvo)


@roteador.get("/grupos/{ident}/saida", response_model=Saida)
def saida_grupo(ident: int):
    grupo = peers_mod.achar_grupo_id(_grupos(), ident)
    if grupo is None:
        return _nao_encontrado("grupo")
    rede = _rede()
    # o grupo nao tem bloco de remocao: o Saida sai com o remover nulo
    return Saida(bloco=render.render_grupo(grupo, rede=rede),
                 criar_lista=_criar_lista_do_grupo(grupo, rede),
                 arquivo=grupo.arquivo().name)


def _blocos_do_pedido(pedido):
    return form._blocos_do_formulario({"blocos_v4": pedido.v4,
                                       "blocos_v6": pedido.v6})


def _originacao(blocos, rede):
    # so os prefixos em servico vao para a configuracao
    ativos = form._ativos(blocos)
    if not any(ativos.get(f) for f in plan.FAMILIAS):
        return None
    return render.render_blocos(ativos, rede)


def _resposta_blocos(blocos, rede):
    """O texto dos editores e os dois blocos que o /api/blocos devolve.

    A remocao cobre o cadastro inteiro, e nao so o que esta em servico: o
    prefixo que acabou de sair do ar e o que mais provavelmente ainda esta
    configurado no equipamento.
    """
    tem_algum = any(blocos.get(f) for f in plan.FAMILIAS)
    return Blocos(
        texto=BlocosTexto(**form._texto_blocos(blocos)),
        originacao=_originacao(blocos, rede),
        remover=render.render_remove_blocos(blocos, rede) if tem_algum else None)


@roteador.get("/blocos", response_model=Blocos)
def ler_blocos():
    return _resposta_blocos(peers_mod.carregar_blocos(_yaml()), _rede())


@roteador.put("/blocos", response_model=Blocos)
def salvar_blocos(pedido: BlocosTexto):
    rede = _rede()
    blocos = _blocos_do_pedido(pedido)
    erros = validate.validar_blocos(blocos, rede)
    if erros:
        return _falha(422, erros)
    peers_mod.gravar_blocos(blocos, _yaml())
    # o arquivo de onde o operador cola, com os ativos
    render.escrever_blocos(form._ativos(blocos), rede)
    return _resposta_blocos(blocos, rede)


@roteador.post("/blocos/previa", response_model=Previa)
def previa_blocos(pedido: BlocosTexto):
    """O bloco de originacao que o salvar escreveria, sem gravar nada."""
    rede = _rede()
    blocos = _blocos_do_pedido(pedido)
    # o OUT e lido na hora, como o PEERS_YAML: os testes o trocam
    salvo = _ler(render.OUT / "blocos.txt")
    erros = validate.validar_blocos(blocos, rede)
    if erros:
        return Previa(erros=validate.erros_para_dict(erros), salvo=salvo)
    return Previa(bloco=_originacao(blocos, rede), arquivo="blocos.txt",
                  salvo=salvo)


@roteador.post("/blocos/irr", response_model=BlocosTexto,
               responses={502: {"model": ErroResposta}})
def consultar_blocos(pedido: BlocosIrrPedido):
    """Consulta o IRR do AS da rede e mescla com o texto recebido.

    A base da mesclagem e o texto que veio, e nao o arquivo: o operador pode
    ter mexido numa linha antes de consultar. O prefixo torto e recusado antes
    da consulta, nomeado no campo dele. Nada e gravado.
    """
    rede = _rede()
    blocos = _blocos_do_pedido(pedido)
    erros = validate.validar_blocos(blocos, rede)
    if erros:
        return _falha(422, erros)
    try:
        consulta = prefixes.coletar(rede.asn, rede.ASN, forcar=pedido.forcar,
                                    etiqueta="ORIGEM")
    except (OSError, RuntimeError, ValueError) as exc:
        return _falha(502, [validate.Erro("bgpq4", str(exc))])
    ausentes = []
    for fam in plan.FAMILIAS:
        blocos[fam], faltou = peers_mod.mesclar_blocos(
            blocos[fam], consulta.get(fam) or [])
        ausentes.extend(faltou)
    return BlocosTexto(**form._texto_blocos(blocos, ausentes))


def _nome_do_peer(peer):
    return peer.apelido or peer.nome or peer.token


def _secao_base(rede):
    # sem arquivo e sem `salvo`: o base e montado a cada requisicao, como no
    # /base.txt, e nunca teve uma versao em out/ para comparar
    return SecaoConfig(chave="base", titulo="Bloco base",
                       texto=render.render_base(rede=rede))


def _secao_originacao(blocos, rede):
    # sem prefixo proprio em servico nao ha bloco, e a secao vazia so faria
    # volume numa pagina que ja e longa
    texto = _originacao(blocos, rede)
    if texto is None:
        return None
    arquivo = render.OUT / "blocos.txt"
    return SecaoConfig(chave="originacao",
                       titulo="Originacao dos prefixos proprios",
                       texto=texto, arquivo=arquivo.name,
                       salvo=arquivo.exists())


def _secao_grupo(grupo, rede):
    destino = grupo.arquivo()
    return SecaoConfig(chave="grupo-%s" % grupo.id,
                       titulo="%s (%s)" % (grupo.nome, grupo.tipo),
                       texto=render.render_grupo(grupo, rede=rede),
                       arquivo=destino.name, salvo=destino.exists())


def _secao_peer(peer, grupo, rede):
    """O bloco do peer mais o quadro "ao criar", na ordem das abas da tela.

    O texto e a juncao dos dois porque quem cola no equipamento cola a secao
    inteira; o quadro so existe nos tipos com APPLY-PEER, e e o proprio
    _criar_lista_do_peer que decide isso.
    """
    partes = [render.render_peer(peer, grupo=grupo, rede=rede)]
    criar = _criar_lista_do_peer(peer, rede)
    if criar is not None:
        partes.append(criar)
    destino = peer.arquivo()
    return SecaoConfig(chave="peer-%s" % peer.id,
                       titulo="%s (%s, AS%s)" % (_nome_do_peer(peer), peer.tipo,
                                                 peer.asn),
                       texto="\n\n".join(partes),
                       arquivo=destino.name, salvo=destino.exists())


@roteador.get("/config", response_model=Config)
def ler_config():
    """A config inteira numa resposta so, montada na hora pelo render.

    Quem cola no equipamento le daqui: e a mesma saida das telas de cada
    registro, na ordem em que os blocos se apoiam, e sem nada gravado em
    out/ no caminho.
    """
    peers, grupos, rede = _peers(), _grupos(), _rede()
    # a ordem e a do "Ordem de colagem no F1A" do README: o base primeiro, o
    # grupo antes dos membros que herdam dele, e os prefixos proprios por
    # ultimo, que nao dependem de nem sustentam bloco nenhum
    secoes = [_secao_base(rede)]
    secoes.extend(_secao_grupo(grupo, rede) for grupo in grupos)
    for peer in peers:
        grupo = _grupo_do_peer(peer, grupos)
        if peer.grupo_id is not None and grupo is None:
            # o membro herda do grupo; sem ele o bloco sai errado, e a tela
            # do peer ja recusa por isso. Aqui a recusa e da config inteira,
            # nomeando quem aponta para o vazio
            return _falha(422, [validate.Erro(
                "grupo_id", "o grupo %s do peer %s nao existe"
                            % (peer.grupo_id, _nome_do_peer(peer)))])
        secoes.append(_secao_peer(peer, grupo, rede))
    originacao = _secao_originacao(peers_mod.carregar_blocos(_yaml()), rede)
    if originacao is not None:
        secoes.append(originacao)
    return Config(secoes=secoes)


@publico.post("/login", response_model=SessaoResposta)
def entrar(pedido: LoginPedido, resposta: Response):
    """Confere a senha e abre a sessao no cookie.

    Usuario errado e senha errada devolvem a mesma mensagem de proposito:
    quem tenta adivinhar nao descobre qual dos dois acertou.
    """
    if not auth.conferir(pedido.usuario, pedido.senha):
        return _falha(401, [validate.Erro("_", "usuario ou senha invalidos")])
    auth.abrir_sessao(resposta, pedido.usuario)
    return SessaoResposta(logado=True, usuario=pedido.usuario)


@publico.post("/logout", response_model=SessaoResposta)
def sair(resposta: Response):
    """Apaga o cookie. Sem estado no servidor, nao ha mais o que apagar."""
    auth.fechar_sessao(resposta)
    return SessaoResposta(logado=False, usuario=None)


@publico.get("/sessao", response_model=SessaoResposta)
def ler_sessao(request: Request):
    """Quem esta logado agora, sem exigir cookie.

    E o que a SPA pergunta ao abrir a pagina: um 401 aqui obrigaria a
    tela a adivinhar pelo erro de outra consulta.
    """
    usuario = auth.da_requisicao(request)
    return SessaoResposta(logado=usuario is not None, usuario=usuario)


async def _pedido_invalido(request: Request, exc: RequestValidationError):
    """Corpo, caminho ou query fora do modelo, no formato das outras recusas.

    O erro nao e de um campo do formulario, e por isso vai na chave _corpo.
    Fora de /api a resposta continua a padrao do FastAPI.
    """
    if not request.url.path.startswith("/api/"):
        return await request_validation_exception_handler(request, exc)
    partes = ["%s: %s" % (".".join(str(p) for p in e["loc"]), e["msg"])
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={
        "erros": {"_corpo": "; ".join(partes)}, "avisos": []})


async def _falha_inesperada(request: Request, exc: Exception):
    """Excecao sem tratamento: em /api vira JSON com a mensagem.

    O caso real e o peers.yaml editado a mao que o carregar recusa (ASN de 32
    bits sem namespace, prefixo torto nos blocos). A mensagem nomeia o arquivo
    e a chave, e a tela nova a mostra num toast, em vez de um traceback.
    """
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=500, content={
            "erros": {"_": str(exc)}, "avisos": []})
    return PlainTextResponse("Internal Server Error", status_code=500)


async def _sem_sessao(request: Request, exc: auth.NaoAutenticado):
    """O 401 das rotas protegidas, no formato das outras recusas.

    Um HTTPException daria {"detail": ...}, que e o formato que a SPA leria
    como resposta fora do modelo.
    """
    return _falha(401, [validate.Erro("_", str(exc))])


def instalar(app: FastAPI):
    """Monta as rotas /api e os tres tratadores de erro no app."""
    app.include_router(publico)
    app.include_router(roteador)
    app.add_exception_handler(RequestValidationError, _pedido_invalido)
    app.add_exception_handler(auth.NaoAutenticado, _sem_sessao)
    app.add_exception_handler(Exception, _falha_inesperada)
