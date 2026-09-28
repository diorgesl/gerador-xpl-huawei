import { cpSync, mkdirSync, rmSync } from "node:fs"
import { fileURLToPath } from "node:url"

/**
 * A copia da arvore de que o e2e roda.
 *
 * O app resolve a pasta peers/ e o out/ a partir da raiz do projeto, por
 * Path(__file__).parent.parent. A unica forma de apontar o e2e para um cadastro
 * temporario sem mexer no app e rodar de uma copia da arvore: aqui ela nasce em
 * web/e2e/.tmp, com o app/, os templates/ e o tenant do e2e.
 *
 * Quem chama e o comando do webServer, e nao o `globalSetup` do Playwright:
 * medido nesta versao (1.63), o plugin do webServer sobe ANTES das tarefas de
 * globalSetup (createPluginSetupTasks vem antes de globalSetups em
 * createGlobalSetupTasks), e o `cd` do uvicorn precisa da copia pronta. Um
 * globalSetup aqui rodaria depois do uvicorn, e o rmSync apagaria o .tmp
 * debaixo do servidor que ja estivesse de pe.
 */
const repo = fileURLToPath(new URL("../..", import.meta.url))
const temp = fileURLToPath(new URL("./.tmp", import.meta.url))

rmSync(temp, { recursive: true, force: true })
mkdirSync(temp, { recursive: true })

cpSync(`${repo}/app`, `${temp}/app`, {
  recursive: true,
  filter: (origem) => !origem.includes("__pycache__"),
})
cpSync(`${repo}/templates`, `${temp}/templates`, { recursive: true })
// o cadastro do e2e vai para a pasta de tenants, com o nome do ASN que ele
// declara dentro: e o nome do arquivo que manda, e um `peers.yaml` na raiz
// seria migrado pelo boot, com .bak e log, a cada subida do uvicorn
mkdirSync(`${temp}/peers`, { recursive: true })
cpSync(`${repo}/web/e2e/peers/64512.yaml`, `${temp}/peers/64512.yaml`)
mkdirSync(`${temp}/out`, { recursive: true })
