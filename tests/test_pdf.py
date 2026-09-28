"""O PDF que o cliente recebe: os dados do politica.py impressos.

Os casos leem os bytes que saem do gerador, e nao um objeto intermediario:
e a unica ponta que prova que a tabela chegou na folha. E por isso que o
gerador nao comprime as paginas - o texto vai literal no arquivo.
"""

from app import pdf, plan, politica

REDE = plan.Rede(264130, 65532)
DATA = "28/09/2026"


def gerado():
    return pdf.gerar(politica.documento(REDE, emitido_em=DATA))


def test_o_arquivo_e_um_pdf():
    assert gerado().startswith(b"%PDF-")


def test_nenhum_canto_do_pdf_mostra_o_namespace_de_fabrica():
    """Titulo, rodape e metadado saem todos do mesmo documento.

    O gerador ja teve um `rede` por parametro, e quem o chamasse sem passar
    o da rede imprimia `64512` embaixo de uma tabela `65532`: o rodape e o
    assunto do arquivo ficavam com o namespace de fabrica. O caso vale para
    o PDF inteiro de proposito, para nao deixar canto novo fora dele.
    """
    assert b"64512" not in gerado()


def test_o_pdf_leva_a_community_no_namespace_da_rede():
    # o caminho inteiro: plan.Rede -> politica.documento -> folha impressa
    dados = gerado()
    assert b"65532:101" in dados
    assert b"64512:101" not in dados


def test_o_pdf_traz_o_as_e_a_data_de_emissao():
    # a data e o que deixa o cliente saber de que revisao da politica ele
    # tem uma copia na mao
    dados = gerado()
    assert b"AS264130" in dados
    assert DATA.encode("ascii") in dados


def test_o_pdf_nao_depende_do_relogio():
    # o mesmo documento gera os mesmos bytes: sem isto, um caso que cobra a
    # data so passa no dia em que foi escrito
    assert gerado() == gerado()


# --- a rota ------------------------------------------------------------
#
# O /politica-cliente.pdf nao esta em /api, e do tenant como o /base.txt:
# quem baixa o documento baixa o de uma rede, e o namespace das communities
# que saem nele e o dela.


def test_a_rota_entrega_um_pdf(api):
    r = api.get("/politica-cliente.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")


def test_o_arquivo_baixado_tem_nome(api):
    # o navegador usa este nome quando o operador salva; sem ele o arquivo
    # sai como "politica-cliente.pdf" e a pasta do ISP enche de homonimos
    r = api.get("/politica-cliente.pdf")
    assert "politica-bgp-64512.pdf" in r.headers["content-disposition"]


def test_a_rota_segue_o_namespace_gravado(api):
    """O caminho de ponta a ponta do PUT /api/rede, como no /base.txt.

    O namespace vai para o arquivo do tenant e a proxima leitura ja sai com
    ele: um documento que fixasse o 64512 do plan.py entregaria ao cliente
    uma community que nao existe na rede dele.
    """
    assert api.put("/api/rede", json={"politica": "64500"}).status_code == 200
    corpo = api.get("/politica-cliente.pdf").content
    assert b"64500:101" in corpo
    assert b"64512:101" not in corpo


def test_a_rota_recusa_sem_o_asn(api):
    # o mesmo 422 do /base.txt: o `?asn=` e o que escolhe o arquivo do tenant
    assert api.cru.get("/politica-cliente.pdf").status_code == 422


def test_a_rota_recusa_asn_sem_tenant(api):
    """404 no formato das outras recusas, e não o "Not Found" do FastAPI.

    A diferenca entre os dois e o que separa "este ASN nao tem cadastro" de
    "esta rota nao existe", e sem ela este caso passaria com a rota apagada.
    """
    r = api.get("/politica-cliente.pdf", params={"asn": 999})
    assert r.status_code == 404
    assert "999" in r.json()["erros"]["_"]
