"""O login: o arquivo de usuarios, a senha e a sessao.

O bootstrap e o caminho de verdade do admin, entao os testes o chamam
direto (e nao pelo lifespan do app): quem exercita o lifespan e a fixture
`api` do conftest.
"""

import stat

import pytest

from app import auth

SENHA = "senha-de-teste"


@pytest.fixture
def caminho(tmp_path, monkeypatch):
    """O usuarios.yaml em tmp_path, com a senha de teste no ambiente."""
    monkeypatch.setattr(auth, "USUARIOS_YAML", tmp_path / "usuarios.yaml")
    monkeypatch.setenv("BGPGEN_ADMIN_SENHA", SENHA)
    return tmp_path / "usuarios.yaml"


def test_o_boot_cria_o_admin_e_imprime_a_senha(caminho, capsys):
    senha = auth.bootstrap()

    assert senha == SENHA
    assert "senha: %s" % SENHA in capsys.readouterr().out
    assert auth.conferir(auth.NOME_ADMIN, SENHA)


def test_o_boot_sem_a_variavel_sorteia_a_senha(caminho, monkeypatch, capsys):
    monkeypatch.delenv("BGPGEN_ADMIN_SENHA")

    senha = auth.bootstrap()

    assert len(senha) >= 16
    assert senha in capsys.readouterr().out
    assert auth.conferir(auth.NOME_ADMIN, senha)


def test_o_boot_com_usuario_nao_toca_no_arquivo(caminho, capsys):
    auth.bootstrap()
    antes = caminho.read_bytes()
    capsys.readouterr()

    assert auth.bootstrap() is None
    assert caminho.read_bytes() == antes
    assert capsys.readouterr().out == ""


def test_o_boot_com_arquivo_vazio_cria_o_admin(caminho):
    # arquivo de zero byte e o mesmo caso do arquivo ausente: nao ha usuario
    caminho.write_text("")

    assert auth.bootstrap() == SENHA
    assert auth.conferir(auth.NOME_ADMIN, SENHA)


def test_o_arquivo_nasce_so_para_o_dono(caminho):
    auth.bootstrap()

    modo = stat.S_IMODE(caminho.stat().st_mode)
    assert modo == 0o600, oct(modo)


def test_a_senha_certa_confere_e_a_errada_nao(caminho):
    auth.bootstrap()

    assert auth.conferir(auth.NOME_ADMIN, SENHA)
    assert not auth.conferir(auth.NOME_ADMIN, "outra")
    assert not auth.conferir(auth.NOME_ADMIN, "")


def test_usuario_que_nao_existe_nao_confere(caminho):
    auth.bootstrap()

    assert not auth.conferir("ninguem", SENHA)


def test_o_hash_nao_guarda_a_senha(caminho):
    auth.bootstrap()

    assert SENHA not in caminho.read_text(encoding="utf-8")


def test_o_boot_de_um_segundo_app_acha_o_admin_do_primeiro(caminho):
    auth.bootstrap()
    dados = auth.carregar()

    assert dados["segredo"]
    assert set(dados["usuarios"]) == {auth.NOME_ADMIN}
    assert dados["usuarios"][auth.NOME_ADMIN]["n"] == auth.SCRYPT_N


def test_o_boot_sem_poder_gravar_falha(tmp_path, monkeypatch):
    """Volume somente leitura: um app que sobe aberto e pior que um que nao sobe.
    """
    travado = tmp_path / "travado"
    travado.mkdir()
    monkeypatch.setattr(auth, "USUARIOS_YAML", travado / "usuarios.yaml")
    monkeypatch.setenv("BGPGEN_ADMIN_SENHA", SENHA)
    travado.chmod(0o500)
    try:
        with pytest.raises(OSError):
            auth.bootstrap()
    finally:
        # sem devolver a permissao, o tmp_path nao pode ser limpo no fim do caso
        travado.chmod(0o700)
