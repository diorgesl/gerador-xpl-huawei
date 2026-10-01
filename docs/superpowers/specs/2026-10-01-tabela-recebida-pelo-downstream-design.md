# Tabela recebida pelo downstream, AS64512

2026-10-01

## Problema

O egress de cliente não restringe o que sai. O `CUST-<T>-EXPORT-<U>` (`filtro_downstream_export`, `templates/_macros.j2:288`) recusa restrição RFC 1997, pedido de blackhole, no-advertise, só-não-cliente e os controles por ASN, e termina em `finish`. Todo cliente e todo parceiro recebem a full table. O PLANO registra a lacuna em `PLANO.md:96`: "Se algum contrato não prevê full table, falta o ramo correspondente no filtro daquela sessão."

A única opção hoje é o `default_route`, que acrescenta `peer <ip> default-route-advertise` na sessão. A default vai somada à full table, nunca no lugar dela.

O operador quer escolher, por downstream, o que a sessão recebe: só a default, uma tabela parcial (rotas próprias e de clientes), a parcial com as rotas aprendidas no IX, ou a full table. Peer novo nasce recebendo só a default.

## Fato de equipamento

O `peer <ip> default-route-advertise` do VRP não passa pelo route-filter de export da sessão, e origina `0.0.0.0/0` e `::/0` mesmo quando não há default na RIB nem na FIB. Quem confirmou foi o operador, no equipamento. Duas consequências:

- O filtro de export não precisa de ramo que libere a default. No modo sem tabela ele pode recusar tudo, e a default sai assim mesmo.
- O aviso que o cabeçalho do bloco imprime hoje ("confirme que ha um default na tabela", `_macros.j2:8` e `_macros.j2:222`) está errado e muda.

## Modelo

Dois campos independentes em `Peer` e `Grupo`:

| Campo | Valores | Peer ou grupo novo | Ausente no YAML |
| --- | --- | --- | --- |
| `default_route` | `bool` | `true` | `false` (como hoje) |
| `tabela` | `nenhuma`, `parcial`, `parcial_ix`, `full` | `nenhuma` | `full` |

- Os valores ficam numa constante `plan.TABELAS`, na ordem acima.
- O campo ausente no YAML é lido como `full` para que o cadastro existente gere o mesmo bloco de hoje. Os dois parceiros do `peers/264130.yaml` continuam como estão: um recebe full + default e o outro só full. O padrão "só default" vale para cadastro novo e entra por três lugares: o `GET /api/peers/novo` e o `/api/grupos/novo` (`peer_em_branco` e `grupo_em_branco`), o formulário em branco do front e a cascata da troca de tipo.
- O contrato do POST não muda para o `default_route`: o campo ausente no corpo continua `false`. Se ele passasse a `true`, um POST de upstream sem o campo seria recusado pelo `validate`, que barra default route fora de downstream. A `tabela` ausente ou em branco num downstream vira `nenhuma`.
- Os dois campos combinam livremente. Parcial + default é o pacote comum para cliente multihomed.
- `tabela` entra em `CAMPOS_POR_TIPO` e em `CAMPOS_POR_TIPO_GRUPO` (`app/formulario.py:658`) só para `cliente` e `parceiro`, ao lado do `default_route`.
- Membro de grupo herda a tabela do grupo. O export do membro (`export_por_asn_do_membro`, `_macros.j2:253`) já termina em `call route-filter CUST-<grupo>-EXPORT-<U>`, então o portão do grupo vale para ele sem nada novo. O render ignora o valor gravado no membro. O `default_route` continua sendo por membro, como hoje.
- Quem reaproveita a política de outro peer (`politica_de`) chama o export da origem, então recebe a tabela da origem. A tela já avisa que editar os campos de quem reaproveita não muda o que é gerado.
- `tabela` não entra em `tem_filtro_proprio`, porque o membro não sobrescreve a tabela.

## XPL

### Lista nova no bloco base

```
xpl community-list CL-ORIGEM-PARCIAL-IX
 <CL-ORIGEM-ANUNCIAVEL>,
 64512:1300
end-list
```

Sai de uma função `_origem_parcial_ix(ns)` em `plan.py`, ao lado de `_origem_anunciavel` (`app/plan.py:209`), que acrescenta `c(ORIGEM["ix"], ns)` ao conjunto anunciável. Ela respeita o namespace da rede como as outras (`Plan.__init__`, `app/plan.py:784`). O `64512:1300` é a marca que o `filtro_ix_import` já carimba (`_macros.j2:625`). PNI (`1500`) e upstream (`1400`) ficam de fora.

Uma lista só, em vez de `not ... and not ...` com duas listas, evita a precedência de `and`/`or` que a referência de sintaxe do PLANO documenta como armadilha.

### Portão em `filtro_downstream_export`

Os vetos atuais ficam onde estão. Depois deles, e antes do ramo de prepend por ASN, entra o portão do modo de `alvo.tabela`:

| Modo | O que entra |
| --- | --- |
| `full` | nada; o filtro sai idêntico ao de hoje |
| `parcial` | `if not community matches-any CL-ORIGEM-ANUNCIAVEL then` / `refuse` / `endif` |
| `parcial_ix` | o mesmo, contra `CL-ORIGEM-PARCIAL-IX` |
| `nenhuma` | o corpo do filtro é só `refuse` |

O `if not community matches-any` já é usado no `EXPORT-SANITY` (`templates/base.txt.j2:221`).

No modo `nenhuma`, os vetos e os prepends saem do filtro: não há rota para vetar nem para prependar. O filtro continua existindo, porque a sessão o referencia.

### Cabeçalho

`cabecalho` e `cabecalho_grupo` passam a imprimir, só em cliente e parceiro:

```
# tabela recebida: <modo>
# default route: o VRP origina 0/0 e ::/0 nesta sessao mesmo sem default na tabela
```

A segunda linha só sai com `default_route`. O `cabecalho` do peer passa a receber o grupo e a origem do reaproveitamento, e a primeira linha mostra a tabela que vale de fato: a do grupo no membro (`# tabela recebida: parcial (a do grupo CLIENTES)`) e a da origem em quem reaproveita. Os comentários ficam em ASCII, como pede o pipeline de TFTP.

## Validação

- `tabela` fora de `plan.TABELAS` é erro, em `validar` e em `validar_grupo`.
- Em upstream, IX e PNI o campo é ignorado. Ele só é lido em `filtro_downstream_export`, que esses tipos não usam, e a tela não o mostra para eles.
- Peer cliente ou parceiro avulso (sem grupo e sem `politica_de`) com `default_route=false` e `tabela=nenhuma` gera aviso em `avisos()` (`app/validate.py:48`): a sessão não recebe rota nenhuma. Não é erro, porque é legítimo para quem só anuncia. O grupo não tem `avisos()` hoje e esta spec não cria um.

## API e front

- `modelos_api.py`: `tabela: str = ""` em `PeerForm` e `GrupoForm`; o `default_route` do modelo continua `False`. `Plano` ganha `tabelas: list[str]` (o `plan.TABELAS`), para a tela montar o select sem repetir os valores. `TabelaTipo` ganha `default_route: bool` e `tabela: str`, que a cascata lê. `GrupoResumo` ganha `tabela: str`.
- `api.py`: `modelo_do_peer` e `modelo_do_grupo` devolvem a `tabela` só em downstream e, no peer, só fora de grupo; nos outros casos devolvem `""`, para o campo não aparecer na tela por ter valor guardado. `listar_grupos` devolve a `tabela` no resumo.
- `formulario.py` lê `tabela` nos dois caminhos (linhas 422 e 521), só em downstream, com o branco virando `nenhuma`. Em upstream, IX e PNI o campo fica no default do dataclass. `peer_em_branco` e `grupo_em_branco` nascem com `default_route=True` e `tabela="nenhuma"` em downstream. `_padroes()` ganha, por tipo, `default_route` (verdadeiro em downstream) e `tabela` (`nenhuma` em downstream, `""` nos outros).
- `camposPeer.ts` e `camposGrupo.ts`: select "Tabela recebida" com as opções de `plano.tabelas`, ao lado da caixa "Anuncia default route". `CAMPO_BRANCO` e `CAMPO_BRANCO_GRUPO` passam a `default_route: true` e `tabela: "nenhuma"`.
- `campos.ts`: `tabela` restrito a cliente e parceiro, na mesma seção do `default_route`. `CASCATA_PEER` e `CASCATA_GRUPO` ganham `default_route` e `tabela`, e a `cascata` passa a escrever booleano como booleano (hoje ela converte tudo em texto).
- Membro de grupo: a tela não tem hoje mecanismo para esconder campo herdado. O `FormularioPeer` tira a `tabela` do mapa de campos por tipo quando há `grupo_id`, e limpa o valor ao entrar num grupo (ou volta a `nenhuma` ao sair). A `PeerTela`, que já acha o grupo do membro (`web/src/telas/peers/PeerTela.tsx:353`), mostra a tabela herdada ao lado do nome do grupo.
- `npm run api:tipos` regenera `web/src/api/schema.d.ts`, e o `api:conferir` cobra.

Rótulos dos modos na tela:

| Valor | Rótulo |
| --- | --- |
| `nenhuma` | Nenhuma (só a default, se marcada) |
| `parcial` | Parcial: rotas próprias e de clientes |
| `parcial_ix` | Parcial + IX |
| `full` | Full table |

## Documento e PDF do cliente

- `PLANO.md:96`: o parágrafo deixa de dizer que falta o ramo e passa a descrever os quatro modos e o portão, apontando as duas listas.
- O exemplo "cliente de trânsito" (seção Export, `PLANO.md:1200`) ganha uma nota: o exemplo é o modo `full`, e os outros acrescentam o portão depois dos vetos.
- O comportamento do `default-route-advertise` fica registrado como confirmado no equipamento pelo operador, sem a marca de "a confirmar com `xpl simulate`".
- Tabela pública para clientes (`PLANO.md:1978`) e PDF (`app/politica.py`): uma seção curta, "O que você recebe de nós", com a default, a parcial, a parcial + IX e a full, e a default combinável com qualquer uma. A seção não cita community nem lista XPL, só o que o cliente recebe.

## Testes

- Goldens novos em `tests/golden/`: cliente com `nenhuma`, `parcial` e `parcial_ix`, e um grupo de cliente com `parcial`.
- Nas goldens de downstream existentes (modo `full`) só muda o cabeçalho, que ganha a linha `# tabela recebida: full`. Os filtros saem idênticos, e isso é o teste de compatibilidade do render. O `_base.txt` muda, porque ganha a `CL-ORIGEM-PARCIAL-IX`.
- `test_peers.py`: `tabela` atravessa o YAML, e ausente vira `full`, no peer e no grupo.
- `test_plan.py`: a lista parcial + IX contém a anunciável e o `1300` do namespace da rede.
- `test_validate.py`: valor inválido é erro no peer e no grupo; `default_route=false` com `nenhuma` gera aviso.
- `test_api_peers.py` e `test_api_grupos.py`: o `GET .../novo` de cliente e de parceiro vem com `default_route=true` e `tabela=nenhuma`, e o de upstream com `default_route=false` e `tabela=""`; POST de cliente sem a `tabela` grava `nenhuma`.
- `test_formulario.py`: a conferência do `CAMPOS_POR_TIPO` passa com o campo novo.
- `test_politica.py` e `test_pdf.py`: a seção nova sai no documento.
- vitest: o select aparece em cliente e parceiro, não aparece em upstream, IX e PNI, vira a linha de herança no membro de grupo, e o novo cadastro vem com os padrões.

## Fora do escopo

- Tabela por membro de grupo, diferente da do grupo.
- PNI e upstream na parcial. Se precisar, vira outro valor de `tabela` com outra lista.
- As classes `2010` a `2090`. O portão usa a marca de origem que o import já escreve, e elas continuam reservadas.
- Migrar o cadastro existente para "só default". Quem quiser muda pela tela, peer a peer.
- Default condicional (`default-route-advertise` com route-policy ou `conditional-route-match-all`).
