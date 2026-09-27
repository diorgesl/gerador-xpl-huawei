# Pendências do front e do app

2026-09-27

## Problema

As três etapas do front em SPA estão entregues e mergeadas na `main`. Ficou uma
lista de pendências que as etapas anteriores registraram de propósito, cada uma
no seu lugar: três perguntas de produto que ninguém respondeu, seis minors
adiados do front, três registros de manutenção da re-revisão da etapa 2, quatro
do e2e, e quinze comentários que o corte deixou apontando para o que apagou.

Nada disso quebra o app. Junto, é o que falta para o assunto fechar, e duas das
pendências são de comportamento: uma validação que não confere o que diz
conferir, e um erro de tela que não tem saída.

## Decisões do brainstorming

| Pergunta | Decisão |
| --- | --- |
| Origem do peer fora da tabela do tipo | Aviso em âmbar, sem bloquear o salvar |
| ASN repetido entre peers | Mantido como está: o token é a identidade, e o porquê fica registrado |
| "Salvar e copiar" no Safari | Medir primeiro, com um caso novo no `copiar.spec` rodando nos dois navegadores |
| Beco sem saída da recusa por `id` no grupo | A tela rebusca o próximo id livre e mantém o que foi digitado |

### Por que a origem vira aviso e não erro

O cadastro real (`peers.yaml`) tem três peers de upstream com origem de
downstream: BRDIGITAL com 1120, ALT e VIAMS com 1100. A tabela do tipo é
`ORIGENS_POR_TIPO["upstream"] = (1400, 1000, 1900)`. Recusar fecharia o buraco e,
no mesmo gesto, tornaria esses três impossíveis de salvar até alguém trocar a
origem deles, o que muda a community que sai no bloco gerado. Isso é decisão de
rede, não de app. O aviso mostra a anomalia na cara do operador e deixa a decisão
com ele, que é o mesmo tratamento que o ASN privado e a community fora do
namespace já têm.

### Por que o ASN repetido fica como está

A identidade do peer é `apelido or str(asn)`, e o validador compara tokens. Dois
peers com o mesmo ASN e apelidos diferentes são legítimos: é como se modela o
mesmo cliente em dois POPs. Para criar uma duplicata é preciso dar um apelido
novo de propósito, e o token repetido já é recusado. A pergunta de produto que a
etapa 2 deixou aberta fecha aqui, sem linha de código.

## Escopo

### O que entra

- O aviso de origem fora da tabela, nos tipos de peer que hoje não têm
  conferência nenhuma.
- A saída do beco do `id` no grupo.
- Todos os avisos de um campo na tela, e não só o primeiro.
- O `camposDoErro` deixando de tratar chave desconhecida como campo.
- A aba ativa subindo para a tela, para o "copiar o bloco aberto" copiar a aba
  certa.
- `aria-pressed` no tema, um link por campo no resumo de erros, estado "tentando"
  no `Falha`, e o `_corpo` dos prefixos alinhado com peer e grupo.
- A invariante do `toast.dismiss()` documentada no harness.
- Os quatro pendentes do e2e (aspas nos caminhos, typecheck, globais de Node, e
  a cópia provando o bloco daquele peer).
- O caso de "salvar e copiar" nos dois navegadores.
- Os quinze comentários obsoletos.

### O que não entra

- **O custo da prévia.** A spec do front manda subir o intervalo de 400 ms antes
  de pensar em cache, e só se ficar lento. Nada mediu lentidão.
- **Mudança no `PLANO.md`.** A política do documento não muda; o aviso de origem
  é decisão de app.
- **A regra de ASN repetido.** Decidida acima, sem código.
- **Refatorar os casos que dependem do `toast.dismiss()`.** A linha está certa; o
  que falta é dizer o que ela isola.
- **Push.** É do operador.

## Comportamento

### O aviso de origem

Hoje o peer só tem uma conferência de origem, e ela vale apenas para os tipos
downstream: `validate.py:612-613` recusa quando a origem está fora da faixa 1xxx
(`ORIGENS_CLIENTE`). Em `upstream`, `ix` e `pni` não há conferência nenhuma. O
grupo é mais estrito: `validate.py:442-447` confere contra
`plan.ORIGENS_POR_TIPO[tipo]`. O próprio código registra a assimetria e diz que
alinha-la é mudança separada (`validate.py:438-441`). Esta é a mudança separada,
e ela vem como aviso, não como erro.

O aviso entra no `validate.avisos`, para os tipos em que hoje não há
conferência, comparando com `plan.ORIGENS_POR_TIPO[tipo]`. A mensagem fica em
ASCII, como as outras, e é a mesma família da que o grupo já usa: o grupo diz
"origem do %s tem que ser uma de %s", e o peer passa a dizer "origem %d nao esta
na tabela do %s: o plano usa %s", com a lista do tipo no fim. O campo é `origem`,
que é o que a tela usa para achar onde desenhar a linha. Nos tipos downstream
nada muda: o erro de faixa já cobre, e é a mesma lista de valores.

O `_origem_padrao` (`formulario.py:195-206`) já devolve um valor que está dentro
da tabela em todos os tipos, então o aviso não aparece em peer novo nem em
cópia. Ele aparece só em cadastro antigo com origem de outro tipo, que é
exatamente o caso que se quer mostrar.

### A saída do beco do `id` no grupo

A recusa nasce em `api.py:428-432`: um POST de grupo com id já tomado devolve 422
no campo `id`. O formulário do grupo não tem esse campo (`camposGrupo.ts` não
tem nenhum `nome: "id"`, ao contrário do `camposPeer.ts:43`), e a seção de
identificação do grupo não inclui `id` (`campos.ts:90`). Resultado de hoje: o
resumo mostra a mensagem com um link que não leva a lugar nenhum.

Duas mudanças, uma de raiz e uma de fluxo:

1. O `camposDoErro` deixa de tratar chave desconhecida como campo, então a
   mensagem aparece no resumo sem link, que é o certo.
2. Ao receber essa recusa, a tela pede `GET /api/grupos/novo` de novo, põe o id
   livre no formulário e mantém tudo o que o operador digitou. Salvar de novo
   funciona. O aviso diz que o id anterior foi tomado no meio do caminho.

### Todos os avisos de um campo

`Formulario.tsx:119` usa `avisos.find((a) => a.campo === campo.nome)`, então só o
primeiro aviso de cada campo aparece. A API pode devolver vários para o mesmo
campo: `validate.py:300-309` emite um por community fora do plano, e o `_avisos`
da API não deduplica por campo (`api.py:134-135`).

O `aviso` do `CampoRender` e do `Campo` passa a ser lista, e o campo desenha uma
linha por aviso. O `Campo.tsx` já desenha aviso e erro separados; o que muda é a
quantidade de linhas.

## Front

### `camposDoErro` e chave desconhecida

`campos.ts:122-131`: `SEM_CAMPO` lista as chaves que não são campo, e qualquer
outra chave volta como `[chave]`. É o que faz uma chave nova do backend fechar o
painel de saída (`PeerTela.tsx:150-152` pergunta só se há campo) sem desenhar
campo nenhum. Passa a devolver `[]` quando a chave não é campo do formulário
daquele tipo. Chaves que são campo continuam devolvendo o próprio nome, e as
compostas continuam se abrindo no mapa (`sessoes` nos quatro campos, `prefixos`
nas duas famílias, `te_prefixos` nas duas).

### A aba ativa

`PainelSaida.tsx:46` guarda a aba corrente em estado interno, e as telas publicam
`abas[0]` para a paleta (`PeerTela.tsx:304` e `:315`, `GrupoTela.tsx:262` e
`:270`, `PrefixosTela.tsx:165` e `:171-174`). Com duas abas, "copiar o bloco
aberto" na paleta copia a primeira em vez da que está na tela.

O painel ganha um `aoTrocarAba?: (id: string) => void` e continua dono do estado;
a tela espelha a aba corrente e publica a cópia dessa aba. O valor inicial da
tela é o mesmo que o painel escolhe (`abas[0]`), então não há divergência no
primeiro render.

### O tema

`ConfiguracoesTela.tsx:140-150` marca o tema escolhido só por `variant` e
`ring-1`, e `Paleta.tsx:112-120` só pelo texto " (atual)". Os dois botões ganham
`aria-pressed`, que é o que faz o estado ser lido por leitor de tela.

### O resumo de erros

`ResumoErros.tsx:24-26` pega `campos[0]` e desenha um botão por chave. Uma chave
que se abre em vários campos (um erro de `sessoes`, de `prefixos` ou de
`te_prefixos`) sempre leva ao primeiro. Passa a desenhar um item por campo do
mapa, cada um com o seu destino.

### O retry do `Falha`

`Falha.tsx` não tem estado nenhum: o botão chama `aoTentar` direto, e o refetch
do TanStack reinicia o pedido em voo, então o clique duplo dispara dois pedidos
(nos peer e grupo, quatro, porque cada um refaz duas consultas). O componente
ganha `tentando?: boolean` e desabilita o botão enquanto o valor for verdadeiro;
os cinco chamadores passam o `isFetching` do que eles refazem.

### O `_corpo` dos prefixos

`lerRecusa` (`consultas.ts:27-30`) devolve `_corpo: "resposta inesperada da API"`
quando o corpo não tem o formato da API. Peer e grupo suprimem esse texto quando
o status é de falha do servidor (`PeerTela.tsx:237-240`, `GrupoTela.tsx:196-199`
e `:244-247`), e as configurações apenas não o renderizam. A tela dos prefixos
mostra os dois avisos juntos (`PrefixosTela.tsx:76` e `:136-140`). Ela passa a
suprimir o `_corpo` no mesmo caso, como as outras duas.

### O harness de teste

`roteador.tsx:39-45` faz `toast.dismiss()` no `afterEach`, e é isso que isola os
casos: o estado dos toasts vive no módulo do sonner, e a limpeza do
testing-library desmonta a árvore sem zerá-lo. Sem a linha, os toasts do caso
anterior voltam a ser desenhados, e vários casos quebram por um motivo que não é
de quem mexeu: `PeerTela.test.tsx:529` acha três cópias do mesmo texto,
`:659` e `GrupoTela.test.tsx:342` encontram um toast que não é do caso deles.

A linha fica e ganha o comentário que nomeia esses casos. Não vale refatorar
dezessete casos para não depender de uma linha que está certa.

## e2e

| Item | O que muda |
| --- | --- |
| `playwright.config.ts:25` | Os caminhos do comando do `webServer` vão entre aspas: hoje um repositório com espaço no caminho quebra o `cd` |
| `web/tsconfig.e2e.json` (novo) | `playwright.config.ts` e `e2e/**` passam a ser typechecados; hoje não estão em nenhum `include` |
| `eslint.config.js` | Um bloco com `globals.node` para `e2e/**` e `playwright.config.ts`, que rodam em Node e hoje recebem `document`, `window` e `localStorage` como definidos |
| `copiar.spec.ts:16-23` | A asserção da área de transferência passa a exigir algo do peer 1 (token ou apelido do ACME); `end-filter` casa com qualquer bloco XPL, de qualquer peer |
| `copiar.spec.ts`, caso novo | "Salvar e copiar" nos dois navegadores, que é a medição do Safari. Se o WebKit recusar a escrita, o plano implementa o socorro que a spec do front desenha: salvar, trocar o botão para "copiar" já habilitado e pedir o segundo clique |

## Comentários

Os comentários que o corte deixou obsoletos, todos citando o que foi apagado: os
de `app/api.py`, que falavam das telas Jinja e das rotas que saíram, e os de
`app/formulario.py`, que citavam `_contexto`, `_contexto_grupo` e `POP_USADOS`,
que não existem mais, e as tags da tela. Cada um passa a descrever o que o código
faz hoje, e nenhum deles muda comportamento.

## Testes

- **O aviso de origem:** teste no `test_validate.py` (a tabela do tipo, os três
  tipos sem conferência, e o downstream sem aviso novo) e no `test_api.py` (o
  aviso chega no envelope de um POST de upstream com origem fora da tabela).
- **O id do grupo:** teste no `GrupoTela.test.tsx`, com o 422 no `id` e a
  resposta nova de `GET /api/grupos/novo`, provando que o digitado fica e que o
  segundo salvar sai com o id novo.
- **Os avisos por campo:** `FormularioPeer.test.tsx`, com dois avisos no mesmo
  campo.
- **O `camposDoErro`:** `campos.test.ts`, com uma chave que não é campo (fecha
  nada) e com as compostas de sempre.
- **A aba ativa:** `PainelSaida.test.tsx` (o callback) e o caso de copiar em
  `PeerTela.test.tsx` ou `PrefixosTela.test.tsx`, provando que a cópia é da aba
  corrente.
- **Os demais minors do front:** no arquivo de teste de cada componente, com o
  caso que falha antes.
- **O e2e:** os quatro pendentes, mais o caso novo nos dois navegadores.

## Etapas

Uma spec, um plano. A implementação roda na própria worktree, e o merge no
checkout principal fica com o operador, como nas etapas anteriores.

## Riscos e pontos em aberto

- **O WebKit pode recusar o "salvar e copiar".** É o risco que a spec do front
  registrou e que esta leva mede. Se recusar, o socorro de dois cliques entra no
  mesmo plano, e o Chrome passa a pagar um clique a mais.
- **A aba ativa é o item de maior superfície.** Mexe no `PainelSaida`, nas três
  telas e nos testes do painel. O resto é local.
- **Os avisos por campo mexem no `Formulario` e no `Campo`,** que as duas telas
  de formulário usam. Um erro de tipo aqui aparece nas duas.
- **O aviso de origem é a única mudança visível no cadastro real:** abrir
  BRDIGITAL, ALT ou VIAMS passa a mostrar um aviso em âmbar que não existia.
  Nenhum bloco gerado muda por causa dele.
- **Os três peers do cadastro seguem com origem fora da tabela** depois desta
  leva. O aviso não é conserto, é visibilidade.
