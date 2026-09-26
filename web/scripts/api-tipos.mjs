// Gera o web/src/api/schema.d.ts a partir do app.openapi(). O arquivo gerado
// e versionado: assim o build do front nao precisa de Python nem de rede.
import { execFileSync } from "node:child_process"
import { mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join, resolve } from "node:path"

const RAIZ = resolve(dirname(import.meta.filename), "../..")
const PYTHON = process.env.BGPGEN_PYTHON ?? join(RAIZ, ".venv/bin/python")
const DESTINO = process.argv[2] ?? join(RAIZ, "web/src/api/schema.d.ts")

const json = execFileSync(
  PYTHON,
  ["-c", "import json; from app.app import app; print(json.dumps(app.openapi()))"],
  { cwd: RAIZ, encoding: "utf8" },
)

const temp = join(mkdtempSync(join(tmpdir(), "bgpgen-")), "openapi.json")
writeFileSync(temp, json)

execFileSync(
  join(RAIZ, "web/node_modules/.bin/openapi-typescript"),
  [temp, "-o", DESTINO],
  { stdio: "inherit" },
)
