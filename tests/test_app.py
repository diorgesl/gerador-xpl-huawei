import json
import os
import re
import time

import pytest
from fastapi.testclient import TestClient

from app import app as mod
from app import peers as peers_mod
from app import plan
from app import prefixes, render

CLIENTE = {
    "apelido": "", "nome": "Cliente ACME", "tipo": "cliente",
    "asn": "268127", "classe": "residencial", "descricao": "CLIENTE-AS268127",
    "lp_base": "300", "origem": "1110", "pop": "2001", "route_limit": "50",
    "bfd": "on", "graceful_restart": "on",
    "prefixos_v4": "45.169.232.0/22", "prefixos_v6": "",
    "sessao_v4_local": "198.51.100.1", "sessao_v4_remoto": "198.51.100.2",
}


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(peers_mod, "PEERS_YAML", tmp_path / "peers.yaml")
    monkeypatch.setattr(peers_mod, "OUT", tmp_path / "out")
    monkeypatch.setattr(render, "OUT", tmp_path / "out")
    monkeypatch.setattr(mod, "PEERS_YAML", tmp_path / "peers.yaml")
    monkeypatch.setattr(mod, "OUT", tmp_path / "out")
    # o CACHE do bgpq4 tambem sai do repositorio: sem o patch, um teste que
    # deixe o coletar rodar de verdade escreve out/.cache/ no checkout
    monkeypatch.setattr(prefixes, "CACHE", tmp_path / "out" / ".cache")
    return TestClient(mod.app)


def salvar(c, dados=None, **kw):
    return c.post("/peer", data=dict(dados or CLIENTE, **kw),
                  follow_redirects=False)


def salvar_editando(c, ident, dados=None, **kw):
    """O POST de um formulario aberto em /peer/<token>.

    A tela manda o id da entrada que esta na frente do operador no campo
    escondido, e e ele que diz qual registro o POST substitui. Sem o
    campo, o POST e um criar, e o validar recusa o ASN repetido.
    """
    return salvar(c, dados, id_original=str(ident), **kw)


def test_a_tela_comeca_vazia(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "nenhum peer" in r.text.lower()


def test_a_tela_tem_lista_e_formulario(cliente):
    # tela unica: lista a esquerda, formulario a direita
    r = cliente.get("/")
    assert 'id="lista"' in r.text
    assert 'id="formulario"' in r.text
    assert 'name="asn"' in r.text
    assert 'name="apelido"' in r.text
    # o token nao tem campo: ele e o ASN, e sai derivado
    assert 'name="token"' not in r.text


def test_salvar_cria_o_peer_e_o_arquivo(cliente, tmp_path):
    r = salvar(cliente)
    assert r.status_code == 303
    assert (tmp_path / "out" / "268127-cliente.txt").exists()
    assert "268127" in cliente.get("/").text


def test_mudar_o_tipo_apaga_o_arquivo_do_tipo_antigo(cliente, tmp_path):
    # dois blocos para a mesma sessao no diretorio de onde o operador cola
    salvar(cliente)
    antigo = tmp_path / "out" / "268127-cliente.txt"
    assert antigo.exists()
    salvar_editando(cliente, 0, tipo="upstream", aprendizado="3000")
    assert not antigo.exists()
    assert (tmp_path / "out" / "268127-upstream.txt").exists()


def test_salvar_com_erro_nao_grava_arquivo(cliente, tmp_path):
    r = salvar(cliente, asn="0")
    assert r.status_code == 200
    assert "ASN reservado" in r.text
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()


# Fix final: a origem em branco. O campo nao vinha preenchido no formulario
# novo e nao tinha default no salvar, e a faixa so confere quando ha valor:
# validava limpo e estourava no render, no "%d". Como o peer e gravado antes
# do render, o estouro levava junto o estado ja salvo.


def test_origem_em_branco_no_salvar_cai_no_default_da_classe(cliente, tmp_path):
    r = salvar(cliente, origem="", classe="cgnat")
    assert r.status_code == 303
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert lido[0].origem == 1130       # ORIGEM_CLASSE["cgnat"]
    texto = (tmp_path / "out" / "268127-cliente.txt").read_text(encoding="ascii")
    assert "64512:1130" in texto


def test_origem_em_branco_no_upstream_cai_no_default_do_tipo(cliente, tmp_path):
    r = salvar(cliente, tipo="upstream", classe="", origem="",
               aprendizado="3100", prefixos_v4="", prefixos_v6="")
    assert r.status_code == 303
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert lido[0].origem == 1400       # ORIGEM["upstream"]
    texto = (tmp_path / "out" / "268127-upstream.txt").read_text(encoding="ascii")
    assert "64512:1400" in texto


def test_origem_digitada_vence_o_default(cliente, tmp_path):
    salvar(cliente, origem="1120", classe="cgnat")
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert lido[0].origem == 1120


def test_o_parceiro_salva_como_cliente_e_sai_com_a_marca(cliente, tmp_path):
    # o caminho inteiro do parceiro: o formulario grava com a classe, a
    # origem em branco cai na classe (e nao na do tipo, que tambem da 1100
    # aqui) e o bloco sai do template do cliente com a marca no import
    r = salvar(cliente, tipo="parceiro", classe="corporativo", origem="")
    assert r.status_code == 303
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert lido[0].tipo == "parceiro"
    assert lido[0].origem == plan.ORIGEM_CLASSE["corporativo"]
    texto = (tmp_path / "out" / "268127-parceiro.txt").read_text(encoding="ascii")
    assert "apply community {64512:1120, 64512:2001, 64512:2091} additive" in texto
    assert "64512:2091" not in texto.split("-EXPORT-V4")[1]


def test_origem_fora_da_faixa_volta_com_erro_na_tela(cliente, tmp_path):
    r = salvar(cliente, origem="1700")
    assert r.status_code == 200
    assert "origem fora da faixa" in r.text     # a mensagem, nao o rotulo do campo
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()


# Fix final: o prefixo de TE do upstream. A checagem de prefixo existia so no
# ramo do cliente, e so sobre `prefixos`: uma entrada sem barra no te_prefixos
# de um upstream validava limpa e estourava no render, com o mesmo estrago do
# caso da origem.


def test_prefixo_de_te_malformado_volta_com_erro_na_tela(cliente, tmp_path):
    r = salvar(cliente, tipo="upstream", classe="", aprendizado="3100",
               prefixos_v4="", prefixos_v6="", te_prefixos_v4="10.0.0.0")
    assert r.status_code == 200
    assert "prefixo invalido: 10.0.0.0" in r.text
    assert not (tmp_path / "out" / "268127-upstream.txt").exists()
    assert peers_mod.carregar(tmp_path / "peers.yaml") == []


def test_prefixo_de_te_valido_salva_normalmente(cliente, tmp_path):
    r = salvar(cliente, tipo="upstream", classe="", aprendizado="3100",
               prefixos_v4="", prefixos_v6="",
               te_prefixos_v4="198.51.100.0/24")
    assert r.status_code == 303
    texto = (tmp_path / "out" / "268127-upstream.txt").read_text(encoding="ascii")
    assert "198.51.100.0 24 le 24" in texto


def test_desmarcar_bfd_chega_no_yaml(cliente, tmp_path):
    dados = dict(CLIENTE)
    dados.pop("bfd")
    salvar(cliente, dados)
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert lido[0].bfd is False
    assert lido[0].graceful_restart is True


def test_a_caixa_da_default_route_nasce_desmarcada_e_chega_no_yaml(cliente, tmp_path):
    assert 'name="default_route"' in cliente.get("/peer/novo").text
    salvar(cliente)
    assert peers_mod.carregar(tmp_path / "peers.yaml")[0].default_route is False
    salvar_editando(cliente, 0, default_route="on")
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert len(lido) == 1
    assert lido[0].default_route is True


def test_o_formulario_deixa_escolher_o_id(cliente, tmp_path):
    # o ID e o PP de 64512:4PP0 e do CL-5PPA-<id>: o operador precisa poder
    # repetir o que o peer ja tem na tabela do PLANO e no equipamento
    salvar(cliente, id="7")
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert lido[0].id == 7
    assert '<input name="id" value="7">' in cliente.get("/peer/268127").text


def test_o_formulario_de_grupo_novo_nao_reusa_o_id_de_um_peer(cliente, tmp_path):
    # o peers.yaml de verdade ja tem essa colisao (peer 0 e grupo 0). O
    # formulario em branco tem que desviar dela, e nao criar mais uma.
    salvar(cliente)
    r = cliente.get("/grupo/novo")
    assert 'name="id" value="1"' in r.text


def test_salvar_grupo_com_id_de_peer_e_recusado(cliente, tmp_path):
    salvar(cliente)
    r = cliente.post("/grupo", data={"nome": "PARCEIROS", "tipo": "parceiro",
                                     "id": "0", "classe": "transito",
                                     "origem": "1100", "pop": "2001"})
    assert "ja usado pelo peer" in r.text


def test_o_formulario_de_um_tipo_novo_vem_com_os_defaults_da_tabela(cliente):
    r = cliente.get("/peer/novo?tipo=upstream")
    assert r.status_code == 200
    assert 'value="1500000"' in r.text          # ROUTE_LIMIT["upstream"]
    assert 'name="timer_keepalive"' in r.text


def test_o_formulario_novo_vem_com_a_origem_da_tabela(cliente):
    # a origem e o default que faltava no formulario em branco, e em branco
    # ela estourava o render depois do peer gravado. O campo virou select
    # preso a tabela do tipo, entao o default agora e a opcao marcada.
    for tipo, esperado in (("cliente", 1100), ("parceiro", 1100),
                           ("upstream", 1400), ("ix", 1300), ("pni", 1500)):
        r = cliente.get("/peer/novo?tipo=%s" % tipo)
        assert '<option value="%d" selected>' % esperado in r.text, tipo
        # e a lista do tipo nao oferece a marca de cliente de outro
        assert ('<option value="1110"' not in r.text
                or tipo in plan.TIPOS_DOWNSTREAM), tipo


def _opcoes(texto, nome):
    bloco = re.search(r'<select name="%s">(.*?)</select>' % nome, texto, re.S)
    return re.findall(r'<option value="([^"]+)"', bloco.group(1))


def _padroes(cliente, tipo="cliente"):
    r = cliente.get("/peer/novo?tipo=%s" % tipo)
    blob = re.search(r'<script id="padroes" type="application/json">(.*?)</script>',
                     r.text, re.S).group(1)
    return r, json.loads(blob)


def test_o_select_de_origem_so_oferece_a_lista_do_tipo(cliente):
    # a origem e vocabulario do plano, nao inventario do operador: por isso
    # e select, e por isso a lista encolhe conforme o tipo. A marca de
    # cliente de outro tipo seria a combinacao sem sentido - 1110 num
    # upstream, por exemplo.
    for tipo in plan.TIPOS:
        r = cliente.get("/peer/novo?tipo=%s" % tipo)
        oferecidas = set(_opcoes(r.text, "origem"))
        permitidas = set(str(c) for c in plan.ORIGENS_POR_TIPO[tipo])
        assert oferecidas == permitidas, (tipo, oferecidas, permitidas)
        assert str(plan.ORIGEM[tipo]) in oferecidas, tipo


def test_o_cliente_e_o_maior_lp_dos_tipos(cliente):
    # o padrao do plano e cliente 300, PNI 200, IX 190, upstream 100. Escolher
    # o tipo no formulario tem que trazer o LP junto: era o caso que faltava,
    # o campo ficava com o valor do tipo anterior. O parceiro empata com o
    # cliente, que e o desenho: por baixo da marca ele e um downstream.
    _, p = _padroes(cliente)
    lps = {t: p["tipos"][t]["lp_base"] for t in plan.TIPOS}
    assert lps == {"cliente": 300, "parceiro": 300, "pni": 200, "ix": 190,
                   "upstream": 100}
    assert lps["cliente"] == max(lps.values())


def test_o_bloco_da_cascata_e_a_tabela_do_plano(cliente):
    # o JS da tela nao pode divergir do plan.py: se um valor mudar la e nao
    # aqui, o formulario passa a preencher com a politica antiga em silencio
    _, p = _padroes(cliente)
    assert p["origem_tipo"] == dict(plan.ORIGEM)
    assert p["origem_classe"] == dict(plan.ORIGEM_CLASSE)
    # a lista que o JS usa para saber em que tipos a classe carrega a origem
    assert p["downstream"] == list(plan.TIPOS_DOWNSTREAM)
    assert p["origens_por_tipo"] == {t: list(v)
                                     for t, v in plan.ORIGENS_POR_TIPO.items()}
    assert p["origem_nome"] == {str(c): n for c, n in plan.ORIGEM_NOME.items()}
    for tipo in plan.TIPOS:
        assert p["tipos"][tipo] == {
            "lp_base": plan.LP_BASE[tipo],
            "route_limit": plan.ROUTE_LIMIT[tipo],
            "timer_keepalive": plan.TIMER_PADRAO[tipo][0],
            "timer_hold": plan.TIMER_PADRAO[tipo][1],
        }, tipo


def test_a_cascata_esta_ligada_nos_dois_selects(cliente):
    r, _ = _padroes(cliente)
    assert r.text.isascii()
    assert 'addEventListener("change", cascata)' in r.text
    # o datalist nao desenha seta sozinho: sem a marca no CSS o campo com
    # sugestao fica identico a um campo livre
    assert "input[list]" in r.text
    for ident in ("d-lp_base", "d-route_limit", "d-pop", "d-aprendizado"):
        assert 'list="%s"' % ident in r.text, ident


def test_a_origem_gravada_fora_da_tabela_nao_e_trocada_em_silencio(cliente):
    # Sem esta opcao o select cairia no primeiro item e o peer trocaria de
    # origem so por abrir a tela. O caminho alcancavel hoje e o tipo que a
    # validacao nao confere faixa - o cliente recusa 1700 no salvar, o
    # upstream aceita 14 (buraco aberto, registrado na re-revisao).
    r = salvar(cliente, tipo="upstream", classe="", origem="14",
               aprendizado="3100", prefixos_v4="", prefixos_v6="")
    assert r.status_code == 303, r.text
    r = cliente.get("/peer/268127")
    assert 'fora da tabela do tipo' in r.text
    assert '<option value="14" selected>' in r.text


def test_o_pop_ja_cadastrado_vira_sugestao(cliente):
    # POP e ponto de aprendizado sao inventario do operador: o plano da a
    # faixa, nao a lista. O campo sugere o que ja existe e continua aceitando
    # valor novo, que e o que um select de verdade nao faria.
    r = cliente.get("/peer/novo?tipo=cliente")
    assert re.search(r'<datalist id="d-pop">\s*</datalist>', r.text)

    salvar(cliente, pop="2007", aprendizado="3010")
    r = cliente.get("/peer/novo?tipo=cliente")
    assert '<option value="2007">ja cadastrado</option>' in r.text
    assert '<option value="3010">ja cadastrado</option>' in r.text


def test_o_painel_de_saida_tem_as_duas_abas(cliente):
    salvar(cliente)
    r = cliente.get("/saida/268127")
    assert r.status_code == 200
    assert 'data-aba="criar"' in r.text
    assert 'data-aba="remover"' in r.text


def test_o_painel_de_saida_tem_botao_de_copiar(cliente):
    # os dois blocos ficam a vista, e cada um leva o proprio botao
    salvar(cliente)
    r = cliente.get("/saida/268127")
    assert 'id="saida-criar"' in r.text
    assert 'id="saida-remover"' in r.text
    assert "copiar('saida-criar')" in r.text
    assert "copiar('saida-remover')" in r.text
    assert "navigator.clipboard.writeText" in r.text
    # a contagem e a dos botoes de copiar, nao a de "type=button" na pagina
    # inteira: um botao futuro que nao copie nada nao reprova este teste
    assert r.text.count("onclick=\"copiar(") == 2


def test_a_aba_de_criacao_nao_leva_undo(cliente):
    salvar(cliente)
    r = cliente.get("/saida/268127")
    criar = r.text.split('data-aba="criar"')[1].split('data-aba="remover"')[0]
    assert "undo " not in criar


def test_o_quadro_ao_criar_o_peer_mostra_a_lista_vazia(cliente):
    salvar(cliente)
    r = cliente.get("/saida/268127/criar-lista")
    assert r.status_code == 200
    assert "xpl community-list CL-PEER-268127" in r.text
    assert "APPLY-PEER-268127" in r.text
    assert r.text.isascii()


# Fix final: o par CL-PEER-<T> / APPLY-PEER-<T> so existe em cliente e
# upstream. O quadro "ao criar o peer" emitia o par para os quatro tipos, e a
# rota nao tinha portao nenhum: o operador de IX colava uma lista que o bloco
# do peer nao usa.


def test_o_quadro_ao_criar_o_peer_nao_e_servido_para_ix_e_pni(cliente):
    # cada tipo entra com o proprio ASN e o proprio endereco remoto: o
    # validar recusa dois peers com o mesmo ASN, e a sessao repetida tambem
    for i, (tipo, extra) in enumerate(
            (("ix", dict(aprendizado="3010", ix_id="9999")),
             ("pni", dict(ap_allowed="64510")))):
        asn = "6450%d" % i
        r = salvar(cliente, asn=asn, tipo=tipo, classe="", prefixos_v4="",
                   prefixos_v6="", sessao_v4_remoto="198.51.100.%d" % (i + 10),
                   **extra)
        assert r.status_code == 303, tipo
        r = cliente.get("/saida/%s/criar-lista" % asn, follow_redirects=False)
        assert r.status_code == 303, tipo
        assert r.headers["location"] == "/saida/%s" % asn, tipo
        # e o link do painel nao aparece para quem nao tem o par
        assert "/saida/%s/criar-lista" % asn not in cliente.get(
            "/saida/%s" % asn).text


def test_o_painel_do_cliente_e_do_upstream_tem_o_link_do_quadro(cliente):
    salvar(cliente)
    assert "/saida/268127/criar-lista" in cliente.get("/saida/268127").text


# Round 2: o tipo. O formulario so oferece os quatro, mas o POST nao tinha o
# portao que o /peer/novo tem, e um tipo fora da tabela gravava o peer para
# depois estourar no render, com TemplateNotFound, e no avisos, com KeyError.


def test_tipo_desconhecido_volta_com_erro_na_tela(cliente, tmp_path):
    r = salvar(cliente, tipo="xyz")
    assert r.status_code == 200
    assert "tipo desconhecido: xyz" in r.text
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()
    assert peers_mod.carregar(tmp_path / "peers.yaml") == []


def test_tipo_vazio_no_post_cai_no_cliente(cliente, tmp_path):
    # o caso comum do fallback: o campo ausente ou em branco e cliente, que e
    # o que o _texto ja fazia e o que o /peer/novo mostrou
    r = salvar(cliente, tipo="")
    assert r.status_code == 303
    assert peers_mod.carregar(tmp_path / "peers.yaml")[0].tipo == "cliente"


def test_editar_existente_nao_duplica(cliente, tmp_path):
    salvar(cliente)
    salvar_editando(cliente, 0, nome="editado")
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert len(lido) == 1
    assert lido[0].nome == "editado"
    assert lido[0].id == 0


def test_post_sem_a_identidade_nao_sobrescreve_o_peer_do_asn(cliente, tmp_path):
    # um POST sem o campo escondido e um criar, e nao uma edicao do peer que
    # ja tem aquele ASN: quem mandou o formulario na mao recebe o erro do ASN
    # repetido em vez de trocar em silencio o registro que estava la
    salvar(cliente)
    r = salvar(cliente, nome="outro")
    assert r.status_code == 200
    assert "ASN ja usado" in r.text
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert len(lido) == 1
    assert lido[0].nome == "Cliente ACME"


def test_trocar_o_asn_renomeia_o_peer_sem_duplicar(cliente, tmp_path):
    # o campo escondido id_original e o que a tela manda, e e o que diz qual
    # entrada esta por baixo quando o ASN muda: o token e derivado do ASN,
    # entao ele muda junto e nao serve mais de identidade
    salvar(cliente)
    r = salvar(cliente, id_original="0", asn="264130",
               descricao="CLIENTE-AS264130")
    assert r.status_code == 303
    lido = peers_mod.carregar(tmp_path / "peers.yaml")
    assert len(lido) == 1
    assert lido[0].asn == 264130
    assert not (tmp_path / "out" / "268127-cliente.txt").exists()
    assert (tmp_path / "out" / "264130-cliente.txt").exists()


def test_excluir_tira_da_lista_e_apaga_o_arquivo(cliente, tmp_path):
    salvar(cliente)
    arquivo = tmp_path / "out" / "268127-cliente.txt"
    assert arquivo.exists()
    cliente.post("/peer/268127/excluir", data={"confirmado": "sim"},
                 follow_redirects=False)
    assert not arquivo.exists()
    assert peers_mod.carregar(tmp_path / "peers.yaml") == []


def test_excluir_sem_confirmar_nao_apaga(cliente, tmp_path):
    salvar(cliente)
    r = cliente.post("/peer/268127/excluir", data={}, follow_redirects=False)
    assert r.status_code == 200
    assert (tmp_path / "out" / "268127-cliente.txt").exists()
    assert len(peers_mod.carregar(tmp_path / "peers.yaml")) == 1


def test_o_bloco_de_remocao_deixa_a_community_list_do_peer_comentada(cliente):
    # CL-PEER-<T> carrega valor posto a mao: o undo dela sai comentado
    salvar(cliente)
    r = cliente.get("/saida/268127")
    remover = r.text.split('data-aba="remover"')[1]
    assert "!- undo xpl community-list CL-PEER-268127" in remover
    assert "\nundo xpl community-list CL-PEER-268127" not in remover


def test_o_bloco_de_remocao_poe_o_undo_peer_antes_dos_undo_xpl(cliente):
    salvar(cliente)
    r = cliente.get("/saida/268127")
    remover = r.text.split('data-aba="remover"')[1]
    assert remover.index("undo peer") < remover.index("undo xpl")
    assert "APPLY-PEER-268127" in remover


def test_o_cliente_nao_leva_undo_de_noadv_por_peer(cliente):
    # o egress de cliente usa a CL-NOADV-CUST compartilhada
    salvar(cliente)
    r = cliente.get("/saida/268127")
    remover = r.text.split('data-aba="remover"')[1]
    assert "undo xpl community-list CL-NOADV-268127" not in remover


def test_gerar_o_peer_b_nao_muda_a_saida_do_a(cliente, tmp_path):
    a = dict(CLIENTE, apelido="CLIENTEA", asn="64500", descricao="C-AS64500",
             classe="transito", origem="1100", prefixos_v4="45.169.0.0/24",
             sessao_v4_remoto="198.51.100.10")
    b = dict(a, apelido="CLIENTEB", asn="64501", descricao="C-AS64501",
             prefixos_v4="45.169.1.0/24", sessao_v4_remoto="198.51.100.11")
    salvar(cliente, a)
    primeira = (tmp_path / "out" / "CLIENTEA-cliente.txt").read_text(encoding="ascii")
    salvar(cliente, b)
    salvar(cliente, a)
    assert (tmp_path / "out" / "CLIENTEA-cliente.txt").read_text(encoding="ascii") == primeira


def test_a_tela_nao_avisa_sobre_o_base(cliente):
    """O base e download puro, entao a tela nao diz nada sobre ele.

    O aviso antigo lia o out/_base.txt, que nenhuma rota gravava: sem o
    arquivo ele ficava aceso para sempre, e baixar nao o criava.
    """
    salvar(cliente)
    pagina = cliente.get("/").text
    assert "ainda nao gerado" not in pagina
    assert "desatualizado" not in pagina


def test_a_tela_nao_avisa_nem_com_um_base_velho_no_disco(cliente, tmp_path):
    salvar(cliente)
    base = tmp_path / "out" / "_base.txt"
    base.write_text("x", encoding="ascii")
    velho = time.time() - 3600
    os.utime(base, (velho, velho))
    assert "desatualizado" not in cliente.get("/").text


def test_download_do_bloco_base(cliente):
    r = cliente.get("/base.txt")
    assert r.status_code == 200
    assert "IMPORT-SANITY-V4" in r.text
    assert r.text.isascii()


def test_baixar_o_base_nao_grava_arquivo(cliente, tmp_path):
    """Servir o base e so renderizar: nada vai para o disco."""
    cliente.get("/base.txt")
    assert not (tmp_path / "out" / "_base.txt").exists()


def test_o_base_baixado_e_o_render_de_agora(cliente):
    """Sem arquivo guardado nao ha o que comparar: toda vez que o operador
    baixa, sai o que o plan.py diz naquele momento."""
    assert cliente.get("/base.txt").text == render.render_base()


def test_consultar_o_irr_preenche_os_prefixos(cliente, monkeypatch):
    from app import prefixes
    vistos = []

    def falso(asn, token, familias=("v4", "v6"), forcar=False):
        vistos.append((asn, token, forcar))
        return {"v4": ["203.0.113.0/24"], "v6": ["2001:db8::/32"]}

    monkeypatch.setattr(prefixes, "coletar", falso)
    r = cliente.post("/bgpq4", data=CLIENTE, follow_redirects=False)
    assert r.status_code == 200
    assert vistos == [(268127, "268127", False)]   # token derivado do ASN do corpo
    assert "203.0.113.0/24" in r.text               # a tela volta preenchida
    assert "2001:db8::/32" in r.text
    assert "45.169.232.0/22" not in r.text          # a coleta substitui o campo
    assert "Cliente ACME" in r.text                 # o resto do formulario volta


def test_o_botao_atualizar_ignora_o_cache(cliente, monkeypatch):
    from app import prefixes
    vistos = []

    def falso(asn, token, familias=("v4", "v6"), forcar=False):
        vistos.append(forcar)
        return {"v4": [], "v6": []}

    monkeypatch.setattr(prefixes, "coletar", falso)
    r = cliente.post("/bgpq4", data=CLIENTE, follow_redirects=False)
    cliente.post("/bgpq4?forcar=1", data=CLIENTE, follow_redirects=False)
    assert 'id="formulario"' in r.text          # a tela volta inteira, nao um fragmento
    assert vistos == [False, True]


def test_consultar_sem_asn_nao_chama_o_bgpq4(cliente, monkeypatch):
    from app import prefixes
    vistos = []
    monkeypatch.setattr(prefixes, "coletar",
                        lambda asn, token, **kw: vistos.append(asn) or {"v4": [], "v6": []})
    digitados = dict(CLIENTE, asn="", prefixos_v4="45.169.232.0/22",
                     prefixos_v6="2001:db8:100::/48")
    r = cliente.post("/bgpq4", data=digitados, follow_redirects=False)
    assert r.status_code == 200
    assert vistos == []
    assert "informe o ASN" in r.text
    # a consulta que nem chegou a sair nao pode custar o que ja estava digitado
    assert "45.169.232.0/22" in r.text
    assert "2001:db8:100::/48" in r.text


def test_uma_coleta_que_falha_nao_apaga_os_prefixos_digitados(cliente, monkeypatch):
    # bgpq4 fora do ar tambem nao pode custar o que ja estava digitado
    from app import prefixes

    def quebrado(asn, token, **kw):
        raise RuntimeError("bgpq4 nao encontrado")

    monkeypatch.setattr(prefixes, "coletar", quebrado)
    digitados = dict(CLIENTE, prefixos_v4="45.169.232.0/22",
                     prefixos_v6="2001:db8:100::/48")
    r = cliente.post("/bgpq4", data=digitados, follow_redirects=False)
    assert r.status_code == 200
    assert "bgpq4 nao encontrado" in r.text
    assert "45.169.232.0/22" in r.text
    assert "2001:db8:100::/48" in r.text


# A CL-PEER-<T> no formulario: a lista passou a viver no cadastro, e o quadro
# "ao criar o peer" e o que a leva para o equipamento.


def test_o_formulario_grava_as_communities_da_cl_peer(cliente, tmp_path):
    salvar(cliente, communities="64512:1500\n64512:1501",
           large_communities="64512:4:264130")
    peer = peers_mod.carregar(tmp_path / "peers.yaml")[0]
    assert peer.communities == ["64512:1500", "64512:1501"]
    assert peer.large_communities == ["64512:4:264130"]


def test_a_tela_devolve_as_communities_gravadas(cliente):
    # sem isso, abrir o peer para editar e salvar apagaria a lista
    salvar(cliente, communities="64512:1500",
           large_communities="64512:4:264130")
    pagina = cliente.get("/peer/268127").text
    assert "64512:1500" in pagina
    assert "64512:4:264130" in pagina


def test_o_quadro_ao_criar_o_peer_traz_a_lista_do_cadastro(cliente):
    salvar(cliente, communities="64512:1500\n64512:1501",
           large_communities="64512:4:264130")
    r = cliente.get("/saida/268127/criar-lista")
    assert r.status_code == 200
    assert "xpl community-list CL-PEER-268127" in r.text
    assert "64512:1500," in r.text
    assert "xpl large-community-list LC-PEER-268127" in r.text
    assert r.text.isascii()


def test_community_invalida_e_erro_no_campo_e_nao_grava(cliente, tmp_path):
    r = salvar(cliente, communities="nao e community")
    assert r.status_code == 200
    assert "community invalida" in r.text
    # a ancora leva ao campo: o erro do resumo nao pode ser so texto solto
    assert 'href="#f-communities"' in r.text
    assert "nao e community" in r.text
    assert not (tmp_path / "peers.yaml").exists()


def test_community_fora_da_faixa_do_plano_grava_com_aviso(cliente, tmp_path):
    # a faixa do plano nao descreve o contrato: avisa e deixa passar
    r = salvar(cliente, communities="64512:50")
    assert r.status_code == 303
    peer = peers_mod.carregar(tmp_path / "peers.yaml")[0]
    assert peer.communities == ["64512:50"]


def test_o_aviso_da_community_fora_da_faixa_chega_na_tela(cliente):
    # o aviso nao barra a gravacao, e o unico ramo que renderiza avisos e o
    # que volta com erro: entao ele aparece junto de um erro de outro campo.
    # O aviso do route_limit ja vivia assim.
    r = salvar(cliente, communities="64512:50", asn="")
    assert r.status_code == 200
    assert "fora do namespace" in r.text


# Grupo BGP (VRP `group`): rotas CRUD em app.py, mesmo padrao das rotas de
# peer acima (fixture `cliente` isola PEERS_YAML/OUT em tmp_path).


def salvar_grupo(c, dados=None, **kw):
    base = {
        "nome": "PARCEIROS_CDN", "tipo": "parceiro", "classe": "transito",
        "lp_base": "300", "origem": "1100", "pop": "2001",
    }
    return c.post("/grupo", data=dict(dados or base, **kw), follow_redirects=False)


def test_criar_grupo_grava_no_yaml(cliente, tmp_path):
    r = salvar_grupo(cliente)
    assert r.status_code == 303
    assert r.headers["location"] == "/saida/grupo/PARCEIROS_CDN"
    grupos = peers_mod.carregar_grupos(tmp_path / "peers.yaml")
    assert len(grupos) == 1 and grupos[0].nome == "PARCEIROS_CDN"


def test_criar_grupo_com_erro_nao_grava(cliente, tmp_path):
    r = cliente.post("/grupo", data={"nome": "minusculo", "tipo": "parceiro"})
    assert r.status_code == 200
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []


def test_grupo_com_prefixo_malformado_nao_grava_nem_derruba_a_saida(cliente, tmp_path):
    # o prefixo do grupo vai para o plan.cidr_para_xpl no render. Gravado
    # assim mesmo, ele deixava /grupo/X e /saida/grupo/X em 500 para sempre,
    # sem a tela oferecer como consertar: o cadastro tem que recusar antes.
    r = salvar_grupo(cliente, asn="64500", prefixos_v4="203.0.113.0")
    assert r.status_code == 200
    assert "prefixo invalido: 203.0.113.0" in r.text
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []
    assert not (tmp_path / "out" / "grupo-PARCEIROS_CDN.txt").exists()


def test_grupo_com_asn_reservado_nao_grava(cliente, tmp_path):
    r = salvar_grupo(cliente, asn="-5")
    assert r.status_code == 200
    assert "ASN reservado pela IANA" in r.text
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []


def test_excluir_grupo_exige_confirmacao(cliente, tmp_path):
    salvar_grupo(cliente, dados={
        "nome": "X", "tipo": "parceiro", "classe": "transito",
        "lp_base": "300", "origem": "1100", "pop": "2001"})
    r = cliente.post("/grupo/X/excluir", data={})
    assert r.status_code == 200
    assert len(peers_mod.carregar_grupos(tmp_path / "peers.yaml")) == 1
    r = cliente.post("/grupo/X/excluir", data={"confirmado": "sim"},
                     follow_redirects=False)
    assert r.status_code == 303
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []


def test_saida_do_grupo_mostra_o_bloco(cliente):
    salvar_grupo(cliente, dados={
        "nome": "X", "tipo": "parceiro", "classe": "transito",
        "lp_base": "300", "origem": "1100", "pop": "2001"})
    r = cliente.get("/saida/grupo/X")
    assert r.status_code == 200
    assert "group X external" in r.text


# Task 10 (multitipo): o quadro "ao criar" do grupo de upstream. So os tipos
# com o par CL-PEER / APPLY-PEER oferecem o link, o mesmo criterio da tela do
# peer avulso.


def test_a_saida_do_grupo_de_upstream_oferece_o_quadro_ao_criar(cliente, tmp_path):
    cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "communities": "14840:9133",
    }, follow_redirects=False)
    r = cliente.get("/saida/grupo/OPERADORA")
    assert "/saida/grupo/OPERADORA/criar-lista" in r.text


def test_a_saida_do_grupo_de_ix_nao_oferece_o_quadro(cliente, tmp_path):
    cliente.post("/grupo", data={
        "nome": "IXBR", "tipo": "ix", "id": "4", "asn": "26162",
        "lp_base": "190", "origem": "1300", "aprendizado_ix": "3200",
        "ix_id": "1234",
    }, follow_redirects=False)
    r = cliente.get("/saida/grupo/IXBR")
    # sem esta linha o teste passava com o grupo nem criado: o GET de um grupo
    # que nao existe redireciona, e o texto vazio satisfaz o `not in`
    assert "IXBR" in r.text
    assert "/saida/grupo/IXBR/criar-lista" not in r.text


def test_a_saida_do_grupo_de_parceiro_nao_oferece_o_quadro(cliente):
    # o bloco do grupo de downstream nao define nem chama APPLY-PEER nenhum -
    # a CL-PEER dele e por membro -, entao o quadro "ao criar" criava uma
    # CL-PEER-<G> e um APPLY-PEER-<G> que nenhum filtro do grupo chama. O
    # criterio do alvo grupo nao e o TIPOS_COM_APPLY_PEER do peer avulso.
    salvar_grupo(cliente)
    r = cliente.get("/saida/grupo/PARCEIROS_CDN")
    # sem esta linha o teste passaria com o grupo nem criado: o GET de um
    # grupo que nao existe redireciona e o texto vazio satisfaz o `not in`
    assert "PARCEIROS_CDN" in r.text
    assert "/criar-lista" not in r.text


def test_a_rota_do_quadro_ao_criar_do_grupo_de_parceiro_redireciona(cliente):
    salvar_grupo(cliente)
    r = cliente.get("/saida/grupo/PARCEIROS_CDN/criar-lista",
                    follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/saida/grupo/PARCEIROS_CDN"


def test_a_rota_do_quadro_ao_criar_do_grupo_serve_a_lista(cliente, tmp_path):
    # a tela oferece o link e a rota tem que servir o quadro com o conteudo do
    # cadastro do grupo: e o grupo que e dono da CL-PEER da rede remota
    cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "communities": "14840:9133\n14840:9134",
    }, follow_redirects=False)
    r = cliente.get("/saida/grupo/OPERADORA/criar-lista")
    assert r.status_code == 200
    assert "xpl community-list CL-PEER-OPERADORA" in r.text
    assert " 14840:9134" in r.text
    assert "xpl route-filter APPLY-PEER-OPERADORA" in r.text
    # o cabecalho diz de quem e o quadro: sem o grupo na chamada do render o
    # quadro sai como o do peer avulso, com o AS no fim, e o operador cola uma
    # lista que se diz do peer 3 quando ela e do grupo
    assert "# ao criar o grupo 3 - upstream\n" in r.text
    assert "# ao criar o peer" not in r.text
    assert r.text.isascii()


def test_a_rota_do_quadro_ao_criar_do_grupo_de_ix_redireciona(cliente, tmp_path):
    # sem APPLY-PEER nao ha quadro: a rota devolve o operador para a saida do
    # grupo, como a rota do peer faz com o peer de ix
    salvar_grupo(cliente, dados={
        "nome": "IXBR", "tipo": "ix", "id": "4", "asn": "26162",
        "lp_base": "190", "origem": "1300", "aprendizado_ix": "3200",
        "ix_id": "1234"})
    r = cliente.get("/saida/grupo/IXBR/criar-lista", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/saida/grupo/IXBR"


def test_a_rota_do_quadro_ao_criar_de_grupo_inexistente_redireciona(cliente, tmp_path):
    r = cliente.get("/saida/grupo/NAOEXISTE/criar-lista", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_o_quadro_ao_criar_do_grupo_nao_vira_rota_de_peer(cliente, tmp_path):
    # a rota de peer acha por token e a de grupo por nome; passar um nome de
    # grupo na rota de peer tem que redirecionar, nao estourar
    cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
    }, follow_redirects=False)
    r = cliente.get("/saida/OPERADORA/criar-lista", follow_redirects=False)
    assert r.status_code == 303


def test_editar_grupo_sem_renomear_nao_grava_erro_de_duplicata(cliente, tmp_path):
    # a regressao carregada da task 3: grupo_salvar monta um Grupo novo a
    # cada POST, e a lista `grupos` ainda carrega o objeto antigo com o
    # mesmo nome. Sem o `anterior` em validar_grupo, editar um campo sem
    # trocar o nome batia "nome ja usado" contra si mesmo.
    salvar_grupo(cliente)
    grupos = peers_mod.carregar_grupos(tmp_path / "peers.yaml")
    r = salvar_grupo(cliente, id=str(grupos[0].id), lp_base="250")
    assert r.status_code == 303, r.text
    grupos = peers_mod.carregar_grupos(tmp_path / "peers.yaml")
    assert len(grupos) == 1
    assert grupos[0].lp_base == 250


def test_grupo_novo_e_grupo_editar_respondem(cliente):
    assert cliente.get("/grupo/novo").status_code == 200
    salvar_grupo(cliente)
    assert cliente.get("/grupo/PARCEIROS_CDN").status_code == 200


def test_o_formulario_do_grupo_traz_bfd_e_timers(cliente, tmp_path):
    # o POST so manda o que esta na tela, e a tela do grupo nao tinha bfd,
    # graceful-restart nem timers: todo salvar - inclusive o que so mexia no
    # lp_base - gravava bfd=False e graceful_restart=False, desligando os
    # dois em silencio. A tela passa a mostrar o estado do dataclass (os dois
    # ligados no grupo novo) e o que ela mostra e o que volta.
    r = cliente.get("/grupo/novo")
    assert 'name="bfd" checked' in r.text
    assert 'name="graceful_restart" checked' in r.text

    salvar_grupo(cliente, bfd="on", graceful_restart="on",
                 timer_keepalive="30", timer_hold="90")
    grupo = peers_mod.carregar_grupos(tmp_path / "peers.yaml")[0]
    assert grupo.bfd is True and grupo.graceful_restart is True
    assert grupo.timer_keepalive == 30 and grupo.timer_hold == 90

    r = cliente.get("/grupo/PARCEIROS_CDN")
    assert 'name="bfd" checked' in r.text
    assert 'name="timer_keepalive" value="30"' in r.text
    assert 'name="timer_hold" value="90"' in r.text

    # desmarcar e escolha do operador, e chega no yaml como no peer
    salvar_grupo(cliente, id=str(grupo.id))
    grupo = peers_mod.carregar_grupos(tmp_path / "peers.yaml")[0]
    assert grupo.bfd is False and grupo.graceful_restart is False
    assert grupo.timer_keepalive is None and grupo.timer_hold is None


def test_grupo_editar_inexistente_redireciona(cliente):
    r = cliente.get("/grupo/NAO_EXISTE", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_excluir_grupo_inexistente_redireciona(cliente):
    r = cliente.post("/grupo/NAO_EXISTE/excluir", data={"confirmado": "sim"},
                     follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_id_nao_numerico_no_post_de_grupo_nao_derruba(cliente, tmp_path):
    # um id torto no campo escondido nao pode estourar: mesmo caminho seguro
    # que o _id_do_formulario ja da ao peer, tratado como "cria novo"
    r = salvar_grupo(cliente, id="abc")
    assert r.status_code == 303
    grupos = peers_mod.carregar_grupos(tmp_path / "peers.yaml")
    assert len(grupos) == 1 and grupos[0].nome == "PARCEIROS_CDN"


def test_valor_numerico_torto_no_grupo_volta_com_erro(cliente, tmp_path):
    # o int() do grupo engolia o ValueError: o campo torto virava None e o
    # grupo era gravado com o default da tabela, como se o operador nao
    # tivesse digitado nada. No peer o mesmo campo devolve "valor numerico
    # invalido" e nao grava; o grupo agora tambem.
    r = salvar_grupo(cliente, lp_base="trezentos")
    assert r.status_code == 200
    assert "valor numerico invalido" in r.text
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []
    assert not (tmp_path / "out" / "grupo-PARCEIROS_CDN.txt").exists()


def test_lp_base_zero_no_grupo_nao_vira_o_default(cliente, tmp_path):
    # lp_base e 0..65535, mas o `or 300` trocava o zero digitado pelo default
    # do tipo em silencio: o operador so descobria depois de gravar
    r = salvar_grupo(cliente, lp_base="0")
    assert r.status_code == 303, r.text
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml")[0].lp_base == 0


def test_lp_base_em_branco_cai_no_default_do_tipo(cliente, tmp_path):
    # em branco continua sendo "usa a tabela", como no peer
    salvar_grupo(cliente, tipo="cliente", lp_base="")
    grupo = peers_mod.carregar_grupos(tmp_path / "peers.yaml")[0]
    assert grupo.lp_base == plan.LP_BASE["cliente"]


def test_o_lp_base_do_grupo_novo_acompanha_o_tipo(cliente):
    # o formulario em branco nasce com o LP do tipo, como o do peer, e o
    # /grupo/novo so sabia montar o de parceiro: os cinco tipos do plano
    # chegavam todos com LP 300 na tela. O parceiro continua empatando com o
    # cliente, que e o desenho: por baixo da marca ele e um downstream.
    for tipo, esperado in (("upstream", 100), ("ix", 190), ("pni", 200)):
        r = cliente.get("/grupo/novo?tipo=%s" % tipo)
        assert 'name="lp_base" value="%d"' % esperado in r.text, tipo


def test_o_aprendizado_do_grupo_novo_nasce_cheio(cliente):
    # o campo e obrigatorio em upstream e ix, e o formulario em branco chegava
    # com ele vazio: o operador tinha que inventar um numero no meio do
    # cadastro, enquanto lp_base, origem e timers ja vinham preenchidos. A
    # tela propoe o primeiro valor livre do bloco do tipo, que e o desenho da
    # tabela do PLANO (31xx upstream, 30xx IX), e o campo continua aceitando
    # qualquer 3xxx.
    assert 'name="aprendizado" list="d-aprendizado" value="3100"' in cliente.get(
        "/grupo/novo?tipo=upstream").text
    assert 'name="aprendizado" list="d-aprendizado" value="3010"' in cliente.get(
        "/grupo/novo?tipo=ix").text


def test_o_tipo_sem_ponto_de_aprendizado_nao_ganha_numero(cliente):
    # os dois blocos da tela mostram o campo, mas quem nao tem ponto de
    # aprendizado nao pode receber um numero so por o campo estar escondido:
    # um grupo de cliente carimbado com 3xxx diria que aprendeu de fora.
    for tipo in ("cliente", "parceiro", "pni"):
        r = cliente.get("/grupo/novo?tipo=%s" % tipo)
        assert 'name="aprendizado" list="d-aprendizado" value=""' in r.text, tipo


def test_o_aprendizado_do_grupo_novo_pula_o_que_ja_existe(cliente):
    # o 3xxx identifica de onde a rota foi aprendida, entao dois cadastros
    # com o mesmo numero perdem a informacao. O campo nasce no primeiro
    # valor livre, e o espaco e um so: um peer de upstream ocupa 3101 para
    # o grupo tambem, que e a mesma disputa do eixo 5PPA.
    cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
    }, follow_redirects=False)
    assert 'name="aprendizado" list="d-aprendizado" value="3101"' in cliente.get(
        "/grupo/novo?tipo=upstream").text

    r = salvar(cliente, tipo="upstream", classe="", origem="1400",
               aprendizado="3101", prefixos_v4="", prefixos_v6="")
    assert r.status_code == 303, r.text
    assert 'name="aprendizado" list="d-aprendizado" value="3102"' in cliente.get(
        "/grupo/novo?tipo=upstream").text


def test_o_aprendizado_do_peer_novo_nasce_cheio_tambem(cliente):
    # a mesma correcao no formulario do peer avulso, que tem o mesmo campo
    # obrigatorio e a mesma tabela do lado: as duas telas nao podem divergir
    assert 'list="d-aprendizado" value="3100"' in cliente.get(
        "/peer/novo?tipo=upstream").text
    assert 'list="d-aprendizado" value=""' in cliente.get(
        "/peer/novo?tipo=cliente").text


def test_o_aprendizado_gasto_por_um_grupo_e_sugestao_no_peer(cliente):
    # o 3xxx e um espaco so, e o _aprendizado_padrao ja conta os dois lados ao
    # escolher o numero do campo em branco. A lista de "ja cadastrado" do
    # formulario do peer contava so os peers, entao um numero que um grupo ja
    # tinha gasto aparecia livre na tela do peer - e o operador escolhia de
    # novo um ponto de aprendizado que ja existia.
    cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
    }, follow_redirects=False)
    r = cliente.get("/peer/novo?tipo=upstream")
    assert '<option value="3100">ja cadastrado</option>' in r.text


def test_a_tela_do_grupo_sugere_o_aprendizado_ja_cadastrado(cliente):
    # a tela do peer sugere o 3xxx ja cadastrado num datalist; a do grupo nao
    # tinha nenhum, entao o operador so descobria o numero gasto pelo outro
    # lado errando o salvar. O campo existe nos dois blocos e os dois ficam no
    # formulario ao mesmo tempo, entao o datalist e um so e os dois inputs
    # chegam nele pelo list=: um por bloco repetiria o id, que e HTML invalido
    # - o mesmo motivo do f-aprendizado / f-aprendizado_ix.
    salvar(cliente, tipo="upstream", classe="", origem="1400",
           aprendizado="3100", prefixos_v4="", prefixos_v6="")
    cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3101",
    }, follow_redirects=False)

    r = cliente.get("/grupo/novo?tipo=upstream")
    assert r.text.count('<datalist id="d-aprendizado">') == 1
    assert '<input name="aprendizado" list="d-aprendizado"' in r.text
    assert '<input name="aprendizado_ix" list="d-aprendizado"' in r.text
    # a lista e a das duas telas: o numero do peer e o do grupo
    assert '<option value="3100">ja cadastrado</option>' in r.text
    assert '<option value="3101">ja cadastrado</option>' in r.text


def test_o_formulario_de_grupo_oferece_os_cinco_tipos(cliente):
    # o select de tipo da tela do grupo listava cliente, parceiro e upstream
    # na mao. O plan.py tem os cinco e o render ja aceita os cinco: a tela
    # era a unica que ainda nao sabia
    r = cliente.get("/grupo/novo")
    assert _opcoes(r.text, "tipo") == list(plan.TIPOS)


def test_o_select_de_origem_do_grupo_so_oferece_a_lista_do_tipo(cliente):
    # a origem e vocabulario do plano, nao inventario do operador, e o
    # validar_grupo recusa um grupo com a marca de outro tipo. Por isso o
    # campo e select preso a ORIGENS_POR_TIPO, e nao mais um input livre
    for tipo in plan.TIPOS:
        r = cliente.get("/grupo/novo?tipo=%s" % tipo)
        oferecidas = set(_opcoes(r.text, "origem"))
        permitidas = set(str(o) for o in plan.ORIGENS_POR_TIPO[tipo])
        assert oferecidas == permitidas, (tipo, oferecidas, permitidas)


def test_a_origem_do_grupo_fora_da_tabela_nao_e_trocada_em_silencio(cliente):
    # o select e preso a tabela do tipo. Sem a opcao de fallback uma origem
    # gravada fora dela - yaml editado a mao, tabela do tipo que mudou - nao
    # casaria com option nenhuma: o navegador cairia na primeira e o proximo
    # salvar reescrevia a origem do grupo sem avisar. O caminho alcancavel
    # hoje e o POST que a validacao recusa: a tela volta com o grupo do
    # formulario, que e o estado que o operador ve gravado. Mesma opcao da
    # tela do peer.
    r = salvar_grupo(cliente, tipo="ix", asn="26162", origem="1100",
                     aprendizado_ix="3200", ix_id="1234")
    assert r.status_code == 200
    permitidas = ", ".join(str(o) for o in plan.ORIGENS_POR_TIPO["ix"])
    assert ("origem do ix tem que ser uma de %s" % permitidas) in r.text
    assert ('<option value="1100" selected>1100 - fora da tabela do tipo'
            '</option>') in r.text
    # a opcao entra alem da lista do tipo, nao no lugar dela
    assert set(_opcoes(r.text, "origem")) == (
        set(str(o) for o in plan.ORIGENS_POR_TIPO["ix"]) | {"1100"})


def test_nenhum_id_da_tela_do_grupo_se_repete(cliente):
    # o campo de aprendizado existe nos dois blocos, o de upstream e o de ix,
    # e o erro sai com a chave `aprendizado` nos dois, porque o campo do Grupo
    # e um so. Com o mesmo id nos dois labels o id se repetiria no DOM (HTML
    # invalido) e o navegador resolveria para o primeiro, o do bloco de
    # upstream: num grupo de ix a ancora do erro pularia para um bloco
    # escondido. Os dois blocos ficam no formulario ao mesmo tempo em qualquer
    # tipo, entao a varredura vale para os cinco.
    for tipo in plan.TIPOS:
        r = cliente.get("/grupo/novo?tipo=%s" % tipo)
        ids = re.findall(r'id="([^"]+)"', r.text)
        repetidos = sorted(i for i in set(ids) if ids.count(i) > 1)
        assert repetidos == [], (tipo, repetidos)
        assert "f-aprendizado" in ids and "f-aprendizado_ix" in ids, tipo


def test_o_grupo_marca_os_campos_por_tipo(cliente):
    # data-para diz ao JS quais blocos mostrar; o HTML ja sai com o certo
    # para o tipo gravado, e o JS so corrige depois de uma troca
    r = cliente.get("/grupo/novo?tipo=upstream")
    assert 'data-para="upstream"' in r.text


def test_a_tela_do_grupo_mostra_o_bh_upstream_gravado(cliente, tmp_path):
    # o campo ja era lido pelo grupo_do_formulario, mas nao tinha campo na
    # tela: o operador salvava pela pagina e o valor sumia sem aviso. Este
    # teste olha a tela, e nao o corpo do POST, porque e a tela que muda
    cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "bh_upstream": "14840:666",
    }, follow_redirects=False)
    r = cliente.get("/grupo/OPERADORA")
    assert 'name="bh_upstream"' in r.text
    assert 'value="14840:666"' in r.text


def test_o_campo_do_bh_upstream_do_grupo_tem_onde_mostrar_o_erro(cliente):
    # o campo esta em `ancoraveis`, entao o resumo do topo linka para ele: o
    # erro tem que aparecer do lado do campo, como no campo homonimo da tela
    # do peer. Sem o span, o campo sairia marcado e mudo - a ancora levaria a
    # uma mensagem que nao esta na tela. O render vai direto pelo template
    # porque nenhuma validacao escreve nessa chave hoje (o campo e inerte), e
    # um GET comum nao tem como trazer o erro para a tela.
    grupo = peers_mod.Grupo(id=3, nome="OPERADORA", tipo="upstream",
                            lp_base=100, origem=1400, aprendizado=3100)
    html = mod.templates.env.get_template("pagina_grupo.html").render(
        **mod._contexto_grupo(
            None, grupo, criando=False,
            erros={"bh_upstream": "a community do blackhole esta torta"}))
    campo = re.search(
        r'<label class="campo[^"]*" id="f-bh_upstream">([\s\S]*?)</label>', html)
    assert campo is not None
    assert "a community do blackhole esta torta" in campo.group(1)


def test_salvar_grupo_de_upstream_grava_os_campos_do_tipo(cliente, tmp_path):
    r = cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "te_prefixos_v4": "1.1.1.0/24", "ap_block": "64500",
        "ap_te": "64501", "bh_upstream": "14840:666", "prepend_base": "2",
        "communities": "14840:9133", "large_communities": "14840:1:3333",
    }, follow_redirects=False)
    assert r.status_code == 303
    g = peers_mod.carregar_grupos(tmp_path / "peers.yaml")[0]
    assert (g.tipo, g.aprendizado, g.prepend_base) == ("upstream", 3100, 2)
    assert g.te_prefixos["v4"] == ["1.1.1.0/24"]
    assert g.communities == ["14840:9133"]
    assert g.large_communities == ["14840:1:3333"]


def test_o_bh_upstream_do_grupo_atravessa_dois_salvarios(cliente, tmp_path):
    # guarda de ida e volta pelo corpo do POST: o primeiro salvar grava, o
    # segundo substitui o mesmo grupo e o valor continua la. Este teste NAO
    # olha a tela - o campo nao existia nela e o teste antigo nao provava o
    # contrario, porque mandava o campo na mao. Quem olha a tela e o
    # test_a_tela_do_grupo_mostra_o_bh_upstream_gravado, logo acima.
    dados = {
        "nome": "OPERADORA", "tipo": "upstream", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "bh_upstream": "14840:666",
    }
    assert cliente.post("/grupo", data=dados,
                        follow_redirects=False).status_code == 303
    ident = peers_mod.carregar_grupos(tmp_path / "peers.yaml")[0].id
    assert cliente.post("/grupo", data=dict(dados, id=str(ident)),
                        follow_redirects=False).status_code == 303
    grupos = peers_mod.carregar_grupos(tmp_path / "peers.yaml")
    assert len(grupos) == 1
    assert grupos[0].bh_upstream == "14840:666"


def test_grupo_com_aprendizado_torto_volta_com_erro(cliente, tmp_path):
    # um aprendizado torto num grupo de upstream nao pode gravar nada. O
    # "abc" vira None no int(), o validar_grupo cobra o 3xxx do upstream, e
    # as duas mensagens saem para o mesmo campo: o erros_para_dict guarda a
    # PRIMEIRA, que e a do campo, e nao a do validar, que so ve o None que
    # sobrou do int(). Por isso a assercao cobra as duas pontas: o valor
    # numerico invalido tem que aparecer, e a cobranca da faixa nao pode
    # tomar o lugar dele
    r = cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "abc",
    })
    assert r.status_code == 200
    assert "campo(s) para corrigir" in r.text
    assert "valor numerico invalido" in r.text
    assert "ponto de aprendizado 3xxx obrigatorio" not in r.text
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []


def test_o_aprendizado_torto_no_grupo_vira_erro_de_campo(cliente, tmp_path):
    # o aprendizado entrou no CAMPOS_INT_GRUPO nesta task: sem ele o campo
    # nao era lido e um "abc" passava batido pelo formulario, porque so o
    # upstream e o ix o cobram. Num tipo que nao cobra, esta chave fica so
    # com a mensagem do campo - o mesmo POST levanta tambem o erro de
    # ap_allowed vazio, mas e de outro campo e nao disputa com esta
    r = cliente.post("/grupo", data={
        "nome": "OPERADORA", "tipo": "pni", "id": "3", "asn": "14840",
        "lp_base": "200", "origem": "1500", "aprendizado": "abc",
    })
    assert "valor numerico invalido" in r.text
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml") == []


def corpo(pares):
    """O corpo urlencoded, na ordem e com os nomes repetidos que o POST leva.

    O TestClient nao monta formulario com nome repetido a partir de lista de
    tuplas, e e justamente o nome repetido que este teste precisa reproduzir.
    """
    return "&".join("%s=%s" % par for par in pares)


def test_o_bloco_escondido_nao_apaga_o_aprendizado_do_bloco_visivel(cliente, tmp_path):
    # os blocos de upstream e de IX ficam os dois no formulario, e o que nao e
    # do tipo escolhido vai em branco no POST. Com um nome so para os dois, o
    # dict(await request.form()) guardava o ultimo - o branco do bloco
    # escondido apagava o que o operador digitou no visivel, e o salvar
    # recusava o campo dizendo "ponto de aprendizado 3xxx obrigatorio" com o
    # numero escrito na frente dele. Nao havia como sair dali.
    pares = [
        ("nome", "PROVEDOR"), ("tipo", "upstream"), ("asn", "14840"),
        ("lp_base", "100"), ("origem", "1400"),
        ("aprendizado", "3101"),     # o bloco visivel, preenchido
        ("aprendizado_ix", ""),      # o bloco do IX, escondido
    ]
    r = cliente.post("/grupo", content=corpo(pares),
                     headers={"Content-Type": "application/x-www-form-urlencoded"},
                     follow_redirects=False)
    assert r.status_code == 303
    assert peers_mod.carregar_grupos(tmp_path / "peers.yaml")[0].aprendizado == 3101


def test_o_aprendizado_vem_do_bloco_do_tipo_escolhido(cliente, tmp_path):
    # o bloco escondido nao vem vazio so quando a tela volta de um erro: ao
    # abrir a tela os dois blocos nascem com o valor proposto, e o do outro
    # tipo e um numero valido. Escolher entre eles nao pode ser "o primeiro"
    # nem "o que veio por ultimo": e o tipo que diz de qual bloco ele vem.
    c = cliente
    r = c.post("/grupo", content=corpo([
        ("nome", "PROVEDOR"), ("tipo", "upstream"), ("asn", "14840"),
        ("lp_base", "100"), ("origem", "1400"),
        ("aprendizado", "3101"), ("aprendizado_ix", "3010"),
    ]), headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False)
    assert r.status_code == 303
    r = c.post("/grupo", content=corpo([
        ("nome", "IXSP"), ("tipo", "ix"), ("asn", "14840"),
        ("lp_base", "100"), ("origem", "1300"), ("ix_id", "1234"),
        ("aprendizado", "3101"), ("aprendizado_ix", "3010"),
    ]), headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False)
    assert r.status_code == 303
    grupos = {g.nome: g.aprendizado
              for g in peers_mod.carregar_grupos(tmp_path / "peers.yaml")}
    assert grupos == {"PROVEDOR": 3101, "IXSP": 3010}


def _bloco_do_id(texto, ident):
    """O data-para do bloco onde mora o elemento com este id.

    O mostraCampos esconde todo bloco data-para que nao seja o do tipo da
    tela, e esconder o bloco esconde o que esta dentro dele: a ancora de um
    erro so leva a algum lugar se o id do campo estiver fora de data-para
    (""), ou no bloco do tipo da propria tela. Vale o data-para do ancestral
    mais proximo que tem um, e nao o do div de dentro (o `campos` do
    fieldset nao tem nenhum). None quando o id nao existe, para o teste que
    espera um bloco falhar alto em vez de passar calado com a tela quebrada.
    """
    pilha = []
    for m in re.finditer(r"<(/?)(\w+)([^>]*)>", texto):
        fecha, tag, attrs = m.group(1), m.group(2), m.group(3)
        if tag == "div":
            if fecha:
                if pilha:
                    pilha.pop()
            else:
                achado = re.search(r'data-para="([^"]*)"', attrs)
                pilha.append(achado.group(1) if achado else "")
        if re.search(r'\bid="%s"' % re.escape(ident), attrs):
            return next((v for v in reversed(pilha) if v), "")
    return None


def test_o_erro_de_prefixo_do_grupo_ancora_num_campo_de_todo_tipo(cliente):
    # o _valida_prefixos roda nos cinco tipos, mas o bloco do campo estava
    # dentro de data-para="cliente parceiro": num grupo de upstream o JS
    # esconde o bloco inteiro, e o link do erro pulava para dentro de um
    # campo que nao esta na tela
    r = cliente.post("/grupo", data={
        "nome": "PROVEDOR", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100",
        "prefixos_v4": "203.0.113.0", "prefixos_v6": "",
    })
    assert r.status_code == 200
    assert "prefixo invalido: 203.0.113.0" in r.text
    assert 'href="#f-prefixos"' in r.text
    assert _bloco_do_id(r.text, "f-prefixos") == ""


def test_a_ancora_do_aprendizado_acompanha_o_bloco_do_tipo_da_tela(cliente):
    # o campo do aprendizado mora em dois blocos, um por tipo, com nomes
    # diferentes no POST (aprendizado e aprendizado_ix), e o erro sai com a
    # chave `aprendizado` nos dois: a ancora tem que apontar para o bloco do
    # tipo da tela, senao ela cai num bloco que o JS esconde
    ix = cliente.post("/grupo", data={
        "nome": "IXBR", "tipo": "ix", "id": "4", "asn": "26162",
        "lp_base": "190", "origem": "1300", "ix_id": "1234",
    })
    assert ix.status_code == 200
    assert 'href="#f-aprendizado_ix"' in ix.text
    assert 'href="#f-aprendizado"' not in ix.text
    assert _bloco_do_id(ix.text, "f-aprendizado_ix") == "ix"

    up = cliente.post("/grupo", data={
        "nome": "PROVEDOR", "tipo": "upstream", "id": "3", "asn": "14840",
        "lp_base": "100", "origem": "1400",
    })
    assert up.status_code == 200
    assert 'href="#f-aprendizado"' in up.text
    assert _bloco_do_id(up.text, "f-aprendizado") == "upstream"


def test_salvar_peer_com_grupo_grava_grupo_id(cliente, tmp_path):
    cliente.post("/grupo", data={
        "nome": "PARCEIROS_CDN", "tipo": "parceiro", "classe": "transito",
        "lp_base": "300", "origem": "1100", "pop": "2001"})
    grupo_id = peers_mod.carregar_grupos(mod.PEERS_YAML)[0].id
    resp = cliente.post("/peer", data={
        "tipo": "parceiro", "asn": "264130", "nome": "EXEMPLO TELECOM",
        "descricao": "EXEMPLO TELECOM", "grupo_id": str(grupo_id),
        "sessao_v4_local": "192.0.2.2", "sessao_v4_remoto": "192.0.2.3",
    }, follow_redirects=False)
    assert resp.status_code == 303
    peer = peers_mod.carregar(mod.PEERS_YAML)[0]
    assert peer.grupo_id == grupo_id
    saida = peer.arquivo().read_text()
    assert "group PARCEIROS_CDN" in saida
    assert "PL-CUST" not in saida  # sem override, sem prefixo


def test_membro_com_asn_diferente_do_grupo_volta_com_erro(cliente, tmp_path):
    # num grupo com ASN proprio o membro nao repete o as-number (o bloco do
    # grupo o declara): aceitar outro ASN aqui abriria a sessao com o ASN do
    # grupo enquanto a pagina e o arquivo do membro mostram o outro
    #
    # o nome do grupo e o do VRP: sem hifen (ver NOME_GRUPO_RE)
    salvar_grupo(cliente, dados={
        "nome": "UP_REDUNDANTE", "tipo": "parceiro", "classe": "transito",
        "asn": "64500", "lp_base": "300", "origem": "1100", "pop": "2001"})
    grupo_id = peers_mod.carregar_grupos(mod.PEERS_YAML)[0].id
    resp = cliente.post("/peer", data={
        "tipo": "parceiro", "asn": "64501", "nome": "EXEMPLO TELECOM",
        "descricao": "EXEMPLO TELECOM", "grupo_id": str(grupo_id),
        "sessao_v4_local": "192.0.2.2", "sessao_v4_remoto": "192.0.2.3",
    }, follow_redirects=False)
    assert resp.status_code == 200
    assert "difere do ASN" in resp.text
    assert peers_mod.carregar(mod.PEERS_YAML) == []


def test_peer_de_upstream_membro_de_grupo_de_upstream_grava(cliente, tmp_path):
    # o gate de membro vale para os cinco tipos: o mesmo objeto de grupo
    # existe em todos, e quem recusa o par errado e o validate. Antes desta
    # correcao o POST de um peer de upstream com um grupo escolhido gravava
    # grupo_id nulo, sem erro nenhum, e o grupo ficava vazio.
    # o grupo nasce com o mesmo ASN do membro de proposito: com outro, a
    # recusa passa a ser a do asn divergente, e o que este teste prova e o
    # gate de membro
    r = salvar_grupo(cliente, dados={
        "nome": "PROVEDOR", "tipo": "upstream", "id": "3", "asn": "64500",
        "lp_base": "100", "origem": "1400", "aprendizado": "3100"})
    assert r.status_code == 303, r.text
    grupo_id = peers_mod.carregar_grupos(mod.PEERS_YAML)[0].id
    r = salvar(cliente, tipo="upstream", asn="64500", classe="", origem="",
               aprendizado="3100", prefixos_v4="", prefixos_v6="",
               grupo_id=str(grupo_id))
    assert r.status_code == 303, r.text
    lido = peers_mod.carregar(mod.PEERS_YAML)[0]
    assert lido.grupo_id == grupo_id
    texto = (tmp_path / "out" / "64500-upstream.txt").read_text(encoding="ascii")
    assert "group PROVEDOR" in texto
    # e o grupo deixa de estar vazio para a tela: a confirmacao de exclusao
    # lista o membro pelo que esta gravado
    r = cliente.post("/grupo/PROVEDOR/excluir", data={})
    assert "Peers apontando para ele: 64500" in r.text


def test_peer_de_upstream_com_grupo_de_outro_tipo_volta_com_o_erro(cliente, tmp_path):
    # o par errado continua recusado, agora no lugar certo: o grupo e de
    # parceiro e o membro e de upstream
    salvar_grupo(cliente)
    grupo_id = peers_mod.carregar_grupos(mod.PEERS_YAML)[0].id
    r = salvar(cliente, tipo="upstream", classe="", origem="",
               aprendizado="3100", prefixos_v4="", prefixos_v6="",
               grupo_id=str(grupo_id))
    assert r.status_code == 200
    assert "grupo PARCEIROS_CDN e de parceiro, nao de upstream" in r.text
    assert peers_mod.carregar(mod.PEERS_YAML) == []


def _arvore(raiz):
    """O retrato do disco: bytes de cada arquivo, por caminho relativo.

    A recusa de exclusao tem que ser um no-op completo - nem o yaml, nem a
    saida do membro, nem a do grupo podem mudar de byte.
    """
    return {str(p.relative_to(raiz)): p.read_bytes()
            for p in sorted(raiz.rglob("*")) if p.is_file()}


def test_excluir_grupo_com_membro_e_recusado(cliente, tmp_path):
    # o membro sem filtro proprio nao tem politica nenhuma no arquivo dele -
    # a validacao dispensou classe/origem/prefixo justamente porque eles
    # vinham do grupo -, entao apagar o grupo por baixo dele nao o devolve
    # ao estado avulso: so deixa a saida dele estourando. Enquanto houver
    # membro a exclusao para, e o erro diz quem sai primeiro.
    salvar_grupo(cliente)
    grupo_id = peers_mod.carregar_grupos(mod.PEERS_YAML)[0].id
    r = salvar(cliente, tipo="parceiro", classe="", origem="", prefixos_v4="",
               grupo_id=str(grupo_id))
    assert r.status_code == 303, r.text
    membro = peers_mod.carregar(mod.PEERS_YAML)[0]
    antes = _arvore(tmp_path)

    r = cliente.post("/grupo/PARCEIROS_CDN/excluir", data={"confirmado": "sim"},
                     follow_redirects=False)

    assert r.status_code == 200
    assert membro.token in r.text
    assert "antes de excluir" in r.text
    assert len(peers_mod.carregar_grupos(mod.PEERS_YAML)) == 1
    assert _arvore(tmp_path) == antes


def test_saida_de_membro_com_o_grupo_sumido_nao_estoura(cliente, tmp_path):
    # um grupo_id orfao no yaml - arquivo editado a mao, gravacao pela
    # metade - nao pode virar 500 nem, pior, um bloco avulso: sem o grupo,
    # o membro sem filtro proprio sairia sem filtro nenhum e sem o `group`
    # do VRP, isto e, anunciando tudo. A tela volta com o erro que ancora no
    # select do grupo.
    salvar_grupo(cliente)
    grupo_id = peers_mod.carregar_grupos(mod.PEERS_YAML)[0].id
    r = salvar(cliente, tipo="parceiro", classe="", origem="", prefixos_v4="",
               grupo_id=str(grupo_id))
    assert r.status_code == 303, r.text
    membro = peers_mod.carregar(mod.PEERS_YAML)[0]

    peers_mod.gravar_grupos([], mod.PEERS_YAML)  # o grupo some por fora

    r = cliente.get("/saida/%s" % membro.token)
    assert r.status_code == 200
    assert "grupo nao encontrado" in r.text


def test_a_tela_avisa_que_o_membro_sem_filtro_nao_usa_os_campos_de_politica(
        cliente, tmp_path):
    # F1 da revisao final: o membro de grupo sem filtro proprio aceita
    # lp_base, origem, aprendizado, pop, classe e ix_id no formulario, os
    # valores chegam ao peers.yaml, e o bloco dele nao leva politica nenhuma:
    # as linhas do ramo de membro sao de sessao e de `group <nome>`, e quem
    # carrega a politica e o arquivo do grupo. O
    # comportamento fica: e a heranca que a spec descreve, e o filtro proprio
    # (Peer.tem_filtro_proprio) e o unico caminho para o membro ter politica
    # propria. O que entra e o aviso, sem recusa no validate (barraria
    # configuracao que ja existe no yaml) e sem JS (a cascata da tela do peer
    # nao roda, entao nota condicional nao e opcao). As duas notas sao fixas e
    # verdadeiras nos
    # dois casos: a do grupo BGP vale para o membro sem filtro proprio, e a da
    # secao politica nomeia esse mesmo caso - no peer sem grupo, que e o outro
    # caso da tela, ela nao afirma nada.
    salvar_grupo(cliente)
    grupo_id = peers_mod.carregar_grupos(mod.PEERS_YAML)[0].id
    r = salvar(cliente, tipo="parceiro", classe="", origem="", prefixos_v4="",
               prefixos_v6="", lp_base="999", grupo_id=str(grupo_id))
    assert r.status_code == 303, r.text
    membro = peers_mod.carregar(mod.PEERS_YAML)[0]
    # a premissa do teste, presa: o membro e puro, e o predicado e quem decide
    # entre o ramo proprio e a heranca do grupo
    assert not membro.tem_filtro_proprio()
    # a prova de que o campo e gravado e ignorado, na mesma rodada: o 999 esta
    # no yaml e nao esta no bloco
    assert membro.lp_base == 999
    bloco = (tmp_path / "out" / ("%s-parceiro.txt" % membro.token)).read_text(
        encoding="ascii")
    assert "999" not in bloco
    assert "apply local-preference" not in bloco
    # a nota aparece nas duas telas que renderizam o formulario: a do peer
    # vazio (GET /) e a do peer gravado
    for texto in (cliente.get("/").text,
                  cliente.get("/peer/%s" % membro.token).text):
        assert ('<span class="rotulo">grupo BGP <span class="tag">sem filtro '
                'proprio, herda do grupo</span></span>') in texto
        assert ('<legend>politica <span class="tag">o membro sem filtro '
                'proprio nao usa estes campos</span></legend>') in texto


# ---------------------------------------------------------------------
# O AS da rede, no topo da tela
#
# O campo grava a chave `asn` no topo do peers.yaml, e tudo que o app
# renderiza depois sai no AS novo. Sem a chave vale o de fabrica, e o
# caminho antigo continua sendo o que os outros testes ja exercitam.
# ---------------------------------------------------------------------


def gravar_asn(c, **kw):
    return c.post("/asn", data=kw, follow_redirects=False)


def test_o_cabecalho_mostra_o_as_de_fabrica(cliente):
    r = cliente.get("/")
    assert "AS64512" in r.text
    assert 'value="64512"' in r.text


def test_gravar_o_as_grava_a_chave_no_topo(cliente):
    r = gravar_asn(cliente, asn_rede="64500")
    assert r.status_code == 303
    assert peers_mod.carregar_asn(mod.PEERS_YAML).ASN == "64500"
    assert "AS64500" in cliente.get("/").text


def test_o_as_gravado_chega_na_config_gerada(cliente):
    gravar_asn(cliente, asn_rede="64500")
    assert salvar(cliente).status_code == 303
    token = peers_mod.carregar(mod.PEERS_YAML)[0].token
    bloco = cliente.get("/saida/%s" % token).text
    assert "bgp 64500" in bloco
    assert "64512" not in bloco
    assert "64500:1500" in bloco  # a origem do cliente, no namespace novo
    assert "64500:" in cliente.get("/base.txt").text


def test_o_as_de_32_bits_com_namespace_grava_as_duas_chaves(cliente):
    r = gravar_asn(cliente, asn_rede="264130", asn_politica="64500")
    assert r.status_code == 303
    rede = peers_mod.carregar_asn(mod.PEERS_YAML)
    assert (rede.asn, rede.politica) == (264130, 64500)
    texto = cliente.get("/").text
    assert "AS264130" in texto
    # o namespace declarado volta no campo, para o operador ver o que esta
    # gravado sem abrir o yaml
    assert 'value="64500"' in texto
    assert salvar(cliente).status_code == 303
    token = peers_mod.carregar(mod.PEERS_YAML)[0].token
    bloco = cliente.get("/saida/%s" % token).text
    assert "bgp 264130" in bloco
    assert "apply as-path 264130" in bloco
    assert "64500:1500" in bloco
    assert "264130:1500" not in bloco


def test_o_as_de_32_bits_sem_namespace_e_recusado_sem_estragar_o_arquivo(cliente):
    assert gravar_asn(cliente, asn_rede="64500").status_code == 303
    r = gravar_asn(cliente, asn_rede="264130")
    assert r.status_code == 200
    # o que falta e o namespace, entao e ele que fica marcado: o AS que o
    # operador digitou esta certo, e o 16 bits e que nao veio
    assert 'campo campo-com-erro" id="f-asn_politica"' in r.text
    assert "informe o namespace das standard" in r.text
    # a recusa e antes da escrita: o arquivo continua com o AS que estava bom
    assert peers_mod.carregar_asn(mod.PEERS_YAML).asn == 64500


def _erro_no_campo(texto, campo):
    """O que a tela mostra dentro do campo, ate o fim da etiqueta.

    O layout e o que prova a ancoragem: o erro e do valor que esta do lado
    dele, e nao do formulario inteiro. Uma assercao de "esta na pagina" nao
    distingue o erro no campo do AS do erro no campo do namespace.
    """
    return texto.split('id="f-%s"' % campo)[1].split("</label>")[0]


def test_o_namespace_fora_dos_16_bits_e_erro_no_proprio_campo(cliente):
    # o caso da tela: o ASN de 32 bits digitado nos dois campos. Ele cabe no
    # campo do AS e nao no das standard, e o erro tem que aparecer no campo
    # das standard, dizendo a faixa
    r = gravar_asn(cliente, asn_rede="264130", asn_politica="264130")
    assert r.status_code == 200
    assert "namespace das standard vai de 1 a 65535" in _erro_no_campo(
        r.text, "asn_politica")
    # a marca da borda vermelha e do mesmo campo: o do AS esta certo
    assert 'class="campo campo-com-erro" id="f-asn_politica"' in r.text
    assert 'class="campo campo-com-erro" id="f-asn_rede"' not in r.text
    # e nada foi gravado: sem a politica o Rede nem monta
    assert peers_mod.carregar_asn(mod.PEERS_YAML).asn == plan.ASN_PADRAO


def test_a_recusa_devolve_os_dois_campos_digitados(cliente):
    # o erro e do valor que esta na tela. Sem a devolucao o campo do AS
    # voltava com o 64512 gravado, e o erro do namespace ficava embaixo de
    # um campo que o operador nem tinha preenchido com aquilo
    gravar_asn(cliente, asn_rede="64500")
    r = gravar_asn(cliente, asn_rede="264130", asn_politica="264130")
    assert '<input name="asn_rede" value="264130"' in r.text
    assert '<input name="asn_politica" value="264130"' in r.text


def test_sem_recusa_o_campo_mostra_o_que_esta_gravado(cliente):
    # a devolucao vale so enquanto a recusa esta na tela: a pagina normal
    # segue lendo o peer.yaml, e nao um rascunho que ficou no formulario
    gravar_asn(cliente, asn_rede="264130", asn_politica="64500")
    texto = cliente.get("/").text
    assert '<input name="asn_rede" value="264130"' in texto
    assert '<input name="asn_politica" value="64500"' in texto
    # e um ASN de 16 bits nao escreve namespace nenhum no campo
    gravar_asn(cliente, asn_rede="64500")
    assert '<input name="asn_politica" value=""' in cliente.get("/").text


def test_o_as_fora_da_faixa_do_asn_e_erro_de_campo(cliente):
    # a faixa do AS da rede e a mesma que o validate exige dos peers e dos
    # grupos: o 23456 e o AS_TRANS, que a IANA reserva, e o que passa dos
    # 32 bits nao e ASN
    r = gravar_asn(cliente, asn_rede="23456")
    assert r.status_code == 200
    assert "ASN reservado pela IANA" in _erro_no_campo(r.text, "asn_rede")

    r = gravar_asn(cliente, asn_rede="99999999999")
    assert r.status_code == 200
    assert "ASN de 1 a 4294967294" in _erro_no_campo(r.text, "asn_rede")
    # as duas recusas sao antes da escrita: o arquivo segue com o de fabrica
    assert peers_mod.carregar_asn(mod.PEERS_YAML).asn == plan.ASN_PADRAO


def test_o_namespace_em_branco_apaga_a_chave(cliente):
    gravar_asn(cliente, asn_rede="264130", asn_politica="64500")
    # trocar para um ASN de 16 bits tira a necessidade do namespace, e o
    # campo vem em branco: a chave sai do arquivo em vez de ficar velha
    assert gravar_asn(cliente, asn_rede="64500").status_code == 303
    assert "asn_politica" not in mod.PEERS_YAML.read_text(encoding="utf-8")
    assert peers_mod.carregar_asn(mod.PEERS_YAML).ns == "64500"


def test_o_as_fora_de_digitos_e_erro_de_campo(cliente):
    r = gravar_asn(cliente, asn_rede="64x00")
    assert r.status_code == 200
    assert "so digitos" in r.text
    assert peers_mod.carregar_asn(mod.PEERS_YAML).asn == plan.ASN_PADRAO


def test_o_as_vazio_e_erro_de_campo(cliente):
    r = gravar_asn(cliente, asn_rede="")
    assert r.status_code == 200
    assert "informe o AS da rede" in r.text


def test_o_namespace_sem_o_as_e_erro_de_campo(cliente):
    # sem o AS da rede nao ha o que gravar: o namespace sozinho nao monta
    # um Rede, e o erro ancora no campo que falta
    r = gravar_asn(cliente, asn_rede="", asn_politica="64500")
    assert r.status_code == 200
    assert "informe o AS da rede" in r.text


def test_o_as_nao_salva_o_peer_que_estava_aberto(cliente):
    # o formulario do topo e um form a parte: gravando, ele nao leva junto
    # o que estava digitado no cadastro de baixo
    salvar(cliente, nome="Cliente ACME")
    r = gravar_asn(cliente, asn_rede="64500")
    assert r.status_code == 303
    assert len(peers_mod.carregar(mod.PEERS_YAML)) == 1


BLOCOS = {
    "blocos_v4": "38.252.64.0/22  64512:613 64512:621\n38.252.64.0/24  64512:211",
    "blocos_v6": "",
}


def test_o_formulario_le_uma_linha_por_prefixo(cliente):
    blocos = mod._blocos_do_formulario(BLOCOS)
    assert [(b.prefixo, b.communities) for b in blocos["v4"]] == [
        ("38.252.64.0/22", ["64512:613", "64512:621"]),
        ("38.252.64.0/24", ["64512:211"])]
    assert blocos["v6"] == []


def test_linha_fora_de_servico_fica_no_cadastro_marcada(cliente):
    """A linha `!-` nao tira o prefixo do cadastro: ela o poe fora de
    servico, com o tratamento que ele ja tinha. Tirar do ar nao pode
    custar o trabalho de escrever as communities."""
    blocos = mod._blocos_do_formulario(
        {"blocos_v4": "!- 38.252.64.0/24 64512:211\n38.252.64.0/22",
         "blocos_v6": ""})
    assert [(b.prefixo, b.communities, b.ativo) for b in blocos["v4"]] == [
        ("38.252.64.0/24", ["64512:211"], False),
        ("38.252.64.0/22", [], True)]


def test_a_marca_do_ausente_nao_vira_community(cliente):
    blocos = mod._blocos_do_formulario(
        {"blocos_v4": "38.252.66.0/24 64512:211  !- nao veio na consulta",
         "blocos_v6": ""})
    assert blocos["v4"][0].communities == ["64512:211"]


def test_o_texto_do_formulario_volta_marcado(cliente):
    salvo = peers_mod.Bloco(prefixo="38.252.66.0/24", communities=["64512:211"])
    texto = mod._texto_blocos({"v4": [salvo], "v6": []}, ausentes=[salvo])
    assert texto["v4"] == "38.252.66.0/24 64512:211  !- nao veio na consulta ao IRR"


def test_salvar_blocos_grava_no_yaml(cliente):
    r = cliente.post("/blocos", data=BLOCOS)
    assert r.status_code == 200
    lido = peers_mod.carregar_blocos(mod.PEERS_YAML)
    assert [b.prefixo for b in lido["v4"]] == ["38.252.64.0/22",
                                               "38.252.64.0/24"]


def test_salvar_blocos_escreve_o_arquivo_da_ordem_de_colagem(cliente,
                                                             tmp_path):
    """O bloco dos prefixos proprios e um artefato como os outros: o POST
    escreve o arquivo que o README lista na ordem de colagem, com o `rede`
    da requisicao."""
    cliente.post("/blocos", data=BLOCOS)
    ativos = mod._ativos(mod._blocos_do_formulario(BLOCOS))
    assert (tmp_path / "out" / "blocos.txt").read_text(
        encoding="ascii") == render.render_blocos(ativos)


def test_o_arquivo_do_bloco_nao_leva_o_prefixo_fora_de_servico(cliente,
                                                               tmp_path):
    cliente.post("/blocos", data={
        "blocos_v4": "38.252.64.0/22 64512:613\n!- 38.252.64.0/24 64512:211",
        "blocos_v6": ""})
    texto = (tmp_path / "out" / "blocos.txt").read_text(encoding="ascii")
    assert "ORIGEM-38-252-64-0_22" in texto
    assert "ORIGEM-38-252-64-0_24" not in texto


def test_o_bloco_recusado_nao_escreve_o_arquivo(cliente, tmp_path):
    # o mesmo desenho do quadro de saida: no caminho de erro nada seria
    # gravado, entao o arquivo tambem nao sai
    r = cliente.post("/blocos", data={"blocos_v4": "38.252.64.0/22 64512:673",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    assert not (tmp_path / "out" / "blocos.txt").exists()


def test_salvar_blocos_com_community_que_ninguem_le_nao_grava(cliente):
    r = cliente.post("/blocos", data={"blocos_v4": "38.252.64.0/22 64512:673",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    assert "classe 7" in r.text
    assert peers_mod.carregar_blocos(mod.PEERS_YAML) == {"v4": [], "v6": []}


def test_prefixo_fora_do_irr_salva_igual(cliente):
    """O gate e a consulta, e nao a verdade: o operador responde pelo que
    assume, e um prefixo digitado a mao nao pode ser recusado."""
    r = cliente.post("/blocos", data={"blocos_v4": "203.0.113.0/24",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    assert [b.prefixo for b in
            peers_mod.carregar_blocos(mod.PEERS_YAML)["v4"]] == ["203.0.113.0/24"]


def test_a_reconsulta_nao_grava_o_yaml(cliente, fake_bgpq4):
    """Quem grava e o salvar: a consulta so redesenha a tela."""
    salvo = {"blocos_v4": "203.0.113.0/24 64512:211", "blocos_v6": ""}
    cliente.post("/blocos", data=salvo)
    cliente.post("/blocos/bgpq4", data=salvo)
    lido = peers_mod.carregar_blocos(mod.PEERS_YAML)
    assert [b.prefixo for b in lido["v4"]] == ["203.0.113.0/24"]
    assert "45.169.232.0/22" not in [
        b.prefixo for b in lido["v4"]], "a consulta nao pode ter gravado"


def test_prefixo_torto_nao_derruba_a_tela(cliente):
    """O operador tem que ler a mensagem do validate, e nao um 500."""
    r = cliente.post("/blocos", data={"blocos_v4": "torto 64512:211",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    assert "CIDR" in r.text


def test_a_reconsulta_com_prefixo_torto_tambem_nao_derruba(cliente,
                                                           fake_bgpq4,
                                                           monkeypatch):
    contexto = contexto_da_rota(monkeypatch)
    r = cliente.post("/blocos/bgpq4", data={"blocos_v4": "torto",
                                            "blocos_v6": ""})
    assert r.status_code == 200
    assert "CIDR" in r.text
    assert not contexto()["saida_blocos"]


def test_o_prefixo_e_canonizado_no_formulario(cliente):
    """Um v6 em caixa alta, que e como o VRP imprime, tem que casar com o
    que a consulta devolve em caixa baixa."""
    blocos = mod._blocos_do_formulario(
        {"blocos_v4": "38.252.64.7/22", "blocos_v6": "2804:36B4::/32"})
    assert blocos["v4"][0].prefixo == "38.252.64.0/22"
    assert blocos["v6"][0].prefixo == "2804:36b4::/32"


def test_a_linha_com_dois_pontos_guarda_o_tratamento(cliente):
    """Tirar do ar nao pode custar o trabalho de escrever as communities.

    O texto da tela sai do `texto_blocos` do contexto, e nao de `r.text`:
    quem imprime essa chave no HTML e a secao da Task 8, e as duas
    assercoes sobre a pagina vao com ela.
    """
    r = cliente.post("/blocos", data={"blocos_v4": "!- 38.252.64.0/24 64512:211",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    lido = peers_mod.carregar_blocos(mod.PEERS_YAML)
    assert [(b.prefixo, b.communities, b.ativo) for b in lido["v4"]] == [
        ("38.252.64.0/24", ["64512:211"], False)]
    contexto = mod._contexto(None, blocos=lido)
    assert contexto["texto_blocos"]["v4"] == "!- 38.252.64.0/24 64512:211"
    assert "ORIGEM-38-252-64-0_24" not in (contexto["saida_blocos"] or "")


def test_o_fora_de_servico_nao_entra_na_saida(cliente):
    r = cliente.post("/blocos", data={
        "blocos_v4": "38.252.64.0/22 64512:613\n!- 38.252.64.0/24 64512:211",
        "blocos_v6": ""})
    assert r.status_code == 200
    contexto = mod._contexto(None,
                             blocos=peers_mod.carregar_blocos(mod.PEERS_YAML))
    assert "ORIGEM-38-252-64-0_22" in contexto["saida_blocos"]
    assert "ORIGEM-38-252-64-0_24" not in contexto["saida_blocos"]


def test_endereco_sem_barra_e_recusado(cliente):
    """Sem a guarda, o ip_network aceita o endereco cru e devolve /32: o
    prefixo sairia anunciado como host route, sem erro nenhum."""
    r = cliente.post("/blocos", data={"blocos_v4": "38.252.64.0 64512:211",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    assert "CIDR" in r.text
    assert peers_mod.carregar_blocos(mod.PEERS_YAML) == {"v4": [], "v6": []}


def test_o_remover_cobre_o_prefixo_fora_de_servico(cliente):
    """O prefixo que o operador acabou de tirar do ar e o que mais
    provavelmente ainda esta configurado no equipamento: sem ele no
    remover, o tira do ar e cola o remover nao tiraria nada."""
    r = cliente.post("/blocos", data={"blocos_v4": "!- 38.252.64.0/24 64512:211",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    contexto = mod._contexto(None,
                             blocos=peers_mod.carregar_blocos(mod.PEERS_YAML))
    remover = contexto["saida_blocos_remover"]
    assert "undo xpl route-filter ORIGEM-38-252-64-0_24" in remover
    assert "xpl route-filter ORIGEM-38-252-64-0_24" not in (
        contexto["saida_blocos"] or "")


def contexto_da_rota(monkeypatch):
    """O contexto que a rota mandou para o template, para o teste ler.

    As chaves que a secao da Task 8 imprime saem daqui, e nao de `r.text`:
    com a secao ainda por vir, o que a tela vai mostrar e este valor. O
    espiao tambem e o que deixa ler o `erros` que a rota passou, que e o
    que decide se a saida sai.
    """
    vistos = {}
    real = mod._contexto

    def espiao(request, *a, **k):
        vistos["ultimo"] = real(request, *a, **k)
        return vistos["ultimo"]

    monkeypatch.setattr(mod, "_contexto", espiao)
    return lambda: vistos["ultimo"]


def test_a_saida_nao_sai_no_caminho_de_erro(cliente, monkeypatch):
    """A saida e uma previa do que seria gravado, e com erro nada seria:
    o operador nao pode copiar para o equipamento um bloco de um prefixo
    que a tela acabou de recusar."""
    contexto = contexto_da_rota(monkeypatch)
    r = cliente.post("/blocos", data={"blocos_v4": "38.252.64.0 64512:211",
                                      "blocos_v6": ""})
    assert "CIDR" in r.text
    assert not contexto()["saida_blocos"]
    r = cliente.post("/blocos", data={"blocos_v4": "38.252.64.0/22 64512:613",
                                      "blocos_v6": ""})
    assert r.status_code == 200
    assert "ORIGEM-38-252-64-0_22" in contexto()["saida_blocos"]


def test_a_pagina_tem_a_secao_dos_blocos(cliente):
    r = cliente.get("/")
    assert 'id="blocos"' in r.text
    assert 'name="blocos_v4"' in r.text
    assert 'name="blocos_v6"' in r.text
    assert 'action="/blocos"' in r.text
    assert 'action="/blocos/bgpq4"' in r.text


def test_a_secao_mostra_o_que_esta_salvo(cliente):
    """A textarea sai com um espaco entre os campos, e nao com os dois que
    o operador pode ter digitado: separador de espaco no texto e do
    formulario, e nao do formato."""
    cliente.post("/blocos", data=BLOCOS)
    r = cliente.get("/")
    assert "38.252.64.0/22 64512:613 64512:621" in r.text
    assert "38.252.64.0/24 64512:211" in r.text


def test_a_secao_mostra_a_saida_depois_de_salvar(cliente):
    r = cliente.post("/blocos", data=BLOCOS)
    assert "xpl route-filter ORIGEM-38-252-64-0_22" in r.text
    assert "undo xpl route-filter ORIGEM-38-252-64-0_22" in r.text


def test_o_botao_de_consultar_manda_o_forcar(cliente):
    r = cliente.get("/")
    assert "/blocos/bgpq4?forcar=1" in r.text


def test_a_secao_nao_quebra_a_pagina_sem_bloco(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert 'id="blocos"' in r.text


def test_o_alerta_do_topo_leva_ao_campo_do_bloco(cliente):
    """Os dois campos do bloco entram em `ancoraveis`, como os do peer: o
    resumo do topo vira link, e o link chega na caixa do campo."""
    r = cliente.post("/blocos", data={"blocos_v4": "38.252.64.0 64512:211",
                                      "blocos_v6": ""})
    assert 'href="#f-blocos_v4"' in r.text
    assert 'id="f-blocos_v4"' in r.text


# Os tres que vieram da Task 7. Eles afirmam sobre a lista mesclada na tela,
# e a tela so a mostra a partir daqui.

def test_a_reconsulta_preserva_o_tratamento_do_prefixo_que_ficou(
        cliente, fake_bgpq4):
    """O bgpq4 de mentira devolve 45.169.232.0/22 e 45.169.236.0/23 em v4.
    O primeiro ja estava salvo com tratamento, e o segundo e novo."""
    salvo = {"blocos_v4": "45.169.232.0/22  64512:613", "blocos_v6": ""}
    cliente.post("/blocos", data=salvo)
    r = cliente.post("/blocos/bgpq4", data=salvo)
    assert r.status_code == 200
    assert "45.169.232.0/22 64512:613" in r.text
    assert "45.169.236.0/23" in r.text


def test_a_reconsulta_marca_o_prefixo_que_sumiu(cliente, fake_bgpq4):
    salvo = {"blocos_v4": "203.0.113.0/24 64512:211", "blocos_v6": ""}
    cliente.post("/blocos", data=salvo)
    r = cliente.post("/blocos/bgpq4", data=salvo)
    assert "nao veio na consulta ao IRR" in r.text
    assert "203.0.113.0/24 64512:211" in r.text


def test_bgpq4_fora_do_ar_nao_perde_a_lista_do_operador(cliente,
                                                        monkeypatch):
    def explodir(*a, **k):
        raise RuntimeError("bgpq4 nao esta no PATH: e dependencia de execucao")

    monkeypatch.setattr(prefixes, "coletar", explodir)
    r = cliente.post("/blocos/bgpq4", data=BLOCOS)
    assert r.status_code == 200
    assert "bgpq4" in r.text
    assert "38.252.64.0/22" in r.text
