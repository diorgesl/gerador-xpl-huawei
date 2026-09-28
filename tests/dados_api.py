"""Formularios em JSON que os testes da API reusam.

Os valores sao os dos formularios do test_app.py, no formato da API: texto nos
escalares, lista nas listas, booleano nas caixas. Todos passam na validacao.
"""

# o tenant que a suite usa; quem precisa de outro passa o proprio asn no
# `params`, que vence o padrao do ClienteComAsn
ASN_DE_TESTE = 64512

CLIENTE = {
    "nome": "Cliente ACME", "tipo": "cliente", "asn": "268127",
    "classe": "residencial", "descricao": "CLIENTE-AS268127",
    "lp_base": "300", "origem": "1110", "pop": "2001", "route_limit": "50",
    "prefixos_v4": ["45.169.232.0/22"],
    "sessao_v4_local": "198.51.100.1", "sessao_v4_remoto": "198.51.100.2",
}

UPSTREAM = {
    "apelido": "OPERADORA", "nome": "OPERADORA-20G", "tipo": "upstream",
    "asn": "14840", "descricao": "OPERADORA-20G", "lp_base": "100",
    "origem": "1400", "aprendizado": "3100", "route_limit": "1500000",
    "timer_keepalive": "10", "timer_hold": "30", "bh_upstream": "14840:666",
    "sessao_v4_local": "203.0.113.2", "sessao_v4_remoto": "203.0.113.1",
}

IX = {
    "apelido": "IX-SP", "nome": "IX.br Sao Paulo", "tipo": "ix",
    "asn": "26162", "descricao": "IX-SP-AS26162", "lp_base": "190",
    "origem": "1300", "aprendizado": "3010", "ix_id": "9999",
    "route_limit": "500000", "ap_prefer": ["15169"],
    "sessao_v4_local": "187.16.192.1", "sessao_v4_remoto": "187.16.192.2",
}

GRUPO_PARCEIROS = {
    "nome": "PARCEIROS_CDN", "tipo": "parceiro", "classe": "transito",
    "lp_base": "300", "origem": "1100", "pop": "2001",
}

GRUPO_UPSTREAM = {
    "nome": "OPERADORA", "tipo": "upstream", "asn": "14840",
    "lp_base": "100", "origem": "1400", "aprendizado": "3100",
    "communities": ["14840:9133"],
}

BLOCOS = {
    "v4": "38.252.64.0/22  64512:613 64512:621\n38.252.64.0/24  64512:211",
    "v6": "",
}


def membro_de(grupo_id):
    """Um parceiro sem politica propria, que herda tudo do grupo."""
    return dict(CLIENTE, tipo="parceiro", classe="", origem="",
                prefixos_v4=[], grupo_id=str(grupo_id))


def arvore(raiz):
    """O retrato do disco: os bytes de cada arquivo, por caminho relativo.

    Serve para conferir que uma recusa ou uma previa nao mexeu em nada.
    """
    return {str(p.relative_to(raiz)): p.read_bytes()
            for p in sorted(raiz.rglob("*")) if p.is_file()}


def caminho_tenant(tmp_path, asn=ASN_DE_TESTE):
    """O arquivo do tenant na pasta que a fixture `api_anonimo` patcheia.

    O nome do arquivo E o ASN, e e por ele que a API acha o tenant: toda
    gravacao que um teste faz por fora da rota tem que cair aqui, senao a
    rota procura o tenant em outro lugar e responde 404.
    """
    pasta = tmp_path / "peers"
    pasta.mkdir(exist_ok=True)
    return pasta / ("%d.yaml" % asn)
