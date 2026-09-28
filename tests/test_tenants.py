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
