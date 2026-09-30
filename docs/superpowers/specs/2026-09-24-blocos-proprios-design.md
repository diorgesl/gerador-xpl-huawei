# Blocos do próprio AS — AS64512

2026-09-24

## Problema

O gerador cobre peers e grupos e não cobre o que o AS anuncia por conta própria. Os prefixos do próprio AS não têm cadastro, não têm consulta e não saem em configuração nenhuma.

O gate do outro lado já espera por eles. `CL-ORIGEM-ANUNCIAVEL` inclui `64512:1000`, "prefixo próprio do AS", desde que `_origem_anunciavel` foi escrita (`app/plan.py:181`), e o `EXPORT-SANITY` recusa tudo que não case ali. Ninguém escreve esse `1000`, porque não existe originação no gerado. A única marca de origem que o plano define e não implementa é justamente a do prefixo do próprio operador.

O `PLANO.md` descreve a originação na seção "Originação dos próprios prefixos", com as três peças por prefixo: estática para NULL0, `network` e a política com LP 900 e o conjunto de communities. Faltam duas coisas lá. A primeira é de onde sai a lista de prefixos. A segunda é de forma: o documento afirma que `network` aceita `route-policy` e não `route-filter`, e manda confirmar na release antes de assumir.

**Confirmado no F1A em 2026-09-24:** `network <ip> <mask> route-filter <nome> ?` completa com `label-index`, `non-relay-tunnel` e `<cr>`, ou seja, a palavra-chave existe. A originação pode ser XPL como o resto do gerado.

## O que já existe e o que falta

| Peça | Estado |
| --- | --- |
| `CL-ORIGEM-ANUNCIAVEL` com o `1000` dentro | existe, `base.txt.j2:79` |
| `AP-LOCAL-ORIGIN` como `regular ^$` | existe, `base.txt.j2:55`, usado só pelo `IMPORT-SANITY` |
| recusa explícita de `1900` e `1901` no egress externo | **não existe**; hoje quem barra é o `EXPORT-SANITY`, por tabela |
| consulta ao IRR | `prefixes.coletar` já serve, é o mesmo `bgpq4` do cliente |
| cadastro no `peers.yaml`, tela, template e remover | não existem |

A linha do `1900` é a que surpreende. O único lugar do gerado que recusa `1900` e `1901` é o export de cliente (`_macros.j2:216`). Nos egress de upstream, IX e PNI o que segura a marca de infra interna é o `CL-ORIGEM-ANUNCIAVEL` não conter esse valor, e isso deixa de bastar com a mudança de `EXPORT-SANITY` que esta spec propõe. O buraco está fechado abaixo, na seção do `EXPORT-SANITY`.

## Escopo

### O que entra

- Cadastro dos prefixos próprios no `peers.yaml`, por prefixo, com consulta ao IRR no ASN da rede e edição por cima do resultado.
- Reconsulta que casa por prefixo e preserva o tratamento já dado a cada um.
- Por prefixo, a lista de communities do tratamento manual, com o `64512:1000` gerado e não digitável.
- Geração de três peças por prefixo: estática para NULL0 com `preference 250`, `xpl route-filter ORIGEM-<nome>` e a linha `network ... route-filter`.
- Mudança no `EXPORT-SANITY`: rota originada localmente passa a dispensar a marca de origem, e a infra interna ganha barreira explícita.
- Os dois removeres do bloco.
- Atualização do `PLANO.md`.

### O que não entra

- Campo de linhas livres de política por prefixo. A lista de communities cobre o caso pedido, e o campo livre não cabe por causa do `apply community` sem `additive`, explicado na seção da saída gerada.
- Conjunto de communities compartilhado entre prefixos. Cada prefixo tem o seu, mesmo quando dois saem iguais, e o nome do filtro continua descrevendo o prefixo.
- Validação de community de terceiro. O vocabulário do mundo não dá para conferir, e o que o gerado pode fazer é não atrapalhar.
- Grupo de blocos. Um prefixo é uma linha, e o PLANO não tem essa agregação.
- Originação por `route-policy` clássica. Confirmado que não é necessária.

## O cadastro e a consulta

**Decisão.** A lista mora no `peers.yaml`, numa seção `blocos` no fim do arquivo, ao lado de `asn`, `asn_politica`, `peers` e `grupos`. O arquivo deixou de ser só de peers desde que o `asn` e o `asn_politica` entraram no topo; o bloco próprio é dado da rede, como eles.

```yaml
blocos:
  v4:
  - prefixo: 38.252.64.0/22
    communities: [64512:613, 64512:621, 15169:12100]
  - prefixo: 38.252.64.0/24
    communities: [64512:211]
  v6:
  - prefixo: 2804:36b4::/32
    communities: []
```

As famílias são chaves explícitas, como em `prefixos` do peer, e não deduzidas do CIDR. A consulta já devolve por família e o formulário é o mesmo padrão das listas atuais.

Seção ausente é lista vazia, mesma decisão que a chave `asn` tomou no design anterior: o `peers.yaml` de hoje carrega sem migração.

O `bloco` não tem `id`. Ele não entra no espaço de identificadores de peer e grupo, que existe para o `5PPA` e o `6CA`, e o prefixo já é o identificador.

### A consulta

Reusa `prefixes.coletar`, com o ASN da rede no lugar do ASN do peer. `_comando` monta o rótulo da lista como `PL-CUST-<token>-<FAM>`, que é cosmético para o `bgpq4` porque `-F '%n/%l '` devolve CIDR puro, e por isso ganha um parâmetro de etiqueta com o valor de hoje como default. O caminho do bloco passa `ORIGEM`.

O cache continua com chave só no ASN, e isso é de propósito. A consulta é a mesma para o mesmo ASN, então um peer que tenha o ASN da própria rede e o cadastro de blocos podem compartilhar a entrada sem prejuízo. O `CACHE_VERSAO` já existe para o caso em que muda o que a consulta devolve.

### A reconsulta

O comportamento do peer não serve aqui. Em `app.py:700` a reconsulta substitui a lista inteira, o que é correto para o peer, porque a lista dele é espelho do IRR e nada mais. No bloco, cada prefixo carrega um tratamento escrito à mão, e a substituição apagaria esse trabalho sem aviso, porque o prefixo continua na lista e nada parece ter mudado.

**Decisão.** A reconsulta casa por prefixo:

- prefixo que veio da consulta e já estava salvo mantém as communities que tinha;
- prefixo que veio da consulta e não estava salvo entra com a lista vazia;
- prefixo que estava salvo e não veio da consulta entra marcado como ausente no IRR, e a decisão de manter ou remover é do operador antes de salvar.

O default do marcado é **manter**. Deixar de anunciar um prefixo vivo por causa do que o IRR diz é pior do que continuar anunciando um prefixo que saiu de lá, e o marcador fica visível na tela antes de gravar. O CIDR é chave estável, então casar por ele não custa nada.

O `peers.yaml` continua guardando só o que foi salvo, como o cache do `bgpq4` guarda só o que a consulta devolveu. A marca de ausente vive na tela, entre a consulta e o salvar, e não no arquivo.

## O que um prefixo carrega

Um campo, a lista de communities. O `64512:1000` não está nela e não é digitável: é gerado, entra sempre, e é o que identifica o prefixo como próprio no `display bgp routing-table`.

O LP não é campo. Vai fixo em 900 na política gerada, que é o valor das duas fontes, o exemplo do `PLANO.md` e o `BGP_EXEMPLO.txt`.

As communities que valem aqui são as mesmas que o cliente escreve na sessão dele. Onde o cliente digita `64512:613`, o operador digita `613` no cadastro do bloco. O que o egress lê hoje:

| Eixo | Forma | Valor de exemplo |
| --- | --- | --- |
| Escopo de anúncio | `2xx` | `211`, "anunciar somente para IX" |
| Prepend por classe de peer | `6CA` | `613`, P3 nos upstreams |
| Prepend e bloqueio por peer | `5PPA` | `5133`, dois prepends no peer de ID 13 |
| Prepend por peering de 32 bits | large `1:<ASN>`, `3:<ASN>` | `64512:3:14840` |
| Blackhole e manutenção | `666`, `667`, `9666` | `667` propaga aos upstreams |
| Informativas | `1000`–`9999` | `2101`, região Centro-Oeste |

O eixo `1xx` de local preference **não** entra, e a diferença em relação ao cliente é real. Lá o `1xx` é lido pelo `APPLY-CUSTOMER-LP`, que só é chamado no import de cliente (`_macros.j2:155`). O prefixo próprio não passa por import nenhum, então o LP dele é escrito direto na política de originação e uma community `1xx` na lista não seria lida por ninguém.

### A validação

**Decisão.** Community no namespace da rede que nenhum filtro lê é recusada ao salvar, com o motivo. Community de outro AS passa sem checagem, porque o vocabulário do mundo não dá para conferir.

Isso é o que fecha dois buracos que existem no documento hoje. O exemplo de `ORIGIN` da seção de originação do `PLANO.md` escreve `64512:673`, que é classe 7 ("todos") com P3, e o egress não implementa a classe 7: `CLASSE_6CA` tem só `upstream: 1`, `ix: 2` e `pni: 4` (`app/plan.py:243`), os três macros de export consultam exatamente essas três, e há teste afirmando que o conjunto é só esse. A large `64512:4:<ASN>`, "anunciar somente para este ASN", está na mesma situação: o egress implementa as funções `0`, `1`, `2` e `3` e não tem ramo para a `4`.

A tabela de recusa sai das mesmas tabelas que os templates leem, para não haver duas listas de verdade:

| Recusa | Motivo |
| --- | --- |
| `1xx` | o consumidor é o import de cliente, e a rota própria não passa por lá |
| `3xx`, `4xx`, `7xx`, `8xx` | faixas sem dono no plano |
| `2xx` fora de `200`–`204` e `210`–`213` | nenhum ramo de egress lê |
| `6CA` com classe fora de `1`, `2` e `4`, ou dígito fora de `1`–`4` | `CLASSE_6CA` e `DIGITO_PREPEND` |
| `5PPA` com dígito fora de `0`–`4` | `CL-5PPA-<id>` cobre `range(5)` |
| large `4:<ASN>` | anunciar somente para um ASN não tem ramo |

## O nome do filtro

`ORIGEM-<ip>_<máscara>`, com o IP em traço no lugar de ponto:

```
38.252.64.0/22       -> ORIGEM-38-252-64-0_22
2804:36b4:8000::/34  -> ORIGEM-2804-36b4-8000_34
```

O `_` antes da máscara lê como máscara, que é o que o `m` de `ORIGIN-38-252-64-0m22` não faz: ele parece parte do endereço. A convenção antiga vinha do `BGP_EXEMPLO.txt` e do `PLANO.md`, e o motivo que o documento dá para o nome carregar o prefixo é "localizável sem consultar índice". Esse motivo caiu, porque o índice agora é o YAML e a tela. O que continua valendo é o nome aparecer no `network` e no `display`, e ali ele precisa dizer de qual prefixo é sem decodificação.

Sem marca de família. Um v6 não gera nome com cara de v4 válido, então não há ambiguidade na prática, e os nomes ficam mais curtos.

`ORIGEM` e não `ORIGIN`: o resto do gerado usa português nos nomes próprios, e o `BGP_EXEMPLO.txt` é a única fonte que escreve em inglês.

**A confirmar no equipamento:** se o nome aceita ponto, a forma `ORIGEM-38.252.64.0_22` é melhor ainda, porque se lê como o prefixo. Um `xpl route-filter ORIGEM-38.252.64.0_22` responde. Enquanto não for confirmado, o gerado usa traço.

## A saída gerada

Três peças por prefixo, em dois fragmentos, no mesmo esquema dos peers: um fora da view do `bgp` e um dentro da view da família.

```
# --- blocos proprios do AS64512 ---
# fora da view do bgp: estaticas e filtros

ip route-static 38.252.64.0 255.255.252.0 NULL0 preference 250
ip route-static 38.252.64.0 255.255.255.0 NULL0 preference 250

xpl route-filter ORIGEM-38-252-64-0_22
 apply local-preference 900
 apply community {64512:1000, 64512:613, 64512:621, 15169:12100} overwrite
 break
end-filter

xpl route-filter ORIGEM-38-252-64-0_24
 apply local-preference 900
 apply community {64512:1000, 64512:211} overwrite
 break
end-filter
```

e dentro de `ipv4-family unicast`

```
 network 38.252.64.0 255.255.252.0 route-filter ORIGEM-38-252-64-0_22
 network 38.252.64.0 255.255.255.0 route-filter ORIGEM-38-252-64-0_24
```

As formas mudam com a família em dois pontos e só neles. Em v6 a estática é `ipv6 route-static <prefixo> <comprimento> NULL0 preference 250`, a linha da view é `network <prefixo> <comprimento> route-filter <nome>`, e o comprimento vai direto, sem pontuação, como no `network 2804:36B4:: 32 route-policy ORIGIN-2804-36b4m32` do `BGP_EXEMPLO.txt`. O filtro é idêntico nas duas.

### Por que `preference 250`

O `PLANO.md` escreve `preference 1`, para a estática ganhar de tudo e o `network` nunca ficar sem o que originar. Com `250` ela continua ganhando do BGP, que é o que importa: um cliente com sub-alocação dentro do bloco que anuncie o mesmo `/24` tem a rota dele em BGP, com preferência 255, e a estática em 250 vence, então o `network` origina o local e não a rota do cliente carimbada com a marca de origem da rede.

O que ela deixa de fazer é ganhar do IGP e das estáticas de preferência default, que é 60. Um agregado que exista de verdade na tabela passa a sair com o next-hop de verdade em vez de ir para o NULL0.

### Por que `overwrite`

É a regra que o `PLANO.md` já fixa para o resto do desenho, "sempre `overwrite` primeiro". Aqui ele garante que o prefixo saia com exatamente o `1000` mais a lista. Com `additive` ele herdaria o que a rota que ganhou a tabela estivesse carregando, que é justamente o caso da sub-alocação do cliente.

### Por que cada prefixo tem a estática dele

O `network` casa o prefixo exato na tabela de rotas. Sem a estática do `/24`, o `network ... m24` ou não origina nada, ou casa a rota de outra origem que tenha aquele `/24`. É o mesmo caso acima, e a estática resolve os dois.

### Por que não há campo de linhas livres

No `route-policy` e no `route-filter` do VRP, `apply community` sem `additive` substitui o atributo inteiro. Uma linha livre escrita depois da linha gerada apagaria o `1000`, e o prefixo voltaria a ser recusado em todo egress, sem nada aparecer na tela. A lista é o lugar certo para communities, e é o que o caso pedido precisa.

## A mudança no `EXPORT-SANITY`

A originação passa a ser dispensada da marca de origem quando a rota nasceu aqui, e o `1900` ganha barreira própria:

```
xpl route-filter EXPORT-SANITY
 !- infra interna nunca sai, nem como rota propria
 if community matches-any {64512:1900, 64512:1901} then
  refuse
 endif
 !- path vazio e rota originada localmente: nao precisa de marca
 if not as-path matches-any AP-LOCAL-ORIGIN then
  if not community matches-any CL-ORIGEM-ANUNCIAVEL then
   refuse
  endif
 endif
 break
end-filter
```

### Por que a lista é `AP-LOCAL-ORIGIN` e não uma nova

`AP-LOCAL-ORIGIN` é `regular ^$` (`base.txt.j2:55`), o `IMPORT-SANITY` já a usa como quarta condição, e o `PLANO.md` define em [PLANO.md:683](../../../PLANO.md) que ela "casa AS-path vazio, ou seja, rota originada localmente". A definição de "rota originada localmente" já é essa no documento. A mudança usa do lado do egress a mesma definição que o import usa, e não inventa conceito.

O `as-path in OWN-ASN` que motivou esta seção provavelmente não parseia: o gerado escreve `as-path matches-any <lista>` em todos os lugares, e o `in` aparece no `PLANO.md` só para prefixo, em `ip route-destination in`.

### O que a mudança troca

O `EXPORT-SANITY` deixa de ser a única barreira e passa a depender de o path vazio só existir para rota nascida aqui. Hoje isso se sustenta: o `IMPORT-SANITY` recusa path vazio em toda sessão, e o `check-first-as` no default impede o vizinho eBGP de anunciar rota sem o próprio ASN no path. Na sessão do route server do IX o `check-first-as` é desligado de propósito, e ali o `AP-LOCAL-ORIGIN` do `IMPORT-SANITY` deixa de ser rede de segurança e passa a ser a barreira em vigor, como o `PLANO.md:907` já registra.

O que passa a pesar é `import-route` e `aggregate`, que não existem no desenho hoje. Qualquer um dos dois coloca rota local com path vazio na RIB, e essa rota vira anunciável em todo lugar sem marca de origem. É condição para escrever no documento, não impedimento para a mudança.

### O que ganha

O `network` fica autossuficiente. Reemitir a linha sem filtro mantém o bloco anunciado para tudo, então o filtro deixa de ser o que segura o anúncio e passa a ser só o tratamento manual. Uma remoção acidental de filtro deixa de tirar um prefixo da tabela global.

O `64512:1000` continua sendo gerado. Só deixa de ser o que sustenta o anúncio e passa a ser o que identifica o prefixo no `display`.

O caso do `1900` é o preço. Como o prefixo próprio tem path vazio e passa a escapar da checagem de marca, a marca de infra interna precisava de um ramo explícito, e o `PLANO.md` nunca teve um. A regra fica mais clara do que estava, escrita em vez de acidental.

## Os dois removeres

São operações diferentes e o remover precisa distinguir.

**Tirar o tratamento manual.** Esvaziar a lista. O filtro continua existindo com o `1000`, e o prefixo continua anunciado para tudo. É o caso comum.

**Desligar o prefixo.** Nesta ordem, porque o filtro não pode ser apagado enquanto estiver referenciado:

```
 undo network 38.252.64.0 255.255.252.0
 undo xpl route-filter ORIGEM-38-252-64-0_22
 undo ip route-static 38.252.64.0 255.255.252.0 NULL0
```

O `undo network` vem antes do `undo xpl route-filter` pelo motivo de sempre: objeto em uso não é apagável. A estática vai por último. Se ela sair primeiro e o `network` ficar, o prefixo some por falta de rota na tabela, em silêncio.

**A confirmar no equipamento:** se `undo network <ip> <mask>` remove a entrada que tem `route-filter` junto, ou se é preciso reemitir a linha sem o filtro antes. O desenho assume que remove, porque é o que o comando significa, mas é um `display this` de distância.

## A tela

Uma seção nova na página principal, abaixo do formulário do peer. Dois botões de consulta, com e sem `forcar`, no mesmo formato do peer.

**Decisão.** O formulário é uma `textarea` por família, uma linha por prefixo, no formato `<cidr> [community ...]`:

```
38.252.64.0/22  64512:613 64512:621 15169:12100
38.252.64.0/24  64512:211
```

A community vai na forma completa, com o namespace: o `_forma_ok` do validate exige `ASN:VALOR`, e a forma curta que esta spec mostrava antes seria recusada ao salvar. O `tests/golden/blocos.txt` e o `dados_api.BLOCOS` sempre escreveram assim, e é o documento que estava torto.

É a mesma forma das listas que o app já usa, e o analisador de linha é trivial. Uma tabela com um par de campos por prefixo daria mais HTML e obrigaria um analisador novo para o mesmo resultado.

A marca de ausente entra no fim da linha, e a linha sai marcada na tela antes de salvar. O salvamento ignora a marca: o prefixo continua se a linha continuar, e sai se o operador apagar a linha.

```
38.252.66.0/24  64512:211  !- nao veio na consulta ao IRR
!- 38.252.67.0/24  64512:211
```

Linha que começa com `!-` é ignorada, e isso serve para tirar um prefixo do ar sem perder o tratamento já escrito nele.

Seção na página principal e não página própria porque o cadastro é curto, uma linha por prefixo. Se crescer, vira página como o grupo virou.

O bloco de saída segue o padrão dos outros: um quadro `txt` com os dois fragmentos prontos para colar.

## Alterações no `PLANO.md`

1. **"Originação dos próprios prefixos".** O `preference 1` vira `250`, com o motivo. As três peças ganham a origem da lista, que é a consulta ao IRR no próprio ASN com edição. A subseção "Por que não fazer isso em XPL" perde o corpo e fica como registro de que a limitação foi verificada e não existe na release, no mesmo espírito do `STRIP-EXTERNAL`, que o documento mantém como registro do que não é possível.
2. **"EXPORT-SANITY".** O corpo novo, com o ramo do `1900` e a dispensa da marca para rota originada localmente, junto do parágrafo que explica de que o path vazio depende.
3. **"Origem da rota — 1xxx".** Uma nota no `1000` dizendo que ele é escrito pelo filtro de originação e que ele deixou de ser o que sustenta o anúncio.
4. **"Ponto em aberto" da originação.** Sai, porque foi respondido.
5. **Condição do path vazio.** O `import-route` e o `aggregate` passam a ser condição registrada no documento: qualquer um dos dois quebra a dispensa da marca.

## Testes

Na casa: `test_render.py` para o fragmento gerado, comparando o bloco inteiro contra o esperado; `test_prefixes.py` para a etiqueta da consulta e o cache compartilhado; `test_validate.py` para a tabela de recusa, caso a caso, incluindo o `673` e o large `4:<ASN>`; `test_app.py` para o casamento por prefixo na reconsulta, o marcado que não veio, e o default de manter.

Os dois testes que mudam de valor são os de `EXPORT-SANITY` no `test_render.py`, porque o corpo do filtro muda.

## O que confirmar no equipamento

1. Se o nome do filtro aceita ponto, em `xpl route-filter ORIGEM-38.252.64.0_22`.
2. Se `undo network <ip> <mask>` remove a entrada que tem `route-filter`.
3. Que o `route-filter` do `network` de fato roda na originação e aplica o LP e as communities, e não só na primeira configuração.
4. Que uma rota originada por `network` aparece com AS-path vazio no `display bgp routing-table`, que é a premissa da mudança no `EXPORT-SANITY`.
