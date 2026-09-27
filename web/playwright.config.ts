import { defineConfig, devices } from "@playwright/test"
import { fileURLToPath } from "node:url"

const repo = fileURLToPath(new URL("..", import.meta.url))
const temp = fileURLToPath(new URL("./e2e/.tmp", import.meta.url))
const PORTA = 8099

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  // Um worker so: os dois arquivos atacam o MESMO uvicorn e o mesmo
  // peers.yaml, e o peer 1 e gravado pelo copiar.spec e editado pelo
  // fluxos.spec. Em paralelo os dois disputam o registro e o arquivo em out/,
  // e o caso do "salvar e copiar" ve o bloco do outro.
  workers: 1,
  use: { baseURL: `http://127.0.0.1:${PORTA}`, trace: "retain-on-failure" },
  webServer: {
    // O uvicorn roda de dentro da copia, e serve o build de verdade: o e2e
    // exercita o FastAPI servindo a SPA, e nao o Vite.
    //
    // A copia sai aqui, no proprio comando, e nao num `globalSetup` da config:
    // medido nesta versao (1.63), o webServer sobe antes do globalSetup, e o
    // `cd` da copia falhava com "No such file or directory" antes de o
    // globalSetup ter chance de rodar.
    command: `node ${repo}web/e2e/global-setup.ts && cd ${temp} && BGPGEN_WEB=${repo}web/dist ${repo}.venv/bin/python -m uvicorn app.app:app --port ${PORTA}`,
    url: `http://127.0.0.1:${PORTA}/api/plano`,
    reuseExistingServer: false,
    stdout: "pipe",
  },
  projects: [
    // o chromium roda tudo, incluindo a copia; o webkit roda so a copia, que e
    // onde o Safari pode recusar o writeText depois da requisicao do salvar
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] }, testMatch: /copiar\.spec\.ts/ },
  ],
})
