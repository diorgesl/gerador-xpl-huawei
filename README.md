# bgpgen

Gera o bloco XPL de uma sessão BGP do AS64512 a partir de um formulário, mais
um bloco base com os sets e filtros que todas as sessões compartilham.

## O que é

A tela lista os peers e traz o formulário ao lado. Preenchido o formulário, o
app escreve o bloco daquela sessão em `out/<token>-<tipo>.txt`, sobrescrevendo
só esse arquivo. Gerar um peer não toca na saída dos outros. O bloco base, que
é igual para todos, a tela serve em `GET /base.txt`.

Além da tela, o app serve uma API JSON em `/api`, que a tela nova (em
construção, ver `docs/superpowers/specs/2026-09-26-front-spa-design.md`) vai
consumir. As rotas usam o mesmo formulário, a mesma validação e o mesmo render
da tela, e a documentação interativa fica em `/docs`. A prévia
(`POST /api/peers/previa`) monta o bloco sem gravar nada.

O estado é o `peers.yaml`, o cadastro dos peers. O que está em `out/` é saída, e
está no `.gitignore`.

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
docker compose up --build
```

A tela fica em http://127.0.0.1:8765/. O `compose.yaml` monta o checkout em
`/app`, então o `peers.yaml` e o `out/` são os do repositório e editar template
vale na hora. Sem essa linha de `volumes:`, a imagem roda sozinha com o que foi
copiado no build.

A imagem é o `python:3.14-slim` mais o `bgpq4` 1.12 do repositório Debian. O
`bgpq4` do brew está na 1.16, então as duas rotas não dão a mesma versão do
binário.

Suíte: `.venv/bin/python -m pytest`, ou
`docker compose run --rm bgpgen python -m pytest` para rodar dentro do container.

## Ordem de colagem no F1A

1. **O bloco base, uma vez, antes de tudo.** A tela serve em `GET /base.txt`,
   no botão "baixar bloco base". O corpo é montado na hora do download, então o
   que o navegador salva é sempre o que o `plan.py` diz agora: não há arquivo em
   `out/` guardando uma versão antiga, nem aviso de desatualizado para conferir.
   Salve onde quiser e cole antes dos blocos de peer.
2. **O bloco de cada peer**, na ordem que quiser: `out/<token>-cliente.txt`,
   `out/<token>-upstream.txt`, `out/<token>-ix.txt`, `out/<token>-pni.txt`.
3. **A `CL-PEER-<T>` do quadro "ao criar o peer"**, na primeira vez que aquela
   sessão subir, e de novo sempre que a lista mudar. Vale para cliente e
   upstream: são os dois tipos que ganham community própria de sessão. O IX não
   precisa (o route server repassa o mesmo path a todos) e o PNI também não, e
   para esses dois o quadro nem aparece. Os membros saem do campo "CL-PEER, uma
   por linha" do formulário, então re-colar o quadro troca o conteúdo pelo que
   está no cadastro; reaplicar o bloco do peer mexe só nos filtros e não tem
   como zerar o que está lá dentro.
4. **O bloco dos prefixos do próprio AS**, se houver: `out/blocos.txt`, escrito
   no salvar da seção de blocos. Ele traz as estáticas de ancoragem, os
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
