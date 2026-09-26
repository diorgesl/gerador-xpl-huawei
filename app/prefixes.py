"""bgpq4 mais o cache em disco.

O bgpq4 e o ponto de partida, nao a palavra final: a lista sempre pode
ser editada no formulario depois da consulta. Por isso o cache guarda o
que o bgpq4 devolveu, e nao o que o usuario digitou.
"""

import ipaddress
import json
import subprocess
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "out" / ".cache"
TTL_HORAS = 24
SERVIDOR_IRR = "whois.radb.net"
# sobe quando mudar o que a consulta devolve. Um cache gravado sob a
# versao anterior guarda a lista com outra forma, e serve-la depois da
# mudanca faria a consulta nova parecer que nao pegou.
CACHE_VERSAO = 2


def _comando(asn, token, fam, etiqueta=None):
    """Monta a consulta.

    -F '%n/%l ' devolve CIDR puro, tudo numa linha separado por espaco.

    -A agrega, e o que ele agrega e irmao de mesmo tamanho virando pai: o
    agregado cobre exatamente o que o IRR tem, nunca buraco. Em AS3333 os
    /23 de 193.0.20.0 e 193.0.22.0 saem como 193.0.20.0/22, e os de 10.0
    e 12.0 continuam separados, porque o /22 entre eles nao esta
    registrado. Quem cobre buraco e o -R/-r, que marca um prefixo
    existente como faixa sem conferir se os mais especificos existem
    (sx_radix_node_refine, no sx_prefix.c do bgpq4 1.12).

    O -A repete uma entrada quando o agregado tambem e objeto registrado:
    o /32 v6 do AS264130 veio duas vezes. O _normalizar tira a repeticao.

    O rotulo do -l e so um nome para o objeto que o bgpq4 descreve, e com
    -F '%n/%l ' ele nem aparece na saida. A etiqueta existe para o bloco
    proprio nao sair chamado de PL-CUST; o cache nao a distingue, porque a
    resposta e a mesma.
    """
    rotulo = "%s-%s" % (etiqueta or ("PL-CUST-%s" % token), fam.upper())
    return ["bgpq4", "-4" if fam == "v4" else "-6", "-A", "-F", "%n/%l ",
            "-h", SERVIDOR_IRR, "-l", rotulo, "AS%d" % asn]


def _rodar(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError("bgpq4 nao esta no PATH: e dependencia de execucao")
    if proc.returncode != 0:
        raise RuntimeError("bgpq4 falhou: %s" % (proc.stderr.strip() or proc.returncode))
    return [l.strip() for l in proc.stdout.splitlines() if l.strip()]


def _caminho(asn):
    return CACHE / ("%d.json" % asn)


def _dados_do_cache(asn):
    """O cache gravado sob a versao atual, se houver.

    O vencido nao e problema aqui: quem confere o prazo e o do_cache, e a
    idade_horas precisa enxergar a entrada velha para poder contar ha
    quantas horas ela foi coletada. Sem versao nenhuma e o mesmo que nao
    haver cache.
    """
    caminho = _caminho(asn)
    if not caminho.exists():
        return None
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if dados.get("versao") != CACHE_VERSAO:
        return None
    return dados


def do_cache(asn):
    """O conteudo do cache, se ele existir e nao estiver vencido."""
    dados = _dados_do_cache(asn)
    if dados is None:
        return None
    if time.time() - dados.get("coletado_em", 0) > TTL_HORAS * 3600:
        return None
    return dados.get("prefixos")


def idade_horas(asn):
    dados = _dados_do_cache(asn)
    if dados is None:
        return None
    return (time.time() - dados.get("coletado_em", 0)) / 3600.0


def _normalizar(bruto):
    """O bgpq4 devolve CIDR; o formulario trabalha em CIDR tambem.

    Com -F '%n/%l ' a saida vem numa linha so, com os prefixos separados
    por espaco, entao a quebra e por espaco em branco. Newline continua
    servindo pela mesma regra, e a virgula entra como separador pelo
    mesmo motivo.
    """
    saida = []
    for linha in bruto:
        for pedaco in linha.replace(",", " ").split():
            ipaddress.ip_network(pedaco, strict=False)
            if pedaco not in saida:
                saida.append(pedaco)
    return saida


def coletar(asn, token, familias=("v4", "v6"), forcar=False, etiqueta=None):
    if not forcar:
        em_cache = do_cache(asn)
        if em_cache is not None:
            return em_cache

    prefixos = {}
    for fam in familias:
        prefixos[fam] = _normalizar(_rodar(_comando(asn, token, fam,
                                                    etiqueta=etiqueta)))

    CACHE.mkdir(parents=True, exist_ok=True)
    _caminho(asn).write_text(
        json.dumps({"asn": asn, "versao": CACHE_VERSAO,
                    "coletado_em": time.time(), "prefixos": prefixos},
                   indent=2),
        encoding="utf-8")
    return prefixos
