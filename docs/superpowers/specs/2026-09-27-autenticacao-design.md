# Autenticação do bgpgen

2026-09-27

## Problema

O app está aberto. Quem alcança a porta lê o `peers.yaml` inteiro, gera o bloco
de qualquer peer, salva por cima, apaga grupo e pede prefixo ao IRR. O
`compose.yaml` publica em `127.0.0.1:8765` e o problema fica pequeno, mas
qualquer decisão de expor o app em outro lugar esbarra numa senha que não
existe.

Esta etapa põe um login na frente do app, com um admin criado no primeiro boot
e senha aleatória impressa no log.

## Decisões do brainstorming

| Pergunta | Decisão |
| --- | --- |
| Quem são os usuários | Um admin só, criado no boot. Sem tela de gestão de usuários e sem papéis |
| Como o operador recebe a senha | Impressa no log do boot, uma vez. `BGPGEN_ADMIN_SENHA` no ambiente sobrepõe a sorteada |
| Mecanismo | Cookie de sessão assinado com HMAC-SHA256, `scrypt` para a senha, tudo da stdlib |
| Superfície | Todo o `/api` menos as três rotas de sessão, mais `/base.txt`, `/docs` e `/openapi.json`. A SPA e os arquivos do build ficam abertos |
| Trocar a senha | Apagar o `usuarios.yaml` e reiniciar o app |

### Por que cookie assinado e não HTTP Basic

O app é uma SPA e o front precisa saber se há sessão antes de desenhar a casca.
Com Basic o navegador abre o popup nativo, não existe logout de verdade e a
única forma de a SPA descobrir que a sessão caiu é a primeira chamada falhar.
Com cookie, o `GET /api/sessao` responde a pergunta e o logout apaga o cookie.

### Por que `/docs` fica protegido

O `app.openapi()` continua acessível dentro do processo, que é de onde o
`npm run api:tipos` o lê (`web/scripts/api-tipos.mjs:14`). Fechar as duas rotas
HTTP não atrapalha a geração do `schema.d.ts` e tira o mapa da API da mão de
quem não entrou. Com o cookie no navegador, o Swagger continua utilizável.

## Escopo

### O que entra

- `app/auth.py`, com o arquivo de usuários, o bootstrap, a senha, o cookie e a
  dependência `exigir_login`.
- O `lifespan` no `app.py`, que chama o bootstrap.
- `POST /api/login`, `POST /api/logout` e `GET /api/sessao`, com o
  `LoginPedido` e o `SessaoResposta` em `app/modelos_api.py` e o
  `web/src/api/schema.d.ts` regerado.
- A dependência `exigir_login` nas rotas protegidas.
- A tela de login, a guarda de sessão, o tratamento de 401 e o botão "sair".
- O login no e2e e os dois testes que montam `TestClient` por conta própria.

### O que não entra

- **Limite de tentativas de login.** É um admin só, numa ferramenta que escuta
  em loopback. Quem expõe o app na internet resolve isso no proxy da frente.
- **Tela de troca de senha e comando de CLI para trocá-la.** O caminho é apagar
  o `usuarios.yaml` e reiniciar. Uma tela de usuários foi descartada no
  brainstorming.
- **Sessão com validade deslizante ou lista de sessões no servidor.** Sete dias
  fixos desde o login, e reiniciar o processo não desloga ninguém.
- **HTTPS.** O app fala http em loopback. Quando houver TLS na frente, a
  variável `BGPGEN_COOKIE_SEGURO=1` liga o atributo `Secure` do cookie.

## Comportamento

### O arquivo de usuários

`usuarios.yaml` mora na raiz do checkout, ao lado do `peers.yaml`, e é lido do
disco a cada login, como o `peers.yaml` é lido a cada requisição. Entra no
`.gitignore` e no `.dockerignore`: o arquivo tem o hash da senha e o segredo
que assina os cookies, e nenhum dos dois pode viajar dentro da imagem.

```yaml
segredo: "<32 bytes em base64url>"
usuarios:
  admin:
    salt: "<16 bytes em base64url>"
    hash: "<32 bytes em base64url>"
    n: 16384
    r: 8
    p: 1
```

Os parâmetros do scrypt ficam no arquivo, e não fixos no código, para que
aumentá-los depois não invalide o hash que já está lá.

O arquivo é escrito com permissão `0600`.

### O bootstrap

Roda no `lifespan` do FastAPI, ou seja, antes de a primeira requisição ser
atendida. Ele lê o `usuarios.yaml`. Se o arquivo não existe, ou existe sem
nenhum usuário dentro, cria o `admin`:

- a senha é `BGPGEN_ADMIN_SENHA` quando a variável está no ambiente, e
  `secrets.token_urlsafe(12)` quando não está (16 caracteres, 96 bits);
- o `segredo` nasce junto, com `secrets.token_urlsafe(32)`;
- a senha sai no log e não é gravada em lugar nenhum.

```
==================== bgpgen ====================
 admin criado. usuario: admin
 senha: 7Kx2Qm-9pRt4Wz8A
 esta senha nao aparece de novo. Para trocar,
 apague usuarios.yaml e reinicie o app.
================================================
```

O texto é ASCII, como as outras mensagens do app, e sai com `print(...,
flush=True)`: o app não configura `logging`, e o `print` chega no
`docker compose logs` sem depender de nível de logger.

Se já existe usuário, o bootstrap não escreve nada e não imprime nada. Se o
arquivo não existe e não dá para criar (volume somente leitura), a subida
falha com a mensagem do erro: um app que sobe sem login é pior do que um app
que não sobe.

### A senha

`hashlib.scrypt(senha, salt=salt, n=n, r=r, p=p, dklen=32)`, conferida com
`hmac.compare_digest`. Medido no venv do checkout: 27 ms por conferência com
`n=16384, r=8, p=1`, que é o que uma tela de login pode pagar.

### O login e a sessão

`POST /api/login` recebe `{usuario, senha}` e, quando confere, devolve
`Set-Cookie: bgpgen_sessao=admin.<expira>.<assinatura>` com `httpOnly`,
`SameSite=Lax`, `path=/` e `Max-Age` de sete dias. O `expira` é um epoch em
segundos e a `assinatura` é o HMAC-SHA256 de `admin.<expira>` com o `segredo`
do arquivo, em base64url. Não existe estado de sessão no processo: quem valida
a assinatura e a validade é o `exigir_login`, a cada requisição.

Usuário ou senha errados devolvem 401 com a mesma mensagem nos dois casos
(`usuario ou senha invalidos`), e não dizem qual dos dois falhou.

`POST /api/logout` devolve o mesmo cookie com `Max-Age=0`. `GET /api/sessao`
responde `{logado: bool, usuario: str | null}` sem exigir cookie, e é o que a
SPA usa para escolher entre a casca e a tela de login.

`SameSite=Lax` é a defesa de CSRF desta etapa: ele barra o cookie em POST de
outra origem, e os endpoints que escrevem só aceitam corpo JSON, que exige
preflight quando vem de outro site.

### A superfície protegida

| Rota | Sem sessão |
| --- | --- |
| `/api/login`, `/api/logout`, `/api/sessao` | abertas por definição |
| todo o resto de `/api` | 401 com o corpo do `ErroResposta` (`erros`, `avisos`) |
| `/base.txt` | 401 |
| `/docs`, `/openapi.json` | 401 |
| `/`, as rotas da SPA, `/assets/*`, `/favicon.svg` | abertos: a tela de login precisa carregar antes de existir cookie |

O `exigir_login` é uma dependência do FastAPI. Ela entra no `roteador` de
`app/api.py:112`, que passa a ser o roteador protegido, e as três rotas de
sessão saem dele para um segundo `APIRouter`. Fora de `/api` ela entra em
`/base.txt`, em `/docs` e em `/openapi.json`, que passam a ser declarados à mão
(o `app` nasce com `docs_url=None`, `openapi_url=None` e `redoc_url=None`, e as
duas rotas voltam com a dependência). O `instalar()` (`app/api.py:672`) não
muda de forma: ele inclui os dois roteadores.

### Quando dá errado

- **Senha esquecida:** apagar o `usuarios.yaml` e reiniciar. O boot seguinte
  recria o admin com senha nova e imprime.
- **Cookie expirado ou adulterado:** 401, e a SPA volta para a tela de login.
- **Senha errada no login:** 401 na tela, sem levar para lugar nenhum, para não
  perder o que foi digitado.
- **`usuarios.yaml` apagado com o app de pé:** toda requisição passa a dar 401,
  inclusive o login, porque não há segredo para conferir nada. O app fica
  trancado até reiniciar, que é o comportamento previsível: o bootstrap só roda
  no boot.
- **`segredo` ou `hash` torto no arquivo:** a leitura estoura, o login vira 500
  pelo `_falha_inesperada` que já existe, e a mensagem nomeia o arquivo.

## Front

### A tela de login

`web/src/telas/login/LoginTela.tsx`, registrada em `/login` fora da `Casca`,
para não desenhar barra lateral em quem ainda não entrou. Campo de usuário
pré-preenchido com `admin`, campo de senha, e a mensagem de erro da recusa 401
em cima do botão. Ao entrar, navega para `/peers`.

A rota `/login` precisa entrar na lista de rotas da SPA em `app/app.py:115`: o
servidor é quem responde o `index.html` de um F5 na tela de login, e sem a
linha o recarregamento dá 404 antes de o React existir.

### A guarda

`web/src/app/roteador.tsx` ganha um `ExigeLogin` em volta da `Casca`, que
consulta `GET /api/sessao`. Enquanto a consulta está em voo, não desenha nada
(meia tela de casca piscando é pior que meio segundo parado); com
`logado: false`, `<Navigate to="/login" replace />`.

### O 401 no meio do caminho

`web/src/api/cliente.ts` ganha um middleware que chama o callback registrado
por `aoPerderSessao(fn)` a cada 401, seja de qual chamada for. Quem registra é
o `provedores.tsx`, que é onde o `QueryClient` vive: o callback limpa o cache e
navega para `/login` com `window.location.replace`. A escolha do
`location.replace` é o que descarta o formulário em edição no meio do caminho,
que não teria para onde ir depois do login. O `credentials: "same-origin"`
entra explícito no cliente, mesmo sendo o padrão do `fetch`, para que a
intenção esteja escrita.

Esse middleware precisa de um teste que prove que ele não atrapalha os erros
que já existem: 422 e 500 continuam chegando na tela como hoje.

### O sair

Um botão na `BarraLateral.tsx`, ao lado do que já está lá, que chama
`POST /api/logout`, limpa o cache do `react-query` e vai para `/login`.

## Testes

- **`tests/conftest.py`:** a fixture `api` passa a fazer o boot de verdade
  (context manager do `TestClient`, com `BGPGEN_ADMIN_SENHA` monkeypatchada) e a
  entrar logada antes de devolver o cliente. Os 24 arquivos que usam a fixture
  seguem sem mudança.
- **Dois pontos que a fixture não cobre:** `tests/test_api.py:85` e `:97`
  montam `TestClient(mod.app, raise_server_exceptions=False)` na mão, e
  `tests/test_isolamento.py:273` monta o dela. Os três passam a usar um helper
  do `conftest` que devolve o cliente logado, senão viram 401.
- **`tests/test_auth.py`, novo:** o boot cria o admin e imprime a senha; o boot
  com arquivo já preenchido não reescreve nada; senha certa entra; senha errada
  e usuário errado dão 401 com a mesma mensagem; cookie adulterado dá 401;
  cookie vencido dá 401; o logout apaga; `/base.txt`, `/docs` e `/openapi.json`
  dão 401 sem cookie; as rotas da SPA e os assets seguem abertos; o arquivo
  nasce com permissão `0600`.
- **Vitest:** a tela de login (senha errada mostra a mensagem, senha certa
  navega), a guarda (sem sessão leva para `/login`, com sessão desenha a casca)
  e o middleware de 401 (redireciona no 401 e deixa 422 e 500 em paz).
- **e2e:** a senha entra pelo `BGPGEN_ADMIN_SENHA` no comando do `webServer` de
  `web/playwright.config.ts:36`, um projeto de setup loga pela tela e grava o
  `storageState`, e os 12 casos existentes passam a usá-lo. Um caso novo
  exercita a tela de login (senha errada, depois certa) e o sair.

## Etapas

Uma spec, um plano. A implementação roda numa worktree, e o merge no checkout
principal fica com o operador, como nas etapas anteriores.

## Riscos e pontos em aberto

- **A senha fica no log do container** enquanto ele existir. Quem tem acesso a
  `docker compose logs` tem a senha do admin, e apagar o `usuarios.yaml` e
  reiniciar resolve. É o preço de não deixar a senha em arquivo.
- **A sessão é um cookie só, sem revogação.** Não há como derrubar uma sessão
  roubada sem trocar o `segredo` do arquivo, o que desloga todo mundo. Para um
  admin só, é aceitável; com mais gente, deixa de ser.
- **`scrypt` depende do OpenSSL da imagem.** Medido no venv do checkout
  (Python 3.14.6, 27 ms). Se o `python:3.14-slim` não trouxer o algoritmo, a
  alternativa é `pbkdf2_hmac`, que está em qualquer build, e o formato do
  arquivo já guarda os parâmetros por hash.
- **Esquecer a rota `/login` no `app.py`.** O sintoma é um 404 só no
  recarregamento da tela de login, que passa no teste de navegação e no
  `npm run dev`. O teste de `test_web.py` cobre isso se a rota entrar na lista
  de rotas da SPA.
- **O `Secure` desligado por padrão.** Se o app for exposto atrás de TLS e
  ninguém ligar a variável, o cookie viaja em claro entre o proxy e o
  navegador. Fica no README, junto das outras variáveis.
- **O primeiro boot depois do merge muda o dia a dia de quem já usa o app:**
  a senha sai no log uma vez, e quem não olhou o log precisa apagar o
  `usuarios.yaml` e reiniciar para gerar outra.
