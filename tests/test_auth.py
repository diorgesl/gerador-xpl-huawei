"""O login: o arquivo de usuarios, a senha e a sessao.

O bootstrap e o caminho de verdade do admin, entao os testes o chamam
direto (e nao pelo lifespan do app): quem exercita o lifespan e a fixture
`api` do conftest.
"""

import stat
import time
from types import SimpleNamespace

import pytest
from fastapi import Response

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


def _resposta():
    """Uma Response solta, que e onde o cookie e escrito."""
    return Response()


def _pedido(cookie=None):
    """O minimo que o da_requisicao le de um Request."""
    return SimpleNamespace(cookies={} if cookie is None else {auth.COOKIE: cookie})


def test_o_cookie_aberto_volta_com_o_usuario(caminho):
    auth.bootstrap()
    resposta = _resposta()

    auth.abrir_sessao(resposta, auth.NOME_ADMIN)
    cookie = resposta.headers["set-cookie"]

    assert auth.COOKIE in cookie
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    valor = cookie.split("%s=" % auth.COOKIE, 1)[1].split(";", 1)[0]
    assert auth.da_requisicao(_pedido(valor)) == auth.NOME_ADMIN


def test_o_cookie_de_outro_segredo_nao_vale(caminho):
    auth.bootstrap()
    resposta = _resposta()
    auth.abrir_sessao(resposta, auth.NOME_ADMIN)
    valor = resposta.headers["set-cookie"].split("%s=" % auth.COOKIE, 1)[1].split(";", 1)[0]

    # o operador apagou o usuarios.yaml e o app criou outro, com outro segredo:
    # e assim que se revoga uma sessao aberta
    caminho.unlink()
    auth.criar_admin("outra-senha", caminho)

    assert auth.da_requisicao(_pedido(valor)) is None


def test_o_cookie_com_a_assinatura_torta_nao_vale(caminho):
    auth.bootstrap()
    expira = int(time.time()) + 60
    valor = "%s.%d.%s" % (auth.NOME_ADMIN, expira, "0" * 64)

    assert auth.da_requisicao(_pedido(valor)) is None


def test_o_cookie_vencido_nao_vale(caminho):
    auth.bootstrap()
    dados = auth.carregar()
    expira = int(time.time()) - 1
    valor = "%s.%d.%s" % (auth.NOME_ADMIN, expira,
                          auth.assinatura(auth.NOME_ADMIN, expira, dados["segredo"]))

    assert auth.da_requisicao(_pedido(valor)) is None


def test_o_cookie_sem_os_tres_pedacos_nao_vale(caminho):
    auth.bootstrap()

    assert auth.da_requisicao(_pedido("admin")) is None
    assert auth.da_requisicao(_pedido("admin.123")) is None
    assert auth.da_requisicao(_pedido("")) is None


def test_usuario_com_ponto_no_nome_nao_vira_outro_usuario(caminho):
    auth.bootstrap()
    dados = auth.carregar()
    # um nome com ponto so sobrevive ao rsplit: com um split cru, o usuario
    # lido seria o pedaco errado, e a sessao de "a.b" viraria a de "a"
    expira = int(time.time()) + 60
    valor = "a.b.%d.%s" % (expira, auth.assinatura("a.b", expira, dados["segredo"]))

    assert auth.da_requisicao(_pedido(valor)) == "a.b"


def test_sem_usuarios_yaml_nao_ha_sessao(caminho):
    auth.bootstrap()
    resposta = _resposta()
    auth.abrir_sessao(resposta, auth.NOME_ADMIN)
    valor = resposta.headers["set-cookie"].split("%s=" % auth.COOKIE, 1)[1].split(";", 1)[0]

    caminho.unlink()

    # arquivo ausente e o estado "ninguem entrou ainda", e nao erro de
    # leitura: a sessao antiga nao vale mais, e nada estoura
    assert auth.da_requisicao(_pedido(valor)) is None


def test_usuarios_yaml_sem_segredo_e_erro_com_nome(caminho):
    auth.escrever({"usuarios": {}}, caminho)

    with pytest.raises(ValueError) as erro:
        auth.da_requisicao(_pedido("admin.1.x"))

    assert str(caminho) in str(erro.value)


def test_fechar_sessao_zera_o_cookie(caminho):
    resposta = _resposta()

    auth.fechar_sessao(resposta)

    cookie = resposta.headers["set-cookie"]
    assert "%s=" % auth.COOKIE in cookie
    assert "Max-Age=0" in cookie or "expires" in cookie.lower()


def test_exigir_login_devolve_o_usuario_e_recusa_sem_cookie(caminho):
    auth.bootstrap()
    resposta = _resposta()
    auth.abrir_sessao(resposta, auth.NOME_ADMIN)
    valor = resposta.headers["set-cookie"].split("%s=" % auth.COOKIE, 1)[1].split(";", 1)[0]

    assert auth.exigir_login(_pedido(valor)) == auth.NOME_ADMIN
    with pytest.raises(auth.NaoAutenticado):
        auth.exigir_login(_pedido())


def test_o_cookie_so_vai_com_secure_quando_a_variavel_pede(caminho, monkeypatch):
    auth.bootstrap()

    monkeypatch.delenv("BGPGEN_COOKIE_SEGURO", raising=False)
    sem_variavel = _resposta()
    auth.abrir_sessao(sem_variavel, auth.NOME_ADMIN)
    assert "Secure" not in sem_variavel.headers["set-cookie"]

    monkeypatch.setenv("BGPGEN_COOKIE_SEGURO", "1")
    com_variavel = _resposta()
    auth.abrir_sessao(com_variavel, auth.NOME_ADMIN)
    assert "Secure" in com_variavel.headers["set-cookie"]
