"""O PDF que o cliente recebe: os dados do politica.py impressos.

Os casos leem os bytes que saem do gerador, e nao um objeto intermediario:
e a unica ponta que prova que a tabela chegou na folha. E por isso que o
gerador nao comprime as paginas - o texto vai literal no arquivo.
"""

from dados_api import UPSTREAM

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


def secao(titulo):
    """Os textos de uma secao do documento, antes de virar folha."""
    doc = politica.documento(REDE, emitido_em=DATA)
    return " ".join(texto for s in doc.secoes if s.titulo == titulo
                    for texto in s.textos)


def test_o_pdf_diz_que_a_restricao_padronizada_e_honrada():
    """A preservacao da restricao recebida muda o que o cliente ve: a rota
    marcada com NO_EXPORT deixa de sair para os outros clientes. Isso e
    promessa da folha, nao so do filtro."""
    texto = secao("Controle de anúncio")
    for marca in ("NO_EXPORT_SUBCONFED", "NO_ADVERTISE", "NO_EXPORT"):
        assert marca in texto
    # e o efeito tem que estar dito: nao sai para destino nenhum
    assert "não é anunciada em destino nenhum" in texto
    # na folha tambem, que e a ponta que o cliente le
    assert b"NO_ADVERTISE" in gerado()


def test_o_pdf_diz_que_a_propagacao_do_blackhole_respeita_o_destino():
    """O achado 5 da auditoria: o ramo de RTBH terminava antes dos bloqueios,
    e o pedido de propagacao atropelava o que o cliente tinha marcado."""
    texto = secao("Blackhole")
    assert "respeita as mesmas restrições de destino" in texto
    assert "65532:0:<ASN>" in texto


def test_o_pdf_diz_que_blackhole_fora_do_host_e_recusado():
    """A auditoria v5, secao 3: o pedido de descarte num prefixo maior que o
    host caia no fluxo normal e saia com a community. Agora o import o recusa,
    e o cliente precisa saber que o anuncio inteiro some, nao so o pedido."""
    texto = secao("Blackhole")
    assert "é recusado" in texto


def test_o_cabecalho_da_tabela_sai_em_negrito():
    """A faixa cinza sozinha nao separa o cabecalho do corpo.

    O estilo CABECALHO existia sem nenhum consumidor desde o primeiro
    commit: o cabecalho saia com a fonte do corpo, e a tabela do alias, que
    e a mais larga do documento, e a que mais depende disso.
    """
    assert pdf.estilo_da_celula(0, 0).fontName == "Helvetica-Bold"
    assert pdf.estilo_da_celula(0, 3).fontName == "Helvetica-Bold"
    # a primeira coluna do corpo e mono; o resto, nao
    assert pdf.estilo_da_celula(1, 0).fontName == "Courier"
    assert pdf.estilo_da_celula(1, 3).fontName == "Helvetica"


def test_a_tabela_do_alias_cabe_na_folha():
    """Sete colunas sao a tabela mais larga do documento.

    As larguras eram fixas em duas colunas (`[LARGURA/2]*2`) e uma tabela de
    sete sairia com duas celulas para sete valores, o que o reportlab aceita
    calado: a linha some da folha sem erro nenhum.
    """
    larguras = pdf._colunas(7)
    assert len(larguras) == 7
    assert abs(sum(larguras) - pdf.LARGURA) < 0.01


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


def test_o_pdf_publica_os_upstreams_do_cadastro(api):
    """A tabela do alias sai do cadastro da rede, e nao de uma lista fixa.

    Quem le o PDF nao descobre o identificador de um upstream sozinho, e o
    que o operador cadastra pela tela e o que tem que aparecer na folha. O
    caso le o ID de volta da lista, como faria quem acabou de criar o peer.
    """
    assert api.post("/api/peers", json=UPSTREAM).status_code == 201
    ident = api.get("/api/peers").json()[0]["id"]

    corpo = api.get("/politica-cliente.pdf").content

    assert plan.c5ppa(ident, 1, "64512").encode("ascii") in corpo
    assert b"14840" in corpo


def test_o_pdf_publica_o_id_do_grupo_e_nao_o_do_membro(api):
    """O caminho de ponta a ponta do upstream agrupado.

    O operador cria o grupo de upstream, poe o peer como membro e gera o
    PDF. O identificador que sai na folha tem que ser o do grupo: o membro
    nao tem CL-5PPA nenhum no bloco dele.
    """
    from dados_api import GRUPO_UPSTREAM

    assert api.post("/api/grupos", json=GRUPO_UPSTREAM).status_code == 201
    grupo_id = api.get("/api/grupos").json()[0]["id"]
    # o apelido vira o token do peer, e o nome do grupo e o token dele
    # disputam o mesmo nome de objeto: com o mesmo texto nos dois, o
    # cadastro recusa antes de chegar ao PDF
    membro = dict(UPSTREAM, apelido="OPERADORA-SP", grupo_id=str(grupo_id))
    assert api.post("/api/peers", json=membro).status_code == 201
    membro_id = api.get("/api/peers").json()[0]["id"]
    # os dois IDs saem da mesma faixa de 0 a 99, e o proximo_id nao repete
    # nenhum: se repetissem, este caso passaria por acidente
    assert grupo_id != membro_id

    corpo = api.get("/politica-cliente.pdf").content

    assert plan.c5ppa(grupo_id, 1, "64512").encode("ascii") in corpo
    assert plan.c5ppa(membro_id, 1, "64512").encode("ascii") not in corpo


def test_o_pdf_publica_o_id_da_origem_e_nao_o_de_quem_reaproveita(api):
    """O irmao do caso do grupo, para o outro upstream que nao emite 5PPA.

    Quem reaproveita a politica de outro nao tem CL-5PPA nenhum: o bloco dele
    so chama os filtros da origem, e a unica lista de alias que existe e a
    dela, com o id dela. Publicar o id de quem reaproveita daria dois
    identificadores para o mesmo ASN, e o cliente que escolhesse o segundo
    mandaria uma community que nao casa com ramo nenhum: ela cai no ramo
    default do 6CA, e o prepend pedido some sem aviso.
    """
    r = api.post("/api/peers", json=UPSTREAM)
    assert r.status_code == 201
    origem_id = r.json()["registro"]["id"]
    # o segundo link tem os enderecos dele: o da origem ja esta em uso, e o
    # validate recusa a sessao repetida antes de qualquer render
    backup = dict(UPSTREAM, apelido="OP-BKP", id="",
                  politica_de=str(origem_id), sessao_v4_local="203.0.113.4",
                  sessao_v4_remoto="203.0.113.3")
    r = api.post("/api/peers", json=backup)
    assert r.status_code == 201, r.text
    backup_id = r.json()["registro"]["id"]
    # os dois IDs saem da mesma faixa de 0 a 99, e o proximo_id nao repete
    # nenhum: se repetissem, este caso passaria por acidente
    assert origem_id != backup_id

    corpo = api.get("/politica-cliente.pdf").content

    assert plan.c5ppa(origem_id, 1, "64512").encode("ascii") in corpo
    assert plan.c5ppa(backup_id, 1, "64512").encode("ascii") not in corpo


def test_o_pdf_nao_publica_identificador_de_ix(api):
    """O IX tem ID no cadastro, mas nao tem ramo de alias no filtro.

    O filtro do route server repassa o mesmo AS-path a todos os membros, e
    por isso nao ha 5PPA para IX nenhum. A tabela do PDF so pode listar o
    que o equipamento executa.
    """
    from dados_api import IX

    assert api.post("/api/peers", json=IX).status_code == 201
    ident = api.get("/api/peers").json()[0]["id"]

    corpo = api.get("/politica-cliente.pdf").content

    assert plan.c5ppa(ident, 1, "64512").encode("ascii") not in corpo


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


def test_o_pdf_diz_o_que_o_cliente_recebe():
    texto = secao("O que você recebe de nós")
    assert "full table" in texto
