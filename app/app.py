"""Rotas do app.

O uvicorn e o unico processo: ele serve a API em /api, o bloco base em
/base.txt, os arquivos do build do front em /assets e o index.html da SPA nas
rotas dela. A raiz leva para a SPA. Sem banco: o estado e o peers.yaml.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import (FileResponse, HTMLResponse, PlainTextResponse,
                               RedirectResponse)

from app import api, auth, render, tenants
from app import peers as peers_mod

RAIZ = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def ciclo(app: FastAPI):
    """O que roda uma vez por processo, antes da primeira requisicao.

    Hoje e o bootstrap do admin e a migracao do peers.yaml para a pasta
    dos tenants, nesta ordem: o login primeiro, para um erro na migracao
    nao deixar o app inalcancavel.

    A migracao nao pode derrubar o boot: um yaml torto (ASN de 32 bits sem
    namespace) deixaria o app num laco de restart do docker, quando o que
    ele tem a fazer e subir vazio e dizer no log o que houve.
    """
    auth.bootstrap()
    try:
        migrado = tenants.migrar()
    except Exception as exc:
        # Qualquer coisa: o arquivo e editavel a mao, e um yaml torto de
        # sintaxe nao e ValueError nem OSError - o safe_load estoura um
        # ParserError, e uma raiz que nao e um mapa estoura AttributeError
        # no .get do carregar_asn. Deixar qualquer um dos dois subir daqui
        # poe o app num laco de restart do docker por causa de uma virgula
        # no cadastro, que e exatamente o que a migracao tolerante existe
        # para evitar.
        print("bgpgen: a migracao do peers.yaml parou: %s" % exc, flush=True)
    else:
        if migrado is not None:
            print("bgpgen: peers.yaml virou %s (copia em peers.yaml.bak)"
                  % migrado, flush=True)
    yield


# docs_url, openapi_url e redoc_url desligados: as duas rotas do docs voltam
# logo abaixo, atras do login. O app.openapi() continua valendo dentro do
# processo, que e de onde o npm run api:tipos o le.
app = FastAPI(title="bgpgen", lifespan=ciclo,
              docs_url=None, openapi_url=None, redoc_url=None)

# a API JSON em /api, que a SPA consome
api.instalar(app)


@app.get("/openapi.json", include_in_schema=False,
         dependencies=[Depends(auth.exigir_login)])
def schema_do_app():
    return app.openapi()


@app.get("/docs", include_in_schema=False,
         dependencies=[Depends(auth.exigir_login)])
def docs_do_app():
    """O Swagger, que so carrega o schema com o cookie no navegador."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="bgpgen")


def rede():
    """O plan.Rede do AS declarado no topo do peers.yaml.

    Sai do arquivo a cada requisicao, como as outras leituras: o operador grava
    o AS no topo e recarrega, sem reiniciar o app. Sem a chave no arquivo o
    Rede e o de fabrica, e a config gerada e a de sempre.

    Le o PEERS_YAML do peers.py, e nao uma copia daqui: era a copia que os
    testes trocavam por monkeypatch, e com uma fonte so o modulo do app nao
    tem mais estado de arquivo nenhum.
    """
    return peers_mod.carregar_asn(peers_mod.PEERS_YAML)


@app.get("/base.txt", response_class=HTMLResponse,
         dependencies=[Depends(auth.exigir_login)])
def baixar_base():
    # texto puro, e nao HTML: e o mesmo corpo de antes do corte, montado na
    # hora do download (nao ha arquivo em out/ com uma versao antiga dele)
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


@app.get("/favicon.svg", include_in_schema=False)
def favicon_do_build():
    """O icone do build, que o Vite deixa na raiz do dist e nao em /assets.

    O index.html gerado linka /favicon.svg, entao sem esta rota o navegador
    pede um arquivo que ninguem serve, mesmo com o build inteiro no lugar. E
    um arquivo so, e nao um curinga da raiz do build.
    """
    alvo = _dir_web() / "favicon.svg"
    if not alvo.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(alvo)


@app.get("/")
def raiz():
    """A raiz leva para a lista da SPA.

    O 307 e temporario de proposito: um 308 ficaria no cache do navegador do
    operador, e voltar atras viraria limpeza de cache. Quem segue o redirect
    sem pensar e o HEALTHCHECK do Dockerfile, que bate em / desde antes deste
    corte e continua lendo 200 no fim da corrente (o /peers servido pelo build).
    """
    return RedirectResponse("/peers", status_code=307)


# As rotas da SPA.
#
# O /login entra na lista: o servidor e quem responde o index.html de um F5
# na tela de login, e sem a linha o recarregamento da 404 antes de o React
# existir.
#
# Fora do openapi(): elas devolvem o index.html, nao JSON, e nao acrescentam
# nada ao contrato que o front consome. Como o web/src/api/schema.d.ts e
# gerado do app.openapi(), deixa-las dentro mexeria no schema por uma rota que
# nao e da API - o test_tipos_api.py pega isso na hora.
for _rota in ("/peers", "/grupos", "/prefixos", "/base", "/config-completa",
              "/configuracoes", "/login"):
    app.add_api_route(_rota, pagina_spa, methods=["GET"],
                      include_in_schema=False)
for _rota in ("/peers", "/grupos"):
    app.add_api_route(_rota + "/{caminho:path}", pagina_spa, methods=["GET"],
                      include_in_schema=False)
