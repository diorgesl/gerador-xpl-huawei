"""Gerar o peer B nao pode mexer na saida do peer A."""

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import app as servidor
from app import auth
from app import peers as mod
from app import prefixes, render


def faz(apelido, ident, asn, **kw):
    """Um peer com nome de objeto escolhido a dedo.

    O token e o ASN, e o ASN sozinho nao da nome legivel para comparar
    saida de um peer contra a do outro. O apelido entra no lugar dele e
    deixa cada fixture com um nome que o teste consegue citar.
    """
    base = dict(
        id=ident, apelido=apelido, nome=apelido, tipo="cliente", asn=asn,
        classe="transito", descricao="%s-AS%d" % (apelido, asn),
        lp_base=300, origem=1100, pop=2001,
        prefixos={"v4": ["45.169.%d.0/24" % ident], "v6": []},
        prepend_base=0, route_limit=50,
        sessoes={"v4": {"local": "198.51.100.1",
                        "remoto": "198.51.%d.2" % ident}, "v6": {}},
    )
    base.update(kw)
    return mod.Peer(**base)


@pytest.fixture
def out(tmp_path, monkeypatch):
    # patch dos dois OUT: escrever_peer faz o mkdir com render.OUT, e o caminho do arquivo sai de peers.OUT via peer.arquivo(); patchando so um, o out/ do repo e tocado
    monkeypatch.setattr(mod, "OUT", tmp_path)
    monkeypatch.setattr(render, "OUT", tmp_path)
    return tmp_path


def test_gerar_b_nao_muda_a_saida_de_a(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)

    render.escrever_peer(a)
    primeira = a.arquivo().read_text(encoding="ascii")

    render.escrever_peer(b)
    render.escrever_peer(a)
    assert a.arquivo().read_text(encoding="ascii") == primeira


def test_gerar_b_nao_toca_no_mtime_de_a(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)
    render.escrever_peer(a)
    mtime = a.arquivo().stat().st_mtime_ns
    render.escrever_peer(b)
    assert a.arquivo().stat().st_mtime_ns == mtime


def test_a_saida_de_a_nao_menciona_b(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)
    render.escrever_peer(b)
    texto = render.render_peer(a)
    assert "CLIENTEB" not in texto
    assert "64501" not in texto
    assert "198.51.2.2" not in texto


def test_cada_peer_grava_no_proprio_arquivo(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)
    render.escrever_peer(a)
    render.escrever_peer(b)
    assert a.arquivo().name == "CLIENTEA-cliente.txt"
    assert b.arquivo().name == "CLIENTEB-cliente.txt"
    assert a.arquivo().read_text() != b.arquivo().read_text()


def test_gerar_um_peer_nao_cria_arquivo_alheio(out):
    render.escrever_peer(faz("CLIENTEA", 1, 64500))
    render.escrever_peer(faz("CLIENTEB", 2, 64501))
    assert sorted(p.name for p in out.iterdir()) == [
        "CLIENTEA-cliente.txt", "CLIENTEB-cliente.txt"]


def test_o_bloco_base_nao_depende_de_peer_nenhum(out):
    vazio = render.render_base()

    render.escrever_peer(faz("CLIENTEA", 1, 64500))
    depois_de_a = render.render_base()

    render.escrever_peer(faz("CLIENTEB", 2, 64501))
    depois_de_b = render.render_base()

    assert depois_de_a == vazio
    assert depois_de_b == vazio


def test_a_ordem_de_gravacao_nao_importa(out):
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)

    render.escrever_peer(a)
    render.escrever_peer(b)
    ab = (a.arquivo().read_text(encoding="ascii"),
          b.arquivo().read_text(encoding="ascii"))

    render.escrever_peer(b)
    render.escrever_peer(a)
    ba = (a.arquivo().read_text(encoding="ascii"),
          b.arquivo().read_text(encoding="ascii"))

    assert ab == ba


def test_os_tipos_nao_dividem_arquivo(out):
    # mesmo apelido, tipos diferentes: arquivos distintos, sem sobrescrita
    c = faz("PARCEIRO", 1, 64500, tipo="cliente")
    u = faz("PARCEIRO", 2, 64501, tipo="upstream", classe=None,
            aprendizado=3100, prefixos={"v4": [], "v6": []})
    render.escrever_peer(c)
    render.escrever_peer(u)
    assert c.arquivo().name == "PARCEIRO-cliente.txt"
    assert u.arquivo().name == "PARCEIRO-upstream.txt"
    assert c.arquivo().read_text(encoding="ascii") == render.render_peer(c)


def test_gerar_um_peer_de_cada_tipo_nao_mistura_nada(out):
    gente = [
        faz("CLIENTEA", 1, 64500),
        faz("UPSTREAMX", 2, 64502, tipo="upstream", classe=None,
            aprendizado=3100, prefixos={"v4": [], "v6": []}),
        faz("IXY", 3, 64503, tipo="ix", classe=None, aprendizado=3010,
            ix_id=1234, prefixos={"v4": [], "v6": []}),
        faz("PNIZ", 4, 64504, tipo="pni", classe=None,
            prefixos={"v4": [], "v6": []}, ap_allowed=["64504"]),
    ]
    for p in gente:
        render.escrever_peer(p)
    for p in gente:
        texto = p.arquivo().read_text(encoding="ascii")
        for outro in gente:
            if outro is p:
                continue
            assert outro.token not in texto, (p.token, outro.token)


def test_o_peers_yaml_guarda_os_dois_sem_perder_nada(tmp_path):
    caminho = tmp_path / "peers.yaml"
    a, b = faz("CLIENTEA", 1, 64500), faz("CLIENTEB", 2, 64501)
    mod.gravar([a, b], caminho)
    lido = mod.carregar(caminho)
    assert [p.token for p in lido] == ["CLIENTEA", "CLIENTEB"]
    assert lido == [a, b]


# O grupo e o membro sao arquivos distintos: o membro herda a politica do
# grupo na hora de renderizar, e nao no arquivo. Mexer num nao pode mexer
# no outro, nem mexer num membro pode mexer no vizinho de grupo. A
# propriedade nao tem nada de downstream - os dois alvos tem arquivo proprio
# nos cinco tipos, e o par grupo/membro e o mesmo objeto -, entao a varredura
# e pelos cinco.

TIPOS = ("cliente", "parceiro", "upstream", "ix", "pni")


def grupo_e_membro(tipo, nome="PARCEIROS_CDN", ident=0, **kw):
    """O par grupo/membro de um dos cinco tipos, com os campos que o template
    de cada um le: o IX precisa do ix_id, o upstream do ponto de aprendizado
    3xxx, o PNI da propria allowlist. O membro nasce sem override nenhum -
    quem precisa de um passa pelo kw.
    """
    campos = dict(id=ident, nome=nome, tipo=tipo, lp_base=300, origem=1100,
                  pop=2001)
    if tipo in ("cliente", "parceiro"):
        campos["classe"] = "transito"
    if tipo == "upstream":
        # o ASN do grupo so e obrigatorio nos tres tipos novos: e ele que
        # entra na LC-NOADV e no 5PPA, e o grupo de downstream o deixa vazio
        # de proposito (o ASN e do membro)
        campos["asn"] = 14840
        campos["aprendizado"] = 3100
    if tipo == "ix":
        campos["asn"] = 26162
        campos["ix_id"] = 1234
        campos["aprendizado"] = 3200
    if tipo == "pni":
        campos["asn"] = 264130
    grupo = mod.Grupo(**campos)

    membro = dict(id=ident + 1, nome="EXEMPLO", tipo=tipo, asn=264130,
                  grupo_id=ident, descricao="EXEMPLO",
                  sessoes={"v4": {"local": "192.0.2.2",
                                  "remoto": "192.0.2.3"},
                           "v6": {}})
    if tipo == "upstream":
        membro["aprendizado"] = 3100
    if tipo == "ix":
        membro["ix_id"] = 1234
        membro["aprendizado"] = 3200
    membro.update(kw)
    return grupo, mod.Peer(**membro)


def test_gerar_grupo_nao_muda_saida_de_peer_membro(out):
    for tipo in TIPOS:
        grupo, membro = grupo_e_membro(tipo)
        render.escrever_grupo(grupo)
        antes = render.escrever_peer(membro, grupo=grupo).read_text(
            encoding="ascii")

        # o mesmo grupo regerado com outro conteudo: nem assim o arquivo do
        # membro muda
        render.escrever_grupo(replace(grupo, lp_base=250, origem=1110,
                                      pop=2002))

        depois = membro.arquivo().read_text(encoding="ascii")
        assert antes == depois, tipo


def test_gerar_peer_membro_nao_muda_saida_do_grupo(out):
    for tipo in TIPOS:
        grupo, membro = grupo_e_membro(tipo)
        antes = render.escrever_grupo(grupo).read_text(encoding="ascii")

        render.escrever_peer(membro, grupo=grupo)

        depois = grupo.arquivo().read_text(encoding="ascii")
        assert antes == depois, tipo


def test_gerar_um_membro_nao_muda_outro_membro(out):
    for tipo in TIPOS:
        grupo, a = grupo_e_membro(tipo)
        b = mod.Peer(id=a.id + 1, nome="B", tipo=tipo, asn=264131,
                     grupo_id=grupo.id, descricao="B",
                     prefixos={"v4": ["198.51.100.0/24"], "v6": []},
                     classe="transito", origem=1100, pop=2001,
                     # os campos que so o tipo novo usa vem do a, que nasceu
                     # pelo mesmo caminho: sem eles o render do membro de
                     # upstream e do de ix para no ponto de aprendizado e no
                     # ix_id, e nao no override deste teste
                     aprendizado=a.aprendizado, ix_id=a.ix_id,
                     sessoes={"v4": {"local": "10.0.1.1", "remoto": "10.0.1.2"},
                              "v6": {}})
        antes = render.escrever_peer(a, grupo=grupo).read_text(encoding="ascii")
        render.escrever_peer(b, grupo=grupo)  # b tem override, filtro proprio
        depois = a.arquivo().read_text(encoding="ascii")
        assert antes == depois, tipo


def _retrato(raiz):
    """Bytes de cada arquivo sob a raiz, por caminho relativo.

    A exclusao de grupo tem que ser tudo ou nada: ou some o arquivo do
    grupo e mais nada, ou nao muda byte nenhum - nem o yaml, nem a saida
    dos membros, nem a do vizinho.
    """
    return {p.relative_to(raiz): p.read_bytes()
            for p in sorted(raiz.rglob("*")) if p.is_file()}


@pytest.fixture
def cliente(out, usuarios_em_tmp, logar, monkeypatch):
    """O app apontando para o mesmo tmp_path que o `out` ja patcheia, logado.

    A exclusao passa pela rota, entao o peers.yaml tambem tem que sair do
    checkout: sem o patch, a rota leria o arquivo de verdade e o teste
    apagaria o grupo do repositorio. O CACHE do bgpq4 entra junto pelo
    mesmo motivo. O admin nasce do bootstrap, e este cliente nao roda o
    lifespan (nao ha context manager): por isso a chamada explicita.
    """
    auth.bootstrap()
    monkeypatch.setattr(mod, "PEERS_YAML", out / "peers.yaml")
    monkeypatch.setattr(prefixes, "CACHE", out / ".cache")
    return logar(TestClient(servidor.app))


def test_excluir_grupo_com_membro_e_recusado_sem_tocar_em_arquivo(out, cliente):
    grupo = mod.Grupo(id=0, nome="PARCEIROS_CDN", tipo="cliente",
                      classe="transito", lp_base=300, origem=1100, pop=2001)
    a = faz("CLIENTEA", 1, 64500, grupo_id=grupo.id)
    b = faz("CLIENTEB", 2, 64501, grupo_id=grupo.id)
    mod.gravar_grupos([grupo], out / "peers.yaml")
    mod.gravar([a, b], out / "peers.yaml")
    render.escrever_grupo(grupo)
    render.escrever_peer(a, grupo=grupo)
    render.escrever_peer(b, grupo=grupo)
    antes = _retrato(out)

    r = cliente.delete("/api/grupos/%d" % grupo.id)

    assert r.status_code == 409
    assert "CLIENTEA" in r.json()["erros"]["membros"]
    assert "CLIENTEB" in r.json()["erros"]["membros"]
    assert [g.nome for g in mod.carregar_grupos(out / "peers.yaml")] == [
        "PARCEIROS_CDN"]
    # a recusa nao pode deixar rastro: nem o yaml, nem a saida do grupo,
    # nem a dos membros mudam de byte
    assert _retrato(out) == antes

    # os membros saem do grupo por fora (nao ha tela para isso ainda, ver
    # "Fora do escopo deste plano" do plano): so entao a exclusao passa
    mod.gravar([], out / "peers.yaml")
    antes = _retrato(out)

    r = cliente.delete("/api/grupos/%d" % grupo.id)

    assert r.status_code == 204
    assert mod.carregar_grupos(out / "peers.yaml") == []
    agora = _retrato(out)
    sumiu = set(antes) - set(agora)
    assert sumiu == {Path("grupo-PARCEIROS_CDN.txt")}
    assert set(agora) - set(antes) == set()
    # so o yaml muda de conteudo, e so para perder a entrada do grupo: a
    # saida dos membros fica no disco, byte a byte, para o operador recolher
    for caminho, conteudo in antes.items():
        if caminho in sumiu or caminho == Path("peers.yaml"):
            continue
        assert agora[caminho] == conteudo
