"""As duas rotas que listam e criam tenants."""

from dados_api import ASN_DE_TESTE, CLIENTE


def test_a_lista_traz_o_tenant_de_teste(api):
    assert api.get("/api/asns").json() == [str(ASN_DE_TESTE)]


def test_a_lista_sai_ordenada_e_como_texto(api, tmp_path):
    from app import tenants

    tenants.criar(999)
    tenants.criar(264130, 65532)
    assert api.get("/api/asns").json() == ["999", "64512", "264130"]


def test_a_lista_nao_pede_asn(api):
    assert api.cru.get("/api/asns").status_code == 200


def test_criar_devolve_a_lista_nova(api):
    resposta = api.post("/api/asns", json={"asn": "64513", "politica": ""})
    assert resposta.status_code == 201
    assert resposta.json() == ["64512", "64513"]


def test_criar_grava_o_arquivo_do_tenant(api, tmp_path):
    api.post("/api/asns", json={"asn": "264130", "politica": "65532"})
    assert (tmp_path / "peers" / "264130.yaml").read_text(encoding="utf-8") == (
        "asn: 264130\nasn_politica: 65532\n")


def test_criar_o_que_ja_existe_e_422_no_campo(api):
    resposta = api.post("/api/asns", json={"asn": "64512", "politica": ""})
    assert resposta.status_code == 422
    assert "ja tem cadastro" in resposta.json()["erros"]["asn_rede"]


def test_criar_asn_de_32_bits_sem_namespace_e_422_no_campo(api):
    resposta = api.post("/api/asns", json={"asn": "264130", "politica": ""})
    assert resposta.status_code == 422
    assert "namespace" in resposta.json()["erros"]["asn_politica"]


def test_criar_asn_reservado_e_422(api):
    resposta = api.post("/api/asns", json={"asn": "23456", "politica": ""})
    assert resposta.status_code == 422
    assert "reservado" in resposta.json()["erros"]["asn_rede"]


def test_criar_asn_que_nao_e_numero_e_422(api):
    resposta = api.post("/api/asns", json={"asn": "abc", "politica": ""})
    assert resposta.status_code == 422
    assert "so digitos" in resposta.json()["erros"]["asn_rede"]


def test_criar_sem_asn_e_422_no_campo(api):
    """O campo vazio, que a tela nova manda quando ninguem digitou nada.

    E o caminho que os dois testes apagados na tarefa 3 deixaram sem
    cobertura: com o `asn` fora do RedeForm, o "informe o AS da rede" do
    _asn_do_formulario so tem esta rota para aparecer.
    """
    resposta = api.post("/api/asns", json={"asn": "", "politica": ""})
    assert resposta.status_code == 422
    assert "informe o AS da rede" in resposta.json()["erros"]["asn_rede"]


def test_criar_asn_de_16_bits_sem_namespace_usa_o_proprio(api, tmp_path):
    api.post("/api/asns", json={"asn": "64513", "politica": ""})
    assert (tmp_path / "peers" / "64513.yaml").read_text(encoding="utf-8") == (
        "asn: 64513\n")


def test_dois_tenants_com_o_mesmo_token_nao_se_atropelam(api, tmp_path):
    """O mesmo peer cadastrado em duas redes escreve em duas pastas.

    E o motivo de o out/ ter subido para out/<asn>/: com o out/ plano, o
    bloco de uma rede escreveria por cima do da outra, e o diff da tela
    passaria a comparar contra o bloco de outra rede. O que se perde ali e
    o registro de que aquele bloco ja foi colado no equipamento.

    Os dois blocos nao sao iguais: o namespace das communities e o de cada
    rede, e o mesmo cadastro gera blocos diferentes em cada tenant. O que
    se prova aqui e que cada um saiu na pasta dele.
    """
    from test_render import peer_cliente, peer_ix

    from app import peers as mod

    criado = api.post("/api/asns", json={"asn": "64513", "politica": ""})
    # o segundo tenant nasce da rota, e nao do gravar abaixo: sem esta linha
    # o teste passaria com o POST /api/asns fora do ar, porque quem cria o
    # arquivo seria o gravar
    assert criado.status_code == 201, criado.text
    pasta = tmp_path / "peers"
    # o peer semeado em cada arquivo e de outro token de proposito: com o
    # proprio peer_cliente() que os POSTs cadastram, o validar recusa o token
    # repetido dentro do mesmo tenant (422) e o teste nao chega ao out/
    mod.gravar([peer_ix()], pasta / "64512.yaml")
    mod.gravar([peer_ix()], pasta / "64513.yaml")

    assert api.post("/api/peers", json=CLIENTE).status_code == 201
    assert api.post("/api/peers", json=CLIENTE,
                    params={"asn": 64513}).status_code == 201

    um = tmp_path / "out" / "64512" / "268127-cliente.txt"
    outro = tmp_path / "out" / "64513" / "268127-cliente.txt"
    assert um.exists() and outro.exists()
    assert um.read_text() != outro.read_text()
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()
