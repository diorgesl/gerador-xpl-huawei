// Gera de novo num arquivo temporario e falha se o versionado estiver
// diferente: e o que impede o front de compilar contra um schema velho.
import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join, resolve } from "node:path"

const RAIZ = resolve(dirname(import.meta.filename), "..")
const VERSIONADO = join(RAIZ, "src/api/schema.d.ts")
const temp = join(mkdtempSync(join(tmpdir(), "bgpgen-")), "schema.d.ts")

execFileSync(process.execPath, [join(RAIZ, "scripts/api-tipos.mjs"), temp], { stdio: "inherit" })

const a = readFileSync(VERSIONADO, "utf8")
const b = readFileSync(temp, "utf8")
if (a !== b) {
  console.error("schema.d.ts esta diferente do app.openapi(): rode npm run api:tipos")
  process.exit(1)
}
console.log("schema.d.ts bate com o app.openapi()")
