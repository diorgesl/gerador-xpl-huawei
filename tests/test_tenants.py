"""A pasta dos tenants: a lista, a criacao e a migracao."""

import pytest

from app import tenants


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    """A pasta de tenants e a de saida num tmp_path.

    O patch e nos modulos, e nao nos caminhos de quem chama: toda funcao do
    tenants le a constante na hora da chamada, como o _yaml() do api.py.
    """
    monkeypatch.setattr(tenants, "PASTA", tmp_path / "peers")
    monkeypatch.setattr(tenants, "SAIDA", tmp_path / "out")
    monkeypatch.setattr(tenants, "ORIGEM", tmp_path / "peers.yaml")
    monkeypatch.setattr(tenants, "BKP", tmp_path / "peers.yaml.bak")
    return tmp_path


def test_a_lista_de_pasta_inexistente_e_vazia(pasta):
    assert tenants.listar() == []


def test_a_lista_traz_os_asns_ordenados(pasta):
    (pasta / "peers").mkdir()
    for nome in ("64512.yaml", "264130.yaml", "999.yaml"):
        (pasta / "peers" / nome).write_text("asn: 0\n")
    assert tenants.listar() == [999, 64512, 264130]


def test_a_lista_ignora_o_que_nao_tem_nome_de_asn(pasta):
    (pasta / "peers").mkdir()
    (pasta / "peers" / "64512.yaml").write_text("asn: 64512\n")
    (pasta / "peers" / "notas.txt").write_text("oi\n")
    (pasta / "peers" / "64512.txt").write_text("oi\n")
    (pasta / "peers" / "backup.yaml.bak").write_text("oi\n")
    (pasta / "peers" / ".DS_Store").write_text("")
    assert tenants.listar() == [64512]


def test_abrir_devolve_o_tenant_com_os_dois_caminhos(pasta):
    (pasta / "peers").mkdir()
    (pasta / "peers" / "64512.yaml").write_text("asn: 64512\n")
    achado = tenants.abrir(64512)
    assert achado.asn == 64512
    assert achado.caminho == pasta / "peers" / "64512.yaml"
    assert achado.saida == pasta / "out" / "64512"


def test_abrir_o_que_nao_existe_e_none(pasta):
    assert tenants.abrir(64512) is None


def test_criar_grava_o_arquivo_com_o_asn_e_a_politica(pasta):
    tenant = tenants.criar(264130, 65532)
    assert tenant.caminho.read_text(encoding="utf-8") == (
        "asn: 264130\nasn_politica: 65532\n")


def test_criar_sem_politica_nao_grava_a_chave(pasta):
    tenant = tenants.criar(64512)
    assert tenant.caminho.read_text(encoding="utf-8") == "asn: 64512\n"


def test_criar_nao_cria_as_listas_vazias(pasta):
    texto = tenants.criar(64512).caminho.read_text(encoding="utf-8")
    assert "peers" not in texto and "grupos" not in texto and "blocos" not in texto


def test_criar_o_que_ja_existe_e_erro(pasta):
    tenants.criar(64512)
    with pytest.raises(ValueError, match="ja tem cadastro"):
        tenants.criar(64512)


def test_criar_asn_de_32_bits_sem_politica_e_erro(pasta):
    with pytest.raises(ValueError, match="nao cabe nos 16 bits"):
        tenants.criar(264130)
    assert not (pasta / "peers" / "264130.yaml").exists()


def test_migrar_sem_peers_yaml_nao_faz_nada(pasta):
    assert tenants.migrar() is None
    assert not (pasta / "peers").exists()


def test_migrar_move_o_arquivo_e_deixa_o_bak(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\npeers: []\n")
    destino = tenants.migrar()
    assert destino == pasta / "peers" / "264130.yaml"
    assert not (pasta / "peers.yaml").exists()
    assert (pasta / "peers.yaml.bak").read_text() == (
        "asn: 264130\nasn_politica: 65532\npeers: []\n")
    # o conteudo atravessa inteiro, e nao so a chave do ASN
    assert destino.read_text() == (pasta / "peers.yaml.bak").read_text()


def test_migrar_usa_o_as_de_fabrica_sem_a_chave(pasta):
    (pasta / "peers.yaml").write_text("peers: []\n")
    assert tenants.migrar() == pasta / "peers" / "64512.yaml"


def test_migrar_leva_os_blocos_da_raiz_do_out(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    (pasta / "out").mkdir()
    (pasta / "out" / "14840-upstream.txt").write_text("bloco\n")
    (pasta / "out" / "blocos.txt").write_text("origem\n")
    tenants.migrar()
    assert (pasta / "out" / "264130" / "14840-upstream.txt").read_text() == "bloco\n"
    assert (pasta / "out" / "264130" / "blocos.txt").read_text() == "origem\n"
    assert not (pasta / "out" / "14840-upstream.txt").exists()


def test_migrar_nao_toca_no_cache_do_bgpq4(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    (pasta / "out" / ".cache").mkdir(parents=True)
    (pasta / "out" / ".cache" / "14840.json").write_text("{}")
    tenants.migrar()
    assert (pasta / "out" / ".cache" / "14840.json").exists()


def test_migrar_nao_sobrescreve_o_que_ja_esta_no_destino(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    (pasta / "out" / "264130").mkdir(parents=True)
    (pasta / "out" / "264130" / "blocos.txt").write_text("novo\n")
    (pasta / "out" / "blocos.txt").write_text("velho\n")
    tenants.migrar()
    assert (pasta / "out" / "264130" / "blocos.txt").read_text() == "novo\n"
    assert (pasta / "out" / "blocos.txt").read_text() == "velho\n"


def test_migrar_nao_sobrescreve_um_tenant_que_ja_existe(pasta):
    (pasta / "peers").mkdir()
    (pasta / "peers" / "264130.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\npeers: []\n")
    assert tenants.migrar() is None
    assert (pasta / "peers.yaml").exists()
    assert not (pasta / "peers.yaml.bak").exists()


def test_migrar_com_destino_ocupado_diz_qual_e_nao_toca_em_nada(
        pasta, capsys, usuarios_em_tmp):
    """O caso do arquivo posto a mao: nada se move e sobra a linha no log.

    O destino ocupado e o unico caminho de falha da migracao que nao deixa
    rastro em arquivo nenhum: nao nasce .bak, o peers.yaml fica onde esta e
    a pasta ja tinha o tenant. Sem a linha o operador fica com o app de pe,
    um ASN plausivel e o cadastro que nao e o dele, sem sinal de que a
    migracao parou.
    """
    from fastapi.testclient import TestClient

    from app import app as mod

    (pasta / "peers").mkdir()
    (pasta / "peers" / "264130.yaml").write_text(
        "asn: 264130\nasn_politica: 65532\n")
    (pasta / "peers.yaml").write_text(
        "asn: 264130\nasn_politica: 65532\npeers: []\n")

    # o boot inteiro, e nao so o migrar(): e ele que engole o None em
    # silencio quando a linha nao existe
    with TestClient(mod.app) as cliente:
        assert cliente.get("/api/sessao").status_code == 200

    saida = capsys.readouterr().out
    assert "nao migrou" in saida
    # a linha nomeia o destino, que e o que colidiu: o caminho do tenant que
    # ja estava la, e nao o do peers.yaml
    assert str(pasta / "peers" / "264130.yaml") in saida
    assert "sem copia em %s" % (pasta / "peers.yaml.bak") in saida
    # e os dois arquivos ficaram exatamente onde estavam, sem .bak
    assert (pasta / "peers.yaml").exists()
    assert (pasta / "peers" / "264130.yaml").read_text() == (
        "asn: 264130\nasn_politica: 65532\n")
    assert not (pasta / "peers.yaml.bak").exists()


def test_migrar_duas_vezes_e_no_op(pasta):
    (pasta / "peers.yaml").write_text("asn: 264130\nasn_politica: 65532\n")
    assert tenants.migrar() is not None
    assert tenants.migrar() is None


def test_migrar_yaml_torto_estoura_e_nao_move_nada(pasta):
    # ASN de 32 bits sem namespace: o mesmo ValueError que hoje estoura na
    # primeira requisicao
    (pasta / "peers.yaml").write_text("asn: 264130\n")
    with pytest.raises(ValueError, match="nao cabe nos 16 bits"):
        tenants.migrar()
    assert (pasta / "peers.yaml").exists()
    assert not (pasta / "peers.yaml.bak").exists()


def test_o_boot_nao_cai_com_peers_yaml_torto(pasta, usuarios_em_tmp):
    """O lifespan roda a migracao e segue de pe, com a lista vazia."""
    from fastapi.testclient import TestClient

    from app import app as mod

    (pasta / "peers.yaml").write_text("asn: 264130\n")
    with TestClient(mod.app) as cliente:
        assert cliente.get("/api/sessao").status_code == 200
    assert tenants.listar() == []
    assert (pasta / "peers.yaml").exists()


def test_o_boot_sobrevive_a_um_yaml_que_nao_parseia(pasta, usuarios_em_tmp):
    """Um yaml torto de sintaxe nao e ValueError nem OSError.

    O safe_load estoura um ParserError, que escaparia de um except estreito e
    deixaria o app num laco de restart do docker por causa de uma virgula. O
    arquivo fica onde esta, sem .bak, e a lista fica vazia.
    """
    from fastapi.testclient import TestClient

    from app import app as mod

    (pasta / "peers.yaml").write_text("asn: [264130\n")
    with TestClient(mod.app) as cliente:
        assert cliente.get("/api/sessao").status_code == 200
    assert tenants.listar() == []
    assert (pasta / "peers.yaml").read_text() == "asn: [264130\n"
    assert not (pasta / "peers.yaml.bak").exists()
