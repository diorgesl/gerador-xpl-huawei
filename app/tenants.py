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
