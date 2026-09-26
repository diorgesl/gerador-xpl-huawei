# Gerador de sessões BGP — AS64512

2026-09-21

## Problema

O `PLANO.md` define a política de communities e traz exemplos de filtro para os tipos de sessão. Escrever cada peer à mão a partir dos exemplos é onde nasce o erro que derruba BGP de madrugada: nome de set trocado, community fora de faixa, prefix-list que não bate com o do import, `finish` no lugar de `break`.

O gerador transforma o plano em configuração. Ele não decide política: as faixas, a polaridade e as tabelas saem do `PLANO.md` como estão.

## Escopo

### O que entra

Configuração completa de uma sessão, pronta para colar no F1A: os sets, os route-filters de import e export, e o bloco `bgp 64512` do peer.

Os cinco tipos de sessão: cliente, parceiro, upstream, IX e PNI. O parceiro é um downstream que fica no roteador onde as CDNs peeram e segue a regra do cliente, import e export; o que o separa é a marca `64512:2091`, que o import dele carimba junto da origem e do POP.

Criar, editar e excluir um peer sem tocar nos outros. Esse é o requisito duro: o bloco de um peer é gerado, apagado e regerado sozinho.

Formulário web. O `peers.yaml` é estado interno do app, não é para editar à mão.

`bgpq4` chamado pelo próprio app, com cache em disco e botão de atualizar.

### O que não entra

Nada de falar com o equipamento. O app escreve arquivos e valida; quem cola no F1A é você.

Nada de importar os peers de exemplo do `PLANO.md`. O software começa vazio.

A seção de originação dos próprios prefixos (`network ... route-policy ORIGIN-*`) fica de fora. Ela é por prefixo, não por peer, e o plano já registra que permanece em `route-policy` porque a cláusula `network` não aceita `route-filter`. Vai para uma segunda etapa, se valer a pena.

## Stack

Python 3 mais FastAPI no uvicorn, escutando em localhost. HTML pelo Jinja2, renderizado no servidor, com as ações do formulário em POST comum. O único JavaScript é o botão de copiar do painel de saída.

Sem npm, sem bundler, sem etapa de build. O app sobe com um comando e não precisa de Node instalado.

O estado é um `peers.yaml` versionado em git, uma entrada por peer. Sem banco. É o YAML único que a seção "Geração por template" do plano já previa.

## Estrutura

```
app/
  plan.py        as tabelas do PLANO.md como dados
  peers.py       ler e gravar o peers.yaml, um peer por vez
  render.py      Jinja2, um template por tipo de peer
  prefixes.py    bgpq4 mais o cache em disco
  validate.py    o que o app recusa antes de gerar
  app.py         rotas FastAPI e o formulario
templates/
  base.txt.j2
  cliente.txt.j2
  upstream.txt.j2
  ix.txt.j2
  pni.txt.j2
  *.html
tests/
  test_render.py
  test_validate.py
  golden/
peers.yaml
out/
```

## Fluxo

```
peers.yaml  ->  formulario  ->  validate  ->  render  ->  out/<token>-<tipo>.txt
                    |                                          |
                 bgpq4 (cache)                             duas abas
```

O painel de saída tem duas abas, **criar / atualizar** e **remover**, e o botão copiar pega a aba ativa. O de criação nunca leva um `undo` junto.

## As duas saídas

Nem tudo é por peer. O app emite dois artefatos separados, e a separação é o que faz o isolamento funcionar.

### Bloco base

Sets e filtros compartilhados, gerados uma vez e colados no F1A uma vez. Só mudam quando o plano muda.

- `PL-BOGONS-V4`, `PL-BOGONS-V6`
- `AP-BOGON-ASN`, `AP-LOCAL-ORIGIN`, `AP-PATH-TOO-LONG`
- `CL-BLACKHOLE`, `CL-BLACKHOLE-PROPAGATE`, `CL-GSHUT`, `CL-ORIGEM-ANUNCIAVEL`
- `CL-ONLY-NOT-UP`, `CL-ONLY-NOT-IX`, `CL-ONLY-NOT-PNI`, `CL-ONLY-NOT-CLIENT`
- `CL-NOADV-CUST`, `CL-OWN-ALL`
- `IMPORT-SANITY-V4`, `IMPORT-SANITY-V6`, `EXPORT-SANITY`, `APPLY-CUSTOMER-LP`
- as duas rotas de descarte (`192.0.2.1/32` e `100::/64` para `NULL0` com `tag 666`)

Saída em `/base.txt`, montada na hora do download. O base não vira arquivo em `out/`: ele é função só do `plan.py`, então renderizar a cada pedido dá sempre a versão de agora, e guardar cópia só criaria um estado a mais para ficar para trás.

### Bloco do peer

Tudo que é específico de uma sessão: prefix-lists, as-path-lists, community-lists com o ID ou o ASN do peer dentro, os route-filters de import e export, e o bloco `bgp 64512` daquele peer.

Saída em `out/<token>-<tipo>.txt`, sobrescrita a cada gravação. Nenhum outro arquivo é tocado, e é isso que garante o "sem mexer nos outros já feitos".

### O que o bloco do peer não pode conter

`CL-PEER-<T>` carrega o valor que o contrato ou a topologia pedir. Esse valor vive no `peers.yaml`, no cadastro do peer, e é o gerador que o reproduz.

O bloco do peer, por isso, **não emite a lista**. Ele emite o `route-filter APPLY-PEER-<T>` e o `call`, e nada mais. Reaplicar o bloco depois de qualquer edição mexe só nos filtros, e não tem como zerar uma lista que ele não menciona.

A lista aparece num quadro separado do painel de saída, marcado como **ao criar o peer**, com o par `xpl community-list` / `end-list` e os membros do cadastro. É o único lugar que escreve a lista, então re-colar o quadro troca o conteúdo pelo que está no cadastro, e re-colar o bloco do peer não mexe nele. O diálogo de exclusão lista a `CL-PEER-<T>` junto do resto, com o `undo` comentado: derrubar a sessão não exige apagar a lista, e o quadro recria.

## Nomes

O token do nome é o **ASN do peer**, seguindo a convenção da produção legada: `PL-CUST-268127-V4`, `CUST-268127-IMPORT`.

O ASN não serve para tudo. Numa sessão de IX o ASN é o do route server (`26162` no IX.br), o mesmo em todos os IXs, então dois IXs colidiriam. Nesses casos o formulário aceita um **apelido** que substitui o ASN no token: `IX-SP`, `IX-CG`. O que a validação confere é o token, então o apelido tem de ser único contra os outros apelidos e contra os ASNs.

O **ID** do peer é outra coisa: é o número de dois dígitos da tabela de peers, que entra nas communities `64512:4PP0` e `64512:5PPA` e nas listas que as leem. O app aloca o primeiro ID livre, e o campo é editável.

O token não é gravado. Ele é o ASN, ou o apelido quando existe um, e sai daí toda vez que alguém o lê: um `peers.yaml` antigo que traga `token: GIS` num peer de ASN 264130 carrega como 264130, sem migração à parte. Quem identifica o registro é o **ID**, e é ele que o formulário leva escondido para saber qual entrada o POST substitui. O token não serve para isso: ele muda quando o ASN muda, então o peer renomeado deixaria de ser reconhecido como ele mesmo e a validação acusaria conflito dele contra ele.

Objetos por peer, com `<T>` sendo o token e `<fam>` sendo `V4` ou `V6`. Só sai o que o tipo usa:

| Tipo | Objetos |
| --- | --- |
| Cliente | `PL-CUST-<T>-<fam>`, `PL-CUST-<T>-BH-<fam>`, `AP-CUST-<T>`, `CUST-<T>-IMPORT-<fam>`, `CUST-<T>-EXPORT-<fam>`, `CL-PEER-<T>`, `APPLY-PEER-<T>` |
| Parceiro | os mesmos do cliente, sigla `CUST-` inclusive |
| Upstream | `AP-BLOCK-<T>`, `AP-TE-PREFER-<T>`, `PL-TE-PREFER-<fam>`, `CL-NOADV-<T>`, `LC-NOADV-<T>`, `CL-5PPA-<ID>`, `LC-5PPA-<T>`, `LC-PREP1-<T>`, `LC-PREP2-<T>`, `LC-PREP3-<T>`, `UP-<T>-IMPORT-<fam>`, `UP-<T>-EXPORT-<fam>`, `CL-PEER-<T>`, `APPLY-PEER-<T>` |
| IX | `CL-NOADV-<T>`, `LC-NOADV-<T>`, `AP-IX-<T>` (opcional), `IX-<T>-IMPORT-<fam>`, `IX-<T>-EXPORT-<fam>` |
| PNI | `AP-<T>-ALLOWED`, `CL-NOADV-<T>`, `LC-NOADV-<T>`, `PNI-<T>-IMPORT-<fam>`, `PNI-<T>-EXPORT-<fam>` |

O `AP-IX-<T>` é o `AP-IX-CDN-A` do plano, a lista que separa um membro do IX para dar LP 195 em vez de 190. Ela é opcional e nasce vazia.

O `CL-PEER-<T>` e o `APPLY-PEER-<T>` não levam o tipo do peer no nome, e isso é deliberado: o token já identifica a sessão sozinho, e a palavra do tipo só criaria `CL-IX-IX-SP` quando o token de um IX é apelido. O par serve os três tipos que o definem e o chamam, cliente, parceiro e upstream, como a tabela acima mostra; no IX e no PNI ele não existe, não é emitido e não há `call`. É um template só, gateado por tipo.

O `AP-TE-PREFER-<T>` e o `PL-TE-PREFER-<fam>` são preenchidos à mão no formulário, como o plano manda: são prefixos e ASNs do upstream que você alcança melhor pela borda dele. Em branco, a exceção de TE simplesmente não existe e o filtro não quebra.

O gerador emite set nomeado onde o plano usa set nomeado e escreve literal onde o plano escreve literal. O egress de cliente, por exemplo, referencia `{64512:0:<ASN>}` direto na condição, como no exemplo do plano, em vez de virar um `LC-NOADV-CUST-<T>`.

## Um filtro por família

Os route-filters de sessão levam o sufixo `-V4` ou `-V6` e são separados por família.

O plano não separa v4 de v6 na numeração de communities, e isso continua valendo: um peer dual-stack carimba as mesmas communities nos dois protocolos. Mas o corpo do filtro é específico de família em três pontos que não dão para contornar: o `ip route-destination in PL-...` aponta para uma prefix-list de uma família só, o next-hop do blackhole é `apply ip next-hop` num caso e `apply ipv6 next-hop` no outro, e a cláusula de prefixo do ramo de blackhole do egress escreve `{0.0.0.0 0 ge 32 le 32}` ou `{:: 0 ge 128 le 128}`.

O anexo no `bgp` também é por família, então o sufixo acompanha o que o VRP já obriga a separar.

## Tabelas do plano como dados

O `plan.py` guarda as tabelas do `PLANO.md` como estrutura, não como texto de template. É o que permite validar contra a faixa e oferecer os valores no select.

### Derivados do tipo

Escolher o tipo preenche a política. O formulário mostra os campos já preenchidos e você sobrescreve se precisar.

| Campo | Cliente | Parceiro | Upstream | IX | PNI |
| --- | --- | --- | --- | --- | --- |
| `lp_base` | 300 | 300 | 100 | 190 | 200 |
| Origem `1xxx` | 1100 (ou 1110/1120/1130 pela classe) | igual ao cliente | 1400 | 1300 | 1500 |
| Ponto de aprendizado `3xxx` | — | — | por peer | por peer | — |
| `route-limit` | 50 | 50 | 1500000 | 500000 | 10000 |
| Ação de limite | `alert-only` | `alert-only` | `alert-only` | `alert-only` | `alert-only` |
| `public-as-only force` | sim | sim | sim | sim | sim |

A classe do cliente (`transito`, `residencial`, `corporativo`, `cgnat`) troca a origem entre `1100`, `1110`, `1120` e `1130`. É o único campo derivado que depende de outro, e vale igual para o parceiro, que tem a classe de cliente por baixo da marca.

O `route-limit` sugerido para upstream é `1500000` pela tabela do plano; o exemplo de aplicação usa `1000000`. Fica o da tabela como default e o exemplo como nota no formulário.

### Ingress por tipo

O que cada filtro de import faz depois do `call` de sanidade. Sai do plano, seção por seção.

| | Cliente | Upstream | IX | PNI |
| --- | --- | --- | --- | --- |
| Sanidade | `IMPORT-SANITY-<fam>` | idem | idem | idem |
| Blackhole | ramo próprio, LP 400, `finish` | — | — | — |
| Confinamento de prefixo | `if not ip route-destination in PL-CUST-<T>-<fam> then refuse` | — | — | — |
| Confinamento de AS-path | `if not as-path matches-any AP-CUST-<T> then refuse` | `AP-BLOCK-<T>` recusa | `length ge 4` recusa | `AP-<T>-ALLOWED` recusa |
| LP | `call APPLY-CUSTOMER-LP` | `apply local-preference 100` | 190, ou 195 para membro de CDN | 200 |
| Carimbo | `additive` | `overwrite` | `overwrite` | `overwrite` |
| Communities | origem + POP + large do ASN | `1400`, `3xxx`, `2000` | `1300`, `3xxx`, `2000` | `1500`, `1200`, `2000` |
| Large | `64512:1000:<ASN>` | `64512:1000:<ASN>` | `64512:1001:<IX-ID>` | `64512:1000:<ASN>` |
| Community do peer | `call APPLY-PEER-<T>` | — | — | — |
| Fecho | `finish` | `approve` | `finish` | `finish` |

O cliente usa `additive` e os outros três usam `overwrite`, e isso é o que torna o `matches-any CL-ORIGEM-ANUNCIAVEL` do `EXPORT-SANITY` confiável. Está na tabela do plano e o gerador reproduz.

O fecho do import de upstream é `approve`, como no plano. Não é descuido: o `approve` não encerra o processamento, e ali não há mais nada depois dele. O import de cliente fecha em `finish` porque a rota já passou por tudo.

O parceiro não tem coluna nas duas tabelas porque não tem regra própria: o import dele é o do cliente com uma community a mais, o `64512:2091` no carimbo, ao lado da origem e do POP, e o egress é o do cliente, sem a marca. Quem a lê é o operador, para saber de qual sessão a rota veio, e filtro nenhum decide coisa alguma por ela. O bloco sai do mesmo template do cliente, e não de um arquivo copiado: duas cópias da mesma regra divergem na primeira mudança, e a segunda a ser colada é a que vale.

### Egress por tipo

| | Cliente | Upstream | IX | PNI |
| --- | --- | --- | --- | --- |
| `EXPORT-SANITY` | não | sim | sim | sim |
| Rede de segurança do `2000` | não | sim | sim | sim |
| Escopo de anúncio | `CL-NOADV-CUST` | `CL-NOADV-<T>` ou `LC-NOADV-<T>` | idem | idem |
| `21x` | `CL-ONLY-NOT-CLIENT` | `CL-ONLY-NOT-UP` | `CL-ONLY-NOT-IX` | `CL-ONLY-NOT-PNI` |
| Prepend | large `1/2/3:<ASN>` | `5PPA` do peer, senão `6CA` classe 1 | `6CA` classe 2 | `6CA` classe 4 |
| Prepend base | — | valor literal por peer | — | — |
| `med` | — | `0` | — | — |
| Community do peer | — | `call APPLY-PEER-<T>` | — | — |

O egress de cliente não leva `EXPORT-SANITY` e não leva limpeza. É deliberado no plano: o cliente precisa das informativas, é o que transforma o plano em produto.

Nenhum egress leva limpeza. O `apply community {...} overwrite` de fecho saiu do plano, e o `64512:1901` que ele gravava foi aposentado junto. O que ocupa o lugar dele é o par por peer, `CL-PEER-<T>` e `APPLY-PEER-<T>`, aplicado com `additive` por um filtro de uma linha que fecha em `break`. O par vale para cliente, parceiro e upstream, os três tipos que o chamam; no IX e no PNI não há `call`. Entre os dois, o que muda é onde o `call` fica: no import de cliente e no export de upstream.

O ramo de blackhole do egress de upstream segue com `overwrite` e não é exceção: ali ele define o anúncio sintético, não limpa. Sai com a community de blackhole do upstream e nada mais.

O `CL-NOADV-<T>` segue a composição do plano, um valor de cada eixo:

| Tipo | Conteúdo | Leitura |
| --- | --- | --- |
| Upstream | `{200, 201, 5<ID>0}` | ninguém, não-upstream, não este peer |
| IX | `{200, 203, 5<ID>0}` | ninguém, não-IX, não este peer |
| PNI | `{200, 202, 5<ID>0}` | ninguém, não-bilateral, não este peer |

O `CL-NOADV-CUST` do egress de cliente é fixo em `{200, 204}` e não tem eixo por peer. `201`, `202` e `203` ficam de fora de propósito: dizem "não anunciar para aquele tipo", não "não anunciar para cliente", então a rota segue para o cliente.

### Prepend por peer

O ramo do `5PPA` no egress de upstream é o mais aninhado do plano e sai igual: se veio qualquer `5PPA` do peer, o específico vence o genérico e a classe `6CA` não entra; senão, vale a classe.

```
 if community matches-any CL-5PPA-<ID> or large-community matches-any LC-5PPA-<T> then
  if ... {64512:50<ID>4} or LC-PREP3-<T> then apply as-path 64512 3 additive
  elseif ... {64512:50<ID>3} or LC-PREP2-<T> then apply as-path 64512 2 additive
  elseif ... {64512:50<ID>2} or LC-PREP1-<T> then apply as-path 64512 1 additive
  endif
 else
  if community matches-any {64512:614} then apply as-path 64512 3 additive
  elseif community matches-any {64512:613} then apply as-path 64512 2 additive
  elseif community matches-any {64512:612} then apply as-path 64512 1 additive
  endif
 endif
```

O dígito `1` do `5PPA` (P1 explícito) não tem ramo de prepend. Ele existe para barrar a classe, e é por isso que o aninhamento é `if` e não `finish`.

Esse ramo só existe no egress de **upstream**. No IX ele não tem como funcionar, e o plano registra o motivo: o route server repassa o mesmo AS-path a todos os membros, então um prepend no egress da sessão com o RS prependa para todo mundo. Prepend por membro de IX só com sessão bilateral, e isso está na tabela pública ao cliente.

O PNI é bilateral e aceitaria o ramo, mas o exemplo do plano não o traz. O gerador segue o exemplo e não emite. Fica na lista de pendências, não como decisão tomada.

O eixo do `5PPA` que funciona nos três tipos externos é o do **bloqueio**: o valor `64512:5<ID>0` entra no `CL-NOADV-<T>` de upstream, IX e PNI, então "não anunciar para este peer" vale nos três.

### Sem parâmetro `$`

Os filtros de upstream no plano são parametrizados (`UP-IMPORT-14840($lp_base)`), para um par de filtros servir três upstreams. O gerador emite valor literal.

Dois motivos, os dois já registrados no plano. O isolamento por peer quer um filtro por sessão, não um genérico servindo três. E o `xpl simulate` não aceita filtro parametrizado, então sessão de upstream gerada com parâmetro não teria como ser testada no equipamento.

O efeito colateral é bom, e não é só higiene: com a aritmética de prepend feita em Python e o valor literal, a linha do `apply as-path` simplesmente não é emitida quando o valor é zero. O contador `0` não é aceito no equipamento, e isso está verificado em campo (`PLANO.md:393`), então não emitir a linha é o que evita a configuração inválida.

## bgpq4

O app chama `bgpq4` pelo ASN do peer e guarda o resultado em `out/.cache/<asn>.json`, com a data da coleta.

```
bgpq4 -4 -A -F '%n/%l ' -h whois.radb.net -l PL-CUST-268127-V4 AS268127
bgpq4 -6 -A -F '%n/%l ' -h whois.radb.net -l PL-CUST-268127-V6 AS268127
```

A chamada vai com `-A` e sem `-X`. O `-X` pede a saída no formato de configuração do IOS XR, e não uma lista de CIDRs. O `-F '%n/%l '` devolve `rede/máscara` puro, que é o que o campo espera.

O `-A` junta irmãos: dois prefixos do mesmo tamanho que juntos cobrem o pai viram o pai, e nada além disso. O agregado cobre exatamente o que o IRR tem. Em `AS3333`, os `/23` de `193.0.20.0` e `193.0.22.0` saem como `193.0.20.0/22`, e os de `193.0.10.0` e `193.0.12.0` continuam separados, porque o `/22` entre eles não está registrado. Quem cobre buraco é o `-R` e o `-r`, que marcam um prefixo registrado como faixa até um tamanho maior sem conferir se os mais específicos existem (`sx_radix_node_refine`, no `sx_prefix.c` do bgpq4 1.12). Esses dois ficam fora, e é o que torna a agregação segura aqui.

Sem `-A` a lista trazia cada bloco registrado: o `AS264130`, que tem um `/22` e quatro `/24` dentro dele, gerava sete linhas onde cabe uma. O agregado repete a entrada quando ele mesmo é um objeto registrado (o `/32` v6 do `AS264130` voltou duas vezes), e o `_normalizar` tira a repetição.

O botão **atualizar** no formulário refaz a consulta e ignora o cache. Sem ele, o cache é usado enquanto tiver menos de 24 horas; passado isso o app avisa na tela, sem bloquear a geração. O cache leva uma versão junto, que subiu para 2 quando o `-A` entrou: arquivo gravado antes guarda a lista sem agregar, e servir essa lista faria a consulta nova parecer que não pegou.

A lista sempre pode ser editada à mão no formulário depois da consulta. O `bgpq4` é o ponto de partida, não a palavra final.

A soma dos blocos de todos os clientes alimenta uma checagem de sobreposição entre peers, que é o `/22` duplicado do legado virando erro de formulário em vez de erro de produção.

## Validação

O `validate.py` roda antes de gerar e recusa com mensagem no campo.

| Regra | Por quê |
| --- | --- |
| ASN entre 1 e 4294967294, diferente de 23456 | Reservados pela IANA; o `AP-BOGON-ASN` do plano recusa exatamente esses |
| ASN privado gera aviso, não erro | Cliente com ASN privado existe |
| ID entre 0 e 99, único entre os peers | É o `PP` de `64512:4PP0` e `64512:5PPA` |
| Token único, `[A-Z0-9]`, até 12 caracteres | Nome de objeto do VRP e legibilidade da config |
| Endereços de sessão válidos e únicos entre peers | Dois peers com o mesmo IP remoto é erro de digitação |
| Pelo menos uma família configurada | Sessão sem endereço não gera nada |
| Cliente sem prefix-list é erro | O plano é explícito: a sessão de cliente não pode subir sem ele |
| Bloco de cliente sobreposto ao de outro peer é erro | O `/22` para dois ASNs do legado |
| `lp_base` entre 0 e 65535 | Faixa do atributo |
| `route_limit` maior que zero | |
| Community fora das faixas do `plan.py` é erro | O app conhece a tabela; valor inventado não passa |
| Excluir peer exige confirmação com o que sai do equipamento à vista | |

A checagem de faixa vale para os campos que viram community. Se um dia a tabela do plano mudar, muda no `plan.py` e a validação acompanha.

## Interface

Tela única, com a lista de peers à esquerda e o formulário à direita. O painel de saída abre abaixo do formulário.

**Formulário.** Identificação (ID, nome, ASN, tipo, classe), sessão (endereço local e remoto por família), prefixos (do `bgpq4`, editáveis, com o botão de atualizar) e política (LP base, origem, POP, prepend base, route-limit).

Escopo de anúncio e prepend por classe não são campos, e a ausência é do desenho, não uma falta. O prepend por classe é derivado do prepend base pela tabela do `6CA`, então digitá-lo seria pedir ao operador que refizesse a conta. O escopo é do cliente: é ele que sinaliza `64512:2xx` ou o alias `5PPA`, e o que o gerador faz é emitir a `CL-5PPA-<ID>` que o captura. Um campo de escopo no formulário faria a operadora escrever uma community de ação no lugar de quem tem direito de escrevê-la.

**Derivados.** Os campos de política aparecem preenchidos pelo tipo escolhido, e todos são editáveis. Nada escondido atrás de um bloco recolhido: o que o tipo decidiu fica à vista, e sobrescrever é digitar por cima.

**Selects.** Os campos que só aceitam valores da tabela são `select` nativo, com o código e o nome numa linha só: `64512:1110 — Cliente residencial / FTTH`. Select nativo porque funciona no teclado, no celular e no leitor de tela sem código extra.

**Painel de saída.** Dois blocos rotulados, criar/atualizar e remover, cada um com o próprio botão de copiar. Os dois ficam à vista juntos: a colagem é em sequência, e uma aba escondida obrigaria a alternar para copiar o segundo. Cabeçalho em `!-` dizendo o peer e o tipo, porque config gerada que ninguém sabe de onde veio é config que ninguém ousa apagar.

**Exclusão.** O diálogo de excluir lista o que sai do equipamento antes de mostrar o bloco de `undo`: as prefix-lists, os route-filters, os community-lists e a sessão. O `undo` sai na ordem que o VRP aceita, com o `undo peer` antes dos `undo xpl`.

## Testes

`pytest` sobre `render.py` e `validate.py`.

**Golden por tipo.** Um caso por tipo de peer, com o `peers.yaml` de entrada e o `.txt` de saída commitado em `tests/golden/`. É o que pega mudança acidental de template.

**Propriedade que os testes precisam cobrir:** gerar o peer B não muda a saída do peer A. Um teste que gera A, gera B, regera A e compara com a primeira saída.

**Validação.** Um teste por regra da tabela acima, com o caso que passa e o que falha.

Nada de teste de UI. O formulário é fino de propósito; o que decide está no `render.py` e no `validate.py`.

## Conferência antes de colar

O app não fala com o equipamento, então o que ele pode fazer é deixar a conferência barata:

- A saída é ASCII puro e os comentários usam `!-`. Caractere fora de ASCII quebra o pipeline de TFTP, backup e diff.
- O cabeçalho de cada arquivo diz qual bloco base ele pressupõe. A tela não avisa sobre o base: sem arquivo guardado não há com o que comparar, e um aviso assim só acenderia por engano.
- O `xpl simulate` do plano não aceita filtro parametrizado, e por isso não há parâmetro nenhum na saída. Todos os filtros gerados podem ser armados e testados.

## Decisões

| Decisão | Escolha | Motivo |
| --- | --- | --- |
| Comentário na saída | só procedência, instrução de colagem e comando desligado | O porquê de cada regra fica no template como comentário Jinja; o que sai é o que o operador precisa ler antes de colar |
| Token do nome | ASN, com apelido para IX | Convenção da produção legada; o ASN do route server se repete |
| Token no `peers.yaml` | não é campo: sai do ASN, ou do apelido quando há um | Guardar os dois é guardar a mesma coisa duas vezes, e o token gravado fica para trás quando o ASN muda |
| Identidade do registro | o `id`, em campo escondido, e só ao editar | O token muda junto com o ASN: por ele, o peer renomeado conflita consigo mesmo, e um ASN já usado sobrescreve o peer que estava lá |
| Filtros | um por família | O corpo é específico de família em três pontos |
| Parâmetro `$` | não usar | Isolamento por peer mais o `xpl simulate` |
| Limpeza no egress | nenhuma | O `overwrite` de fecho apagava junto o que a operadora precisa enviar ao peer |
| Community do peer | lista no cadastro do peer, e o quadro "ao criar o peer" é quem a escreve | O valor depende de contrato e muda sem aviso. Guardá-lo é o que permite reescrever a lista igual, e o quadro é o único lugar que a escreve, então re-colar o bloco do peer continua não mexendo nela |
| Community do peer fora da sintaxe do equipamento | erro | Um valor que o `community-list` não aceita derruba o objeto inteiro no commit, e o resto da lista com ele |
| Community do peer fora das faixas do plano | aviso, não erro | As faixas descrevem as communities do plano, não o que o contrato pediu: barrar seria o gerador decidindo contrato |
| Nome do par | `CL-PEER-<T>` / `APPLY-PEER-<T>`, sem o tipo | O token já identifica a sessão, e o tipo só criaria `CL-IX-IX-SP` nos apelidos de IX |
| A lista no bloco do peer | não | Reaplicar o bloco não pode zerar a lista do equipamento |
| Default route ao cliente | caixa no formulário, com o comando `default-route-advertise` na família | Serviço de downstream, pedido caso a caso: nasce desligada, e quem quiser bloqueá-la bloqueia do lado dele |
| Ramo da default no export | nenhum | A rota sai pelo comando da sessão e não precisa de filtro |
| `IMPORT-SANITY-V6` | emitir | Única extensão autorizada ao plano; sem ela a sessão v6 não tem sanidade |
| Base e peer | saídas separadas | É o que faz o isolamento valer |
| Base em disco | não | O base é função só do `plan.py`: o download já sai sempre atual, e o arquivo guardado só servia para o aviso comparar datas, com o sinal no evento errado (mexer num peer não muda o base) |
| GSHUT | só no `APPLY-CUSTOMER-LP` | O plano registra como ponto em aberto; o gerador não decide política |
| Originação | fora do escopo | É por prefixo, não por peer |
| Consulta ao IRR | `bgpq4` com `-A` | O agregado é irmão virando pai, então cobre só o que o IRR tem; a lista crua repetia os quatro `/24` de dentro do `/22` |

## Pendências

Nada aqui bloqueia começar.

- **A default route do cliente está fora do PLANO.** O documento não tem community, filtro nem menção a `default-route-advertise`: é serviço que o cliente pede, e o gerador emite o comando seco, com a caixa desmarcada por padrão. O `!-` do cabeçalho lembra de conferir se há um default na tabela do equipamento, que é o que o comando anuncia. A extensão entra no PLANO quando o texto do documento for revisto.
- **Prepend por peer em PNI.** O exemplo do plano não traz o ramo `5PPA` no egress de PNI, e o gerador segue o exemplo. Como o PNI é bilateral, o ramo funcionaria. Decide-se quando houver um PNI que peça prepend.
- **A checagem espelhada do `64512:4:<ASN>`.** O plano define `LC-ONLY-14840` e registra que a implementação ficou em aberto de propósito: recusar `64512:4:<ASN>` de terceiro em cada egress que não é o do próprio ASN. Sem ela, "anuncie só para o peer X" não restringe nada. Depende de confirmar no equipamento se o coringa funciona em large-community-list, e o plano já avisa que ele foi verificado só em standard.
- **GSHUT em upstream, IX e PNI.** O plano registra que o `65535:0` hoje só é lido em `APPLY-CUSTOMER-LP`. O gerador reproduz; não é decisão dele cobrir os outros três.
- A seção de scrubbing center do plano tem um ponto em aberto sobre `apply preference` e `apply preferred-value` no `route-filter`. Quando você confirmar no equipamento, entra como um quinto tipo de sessão ou como um campo do PNI.
- O `3xxx` de ponto de aprendizado é por peer, então o formulário pede o valor. Uma tabela de IXs e upstreams conhecidos pode preencher sozinha mais tarde.
- A rota de descarte do RTBH entra no bloco base. Se o `192.0.2.1` de exemplo conflitar com algo da produção, troca no `plan.py`.
- **Duas confirmações no equipamento antes do primeiro peer.** Se `apply community` aceita lista nomeada e com que sintaxe, já que o legado usa `apply community community-list <nome>` em `route-policy` e as duas views divergem em outros pontos. E se uma `community-list` sem nenhum membro é aceita, deixando a rota seguir sem alteração. As duas respostas mudam o template do `APPLY-PEER-<T>`; o plano já as registra na tabela de confirmação.
