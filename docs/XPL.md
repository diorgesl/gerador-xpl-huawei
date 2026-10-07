# Manual de XPL (Huawei VRP)

Guia prático da linguagem de política XPL do VRP, escrito a partir do que este projeto já testou no equipamento e do que os filtros gerados pelo app usam. A política do AS64512 em si está no `PLANO.md`. Aqui fica só a linguagem: como se escreve, o que funciona, o que não funciona e como testar antes de colar.

## Como ler este manual

Cada afirmação vem marcada com o grau de certeza que ela tem:

| Marca          | Significado                                                                          |
| -------------- | ------------------------------------------------------------------------------------ |
| `[F1A]`        | Verificado no NetEngine 8000 F1A, por `?`, `commit` ou `xpl simulate`                |
| `[NE40]`       | Verificado no `rt-tecmais-ne40-downstream`                                           |
| `[NE8K]`       | Verificado no `rt-tecmais-ne8k` ou no `rt-tecmais-ne8k-bgp-ddos`                     |
| `[gerado]`     | Aparece nos blocos que o app gera e que vão para produção, sem teste isolado         |
| `[doc]`        | Vem da documentação da Huawei e não foi testado aqui                                 |
| `[aberto]`     | Ninguém confirmou ainda. Teste com `?` ou `xpl simulate` antes de depender           |

Um comportamento verificado num modelo pode não valer no outro. A armadilha da condição com parênteses depois de `call`, por exemplo, apareceu no NE40. Quando algo der errado num equipamento diferente do que está marcado, desconfie primeiro da diferença de modelo e release.

## O que é o XPL

XPL (Extended Routing-Policy Language) é a linguagem de política do VRP8, presente no NE40E e no NE8000. Ela substitui o `route-policy` clássico, que é organizado em nodes `permit`/`deny` numerados, por um filtro com `if`/`elseif`/`else`/`endif`, mais perto de uma linguagem de programação.

Na prática o ganho está em três pontos:

- O fluxo é lido de cima para baixo, sem precisar pensar em qual node casa primeiro.
- Os filtros aceitam parâmetros, então um filtro serve várias sessões com valores diferentes.
- Um filtro pode chamar outro (`call route-filter`), o que acaba com o copia e cola de regras comuns.

O XPL tem dois tipos de objeto: os **sets** (listas de prefixo, AS-path e community) e os **route-filters**, que usam os sets nas condições.

## Regras gerais de escrita

### Abertura e fechamento

Todo set fecha em `end-list` e todo route-filter fecha em `end-filter`. `[gerado]`

```scss
xpl community-list CL-BLACKHOLE
 65535:666,
 64512:666
 end-list

xpl route-filter EXEMPLO
 if community matches-any CL-BLACKHOLE then
  refuse
 endif
 finish
 end-filter
```

Num set com vários elementos, a vírgula separa um do outro e o último elemento fica sem vírgula. `[gerado]`

### Comentários

O comentário começa com `!-`. `[F1A]`

```scss
xpl route-filter EXEMPLO
 !- este e um comentario valido
 finish
 end-filter
```

O `#` que aparece na saída de `display current-configuration` é separador de seção do VRP. Escrito dentro de um filtro, ele não comenta nada. `[F1A]`

Use só ASCII em comentário e em nome de objeto. A configuração passa por TFTP, backup e diff, e acento costuma quebrar em algum ponto dessa cadeia.

### Uma condição por linha

O `if` não aceita quebra de linha. A condição inteira, com todos os `and` e `or`, precisa caber numa linha só. Quebrar para ficar legível gera erro de sintaxe ao colar. `[F1A]`

Quando a condição fica longa, junte os valores num set e case o set uma vez:

```scss
!- em vez de: if community matches-any {64512:200} or community matches-any {64512:201} or ...
xpl community-list CL-NOADV-UP1
 64512:200,
 64512:201,
 64512:5010
 end-list

 if community matches-any CL-NOADV-UP1 then
  refuse
 endif
```

Além de caber na linha, um `matches-any` contra um set custa menos CPU que várias condições avaliadas em sequência.

### Convenção de nomes deste projeto

`TIPO-FUNCAO-ESCOPO`, tudo em maiúsculas: `PL` para prefix-list, `AP` para as-path-list, `CL` para community-list, `LC` para large-community-list. Exemplos: `PL-BOGONS-V4`, `AP-BLOCK-14840`, `CL-ORIGEM-ANUNCIAVEL`, `LC-NOADV-14840`.

### Aspas: cada cláusula tem a sua regra

Não existe regra geral. Na dúvida, digite a palavra-chave e um `?`: o equipamento mostra se espera aspas.

| Cláusula        | Aspas | Exemplo                       | Fonte   |
| --------------- | ----- | ----------------------------- | ------- |
| `regular`       | Sem   | `regular _0_`, `regular ^$`   | `[F1A]` |
| `origin`        | Com   | `origin '14840'`              | `[F1A]` |
| `pass`          | Com   | `pass '270814'`               | `[F1A]` |
| `peer-is`       | Com   | `peer-is '64510'`             | `[F1A]` |
| `length`        | Sem   | `length ge 40`                | `[F1A]` |
| `unique-length` | Sem   | `unique-length ge 3`          | `[F1A]` |

`pass ''` (aspas vazias) é erro. `length '222'` também é erro. `[F1A]`

## Sets

### Prefix-list

```scss
xpl ip-prefix-list PL-CUST-268127-V4
 45.169.232.0 22,
 45.169.240.0 22 le 24
 end-list

xpl ipv6-prefix-list PL-CUST-268127-V6
 2804:194c:: 32 le 48
 end-list
```

O endereço e o comprimento vão separados por espaço, sem barra. `[gerado]`

| Entrada                     | Casa                                                  |
| --------------------------- | ----------------------------------------------------- |
| `45.169.232.0 22`           | Só o `/22` exato                                      |
| `45.169.232.0 22 le 24`     | O `/22` e os mais específicos até `/24`               |
| `45.169.232.0 22 ge 32 le 32` | Só os `/32` dentro do `/22` (uso típico: blackhole) |
| `0.0.0.0 8 le 32`           | Tudo dentro de `0.0.0.0/8`, do `/8` ao `/32`          |
| `:: 0 le 0`                 | Só o `::/0`                                           |

Atenção à última linha. A `PL-BOGONS-V6` do projeto contém `:: 0 le 0`, então um filtro que chama o `IMPORT-SANITY-V6` antes de tratar a default recusa o `::/0`. No v4 isso não acontece: `0.0.0.0 8 le 32` começa no `/8` e não alcança o `/0`.

### AS-path-list

```scss
xpl as-path-list AP-BOGON-ASN
 regular _0_,
 pass '23456',
 pass '[64496..64511]',
 pass '[64512..65534]'
 end-list
```

O VRP tem cláusulas semânticas que dispensam regex. Prefira essas: a Huawei recomenda no máximo 100 expressões regulares por política e avisa que regex em AS-path é cara em CPU, ainda mais em full table, onde o path é longo. `[doc]`

| Cláusula               | Casa                                             | Regex equivalente | Fonte      |
| ---------------------- | ------------------------------------------------ | ----------------- | ---------- |
| `origin '<asn>'`       | AS que originou o prefixo (o último do path)     | `_<asn>$`         | `[F1A]`    |
| `pass '<asn>'`         | AS em qualquer posição do path                   | `_<asn>_`         | `[F1A]`    |
| `peer-is '<asn>'`      | AS vizinho (o primeiro do path)                  | `^<asn>_`         | `[F1A]`    |
| `length ge <n>`        | Tamanho do path, contando prepends               | sem equivalente   | `[F1A]`    |
| `unique-length ge <n>` | Tamanho do path ignorando prepends               | sem equivalente   | `[F1A]`    |
| `regular <regex>`      | Regex no estilo do VRP (`_` é separador)         |                   | `[F1A]`    |
| `pass '[a..b]'`        | Qualquer AS da faixa                             |                   | `[gerado]` |

`length` e `unique-length` aceitam `eq`, `ge` e `le`. `[F1A]`

`origin` e `pass` não são intercambiáveis. `origin '270814'` recusa o que o 270814 anuncia como dele e aceita quando ele é só trânsito de outro AS. `pass '270814'` recusa qualquer coisa que passe por ele.

Vários elementos no mesmo set funcionam como OU. O modificador `whole-match`, posto depois do valor, transforma uma string com vários ASNs em E: `[doc]`

```text
pass '64500 64501'              => passa por 64500 OU 64501
pass '64500 64501' whole-match  => passa por 64500 E 64501
```

Confirme com `display xpl as-path-list <nome>` antes de depender do `whole-match`.

Path vazio, que é rota originada localmente, se casa com `regular ^$`.

### Community-list

```scss
xpl community-list CL-ORIGEM-ANUNCIAVEL
 64512:1000,
 64512:1100
 end-list

xpl community-list CL-OWN-ALL
 64512:*
 end-list
```

O coringa `*` vale para o campo inteiro e nunca para parte dele. `64512:*` é aceito; `64512:1*` dá erro de sintaxe apontando para o asterisco. `[F1A]` Para recortar uma faixa dentro do campo, enumere os valores ou use `regular`.

A cláusula `regular` existe em community-list e aceita regex. `[F1A]` Cuidado: dentro de `regular` o `*` é operador de regex, não coringa. `64512:4:*` nunca casa `64512:4:14840`. O certo é `^64512:4:[0-9]+$`. `[F1A]`

Uma community-list pode existir vazia (só a abertura e o `end-list`). `[gerado]`

### Large-community-list

```scss
xpl large-community-list LC-NOADV-14840
 64512:0:14840
 end-list
```

O formato é `<ASN>:<dado1>:<dado2>`, com ASN de 32 bits. O coringa `*` só foi verificado em community-list de standard. Em large-community-list ele está `[aberto]`. Para casar uma família inteira, prefira `regular ^64512:4:[0-9]+$`.

### Set inline

Dentro da condição dá para escrever o set direto, entre chaves, sem criar objeto:

```scss
 if ip route-destination in {45.169.232.0 22 le 24} then
 if community matches-any {64512:5014} then
 if large-community matches-any {64512:0:14840} then
```

A forma inline de prefixo segue a mesma convenção da prefix-list nomeada. `{0.0.0.0 0 ge 32 le 32}` é qualquer rota de host. `[gerado]`

Dois pontos sobre a forma inline continuam `[aberto]`: se `le` sem `ge` é aceito (os blocos gerados já usam, mas ninguém confirmou isoladamente) e se `{0.0.0.0 0}`, sem `ge`/`le`, casa só a default.

## Route-filter

### Estrutura

```scss
xpl route-filter NOME
 if <condicao> then
  <acoes>
 elseif <condicao> then
  <acoes>
 else
  <acoes>
 endif
 <acoes>
 <terminador>
 end-filter
```

`if` aninhado é permitido. `[gerado]`

### Condições

| Condição                                     | Exemplo                                              | Fonte      |
| -------------------------------------------- | ---------------------------------------------------- | ---------- |
| `ip route-destination in <set>`              | `if ip route-destination in PL-BOGONS-V4 then`       | `[gerado]` |
| `ipv6 route-destination in <set>`            | `if ipv6 route-destination in {:: 0 ge 128 le 128} then` | `[gerado]` |
| `as-path in <set>`                           | `if as-path in AP-BLOCK-14840 then`                  | `[gerado]` |
| `community matches-any <set>`                | `if community matches-any CL-GSHUT then`             | `[gerado]` |
| `large-community matches-any <set>`          | `if large-community matches-any LC-NOADV-14840 then` | `[gerado]` |
| `tag eq <n>`                                 | `if tag eq 666 then`                                 | `[gerado]` |
| `not <condicao>`                             | `if not as-path in AP-LOCAL-ORIGIN then`             | `[gerado]` |
| `<a> and <b>`, `<a> or <b>`                  | ver precedência abaixo                               | `[gerado]` |

Num filtro v6 a condição de prefixo é `ipv6 route-destination`. Um `ip route-destination` dentro de filtro v6 está errado: ou o equipamento recusa ao colar, ou a condição nunca casa rota v6 e o `refuse` dela nunca roda.

Existem outras condições (por next-hop, MED, origem da rota, `matches-all` em community). Elas não foram testadas aqui. Confira com `if ?` dentro da view do route-filter. `[doc]`

### Precedência de `and` e `or`

`and` liga mais forte que `or`. `A or B and C` é lido como `A or (B and C)`. Use parênteses em toda condição que mistura os dois. `[F1A]`

Mas veja a armadilha dos parênteses depois de `call`, mais abaixo. No NE40 ela derruba o commit.

### Ações

| Ação                                           | Exemplo                                          | Fonte      |
| ---------------------------------------------- | ------------------------------------------------ | ---------- |
| `apply local-preference <n>`                   | `apply local-preference 300`                     | `[gerado]` |
| `apply med <n>`                                | `apply med 0`                                    | `[gerado]` |
| `apply as-path <asn> <vezes> additive`         | `apply as-path 64512 3 additive`                 | `[F1A]`    |
| `apply community <set> additive`               | `apply community {64512:1100} additive`          | `[gerado]` |
| `apply community <set> overwrite`              | `apply community {64512:1400, 64512:2000} overwrite` | `[gerado]` |
| `apply community <lista> additive`             | `apply community CL-PEER-14840 additive`         | `[F1A]`    |
| `apply large-community <set> additive`         | `apply large-community {64512:1000:268127} additive` | `[gerado]` |
| `apply large-community <set> overwrite`        | `apply large-community {64512:1000:14840} overwrite` | `[gerado]` |
| `apply ip next-hop <ip>`                       | `apply ip next-hop 192.0.2.1`                    | `[gerado]` |
| `apply ipv6 next-hop <ip>`                     | (mesma forma no v6)                              | `[gerado]` |

Detalhes que já custaram tempo:

- **Prepend é ASN + contador.** `apply as-path 64512 3 additive` prepende o 64512 três vezes. No `route-policy` clássico os ASNs são listados um a um (`64512 64512 64512`). Em XPL, o segundo número é a contagem, não outro ASN. `[F1A]`
- **O contador começa em 1.** `apply as-path <asn> 0 additive` é recusado. `[NE8K]`
- **O ASN do prepend aceita 32 bits** (`INTEGER<1-4294967295>`). `apply as-path 264130 3 additive` foi aceito. `[NE8K]`
- **O nome da lista vai direto.** `apply community CL-PEER-14840 additive`. Escrever `apply community community-list CL-PEER-14840`, como no `route-policy`, é aceito sem erro, porque o VRP lê `community-list` como se fosse uma community, e a lista nunca é aplicada. Vale o mesmo para `large-community-list`. `[F1A]`
- **Community só tem `overwrite` e `additive`.** Não existe `apply community <lista> delete` em route-filter. Não dá para remover uma community específica. `[F1A]`
- **`overwrite` com conjunto vazio é recusado.** `apply community {} overwrite` não passa no parser. Não há como zerar as communities de uma rota. `[F1A]`
- **`overwrite` antes de `additive`.** O `overwrite` substitui o conjunto inteiro, então tudo que foi aplicado antes dele no mesmo filtro some.
- **`overwrite` de community não toca large community.** São atributos separados, cada um com o seu `apply`.

Duas ações seguem `[aberto]` em route-filter: `apply preference` e `apply preferred-value`. Elas existem no `route-policy`; confira com `?` se existem na view do route-filter da sua release.

### Terminadores: como o filtro decide

Esta é a parte que mais engana. Leia com calma.

| Terminador | O que faz                                                                                          | Fonte   |
| ---------- | -------------------------------------------------------------------------------------------------- | ------- |
| `finish`   | Aceita a rota e encerra o processamento inteiro, inclusive o do filtro que fez o `call`            | `[F1A]` |
| `refuse`   | Recusa a rota e encerra o processamento inteiro                                                    | `[F1A]` |
| `break`    | Sai do filtro atual. Se ele foi chamado por `call`, o controle volta para a linha seguinte ao `call` | `[F1A]` |
| `approve`  | **Não encerra nada.** Só reencaminha a rota para o próximo `if`                                     | `[doc]` |

**O filtro nega por padrão.** Se a rota chega ao `end-filter` sem que nenhum `finish`, `refuse` ou `apply` tenha rodado, ela é recusada. `[doc]` Por isso todo filtro de sessão precisa terminar em `finish`. Esquecer o `finish` faz o filtro recusar justamente as rotas que deveria deixar passar.

Exemplo real: o filtro abaixo foi escrito para aceitar a default e bloquear rotas que passam por dois ASNs, e não deixava passar nada além da default.

```scss
!- ERRADO: a rota que nao casa nenhum if chega ao fim sem acao e e negada
xpl route-filter DEFAULT-PARTIAL-ESPECIFICO
 if ip route-destination in {0.0.0.0 0} then
  apply local-preference 100
  finish
 endif
 if as-path in AP-BLOCK-ESPECIFICO then
  refuse
 endif
 end-filter

!- CERTO: finish no fecho
xpl route-filter DEFAULT-PARTIAL-ESPECIFICO
 if ip route-destination in {0.0.0.0 0} then
  apply local-preference 100
  finish
 endif
 if as-path in AP-BLOCK-ESPECIFICO then
  refuse
 endif
 finish
 end-filter
```

**`approve` não para o filtro.** Um ramo que aprova com `approve` e segue em frente pode ter a rota recusada logo depois por outra checagem. Quando quiser terminar ali, use `finish`.

### `call route-filter`

Um filtro pode chamar outro:

```scss
 call route-filter IMPORT-SANITY-V4
```

O `call` não funciona como sub-rotina comum. O terminador do filtro **chamado** decide o destino da rota no filtro de fora: `[F1A]`

| O filtro chamado termina em           | Resultado                                                                       |
| ------------------------------------- | ------------------------------------------------------------------------------- |
| `finish`                              | A rota é aceita e a cadeia inteira acaba. O filtro de fora **não** continua      |
| `refuse`                              | A rota é recusada e a cadeia inteira acaba                                      |
| `break`                               | O controle volta para a linha depois do `call`                                  |
| `break` sem nenhum `apply` no caminho | Também volta, sem disparar a negação por padrão                                 |

Daí a regra que este projeto segue: **filtro compartilhado, que roda no meio de outro, fecha em `break`. Quem dá o veredito é sempre o filtro da sessão.**

```scss
xpl route-filter IMPORT-SANITY-V4
 if ip route-destination in PL-BOGONS-V4 then
  refuse
 endif
 if as-path in AP-BOGON-ASN then
  refuse
 endif
 break
 end-filter
```

Com `finish` no lugar do `break`, todo import que chama o `IMPORT-SANITY` pararia na chamada e a rota boa nunca chegaria ao resto do filtro da sessão.

### Armadilha: parênteses depois de `call`

Um `if (A or B) and C then` que aparece depois de qualquer `call route-filter` no mesmo filtro entra sem erro como objeto solto. O `commit` falha (`Error: Failed to commit configuration.`) assim que o filtro é pendurado num peer, e a mensagem não diz o motivo. `[NE40]`

O que passa:

- a mesma condição como primeira linha do filtro, antes do `call`;
- `A or B`, sem parênteses, depois do `call`;
- o `if` aninhado, que é a forma que o projeto usa:

```scss
 call route-filter IMPORT-SANITY-V4
 !- em vez de: if (A or B) and C then
 if ip route-destination in PL-CUST-268127-BH-V4 then
  if community matches-any CL-BLACKHOLE or tag eq 666 then
   ...
  endif
 endif
```

Ainda `[aberto]`: `(A or B)` sozinho, sem o `and`, depois de um `call`.

### Parâmetros

O filtro pode declarar parâmetros na assinatura e recebê-los na sessão:

```scss
xpl route-filter UP-IMPORT-14840($lp_base)
 apply local-preference $lp_base
 finish
 end-filter

bgp 64512
 ipv4-family unicast
  peer 203.0.113.1 route-filter UP-IMPORT-14840(100) import
```

O que se sabe:

- O parâmetro só funciona como **valor dentro de uma cláusula**: `apply local-preference $lp_base`, `apply as-path 64512 $prepend_base additive`.
- Ele **não** funciona como condição. `if $prepend_base eq 1 then` falha, porque o XPL não tem cláusula genérica de comparação. As condições são todas presas a atributos da rota. Qualquer conta tem que ser feita antes, por quem gera a linha do peer.
- **Filtro com parâmetro não pode ser simulado.** O `xpl simulate enable` recusa. Para testar, faça uma cópia com o valor literal. `[F1A]`

- **Parâmetro não entra em set literal.** `apply large-community {64512:1:$peer_asn}` é recusado com `Error: Unrecognized command found at '^' position.` (verificado no equipamento em 2026-10-07). Um filtro genérico que monta a community a partir do ASN não existe: cada peer precisa do valor escrito por extenso no filtro dele. O teste foi com large community; com standard (`{64512:$x}`) a forma não foi testada, mas não há motivo para esperar outro resultado.
- **Filtro com parâmetro aceita ser referenciado sem ele.** Um filtro declarado com `($x)` é aceito sem os parênteses (verificado no equipamento em 2026-10-07).

Ainda `[aberto]`: o que acontece com a linha que usa o parâmetro quando ele não vem. `apply as-path 64512 $prepend_base additive` sem valor pode ser pulada, pode recusar a rota ou pode aplicar algum padrão. O equipamento aceitar a configuração não diz qual dos três acontece. Enquanto ninguém olhar, a sessão sem prepend continua com uma variante própria do filtro, sem o parâmetro. Como filtro com parâmetro não simula, o teste é pela `advertised-routes` de uma sessão de baixo risco, ou por um filtro de fora sem parâmetro que faça `call` no parametrizado sem os parênteses, se esse `call` for aceito.

## Onde o route-filter se pendura

```scss
bgp 64512
 ipv4-family unicast
  peer 203.0.113.1 route-filter UP-IMPORT-14840(100) import
  peer 203.0.113.1 route-filter UP-EXPORT-14840(1) export
  peer 203.0.113.1 advertise-community
  peer 203.0.113.1 advertise-large-community
  network 201.131.152.0 22 route-filter ORIGEM-PROPRIA
```

- **Import e export de peer**, dentro da família. `[gerado]`
- **`network`.** `network <ip> <mask> route-filter <nome>` existe e completa com `label-index`, `non-relay-tunnel` e `<cr>`. `[F1A]` Se o filtro roda de fato na originação, aplicando LP e communities, ainda está `[aberto]`: confira com `display bgp routing-table <prefixo>`.
- **`advertise-community` não é padrão**, nem em iBGP. Sem ele a community não sai, por mais que o filtro a aplique. O mesmo vale para `advertise-large-community`.
- **A default de `default-route-advertise` não passa pelo filtro de export.** O VRP origina `0.0.0.0/0` e `::/0` na sessão mesmo sem default na RIB, e por fora do route-filter. Nenhum `refuse` do export a segura. `[F1A]`
- **Ao habilitar o peer**, o VRP pergunta `This operation will reset the peer session. Continue? [Y/N]`. Num bloco colado, inclua a linha `y` logo depois, senão o resto do bloco cai no prompt.

## Testar antes de colar

### `?` resolve dúvida de sintaxe

Digite a palavra-chave e `?` dentro da view do set ou do filtro. É o jeito mais rápido de saber se uma cláusula existe, se leva aspas e que valores aceita.

### `xpl simulate`

Roda o filtro contra a tabela BGP de verdade, sem aplicar em sessão nenhuma. `[F1A]`

```text
system-view
xpl simulate enable bgp route-filter <nome>
commit
quit
display bgp routing-table route-filter <nome>
```

- O `commit` do meio é obrigatório. Sem ele o `enable` fica pendente e o `display` não mostra nada.
- O `display` mostra a tabela como ela ficaria **depois** do filtro: a rota recusada some, a aceita aparece.
- Os atributos exibidos são os de **antes** do filtro. Um `apply med 111` não muda o MED mostrado.
- Para ver quantas rotas foram aceitas e negadas: `display xpl route-filter name <nome> detail`.
- Filtro com parâmetro não simula. Use uma cópia com o valor literal.
- A Huawei indica teto de 1024 filtros armados. `[doc]` Desarme ao terminar: `undo xpl simulate enable bgp route-filter <nome>`.

Os contadores `permit` e `deny` só andam no filtro armado ou pendurado numa sessão. Um filtro que só roda via `call` mostra `permit: 0, deny: 0` mesmo rodando em toda rota da tabela. Ler `0/0` como "nunca rodou" leva à conclusão errada de que o `call` não funciona. `[F1A]`

### Bisseção com peer falso

Quando um bloco passa na colagem e falha no `commit` sem dizer por quê, não mexa na sessão real. Crie um peer descartável com `ignore`, pendure nele o filtro suspeito e vá tirando metades até achar a linha. Foi assim que a armadilha dos parênteses apareceu no NE40. `[NE40]`

```scss
bgp 64512
 peer 192.0.2.254 as-number 64496
 peer 192.0.2.254 ignore
 ipv4-family unicast
  peer 192.0.2.254 enable
  peer 192.0.2.254 route-filter FILTRO-SUSPEITO import
```

### Comandos de verificação

```text
display xpl as-path-list <nome>
display xpl community-list <nome>
display xpl large-community-list <nome>
display xpl ip-prefix-list <nome>
display xpl route-filter <nome>
display xpl route-filter name <nome> detail
display xpl route-filter name <nome> uses

display bgp routing-table route-filter <nome>
display bgp routing-table <prefixo>
display bgp routing-table peer <ip> advertised-routes
display bgp routing-table peer <ip> received-routes
display bgp peer <ip> verbose
```

O `advertised-routes` é o que prova que o export faz o que você acha que faz. O `received-routes` mostra o que o peer mandou antes do import, e é o primeiro lugar para olhar quando uma rota "não entra".

## Pode e não pode: resumo

| Pode                                                                 | Não pode                                                          |
| -------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `64512:*` (coringa no campo inteiro)                                 | `64512:1*` (coringa em parte do campo)                            |
| `regular ^64512:4:[0-9]+$` em community-list                         | `regular 64512:4:*` esperando que o `*` seja coringa              |
| `apply community {..} overwrite` e `additive`                        | `apply community {..} delete`                                     |
| `apply community {64512:1} overwrite`                                | `apply community {} overwrite`                                    |
| `apply community CL-LISTA additive`                                  | `apply community community-list CL-LISTA` (aceito, mas não aplica) |
| `apply as-path 64512 3 additive`                                     | `apply as-path 64512 64512 64512 additive` (forma do route-policy) |
| `apply as-path 64512 1 additive`                                     | `apply as-path 64512 0 additive`                                  |
| Parâmetro como valor: `apply local-preference $lp`                   | Parâmetro como condição: `if $lp eq 100 then`                     |
| Valor fixo no set: `{64512:1:14840}`                                 | Parâmetro no set: `{64512:1:$peer_asn}`                           |
| `xpl simulate` em filtro sem parâmetro                               | `xpl simulate` em filtro com parâmetro                            |
| Condição inteira numa linha                                          | Condição quebrada em várias linhas                                |
| `if (A or B) and C` como primeira linha do filtro                    | `if (A or B) and C` depois de um `call` (NE40: commit falha)      |
| `break` no fecho de filtro chamado por `call`                        | `finish` no fecho de filtro compartilhado                         |
| `finish` no fecho do filtro da sessão                                | Filtro de sessão terminando sem terminador                        |
| Comentário com `!-`                                                  | Comentário com `#`                                                |
| Comentário em ASCII                                                  | Acento em comentário ou nome                                      |
| `network ... route-filter <nome>`                                    | Esperar que o export filtre a default de `default-route-advertise` |
| `origin`, `pass`, `peer-is`, `length` em vez de regex                | Mais de 100 regex numa política (recomendação da Huawei)          |

## Padrões prontos

### Aceitar a default e bloquear rotas que passam por certos ASNs

```scss
xpl as-path-list AP-BLOCK-ESPECIFICO
 pass '14840',
 pass '53062'
 end-list

xpl route-filter DEFAULT-E-BLOQUEIO
 if ip route-destination in {0.0.0.0 0} then
  apply local-preference 100
  finish
 endif
 if as-path in AP-BLOCK-ESPECIFICO then
  refuse
 endif
 finish
 end-filter
```

Se a sessão for com um dos ASNs bloqueados, todas as rotas dele passam por ele, e só a default entra. Para bloquear o ASN só quando ele aparece atrás do vizinho, troque `pass` por `origin` ou escreva um `regular` que exclua a primeira posição.

### Aceitar só a default e a parcial de um upstream

```scss
!- o que o 14840 origina e o que vem de cliente direto dele
xpl as-path-list AP-PARCIAL-14840
 unique-length le 2
 end-list

xpl route-filter UP-14840-IMPORT-V4
 !- default antes do sanity: no v6 o PL-BOGONS-V6 recusaria o ::/0
 if ip route-destination in {0.0.0.0 0} then
  apply local-preference 100
  apply community {64512:1400, 64512:3100, 64512:2000} overwrite
  apply large-community {64512:1000:14840} overwrite
  finish
 endif
 call route-filter IMPORT-SANITY-V4
 if not as-path in AP-PARCIAL-14840 then
  refuse
 endif
 apply local-preference 100
 apply community {64512:1400, 64512:3100, 64512:2000} overwrite
 apply large-community {64512:1000:14840} overwrite
 finish
 end-filter
```

`unique-length le 2` dentro de as-path-list está `[aberto]`: o projeto só usou `length ge 40` dentro de lista. Confira com `?`.

### Escada de local preference reaproveitável

```scss
xpl route-filter APPLY-CUSTOMER-LP
 if community matches-any {64512:101} then
  apply local-preference 50
  break
 endif
 if community matches-any {64512:104} then
  apply local-preference 250
  break
 endif
 apply local-preference 300
 break
 end-filter

xpl route-filter CUST-IMPORT-268127
 call route-filter IMPORT-SANITY-V4
 if not ip route-destination in PL-CUST-268127-V4 then
  refuse
 endif
 call route-filter APPLY-CUSTOMER-LP
 apply community {64512:1100} additive
 finish
 end-filter
```

Cada degrau fecha em `break` para o seguinte não sobrescrever o LP, e para o filtro da sessão continuar depois do `call`.

### Prepend escolhido pelo cliente

```scss
 if community matches-any {64512:5014} then
  apply as-path 64512 3 additive
 elseif community matches-any {64512:5013} then
  apply as-path 64512 2 additive
 elseif community matches-any {64512:5012} then
  apply as-path 64512 1 additive
 endif
```

O `elseif` garante que só um degrau roda. Com três `if` separados, uma rota com as três communities levaria seis prepends.

## Pontos em aberto

| Pergunta                                                                  | Como resolver                                      |
| ------------------------------------------------------------------------- | -------------------------------------------------- |
| `{0.0.0.0 0}` inline casa só a default?                                   | `xpl simulate` num filtro com só essa condição     |
| A forma inline aceita `le` sem `ge`?                                      | `?` e `xpl simulate`                               |
| Coringa `*` funciona em large-community-list?                             | `?` na view do large-community-list                |
| `unique-length` dentro de as-path-list aceita `le`?                       | `?` na view do as-path-list                        |
| Linha com `$x` num filtro referenciado sem o parâmetro: pula, recusa ou aplica padrão? | `advertised-routes` de sessão de baixo risco |
| `apply preference` e `apply preferred-value` existem em route-filter?     | `?` na view do route-filter                        |
| `(A or B)` sem `and` depois de `call` também derruba o commit no NE40?    | Bisseção com peer falso                            |
| O route-filter do `network` roda na originação?                           | `display bgp routing-table <prefixo>`              |
| A rota originada por `network` sai com AS-path vazio?                     | `display bgp routing-table <prefixo>`              |

Quando um destes for resolvido, atualize a marca neste manual e o ponto correspondente no `PLANO.md`.
