"""Jinja2 sobre os templates. Um template de bloco base e um por tipo.

A excecao e o parceiro, que sai do mesmo arquivo do cliente: ver a tabela
logo abaixo do cabecalho do modulo.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app import plan

RAIZ = Path(__file__).resolve().parent.parent
TEMPLATES = RAIZ / "templates"

CABECALHO_BASE = ("bloco base: sets e filtros compartilhados. "
                  "Cole antes do bloco de qualquer peer.")


def ambiente(rede=None, blocos=None):
    """O ambiente Jinja com o plano injetado.

    O `plan` que o template ve e um plan.Rede e nao o modulo, mas o
    template nao sabe disso: ele segue escrevendo plan.c5ppa e plan.TIPOS,
    e o namespace que sai e o do AS declarado no peers.yaml. Sem argumento
    o Rede e o de fabrica, e a config gerada e a de antes.

    Os `blocos` (os prefixos proprios do tenant) entram pelo mesmo caminho,
    porque o filtro que recusa o proprio prefixo vindo de fora mora no base
    e precisa da lista. Sem eles o filtro sai sem condicao nenhuma, que e o
    caso dos testes de render e do tenant sem bloco cadastrado.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,  # nome errado de variavel falha no teste, nao na config
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["plan"] = rede if rede is not None else plan.Rede()
    env.globals["blocos"] = blocos or {}
    return env


def render_base(rede=None, blocos=None):
    return ambiente(rede, blocos).get_template("base.txt.j2").render()


# o parceiro e um cliente que fica no roteador das CDNs, e nao tem arquivo
# proprio: o bloco dele e este, com a marca de 2091 que o plan.c_downstream
# poe no import. Dois arquivos com a mesma regra divergem na primeira
# mudanca, e o segundo a ser colado seria o que vale.
TEMPLATE_POR_TIPO = {"parceiro": "cliente.txt.j2"}


def render_peer(peer, grupo=None, rede=None, origem=None):
    """O bloco do peer. O `origem` so importa para quem reaproveita: e dela
    que sai o token que nomeia os filtros chamados no bloco."""
    nome = TEMPLATE_POR_TIPO.get(peer.tipo, "%s.txt.j2" % peer.tipo)
    return ambiente(rede).get_template(nome).render(
        peer=peer, grupo=grupo, origem=origem)


# o `saida` e so por palavra-chave e sem default: a chamada de antes desta
# etapa, `escrever_peer(peer, grupo=..., rede=...)`, tem que reprovar com
# TypeError ate alguem dizer de que tenant e o bloco, em vez de escrever na
# raiz do out/, que e o nome que a etapa dos tenants elimina
def escrever_peer(peer, grupo=None, rede=None, origem=None, *, saida):
    saida.mkdir(parents=True, exist_ok=True)
    destino = peer.arquivo(saida)
    destino.write_text(render_peer(peer, grupo=grupo, rede=rede,
                                   origem=origem),
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


def escrever_blocos(blocos, rede=None, *, saida):
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / "blocos.txt"
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


def escrever_grupo(grupo, rede=None, *, saida):
    saida.mkdir(parents=True, exist_ok=True)
    destino = grupo.arquivo(saida)
    destino.write_text(render_grupo(grupo, rede=rede), encoding="ascii")
    return destino
