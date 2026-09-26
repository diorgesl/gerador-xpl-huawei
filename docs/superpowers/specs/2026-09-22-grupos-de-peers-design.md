# Grupos de peers — AS64512

2026-09-22

## Problema

Hoje cada peer do `bgpgen` é uma sessão isolada: um `peer <ip> ...` próprio, com seu próprio par de route-filters de import/export. Isso não bate com três situações reais da operação:

- Um upstream chega por 2 ou 3 sessões redundantes (mesmo ASN, mesma política).
- Um downstream (cliente) chega por múltiplas sessões redundantes, pela mesma razão.
- Vários parceiros distintos (ASNs diferentes) compartilham uma política de import/export idêntica, como o legado já faz hoje com `group PARCEIROS_CDN external` — um filtro só, aplicado a todos os membros, com a possibilidade de um membro específico ter filtro próprio por cima.

Sem isso, cada sessão redundante ou cada parceiro novo duplica o mesmo route-filter com um token diferente, e o filtro do "grupo" (na cabeça do operador) nunca está de fato garantido idêntico entre os membros — diverge na primeira edição feita num só.

Este documento estende o design do gerador (`2026-09-21-gerador-sessoes-bgp-design.md`) com uma camada de **grupo BGP** (o `group` do VRP), mantendo o requisito duro que o app já tem: gerar/editar um peer, ou um grupo, não pode mexer na saída de outro.

## Escopo

### O que entra

- CRUD de grupo (criar, editar, excluir), espelhando o fluxo de peer.
- Um peer pode pertencer a um grupo. Grupo e peer continuam existindo mesmo sem o outro (peer sem grupo funciona como hoje; grupo sem peer nenhum ainda gera o próprio arquivo).
- Os cinco tipos (cliente, parceiro, upstream, IX, PNI) podem ter grupo. Um grupo pertence a **um** tipo só; só peers desse tipo podem entrar nele.
- Grupo com ASN fixo (sessões redundantes do mesmo peer lógico, ex. upstream) ou sem ASN (membros com ASN próprio, ex. vários parceiros).
- Override por peer: um membro pode ter filtro de import e/ou export próprio, que o VRP aplica no lugar do filtro do grupo só para aquela direção e aquele peer.
- Saída em dois artefatos por grupo, no mesmo espírito do bloco base/bloco do peer: o **bloco do grupo** (`out/grupo-<nome>.txt`) e o **bloco do peer membro**, que fica mais enxuto que o de um peer avulso.

### O que não entra

- Grupo misturando tipos diferentes (decidido: um tipo por grupo).
- Grupo IBGP (route-reflector). O legado usa `group IBGP-RR internal` para isso, mas é sessão interna, fora do escopo do `bgpgen`, que hoje só cobre EBGP.
- Migração automática dos peers já cadastrados em `peers.yaml` para dentro de um grupo. Quem quiser agrupar peers existentes edita cada um e escolhe o grupo, um de cada vez, pelo mesmo formulário.

## Modelo de dados

### `Grupo`, entidade nova em `app/peers.py`

Os campos são os de **política** que hoje moram no `Peer`, menos os que são por sessão:

| Campo | Vem de | Observação |
| --- | --- | --- |
| `id` | novo | igual ao do peer: numérico, aloca o primeiro livre, é o que identifica o registro |
| `nome` | novo | o nome do `group` no VRP, ex. `PARCEIROS_CDN`; é o token do grupo |
| `tipo` | igual ao do peer | um de `TIPOS`; fixa qual template/política o grupo usa |
| `asn` | novo, opcional | setado quando todos os membros são o mesmo ASN (upstream/downstream redundante); vazio quando os membros têm ASN próprio (vários parceiros). Setado, vira `peer <NOME> as-number <ASN>` no bloco do grupo e os membros não repetem `as-number`. Vazio, cada peer membro declara o próprio |
| `classe` | igual ao do peer | só cliente/parceiro |
| `lp_base`, `origem`, `pop`, `aprendizado` | igual ao do peer | os campos que hoje decidem o carimbo informativo e a LP |
| `ap_block`, `ap_te`, `ap_allowed`, `ap_prefer` | igual ao do peer | por tipo, como hoje |
| `prepend_base`, `bh_upstream`, `default_route` | igual ao do peer | |
| `bfd`, `graceful_restart`, `timer_keepalive`, `timer_hold` | igual ao do peer | |
| `prefixos` (v4/v6) | novo, opcional, só `cliente`/`parceiro` | **ver "Confinamento de prefixo" abaixo** — é a exceção à regra "sem política por membro" |

Fora do grupo: `communities`/`large_communities` (a `CL-PEER-<T>`) e `route_limit` continuam **só no peer**, mesmo quando ele está num grupo — são valores por sessão, não por grupo.

### `Peer`, campo novo

`grupo_id: int | None`. Quando setado:

- Os campos de política que passaram para o `Grupo` (`classe`, `lp_base`, `origem`, `pop`, `aprendizado`, `ap_*`, `prepend_base`, `bh_upstream`, `default_route`, `bfd`, `graceful_restart`, timers) **deixam de valer** — o app não os lê do peer quando ele tem grupo, e o formulário não os mostra.
- `asn` só é obrigatório no peer se o grupo não tiver `asn` próprio.
- `communities`, `large_communities`, `route_limit`, `descricao`, `apelido`, `sessoes` continuam do peer, sempre.
- `prefixos` do peer: só relevante fora de grupo, ou dentro de um grupo cujo `tipo` não usa `prefixos` de grupo (ver abaixo).

### Confinamento de prefixo dentro de um grupo `cliente`/`parceiro`

Isto ficou em aberto na conversa e a spec assume uma decisão — **confirmar na revisão**:

- **Grupo com `prefixos` preenchido** (o caso "mesmo cliente, 2-3 links redundantes"): o filtro de import do grupo confina ao `PL-CUST-<G>-<fam>` do jeito que o cliente avulso confina hoje, só que o prefix-list é do grupo, não do peer — os membros são a mesma organização, então o bloco é o mesmo nos três links.
- **Grupo com `prefixos` vazio** (o caso "vários parceiros distintos", tipo `PARCEIROS_CDN` do legado): a confinamento de prefixo simplesmente não entra no filtro do grupo — ele aceita o que cada membro anunciar, sujeito só ao `IMPORT-SANITY`/anti-leak, igual ao exemplo real. Nenhuma checagem por membro dentro do filtro do grupo.

Isso resolve os dois casos que você descreveu com o mesmo campo, sem `if peer-address eq <ip>` dentro do filtro do grupo em nenhum dos dois.

## Rotas e UI

Espelha o fluxo de peer (`app/app.py`):

| Rota | Peer (hoje) | Grupo (novo) |
| --- | --- | --- |
| Novo | `GET /peer/novo` | `GET /grupo/novo` |
| Editar | `GET /peer/{token}` | `GET /grupo/{nome}` |
| Salvar | `POST /peer` | `POST /grupo` |
| Excluir | `POST /peer/{token}/excluir` | `POST /grupo/{nome}/excluir` |
| Saída | `GET /saida/{token}` | `GET /saida/grupo/{nome}` |

No formulário de peer: um `select` "grupo", populado só com grupos do `tipo` corrente (trocar o tipo limpa a seleção). Selecionar um grupo esconde os campos de política que passaram a ser do grupo (mesma lógica de "campo derivado" que já existe hoje para o tipo, só que agora escondendo em vez de só preencher).

Excluir um grupo com peers membros: mesma lógica de confirmação que hoje existe para excluir peer, mas listando os membros afetados — a exclusão não deve ser silenciosa quando ainda há peer apontando pro `grupo_id`.

## Geração — preservando "gerar um não mexe no outro"

Dois artefatos novos, nos mesmos moldes do "bloco base" / "bloco do peer" que o design de 2026-09-21 já define:

### Bloco do grupo — `out/grupo-<nome>.txt`

- `group <NOME> external`
- `peer <NOME> as-number <ASN>` (só se o grupo tiver ASN)
- Os sets e route-filters do grupo, com o mesmo objeto-naming que o peer já usa, trocando `<T>` (token do peer) por `<G>` (nome do grupo): `PL-CUST-<G>-<fam>` (se houver `prefixos`), `<PREFIXO-DO-TIPO>-<G>-IMPORT-<fam>`, `<PREFIXO-DO-TIPO>-<G>-EXPORT-<fam>` (`CUST-` para cliente/parceiro, `UP-` para upstream, `IX-`/`PNI-` para os outros dois — os mesmos prefixos que a tabela "Nomes" do design de 2026-09-21 já usa).
- Na família: `peer <NOME> enable`, `peer <NOME> route-filter <...>-IMPORT-<fam> import`, `peer <NOME> route-filter <...>-EXPORT-<fam> export`.
- **Reaproveita a lógica de política que já existe por tipo** (a mesma tabela "Ingress por tipo" / "Egress por tipo" do design anterior) — o `render.py` trata o `Grupo` como um "peer sem sessão", alimentando o mesmo template Jinja do tipo. Evita duplicar a lógica de política em dois lugares.
- Sem `CL-PEER-<G>`/`APPLY-PEER-<G>`: essa é a lista de comunidade por sessão, e sessão é coisa de peer, não de grupo.

### Bloco do peer membro — `out/<token>-<tipo>.txt`

Fica mais enxuto que o de hoje:

- `peer <ip> as-number <ASN>` — só se o grupo não tiver ASN próprio.
- `peer <ip> description <descricao>`.
- Na família: `peer <ip> enable`, `peer <ip> group <NOME>`.
- `peer <ip> group <NOME>` continua presente mesmo quando há override — é o que mantém o peer como membro pra tudo que não foi sobrescrito (enable, `advertise-community`, timers herdados etc.). Se o peer tiver `communities`/`large_communities` (a `CL-PEER-<T>`) **ou** filtro de override: o par `CL-PEER-<T>`/`APPLY-PEER-<T>` de sempre, mais uma linha `peer <ip> route-filter <NOME-DO-FILTRO> import` e/ou `export`, **ao lado de** `peer <ip> group <NOME>`, só na(s) direção(ões) que o peer sobrescreve. O VRP usa o comando de peer em vez do de grupo naquela direção quando os dois existem pra mesma sessão — não precisa de `call` nem de nada especial no gerador. É exatamente o que o exemplo real de `PARCEIROS_CDN` faz: o membro com export próprio mantém `peer <ip> group PARCEIROS_CDN` e ganha `peer <ip> route-policy ... export` ao lado.
- Continua isolado: criar/editar um peer membro não regera nem re-cola o bloco do grupo, e vice-versa. Adicionar um membro novo a um grupo já colado é aditivo — só o arquivo do peer novo precisa ser colado, igual ao exemplo real de `PARCEIROS_CDN` que você mandou.

## Nomes — extensão da tabela do design de 2026-09-21

| Grupo (tipo) | Objetos |
| --- | --- |
| Cliente/Parceiro | `PL-CUST-<G>-<fam>` (se houver `prefixos`), `CUST-<G>-IMPORT-<fam>`, `CUST-<G>-EXPORT-<fam>` |
| Upstream | `AP-BLOCK-<G>`, `AP-TE-PREFER-<G>`, `PL-TE-PREFER-<fam>`, `UP-<G>-IMPORT-<fam>`, `UP-<G>-EXPORT-<fam>` |
| IX | `AP-IX-<G>` (opcional), `IX-<G>-IMPORT-<fam>`, `IX-<G>-EXPORT-<fam>` |
| PNI | `AP-<G>-ALLOWED`, `PNI-<G>-IMPORT-<fam>`, `PNI-<G>-EXPORT-<fam>` |

Sem `CL-NOADV-<G>`/`LC-NOADV-<G>`: esse par existe hoje porque tem o eixo "não anunciar pra este peer" (`5<ID>0`), e `ID` é do peer, não do grupo. Um grupo sem ID próprio não tem como formar esse eixo — fica `CL-NOADV-<tipo>` genérico (sem o terceiro elemento) quando o grupo precisar do escopo de anúncio, ou cada override de peer resolve isso individualmente se precisar bloquear um peer específico.

## Validação — regras novas

| Regra | Por quê |
| --- | --- |
| Nome do grupo único, `[A-Z0-9_]`, até 32 caracteres | nome de objeto `group` do VRP |
| `tipo` do peer bate com `tipo` do grupo escolhido | um grupo é de um tipo só |
| Peer com `grupo_id` não pode preencher campo de política que virou do grupo | evita divergência silenciosa entre o que o formulário mostra e o que o gerador usa |
| Peer sem grupo e sem `asn` é erro (como hoje); peer com grupo e grupo sem `asn` também exige `asn` no peer | precisa de ASN de algum lugar pra declarar a sessão |
| Excluir grupo com peer(s) apontando pra ele exige confirmação explícita listando os membros | mesmo espírito da exclusão de peer |

## Testes — extensão de `tests/`

- `test_peers.py` / `test_validate.py`: CRUD de grupo, as regras da tabela acima.
- `test_render.py`: por tipo, um caso de grupo com `asn` e um sem; um membro sem override (bloco enxuto) e um membro com override de import, de export, e dos dois; grupo sem membro nenhum ainda renderiza o próprio bloco; grupo `cliente`/`parceiro` com `prefixos` preenchido vs vazio.
- Propriedade a cobrir, igual à que o design de 2026-09-21 já pede pra peer: gerar o grupo não muda a saída de nenhum peer membro, e gerar/editar um peer membro não muda a saída do grupo nem a de outro membro.

## Decisões

| Decisão | Escolha | Motivo |
| --- | --- | --- |
| Grupo mistura tipos? | não, um tipo por grupo | mantém a lógica de política já existente por tipo, sem template genérico novo |
| CL-PEER-<T> em membro de grupo | continua por peer, nunca por grupo | é comunidade de sessão, e sessão é do peer |
| Override vira "filtro próprio" | igual ao que o peer avulso já gera hoje pra aquele tipo, só que anexado via `peer <ip> route-filter ... import/export` em vez de auto-suficiente | reaproveita o template do tipo sem inventar mecanismo de `call` novo |
| Confinamento de prefixo em grupo cliente/parceiro | campo `prefixos` no grupo, opcional | cobre "mesmo cliente redundante" (preenchido) e "vários parceiros" (vazio) com o mesmo campo |
| Saída do grupo | arquivo próprio, `out/grupo-<nome>.txt` | preserva "gerar um não mexe no outro" |

## Pendências

- **Confinamento de prefixo em grupo é uma decisão desta spec, não uma resposta que você deu explicitamente** — a pergunta que fiz foi sobre "grupo dispensa prefix-list por membro" (você confirmou), e o campo `prefixos` no grupo (prefixo compartilhado por todos os membros, não por membro) é uma extensão minha em cima disso pra cobrir o caso do upstream/downstream redundante. Confirmar na revisão.
- **Escopo de anúncio (`CL-NOADV`) sem o eixo por peer em grupo** fica em aberto: o design acima descarta o terceiro elemento (`5<ID>0`) por falta de ID de grupo, mas não define se cada tipo de grupo (upstream/IX/PNI) precisa desse eixo de bloqueio por membro de alguma outra forma. Decide-se quando o primeiro grupo desses tipos for cadastrado de verdade.
- **`ap_prefer` de IX em grupo**: hoje é lista de ASNs que ganham LP 195 em vez de 190 — isso já funciona igual em grupo, porque a condição é `as-path peer-is`, não depende de qual sessão física carregou a rota. Só registrando que não precisa de tratamento especial.
- Implementar primeiro para `parceiro` (o caso mais claro, com exemplo real) e só depois estender aos outros quatro tipos, ou implementar os cinco de uma vez — decisão de sequenciamento pra hora de escrever o plano de implementação, não desta spec.
