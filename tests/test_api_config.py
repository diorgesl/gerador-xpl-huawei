"""A config inteira numa resposta so: base, originacao, grupos e peers."""

from dados_api import (ASN_DE_TESTE, BLOCOS, CLIENTE, GRUPO_PARCEIROS, arvore,
                       caminho_tenant)


def _chaves(api):
    return [s["chave"] for s in api.get("/api/config").json()["secoes"]]


def _secoes(api):
    return {s["chave"]: s for s in api.get("/api/config").json()["secoes"]}


def _criar(api, rota, formulario):
    r = api.post(rota, json=formulario)
    assert r.status_code == 201, r.text
    return r.json()["registro"]["id"]


def test_a_config_vazia_e_so_o_bloco_base(api):
    """Sem peer, sem grupo e sem bloco proprio, so o base tem o que dizer.

    O texto e o mesmo do /base.txt, e nao uma copia: sao a mesma funcao do
    render, e o teste prende as duas pontas.
    """
    assert api.get("/api/config").json() == {
        "secoes": [{
            "chave": "base",
            "titulo": "Bloco base",
            "texto": api.get("/base.txt").text,
            "arquivo": None,
            "salvo": None,
        }]}


def test_ler_a_config_nao_escreve_nada(api, tmp_path):
    antes = arvore(tmp_path)
    assert api.get("/api/config").status_code == 200
    assert arvore(tmp_path) == antes


def test_a_config_exige_sessao(api_anonimo):
    assert api_anonimo.get("/api/config").status_code == 401


def test_o_peer_traz_o_bloco_o_criar_a_lista_e_o_arquivo_dele(api):
    ident = _criar(api, "/api/peers", CLIENTE)
    saida = api.get("/api/peers/%d/saida" % ident).json()
    secao = _secoes(api)["peer-%d" % ident]
    assert secao["titulo"] == "Cliente ACME (cliente, AS268127)"
    assert secao["texto"] == saida["bloco"] + "\n\n" + saida["criar_lista"]
    assert secao["arquivo"] == saida["arquivo"]
    assert secao["salvo"] is True


def test_o_grupo_traz_o_bloco_e_o_arquivo_dele(api):
    ident = _criar(api, "/api/grupos", GRUPO_PARCEIROS)
    saida = api.get("/api/grupos/%d/saida" % ident).json()
    secao = _secoes(api)["grupo-%d" % ident]
    assert secao["titulo"] == "PARCEIROS_CDN (parceiro)"
    # o grupo nao tem quadro "ao criar": so o bloco, como no /saida dele
    assert secao["texto"] == saida["bloco"]
    assert secao["arquivo"] == saida["arquivo"]
    assert secao["salvo"] is True


def test_a_originacao_traz_o_arquivo_dos_blocos(api):
    salvo = api.put("/api/blocos", json=BLOCOS).json()
    secao = _secoes(api)["originacao"]
    assert secao["titulo"] == "Originacao dos prefixos proprios"
    assert secao["texto"] == salvo["originacao"]
    assert secao["arquivo"] == "blocos.txt"
    assert secao["salvo"] is True


def test_sem_bloco_proprio_nao_ha_secao_de_originacao(api):
    assert "originacao" not in _chaves(api)


def test_a_ordem_e_base_grupos_peers_e_originacao(api):
    """A ordem e a do "Ordem de colagem no F1A" do README: o base primeiro,
    porque e ele que define os sets e os filtros que os outros chamam, e a
    originacao por ultimo, que nao depende de nem sustenta bloco nenhum."""
    api.put("/api/blocos", json=BLOCOS)
    grupo = _criar(api, "/api/grupos", GRUPO_PARCEIROS)
    peer = _criar(api, "/api/peers", CLIENTE)
    assert _chaves(api) == ["base", "grupo-%d" % grupo, "peer-%d" % peer,
                            "originacao"]


def test_o_bloco_sem_arquivo_em_out_vem_marcado(api, tmp_path):
    """O `salvo` responde "isso ja foi gravado", que e o mais perto de "isso
    esta no equipamento" que o app sabe. Sem o arquivo, o bloco na tela e um
    que talvez nunca tenha sido colado."""
    ident = _criar(api, "/api/peers", CLIENTE)
    pasta = tmp_path / "out" / str(ASN_DE_TESTE)
    (pasta / _secoes(api)["peer-%d" % ident]["arquivo"]).unlink()
    assert _secoes(api)["peer-%d" % ident]["salvo"] is False


def test_peer_apontando_para_grupo_que_saiu_recusa_a_config(api, tmp_path):
    """O membro herda o que o grupo define: sem o grupo o bloco sai errado, e
    a config inteira sai junto com ele, como no /saida do peer."""
    _criar(api, "/api/peers", CLIENTE)
    yaml = caminho_tenant(tmp_path)
    yaml.write_text(yaml.read_text(encoding="ascii").replace(
        "grupo_id: null", "grupo_id: 7"), encoding="ascii")
    r = api.get("/api/config")
    assert r.status_code == 422
    assert r.json()["erros"]["grupo_id"] == "o grupo 7 do peer Cliente ACME nao existe"


def test_o_peer_que_reaproveita_sai_na_config_com_os_filtros_da_origem(api):
    """A secao dele e o bloco dele: os filtros da origem, e objeto nenhum.

    E o mesmo render do /saida, e por isso a config tambem precisa da origem
    resolvida: sem ela o bloco de quem reaproveita estourava dentro do
    template, e a config inteira ia junto.
    """
    origem = _criar(api, "/api/peers", CLIENTE)
    backup = _criar(api, "/api/peers", dict(
        CLIENTE, apelido="ACME-BKP", id="", politica_de=str(origem),
        sessao_v4_local="198.51.100.9", sessao_v4_remoto="198.51.100.10"))

    secao = _secoes(api)["peer-%d" % backup]

    assert "xpl " not in secao["texto"]
    assert "route-filter CUST-268127-IMPORT-V4 import" in secao["texto"]


def test_origem_de_quem_reaproveita_que_saiu_recusa_a_config(api, tmp_path):
    """O irmao do grupo que saiu, para a referencia que aponta para o vazio.

    O arquivo do tenant editado a mao deixa o `politica_de` num id que nao
    existe mais, e o template roda com StrictUndefined: sem a recusa aqui, o
    que voltava era o estouro do render, sem dizer o campo.
    """
    _criar(api, "/api/peers", CLIENTE)
    yaml = caminho_tenant(tmp_path)
    yaml.write_text(yaml.read_text(encoding="ascii").replace(
        "politica_de: null", "politica_de: 7"), encoding="ascii")
    r = api.get("/api/config")
    assert r.status_code == 422
    assert r.json()["erros"]["politica_de"] == (
        "peer de origem nao encontrado no cadastro")
