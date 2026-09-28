"""O documento do politica.py impresso em PDF, com o reportlab.

A separacao e a mesma do render.py: la o Jinja escreve o texto que vai para
o equipamento, aqui o Platypus compoe o que vai para a mesa do cliente. O
que este modulo sabe e de folha - margem, fonte, tabela, numero de pagina -,
e nao de politica nenhuma: os numeros chegam prontos do politica.py.
"""

import html
import re
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

MARGEM = 18 * mm
LARGURA = A4[0] - 2 * MARGEM
COLUNA_ESTREITA = 46 * mm

CINZA = colors.HexColor("#f2f2f2")
LINHA = colors.HexColor("#cccccc")

TITULO = ParagraphStyle(
    "titulo", fontName="Helvetica-Bold", fontSize=19, leading=23,
    spaceAfter=4 * mm)
SUBTITULO = ParagraphStyle(
    "subtitulo", fontName="Helvetica", fontSize=10.5, leading=14,
    textColor=colors.HexColor("#444444"), spaceAfter=2 * mm)
EMISSAO = ParagraphStyle(
    "emissao", fontName="Helvetica", fontSize=8.5, leading=11,
    textColor=colors.HexColor("#666666"), spaceAfter=8 * mm)
SECAO = ParagraphStyle(
    "secao", fontName="Helvetica-Bold", fontSize=12.5, leading=15,
    spaceBefore=6 * mm, spaceAfter=2 * mm,
    # o titulo nao fica sozinho no fim da folha: ele puxa o primeiro
    # paragrafo junto
    keepWithNext=True)
CORPO = ParagraphStyle(
    "corpo", fontName="Helvetica", fontSize=9.5, leading=13, spaceAfter=2 * mm)
CELULA = ParagraphStyle(
    "celula", fontName="Helvetica", fontSize=9, leading=12)
CABECALHO = ParagraphStyle(
    "cabecalho", fontName="Helvetica-Bold", fontSize=9, leading=12)
CODIGO = ParagraphStyle(
    "codigo", fontName="Courier", fontSize=8.5, leading=12)

# o backtick é a marcação de community no texto do politica.py, que é
# prosa e não markup: aqui ele vira a fonte mono, que é o que faz
# `65532:101` e `65532:1011` não se confundirem na leitura
_CODIGO = re.compile(r"`([^`]+)`")


def _marcado(texto):
    """Escapa o texto e troca os backticks pela fonte mono.

    A ordem importa: o `<ASN>` da tabela de large community é texto para o
    cliente, e sem o escape o reportlab o leria como tag e o campo sumiria
    da folha.
    """
    escapado = html.escape(texto, quote=False)
    return _CODIGO.sub(
        lambda m: '<font name="Courier">%s</font>' % m.group(1), escapado)


def _tabela(tabela):
    linhas = [[Paragraph(_marcado(c), CODIGO if i == 0 else CELULA)
               for i, c in enumerate(tabela.colunas)]]
    for linha in tabela.linhas:
        linhas.append([Paragraph(_marcado(c), CODIGO if i == 0 else CELULA)
                       for i, c in enumerate(linha)])
    largura = COLUNA_ESTREITA if len(tabela.colunas) == 1 else None
    colunas = [largura, LARGURA - largura] if largura else [LARGURA / 2] * 2
    return Table(linhas, colWidths=colunas, repeatRows=1, hAlign="LEFT",
                 style=TableStyle([
                     ("BACKGROUND", (0, 0), (-1, 0), CINZA),
                     ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
                     ("VALIGN", (0, 0), (-1, -1), "TOP"),
                     ("LEFTPADDING", (0, 0), (-1, -1), 4),
                     ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                     ("TOPPADDING", (0, 0), (-1, -1), 3),
                     ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                 ]))


def _fluxo(documento):
    fluxo = [Paragraph(_marcado(documento.titulo), TITULO),
             Paragraph(_marcado(documento.subtitulo), SUBTITULO)]
    # a data e opcional porque quem chama pode nao ter uma: o documento sem
    # ela continua valendo, e o que nao pode e sair um "Emitido em " vazio
    if documento.emitido_em:
        fluxo.append(Paragraph("Emitido em %s" % documento.emitido_em, EMISSAO))
    for secao in documento.secoes:
        fluxo.append(Paragraph(_marcado(secao.titulo), SECAO))
        for texto in secao.textos:
            fluxo.append(Paragraph(_marcado(texto), CORPO))
        for tabela in secao.tabelas:
            fluxo.append(Spacer(1, 2 * mm))
            fluxo.append(_tabela(tabela))
    return fluxo


def _rodape(tela, modelo):
    """O que vai no pe de toda folha: o documento, do lado esquerdo."""
    tela.saveState()
    tela.setFont("Helvetica", 7.5)
    tela.setFillColor(colors.HexColor("#666666"))
    tela.drawString(MARGEM, MARGEM - 5 * mm, modelo.documento.rodape)
    tela.drawRightString(A4[0] - MARGEM, MARGEM - 5 * mm,
                         "página %d" % tela.getPageNumber())
    tela.restoreState()


def gerar(documento):
    """Os bytes do PDF do documento.

    O `invariant` e o que faz dois pedidos do mesmo documento darem bytes
    iguais: sem ele o reportlab grava a hora da geracao no arquivo, e nao ha
    como provar por teste que o conteudo nao mudou. A compressao de pagina
    sai desligada pelo mesmo motivo: ela leva alguns KB que este documento
    nao sente, e em troca o texto fica legivel no arquivo, que e o que
    deixa o teste cobrar a tabela na folha em vez de um objeto no meio do
    caminho.
    """
    buffer = BytesIO()
    modelo = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGEM, rightMargin=MARGEM,
        topMargin=MARGEM, bottomMargin=MARGEM + 6 * mm,
        title=documento.titulo, subject=documento.subtitulo,
        invariant=1, pageCompression=0)
    modelo.documento = documento
    modelo.build(_fluxo(documento), onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()
