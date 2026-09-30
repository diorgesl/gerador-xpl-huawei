# Community por prefixo do downstream — AS64512

2026-09-29

## Problema

O campo `prefixos` do peer guarda o que aquele downstream pode anunciar, e o import da sessão usa essa lista como confinamento: `PL-CUST-<T>-<U>` libera o que está nela e os mais específicos até /24 (v4) e /48 (v6), e recusa o resto.

O que o campo não permite é tratar um prefixo diferente do outro. A CL-PEER aplica as mesmas communities em tudo que a sessão anuncia. Um downstream, cliente ou parceiro, que anuncia um /22 e dois /23 dentro dele recebe o mesmo tratamento nos três, e não há onde dizer que um dos /23 sai só por um dos dois upstreams de mesmo ASN. O cliente pode pedir por conta própria, escrevendo a community na sessão dele, mas o pedido vale para a sessão inteira e ele não conhece o identificador dos peers da operadora, que é o que o eixo `5PPA` exige.

O bloco próprio já resolve o problema do lado do prefixo do AS: cada linha carrega a lista de communities e o egress lê. Esta spec leva a mesma forma para o prefixo do downstream.

## O que já existe e o que falta

| Peça | Estado |
| --- | --- |
| `Bloco`, com prefixo, communities e ativo | existe, `app/peers.py:443` |
| Análise da linha `<cidr> community...` e do `!-` | existe, `formulario._blocos_do_formulario`, `app/formulario.py:97` |
| Mesclagem por prefixo na reconsulta ao IRR | existe, `peers.mesclar_blocos`, `app/peers.py:513` |
| Tabela de recusa de community do bloco próprio | existe, `validate._motivo_da_recusa`, `app/validate.py:163` |
| Import do downstream, com o confinamento e a CL-PEER | existe, `_macros.j2:133` |
| Community na linha do prefixo do peer | **não existe** |
| Cláusula por prefixo no import gerado | **não existe** |
| Casamento por prefixo no `/api/irr` | **não existe**: hoje o resultado da consulta substitui a lista inteira |

## Escopo

### O que entra

- `Peer.prefixos` passa a ser lista de `Bloco`, por família, lendo os dois formatos: a string de hoje e a linha tratada. Vale para os dois tipos de downstream, cliente e parceiro, que já compartilham o campo, o template e os filtros.
- Cadeia de cláusulas por prefixo no `CUST-<T>-IMPORT-<U>` do peer avulso, depois da CL-PEER, do prefixo mais longo para o mais curto.
- Validação das communities da linha pela mesma tabela do bloco próprio, com o `1xx` a mais.
- Reconsulta ao IRR casando por prefixo, com o tratamento preservado e o ausente marcado.
- Ajuda na tela, e o `!-` valendo como no bloco próprio.
- Atualização do `PLANO.md`.
- Testes.

### O que não entra

- **O grupo.** O `prefixos` do grupo continua lista de CIDRs pura, e a linha com mais de um campo é erro com mensagem própria. O grupo herda esta forma depois, se precisar.
- **`te_prefixos`.** A exceção de TE é eixo do upstream e alimenta prefix-list própria; fica como está.
- **Seletor de communities na seção de prefixos.** A seção fica com texto livre, como a tela de prefixos próprios. O `AdicionarCommunity` continua só na CL-PEER.
- **Vínculo entre a linha e o prefixo além do CIDR.** Não há id na linha, pela razão do bloco próprio: o prefixo é o identificador.
- **Coerência entre o escopo da linha e o escopo da CL-PEER.** As duas listas somam, e o efeito da soma contraditória fica documentado, não validado (ver "A soma com a CL-PEER").
- **Escrita de community pelo cliente na sessão dele.** Nada muda na CL-PEER.

## O dado

```yaml
peers:
- id: 33
  asn: 268127
  prefixos:
    v4:
    - prefixo: 45.163.212.0/22
      communities: [64512:210, 64512:5070]
    - prefixo: 45.163.212.0/23
      ate: 24
    v6:
    - prefixo: 2804:3300::/32
```

O `ate` é o intervalo da linha, e ele só aparece quando o operador escreve o sufixo: vazio é o prefixo exato. A string do yaml não o comporta, então uma linha com intervalo grava dicionário mesmo sem community.

**Decisão.** A string carrega o CIDR e nada mais; o dicionário, quando houver tratamento, é lido como o bloco próprio, por `Bloco.de_dict`, com campo desconhecido ignorado. A leitura não separa espaço na string: o formato da tela vale na tela, e uma forma só na representação é o que impede um `peers.yaml` editado à mão de virar um segundo jeito de escrever a mesma coisa. É a mesma tolerância que o `Peer.de_dict` já tem com o `token` das versões antigas: o `peers.yaml` de hoje carrega sem migração.

A canonicalização do CIDR acontece na leitura, como em `carregar_blocos`, com uma versão que devolve o texto como veio quando não analisa. O validate é que recusa, nomeando o prefixo, e não a leitura: um `peers.yaml` com CIDR torto tem que carregar para o operador ler a mensagem na tela, em vez de o app morrer no GET.

Essa função já existe como `formulario._canoniza`, e ela muda de casa em vez de ser copiada: vai para `peers.canoniza`, público, e o formulário passa a importar de lá, que é de onde ele já traz o `Bloco`. O contrário não serve, porque o `peers.py` importar o formulário fecharia um ciclo de import.

**Decisão.** A gravação escreve string quando a linha não tem tratamento e está ativa, e dicionário quando tem community ou está com `!-`:

```yaml
    v4:
    - prefixo: 45.163.212.0/22
    - prefixo: 45.163.212.0/23
      communities: [64512:210]
```

O bloco próprio grava dicionário sempre, mas lá a seção inteira nasce com a feature. Aqui o campo já existe na forma de string em todo `peers.yaml` do mundo, e o `gravar` reescreve o arquivo a cada POST: sem esta regra, o primeiro salvamento de qualquer peer viraria um diff de forma em todos os outros, e a mudança apareceria em revisão de código sem ter sido pedida.

**Decisão.** `cidrs(fam)` devolve os prefixos ativos, e é o que as duas prefix-lists e a cláusula por prefixo consomem. `tratamentos(fam)` devolve os pares (prefixo, communities) ativos com community, já ordenados do mais longo para o mais curto, que é a ordem da cadeia. Os dois métodos existem no `Peer` e no `Grupo`, porque as macros do import são de alvo duplo e o `StrictUndefined` do render estoura no teste se um método faltar; no grupo, `tratamentos` devolve lista vazia e `cidrs` devolve a lista de hoje.

Linha com `!-` continua contando para o `tem_filtro_proprio` do membro de grupo: o efeito dela na configuração é o mesmo de não estar escrita, e a lista toda em `!-` é a decisão de quem a escreveu, não um acidente.

## A linha e a tela

Mesmo formato da tela de prefixos próprios, uma textarea por família, com o intervalo opcional depois do comprimento:

```
138.97.60.0/22  64512:210 64512:5070
138.97.60.0/23-24  64512:210 64512:5132
```

A community vai na forma completa, como a CL-PEER e o bloco próprio. O `_forma_ok` do validate exige `ASN:VALOR` com o namespace, então a forma curta que a spec do bloco próprio usa no exemplo da tela (`613 621`), e que o próprio bloco próprio recusaria, não entra aqui.

`!-` no começo deixa a linha fora do PL-CUST e fora da cláusula, com o cadastro preservado. Num peer a consequência é mais forte do que num prefixo próprio: o prefixo sai da lista de confinamento, então a rota dele passa a ser recusada no import da sessão, que é o que fora de serviço significa deste lado. O `!-` no fim da linha é a marca do que sumiu da consulta ao IRR, e o salvamento ignora o que vem depois dele.

A seção de prefixos ganha um texto de ajuda no tom do que a tela de prefixos próprios já tem, dizendo o formato da linha e o efeito do `!-` nas duas pontas. É a única mudança de tela obrigatória, e vale porque o campo hoje não tem ajuda nenhuma: quem digita community lá pela primeira vez descobre o formato pela mensagem de erro, que é o que aconteceu com esta spec.

Nada muda no `Formulario.tsx`: o campo é do tipo `area`, que já junta as linhas da lista com `\n` e as separa na volta (`web/src/components/Formulario.tsx:200`), então a linha com community atravessa a tela como uma string qualquer.

## O XPL gerado

O `PL-CUST-<T>-<U>` e o `PL-CUST-<T>-BH-<U>` não mudam de forma. O que entra é uma cadeia no fim do `CUST-<T>-IMPORT-<U>`, depois do `call APPLY-PEER-<T>`:

```
xpl route-filter CUST-268127-IMPORT-V4
 call route-filter IMPORT-SANITY-V4
 ...
 call route-filter APPLY-PEER-268127
 !- tratamento por prefixo do cadastro, do mais especifico para o menos
 if ip route-destination in {45.163.212.0 23 le 24} then
  apply community {64512:210, 64512:5132} additive
 elseif ip route-destination in {45.163.212.0 22} then
  apply community {64512:210, 64512:5070} additive
 endif
 finish
end-filter
```

As regras da cadeia:

- **Ordem.** Do prefixo mais longo para o mais curto e, no mesmo prefixo, a linha exata antes das com intervalo, do mais estreito para o mais largo. Dois tratamentos que se sobrepõem (um /22 e um /23 dentro dele) aplicam só o mais específico, e o `/22` exato vence o `/22-24` na rota do próprio `/22`, porque o aninhamento é `if/elseif` e não uma sequência de cláusulas soltas. Sem isso, as duas linhas somariam, e dois escopos de `2xx` incompatíveis na mesma rota a deixariam recusada em todo egress, em silêncio.
- **Alcance.** A linha carrega o próprio alcance: `138.97.60.0/22-24` vira `{138.97.60.0 22 le 24}` e a linha sem sufixo vira `{138.97.60.0 22}`, o prefixo exato. O intervalo é limitado pelo teto do `PL-CUST` (24 no v4, 48 no v6), que continua sendo o que define o que a sessão aceita; um intervalo acima dele é avisado na tela, e não é erro. O teto mora no `plan.py`, num `TETO_PREFIXO = {"v4": 24, "v6": 48}` que a macro do confinamento e a validação leem, para não haver dois números.
- **O confinamento segue o mesmo alcance.** O `PL-CUST` do import usa a mesma linha: sem sufixo, a entrada é o prefixo exato (`45.169.236.0 23`) e o mais específico anunciado pelo cliente é recusado no import; com `-24`, a entrada sai `45.169.236.0 23 le 24` e os mais específicos entram tratados. A lista e a cláusula dizem a mesma coisa sobre o mesmo prefixo, e o grupo é a exceção: o campo dele não tem sufixo, e as entradas dele continuam no teto, como sempre foram.
- **Forma.** `{<endereco> <comprimento> le <teto>}`, montado por um `plan.conjunto_do_prefixo(cidr, teto)` novo, que devolve o literal pronto. Não falta helper de comprimento no `plan.py`: o `cidr_para_xpl` que as prefix-lists já usam entrega endereço e comprimento juntos, na forma `45.169.232.0 22`. A montagem fica no Python porque em Jinja o `{{` seguido de `{` fecha a expressão, que é o caso que a macro do blackhole contorna com uma string literal. O v6 usa o mesmo `ip route-destination` que a macro já escreve nas duas famílias.
- **Posição.** Depois do `APPLY-PEER`, e não antes. O `1xx` da linha vence o da CL-PEER porque a última escrita de local-preference vence, que é a mesma regra que o export de upstream já documenta. A cadeia fica antes do `finish` que já fecha o filtro hoje, então nenhuma cláusula dela pode saltar o tratamento que a sessão recebeu.
- **Forma dupla.** Standard e large saem em linhas separadas, com o `plan.separa_communities` e o `plan.conjunto_de` que o bloco próprio já usa. As duas aplicações são `additive`, porque o import do cliente tem que preservar o que a sessão já carimbou antes.

A cadeia só é emitida quando há tratamento; o peer sem nenhuma linha com community sai byte a byte como sai hoje.

Cliente e parceiro são a mesma implementação, e não duas com o mesmo desenho: os dois tipos saem do `cliente.txt.j2` (`render.TEMPLATE_POR_TIPO` manda o parceiro para lá) e passam pelo mesmo `filtro_downstream_import`. O que muda entre os dois é o carimbo de origem, o POP e o `2091` do parceiro, tudo escrito antes da cadeia, pelo código que já existe. A cláusula por prefixo entra igual nos dois, e o teste do parceiro existe para fixar que a cadeia vem depois do carimbo do tipo, e não no lugar dele.

## Validação

A tabela do bloco próprio vale aqui, com uma diferença: o `1xx` é lido pelo `APPLY-CUSTOMER-LP` no import do downstream, então é aceito. É a diferença que o bloco próprio recusa justamente por não passar por import nenhum, e por isso a mensagem daqui tem que dizer o efeito real, e não copiar a de lá.

| Recusa | Motivo |
| --- | --- |
| `3xx`, `4xx`, `7xx`, `8xx` | faixas sem dono no plano |
| `2xx` fora de `200`–`204` e `210`–`213` | nenhum ramo de egress lê |
| `6CA` com classe fora de `1`, `2` e `4`, ou dígito fora de `1`–`4` e `9` | `CLASSE_6CA` e `DIGITO_PREPEND` |
| `5PPA` com dígito fora de `0`–`4` | `CL-5PPA-<id>` cobre `range(5)` |
| large `4:<ASN>` | anunciar somente para um ASN não tem ramo no egress |
| `2000` | o egress de upstream, IX e PNI recusa a rota que o carrega |

As informativas continuam aceitas, como no bloco próprio, e a diferença de efeito fica registrada: a marca informativa da sessão (origem, geografia, POP, e o `2091` do parceiro) é escrita pelo import antes da cláusula, e a da linha soma em cima. Quem escrever `2101` numa linha de downstream ganha duas marcas informativas no mesmo prefixo, e o `display` mostra as duas.

Mais duas regras que o campo ainda não tem:

- **Prefixo repetido** é erro, com a mensagem que o bloco próprio já usa. Com duas linhas do mesmo prefixo, o comprimento empata, a ordem do cadastro desempata, e a segunda linha fica morta em silêncio. É a única regra daqui que o bloco próprio já tem e o campo do peer ainda não tinha.
- **Máscara mais longa que o teto** gera aviso, e não erro. A linha continua nascendo, mas o confinamento não deixa passar rota mais específica que o teto, então a linha `45.163.212.0/25` casaria uma cláusula que nenhuma rota alcança. Aviso e não erro porque o `peers.yaml` de hoje aceita essa linha, e transformar em erro travaria o salvamento de um cadastro que sempre funcionou.

No grupo, uma linha com mais de um campo é erro no campo `prefixos_v4`/`prefixos_v6`, com mensagem própria dizendo que o tratamento por prefixo é do peer avulso. É o que transforma a tentativa no lugar errado numa frase, em vez do "prefixo invalido: 45.163.212.0/22 64512:210" de agora.

## A soma com a CL-PEER

As duas listas somam, e a linha não substitui nada da sessão. Os três casos que valem registrar:

- **Local preference.** O `1xx` da linha vence o da CL-PEER, pela ordem das cláusulas.
- **Escopo.** Duas marcas de `2xx` incompatíveis na mesma rota (uma da CL-PEER, outra da linha) fazem o egress recusar dos dois lados, e a rota não sai por lugar nenhum. Não é risco novo: duas marcas incompatíveis já cabem na CL-PEER sozinha, e o plano nunca teve validação de coerência entre eixos.
- **Prepend.** Os dígitos das duas listas somam no conjunto, e a cadeia de prepend do egress testa do maior para o menor, então vale o maior prepend pedido.

## A reconsulta ao IRR

O `POST /api/irr` passa a receber as linhas que estão na tela e a devolvê-las mescladas, com o mesmo casamento por prefixo que o `/api/blocos/irr` já faz:

- prefixo que veio da consulta e já tinha linha mantém o tratamento que tinha;
- prefixo que veio da consulta e não tinha linha entra sem tratamento;
- prefixo que tinha linha e não veio volta no fim da lista, com a marca `!- nao veio na consulta ao IRR` no fim da linha, mantido por default.

O default de manter é o que o bloco próprio já decidiu, e o argumento é o mesmo: deixar de anunciar um prefixo vivo por causa do que o IRR diz é pior do que continuar anunciando um prefixo que saiu de lá, e o marcador fica visível antes de gravar.

O endpoint é o mesmo do grupo, e ali a mesclagem só muda a ordem e a marca, porque as linhas do grupo não têm tratamento. **Decisão.** É uma consequência aceita: hoje a consulta do grupo substitui a lista inteira, e o prefixo que sumiu do IRR desaparece do cadastro sem aviso no salvamento seguinte; com a mesclagem ele fica marcado e a decisão volta para o operador.

Na tela, o botão do IRR continua sendo o mesmo, e passa a mandar o que está nos campos. A mudança é de uma linha em `PeerTela.tsx` e outra em `GrupoTela.tsx`, mais dois campos no `IrrPedido`.

## Alterações no `PLANO.md`

1. **Import do cliente**, no exemplo completo: a cláusula por prefixo, de onde ela vem (o cadastro do peer), a ordem do mais específico primeiro e a posição depois da CL-PEER.
2. **Referência de sintaxe XPL**: a forma `{<endereco> <comprimento> le <teto>}` e a regra do `if/elseif` que faz o mais específico vencer, se ainda não estiverem lá.
3. **Tabela de peers e IDs**: uma nota de que o tratamento por prefixo é escrito pela operadora no cadastro, e que ele não muda o que o cliente pode anunciar.
4. **Tabela pública para clientes**: nada muda. A community é escrita no cadastro da operadora, e o cliente continua sem como endereçar peer da operadora por prefixo.

## Testes

- `test_render.py`: golden do cliente com duas linhas tratadas, uma delas contendo a outra, para fixar a ordem e o `if/elseif`; o mesmo caso num parceiro, para fixar a cadeia depois do carimbo de tipo; um caso v6; um peer sem tratamento com o bloco igual ao de hoje.
- `test_peers.py`: leitura dos dois formatos de item, a gravação em string quando não há tratamento, e a canonicalização do CIDR na leitura.
- `test_validate.py`: a tabela de recusa caso a caso, com o `1xx` aceito, o `2000` recusado, o prefixo repetido e o aviso do prefixo mais longo que o teto.
- `test_formulario.py`: a análise das linhas com o `!-` nas duas pontas, e o grupo recusando a linha com community.
- `test_api.py`: o `/api/irr` preservando o tratamento, marcando o ausente e mantendo por default; o grupo passando pela mesma mesclagem.
- Front: a ajuda na seção de prefixos e o botão do IRR devolvendo as linhas mescladas.

## O que confirmar no equipamento

1. Que `if ip route-destination in {45.163.212.0 22 le 24}` casa o prefixo da linha junto com os mais específicos, como a entrada equivalente de uma prefix-list nomeada, e que a forma sem `le` (`{45.163.212.0 22}`) casa só o prefixo exato. O desenho assume as duas.
2. Que a cláusula inline aceita `le` sem `ge`, como o `{0.0.0.0 0 ge 32 le 32}` do export já usa, e que ela vale no v6 com o mesmo `ip route-destination` que a macro escreve nas duas famílias hoje.
