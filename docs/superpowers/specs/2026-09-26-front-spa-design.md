# Front em SPA para o bgpgen

2026-09-26

## Problema

A tela do bgpgen funciona, mas o operador acha o uso arcaico. No brainstorming ele apontou três dores: a navegação, o visual datado e a leitura da saída XPL.

O que se vê hoje, em `templates/pagina.html` e `templates/pagina_grupo.html`:

- A lista de peers é uma tabela pequena, sem busca, e peer e grupo não têm navegação comum. O grupo abre numa tela separada com um "← peers" no topo.
- O cabeçalho mistura a configuração do AS da rede, que quase nunca muda, com as ações do dia a dia.
- A seção de prefixos próprios aparece no rodapé de toda página, sem relação com o peer aberto.
- O formulário do peer mostra os cerca de 40 campos para qualquer tipo, e o operador lê as tags ("IX e PNI", "só no tipo upstream") para saber o que ignorar. A tela de grupo já esconde por tipo, a do peer não.
- O bloco gerado só aparece depois de salvar, num `<pre>` sem destaque e cortado nas linhas longas.
- Toda ação recarrega a página inteira.

A folha `_estilo.html` já tem tokens e tema escuro. O problema é estrutural, e o operador escolheu trocar o front inteiro por uma SPA.

Além das dores, o operador pediu um recurso novo: duplicar um peer e abrir o formulário de um peer novo preenchido com a cópia.

## Decisões do brainstorming

| Pergunta | Decisão |
| --- | --- |
| Stack | SPA com React, Vite, TypeScript, Tailwind e shadcn/ui. O FastAPI passa a servir uma API JSON. |
| O que a cópia leva | Tudo. Só o ID vem trocado pelo próximo livre, e o salvar recusa o que repetir. |
| Destino das telas Jinja | Saem no corte, depois que o comportamento que os testes delas protegem estiver coberto por teste de API ou de front. |
| Saída XPL durante a edição | Prévia ao vivo, com diff contra o arquivo salvo em `out/`. |
| Identificador na URL | O ID do `peers.yaml`, e não o token. O token muda quando o ASN ou o apelido mudam. |
| Campos de outro tipo | Ficam escondidos, com as exceções da seção "Campos por tipo". |
| Copiar com alteração não salva | O botão vira "salvar e copiar". |
| Cores | Suaves: pouca saturação, sem branco nem preto puros, texto com contraste AA. |

## Escopo

### O que entra

- API JSON em `/api`, ao lado das rotas HTML atuais, reaproveitando parsing, validação e render que já existem.
- SPA em `web/` cobrindo tudo o que as duas telas fazem hoje: peers, grupos, prefixos próprios, AS da rede, bloco base, consulta ao IRR, exclusão.
- Barra lateral com busca, paleta de comandos (Ctrl+K), URLs por tela.
- Prévia ao vivo da saída, com destaque de sintaxe XPL, diff contra `out/` e "salvar e copiar".
- Duplicar peer e duplicar grupo.
- Tema claro, escuro e do sistema.
- Build do front no Docker.
- Corte: `/` passa a abrir a SPA, e as telas e testes de HTML saem.
- README e `CLAUDE.md` atualizados.

### O que não entra

- Mudança em `plan.py`, `validate.py`, `render.py`, `peers.py`, `prefixes.py` ou em qualquer template `.j2` de XPL. A saída gerada não muda um byte, e os golden continuam valendo.
- Autenticação, usuários, edição simultânea. Duas abas salvando o mesmo registro seguem a regra de hoje: vence quem salva por último.
- Formulário otimizado para celular. No celular dá para consultar e copiar.
- Renderização no servidor (SSR, Next.js).
- Tradução da tela. A tela é em português.
- Mudança nas mensagens de erro do `validate.py`. Elas continuam em ASCII, como estão.

## Arquitetura

### Pastas

```
app/
  app.py          rotas HTML (até o corte), montagem da API e do front
  formulario.py   helpers de formulário tirados do app.py (ver etapa 1)
  api.py          rotas /api
  modelos_api.py  modelos Pydantic de entrada e saída
web/
  package.json, package-lock.json, vite.config.ts, tsconfig.json
  index.html
  src/
    api/          schema.d.ts gerado, cliente openapi-fetch, hooks do TanStack Query
    app/          roteador, casca (layout), providers (query, tema, toasts)
    components/ui shadcn/ui
    components/   BarraLateral, Paleta, PainelSaida, CodigoXpl, Diff,
                  CampoCombo, ResumoErros, AvisoNaoSalvo
    telas/        peers/, grupos/, prefixos/, base/, configuracoes/
    lib/          xpl.ts (tokenizador), diff.ts, copiar.ts, campos.ts
    estilo/       tokens.css
  e2e/            Playwright
```

O `app.py` hoje carrega os helpers de formulário (`peer_do_formulario`, `grupo_do_formulario`, `_padroes`, `_blocos_do_formulario`, `_asn_do_formulario`, `_conferir_faixas`, `_texto_blocos`, `_usados`, `_origem_padrao`, `_aprendizado_padrao` e os que eles chamam). A API precisa deles e o `app.py` precisa montar a API, então importar de um para o outro dá ciclo. A etapa 1 move esses helpers para `app/formulario.py` sem mudar o corpo, e o `app.py` os reexporta enquanto as rotas HTML existirem, porque os testes acessam alguns por `app.app`.

### Stack do front

React 19, Vite, TypeScript em modo estrito, Tailwind v4, shadcn/ui (Radix por baixo), React Router, TanStack Query, React Hook Form, `lucide-react`, `cmdk` (a paleta do shadcn), `sonner` (toasts do shadcn), `diff` e `@fontsource-variable/inter` e `@fontsource-variable/jetbrains-mono`. As versões são as estáveis correntes quando a etapa 2 começar, travadas no `package-lock.json`. O gerenciador é o npm.

Os tipos da API saem do próprio FastAPI. Um script (`npm run api:tipos`) roda `python -c` para imprimir o `app.openapi()` e passa o resultado pelo `openapi-typescript`, gerando `web/src/api/schema.d.ts`. O arquivo gerado é versionado, e assim o build do front não precisa de Python. Um segundo script (`npm run api:conferir`) gera de novo num arquivo temporário e falha se houver diferença. Ele roda junto com os testes.

### Produção e desenvolvimento

Em produção um processo só: o uvicorn. O FastAPI serve a API em `/api`, os arquivos do build em `/assets` e o `index.html` do build nas rotas da SPA: `/peers`, `/peers/*`, `/grupos`, `/grupos/*`, `/prefixos`, `/base` e `/configuracoes`. O `/base.txt` continua onde está.

Até o corte, as rotas HTML continuam no `/`, `/peer/...`, `/grupo/...`, `/saida/...`, `/asn`, `/bgpq4` e `/blocos`. Os nomes da SPA estão no plural e não colidem com nenhuma delas. No corte, `/` passa a redirecionar para `/peers`.

O diretório do build vem da variável `BGPGEN_WEB`, e o padrão é `web/dist` relativo à raiz do projeto. Sem build nesse diretório, as rotas da SPA respondem 503 com um texto curto: "front não compilado: rode `npm run build` em `web/` ou use o Vite na 5173". A API funciona sem o build, e os testes de API não dependem dele.

No desenvolvimento rodam dois processos: o uvicorn na 8000 e o `npm run dev` do Vite na 5173, com proxy de `/api` e `/base.txt` para a 8000. O README descreve os dois.

### Docker

O `Dockerfile` ganha um primeiro estágio `node:22-slim` que roda `npm ci` e `npm run build` em `web/`. O estágio final copia o `dist` para `/srv/web` e define `BGPGEN_WEB=/srv/web`.

O caminho fica fora de `/app` de propósito. O `compose.yaml` monta o checkout inteiro em `/app`, e qualquer coisa que a imagem pusesse ali ficaria escondida pelo bind mount. A consequência é que editar o front no host não muda o que o container serve até o próximo `docker compose up --build`. Para mexer no front, o caminho é o Vite.

O `.dockerignore` e o `.gitignore` ganham `web/node_modules` e `web/dist`.

## API

### Formato

Tudo é JSON. Erro de validação volta com status 422 e sempre no mesmo formato. A exceção é a prévia, que devolve 200 com o mesmo `erros` (ver "A prévia").

```json
{
  "erros": {"asn": "ASN ja usado pelo peer BRDIGITAL-20G"},
  "avisos": [{"campo": "route_limit", "mensagem": "..."}]
}
```

O `erros` sai do `validate.erros_para_dict`, que já existe e já deixa o primeiro erro de cada campo vencer. As chaves são os nomes de campo que o `validate.py` usa hoje, inclusive os compostos (`sessoes.v4.local`, `prefixos`, `te_prefixos`, `bgpq4`, `membros`). O FastAPI tem o próprio formato de 422 para corpo malformado. Um handler de `RequestValidationError` converte esse caso para o formato acima, com a chave `_corpo`.

Outros status: 404 com `{"erros": {"_": "peer nao encontrado"}}` quando o ID não existe, 409 no grupo com membros, 502 quando o bgpq4 falha.

### O modelo do formulário

A API recebe e devolve peer e grupo no formato achatado do formulário de hoje, com os mesmos nomes de campo. O front trabalha com um formato só, e a API não inventa um segundo.

- Campos escalares, inclusive os numéricos, são texto. É o que o operador digitou, e o `peer_do_formulario` é quem converte e devolve "valor numerico invalido". Tipar como `int` no Pydantic trocaria essa mensagem pela do Pydantic, noutro formato.
- Campos de lista (`prefixos_v4`, `prefixos_v6`, `te_prefixos_v4`, `te_prefixos_v6`, `ap_block`, `ap_te`, `ap_allowed`, `ap_prefer`, `communities`, `large_communities`) são listas de texto, uma entrada por linha.
- Caixas (`bfd`, `graceful_restart`, `default_route`) são booleanas.
- Sessões são quatro campos planos: `sessao_v4_local`, `sessao_v4_remoto`, `sessao_v6_local`, `sessao_v6_remoto`.
- O grupo tem o próprio modelo, com o `aprendizado_ix` que a tela do grupo já usa.

Um adaptador em `app/api.py` converte o modelo para o dicionário de texto que `peer_do_formulario` e `grupo_do_formulario` esperam: texto passa como está, lista vira linhas juntadas por `\n`, caixa marcada vira `"on"` e desmarcada fica fora do dicionário, e o `id_original` sai do `{id}` da URL no `PUT`. O caminho inverso, de `Peer` e `Grupo` para o modelo, fica no mesmo arquivo. Um teste confere a volta completa: carregar um peer, converter para o modelo, converter de volta e obter um `Peer` igual.

### Rotas

| Rota | O que faz |
| --- | --- |
| `GET /api/plano` | Rede atual (AS e namespace) e as tabelas que o formulário usa: o `_padroes()` de hoje mais tipos, LP, route-limit e exemplos, classes, origem por classe, nomes de origem, origens por tipo, prepend máximo e implementado, faixas de POP e de aprendizado, POP e aprendizado já cadastrados, tipos com "ao criar o peer" e a tabela de campos por tipo. |
| `PUT /api/rede` | Corpo `{"asn": "...", "politica": "..."}` em texto. Mesmas conferências do `POST /asn` (`_asn_do_formulario`), mesmos erros nos campos `asn_rede` e `asn_politica`. |
| `GET /api/peers` | Lista resumida: id, token, tipo, ASN, apelido, nome, grupo_id. |
| `GET /api/peers/novo?tipo=` | Peer em branco com os defaults do tipo e o próximo ID livre, como o `GET /peer/novo`. |
| `GET /api/peers/{id}` | O peer no modelo do formulário. |
| `GET /api/peers/{id}/copia` | O mesmo peer com o ID trocado por `proximo_id`. Não grava nada. |
| `POST /api/peers` | Cria. Mesmo caminho do `POST /peer` sem `id_original`. Devolve o peer gravado e o nome do arquivo escrito em `out/`. |
| `PUT /api/peers/{id}` | Atualiza. Mesmo caminho do `POST /peer` com `id_original`, inclusive apagar o arquivo antigo de `out/` quando token ou tipo mudam. |
| `DELETE /api/peers/{id}` | Exclui o peer e o arquivo em `out/`. A confirmação é um diálogo na tela, e a API não pede o `confirmado`. |
| `POST /api/peers/previa?id=` | Ver "A prévia". |
| `GET /api/peers/{id}/saida` | Os blocos do registro salvo: bloco do peer, remoção e "ao criar o peer" quando o tipo tem. Grupo apontado que não existe mais dá 422 com `grupo_id: "grupo nao encontrado"`, como o `GET /saida/{token}`. |
| `POST /api/irr` | Corpo `{"asn", "apelido", "forcar"}`. Consulta o bgpq4 e devolve `{"v4": [...], "v6": [...]}` sem gravar. ASN vazio ou zero dá 422 em `asn`; falha do bgpq4 dá 502 em `bgpq4`. |
| `GET /api/grupos` | Lista com id, nome, tipo e contagem de membros. |
| `GET /api/grupos/novo?tipo=`, `GET /api/grupos/{id}`, `GET /api/grupos/{id}/copia`, `POST /api/grupos`, `PUT /api/grupos/{id}`, `POST /api/grupos/previa?id=`, `GET /api/grupos/{id}/saida` | O mesmo conjunto do peer. O `GET /api/grupos/{id}` traz também a lista de membros (id e token). O `POST /api/grupos` recusa, com erro em `id`, um ID que já é de outro grupo: o `validar_grupo` não confere isso, porque na tela de hoje o ID escondido é a identidade do grupo e um POST com ID existente atualiza aquele grupo. No `PUT` vale o ID da URL e o do corpo é ignorado, como na tela de hoje, em que o ID do grupo não é editável. |
| `DELETE /api/grupos/{id}` | Exclui. Com membros, 409 com `membros` na mesma mensagem do `POST /grupo/{nome}/excluir`. |
| `GET /api/blocos` | O texto de v4 e de v6 no formato de hoje (`_texto_blocos`) e os blocos de originação e remoção do cadastro salvo. |
| `PUT /api/blocos` | Corpo `{"v4": "texto", "v6": "texto"}`. Valida com `validar_blocos`, grava o `peers.yaml` e o `out/blocos.txt` e devolve o mesmo que o `GET`. |
| `POST /api/blocos/previa` | Valida e monta o bloco de originação sem gravar, com o conteúdo de `out/blocos.txt` para o diff. |
| `POST /api/blocos/irr` | Corpo `{"v4", "v6", "forcar"}`. Consulta o IRR do AS da rede, mescla com o texto recebido (`mesclar_blocos`) e devolve o texto novo, com os ausentes marcados como hoje. Não grava. |

As rotas de peer e grupo usam o ID porque ele é a identidade do registro. Peer e grupo disputam os mesmos IDs (`proximo_id` olha as duas listas), então um ID aponta para um registro só.

### A prévia

`POST /api/peers/previa?id=<id>` recebe o modelo do formulário. O `id` é o do registro sendo editado e falta quando o peer é novo.

1. Converte pelo adaptador e roda `peer_do_formulario` e `validate.validar` com o registro de `id` como anterior, exatamente como o salvar.
2. Com erro, devolve 200 com `erros`, `avisos` e nenhum bloco. A prévia é informativa, então erro de validação não é erro HTTP aqui.
3. Sem erro, devolve `bloco` (o `render_peer` do peer do formulário), `criar_lista` (o `render_criar_lista`, quando o tipo tem o quadro), `avisos`, `arquivo` (o nome que o salvar escreveria em `out/`) e `salvo`.
4. `salvo` é o conteúdo atual do arquivo em `out/` do registro de `id` (o `anterior.arquivo()`), ou `null` quando não há registro ou o arquivo não existe.

Nada é gravado: nem `peers.yaml`, nem `out/`. Um teste confere os dois.

A remoção fica fora da prévia. Ela desfaz o que está no equipamento, e o que está no equipamento é o registro salvo, então a aba "remoção" sempre vem do `GET /api/peers/{id}/saida`. Peer novo não tem essa aba.

A prévia do grupo e a dos blocos seguem o mesmo contrato, com o arquivo de cada um (`out/grupo-<nome>.txt` e `out/blocos.txt`). No grupo, o `criar_lista` só sai quando `plan.quadro_ao_criar(grupo, de_grupo=True)` diz que o quadro existe, o que hoje é só o grupo de upstream. Os blocos não têm quadro "ao criar".

### Campos por tipo

O mapa de qual campo pertence a qual tipo hoje está espalhado: nas tags da tela do peer e nos `data-para` da tela do grupo. Ele passa a ser uma tabela em `app/formulario.py`, servida pelo `/api/plano`, e o front não decide sozinho o que mostrar.

A tabela foi conferida no render e na validação: para cada campo e cada tipo, o peer de teste de `test_render.py` foi renderizado com o campo vazio e preenchido, e validado nos dois estados. Um campo pertence a um tipo quando muda a saída daquele tipo ou quando a validação o exige ali. Fora dos tipos da tabela, o campo não muda a saída ou é recusado pela validação (é o caso do `default_route`, que o macro emitiria em qualquer tipo e a validação só aceita em cliente e parceiro).

Peer:

| Campo | Tipos |
| --- | --- |
| `classe`, `pop`, `default_route` | cliente, parceiro |
| `aprendizado` | upstream, ix |
| `prepend_base`, `bh_upstream`, `ap_block`, `ap_te`, `te_prefixos_v4`, `te_prefixos_v6` | upstream |
| `ix_id`, `ap_prefer` | ix |
| `ap_allowed` | pni |
| `communities`, `large_communities` | cliente, parceiro, upstream |
| todos os outros, inclusive `apelido` | todos |

Grupo:

| Campo | Tipos |
| --- | --- |
| `classe`, `pop`, `default_route` | cliente, parceiro |
| `aprendizado`, `prepend_base`, `bh_upstream`, `ap_block`, `ap_te`, `te_prefixos_v4`, `te_prefixos_v6`, `communities`, `large_communities` | upstream |
| `aprendizado_ix`, `ix_id`, `ap_prefer` | ix |
| `ap_allowed` | pni |
| todos os outros | todos |

O `apelido` tem a tag "IX e PNI" na tela de hoje, mas o cadastro real tem upstream com apelido (`BRDIGITAL`, `ALT`, `VIAMS`), e o apelido muda a saída de todo tipo. Ele fica visível em todos. Um teste da etapa 1 refaz a conferência acima a cada execução, e a tabela não pode divergir dos templates sem a suíte quebrar.

Um campo aparece quando pertence ao tipo, quando tem erro ou quando tem valor. A última condição é o que impede um dado de ficar guardado e invisível. A tela de grupo de hoje esconde pelo tipo sem olhar o valor, e o próprio comentário do JS dela registra isso como pendência. Numa cópia, ou depois de trocar o tipo, os campos de outro tipo que têm valor continuam à vista, com a nota "o bloco de <tipo> não usa este campo".

## Telas

### Casca e navegação

Barra lateral fixa à esquerda. No topo, o nome do app e o AS da rede, e o AS leva às configurações. Abaixo, uma busca que filtra por ASN, apelido, nome e tipo, e as seções: Peers (com o tipo em badge), Grupos (com a contagem de membros), Prefixos próprios, Bloco base e Configurações. O botão "+ novo" abre um menu com peer de cada tipo e grupo. Abaixo de 1024 px a barra vira uma gaveta.

URLs:

| URL | Tela |
| --- | --- |
| `/peers` | Casca com a lista e um estado vazio ("escolha um peer ou crie um") |
| `/peers/:id` | Peer |
| `/peers/novo?tipo=ix` | Peer novo |
| `/peers/novo?de=:id` | Cópia |
| `/grupos/:id`, `/grupos/novo?tipo=`, `/grupos/novo?de=:id` | Grupo |
| `/prefixos` | Prefixos próprios |
| `/base` | Bloco base |
| `/configuracoes` | AS da rede, namespace, tema |

A paleta abre com Ctrl+K (Cmd+K no Mac). Ela pula para qualquer peer ou grupo e executa ações: novo peer de um tipo, novo grupo, duplicar o registro aberto, copiar o bloco aberto, baixar o bloco base e trocar o tema. Ctrl+S (Cmd+S) salva a tela aberta. Esc fecha diálogo e paleta.

As listas vêm do TanStack Query e são invalidadas depois de salvar, excluir e gravar o AS. Elas também recarregam quando a janela volta ao foco, e uma edição manual no `peers.yaml` aparece sem F5.

### Peer

Cabeçalho da tela com o nome, badges de tipo, token, ASN e grupo, e os botões Salvar e Duplicar. O menu "⋯" tem Excluir, que abre um diálogo de confirmação com o token do peer no texto.

Abaixo, em tela de 1280 px ou mais, o formulário ocupa a esquerda e o painel de saída a direita, fixo enquanto o formulário rola. Abaixo de 1280 px, formulário e saída viram duas abas.

O formulário mantém as seções de hoje: identificação, política, limites e timers, prefixos anunciados, prefixos de exceção de TE, AS-path, CL-PEER e sessões. Um índice no topo leva a cada seção e mostra quantos erros cada uma tem.

- Seleção fechada (tipo, grupo, classe, origem, prepend) usa o select do shadcn. A lista de origem muda com o tipo e a classe pela mesma regra da cascata de hoje, que lê as tabelas do `/api/plano`.
- LP, route-limit, POP e aprendizado usam um combobox que sugere da tabela ou do que já está cadastrado e aceita valor novo, como o datalist faz hoje.
- Trocar o tipo reescreve LP, route-limit e timers só quando eles ainda estão no default do tipo anterior. É a regra da função `cascata()` de hoje.
- Listas são textarea em fonte mono, uma entrada por linha, com a contagem de linhas no rótulo.
- A seção de prefixos tem o botão "consultar IRR" com a opção "ignorar o cache". O resultado substitui v4 e v6 no formulário sem gravar, como hoje.
- Com erro, um resumo no topo do formulário lista as mensagens. Cada uma é um link que rola até o campo e põe o foco nele, e o campo mostra a própria mensagem. Erro sem campo (o do bgpq4) aparece só no resumo e na seção de prefixos.
- Aviso do `validate.avisos` aparece embaixo do campo, em âmbar.
- Salvar com sucesso dá um toast com o arquivo gravado em `out/`. Um peer novo salvo leva a URL para `/peers/:id`.
- Sair da tela com alteração não salva, pela navegação da SPA ou fechando a aba, pede confirmação.

### Duplicar

O botão Duplicar leva a `/peers/novo?de=:id`. A tela carrega o `GET /api/peers/{id}/copia` e abre o formulário de peer novo preenchido, com um aviso no topo: "cópia de <token>: troque ASN, IPs remotos e o que mais for único antes de salvar". Salvar sem mudança faz o validador recusar o que se repete: o token (no campo do ASN ou do apelido), os IPs remotos e, em cliente e parceiro, os prefixos que se sobrepõem aos do original. O resumo de erro leva a cada um. A prévia mostra os mesmos erros enquanto a cópia não for ajustada. O grupo funciona igual, e lá o que colide é o nome.

### Grupo

A mesma estrutura do peer, com os campos do grupo e a mesma regra de campos por tipo. A tela mostra a lista de membros, cada um com link para `/peers/:id`. O Excluir de grupo com membros mostra a mensagem do 409 no diálogo, com os links dos membros.

### Prefixos próprios

Os editores de v4 e v6 ficam lado a lado, com o texto no formato de hoje: uma linha por prefixo, communities depois do CIDR, `!-` no começo para o que está fora de serviço. Um parágrafo curto acima dos editores explica o formato. Os botões são Salvar, "consultar IRR" e "reconsultar". Abaixo fica o painel de saída com as abas "originação" e "remoção", e o diff contra `out/blocos.txt`.

### Bloco base

O texto do `/base.txt` no painel de saída, com destaque, os botões copiar e baixar e uma nota com a ordem de colagem do README.

### Configurações

AS da rede e namespace das standard, com as mesmas mensagens de hoje e a nota de que o namespace só é necessário com ASN de 32 bits. Abaixo, o tema.

## Saída XPL

### Painel

Um componente só (`PainelSaida`) serve peer, grupo, prefixos e base. Ele tem abas, uma por bloco disponível, e para o peer são: bloco do peer, remoção (só com registro salvo) e "ao criar o peer" (só nos tipos com o quadro). O código tem numeração de linha e um botão de quebra de linha. Sem quebra, as linhas longas ganham rolagem horizontal. Em todo caso nenhuma linha fica cortada.

### Destaque de sintaxe

`web/src/lib/xpl.ts` é um tokenizador escrito para o XPL, sem biblioteca. Nem Prism nem Shiki conhecem a linguagem, e uma gramática TextMate no Shiki é mais peso do que um lexer desse tamanho.

Classes de token:

| Token | Exemplo |
| --- | --- |
| comentário | linha que começa com `#` ou `!-` |
| palavra-chave | `xpl`, `route-filter`, `end-filter`, `community-list`, `large-community-list`, `as-path-list`, `ip-prefix-list`, `end-list`, `if`, `elseif`, `else`, `endif`, `then`, `and`, `or`, `call`, `apply`, `approve`, `refuse`, `finish`, `pass`, `break`, `undo`, `peer`, `bgp`, `group`, `network`, `ip`, `route-static` |
| community | `64512:1500`, `64512:4:264130` |
| prefixo e IP | `192.0.2.0/24`, `2001:db8::/32`, `192.0.2.10` |
| nome de objeto | `CL-PEER-268127`, `UP-BRDIGITAL-EXPORT-V4` |
| número | `100`, `666` |
| texto | o resto |

A lista de palavras-chave sai dos templates `.j2`, e o plano da etapa 2 a confere contra eles. O teste que protege o tokenizador roda sobre todos os arquivos de `tests/golden/`, e juntar o texto de todos os tokens tem que devolver o arquivo original byte a byte.

### Diff e estado

O cabeçalho do painel diz o estado do bloco em relação ao arquivo em `out/`:

- "igual ao salvo", quando a prévia bate com o arquivo;
- "arquivo novo", quando `salvo` é `null`;
- "N linhas incluídas, M removidas", quando há diferença.

Um botão liga o modo diff, que marca as linhas incluídas em verde e as removidas em vermelho, calculado no front com `diffLines` da biblioteca `diff`.

A diferença pode aparecer sem nenhuma edição, ao abrir um peer, quando o `plan.py` ou um template mudou depois do último salvar. Nesse caso o cabeçalho diz "o arquivo em out/ está desatualizado", porque é isso que a diferença significa.

A prévia é pedida 400 ms depois da última alteração no formulário. A requisição anterior é cancelada quando outra começa. Com erro de validação, o painel não mostra bloco nenhum, só "a prévia volta quando os erros forem corrigidos". É a regra de hoje: nenhum bloco copiável que o salvar recusaria. Falha de rede na prévia mostra o erro no painel e não trava o formulário.

### Copiar

O que vai para o equipamento tem que ser o que está no `peers.yaml` e em `out/`. A prévia permitiria copiar um bloco que ainda não foi gravado, então:

- com o formulário igual ao salvo e a prévia igual a `out/`, o botão é "copiar";
- com alteração não salva ou com `out/` desatualizado, o botão é "salvar e copiar": grava, e só depois copia o bloco que a resposta do salvar confirmou;
- se o salvar recusar, nada é copiado e o resumo de erro aparece.

Na aba de remoção o botão é sempre "copiar", porque ela vem do registro salvo.

A cópia leva o texto puro, sem numeração. `web/src/lib/copiar.ts` tenta `navigator.clipboard.writeText`. Fora de origem segura (o app aberto por HTTP de outra máquina) o navegador não tem essa API, e a função cai para a cópia por seleção com `document.execCommand("copy")`. Se as duas falharem, o bloco fica selecionado e um toast pede Ctrl+C. O botão confirma com "copiado" por um segundo e meio.

Ao lado de copiar fica "baixar", que salva o bloco como `.txt` com o nome do arquivo de `out/`.

## Visual

É uma ferramenta de trabalho com muitos campos. A tela é densa e calma, e o que se destaca é o dado (ASN, IP, community) e o estado (erro, aviso, diff, não salvo).

### Cores

O operador pediu cores suaves. A regra: fundo e bordas com pouco contraste e pouca saturação, sem branco puro nem preto puro, e o texto corrido com contraste AA (4,5:1) nos dois temas. A suavidade fica no fundo e nas cores de apoio, porque texto apagado cansa mais que texto nítido.

Os tokens ficam em `web/src/estilo/tokens.css`, em oklch, com os nomes do tema do shadcn (`--background`, `--foreground`, `--card`, `--muted`, `--border`, `--primary`, `--ring` e os demais). Valores iniciais:

| Token | Claro | Escuro |
| --- | --- | --- |
| fundo | `oklch(0.975 0.004 85)` off-white quente | `oklch(0.21 0.012 250)` cinza-azulado |
| superfície (card) | `oklch(0.99 0.003 85)` | `oklch(0.245 0.012 250)` |
| superfície rebaixada | `oklch(0.955 0.005 85)` | `oklch(0.28 0.012 250)` |
| borda | `oklch(0.90 0.006 85)` | `oklch(0.33 0.012 250)` |
| texto | `oklch(0.28 0.012 250)` | `oklch(0.88 0.008 250)` |
| texto secundário | `oklch(0.50 0.012 250)` | `oklch(0.70 0.010 250)` |
| destaque (azul-petróleo) | `oklch(0.52 0.07 215)` | `oklch(0.72 0.07 215)` |
| texto sobre destaque | `oklch(0.98 0.01 215)` | `oklch(0.21 0.012 250)` |

Estados, com fundo dessaturado e texto tingido, sem bloco de cor cheia:

| Estado | Claro (fundo / texto) | Escuro (fundo / texto) |
| --- | --- | --- |
| sucesso e linha incluída | `oklch(0.95 0.03 150)` / `oklch(0.42 0.08 150)` | `oklch(0.30 0.04 150)` / `oklch(0.82 0.07 150)` |
| erro e linha removida | `oklch(0.95 0.025 25)` / `oklch(0.48 0.10 25)` | `oklch(0.31 0.04 25)` / `oklch(0.80 0.07 25)` |
| aviso | `oklch(0.95 0.035 80)` / `oklch(0.47 0.08 70)` | `oklch(0.31 0.035 75)` / `oklch(0.84 0.07 80)` |

Badges de tipo, todos na mesma luminosidade e com matizes diferentes. Claro: fundo `oklch(0.93 0.035 H)` e texto `oklch(0.42 0.06 H)`. Escuro: fundo `oklch(0.32 0.035 H)` e texto `oklch(0.85 0.05 H)`. Os matizes são cliente 150 (sálvia), parceiro 95 (areia), upstream 250 (pervinca), IX 300 (lavanda) e PNI 350 (malva). Erro e aviso têm ícone além da cor, e o badge de parceiro não se confunde com o aviso.

O destaque de sintaxe usa a mesma família, em luminosidade 0.45 a 0.50 no claro e 0.78 no escuro, com croma perto de 0.07: palavra-chave no matiz 215, community no 300, prefixo e IP no 150, nome de objeto no 250, número no 60 e comentário no texto secundário em itálico.

Esses valores são o ponto de partida. Um teste do Vitest calcula o contraste WCAG de cada par de texto e fundo nos dois temas e falha abaixo de 4,5:1 (3:1 para borda de campo e anel de foco). Um valor que não passe é ajustado na luminosidade, sem mudar o matiz.

### Tema

Claro, escuro ou sistema, com seletor nas configurações e na paleta. A escolha fica no `localStorage`, e sem ela vale o sistema. O tema é aplicado antes da primeira pintura, por um script curto no `index.html`, para a tela não piscar no tema errado.

### Tipografia e densidade

Inter para a interface e JetBrains Mono para ASN, IP, prefixo, community, textarea de lista e XPL, as duas pelo `@fontsource`, dentro do build. O app não depende de CDN e funciona em rede de gerência sem internet. Números em tabela e em badge usam algarismos tabulares.

Texto base de 14 px, rótulos de 13 px, campos de 32 px de altura, espaçamento em múltiplos de 4 px. Rótulos em caixa de frase, com acento ("sessões", "descrição"). A regra de ASCII do projeto vale para o XPL e para os comentários de código, que não mudam.

### Movimento e acessibilidade

Animação só em painel, diálogo, gaveta e toast, curta (150 a 200 ms), e nenhuma com `prefers-reduced-motion`. Tudo é alcançável por teclado, o foco é sempre visível, todo campo tem rótulo associado, e o toast e o estado da prévia são anunciados por `aria-live`.

## Erros

| Situação | O que a tela faz |
| --- | --- |
| 422 no salvar | Mensagem no campo e no resumo do topo. O formulário continua com o que foi digitado. |
| Erro de validação na prévia (200 com `erros`) | O painel mostra "a prévia volta quando os erros forem corrigidos" e os mesmos erros aparecem nos campos. |
| 404 | Toast "registro não encontrado" e volta para `/peers`. Acontece quando o peer foi excluído noutra aba ou no yaml. |
| 409 no excluir grupo | A mensagem com os membros aparece no diálogo. |
| 502 do bgpq4 | Mensagem na seção de prefixos. O resto da tela funciona. |
| 500 ou rede fora | Toast com "tentar de novo". O formulário não perde nada. |
| Build do front ausente | 503 com a instrução de build, descrito na arquitetura. |

## Testes

### Etapa 1: API

`tests/test_api.py`, com o `TestClient` e um `peers.yaml` temporário, no mesmo padrão do `conftest.py` atual:

- o `GET /api/plano` traz as tabelas do `plan.py` sem cópia (compara com os valores do módulo) e a tabela de campos por tipo;
- `novo` traz os defaults de cada tipo e o próximo ID livre, com os mesmos casos que o `test_app.py` já cobre para o `/peer/novo`;
- `copia` devolve tudo igual ao original, menos o ID;
- o salvar grava `peers.yaml` e `out/`, apaga o arquivo antigo quando token ou tipo mudam, e recusa ID, ASN, apelido e IP remoto repetidos com as mensagens e campos de hoje;
- a prévia não grava nada (compara `peers.yaml` e `out/` antes e depois), não devolve bloco com erro e devolve o `salvo` certo, inclusive `null` para peer novo e para arquivo ausente;
- o bloco da prévia é igual ao que o salvar escreve em `out/`;
- a volta completa do adaptador (peer para modelo para peer);
- os erros de campo do `/api/rede` para as faixas do AS e do namespace;
- o 409 do grupo com membros e o 404 de ID inexistente;
- blocos: salvar, prévia e IRR, com o bgpq4 substituído por mock como nos testes atuais;
- o formato 422 do corpo malformado.

`test_render.py`, `test_validate.py`, `test_peers.py`, `test_plan.py`, `test_prefixes.py`, `test_isolamento.py` e os golden não mudam.

### Etapa 2: front

- Vitest e Testing Library: tokenizador XPL sobre os golden (texto reconstruído idêntico, e nenhuma linha de comentário fora da classe comentário), resumo do diff, visibilidade por tipo (pertence, tem erro, tem valor), mapeamento de erro para campo e para seção no índice, cascata de defaults ao trocar tipo e classe, os três estados do botão copiar, o aviso de alteração não salva, o fallback da cópia fora de origem segura e o contraste dos tokens de cor.
- `tsc --noEmit`, ESLint e o `npm run api:conferir`.
- Playwright contra o uvicorn real com um `peers.yaml` temporário, em cinco fluxos: criar peer, errar e corrigir pelo resumo, duplicar e ajustar, editar e usar "salvar e copiar", editar grupo e tentar excluir com membro.

### Etapa 3: corte

Antes de apagar qualquer asserção do `test_app.py`, o plano da etapa 3 traz uma tabela que liga cada teste removido ao teste novo que cobre o mesmo comportamento (API ou front). Asserção sem par ganha um teste novo antes de sair. As asserções que só conferem marcação (classe CSS, `onclick`, `datalist`) saem sem par, porque a marcação deixa de existir, e a tabela diz isso linha a linha.

## Etapas

Uma spec, três planos. Cada plano roda na própria worktree, e o merge no checkout principal fica com o operador.

1. **API.** `app/formulario.py`, `app/api.py`, `app/modelos_api.py`, montagem no `app.py`, a tabela de campos por tipo, `tests/test_api.py`. As telas HTML continuam como estão e a suíte atual continua verde.
2. **SPA.** `web/` inteiro, os scripts de tipos, o serviço do build no FastAPI com o 503, o `Dockerfile` e os ignores, os testes do front e o README com o fluxo de desenvolvimento. As telas HTML continuam no `/`, e a SPA fica acessível em `/peers`.
3. **Corte.** `/` redireciona para `/peers`. Saem `pagina.html`, `pagina_grupo.html`, `_estilo.html`, `_copiar.html`, as rotas HTML e as asserções de HTML do `test_app.py`, pela tabela de pares. Os reexports do `app.py` saem. README e `CLAUDE.md` descrevem o app como ele fica.

## Riscos e pontos em aberto

- **Tabela de campos por tipo.** O ponto de partida vem das tags da tela, e uma tag pode estar desatualizada, como a do apelido estava. A etapa 1 confere cada linha contra templates e validação.
- **Custo da prévia.** Cada prévia relê o `peers.yaml` e roda o validador e o render. Com o cadastro de hoje (poucas dezenas de registros) isso é barato. Se ficar lento, o intervalo de 400 ms sobe antes de se pensar em cache.
- **Área de transferência depois do salvar.** O "salvar e copiar" escreve na área de transferência depois de uma requisição. O Chrome aceita dentro da janela de ativação do clique, e o Safari pode recusar. O plano da etapa 2 testa nos dois. Se o Safari recusar, a alternativa é salvar e trocar o botão para "copiar" já habilitado, pedindo um segundo clique.
- **Dois fronts até o corte.** Entre as etapas 2 e 3 as duas telas gravam o mesmo `peers.yaml`. Isso é aceitável porque a regra de gravação é uma só, mas a etapa 3 não deve demorar a vir.
