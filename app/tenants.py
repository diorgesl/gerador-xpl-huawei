"""A pasta dos tenants: um arquivo por ASN da rede.

O nome do arquivo E o ASN, e ele e a verdade: a chave `asn:` que mora dentro
e copia de leitura, escrita para o arquivo se descrever sozinho quando
alguem o abre no editor ou o copia para fora, e nunca lida de volta. Guardar
o mesmo dado duas vezes foi o que aposentou o campo `token` dos peers.

A pasta e a lista: um arquivo cujo nome nao e so digito nao e um tenant
torto, e um arquivo que nao e do app, e por isso some da lista em silencio.

O `criar` e burro de proposito: quem confere a faixa do ASN e o formulario,
que sabe dizer em que campo o operador errou. Aqui so o par incoerente
estoura, pelo plan.Rede, e o arquivo nunca chega a nascer.
"""

import os
import shutil

from dataclasses import dataclass
from pathlib import Path

from app import peers as peers_mod

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "peers"
SAIDA = RAIZ / "out"
# o cadastro de antes desta etapa, e a copia que a migracao deixa para tras
ORIGEM = RAIZ / "peers.yaml"
BKP = RAIZ / "peers.yaml.bak"


@dataclass(frozen=True)
class Tenant:
    asn: int
    caminho: Path
    saida: Path


def caminho(asn):
    return PASTA / ("%d.yaml" % asn)


def saida(asn):
    return SAIDA / str(asn)


def listar():
    """Os ASNs com arquivo na pasta, em ordem numerica.

    A ordem e numerica, e nao a do sistema de arquivos, para o seletor da
    tela nao depender da ordem em que o disco devolveu as entradas. O
    `isascii` junto do `isdigit` e o mesmo cuidado do formulario: digitos
    que nao sao ascii, como o sobrescrito, passam no isdigit e estouram no
    int().
    """
    if not PASTA.is_dir():
        return []
    asns = []
    for arquivo in PASTA.glob("*.yaml"):
        nome = arquivo.stem
        if nome.isascii() and nome.isdigit():
            asns.append(int(nome))
    return sorted(asns)


def existe(asn):
    return caminho(asn).is_file()


def abrir(asn):
    """O Tenant do ASN, ou None quando nao ha arquivo."""
    if not existe(asn):
        return None
    return Tenant(asn=asn, caminho=caminho(asn), saida=saida(asn))


def criar(asn, politica=None):
    """Grava o arquivo de um tenant novo e devolve o Tenant.

    O gravar_asn do peers.py ja escreve exatamente o que um tenant vazio
    precisa: a chave `asn`, o `asn_politica` quando declarado, e mais nada.
    Nao nascem `peers`, `grupos` nem `blocos`: a chave ausente e o estado de
    quem nunca usou a tela, como no gravar_blocos.

    O par incoerente estoura no plan.Rede, dentro do gravar_asn, antes de
    qualquer escrita: um ASN de 32 bits sem namespace nao tem como virar
    community standard, e um arquivo assim nasceria estourando na primeira
    leitura, sem a tela ter como conserta-lo.
    """
    if existe(asn):
        raise ValueError("o ASN %d ja tem cadastro" % asn)
    destino = caminho(asn)
    peers_mod.gravar_asn(asn, politica, destino)
    return Tenant(asn=asn, caminho=destino, saida=saida(asn))


def migrar():
    """O peers.yaml de antes desta etapa vira o tenant do AS dele.

    Roda uma vez, no boot. A copia para o .bak vem ANTES do move de
    proposito: e ela que faz o boot seguinte ser no-op, porque depois do
    move o ORIGEM nao existe mais. Ou os dois arquivos estao la (a
    migracao nao chegou a acontecer), ou so o .bak esta (terminou).

    O ASN sai do carregar_asn de sempre, que estoura com o mesmo ValueError
    de antes num arquivo que nao fecha. Quem chama decide o que fazer com
    ele: aqui nada e adivinhado e nenhum arquivo e tocado.

    Devolve o caminho do tenant migrado, ou None quando nao havia o que
    migrar ou quando o destino ja estava ocupado (que e o caso em que a
    linha no log diz qual dos dois arquivos ficou valendo).
    """
    if not ORIGEM.is_file():
        return None
    destino = caminho(peers_mod.carregar_asn(ORIGEM).asn)
    if destino.exists():
        # a pasta ja tem esse tenant: nao ha o que mover, e sobrescrever o
        # que esta la seria trocar um cadastro por outro em silencio.
        #
        # A linha e o unico rastro deste caminho: nao nasce .bak e nenhum dos
        # dois arquivos se move, entao sem ela o operador fica com o app de
        # pe, um ASN plausivel e o cadastro velho na tela, sem saber qual dos
        # dois mandou. E o caso que a spec abencoa, o de um arquivo copiado a
        # mao para a pasta enquanto o peers.yaml do mesmo ASN ainda existe
        print("bgpgen: %s nao migrou: %s ja existe (o original fica onde esta,"
              " e sem copia em %s)" % (ORIGEM, destino, BKP), flush=True)
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ORIGEM, BKP)
    os.replace(ORIGEM, destino)
    _mover_saida(destino.stem)
    return destino


def _mover_saida(asn):
    """Os blocos da raiz do out/ para a pasta do tenant.

    So os .txt da raiz entram: o .cache/ do bgpq4 e derivado do IRR e nao
    da rede, e continua onde esta, compartilhado. O que ja existe no destino
    fica: em duvida entre o arquivo que ja estava e o que chegou, o que ja
    estava e o que corresponde a uma pasta de tenant que alguem criou.
    """
    destino = saida(int(asn))
    destino.mkdir(parents=True, exist_ok=True)
    for arquivo in sorted(SAIDA.glob("*.txt")):
        alvo = destino / arquivo.name
        if alvo.exists():
            print("bgpgen: %s nao migrou: %s ja existe" % (arquivo, alvo),
                  flush=True)
            continue
        os.replace(arquivo, alvo)


class NaoEncontrado(Exception):
    """O ASN pedido nao tem arquivo na pasta.

    E o mesmo desenho do auth.NaoAutenticado: quem transforma em resposta e
    um handler registrado no instalar() do api.py, no formato das outras
    recusas. Um HTTPException daria {"detail": ...}, que a SPA le como
    resposta fora do modelo.
    """

    def __init__(self, asn):
        self.asn = asn
        super().__init__("ASN %s nao tem cadastro em peers/" % asn)
