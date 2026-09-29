# bgpgen

Gera o bloco XPL de uma sessão BGP do AS64512 a partir de um formulário, mais
um bloco base com os sets e filtros que todas as sessões compartilham. A tela é
uma SPA em `web/`, servida pelo próprio FastAPI.

## O que é

A SPA lista os peers na barra da esquerda e abre cada um num formulário. Salvo o
formulário, o app escreve o bloco daquela sessão em
`out/<ASN>/<token>-<tipo>.txt`, sobrescrevendo só esse arquivo: gerar um peer
não toca na saída dos outros. O bloco base, que é igual para todos, sai em
`GET /base.txt`.

A barra tem ainda o "Política do cliente (PDF)", que baixa
`GET /politica-cliente.pdf`: o documento que o ISP entrega ao cliente, com as
communities que ele pode enviar e o que cada uma faz. O texto é montado no
namespace da rede, como o bloco base, e sai de `app/politica.py` (as tabelas,
lidas do `plan.py`) mais `app/pdf.py` (a folha). O `PLANO.md` tem a seção
"Tabela pública para clientes" com o mesmo texto, mas o app não a lê: o que
está no PDF é o que os filtros realmente consomem.

Por baixo dela o app serve uma API JSON em `/api`, que é quem fala com o
cadastro do tenant: a SPA não reimplementa regra nenhuma, e o parsing, a
validação e o render continuam no Python. A raiz (`/`) leva para `/peers`, e a
documentação interativa da API fica em `/docs`. A prévia
(`POST /api/peers/previa`) monta o bloco sem gravar nada. O desenho está em
`docs/superpowers/specs/2026-09-26-front-spa-design.md`.

O estado é a pasta `peers/`, um arquivo por ASN da rede: `peers/<ASN>.yaml`,
com o cadastro dos peers daquele AS. O que está em `out/<ASN>/` é saída, e está
no `.gitignore`.

## O que não faz

- **Não fala com o equipamento.** A saída é texto para colar no F1A; não há
  sessão NETCONF, SSH ou CLI. A única rede que o app toca é a consulta ao IRR,
  e ela só acontece quando você pede os prefixos no formulário.
- **Não decide política.** As regras saem de `app/plan.py`; o formulário
  preenche os valores daquele peer: tipo, classe, LP, prepend e limites.
- **Não guarda o conteúdo da `CL-PEER-<T>` no bloco do peer.** A lista vive no
  cadastro do peer e sai inteira no quadro "ao criar o peer". Reaplicar o bloco
  do peer mexe nos filtros e não tem como zerar o que está no equipamento.
- **Não importa nada do `PLANO.md`.** O documento é a referência de desenho; o
  app não o lê em tempo de execução.
- **O PDF não é por cliente.** Ele descreve a política da rede, que é a mesma
  para todos os clientes dela: não sai com os prefixos, o route-limit nem as
  sessões de quem vai receber. O bloco da sessão daquele cliente continua sendo
  o `out/<ASN>/<token>-<tipo>.txt`.
- **O PDF publica os identificadores que emitem `5PPA`, e só eles.** A tabela
  do alias em standard sai do cadastro da rede, com o ID e o ASN de cada fonte,
  porque o cliente não tem como descobrir esse número. Quem entra é o upstream
  sem grupo e o **grupo** de upstream: o membro de um grupo não tem `CL-5PPA`
  nenhum no bloco dele, então o ID do membro não é publicado. O upstream que
  reaproveita a política de outro peer fica de fora pela mesma razão: o bloco
  dele chama os filtros da origem, e o `CL-5PPA` que existe é o dela, com o ID
  dela — publicar os dois daria dois identificadores para o mesmo ASN, e um
  deles morto. IX e PNI ficam de fora pelo mesmo motivo: o filtro do IX não tem
  ramo de alias (o route server repassa o mesmo AS-path a todos os membros) e o
  do PNI ainda não implementa. Publicar ID que o equipamento não consome ensina
  o cliente a mandar community que morre no filtro.
- **Não regenera o bloco de quem reaproveita a política de outro peer.** Trocar
  o apelido da origem muda o token dela, e com ele o nome dos filtros chamados
  no bloco do outro. O app avisa e deixa a reaplicação para o operador, porque
  regenerar sozinho o bloco de outro peer quebraria a regra de que gerar um não
  mexe na saída do outro.
- **Não tem gestão de usuários.** É um admin só, criado no boot, e sem papéis.
  Trocar a senha é apagar o `usuarios.yaml` e reiniciar; não há tela para isso.

## Como subir

Com o venv do checkout:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.app:app --port 8000
```

O `bgpq4` é dependência de execução e precisa estar no `PATH`. Sem ele, o botão
de consultar prefixos devolve erro; o resto do app funciona igual. No macOS ele
não vem instalado, mas tem no brew (`brew install bgpq4`, hoje na 1.16).

Com Docker, que já traz o `bgpq4` junto:

```bash
cp compose.example.yaml compose.yaml
docker compose up --build
```

O `compose.yaml` não vem no repositório: ele é o arquivo do operador e pode
carregar a senha do admin, então o que fica versionado é o exemplo. A tela fica
em http://127.0.0.1:8765/, que cai em `/peers`. O `compose.yaml` monta o
checkout em `/app`, então a pasta `peers/` e o `out/` são os do repositório, e
editar um template de bloco vale na hora. Sem essa linha de `volumes:`, a imagem
roda sozinha com o que foi copiado no build.

A imagem é o `python:3.14-slim` mais o `bgpq4` 1.12 do repositório Debian. O
`bgpq4` do brew está na 1.16, então as duas rotas não dão a mesma versão do
binário.

Suíte: `.venv/bin/python -m pytest`, ou
`docker compose run --rm bgpgen python -m pytest` para rodar dentro do container.

### O front (SPA)

A tela é uma SPA em `web/`, servida pelo próprio FastAPI. Em produção não há
processo separado: o uvicorn serve a API, os arquivos do build e o `index.html`.

Em desenvolvimento são dois processos, com o Vite recarregando a tela na hora:

```bash
.venv/bin/uvicorn app.app:app --port 8000      # a API e a SPA
cd web && npm install && npm run dev           # a SPA em http://127.0.0.1:5173/peers
```

O Vite faz proxy de `/api` e `/base.txt` para a 8000, então a SPA funciona nos
dois modos com o mesmo código.

Os dois campos de `CL-PEER` (`communities` e `large_communities`) têm um botão
"adicionar" que abre uma busca: digitar `prepend` lista as de prepend, `14840`
lista as daquele ASN. Clicar insere o valor como linha no campo, que continua
livre para digitar e colar. A lista sai do `/api/plano`, montada do `plan.py`
no namespace da rede, e o ASN de cada entrada é o dos upstreams do cadastro:
não há uma segunda lista de communities escrita no front para divergir.

Para servir a SPA pelo uvicorn, com um processo só:

```bash
cd web && npm run build && cd ..
.venv/bin/uvicorn app.app:app --port 8000      # a SPA em /peers
```

O diretório do build vem de `BGPGEN_WEB`, e o padrão é `web/dist`. Sem build, as
rotas da SPA respondem 503 com a instrução de compilar; a API continua
funcionando.

### O login

O app sobe com um admin e uma senha sorteada. A senha sai uma vez, no log do
primeiro boot, e não é gravada em lugar nenhum: quem não guardou precisa apagar
o `usuarios.yaml` e reiniciar para gerar outra.

```bash
docker compose logs bgpgen | grep -A3 "admin criado"   # a senha do primeiro boot
```

O que fica atrás do login é o `/api` inteiro (menos as três rotas de sessão), o
`/base.txt`, o `/politica-cliente.pdf`, o `/docs` e o `/openapi.json`; a SPA e
os arquivos do build continuam abertos, senão a própria tela de login não
carregaria. A sessão é um
cookie de sete dias, e reiniciar o app não desloga ninguém: o que derruba as
sessões abertas é trocar o segredo, o que acontece quando o `usuarios.yaml` é
recriado.

Duas variáveis mexem nisso:

| Variável | Para quê |
| --- | --- |
| `BGPGEN_ADMIN_SENHA` | A senha do admin criado no boot, no lugar da sorteada. É o que o e2e usa |
| `BGPGEN_COOKIE_SEGURO=1` | Liga o atributo `Secure` do cookie, para quem põe o app atrás de um TLS |

O `usuarios.yaml` (o hash da senha e o segredo dos cookies) fica na raiz, ao
lado da pasta `peers/`, e é ignorado pelo git e pelo build da imagem.

### Testes do front

```bash
cd web
npm test              # Vitest: tokenizador XPL, diff, campos, contraste, componentes
npm run lint
npm run api:conferir  # falha se o schema.d.ts estiver velho em relação ao app.openapi()
npx playwright install  # uma vez: baixa os navegadores que o Playwright pede
npm run e2e             # Playwright: compila e roda os casos contra um uvicorn, logando uma vez no setup
```

O `npm run api:tipos` regenera o `web/src/api/schema.d.ts` a partir do
`app.openapi()`. O arquivo é versionado, e o `api:conferir` roda junto com a
suíte do Python quando o front está instalado: o `web/node_modules` no lugar e o
`npm` no `PATH`. Dentro do container ele é pulado, porque a imagem não tem
`npm` — o `node_modules` da máquina chega lá pelo bind mount do `compose.yaml`,
e é por isso que a condição olha os dois.

Os testes do Playwright sobem um uvicorn com uma pasta `peers/` temporária, com o
tenant de `web/e2e/peers/64512.yaml` copiado para `web/e2e/.tmp/peers/` pelo
`web/e2e/global-setup.ts`: o app resolve a pasta a partir da raiz do projeto, e a
cópia é o que permite apontá-lo para outro cadastro sem mudar o app. A cópia
**não** pode ser um `globalSetup` do Playwright: ele roda depois do `webServer`, e
o servidor precisa da árvore antes de subir. O e2e serve o `web/dist` de verdade,
então o `npm run build` vem antes — o script `e2e` faz isso.

Os 19 casos são o setup, que loga uma vez antes dos outros, os 10 do
`fluxos.spec.ts` e os 2 do `login.spec.ts`, que rodam só no chromium, mais os 3
do `copiar.spec.ts` nos dois navegadores. Um desses três é pulado no webkit, que
não expõe o `clipboard-read`: por isso a saída conta 18 passando e 1 pulado.

## Ordem de colagem no F1A

A tela "Config completa" (`/config-completa`) monta a config inteira nesta
ordem, para conferir antes de colar e para copiar tudo de uma vez. Ela marca o
que ainda não está em `out/<ASN>/`, que é a parte que provavelmente não subiu.

1. **O bloco base, uma vez, antes de tudo.** A tela serve em `GET /base.txt`,
   no botão "baixar bloco base". O corpo é montado na hora do download, então o
   que o navegador salva é sempre o que o `plan.py` diz agora: não há arquivo em
   `out/<ASN>/` guardando uma versão antiga, nem aviso de desatualizado para
   conferir. Salve onde quiser e cole antes dos blocos de peer.
2. **O bloco de cada grupo**, antes dos membros dele:
   `out/<ASN>/grupo-<nome>.txt`. O membro sem política própria herda o que o
   grupo define, e a sessão dele chama o grupo pelo nome: colar o membro antes
   deixa a referência pendurada.
3. **O bloco de cada peer**, na ordem que quiser:
   `out/<ASN>/<token>-cliente.txt`, `out/<ASN>/<token>-upstream.txt`,
   `out/<ASN>/<token>-ix.txt`, `out/<ASN>/<token>-pni.txt`. A ordem só deixa
   de ser livre quando o peer reaproveita a política de outro, pelo campo
   "Reaproveitar a política de": o bloco dele não define filtro nenhum e chama
   os da origem pelo nome, então o bloco da origem precisa estar no
   equipamento antes. Colar quem reaproveita primeiro deixa a referência
   pendurada, como no caso do membro de grupo.
4. **A `CL-PEER-<T>` do quadro "ao criar o peer"**, na primeira vez que aquela
   sessão subir, e de novo sempre que a lista mudar. Vale para cliente e
   upstream: são os dois tipos que ganham community própria de sessão. O IX não
   precisa (o route server repassa o mesmo path a todos) e o PNI também não, e
   para esses dois o quadro nem aparece. Os membros saem do campo "CL-PEER, uma
   por linha" do formulário, então re-colar o quadro troca o conteúdo pelo que
   está no cadastro; reaplicar o bloco do peer mexe só nos filtros e não tem
   como zerar o que está lá dentro.
5. **O bloco dos prefixos do próprio AS**, se houver: `out/<ASN>/blocos.txt`,
   escrito no salvar da seção de blocos. Ele traz as estáticas de ancoragem, os
   `ORIGEM-<endereço>_<máscara>` e as linhas `network` de cada família, na
   ordem em que se cola. O bloco de remoção sai na tela, ao lado do de
   originação.

## O que confirmar no equipamento antes do primeiro peer

Perguntas que ficaram em aberto no `PLANO.md`:

- se `apply community` aceita lista nomeada, e se a sintaxe leva `community-list`
  no meio. A mesma dúvida vale para a linha de `apply large-community
  large-community-list`, que o `APPLY-PEER-<T>` só emite quando o cadastro tem
  large community;
- se uma `community-list` sem membro é aceita;
- se um filtro que declara `($prepend_base)` na assinatura aceita ser chamado sem
  os parênteses. Se não aceitar, a sessão sem prepend de engenharia precisa de
  uma segunda variante do filtro, sem o parâmetro na assinatura.
