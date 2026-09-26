# Grupo de upstream, IX e PNI — AS64512

2026-09-22

## Problema

O design de `2026-09-22-grupos-de-peers-design.md` decidiu, na linha "O que entra", que **os cinco tipos** podem ter grupo. A implementação entregou dois: `cliente` e `parceiro`. `validate.TIPOS_COM_GRUPO` (em `app/validate.py`) recusa explicitamente o resto com "grupo ainda so suporta cliente e parceiro", enquanto o `select` de tipo em `templates/pagina_grupo.html` já oferece `upstream`. Escolher a opção que o formulário mostra produz um erro que o formulário mesmo provocou.

Isso dói em três situações reais que o grupo existe para resolver, e que hoje continuam sem solução:

- **Upstream por várias sessões.** O mesmo trânsito chega por 2 ou 3 links. Hoje cada link é um `Peer` avulso que repete o mesmo filtro de import/export com um token diferente, e a política dos três diverge na primeira edição feita num só.
- **IX por vários membros.** Um IX com sessão contra dois route servers, ou um route server mais uma sessão bilateral, quer a mesma política de IX nos dois.
- **PNI por vários links.** Uma CDN que anuncia por dois links diretos quer uma allowlist e uma LP só.

Este documento completa o que o design anterior prometeu. Ele não inventa estrutura nova: estende a que já foi construída.

## O que já existe e o que falta

O `Grupo` em `app/peers.py` nasceu com quase todos os campos dos cinco tipos. Cruzando o que cada template lê contra o dataclass:

| Template | Campos que faltam no `Grupo` |
| --- | --- |
| `upstream.txt.j2` | `aprendizado`, `te_prefixos`, `communities`, `large_communities` |
| `ix.txt.j2` | `aprendizado`, `ix_id` |
| `pni.txt.j2` | nenhum |

`ap_block`, `ap_te`, `ap_allowed`, `ap_prefer`, `prepend_base` e `bh_upstream` já estão lá, e o `de_dict` do `Grupo` descarta chave desconhecida, então o `peers.yaml` de hoje carrega sem migração depois de o dataclass crescer.

`familias()` **não** entra, apesar de os três templates de peer a usarem. Ela devolve as famílias que têm sessão, e grupo não tem sessão: quem tem é o membro. O `grupo_cliente.txt.j2` já resolve isso declarando as duas famílias sempre (`{% for fam in ("v4", "v6") %}`), e os três templates novos fazem igual.

## Escopo

### O que entra

- Os três tipos restantes com grupo: `upstream`, `ix` e `pni`.
- Membros: um peer de qualquer um dos cinco tipos pode apontar para um grupo do próprio tipo, com a mesma herança que o `cliente.txt.j2` já implementa.
- Espaço de identificadores compartilhado entre peers e grupos, com recusa de colisão nos dois sentidos.
- O quadro "ao criar" na tela do grupo, para o tipo que usa `APPLY-PEER`.
- Atualização do `PLANO.md` com a convenção de identificador e a existência de grupo nos cinco tipos.

### O que não entra

- Grupo misturando tipos. Continua um tipo por grupo, como o design anterior decidiu.
- Migração automática de id no `peers.yaml`. A colisão vira erro visível e quem renumera é o operador, pela tela.
- Grupo IBGP, pelo mesmo motivo do design anterior.
- Renumerar o id de um grupo sozinho, em tempo de carga. Decisão registrada abaixo.

## Espaço de identificadores

Esta seção resolve a pendência "Escopo de anúncio (`CL-NOADV`) sem o eixo por peer em grupo" do design anterior. Aquela pendência partia de "um grupo sem ID próprio", e o grupo tem `id` desde a tabela de modelo de dados do mesmo documento. O que faltava não era o campo, era o espaço de nomes.

`plan.c5ppa` monta `"64512:5%02d%d"`, ou seja dois dígitos de identificador mais um dígito de papel. São **100 identificadores no total**, e esse eixo é usado por `plan.noadv(tipo, id)`, que é o terceiro elemento do `CL-NOADV-<T>`, e por `CL-5PPA-<id>` no egress de upstream.

Hoje `peers.proximo_id` e `peers.proximo_id_grupo` sorteiam cada um a partir do zero, sobre conjuntos separados, com `MAX_PEERS = 100` e `MAX_GRUPOS = 100`. Um grupo e um peer podem receber o mesmo número. O `peers.yaml` atual já tem um caso: o grupo `PARCEIROS` e o peer `BRDIGITAL-20G` estão os dois no id 0. É inofensivo enquanto o grupo for `cliente`/`parceiro`, porque esse formato de grupo nunca emite `5PPA`, e deixa de ser no primeiro grupo de `upstream`, `ix` ou `pni`.

**Decisão.** Uma sequência só. `MAX_PEERS` e `MAX_GRUPOS` viram um `MAX_IDS = 100`, e o alocador recebe as duas listas para calcular o primeiro identificador livre. A colisão é recusada na validação, nos dois sentidos:

- `validar_grupo` recusa quando algum peer já usa o `grupo.id`, e recusa `grupo.id` fora de 0 a 99 (hoje ele não checa faixa nenhuma).
- `validar` recusa quando algum grupo já usa o `peer.id`.

A recusa segue o que o app já faz em toda parte: o grupo com membros pendurados, o ASN do membro divergente do grupo, o nome de grupo repetido. O app mostra o motivo e o operador decide, em vez de o arquivo mudar por baixo dele. Renumerar é barato: o id do grupo só aparece hoje num comentário de cabeçalho, em `_macros.j2`, então trocar o número do `PARCEIROS` não muda uma linha de configuração.

## Modelo de dados

`Grupo` ganha cinco campos, todos com default que não quebra o que está gravado:

| Campo | Tipo | Por quê |
| --- | --- | --- |
| `aprendizado` | `int \| None` | o 3xxx do ponto de aprendizado, exigido por `upstream` e `ix`. O design anterior já o listava na tabela do `Grupo`; a implementação não o criou |
| `ix_id` | `int \| None` | o id do IX no PeeringDB, que vira a large-community `1001:<ix_id>` e é exigido por `ix` |
| `te_prefixos` | `dict` por família | as listas `PL-TE-PREFER-<G>-<U>` do TE de upstream |
| `communities` | `list` | o conteúdo da `CL-PEER-<G>` |
| `large_communities` | `list` | o conteúdo da `LC-PEER-<G>` |

`para_dict` acompanha. `de_dict` não precisa de mudança: ele já filtra pelas chaves de `__dataclass_fields__`.

### `communities` no grupo, contra a decisão do design anterior

O design anterior decidiu que `communities`/`large_communities` ficam **só no peer**, porque "é comunidade de sessão, e sessão é do peer", e que o grupo não tem `CL-PEER-<G>`/`APPLY-PEER-<G>`. Esta spec reverte essa parte, e o motivo é a diferença entre os tipos.

Para um cliente, a community descreve a sessão: cada link pode ter a sua, e faz sentido que o membro carregue a dele. Para um upstream, a community descreve a **rede remota**, não o link. Dois links para o mesmo trânsito levam a mesma community, e repeti-la em cada membro é exatamente a duplicação que o grupo existe para eliminar. O `upstream.txt.j2` fecha o export chamando `m.apply_peer(peer)` na linha 170, então um grupo de upstream sem esse par não tem como gerar o bloco.

A reversão não muda nada para `cliente` e `parceiro`: os campos ficam vazios por default, e um grupo de downstream sem comunidade continua sem gerar `APPLY-PEER`, igual ao que o `grupo_cliente.txt.j2` faz hoje.

## Geração

### Macros de alvo duplo

O `_macros.j2` já tem o padrão pronto. `prefix_lists_downstream`, `ap_cust_downstream` e `filtro_downstream_import`/`filtro_downstream_export` recebem `alvo` em vez de `peer`, e é por isso que o `grupo_cliente.txt.j2` consegue chamá-los passando um `Grupo`. O `filtro_downstream_import` já recebe um `chamar_apply_peer` booleano, que o grupo passa como falso e o membro como verdadeiro.

O miolo de `upstream.txt.j2`, `ix.txt.j2` e `pni.txt.j2` sai para macros com a mesma assinatura:

| Macro nova | Substitui o miolo de |
| --- | --- |
| `filtro_upstream_import(alvo, fam, chamar_apply_peer)`, `filtro_upstream_export(alvo, fam, chamar_apply_peer)`, `te_prefix_list(alvo, fam)`, `listas_upstream(alvo)` | `upstream.txt.j2` |
| `filtro_ix_import(alvo, fam)`, `filtro_ix_export(alvo, fam)`, `listas_ix(alvo)` | `ix.txt.j2` |
| `filtro_pni_import(alvo, fam)`, `filtro_pni_export(alvo, fam)`, `listas_pni(alvo)` | `pni.txt.j2` |

A divisão entre `te_prefix_list` e `listas_upstream` não é arbitrária: no `upstream.txt.j2` a definição do `PL-TE-PREFER-<G>-<U>` sai **dentro** do laço de família (linhas 8 a 16), e todo o resto (`CL-NOADV`, `LC-NOADV`, `CL-5PPA`, `LC-5PPA`, `LC-PREP1/2/3`, `AP-BLOCK`, `AP-TE-PREFER`) sai fora dele. `listas_ix` e `listas_pni` cobrem tudo, porque nos dois templates todas as listas são independentes de família, com o comentário de projeto já registrando o motivo de `AP-BLOCK` não poder sair dentro do laço num peer dual-stack.

As macros leem do `alvo` só o que os dois têm: `token`, `id`, `asn`, `origem`, `lp_base`, `aprendizado`, `ix_id`, `te_prefixos`, `ap_block`, `ap_te`, `ap_allowed`, `ap_prefer`, `bh_upstream`, `prepend_base`, `communities`, `large_communities`. Nenhuma delas pode referenciar `sessoes`, `familias()`, `route_limit` ou `descricao`, que são do peer. Junto com a extração, os três templates de peer passam a chamar as macros novas, e o texto gerado tem que continuar byte a byte idêntico ao de hoje. Isso é o teste de aceitação da extração.

### Três templates de grupo

`grupo_upstream.txt.j2`, `grupo_ix.txt.j2` e `grupo_pni.txt.j2`, ao lado do `grupo_cliente.txt.j2`. Cada um fica fino: `cabecalho_grupo`, as macros de filtro e de lista por família, `bgp 64512` com `group <nome> external`, `sessao_do_grupo` e `familia_grupo`.

`TEMPLATE_POR_TIPO_GRUPO` **não muda**. Ele só tem a entrada de `parceiro` porque `parceiro` reaproveita o template do `cliente`; para o resto o `render_grupo` já cai no `"grupo_%s.txt.j2" % grupo.tipo` e encontra o arquivo certo. Criar os três arquivos basta.

### Nomes

Estendendo a tabela de nomes do design anterior, com `<G>` no lugar do token do peer:

| Tipo | Objetos |
| --- | --- |
| `upstream` | `PL-TE-PREFER-<G>-<U>`, `UP-<G>-IMPORT-<U>`, `UP-<G>-EXPORT-<U>`, `CL-NOADV-<G>`, `LC-NOADV-<G>`, `CL-5PPA-<id>`, `LC-5PPA-<G>`, `LC-PREP1/2/3-<G>`, `AP-BLOCK-<G>`, `AP-TE-PREFER-<G>` |
| `ix` | `IX-<G>-IMPORT-<U>`, `IX-<G>-EXPORT-<U>`, `CL-NOADV-<G>`, `LC-NOADV-<G>`, `AP-IX-<G>` |
| `pni` | `PNI-<G>-IMPORT-<U>`, `PNI-<G>-EXPORT-<U>`, `CL-NOADV-<G>`, `LC-NOADV-<G>`, `AP-<G>-ALLOWED` |

O `PL-TE-PREFER-<fam>` da tabela do design anterior é corrigido para `PL-TE-PREFER-<G>-<U>`, que é o formato que o `upstream.txt.j2` realmente emite.

Note que `CL-5PPA-<id>` usa o identificador numérico e `LC-5PPA-<G>` usa o nome. Os dois eixos são espelhos, e é assim que o template de peer já escreve.

## Membros

Esta é a parte maior, e ela não dá para cortar: "vários links, um upstream" só existe se o membro herdar do grupo.

O gate de membro está hoje em `plan.TIPOS_DOWNSTREAM`, em três lugares: `validar` (a checagem de `grupo_id`), o `remover.txt.j2` (três ramos) e o `{% if grupo %}` do `cliente.txt.j2`. Os três passam a valer para `plan.TIPOS`, e as checagens que só fazem sentido em downstream continuam presas a `TIPOS_DOWNSTREAM` dentro do ramo.

Cada um dos três templates de peer ganha um ramo de membro espelhando o do `cliente.txt.j2`:

- `peer <remoto> description <descricao>`.
- `peer <remoto> as-number <asn>` só quando o grupo não tiver ASN próprio.
- `peer <remoto> route-limit <limite> <acao>`.
- `peer <remoto> group <nome>`.
- Na família: `peer <remoto> enable`, `peer <remoto> group <nome>`, mais `route-filter` próprio só quando o membro tiver filtro próprio.

O ramo de membro **não** chama `sessao_do_peer` nem `familia_bgp`. Essas macros reemitem `AS_ONLY`, timers, graceful-restart, bfd e `advertise-community` por membro, e isso tem que existir uma vez só, no arquivo do grupo. O comentário do `cliente.txt.j2` já avisa quem pensar em "limpar a duplicação aparente" reusando as macros do peer.

### Ruling sobre `route-limit` no membro

`sessao_do_peer` emite `route-limit` para todo tipo, sem condição. O ramo de membro do `cliente.txt.j2` emite só quando `peer.tipo == "cliente"`, então um membro de grupo `parceiro` perde o `route-limit` que teria sozinho. É inconsistência do que está construído, não uma decisão.

Ruling: o ramo de membro de todo tipo emite `route-limit`, igual ao peer avulso, porque o limite é da sessão e o `plan.ROUTE_LIMIT` tem valor para os cinco tipos. O ramo existente de `cliente`/`parceiro` perde a condição `peer.tipo == "cliente"` e passa a emitir para os dois. Isso corrige um membro `parceiro` que hoje sai sem limite, e a correção vem com teste próprio para não passar despercebida.

## Quadro "ao criar"

`criar_lista.txt.j2` gera o `CL-PEER-<T>` vazio mais o `APPLY-PEER-<T>`, e o `render_criar_lista` só o produz para `plan.TIPOS_COM_APPLY_PEER`, que é `("cliente", "parceiro", "upstream")`. IX e PNI ficam de fora de propósito: o route server repassa o mesmo AS-path a todos os membros, e o egress do PNI não chama `APPLY-PEER` nenhum.

Com o grupo ganhando `communities`, o `upstream` passa a precisar do quadro na tela do grupo, com as mesmas garantias que o do peer: o bloco do grupo só chama o filtro, então reaplicar o bloco nunca mexe no que o operador escreveu na lista. `ix` e `pni` continuam sem quadro.

## Formulário

A tela do grupo mostra os campos por tipo, com a mesma mecânica que a tela do peer já tem: o JS lê `_padroes()` e as tabelas do `plan` em vez de repetir valor.

Campos novos por tipo:

| Tipo | Campos |
| --- | --- |
| `upstream` | `aprendizado`, `te_prefixos_v4`/`v6`, `ap_block`, `ap_te`, `bh_upstream`, `prepend_base`, `communities`, `large_communities` |
| `ix` | `aprendizado`, `ix_id`, `ap_prefer` |
| `pni` | `ap_allowed` |

Os campos que já existem e continuam: `nome`, `tipo`, `asn`, `lp_base`, timers, `bfd`, `graceful_restart`. `classe`, `origem`, `pop` e `prefixos` ficam presos a `cliente`/`parceiro`, porque é onde eles significam algo. O default de `lp_base` acompanha o tipo (`plan.LP_BASE` dá 100 ao upstream, 190 ao IX e 200 ao PNI) em vez de ficar fixo em 300.

O conjunto de âncoras de erro do template (`ancoraveis`) acompanha os nomes novos, para o aviso do topo continuar levando ao campo.

## Validação

`TIPOS_COM_GRUPO` sai e o portão vira `plan.TIPOS`, com a mesma justificativa que o `validar` do peer já carrega no comentário: um tipo fora da lista grava o registro para estourar depois, no `TemplateNotFound` do render.

`validar_grupo` espelha os ramos por tipo que o `validar` já tem:

| Regra | Tipo | Por quê |
| --- | --- | --- |
| `id` entre 0 e 99 | todos | hoje o grupo não checa faixa, e o `%02d` do `c5ppa` trunca calado |
| `id` não usado por peer | todos | o espaço é compartilhado |
| `classe` em `CLASSES_CLIENTE` | `cliente`, `parceiro` | |
| `origem` em `ORIGENS_CLIENTE` | `cliente`, `parceiro` | |
| `origem` em `ORIGENS_POR_TIPO[tipo]` | `upstream`, `ix`, `pni` | ver ruling abaixo |
| `pop` em 2001-2999 | `cliente`, `parceiro` | é serviço de downstream; quem exige é o import de downstream |
| `prefixos` bem formado | `cliente`, `parceiro` | só esses dois usam o campo |
| `aprendizado` obrigatório, faixa 3000-3999 | `upstream`, `ix` | |
| `ix_id` obrigatório | `ix` | |
| `ap_allowed` não vazio | `pni` | PNI sem allowlist de as-path não sobe |
| `default_route` recusada | `upstream`, `ix`, `pni` | a flag sai de um macro que todos usam, e ligaria o anúncio da default para quem não pediu |
| ASN do grupo com prefixo próprio | `cliente`, `parceiro` | regra que já existe e continua |
| Nome de grupo único | todos | regra que já existe |

E `validar` (o do peer) ganha a checagem recíproca: `peer.id` não pode estar usado por um grupo.

### Ruling sobre a origem fora de downstream

O `validar` do peer confere a origem contra tabela só em downstream, contra `ORIGENS_CLIENTE`. Para `upstream`, `ix` e `pni` ele exige que a origem exista, e nada mais: quem a preenche é o `_origem_padrao`, que lê `plan.ORIGEM[tipo]`. A tabela `ORIGENS_POR_TIPO` alimenta o formulário (`origens_por_tipo`, em `_padroes`) mas não a validação.

Ruling: o grupo valida contra `ORIGENS_POR_TIPO[tipo]`, e é mais estrito que o caminho do peer. O motivo é que a tabela existe justamente para dizer quais origens cada tipo pode carregar, e um grupo de upstream com origem de cliente carimba a rota com um carimbo que mente sobre a procedência. O peer fica como está nesta mudança, e alinhá-lo é uma alteração separada, com teste próprio, porque mexe em cadastro já gravado.

## Testes

A suite tem 377 testes verdes, e eles são a rede desta mudança. Os novos:

- **Identificador**: colisão recusada nos dois sentidos, faixa 0-99 no grupo, e o `peers.yaml` que hoje colide produzindo erro em vez de configuração errada.
- **Extração de macro**: o texto gerado de `upstream`, `ix` e `pni` para um peer avulso continua byte a byte idêntico ao de antes da extração. É o teste que autoriza a refatoração.
- **Grupo por tipo**: um caso de grupo de cada tipo novo, com ASN e sem ASN, renderizando o bloco próprio.
- **Membro por tipo**: um membro de grupo de cada tipo novo herdando, e a prova de que o ramo de membro não reemite `AS_ONLY`/timers/bfd.
- **`route-limit` no membro**: um membro `parceiro` de grupo emite o limite, contra o comportamento de hoje.
- **Validação por tipo**: cada linha da tabela acima com um caso que passa e um que falha.
- **Isolamento**, que é a propriedade dura do app: gerar o grupo não muda a saída de nenhum membro, e gerar um membro não muda a do grupo nem a de outro membro.

## Decisões

| Decisão | Escolha | Motivo |
| --- | --- | --- |
| Tipos de grupo | os cinco, num passe | o escopo do design anterior já prometia os cinco, e o formulário já oferecia `upstream` |
| Espaço de identificadores | um só, 0-99, compartilhado | o eixo `5PPA` tem 100 slots e peers e grupos disputam os mesmos |
| Colisão de id | recusar na validação, nunca renumerar sozinho | o id do grupo vira community publicada; mudá-lo sem o operador pedir quebra o que já foi combinado com o cliente |
| Template de grupo | arquivo próprio por tipo, com macros compartilhadas | é o que foi construído para `cliente`/`parceiro`; três arquivos finos custam menos que ramos por tipo nos templates de peer |
| `communities` no grupo | entra, revertendo o design anterior | para upstream a community descreve a rede remota, não o link |
| `familias()` no grupo | não entra | grupo não tem sessão; os templates declaram as duas famílias, como o de downstream já faz |
| `route-limit` no membro | emite para todo tipo | corrige um membro `parceiro` que hoje sai sem limite |

## Pendências

- **A reversão de `communities` no grupo é o ponto que mais merece sua revisão**, porque contraria uma decisão escrita do design anterior. Se você preferir manter a regra antiga, o caminho é o membro de upstream carregar a própria `CL-PEER` e o grupo não ter `APPLY-PEER`, ao custo de repetir a community em cada link.
- **Ordem de implementação** dos três tipos: o plano de implementação decide, não esta spec. O de upstream é o mais pesado (184 linhas de template contra 102 e 90).
- **O `PLANO.md` precisa de duas seções novas**: a convenção de identificador compartilhado entre peer e grupo, e a existência de grupo nos cinco tipos. Nenhuma das duas está no documento hoje, e ele é a razão de o repositório existir.
- **Alinhar o `validar` do peer com `ORIGENS_POR_TIPO`** fica para uma mudança separada. O grupo nasce mais estrito (ver o ruling na seção de validação), e o peer continua aceitando qualquer origem da faixa 1xxx fora de downstream. A mudança separada precisa de teste e de uma olhada no `peers.yaml` já gravado, porque uma origem fora da tabela lá vira erro depois.
- **Grupo de IX com `ap_prefer`**: o design anterior registrou que a condição é `as-path peer-is` e não depende de qual sessão física carregou a rota, então a lista funciona igual em grupo. Continua valendo, e não precisa de tratamento especial.
