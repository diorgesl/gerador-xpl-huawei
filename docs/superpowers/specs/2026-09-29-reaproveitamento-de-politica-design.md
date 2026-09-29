# Reaproveitamento de política entre peers — AS64512

2026-09-29

## Problema

O mesmo cliente com dois links, um principal e um backup, não tem hoje uma saída que sirva. As duas que existem:

- **Dois peers avulsos.** Cada um gera o par de filtros inteiro, com o token no nome de tudo. Dois links de cliente saem com 12 objetos, sendo 6 duplicados: `AP-CUST-<T>`, dois `PL-CUST-<T>`, `APPLY-PEER-<T>` e os dois `CUST-<T>-IMPORT/EXPORT-<U>`. A política é a mesma, escrita duas vezes, e diverge na primeira edição feita num só.
- **Um grupo.** Resolve o reaproveitamento (os membros não geram objeto nenhum), mas cria um `peer group <nome>` no equipamento e obriga os membros a compartilharem a configuração de sessão, porque é o grupo do VRP que a carrega.

Falta a opção do meio: o segundo link usar a política do primeiro, sem grupo e sem objeto novo.

Este documento estende o design do gerador (`2026-09-21-gerador-sessoes-bgp-design.md`) e o de grupos (`2026-09-22-grupos-de-peers-design.md`), mantendo o requisito duro de sempre: gerar ou editar um peer não pode mexer na saída de outro.

## Escopo

### O que entra

- Um campo opcional no cadastro do peer que aponta para outro peer do mesmo tipo e do mesmo ASN.
- O peer que reaproveita emite só a sessão, e chama os filtros do peer de origem pelo nome dele.
- Os cinco tipos.
- As regras que recusam combinações sem sentido, e a guarda que impede apagar um peer que está sendo reaproveitado.
- No formulário, o campo de escolha e a nota que diz de quem vem a política.

### O que não entra

- **Reaproveitar de um grupo.** É o que o grupo já faz, por outro caminho.
- **Corrente.** A origem tem que ser dona da própria política, então um peer que reaproveita não pode ser origem de ninguém.
- **Tipos ou ASNs diferentes.** A política carrega o ASN no texto (`AP-CUST-<T>`, as large `c_large(f, <asn>)`, a `CL-PEER`), e os filtros são por tipo.
- **LP próprio por link.** Os dois links ficam com a mesma preferência, e a diferença entre principal e backup vem do que o cliente anuncia em cada um. Separar o LP do filtro é uma mudança maior, e ficou fora desta.
- **Regerar sozinho o bloco de quem reaproveita** quando o token da origem muda. O app avisa, e a reaplicação é decisão do operador.

## Modelo de dados

`Peer.politica_de: int | None`, o `id` do peer de origem.

Por `id` e não por token porque o token muda quando o apelido muda, e a referência não pode se desfazer por causa de uma renomeação. O efeito colateral é que renomear a origem deixa o bloco de quem reaproveita desatualizado, e isso está tratado em "O token da origem muda", abaixo.

Um peer com `politica_de` setado:

| Campo | De quem é |
| --- | --- |
| `politica_de`, `apelido`, `nome`, `descricao`, `sessoes`, `route_limit`, `timer_*`, `bfd`, `graceful_restart` | do peer que reaproveita |
| `prefixos`, `te_prefixos`, `communities`, `large_communities`, `ap_*`, `prepend_base`, `bh_upstream`, `classe`, `lp_base`, `origem`, `pop`, `aprendizado`, `ix_id`, `default_route` | da origem |

Os campos da segunda linha continuam existindo no registro, com o valor que tiverem, e o render para de consultá-los. Eles ficam onde estão e aparecem no formulário como sempre: o que muda é de quem o gerador lê, e não o que a tela mostra.

A diferença para o membro de grupo, que hoje tem esses campos escondidos, é deliberada: ali o formulário esconde porque o valor não é do registro, e aqui o valor é do registro e a tela o mostra, com uma nota dizendo que quem manda na geração é a origem.

## Geração

O bloco de quem reaproveita não define objeto nenhum. Só a sessão, com os filtros da origem:

```scss
bgp 64512
 peer 198.51.100.10 description NETMAC-BKP
 peer 198.51.100.10 as-number 270620
 peer 198.51.100.10 route-limit 50 alert-only
 ipv4-family unicast
  peer 198.51.100.10 enable
  peer 198.51.100.10 route-filter CUST-NETMAC-IMPORT-V4 import
  peer 198.51.100.10 route-filter CUST-NETMAC-EXPORT-V4 export
```

A parte de sessão é a do peer avulso de sempre (`sessao_do_peer` e `familia_bgp`), porque aqui não há grupo do VRP carregando nada: `AS_ONLY`, timers, `bfd`, graceful-restart e `advertise-community` saem no bloco de quem reaproveita, com os valores dele.

Os dois filtros que ele referencia, por tipo:

| Tipo | Import | Export |
| --- | --- | --- |
| `cliente`, `parceiro` | `CUST-<T>-IMPORT-<U>` | `CUST-<T>-EXPORT-<U>` |
| `upstream` | `UP-<T>-IMPORT-<U>` | `UP-<T>-EXPORT-<U>` |
| `ix` | `IX-<T>-IMPORT-<U>` | `IX-<T>-EXPORT-<U>` |
| `pni` | `PNI-<T>-IMPORT-<U>` | `PNI-<T>-EXPORT-<U>` |

`<T>` é o token do peer de **origem** e `<U>` é `V4` ou `V6`.

O `APPLY-PEER-<T>` da origem continua sendo chamado pelo export dela, que é o filtro que o segundo link usa. Quem reaproveita não define nem chama esse par.

### Remoção

O bloco de remoção de quem reaproveita derruba só a sessão dele: nenhuma linha `undo xpl`. Derrubar os objetos da origem apagaria a política dos dois links.

## O formulário

Um `select` "Reaproveitar a política de", com os peers do mesmo tipo e do mesmo ASN que são donos da própria política. Trocar o tipo ou o ASN limpa a seleção, como os outros selects encadeados do formulário já fazem.

**Nenhum campo some.** Com a origem escolhida, o formulário continua mostrando tudo, e os campos de política ficam como estão: o que o registro guarda é o que a tela mostra, e o render é quem ignora. Esconder campo tem dois custos que não valem aqui: o operador perde de vista o que está cadastrado, e a regra de visibilidade do formulário teria que aprender mais um caso, num lugar que já decide visibilidade por tipo.

O que entra no lugar do esconderijo é uma nota na seção de política, dizendo de qual peer ela vem e que editar ali não muda o que é gerado. Sem ela, um LP digitado nessa tela pareceria valer.

O quadro "ao criar o peer" continua fora para quem reaproveita: o par `CL-PEER`/`APPLY-PEER` é da origem, e criá-lo aqui daria dois objetos para o mesmo papel.

## O token da origem muda

Trocar o apelido da origem troca o token dela, e com ele o nome de todos os objetos que quem reaproveita chama. O bloco de quem reaproveita fica apontando para nomes que não existem mais no equipamento, até ser gerado de novo.

O app avisa no formulário da origem, listando quantos peers a reaproveitam, e não tenta regenerar o bloco de outro peer sozinho: isso quebraria o requisito de que gerar um não mexe na saída do outro.

## Validação — regras novas

| Regra | Por quê |
| --- | --- |
| A origem existe | Referência a registro que não está lá |
| A origem é do mesmo `tipo` | Os filtros e a política são por tipo |
| A origem é do mesmo `asn` | O ASN entra no texto da política: `AP-CUST-<T>`, as large por ASN, a `CL-PEER` |
| A origem é dona da própria política | Ela não pode ter `politica_de` (corrente) nem estar em grupo (o bloco dela não tem os filtros, eles são do grupo) |
| O peer não pode ser a própria origem | Óbvio, mas é uma linha e evita um caso de render sem saída |
| O peer não pode ter `politica_de` e grupo ao mesmo tempo | São dois mecanismos para a mesma herança, e o grupo já ganha |
| Excluir a origem com alguém apontando para ela é recusado | Mesmo espírito da exclusão de grupo com membros: não pode ser silencioso |

## Testes — extensão de `tests/`

- `test_validate.py`: cada regra da tabela acima, um caso por linha.
- `test_render.py`: por tipo, o bloco de quem reaproveita não tem objeto `xpl` nenhum, referencia os filtros da origem pelo token dela, e traz a sessão completa (timers, `bfd`, `route-limit`). Golden de um caso cliente.
- Remoção: o bloco de remoção de quem reaproveita não tem `undo xpl`.
- `test_api_peers.py`: criar o segundo link pela API reaproveitando o primeiro, e a exclusão da origem recusada enquanto ele existe.
- Front: o campo aparece, a lista só traz peer do mesmo tipo e ASN, e escolher a origem deixa a nota dizendo de quem vem a política. O caso que prova que a tela **não** esconde campo nenhum é tão importante quanto: é a decisão que separa este recurso do que o grupo faz.

A propriedade que o design do gerador já pede vale aqui também: gerar ou editar quem reaproveita não muda a saída da origem, e gerar ou editar a origem não muda a saída de quem reaproveita.

## Decisões

| Decisão | Escolha | Motivo |
| --- | --- | --- |
| O que quem reaproveita guarda de próprio | Só a sessão | É o que "reaproveitar a política" quer dizer; qualquer coisa além disso exigiria separar pedaços do filtro |
| Referência por `id` ou por token | `id` | O token muda com o apelido, e a referência não pode se desfazer por renomeação |
| Corrente de reaproveitamento | Não | A origem tem que ser dona da política; sem isso o nome dos objetos vira uma cadeia para resolver |
| Peer com grupo pode reaproveitar | Não | O grupo já é a herança, e os filtros dele não estão no bloco do membro |
| LP por link | Fica igual | Separar o LP do filtro compartilhado é uma mudança maior, fora do escopo |
| Custo no equipamento | Nenhum objeto novo | É a diferença para o grupo, que cria o `peer group` |
| Campo de política no formulário de quem reaproveita | Fica visível, com nota | O operador não perde de vista o que está cadastrado, e a visibilidade do formulário não ganha mais um caso |
| Aviso do token da origem | No formulário da origem | É onde a renomeação acontece; se não couber ali, vira aviso no salvar da origem |
| `route-limit` diferente entre origem e quem reaproveita | Sem checagem e sem aviso | É campo de sessão, e dois links do mesmo cliente podem legitimamente ter limites diferentes |

## Pendências

Nenhuma. As três questões abertas na revisão foram fechadas acima.
