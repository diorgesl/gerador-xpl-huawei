"""Rotas do app.

Tela unica: a lista de peers a esquerda, o formulario a direita, e a
saida abaixo depois de salvar. Sem banco: o estado e o peers.yaml.
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (FileResponse, HTMLResponse, PlainTextResponse,
                               RedirectResponse)
from fastapi.templating import Jinja2Templates

from app import api, plan, prefixes, render, validate
from app import peers as peers_mod
from app.peers import Peer, Grupo, Bloco

# Os helpers de formulario moram no app/formulario.py, que a API tambem usa.
# Ficam reexportados aqui porque as rotas HTML os chamam pelo nome e o
# test_app.py os le por app.app, ate o corte das telas HTML.
from app.formulario import (  # noqa: F401
    CAMPOS_INT, CAMPOS_INT_GRUPO, _anterior, _aprendizado_do_grupo,
    _aprendizado_padrao, _asn_do_formulario, _ativos, _blocos_do_formulario,
    _canoniza, _conferir_faixas, _id_do_formulario, _id_do_grupo_no_formulario,
    _linhas, _origem_padrao, _padroes, _sessoes, _texto, _texto_blocos,
    _usados, grupo_do_formulario, grupo_em_branco, peer_do_formulario, peer_em_branco,
)

RAIZ = Path(__file__).resolve().parent.parent
PEERS_YAML = peers_mod.PEERS_YAML
OUT = peers_mod.OUT

app = FastAPI(title="bgpgen")

# a API JSON em /api, que a SPA consome. As rotas HTML abaixo continuam ate
# o corte das telas (spec 2026-09-26-front-spa-design.md)
api.instalar(app)

templates = Jinja2Templates(directory=str(render.TEMPLATES))
templates.env.globals["plan"] = plan
templates.env.trim_blocks = True
templates.env.lstrip_blocks = True


def lista():
    return peers_mod.carregar(PEERS_YAML)


def lista_grupos():
    return peers_mod.carregar_grupos(PEERS_YAML)


def rede():
    """O plan.Rede do AS declarado no topo do peers.yaml.

    Sai do arquivo a cada requisicao, como as outras leituras: o operador
    grava o AS no topo e recarrega a pagina, sem reiniciar o app. Sem a
    chave no arquivo o Rede e o de fabrica, e a config gerada e a de sempre.

    Nome curto e de proposito: quem chama e quase todo mundo que renderiza
    ou valida, e o que se le na chamada e o `rede=rede()`.
    """
    return peers_mod.carregar_asn(PEERS_YAML)


def _contexto(request, peer=None, erros=None, avisos=None, criando=False,
              asn_form=None, blocos=None, blocos_ausentes=None):
    peers, grupos = lista(), lista_grupos()
    rede_atual = rede()
    blocos = blocos if blocos is not None else peers_mod.carregar_blocos(PEERS_YAML)
    ausentes = blocos_ausentes or {}
    tem_bloco = any(_ativos(blocos).get(fam) for fam in plan.FAMILIAS)
    tem_algum = any(blocos.get(fam) for fam in plan.FAMILIAS)
    # o render estoura no ip_network de um prefixo que nao analisa, e a tela
    # inteira cai antes de o operador ver a mensagem do validate. Com um
    # prefixo torto na lista, a saida simplesmente nao sai: o que a tela tem
    # que mostrar nesse estado e o erro, e nao o quadro de saida.
    try:
        saida_blocos = (render.render_blocos(_ativos(blocos), rede_atual)
                        if tem_bloco else None)
        # o remover cobre o cadastro inteiro, e nao so o que esta em
        # servico: o prefixo que o operador acabou de tirar do ar e o que
        # mais provavelmente ainda esta configurado no equipamento, e sem
        # esta linha ele nao teria como desfazer. O preco e um undo a mais
        # para quem tirou do ar um prefixo que nunca foi aplicado, e objeto
        # inexistente no paste e ruido visivel, nao falha silenciosa.
        saida_blocos_remover = (render.render_remove_blocos(blocos, rede_atual)
                                if tem_algum else None)
    except ValueError:
        saida_blocos = None
        saida_blocos_remover = None
    # A saida e uma previa do que seria gravado, e no caminho de erro nada
    # seria: o formulario do peer ja se comporta assim. Sem isto a tela
    # mostra o erro ao lado de um quadro que o operador pode copiar para o
    # equipamento, com um prefixo que o validate acabou de recusar.
    if erros:
        saida_blocos = None
        saida_blocos_remover = None
    return {
        "request": request,
        "peers": peers,
        "grupos": grupos,
        # o `plan` do contexto e o Rede do arquivo e nao o modulo que o
        # Jinja2Templates registra no env: em Jinja2 a variavel de contexto
        # ganha do global, entao o cabecalho e o resto da pagina escrevem
        # plan.ASN e saem com o AS declarado
        "plan": rede_atual,
        "peer": peer,
        # o formulario so manda a identidade do registro quando edita: no
        # criar nao ha registro por baixo, e um id escondido ali apontaria
        # para o peer que por acaso ocupasse aquele id
        "criando": criando,
        "erros": validate.erros_para_dict(erros or []),
        # o cabecalho le daqui o que o operador digitou: so a recusa o
        # preenche, e sem ele os dois campos saem do Rede do arquivo
        "asn_form": asn_form,
        "avisos": avisos or [],
        "saida": None,
        "saida_remover": None,
        "tipos": plan.TIPOS,
        "LP_BASE": plan.LP_BASE,
        "ROUTE_LIMIT": plan.ROUTE_LIMIT,
        "ROUTE_LIMIT_EXEMPLO": plan.ROUTE_LIMIT_EXEMPLO,
        "TIMER_PADRAO": plan.TIMER_PADRAO,
        "CLASSES_CLIENTE": plan.CLASSES_CLIENTE,
        "ORIGEM_CLASSE": plan.ORIGEM_CLASSE,
        "ORIGEM_NOME": rede_atual.ORIGEM_NOME,
        "ORIGENS_POR_TIPO": plan.ORIGENS_POR_TIPO,
        "PADROES": _padroes(rede_atual),
        "PREPEND_MAX": plan.PREPEND_MAX,
        "PREPEND_IMPLEMENTADO": plan.PREPEND_IMPLEMENTADO,
        "POP_MIN": plan.POP_MIN,
        "POP_MAX": plan.POP_MAX,
        "POP_USADOS": _usados(peers, "pop"),
        "APRENDIZADO_MIN": plan.APRENDIZADO_MIN,
        "APRENDIZADO_MAX": plan.APRENDIZADO_MAX,
        "APRENDIZADO_USADOS": _usados(peers + grupos, "aprendizado"),
        "blocos": blocos,
        # a marca do ausente entra no proprio texto da textarea, e nao como
        # uma lista a parte: a tela nao tem onde mostrar duas coisas para o
        # mesmo prefixo, e o operador edita o texto.
        "texto_blocos": _texto_blocos(blocos, ausentes.get("v4", [])
                                      + ausentes.get("v6", [])),
        # a saida e barata de montar e so aparece quando ha bloco: um
        # `if` no template para economizar duas chamadas aqui seria o
        # tipo de economia que esconde o caso vazio.
        "saida_blocos": saida_blocos,
        "saida_blocos_remover": saida_blocos_remover,
    }


@app.get("/", response_class=HTMLResponse)
def raiz(request: Request):
    return templates.TemplateResponse(request, "pagina.html", _contexto(request))


@app.get("/peer/novo", response_class=HTMLResponse)
def novo(request: Request, tipo: str = "cliente"):
    # o formulario em branco ja vem com os defaults da tabela do plano
    peer = peer_em_branco(tipo, lista(), lista_grupos())
    return templates.TemplateResponse(request, "pagina.html",
                                      _contexto(request, peer=peer, criando=True))


@app.get("/peer/{token}", response_class=HTMLResponse)
def editar(request: Request, token: str):
    peer = peers_mod.achar(lista(), token)
    if peer is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "pagina.html",
                                      _contexto(request, peer=peer))


@app.post("/peer", response_class=HTMLResponse)
async def salvar(request: Request):
    dados = dict(await request.form())
    peers = lista()
    antigo = _anterior(peers, dados)
    grupos = peers_mod.carregar_grupos(PEERS_YAML)
    peer, erros = peer_do_formulario(dados, peers, antigo, grupos=grupos)

    # a propria entrada fica na lista: quem a dispensa e o validar, pelo
    # registro
    erros = erros + validate.validar(peer, peers, anterior=antigo,
                                     grupos=grupos)
    if erros:
        return templates.TemplateResponse(
            request, "pagina.html",
            _contexto(request, peer=peer, erros=erros,
                      avisos=validate.avisos(peer, peers, rede=rede())),
            status_code=200)

    if antigo is None:
        peers.append(peer)
    else:
        peers[peers.index(antigo)] = peer
        if antigo.arquivo() != peer.arquivo():
            # trocou o token ou o tipo: o bloco com o nome velho sai do
            # diretorio de onde o operador cola, senao fica um orfao que
            # ele pode colar por engano
            antigo.arquivo().unlink(missing_ok=True)

    peers_mod.gravar(peers, PEERS_YAML)
    grupo = (peers_mod.achar_grupo_id(peers_mod.carregar_grupos(PEERS_YAML), peer.grupo_id)
            if peer.grupo_id is not None else None)
    render.escrever_peer(peer, grupo=grupo, rede=rede())
    return RedirectResponse("/saida/%s" % peer.token, status_code=303)


@app.post("/peer/{token}/excluir", response_class=HTMLResponse)
async def excluir(request: Request, token: str):
    dados = dict(await request.form())
    peers = lista()
    peer = peers_mod.achar(peers, token)
    if peer is None:
        return RedirectResponse("/", status_code=303)
    if dados.get("confirmado") != "sim":
        return templates.TemplateResponse(
            request, "pagina.html",
            _contexto(request, peer=peer,
                      erros=[validate.Erro("confirmado",
                                           "confirme para excluir o peer")]),
            status_code=200)
    peer.arquivo().unlink(missing_ok=True)
    peers.remove(peer)
    peers_mod.gravar(peers, PEERS_YAML)
    return RedirectResponse("/", status_code=303)


@app.get("/saida/{token}", response_class=HTMLResponse)
def saida(request: Request, token: str):
    peer = peers_mod.achar(lista(), token)
    if peer is None:
        return RedirectResponse("/", status_code=303)
    grupo = (peers_mod.achar_grupo_id(peers_mod.carregar_grupos(PEERS_YAML), peer.grupo_id)
            if peer.grupo_id is not None else None)
    if peer.grupo_id is not None and grupo is None:
        # o peer aponta para um grupo que nao esta mais no yaml - arquivo
        # editado a mao, ou gravacao pela metade. Sem o grupo o membro perde
        # o que herdava: o que tem filtro proprio mas nao tem classe estoura
        # no render, e o que nao tem filtro nenhum sairia sem filtro e sem o
        # `group` do VRP, isto e, anunciando tudo. O erro e o mesmo que o
        # formulario daria, com o campo que o ancora no select.
        return templates.TemplateResponse(
            request, "pagina.html",
            _contexto(request, peer=peer,
                      erros=[validate.Erro("grupo_id", "grupo nao encontrado")]),
            status_code=200)
    contexto = _contexto(request, peer=peer)
    contexto["saida"] = render.render_peer(peer, grupo=grupo, rede=rede())
    contexto["saida_remover"] = render.render_remove(peer, grupo=grupo,
                                                    rede=rede())
    return templates.TemplateResponse(request, "pagina.html", contexto)


@app.get("/saida/{token}/criar-lista", response_class=HTMLResponse)
def criar_lista(request: Request, token: str):
    peer = peers_mod.achar(lista(), token)
    if peer is None:
        return RedirectResponse("/", status_code=303)
    if peer.tipo not in plan.TIPOS_COM_APPLY_PEER:
        # o par CL-PEER-<T> / APPLY-PEER-<T> e de cliente, parceiro e
        # upstream: para os outros dois tipos o quadro nao tem o que criar,
        # e o painel nem oferece o link
        return RedirectResponse("/saida/%s" % peer.token, status_code=303)
    contexto = _contexto(request, peer=peer)
    contexto["saida"] = render.render_criar_lista(peer, rede=rede())
    return templates.TemplateResponse(request, "pagina.html", contexto)


@app.get("/base.txt", response_class=HTMLResponse)
def baixar_base():
    return HTMLResponse(render.render_base(rede=rede()), media_type="text/plain")


# --- o build do front (SPA) -------------------------------------------
#
# Em producao ha um processo so: o uvicorn serve a API em /api, os arquivos do
# build em /assets e o index.html da SPA nas rotas dela. O diretorio do build
# vem de BGPGEN_WEB, e o padrao e web/dist na raiz do projeto.
#
# O caminho e lido a cada requisicao, e nao no import: os testes o trocam, como
# fazem com o PEERS_YAML.

SEM_BUILD = ("front nao compilado: rode `npm run build` em `web/` "
             "ou use o Vite na 5173")


def _dir_web():
    return Path(os.environ.get("BGPGEN_WEB", str(RAIZ / "web" / "dist")))


def pagina_spa():
    """O index.html do build, ou o 503 que explica como compila-lo."""
    index = _dir_web() / "index.html"
    if not index.is_file():
        return PlainTextResponse(SEM_BUILD, status_code=503)
    return FileResponse(index)


@app.get("/assets/{caminho:path}", include_in_schema=False)
def assets_do_build(caminho: str):
    raiz = _dir_web() / "assets"
    # o caminho resolvido tem que continuar dentro do diretorio: sem isto um
    # /assets/../../peers.yaml levaria o cadastro embora
    alvo = (raiz / caminho).resolve()
    if not alvo.is_file() or raiz.resolve() not in alvo.parents:
        raise HTTPException(status_code=404)
    return FileResponse(alvo)


# As rotas da SPA. Os nomes estao no plural de proposito: nenhum deles colide
# com as rotas HTML, que sao /peer/... e /grupo/... no singular.
#
# Fora do openapi(): elas devolvem o index.html, nao JSON, e nao acrescentam
# nada ao contrato que o front consome. Como o web/src/api/schema.d.ts e
# gerado do app.openapi(), deixa-las dentro mexeria no schema por uma rota que
# nao e da API - o test_tipos_api.py pega isso na hora.
for _rota in ("/peers", "/grupos", "/prefixos", "/base", "/configuracoes"):
    app.add_api_route(_rota, pagina_spa, methods=["GET"],
                      include_in_schema=False)
for _rota in ("/peers", "/grupos"):
    app.add_api_route(_rota + "/{caminho:path}", pagina_spa, methods=["GET"],
                      include_in_schema=False)


@app.post("/asn", response_class=HTMLResponse)
async def salvar_asn(request: Request):
    """O AS da rede, gravado no topo do peers.yaml.

    Recusando, redesenha a propria pagina com o erro de campo, como o salvar
    do peer: o cabecalho continua onde estava, com o que o operador escreveu
    nele. Gravando, a pagina volta pelo 303 e o cabecalho ja sai com o AS
    novo, porque o _contexto le o Rede do arquivo a cada requisicao.

    O `asn_form` leva de volta os dois campos como foram digitados. Sem ele
    a tela devolvia o que esta gravado no arquivo, e um erro do namespace
    aparecia embaixo de um campo do AS que o operador nem tinha preenchido
    com aquilo: o valor do erro e o valor na tela tem que ser o mesmo.
    """
    dados = dict(await request.form())
    asn, politica, erros = _asn_do_formulario(dados)
    if not erros:
        try:
            # o gravar_asn monta o Rede antes de escrever, entao um ASN de 32
            # bits sem namespace nao chega a estragar o arquivo que estava bom
            peers_mod.gravar_asn(asn, politica, PEERS_YAML)
        except ValueError as exc:
            # as duas faixas ja foram conferidas acima, entao o que chega
            # aqui e o que escapou delas e a mensagem do plan e a que nomeia
            erros = [validate.Erro("asn_rede", str(exc))]
    if erros:
        return templates.TemplateResponse(
            request, "pagina.html",
            _contexto(request, erros=erros, asn_form={
                "asn": _texto(dados, "asn_rede"),
                "politica": _texto(dados, "asn_politica")}),
            status_code=200)
    return RedirectResponse("/", status_code=303)


@app.post("/bgpq4", response_class=HTMLResponse)
async def consultar_bgpq4(request: Request, forcar: int = 0):
    """Consulta o IRR e devolve a tela com os prefixos preenchidos.

    Redesenha a pagina inteira, como as outras rotas, em vez de
    devolver um fragmento: o operador ve o resultado no proprio
    formulario e ainda pode editar antes de salvar. O forcar vem pela
    query string, que e o que permite os dois botoes.
    """
    dados = dict(await request.form())
    peers = lista()
    antigo = _anterior(peers, dados)
    # o id sai da mesma faixa do grupo, e esta rota tambem redesenha o
    # formulario com o id alocado quando ele vem em branco
    peer, erros = peer_do_formulario(
        dados, peers, antigo, grupos=peers_mod.carregar_grupos(PEERS_YAML))
    if peer.asn <= 0:
        erros = erros + [validate.Erro("asn",
                                       "informe o ASN antes de consultar o IRR")]
    else:
        try:
            coleta = prefixes.coletar(peer.asn, peer.token, forcar=bool(forcar))
        except (RuntimeError, ValueError) as exc:
            erros = erros + [validate.Erro("bgpq4", str(exc))]
        else:
            for fam in plan.FAMILIAS:
                peer.prefixos[fam] = coleta.get(fam) or []
    return templates.TemplateResponse(
        request, "pagina.html",
        _contexto(request, peer=peer, erros=erros, criando=antigo is None))


@app.post("/blocos", response_class=HTMLResponse)
async def salvar_blocos(request: Request):
    dados = dict(await request.form())
    rede_atual = rede()
    blocos = _blocos_do_formulario(dados)
    erros = validate.validar_blocos(blocos, rede_atual)
    if erros:
        return templates.TemplateResponse(
            request, "pagina.html",
            _contexto(request, erros=erros, blocos=blocos))
    peers_mod.gravar_blocos(blocos, PEERS_YAML)
    # o mesmo caminho do bloco de peer: o POST grava o arquivo de onde o
    # operador cola, e so os ativos entram. Sem esta linha o `out/blocos.txt`
    # da ordem de colagem do README nunca existia, e a secao era o unico
    # artefato do gerador sem arquivo.
    render.escrever_blocos(_ativos(blocos), rede_atual)
    return templates.TemplateResponse(request, "pagina.html",
                                      _contexto(request, blocos=blocos))


@app.post("/blocos/bgpq4", response_class=HTMLResponse)
async def consultar_blocos(request: Request, forcar: int = 0):
    """Consulta o IRR no ASN da propria rede e redesenha a tela.

    A base da mesclagem e o que veio no formulario, e nao o que esta no
    arquivo: o operador pode ter mexido numa linha antes de consultar, e o
    POST que consulta nao grava nada. O ausente volta no fim da lista e
    marcado, e o que o operador fizer com ele e no salvar.
    """
    dados = dict(await request.form())
    rede_atual = rede()
    blocos = _blocos_do_formulario(dados)
    ausentes = {}
    # a rota nao grava, mas valida: o prefixo torto que veio no formulario
    # tem que sair nomeado no campo dele, e nao como uma tela sem o quadro
    # de saida que o operador nao tem como explicar
    erros = validate.validar_blocos(blocos, rede_atual)
    try:
        consulta = prefixes.coletar(rede_atual.asn, rede_atual.ASN,
                                    forcar=bool(forcar), etiqueta="ORIGEM")
    except (RuntimeError, ValueError) as exc:
        # a falha da consulta entra depois dos erros do campo, e o
        # erros_para_dict deixa o primeiro vencer: com o prefixo torto na
        # tela, o que o operador precisa ler e o campo, nao o bgpq4
        erros = erros + [validate.Erro("blocos_v4", str(exc)),
                         validate.Erro("blocos_v6", str(exc))]
    else:
        for fam in plan.FAMILIAS:
            blocos[fam], ausentes[fam] = peers_mod.mesclar_blocos(
                blocos[fam], consulta.get(fam) or [])
    return templates.TemplateResponse(
        request, "pagina.html",
        _contexto(request, erros=erros, blocos=blocos, blocos_ausentes=ausentes))


# Rotas de grupo BGP (VRP `group`), mesmo esquema das rotas de peer acima:
# /grupo/novo e /grupo/{nome} abrem o formulario, POST /grupo salva, o
# excluir exige confirmacao e a saida mostra o bloco renderizado.


def _contexto_grupo(request, grupo, criando, erros=None, membros=(), saida=None):
    """O contexto da tela do grupo, no lugar do _contexto do peer.

    A tela do grupo nao tem os campos do peer avulso, mas tem o mesmo menu:
    a lista de grupos que ja existem, com a contagem de membros de cada um.
    A contagem sai dos peers, e nao de um campo gravado, porque e ela que diz
    se o grupo ainda pode ser excluido - o excluir recusa enquanto houver
    membro."""
    peers, grupos = lista(), lista_grupos()
    rede_atual = rede()
    return {
        "request": request,
        "plan": rede_atual,
        "grupo": grupo,
        "criando": criando,
        "erros": erros or {},
        "grupos": grupos,
        "peers": peers,
        "membros": list(membros),
        "CLASSES_CLIENTE": plan.CLASSES_CLIENTE,
        # a tela do grupo nao tinha nem a tabela de tipos nem o blob que o
        # JS do peer ja le: sem os dois, o select de tipo e a lista de origem
        # ficavam presos ao que estivesse escrito na mao na pagina
        "TIPOS": plan.TIPOS,
        "PADROES": _padroes(rede_atual),
        # a mesma lista da tela do peer, e pelo mesmo motivo: o 3xxx e um
        # espaco so, entao o que ja foi cadastrado num peer tambem aparece
        # aqui, e o que ja foi cadastrado num grupo aparece la
        "APRENDIZADO_USADOS": _usados(peers + grupos, "aprendizado"),
        "saida": saida,
    }


@app.get("/grupo/novo", response_class=HTMLResponse)
def grupo_novo(request: Request, tipo: str = "parceiro"):
    # o formulario em branco ja vem com os defaults da tabela do plano, e o
    # tipo da query e o que o select da tela de peer usa para nascer certo
    grupo = grupo_em_branco(tipo, lista(), lista_grupos())
    return templates.TemplateResponse(
        request, "pagina_grupo.html",
        _contexto_grupo(request, grupo, criando=True))


@app.get("/grupo/{nome}", response_class=HTMLResponse)
def grupo_editar(request: Request, nome: str):
    grupo = peers_mod.achar_grupo(lista_grupos(), nome)
    if grupo is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "pagina_grupo.html",
        _contexto_grupo(request, grupo, criando=False))


@app.post("/grupo", response_class=HTMLResponse)
async def grupo_salvar(request: Request):
    dados = dict(await request.form())
    grupos = lista_grupos()
    ident = _id_do_grupo_no_formulario(dados)
    anterior = peers_mod.achar_grupo_id(grupos, ident) if ident is not None else None
    grupo, erros = grupo_do_formulario(dados, grupos, anterior, peers=lista())
    # os erros de campo vem na frente, como no salvar do peer: eles dizem que
    # o valor nem chegou ao Grupo, e o validar_grupo so ve o que sobrou
    erros = erros + validate.validar_grupo(grupo, grupos, lista(), anterior=anterior)
    if erros:
        return templates.TemplateResponse(
            request, "pagina_grupo.html",
            _contexto_grupo(request, grupo, criando=anterior is None,
                            erros=validate.erros_para_dict(erros)),
            status_code=200)

    if anterior is None:
        grupos.append(grupo)
    else:
        grupos[grupos.index(anterior)] = grupo
        if anterior.nome != grupo.nome:
            anterior.arquivo().unlink(missing_ok=True)

    peers_mod.gravar_grupos(grupos, PEERS_YAML)
    render.escrever_grupo(grupo, rede=rede())
    return RedirectResponse("/saida/grupo/%s" % grupo.nome, status_code=303)


@app.post("/grupo/{nome}/excluir", response_class=HTMLResponse)
async def grupo_excluir(request: Request, nome: str):
    dados = dict(await request.form())
    grupos = lista_grupos()
    grupo = peers_mod.achar_grupo(grupos, nome)
    if grupo is None:
        return RedirectResponse("/", status_code=303)
    membros = [p.token for p in lista() if p.grupo_id == grupo.id]
    if dados.get("confirmado") != "sim":
        return templates.TemplateResponse(
            request, "pagina_grupo.html",
            _contexto_grupo(request, grupo, criando=False, membros=membros,
                            erros={"confirmado": "confirme para excluir o grupo"}),
            status_code=200)
    if membros:
        # o membro nao tem politica propria - a validacao a dispensou
        # justamente porque ela vinha do grupo -, entao apagar o grupo por
        # baixo dele nao o devolve ao estado avulso: a saida dele passa a
        # estourar. Enquanto nao houver como avisar que ele precisa voltar a
        # ter politica propria, a exclusao para aqui.
        return templates.TemplateResponse(
            request, "pagina_grupo.html",
            _contexto_grupo(
                request, grupo, criando=False, membros=membros,
                erros={"membros": "o grupo ainda tem peers membros: %s. "
                                  "Tire-os do grupo antes de excluir."
                                  % ", ".join(membros)}),
            status_code=200)
    grupo.arquivo().unlink(missing_ok=True)
    grupos.remove(grupo)
    peers_mod.gravar_grupos(grupos, PEERS_YAML)
    return RedirectResponse("/", status_code=303)


@app.get("/saida/grupo/{nome}", response_class=HTMLResponse)
def grupo_saida(request: Request, nome: str):
    grupo = peers_mod.achar_grupo(lista_grupos(), nome)
    if grupo is None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "pagina_grupo.html",
        _contexto_grupo(request, grupo, criando=False,
                        saida=render.render_grupo(grupo, rede=rede())))


@app.get("/saida/grupo/{nome}/criar-lista", response_class=HTMLResponse)
def grupo_criar_lista(request: Request, nome: str):
    grupo = peers_mod.achar_grupo(lista_grupos(), nome)
    if grupo is None:
        return RedirectResponse("/", status_code=303)
    if not plan.quadro_ao_criar(grupo, de_grupo=True):
        # so o grupo de upstream tem o quadro: quem define o APPLY-PEER-<G> e
        # ele proprio, e so o export do upstream chama esse filtro. Nos
        # outros quatro o quadro nao tem o que criar e a tela nem oferece o
        # link - ver plan.quadro_ao_criar.
        return RedirectResponse("/saida/grupo/%s" % grupo.nome, status_code=303)
    contexto = _contexto_grupo(request, grupo, criando=False)
    contexto["saida"] = render.render_criar_lista(grupo=grupo, rede=rede())
    return templates.TemplateResponse(request, "pagina_grupo.html", contexto)
