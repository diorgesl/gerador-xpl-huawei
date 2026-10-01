"""A config inteira numa resposta so: base, originacao, grupos e peers."""

import re

from dados_api import (ASN_DE_TESTE, BLOCOS, CLIENTE, GRUPO_PARCEIROS,
                       GRUPO_UPSTREAM, arvore, caminho_tenant, membro_de)


def _chaves(api):
    return [s["chave"] for s in api.get("/api/config").json()["secoes"]]


def _secoes(api):
    return {s["chave"]: s for s in api.get("/api/config").json()["secoes"]}


def _organizada(api):
    return {s["chave"]: s for s in api.get("/api/config/organizada").json()["secoes"]}


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


def test_o_grupo_de_upstream_traz_o_quadro_ao_criar(api):
    """O export do grupo chama `APPLY-PEER-<G>`, e quem define esse filtro e o
    quadro "ao criar" do grupo. Sem ele na config inteira, o arquivo do
    "baixar tudo" sai com a chamada pendurada, e o equipamento recusa a
    colagem. O peer ja entra com o quadro dele; o grupo de upstream tambem."""
    ident = _criar(api, "/api/grupos", GRUPO_UPSTREAM)
    saida = api.get("/api/grupos/%d/saida" % ident).json()
    secao = _secoes(api)["grupo-%d" % ident]
    assert saida["criar_lista"]
    assert secao["texto"] == saida["bloco"] + "\n\n" + saida["criar_lista"]


def test_nenhum_filtro_e_chamado_sem_definicao(api):
    """A config inteira tem que se sustentar sozinha: um `call route-filter`
    sem o `xpl route-filter` do outro lado so estoura no equipamento. Era o
    caso do grupo de upstream, cujo export chamava o APPLY-PEER do grupo que
    o quadro "ao criar" define e a config nao trazia."""
    api.put("/api/blocos", json=BLOCOS)
    _criar(api, "/api/grupos", GRUPO_UPSTREAM)
    _criar(api, "/api/peers", CLIENTE)

    texto = "\n\n".join(s["texto"] for s in api.get("/api/config").json()["secoes"])
    definidos = set(re.findall(r"^xpl route-filter (\S+)", texto, re.M))
    chamados = set(re.findall(r"^ +call route-filter (\S+)$", texto, re.M))
    assert chamados
    assert chamados <= definidos, sorted(chamados - definidos)


def test_a_config_organizada_junta_tudo_por_tipo(api):
    """O arquivo do "baixar tudo": os sets, os filtros, as estaticas e um `bgp`
    so, na ordem em que o equipamento le - e nao na ordem dos registros."""
    api.put("/api/blocos", json=BLOCOS)
    grupo = _criar(api, "/api/grupos", GRUPO_PARCEIROS)
    membro = _criar(api, "/api/peers", membro_de(grupo))

    secoes = _organizada(api)

    assert list(secoes) == ["sets", "filtros", "estaticas", "bgp"]
    assert secoes["bgp"]["titulo"] == "bgp %d" % ASN_DE_TESTE
    assert "xpl ip-prefix-list PL-BOGONS-V4" in secoes["sets"]["texto"]
    assert "xpl route-filter IMPORT-SANITY-V4" in secoes["filtros"]["texto"]
    assert "ip route-static 38.252.64.0" in secoes["estaticas"]["texto"]

    bgp = secoes["bgp"]["texto"]
    assert bgp.splitlines().count("bgp %d" % ASN_DE_TESTE) == 1
    assert bgp.splitlines().count(" ipv4-family unicast") == 1
    # o cabecalho do membro viaja colado no primeiro objeto da secao dele, que
    # e o export por ASN do grupo sem ASN: e ele que diz de quem sao os
    # objetos, e a sessao do membro fica no `bgp` pelo `group`
    assert "# peer %d - parceiro - AS268127" % membro in secoes["filtros"]["texto"]
    assert "call route-filter CUST-PARCEIROS_CDN-EXPORT-V4" in secoes["filtros"]["texto"]
    assert "peer 198.51.100.2 group PARCEIROS_CDN" in bgp
    # e o grupo vem antes de quem herda dele, como na ordem de colagem: sem
    # isso o `peer ... group` do membro referencia um grupo que ainda nao existe
    assert bgp.index("group PARCEIROS_CDN external") < bgp.index(
        "peer 198.51.100.2 group PARCEIROS_CDN")


def test_a_config_organizada_exige_sessao(api_anonimo):
    assert api_anonimo.get("/api/config/organizada").status_code == 401


def test_a_config_organizada_recusa_o_grupo_que_saiu(api, tmp_path):
    """E a mesma montagem do /config, com as mesmas recusas: o arquivo
    organizado nao pode ser a porta por onde passa uma config que a tela
    recusou."""
    _criar(api, "/api/peers", CLIENTE)
    yaml = caminho_tenant(tmp_path)
    yaml.write_text(yaml.read_text(encoding="ascii").replace(
        "grupo_id: null", "grupo_id: 7"), encoding="ascii")
    r = api.get("/api/config/organizada")
    assert r.status_code == 422
    assert r.json()["erros"]["grupo_id"] == "o grupo 7 do peer Cliente ACME nao existe"


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
