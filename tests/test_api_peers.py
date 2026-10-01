"""A API dos peers."""

from app import peers as peers_mod
from app.api import modelo_do_peer
from dados_api import (ASN_DE_TESTE, CLIENTE, UPSTREAM, IX,
                       GRUPO_PARCEIROS, arvore, caminho_tenant, membro_de)
from test_render import peer_cliente, peer_ix


def _grava(tmp_path, *peers):
    # o arquivo do tenant de teste, que e o unico que a API le
    peers_mod.gravar(list(peers), caminho_tenant(tmp_path))


def test_a_lista_comeca_vazia(api):
    assert api.get("/api/peers").json() == []


def test_a_lista_resume_cada_peer(api, tmp_path):
    _grava(tmp_path, peer_cliente(), peer_ix())
    assert api.get("/api/peers").json() == [
        {"id": 1, "token": "268127", "tipo": "cliente", "asn": 268127,
         "apelido": "", "nome": "Cliente ACME", "grupo_id": None,
         "politica_de": None},
        {"id": 10, "token": "IX-SP", "tipo": "ix", "asn": 26162,
         "apelido": "IX-SP", "nome": "IX.br Sao Paulo", "grupo_id": None,
         "politica_de": None},
    ]


def test_o_peer_novo_traz_os_defaults_do_tipo(api):
    corpo = api.get("/api/peers/novo", params={"tipo": "upstream"}).json()
    f = corpo["formulario"]
    assert (corpo["id"], corpo["token"]) == (0, "")
    assert (f["tipo"], f["lp_base"], f["route_limit"]) == ("upstream", "100", "1500000")
    assert (f["timer_keepalive"], f["timer_hold"]) == ("10", "30")
    assert (f["aprendizado"], f["origem"], f["asn"]) == ("3100", "1400", "")


def test_o_peer_novo_de_downstream_recebe_so_a_default(api):
    for tipo in ("cliente", "parceiro"):
        f = api.get("/api/peers/novo", params={"tipo": tipo}).json()["formulario"]
        assert (f["default_route"], f["tabela"]) == (True, "nenhuma"), tipo
    f = api.get("/api/peers/novo", params={"tipo": "upstream"}).json()["formulario"]
    assert (f["default_route"], f["tabela"]) == (False, "")


def test_post_de_cliente_sem_tabela_grava_nenhuma(api, tmp_path):
    r = api.post("/api/peers", json=CLIENTE)
    assert r.status_code == 201, r.text
    assert peers_mod.carregar(caminho_tenant(tmp_path))[0].tabela == "nenhuma"


def test_o_peer_novo_pula_o_id_ocupado(api, tmp_path):
    _grava(tmp_path, peer_cliente(id=0))
    assert api.get("/api/peers/novo").json()["id"] == 1


def test_tipo_desconhecido_vira_cliente(api):
    corpo = api.get("/api/peers/novo", params={"tipo": "xyz"}).json()
    assert corpo["formulario"]["tipo"] == "cliente"


def test_o_registro_traz_o_formulario_do_peer(api, tmp_path):
    peer = peer_ix()
    _grava(tmp_path, peer)
    corpo = api.get("/api/peers/10").json()
    assert corpo["token"] == "IX-SP"
    assert corpo["formulario"] == modelo_do_peer(peer).model_dump()


def test_id_que_nao_existe_e_404(api):
    r = api.get("/api/peers/42")
    assert r.status_code == 404
    assert r.json() == {"erros": {"_": "peer nao encontrado"}, "avisos": []}


def test_id_que_nao_e_numero_volta_422_no_formato_da_api(api):
    r = api.get("/api/peers/abc")
    assert r.status_code == 422
    assert "ident" in r.json()["erros"]["_corpo"]


def test_a_copia_troca_so_o_id(api, tmp_path):
    _grava(tmp_path, peer_cliente(id=0), peer_ix())
    corpo = api.get("/api/peers/0/copia").json()
    original = modelo_do_peer(peer_cliente(id=0)).model_dump()
    assert corpo["id"] == 1
    assert corpo["token"] == "268127"
    assert corpo["formulario"] == dict(original, id="1")


def test_a_copia_nao_grava_nada(api, tmp_path):
    _grava(tmp_path, peer_cliente())
    antes = arvore(tmp_path)
    assert api.get("/api/peers/1/copia").status_code == 200
    assert arvore(tmp_path) == antes


def test_a_copia_de_id_que_nao_existe_e_404(api):
    assert api.get("/api/peers/3/copia").status_code == 404


def test_criar_grava_o_yaml_e_o_bloco(api, tmp_path):
    r = api.post("/api/peers", json=CLIENTE)
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["arquivo"] == "268127-cliente.txt"
    assert (corpo["registro"]["id"], corpo["registro"]["token"]) == (0, "268127")
    assert [p.asn for p in peers_mod.carregar(caminho_tenant(tmp_path))] == [268127]
    assert (tmp_path / "out" / str(ASN_DE_TESTE) / "268127-cliente.txt").exists()


def test_erro_de_campo_volta_422_e_nao_grava(api, tmp_path):
    antes = arvore(tmp_path)
    r = api.post("/api/peers", json=dict(CLIENTE, asn="abc"))
    assert r.status_code == 422
    assert r.json()["erros"]["asn"] == "valor numerico invalido"
    assert arvore(tmp_path) == antes


def test_asn_repetido_e_recusado_no_campo(api):
    api.post("/api/peers", json=CLIENTE)
    r = api.post("/api/peers", json=dict(
        CLIENTE, sessao_v4_remoto="198.51.100.3", prefixos_v4=["45.169.240.0/22"]))
    assert r.status_code == 422
    # o CLIENTE nao tem apelido, entao o token dos dois e o ASN e e ele que
    # colide: o campo do erro e o apelido, que e o que resolve
    assert r.json()["erros"]["apelido"] == (
        "o ASN 268127 ja e o token do peer Cliente ACME: de um apelido a este "
        "peer")


def test_nome_com_acento_volta_422_no_campo(api, tmp_path):
    antes = arvore(tmp_path)
    r = api.post("/api/peers", json=dict(CLIENTE, nome="Cliente S" + chr(0xE3) + "o Paulo"))
    assert r.status_code == 422
    assert r.json()["erros"]["nome"] == "nome so aceita ASCII puro, sem acento"
    assert arvore(tmp_path) == antes


def test_campo_desconhecido_volta_422_nomeando_o_campo(api, tmp_path):
    antes = arvore(tmp_path)
    r = api.post("/api/peers", json=dict(CLIENTE, xpto="1"))
    assert r.status_code == 422
    assert "xpto" in r.json()["erros"]["_corpo"]
    assert arvore(tmp_path) == antes


def test_asn_privado_salva_com_aviso(api):
    r = api.post("/api/peers", json=dict(CLIENTE, asn="64500",
                                          descricao="CLIENTE-AS64500"))
    assert r.status_code == 201, r.text
    assert {"campo": "asn",
            "mensagem": "ASN privado: confirme que o peer tambem o usa"} in r.json()["avisos"]


def test_trocar_o_asn_apaga_o_bloco_antigo(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    r = api.put("/api/peers/0", json=dict(CLIENTE, asn="268128"))
    assert r.status_code == 200, r.text
    assert not (tmp_path / "out" / str(ASN_DE_TESTE) / "268127-cliente.txt").exists()
    assert (tmp_path / "out" / str(ASN_DE_TESTE) / "268128-cliente.txt").exists()


def test_trocar_o_id_no_corpo_move_o_registro_da_url(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    r = api.put("/api/peers/0", json=dict(CLIENTE, id="7"))
    assert r.status_code == 200, r.text
    assert r.json()["registro"]["id"] == 7
    assert [p.id for p in peers_mod.carregar(caminho_tenant(tmp_path))] == [7]
    assert api.get("/api/peers/0").status_code == 404


def test_atualizar_id_que_nao_existe_e_404(api):
    assert api.put("/api/peers/5", json=CLIENTE).status_code == 404


def test_salvar_o_que_o_get_devolveu_nao_muda_nada(api, tmp_path):
    api.post("/api/peers", json=UPSTREAM)
    antes = arvore(tmp_path)
    formulario = api.get("/api/peers/0").json()["formulario"]
    assert api.put("/api/peers/0", json=formulario).status_code == 200
    assert arvore(tmp_path) == antes


def test_excluir_apaga_o_registro_e_o_bloco(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    assert api.delete("/api/peers/0").status_code == 204
    assert peers_mod.carregar(caminho_tenant(tmp_path)) == []
    assert not (tmp_path / "out" / str(ASN_DE_TESTE) / "268127-cliente.txt").exists()
    assert api.delete("/api/peers/0").status_code == 404


def _salvo(tmp_path, nome="268127-cliente.txt"):
    return (tmp_path / "out" / str(ASN_DE_TESTE) / nome).read_text(encoding="ascii")


def test_a_previa_do_peer_novo_e_o_bloco_que_o_salvar_escreve(api, tmp_path):
    previa = api.post("/api/peers/previa", json=CLIENTE).json()
    assert previa["erros"] == {} and previa["salvo"] is None
    assert previa["arquivo"] == "268127-cliente.txt"
    api.post("/api/peers", json=CLIENTE)
    assert _salvo(tmp_path) == previa["bloco"]


def test_a_previa_nao_grava_nada(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    antes = arvore(tmp_path)
    api.post("/api/peers/previa", params={"id": 0}, json=dict(CLIENTE, lp_base="250"))
    api.post("/api/peers/previa", json=UPSTREAM)
    assert arvore(tmp_path) == antes


def test_a_previa_com_erro_volta_200_sem_bloco(api):
    r = api.post("/api/peers/previa", json=dict(CLIENTE, asn="abc"))
    assert r.status_code == 200
    assert r.json()["erros"]["asn"] == "valor numerico invalido"
    assert r.json()["bloco"] is None


def test_a_previa_de_um_peer_salvo_traz_o_arquivo_de_out(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    previa = api.post("/api/peers/previa", params={"id": 0}, json=CLIENTE).json()
    assert previa["salvo"] == _salvo(tmp_path)
    assert previa["bloco"] == previa["salvo"]


def test_arquivo_apagado_de_out_vira_salvo_nulo(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    (tmp_path / "out" / str(ASN_DE_TESTE) / "268127-cliente.txt").unlink()
    previa = api.post("/api/peers/previa", params={"id": 0}, json=CLIENTE).json()
    assert previa["salvo"] is None


def test_o_quadro_ao_criar_so_sai_nos_tipos_com_cl_peer(api):
    cliente = api.post("/api/peers/previa", json=CLIENTE).json()
    assert "xpl community-list CL-PEER-268127" in cliente["criar_lista"]
    assert api.post("/api/peers/previa", json=IX).json()["criar_lista"] is None


def test_a_previa_com_grupo_que_nao_existe_aponta_o_campo(api):
    r = api.post("/api/peers/previa", json=dict(CLIENTE, grupo_id="9"))
    assert r.json()["erros"]["grupo_id"] == "grupo nao encontrado"
    assert r.json()["bloco"] is None


def test_a_saida_traz_bloco_remocao_e_quadro(api, tmp_path):
    api.post("/api/peers", json=CLIENTE)
    corpo = api.get("/api/peers/0/saida").json()
    assert corpo["bloco"] == _salvo(tmp_path)
    assert "undo peer 198.51.100.2" in corpo["remover"]
    assert "APPLY-PEER-268127" in corpo["criar_lista"]
    assert corpo["arquivo"] == "268127-cliente.txt"


def test_a_saida_de_membro_de_grupo_que_saiu_e_recusada(api, tmp_path):
    peers_mod.gravar([peer_cliente(id=0, grupo_id=9)], caminho_tenant(tmp_path))
    r = api.get("/api/peers/0/saida")
    assert r.status_code == 422
    assert r.json()["erros"]["grupo_id"] == "grupo nao encontrado"


def test_a_saida_de_id_que_nao_existe_e_404(api):
    assert api.get("/api/peers/3/saida").status_code == 404


def test_trocar_o_tipo_apaga_o_bloco_do_tipo_antigo(api, tmp_path):
    """O arquivo de out/ muda de nome quando o tipo muda.

    O nome e <token>-<tipo>.txt, entao trocar o tipo deixa o bloco velho orfao
    justamente no diretorio de onde o operador cola. O irmao deste caso
    (test_trocar_o_asn_apaga_o_bloco_antigo) cobre a outra metade, o token.
    """
    assert api.post("/api/peers", json=CLIENTE).status_code == 201
    assert (tmp_path / "out" / str(ASN_DE_TESTE) / "268127-cliente.txt").exists()

    r = api.put("/api/peers/0", json=dict(CLIENTE, tipo="upstream",
                                          aprendizado="3100", prefixos_v4=[]))

    assert r.status_code == 200, r.text
    assert not (tmp_path / "out" / str(ASN_DE_TESTE) / "268127-cliente.txt").exists()
    assert (tmp_path / "out" / str(ASN_DE_TESTE) / "268127-upstream.txt").exists()


def test_o_id_escolhido_no_corpo_e_o_do_registro(api, tmp_path):
    """O id do peer novo vem do formulario quando o operador o preenche.

    O id e a identidade do registro - e o que a URL da SPA usa -, e o campo
    sempre existiu. O id implicito tem teste (test_criar_grava_o_yaml_e_o_bloco)
    e o id que move um registro no PUT tambem
    (test_trocar_o_id_no_corpo_move_o_registro_da_url); o id no POST nao.
    """
    r = api.post("/api/peers", json=dict(CLIENTE, id="7"))

    assert r.status_code == 201, r.text
    assert r.json()["registro"]["id"] == 7
    assert [p.id for p in peers_mod.carregar(caminho_tenant(tmp_path))] == [7]


def test_tipo_desconhecido_no_corpo_e_erro_no_campo(api, tmp_path):
    """O tipo do corpo e conferido, e nao cai em cliente em silencio.

    O GET /api/peers/novo?tipo=xyz cai em cliente (test_tipo_desconhecido_vira_cliente),
    e isso e outra coisa: o formulario em branco nascer com o tipo de sempre.
    Num POST, um tipo que nao existe e recusa.
    """
    r = api.post("/api/peers", json=dict(CLIENTE, tipo="xyz"))

    assert r.status_code == 422
    assert r.json()["erros"]["tipo"] == "tipo desconhecido: xyz"
    assert peers_mod.carregar(caminho_tenant(tmp_path)) == []

    # e o tipo vazio nao e tipo desconhecido: campo em branco cai no cliente,
    # como os outros campos do formulario caem no default da tabela
    assert api.post("/api/peers", json=dict(CLIENTE, tipo="")).status_code == 201
    assert [p.tipo for p in peers_mod.carregar(caminho_tenant(tmp_path))] == ["cliente"]


def test_peer_com_grupo_de_outro_tipo_e_recusado_no_campo(api, tmp_path):
    """O membro tem que ser do tipo do grupo.

    A regra e do validate (test_peer_com_tipo_diferente_do_grupo_e_erro, em
    test_validate.py, olha o campo); o que faltava era a mensagem inteira
    chegando pelo campo certo na rota que o operador usa.
    """
    grupo = api.post("/api/grupos", json=GRUPO_PARCEIROS).json()["registro"]

    r = api.post("/api/peers", json=dict(UPSTREAM, grupo_id=str(grupo["id"]),
                                         nome="MEMBRO", asn="14841"))

    assert r.status_code == 422
    assert r.json()["erros"]["grupo_id"] == (
        "grupo PARCEIROS_CDN e de parceiro, nao de upstream")
    assert peers_mod.carregar(caminho_tenant(tmp_path)) == []


def test_membro_sem_filtro_proprio_nao_usa_o_lp_gravado(api, tmp_path):
    """O lp_base que ficou no cadastro do membro nao entra na saida dele.

    O membro sem filtro proprio herda a politica do grupo, e o render ja tem
    teste disso (test_membro_sem_override_so_referencia_o_grupo, em
    test_render.py). O que nao tinha par era o caso do valor GRAVADO e
    ignorado: o membro herda do grupo mesmo com 999 no proprio cadastro.
    """
    grupo = api.post("/api/grupos", json=GRUPO_PARCEIROS).json()["registro"]
    corpo = membro_de(grupo["id"])
    corpo.update(nome="Membro sem filtro", apelido="MEMBRO", asn="64510",
                 lp_base="999", sessao_v4_local="198.51.100.30",
                 sessao_v4_remoto="198.51.100.31")
    membro = api.post("/api/peers", json=corpo).json()["registro"]

    bloco = api.get("/api/peers/%d/saida" % membro["id"]).json()["bloco"]

    assert [p.lp_base for p in peers_mod.carregar(caminho_tenant(tmp_path))] == [999]
    assert "999" not in bloco
    assert "apply local-preference" not in bloco
    assert "group PARCEIROS_CDN" in bloco


def test_origem_fora_da_tabela_do_tipo_grava(api, tmp_path):
    """O upstream aceita uma origem que nao esta na tabela dele.

    Isto e buraco conhecido, e nao regra: o validate confere a faixa de origem
    dos tipos downstream (ORIGENS_CLIENTE) e cobra o ORIGENS_POR_TIPO do grupo,
    nunca do peer. O bloco de um upstream com origem 14 sai carimbando
    64512:14. O teste existe para o buraco ficar visivel no dia em que alguem
    for fecha-lo - e o comentario do test_app.py que o registrava sai no corte.
    """
    r = api.post("/api/peers", json=dict(UPSTREAM, origem="14"))

    assert r.status_code == 201, r.text
    assert [p.origem for p in peers_mod.carregar(caminho_tenant(tmp_path))] == [14]


def test_origem_em_branco_cai_no_default_da_classe_e_do_tipo(api, tmp_path):
    """A origem apagada no formulario nao zera o campo: ela cai na tabela.

    No cliente e no parceiro quem manda e a classe (cgnat e 1130); no upstream,
    que nao tem classe, e a origem do tipo (1400). O formulario em branco mostra
    esse valor e tem teste (test_o_peer_novo_traz_os_defaults_do_tipo); o POST
    com o campo apagado nao tinha, e era o caminho em que a origem em branco
    estourava o "%d" do render com o peer ja gravado.
    """
    assert api.post("/api/peers", json=dict(CLIENTE, origem="", classe="cgnat")).status_code == 201
    assert api.post("/api/peers", json=dict(UPSTREAM, origem="")).status_code == 201

    assert [p.origem for p in peers_mod.carregar(caminho_tenant(tmp_path))] == [1130, 1400]


def test_o_asn_sem_cadastro_da_404_no_formato_das_recusas(api):
    resposta = api.get("/api/peers", params={"asn": 999})
    assert resposta.status_code == 404
    assert "999" in resposta.json()["erros"]["_"]


def test_o_asn_que_falta_da_422(api):
    resposta = api.cru.get("/api/peers")
    assert resposta.status_code == 422
    assert "_corpo" in resposta.json()["erros"]


def test_o_base_txt_tambem_e_do_tenant(api):
    """O /base.txt e fetch cru no front, e nao do cliente tipado.

    Ele sai do schema como as outras rotas, mas o `?asn=` dele nao esta em
    chamada nenhuma do openapi-fetch: quem o busca e o fetch cru da Casca e
    da tela do bloco base. Sem esta prova, o parametro sumiria de la sem
    nenhum teste reclamar.
    """
    assert api.get("/base.txt").status_code == 200
    assert api.get("/base.txt", params={"asn": 999}).status_code == 404


def test_o_bloco_do_peer_sai_na_pasta_do_tenant(api, tmp_path):
    """O bloco cai em out/<ASN>/, e nao na raiz do out/.

    O peer que ja estava no arquivo continua la: a rota le e grava o mesmo
    arquivo que o _grava escreveu por fora. Sem essa metade, a pasta de
    saida poderia estar certa com o tenant errado por tras.
    """
    _grava(tmp_path, peer_ix())
    resposta = api.post("/api/peers", json=CLIENTE)
    assert resposta.status_code == 201, resposta.text
    assert (tmp_path / "out" / str(ASN_DE_TESTE)
            / "268127-cliente.txt").exists()
    assert [p.token for p in peers_mod.carregar(caminho_tenant(tmp_path))] == [
        "IX-SP", "268127"]


def test_o_segundo_link_do_mesmo_cliente_e_aceito(api):
    """O caso que o operador nao conseguia cadastrar, pela API.

    O cliente com link principal e backup tem dois peers com o mesmo ASN, e
    os dois anunciam os mesmos blocos: o mesmo cliente, o mesmo espaco. A
    recusa vinha da sobreposicao de prefixo, que comparava todo peer
    downstream com todo outro sem olhar de quem era o bloco.

    O apelido e obrigatorio aqui: sem ele o token seria o ASN, e dois peers
    com o mesmo ASN colidiriam no nome do objeto - que e outra regra, e
    continua valendo.
    """
    assert api.post("/api/peers", json=CLIENTE).status_code == 201
    backup = dict(CLIENTE, apelido="ACME-BKP", id="",
                  sessao_v4_local="198.51.100.9", sessao_v4_remoto="198.51.100.10")
    r = api.post("/api/peers", json=backup)
    assert r.status_code == 201, r.text
    assert r.json()["registro"]["token"] == "ACME-BKP"


def test_o_bloco_de_outro_cliente_continua_recusado(api):
    """A dispensa pelo mesmo ASN nao afrouxou a regra do caso oposto.

    Dois clientes, dois ASNs, o mesmo bloco: e conflito, e o segundo
    cadastro tem que continuar sendo recusado.
    """
    assert api.post("/api/peers", json=CLIENTE).status_code == 201
    outro = dict(CLIENTE, asn="268128", apelido="OUTRO", id="",
                 sessao_v4_local="198.51.100.9", sessao_v4_remoto="198.51.100.10")
    r = api.post("/api/peers", json=outro)
    assert r.status_code == 422
    assert "sobrepoe" in r.json()["erros"]["prefixos"]


def test_criar_o_segundo_link_reaproveitando_o_primeiro(api, tmp_path):
    """O caminho de ponta a ponta do recurso, pela API.

    O bloco do segundo link nao define objeto nenhum e chama os filtros do
    primeiro, que continuam saindo no bloco dele.
    """
    assert api.post("/api/peers", json=CLIENTE).status_code == 201
    backup = dict(CLIENTE, apelido="ACME-BKP", id="", politica_de="0",
                  sessao_v4_local="198.51.100.9", sessao_v4_remoto="198.51.100.10")
    r = api.post("/api/peers", json=backup)
    assert r.status_code == 201, r.text

    texto = (tmp_path / "out" / str(ASN_DE_TESTE) / "ACME-BKP-cliente.txt").read_text("ascii")
    assert "xpl " not in texto
    assert "route-filter CUST-268127-IMPORT-V4 import" in texto


def test_excluir_a_origem_e_recusado_enquanto_alguem_a_reaproveita(api, tmp_path):
    # apagar a origem deixaria o bloco do outro apontando para filtros que
    # nao existem mais no equipamento
    api.post("/api/peers", json=CLIENTE)
    api.post("/api/peers", json=dict(CLIENTE, apelido="ACME-BKP", id="",
                                     politica_de="0",
                                     sessao_v4_local="198.51.100.9",
                                     sessao_v4_remoto="198.51.100.10"))
    r = api.delete("/api/peers/0")
    assert r.status_code == 422
    assert "reaproveita" in r.json()["erros"]["_"]
    # e o bloco do segundo continua onde estava
    assert (tmp_path / "out" / str(ASN_DE_TESTE) / "ACME-BKP-cliente.txt").exists()


def test_a_previa_de_quem_reaproveita_tambem_nao_tem_objeto(api):
    api.post("/api/peers", json=CLIENTE)
    # o segundo link tem os enderecos dele: o da origem ja esta em uso, e o
    # validate recusa a sessao repetida antes de qualquer render
    r = api.post("/api/peers/previa",
                 json=dict(CLIENTE, apelido="ACME-BKP", id="", politica_de="0",
                           sessao_v4_local="198.51.100.9",
                           sessao_v4_remoto="198.51.100.10"))
    assert r.status_code == 200
    assert "xpl " not in r.json()["bloco"]
    # o quadro "ao criar" e da origem: null, e nao a string vazia que o
    # render devolveria se a condicao do _criar_lista_do_peer so olhasse o
    # tipo
    assert r.json()["criar_lista"] is None


def test_a_origem_de_outro_tipo_ou_asn_editada_a_mao_e_recusada(api, tmp_path):
    """A irma da origem apagada, para a referencia que resolve torto.

    O arquivo do tenant editado a mao pode apontar o `politica_de` para um
    peer de outro tipo ou de outro ASN. O par tipo/ASN e a politica: o nome
    dos filtros sai do token da origem, e a lista de prefixos, o AP-CUST e
    as large por ASN sao por tipo e por ASN. O bloco sairia com a sessao
    apontando para filtros que nao existem, e num cliente a sessao sem
    filtro tambem e a sessao sem restricao nenhuma no import - pior do que
    a recusa que a rota ja da para a origem que nao existe.

    Os dois peers tortos entram direto no arquivo, cada um com o seu erro: o
    primeiro troca o tipo, o segundo o ASN. O validate recusa os dois no
    salvar, e a leitura que renderiza sem validar e o /saida, que devolve o
    422 pela segunda barreira.
    """
    api.post("/api/peers", json=CLIENTE)
    caminho = caminho_tenant(tmp_path)
    texto = caminho.read_text("utf-8")
    caminho.write_text(texto.replace(
        "peers:", "peers:\n- id: 40\n  apelido: TORTO\n  nome: TORTO\n"
        "  tipo: upstream\n  asn: 268127\n  politica_de: 0\n"
        "  descricao: TORTO\n- id: 41\n  apelido: OUTRO-ASN\n"
        "  nome: OUTRO-ASN\n  tipo: cliente\n  asn: 268128\n"
        "  politica_de: 0\n  descricao: OUTRO-ASN\n", 1), "utf-8")

    r = api.get("/api/peers/40/saida")
    assert r.status_code == 422
    assert r.json()["erros"]["politica_de"] == (
        "o peer de origem e cliente do ASN 268127, e este e upstream do ASN "
        "268127")

    r = api.get("/api/peers/41/saida")
    assert r.status_code == 422
    assert r.json()["erros"]["politica_de"] == (
        "o peer de origem e cliente do ASN 268127, e este e cliente do ASN "
        "268128")


def test_a_origem_apagada_a_mao_e_recusada_com_erro_claro(api, tmp_path):
    """A segunda barreira, para o arquivo editado por fora.

    O `politica_de` apontando para um id que nao existe e recusado pela
    validacao, mas o arquivo do tenant pode chegar torto por edicao a mao.
    O template roda com StrictUndefined: uma origem nula estoura ali dentro
    com um erro que nao diz nada a quem le. O que a API faz e recusar antes,
    com o nome do campo.

    A leitura que renderiza sem validar e o /saida, e e ele que devolve o
    422. A previa passa pelo validate, que ja escreve no campo o erro de
    origem que nao existe: a rota sai pelo caminho de sempre, 200 e sem
    bloco, como faz com qualquer outro campo.
    """
    api.post("/api/peers", json=CLIENTE)
    caminho = caminho_tenant(tmp_path)
    texto = caminho.read_text("utf-8")
    # o peer torto entra no arquivo direto, apontando para um id que nao existe
    caminho.write_text(texto.replace(
        "peers:", "peers:\n- id: 40\n  apelido: TORTO\n  nome: TORTO\n"
        "  tipo: cliente\n  asn: 268127\n  politica_de: 99\n"
        "  descricao: TORTO\n", 1), "utf-8")

    r = api.get("/api/peers/40/saida")
    assert r.status_code == 422
    assert "politica_de" in r.json()["erros"]

    r = api.post("/api/peers/previa",
                 json=dict(CLIENTE, id="40", apelido="TORTO", politica_de="99"))
    assert r.status_code == 200
    assert "politica_de" in r.json()["erros"]
    assert r.json()["bloco"] is None


def test_a_linha_tratada_atravessa_o_post_e_a_volta(api, tmp_path):
    r = api.post("/api/peers", json=dict(
        CLIENTE, prefixos_v4=["45.169.232.0/22 64512:210 64512:5070"]))
    assert r.status_code == 201, r.text
    peer = peers_mod.carregar(caminho_tenant(tmp_path))[0]
    assert peer.prefixos["v4"][0].communities == ["64512:210", "64512:5070"]
    assert r.json()["registro"]["formulario"]["prefixos_v4"] == [
        "45.169.232.0/22 64512:210 64512:5070"]


def test_a_linha_com_intervalo_atravessa_o_post_e_a_volta(api, tmp_path):
    r = api.post("/api/peers", json=dict(
        CLIENTE, prefixos_v4=["138.97.60.0/22-24 64512:210"]))
    assert r.status_code == 201, r.text
    peer = peers_mod.carregar(caminho_tenant(tmp_path))[0]
    assert peer.prefixos["v4"][0].ate == 24
    assert r.json()["registro"]["formulario"]["prefixos_v4"] == [
        "138.97.60.0/22-24 64512:210"]


def test_o_fora_de_servico_volta_com_o_menos_na_frente(api, tmp_path):
    r = api.post("/api/peers", json=dict(
        CLIENTE, prefixos_v4=["!- 45.169.232.0/22 64512:210"]))
    assert r.status_code == 201, r.text
    assert r.json()["registro"]["formulario"]["prefixos_v4"] == [
        "!- 45.169.232.0/22 64512:210"]
    peer = peers_mod.carregar(caminho_tenant(tmp_path))[0]
    assert peer.prefixos["v4"][0].ativo is False


def test_a_saida_recusa_tabela_invalida_do_yaml(api, tmp_path):
    _grava(tmp_path, peer_cliente(tabela="PARCIAL"))
    r = api.get("/api/peers/1/saida")
    assert r.status_code == 422
    assert "tabela" in r.json()["erros"]


def test_a_saida_nao_recusa_a_tabela_ignorada_do_membro(api, tmp_path):
    # o membro carrega a tabela gravada, mas quem define o export e o grupo
    peers_mod.gravar_grupos(
        [peers_mod.Grupo(id=3, nome="CLIENTES", tipo="cliente", classe="transito",
                         origem=1100, pop=2001)], caminho_tenant(tmp_path))
    _grava(tmp_path, peer_cliente(tabela="", grupo_id=3))
    assert api.get("/api/peers/1/saida").status_code == 200


def test_put_sem_tabela_preserva_a_do_cadastro(api, tmp_path):
    # o cliente antigo recebe full; uma integracao que nao conhece o campo
    # atualiza a descricao e nao pode tirar a tabela dele
    _grava(tmp_path, peer_cliente(id=0, tabela="full"))
    r = api.put("/api/peers/0", json=dict(CLIENTE, descricao="NOVA"))
    assert r.status_code == 200, r.text
    assert peers_mod.carregar(caminho_tenant(tmp_path))[0].tabela == "full"
