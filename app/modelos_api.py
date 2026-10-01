"""Modelos da API JSON.

O formulario do peer e o do grupo tem os nomes de campo do formulario HTML, e
os escalares sao texto, como o formulario manda: quem converte e o
peer_do_formulario (e o grupo_do_formulario), que devolve "valor numerico
invalido" no campo. Tipado como int aqui, o erro sairia do pydantic, com outra
mensagem e noutro formato.
"""

from pydantic import BaseModel, ConfigDict


class Modelo(BaseModel):
    # campo desconhecido e erro: um nome trocado no front sumiria em silencio,
    # e o valor que o operador digitou nao chegaria a lugar nenhum
    model_config = ConfigDict(extra="forbid")


class PeerForm(Modelo):
    id: str = ""
    apelido: str = ""
    nome: str = ""
    tipo: str = "cliente"
    grupo_id: str = ""
    politica_de: str = ""
    asn: str = ""
    descricao: str = ""
    classe: str = ""
    lp_base: str = ""
    origem: str = ""
    pop: str = ""
    aprendizado: str = ""
    ix_id: str = ""
    route_limit: str = ""
    prepend_base: str = ""
    timer_keepalive: str = ""
    timer_hold: str = ""
    bfd: bool = True
    graceful_restart: bool = True
    default_route: bool = False
    # em branco num downstream vira "nenhuma" no peer_do_formulario; nos
    # outros tipos o campo nao e lido
    tabela: str = ""
    bh_upstream: str = ""
    prefixos_v4: list[str] = []
    prefixos_v6: list[str] = []
    te_prefixos_v4: list[str] = []
    te_prefixos_v6: list[str] = []
    ap_block: list[str] = []
    ap_te: list[str] = []
    ap_allowed: list[str] = []
    ap_prefer: list[str] = []
    communities: list[str] = []
    large_communities: list[str] = []
    sessao_v4_local: str = ""
    sessao_v4_remoto: str = ""
    sessao_v6_local: str = ""
    sessao_v6_remoto: str = ""


class GrupoForm(Modelo):
    id: str = ""
    nome: str = ""
    tipo: str = "parceiro"
    asn: str = ""
    classe: str = ""
    lp_base: str = ""
    origem: str = ""
    pop: str = ""
    # o grupo_do_formulario le o aprendizado do IX num campo proprio: na tela
    # os blocos de upstream e de IX ficam lado a lado, cada um com o seu
    aprendizado: str = ""
    aprendizado_ix: str = ""
    ix_id: str = ""
    prepend_base: str = ""
    timer_keepalive: str = ""
    timer_hold: str = ""
    bfd: bool = True
    graceful_restart: bool = True
    default_route: bool = False
    # em branco num downstream vira "nenhuma" no peer_do_formulario; nos
    # outros tipos o campo nao e lido
    tabela: str = ""
    bh_upstream: str = ""
    prefixos_v4: list[str] = []
    prefixos_v6: list[str] = []
    te_prefixos_v4: list[str] = []
    te_prefixos_v6: list[str] = []
    ap_block: list[str] = []
    ap_te: list[str] = []
    ap_allowed: list[str] = []
    ap_prefer: list[str] = []
    communities: list[str] = []
    large_communities: list[str] = []


class Aviso(BaseModel):
    campo: str
    mensagem: str


class ErroResposta(BaseModel):
    """O corpo de toda recusa da API: um erro por campo e os avisos."""

    erros: dict[str, str]
    avisos: list[Aviso] = []


class RedeAtual(BaseModel):
    asn: str
    # em branco quando o namespace e o proprio ASN, o caso de todo ASN de
    # 16 bits
    politica: str


class RedeForm(Modelo):
    # sem o ASN: ele e o nome do arquivo do tenant, e nao um campo do corpo.
    # Quem troca de ASN e o seletor, que escolhe outro tenant
    politica: str = ""


class AsnPedido(Modelo):
    """O par do formulario de um tenant novo.

    Os dois campos sao texto, como os do resto do app: quem converte e o
    _asn_do_formulario, que devolve o erro no campo que o causou. O par
    inteiro vem junto porque um ASN de 32 bits precisa do namespace para
    ter um arquivo que funcione: sem ele, o tenant nasceria estourando na
    primeira leitura e a tela nao teria como conserta-lo, porque o plano
    do tenant e justamente o que falha.
    """

    asn: str = ""
    politica: str = ""


class TabelaTipo(BaseModel):
    lp_base: int | None
    route_limit: int | None
    timer_keepalive: int | None
    timer_hold: int | None
    # a caixa da default e a tabela que o tipo recebe ao nascer: a cascata da
    # troca de tipo le estes dois junto com os de cima
    default_route: bool
    tabela: str


class Padroes(BaseModel):
    """O _padroes() do formulario.py: o que a cascata de defaults le."""

    tipos: dict[str, TabelaTipo]
    origem_tipo: dict[str, int]
    origem_classe: dict[str, int]
    downstream: list[str]
    origens_por_tipo: dict[str, list[int]]
    origem_nome: dict[str, str]


class Sugestao(BaseModel):
    """Uma community que o formulario oferece para o operador clicar.

    O `valor` e o que entra no campo, o `rotulo` e o que a busca do
    operador casa e le, e o `grupo` e o cabecalho da lista.
    """

    valor: str
    rotulo: str
    grupo: str


class Sugestoes(BaseModel):
    """Uma lista por campo: a standard e a large nao cabem na mesma.

    Os dois campos do formulario tem formas diferentes (`ASN:VALOR` e
    `ASN:V1:V2`), e a validacao recusa a trocada: juntar as duas listas
    seria oferecer o erro.
    """

    communities: list[Sugestao]
    large_communities: list[Sugestao]


class Plano(BaseModel):
    rede: RedeAtual
    padroes: Padroes
    tipos: list[str]
    tipos_com_criar_lista: list[str]
    classes_cliente: list[str]
    # os valores da tabela recebida, na ordem da tela: o select do formulario
    # sai daqui, e nao de uma copia no front
    tabelas: list[str]
    lp_base: dict[str, int]
    route_limit: dict[str, int]
    route_limit_exemplo: dict[str, int]
    prepend_max: int
    prepend_implementado: int
    pop_min: int
    pop_max: int
    aprendizado_min: int
    aprendizado_max: int
    pop_usados: list[int]
    aprendizado_usados: list[int]
    campos_por_tipo: dict[str, list[str]]
    campos_por_tipo_grupo: dict[str, list[str]]
    sugestoes: Sugestoes


class PeerResumo(BaseModel):
    """Uma linha da barra lateral e da paleta de comandos."""

    id: int
    token: str
    tipo: str
    asn: int
    apelido: str
    nome: str
    grupo_id: int | None
    # quem reaproveita precisa que a tela saiba, para nao se oferecer como
    # origem de ninguem: quem cede politica e dono dela
    politica_de: int | None = None


class PeerRegistro(BaseModel):
    id: int
    # em branco no peer novo, que ainda nao tem ASN nem apelido
    token: str
    formulario: PeerForm


class PeerSalvo(BaseModel):
    registro: PeerRegistro
    # o nome do arquivo escrito em out/, para o toast da tela
    arquivo: str
    avisos: list[Aviso] = []


class Previa(BaseModel):
    """O que o salvar escreveria, sem gravar nada.

    Com erro de validacao, `erros` vem cheio e os blocos vem nulos: a tela nao
    pode ter o que copiar de um registro que o salvar recusaria. `salvo` e o
    arquivo atual em out/, para o diff, ou nulo quando nao ha.
    """

    erros: dict[str, str] = {}
    avisos: list[Aviso] = []
    bloco: str | None = None
    criar_lista: str | None = None
    arquivo: str | None = None
    salvo: str | None = None


class Saida(BaseModel):
    """Os blocos do registro salvo, que e o que esta no equipamento."""

    bloco: str
    remover: str | None = None
    criar_lista: str | None = None
    arquivo: str


class IrrPedido(Modelo):
    asn: str = ""
    # o token do cache e o do peer: o apelido quando ha, senao o ASN
    apelido: str = ""
    forcar: bool = False
    # as linhas que estao na tela, uma por prefixo: e o que a mesclagem usa
    # como base, para a reconsulta nao apagar o tratamento escrito a mao
    v4: list[str] = []
    v6: list[str] = []


class Prefixos(BaseModel):
    v4: list[str]
    v6: list[str]


class Membro(BaseModel):
    id: int
    token: str


class GrupoResumo(BaseModel):
    id: int
    nome: str
    tipo: str
    # a tela do membro mostra a tabela que ele herda
    tabela: str
    # a contagem sai dos peers, e nao de um campo gravado: e ela que diz se o
    # grupo ainda pode ser excluido
    membros: int


class GrupoRegistro(BaseModel):
    id: int
    nome: str
    formulario: GrupoForm
    membros: list[Membro]


class GrupoSalvo(BaseModel):
    registro: GrupoRegistro
    arquivo: str


class BlocosTexto(Modelo):
    """O texto dos dois editores, no formato da textarea de hoje.

    Uma linha por prefixo: o CIDR e depois as communities. Linha comecada por
    `!-` e prefixo fora de servico, e o `!-` no fim da linha e a marca do que
    sumiu da consulta ao IRR, que o salvar ignora.
    """

    v4: str = ""
    v6: str = ""


class Blocos(BaseModel):
    texto: BlocosTexto
    originacao: str | None = None
    remover: str | None = None


class BlocosIrrPedido(Modelo):
    v4: str = ""
    v6: str = ""
    forcar: bool = False


class LoginPedido(Modelo):
    """Usuario e senha do POST /api/login.

    Modelo com o extra="forbid" do resto: um nome de campo trocado no
    front nao pode passar em silencio e virar um login vazio.
    """

    usuario: str = ""
    senha: str = ""


class SessaoResposta(BaseModel):
    """Quem esta logado. E a resposta do login, do logout e do /sessao."""

    logado: bool
    usuario: str | None = None


class SecaoConfig(BaseModel):
    """Um pedaco da config inteira, ja renderizado.

    `arquivo` e o nome em out/ que aquele bloco grava, e `salvo` diz se ele
    esta la. Os dois sao nulos no base, que e montado a cada requisicao pelo
    render e nunca teve arquivo proprio.
    """

    chave: str
    titulo: str
    texto: str
    arquivo: str | None = None
    salvo: bool | None = None


class Config(BaseModel):
    """Toda a config numa resposta so, na ordem em que se cola."""

    secoes: list[SecaoConfig]
