# O front e compilado num estagio proprio: a imagem final nao tem node nem
# node_modules, so o dist.
FROM node:22-slim AS front

WORKDIR /front

# o lock entra sozinho primeiro: mexer no codigo do front nao refaz o npm ci
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# bgpgen num container. O motivo de existir e o bgpq4: o app chama o binario
# pelo PATH (prefixes.py) e ele nao vem instalado no macOS. Tem no brew, que
# hoje traz a 1.16; esta imagem traz a 1.12 do Debian. O ganho da imagem e o
# ambiente fechado, com python e bgpq4 presos na mesma versao, sem mexer no
# que ja esta na maquina.
FROM python:3.14-slim

# O bgpq4 sai do repositorio da distro. E a unica dependencia que nao esta
# no requirements.txt, porque nao e pacote de python.
RUN apt-get update \
 && apt-get install -y --no-install-recommends bgpq4 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# o app importa "from app import ...", entao a raiz do projeto precisa estar
# no sys.path mesmo quando o comando roda de outro diretorio
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# o requirements entra sozinho primeiro: mexer no codigo nao refaz o pip
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# O build sai do estagio do node e fica FORA de /app de proposito: o
# compose.yaml monta o checkout inteiro em /app, e qualquer coisa que a imagem
# pusesse ali seria escondida pelo bind mount.
COPY --from=front /front/dist /srv/web
ENV BGPGEN_WEB=/srv/web

# a imagem cria o out/ e o usuario, mas os dois sao substituidos quando o
# compose monta o checkout por cima. Ficam aqui para o "docker run" puro
# funcionar sem preparo nenhum.
RUN mkdir -p /app/out \
 && useradd --create-home --uid 1000 bgpgen \
 && chown -R bgpgen:bgpgen /app
USER bgpgen

EXPOSE 8000

# sem curl na imagem slim: o proprio python responde se a tela esta de pe. O /
# responde 307 para /peers desde o corte das telas HTML, e o urlopen segue o
# redirect sozinho: quem devolve o 200 e o index.html do build
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
 CMD python -c "import sys,urllib.request; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3).status == 200 else 1)"

CMD ["python", "-m", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]
