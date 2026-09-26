"""Jinja2 sobre os templates. Um template de bloco base e um por tipo.

A excecao e o parceiro, que sai do mesmo arquivo do cliente: ver a tabela
logo abaixo do cabecalho do modulo.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app import plan

RAIZ = Path(__file__).resolve().parent.parent
TEMPLATES = RAIZ / "templates"
OUT = RAIZ / "out"

CABECALHO_BASE = ("bloco base: sets e filtros compartilhados. "
                  "Cole antes do bloco de qualquer peer.")


def ambiente(rede=None):
    """O ambiente Jinja com o plano injetado.

    O `plan` que o template ve e um plan.Rede e nao o modulo, mas o
    template nao sabe disso: ele segue escrevendo plan.c5ppa e plan.TIPOS,
    e o namespace que sai e o do AS declarado no peers.yaml. Sem argumento
    o Rede e o de fabrica, e a config gerada e a de antes.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,  # nome errado de variavel falha no teste, nao na config
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["plan"] = rede if rede is not None else plan.Rede()
    return env


def render_base(rede=None):
    return ambiente(rede).get_template("base.txt.j2").render()


# o parceiro e um cliente que fica no roteador das CDNs, e nao tem arquivo
# proprio: o bloco dele e este, com a marca de 2091 que o plan.c_downstream
# poe no import. Dois arquivos com a mesma regra divergem na primeira
# mudanca, e o segundo a ser colado seria o que vale.
TEMPLATE_POR_TIPO = {"parceiro": "cliente.txt.j2"}


def render_peer(peer, grupo=None, rede=None):
    nome = TEMPLATE_POR_TIPO.get(peer.tipo, "%s.txt.j2" % peer.tipo)
    return ambiente(rede).get_template(nome).render(peer=peer, grupo=grupo)


def escrever_peer(peer, grupo=None, rede=None):
    OUT.mkdir(parents=True, exist_ok=True)
    destino = peer.arquivo()
    destino.write_text(render_peer(peer, grupo=grupo, rede=rede),
                       encoding="ascii")
    return destino


def render_remove(peer, grupo=None, rede=None):
    return ambiente(rede).get_template("remover.txt.j2").render(
        peer=peer, grupo=grupo)


def render_blocos(blocos, rede=None):
    """O bloco dos prefixos proprios: estaticas, filtros e as linhas network.

    Um arquivo so com as duas partes, como os blocos de peer: o operador
    cola o que esta fora da view do bgp e o que esta dentro, na ordem em
    que aparecem.
    """
    return ambiente(rede).get_template("blocos.txt.j2").render(blocos=blocos)


def render_remove_blocos(blocos, rede=None):
    return ambiente(rede).get_template("remover_blocos.txt.j2").render(
        blocos=blocos)


def escrever_blocos(blocos, rede=None):
    OUT.mkdir(parents=True, exist_ok=True)
    destino = OUT / "blocos.txt"
    destino.write_text(render_blocos(blocos, rede=rede), encoding="ascii")
    return destino


def render_criar_lista(peer=None, grupo=None, rede=None):
    """O quadro 'ao criar': a CL-PEER-<T> vazia, colada uma vez so.

    Serve os tres donos possiveis de uma CL-PEER: o peer avulso ou o membro
    com filtro proprio, num tipo com APPLY-PEER (cliente, parceiro ou
    upstream), e o grupo de upstream. Em todos o bloco so chama o filtro,
    entao colar o bloco de novo nunca mexe no que o operador escreveu
    aqui."""
    return ambiente(rede).get_template("criar_lista.txt.j2").render(
        peer=peer, grupo=grupo)


TEMPLATE_POR_TIPO_GRUPO = {"parceiro": "grupo_cliente.txt.j2"}


def render_grupo(grupo, rede=None):
    nome = TEMPLATE_POR_TIPO_GRUPO.get(grupo.tipo, "grupo_%s.txt.j2" % grupo.tipo)
    return ambiente(rede).get_template(nome).render(grupo=grupo)


def escrever_grupo(grupo, rede=None):
    OUT.mkdir(parents=True, exist_ok=True)
    destino = grupo.arquivo()
    destino.write_text(render_grupo(grupo, rede=rede), encoding="ascii")
    return destino
