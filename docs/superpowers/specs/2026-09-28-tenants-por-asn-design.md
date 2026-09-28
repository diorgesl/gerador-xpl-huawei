# Tenants por ASN

2026-09-28

## Problema

O app serve uma rede só. O `peers.yaml` guarda, no mesmo arquivo, o AS da rede,
o namespace das standard, o cadastro de peers, os grupos e os blocos próprios; o
`out/` recebe os blocos gerados com o nome do token do peer e um `blocos.txt` de
nome fixo (`app/peers.py:27`, `app/render.py:15`). Trabalhar na segunda rede
significa sobrescrever a primeira, e o que estava em `out/` da primeira some
junto, inclusive o registro de que aquele bloco já foi colado no equipamento,
que é o que o diff da tela usa como referência.

Esta etapa faz do ASN da rede a unidade do app: cada rede vira um arquivo em
`peers/`, a pasta é a lista, e a tela ganha um seletor de qual rede está aberta.

## Decisões do brainstorming

| Pergunta | Decisão |
| --- | --- |
| O campo "AS da rede" da tela | Continua na tela, mas nesta rodada é somente leitura. Quem troca de ASN é o seletor |
| A chave `asn:` dentro do arquivo | Fica como cópia de leitura: o app grava e nunca lê. Discorda do nome do arquivo, o nome ganha |
| Como o ASN chega na API | Parâmetro de query obrigatório em toda rota de dados: `?asn=264130` |
| Onde saem os blocos gerados | `out/<ASN>/`, uma pasta por rede. O cache do bgpq4 fica em `out/.cache/`, que é do IRR e não da rede |
| A migração do `peers.yaml` | No boot, copiando para `peers.yaml.bak` e movendo para `peers/<asn>.yaml` |
| Criar ASN novo | Pela tela, um "novo ASN" no seletor, com o par AS + namespace |
| O que sai desta rodada | O rename (editar o ASN e o arquivo mudar de nome) e o ASN no caminho da URL |

### Por que o ASN no caminho da URL fica para depois

O seletor mora no `sessionStorage` nesta rodada, e não no caminho da URL
(`/a/64512/peers/3`). Isso custa um ponto: trocar de tenant também navega para
`/peers`, porque o id 3 do tenant A não quer dizer nada no tenant B, e o
`AvisoNaoSalvo` barra a navegação quando há rascunho sujo
(`web/src/components/AvisoNaoSalvo.tsx:20`). Sem o ASN na URL, a seleção
mudaria antes de o bloqueio aparecer, e a tela do peer A ficaria de pé com as
consultas apontando para B.

O conserto desta rodada está na seção do front. Com o ASN no caminho, a troca
seria uma navegação só e o bloqueio resolveria de graça; é o que a rodada do
roteador compra de volta.

## Escopo

### O que entra

- `app/tenants.py`, com a pasta, a lista, a criação, o `Tenant` e a migração.
- O `?asn=` em todas as rotas de dados, por uma dependência do FastAPI.
- `GET /api/asns` e `POST /api/asns`.
- `PUT /api/rede` sem o campo do ASN: só o namespace.
- O `Tenant` atravessando `app/api.py`, o `app/peers.py` e o `app/render.py` até
  o diretório de saída.
- O seletor de ASN na barra lateral, o estado vazio e a troca com rascunho sujo.
- A migração no `lifespan` do `app/app.py`, ao lado do `auth.bootstrap()`.
- O `.gitignore`, os fixtures do pytest e do e2e, e o README.

### O que não entra

- **Renomear o ASN pela tela.** O campo continua editável na rodada que trouxer
  o rename, junto com o `PUT /api/rede {asn}` e o move do arquivo e do `out/`.
- **O ASN no caminho da URL.** Endereço por rede, botão de voltar entre redes,
  link compartilhado.
- **Usuário ligado a ASN.** O `usuarios.yaml` tem um admin só. Permissão por
  rede é um sistema à parte, e não tem caso de uso hoje.
- **Duplicar um tenant a partir de outro.** Copiar o arquivo à mão resolve.
- **`.dockerignore`.** Hoje ele não ignora o `peers.yaml`, então o cadastro
  entra na imagem. Pode ser intencional (deploy sem o bind mount do
  `compose.yaml`), e mexer nisso sem saber quebraria um deploy que funciona.

## Comportamento

### A pasta e o arquivo do tenant

```
peers/264130.yaml                       # asn, asn_politica, peers, grupos, blocos
peers/64512.yaml
out/264130/blocos.txt                   # o que saiu de cada rede
out/264130/14840-upstream.txt
out/.cache/                             # do IRR, compartilhado
usuarios.yaml                           # global: quem entra no app
```

A lista de tenants é a listagem de `peers/`: os arquivos cujo nome é só dígitos
mais `.yaml`, ordenados. Qualquer outra coisa é ignorada em silêncio, para um
`peers/notas.txt` ou um `.DS_Store` não derrubarem a tela.

O conteúdo do arquivo é o de hoje menos a posição: `asn` (cópia de leitura),
`asn_politica`, `peers`, `grupos`, `blocos`. As chaves ausentes continuam
significando o que significam hoje: `asn_politica` ausente é o namespace igual
ao próprio ASN, `blocos` ausente é quem nunca usou a tela
(`app/peers.py:455-469`).

### A chave `asn` e o nome do arquivo

O nome do arquivo é a verdade, e o app nunca lê a chave `asn`. Ele continua
sendo gravado em toda escrita, para o arquivo se descrever sozinho quando
alguém o abre no editor ou o copia para fora. Se as duas discordarem, o nome
ganha e nada reclam; na primeira escrita pela tela a chave volta ao valor do
nome, porque o `gravar_asn` monta o dicionário a partir do ASN do tenant
(`app/peers.py:244-265`).

### `app/tenants.py`

```python
PASTA = RAIZ / "peers"      # lido na hora, como o PEERS_YAML de hoje
SAIDA = RAIZ / "out"

@dataclass(frozen=True)
class Tenant:
    asn: int
    caminho: Path
    saida: Path

def listar(): ...       # os ASNs dos arquivos, ordenados
def existe(asn): ...
def abrir(asn): ...     # o Tenant, ou None
def criar(asn, politica): ...
def migrar(): ...
```

`criar` confere a faixa do ASN com a mesma `_conferir_faixas` do formulário
(`app/formulario.py:466`) e a coerência do par pelo `plan.Rede`, para que um
ASN de 32 bits sem namespace seja recusado na criação em vez de nascer um
arquivo que estoura na primeira leitura. O arquivo nasce com `asn`, com
`asn_politica` quando declarado, e sem `peers`, `grupos` ou `blocos`: a chave
ausente é o estado de quem ainda não usou a tela.

### A migração

Roda uma vez, no `lifespan` do `app.py`, antes da primeira requisição. Se
`peers.yaml` não existe, não faz nada.

1. O ASN sai do `carregar_asn` de sempre: a chave, ou o AS de fábrica quando ela
   falta (`app/peers.py:221-241`).
2. O arquivo é copiado para `peers.yaml.bak`.
3. O original é movido para `peers/<asn>.yaml`.
4. Os `out/*.txt` da raiz vão para `out/<asn>/`, sem tocar em `out/.cache/` e
   sem sobrescrever destino que já exista.

A cópia antes do move é o que faz o segundo boot ser no-op: ou os dois arquivos
estão lá (nada aconteceu), ou só o `.bak` está (a migração terminou). Depois
disso o `peers.yaml` não existe mais, então a condição de disparo, que é ele
existir, não volta a ser verdadeira sozinha.

### Quando dá errado

- **`peers.yaml` que não fecha.** ASN de 32 bits sem `asn_politica` é o
  `ValueError` que hoje estoura na primeira requisição
  (`app/peers.py:236-241`), e o mesmo vale para uma faixa fora do intervalo. A
  migração desiste, deixa o arquivo intacto, imprime o motivo e o app sobe com
  a lista vazia. Um `restart: unless-stopped` do docker não pode virar laço de
  restart por causa de um arquivo torto.
- **Destino ocupado.** `peers/<asn>.yaml` já existindo, ou um arquivo com o
  mesmo nome em `out/<asn>/`: nada é sobrescrito, o que colidiu fica onde está e
  a linha no log diz qual.
- **ASN que não existe na URL.** `?asn=999` sem arquivo dá 404 com o corpo do
  `ErroResposta` (`erros`, `avisos`), o mesmo formato de todas as recusas.
  `?asn=` ausente ou não numérico dá 422 pelo `_pedido_invalido` que já existe
  (`app/api.py:767`).
- **Pasta sem permissão de escrita.** Criar e migrar falham com a mensagem do
  erro do sistema, como o bootstrap do `usuarios.yaml` faz.

## API

### O `?asn=`

Uma dependência resolve o tenant e devolve o `Tenant`; quem não existe dá 404.

```python
def tenant(asn: int = Query(...)) -> Tenant: ...

@roteador.get("/peers", response_model=list[PeerResumo])
def listar_peers(t: Tenant = Depends(tenant)): ...
```

São 26 rotas nesse formato: as de peer, grupo, blocos, IRR, plano, rede e
config. O `_yaml()` do `app/api.py:129-132` sai, e quem entra no lugar dele nos
corpos é `t.caminho`.

O `app/peers.py` já é todo parametrizado por caminho (`carregar(caminho=...)`,
`gravar(peers, caminho=...)`, `carregar_blocos(caminho=...)`), então a camada
de armazenamento quase não muda. O que precisa de assinatura nova é o diretório
de saída: `Peer.arquivo()` e `Grupo.arquivo()` (`app/peers.py:159-160` e
`350-351`) passam a receber a pasta, obrigatória, e os `escrever_*` do
`app/render.py` junto. `peers.OUT` e `render.OUT` dão lugar a `tenants.SAIDA`, e
o `prefixes.CACHE` passa a ser `tenants.SAIDA / ".cache"`.

A pasta é obrigatória e não tem padrão de propósito: um default para a raiz do
`out/` deixaria uma chamada esquecida escrever em `out/<token>-<tipo>.txt`, que
é exatamente o nome que esta etapa elimina.

### As rotas novas

| Rota | O que faz |
| --- | --- |
| `GET /api/asns` | A lista de ASNs, para o seletor. Não pede `?asn=` |
| `POST /api/asns` | Cria o tenant. Recebe `{asn, politica}`, devolve a lista nova com 201 |

A lista sai como texto, `["264130", "64512"]`, como os outros campos da API, e é
o que a tela compara com o que está guardado no `sessionStorage`. O diretório do
tenant nasce na primeira escrita, com o mesmo `mkdir` que hoje cria o `out/`
(`app/render.py:57`).

O `POST` recebe o par inteiro, e não só o ASN, porque um ASN de 32 bits precisa
do namespace para ter um arquivo que funcione: criado sozinho, ele nasceria
estourando na primeira leitura, e a tela não teria como consertá-lo, porque o
plano do tenant é justamente o que falha. As duas recusas são 422 com o erro no
campo que o causou: `asn` repetido, e `politica` que faz falta ou que não fecha.

### As rotas que mudam de significado

`PUT /api/rede` fica só com o `asn_politica`. O ASN vem do tenant, e o
`gravar_asn` do `app/peers.py:244` continua sendo quem escreve, chamado com o
ASN do arquivo: ele reescreve a chave `asn` com o valor que já estava lá e
liga ou apaga o `asn_politica` conforme o formulário.

`GET /api/plano` continua devolvendo o `rede.asn`, agora como eco do `?asn=`: é
o que confirma para a tela qual tenant respondeu.

## Front

### O seletor

`web/src/app/tenant.tsx` novo, com o contexto, o `useAsn()` e o provedor, que
entra no `web/src/app/provedores.tsx` junto do tema. O ASN mora no
`sessionStorage`, na chave `bgpgen.asn`, e o valor guardado vale enquanto estiver
na lista; fora dela (primeiro boot, aba nova, tenant apagado à mão) vale o
primeiro da lista. É esse fallback que faz o e2e continuar passando sem mudança
de fluxo.

O seletor fica no cabeçalho da `web/src/components/BarraLateral.tsx:50-55`, no
lugar do link `AS{asn}` que já está lá: um `DropdownMenu` com os tenants, o atual
marcado, um separador, "novo ASN" e o link para as Configurações. Criar abre um
diálogo com os dois campos do fieldset AS da rede e, ao gravar, seleciona o
tenant novo e vai para `/peers`.

Sem nenhum tenant, a `Casca` desenha uma tela explicando que `peers/` está vazia
e um botão para criar a primeira, com as consultas desabilitadas em vez de
disparando com ASN vazio.

### As consultas

As chaves do `react-query` passam a carregar o ASN. Quem monta as chaves são os
hooks, e é lá que a mudança mora: `web/src/api/consultas.ts` e
`web/src/api/previa.ts` passam a produzir `["peers", asn]` e a mandar
`params: { query: { asn } }` em cada chamada.

As invalidações espalhadas pelas telas não mudam. `invalidateQueries({ queryKey:
chaves.peers })` casa por prefixo, então `["peers"]` atinge `["peers", "264130"]`
e `["peers", "64512"]` de uma vez, que é o comportamento desejado depois de
salvar: o ASN entrou no nome de toda community e tudo que estava na tela ficou
velho.

### A troca de tenant

Trocar de tenant navega para `/peers`, porque os ids são por tenant e o registro
aberto não existe do outro lado.

O rascunho sujo é o ponto delicado. Cada tela de formulário já calcula o `sujo`
que passa para o `AvisoNaoSalvo`, e a troca publica esse valor no contexto de
ações (`web/src/app/acoes-contexto.ts`), onde o seletor o lê. Com rascunho sujo,
o seletor pergunta antes, com o mesmo texto do aviso de saída; confirmando, o
tenant troca e a navegação segue; cancelando, nada muda.

O `usePublicarAcoes` hoje monta um objeto estável cujos campos são todos funções
(`web/src/app/acoes-contexto.ts:46-61`), e o `sujo` é um valor. Ele entra por
fora dessa lista de campos, com o próprio caminho: quem quiser saber se há
rascunho sujo pergunta ao contexto, e a resposta acompanha o render.

### O campo AS da rede

O `Input` do AS em `web/src/telas/configuracoes/ConfiguracoesTela.tsx:98-106`
vira texto somente leitura, com uma nota apontando para o seletor. O namespace
continua editável, e o `PUT /api/rede` que ele dispara não manda mais o ASN.

## Testes

- **`tests/test_tenants.py`, novo.** Listar (ordena, ignora o que não é `.yaml`
  de dígitos), criar (recusa repetido, recusa fora de faixa, recusa par
  incoerente, nasce sem as chaves que diriam nada), e a migração inteira: move,
  deixa o `.bak`, leva os `out/*.txt`, não toca no `out/.cache/`, é no-op no
  segundo boot, e o yaml torto não move nada.
- **Fixtures.** `tests/conftest.py:82-85` troca o patch do `PEERS_YAML` e dos
  dois `OUT` por um que cria `peers/<asn>.yaml` sob o `tmp_path` e aponta
  `tenants.PASTA` e `tenants.SAIDA`. Toda chamada de API nos testes ganha o
  `?asn=`. É o grosso do diff em `test_api*.py` e no `test_isolamento.py`, e
  cabe num helper da fixture.
- **`tests/test_api_asns.py`, novo.** A lista, a criação, as duas recusas, o 404
  do ASN que não existe e o 422 do `?asn=` ausente.
- **`tests/test_api.py:84` e `:96`, `tests/test_isolamento.py:274`.** Patcham
  `peers_mod.PEERS_YAML` na mão; passam a apontar a pasta de tenants.
- **Vitest.** O seletor (lista, troca, cria), o fallback do primeiro tenant, o
  estado vazio e a troca com rascunho sujo. As telas montadas nos testes
  existentes precisam do provedor novo, que vai num helper do `web/src/teste/`.
- **e2e.** O fixture `web/e2e/peers.yaml` vira `web/e2e/peers/64512.yaml`, e o
  `web/e2e/global-setup.ts:30` copia para `<temp>/peers/64512.yaml`. Os cinco
  fluxos seguem sem mudança.

### Os arquivos que andam junto

- **`.gitignore`.** `out/*.txt` não casa com `out/264130/blocos.txt`: com a
  pasta por tenant, os blocos de produção aparecem como não rastreados e entram
  num `git add .` sem ninguém ver. A linha dá lugar a `out/*/`. A linha
  `peers.yaml` dá lugar a `peers/` e `peers.yaml.bak`. E a exceção
  `!web/e2e/peers.yaml` precisa virar `!web/e2e/peers/`, senão o fixture do e2e
  sai do repositório junto.
- **README e CLAUDE.md.** Os dois descrevem o `peers.yaml` como o estado do app,
  e o comentário do bind mount no `compose.example.yaml` fala dele.

## Etapas

Uma spec, um plano. A implementação roda numa worktree, e o merge no checkout
principal fica com o operador, como nas etapas anteriores.

## Riscos e pontos em aberto

- **A migração roda no primeiro boot depois do merge, num arquivo de produção
  que o git não guarda.** O `.bak` é a rede de segurança, e ele nasce antes do
  move. Vale rodar o app uma vez contra uma cópia do `peers.yaml` antes de subir
  a versão nova no lugar onde ele vive.
- **Um `peers.yaml` que não fecha deixa o app sem nenhum tenant.** O sintoma é a
  tela vazia, e o motivo está no log do boot, não na tela. Se acontecer, o
  conserto é editar o arquivo e reiniciar.
- **A troca de tenant com rascunho sujo depende do que cada tela publica.** Uma
  tela nova que esqueça de publicar o `sujo` perde a pergunta, e o rascunho se
  perde em silêncio na troca. O teste de vitest cobre as telas de hoje; a que
  vier depois precisa entrar nele.
- **Duas abas no mesmo navegador podem ficar em tenants diferentes**, porque o
  `sessionStorage` é por aba e a API é sem estado. É a propriedade que a escolha
  do parâmetro de query compra, e não um defeito.
- **O campo do AS somente leitura é transitório.** Quem esperar editá-lo para
  trocar de ASN vai encontrar um campo travado até a rodada do rename.
