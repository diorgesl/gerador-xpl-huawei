import js from "@eslint/js"
import globals from "globals"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import tseslint from "typescript-eslint"
import { defineConfig, globalIgnores } from "eslint/config"

// o template do Vite escreve este arquivo; o gerador de hoje entrou com o
// oxlint no lugar, entao ele nasce aqui com as mesmas regras.
export default defineConfig([
  globalIgnores(["dist"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
    ],
    plugins: {
      "react-refresh": reactRefresh,
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
    },
  },
  {
    // Os globais de Node para o e2e. Hoje este bloco nao confere nada: o
    // typescript-eslint desliga o no-undef nos arquivos TS, e ele e o unico
    // rule que olharia para globais (medido com --print-config). Fica como
    // intencao declarada, e nao como se estivesse pegando alguma coisa.
    // Detalhe de como o flat config resolve: os globais se MESCLAM com os do
    // bloco anterior, entao o browser nao sai daqui
    files: ["playwright.config.ts", "e2e/**/*.ts"],
    languageOptions: { globals: globals.node },
  },
  {
    // as regras recomendadas entram junto dos globais: so os globais nao
    // conferem nada, porque nenhuma regra olha para eles
    files: ["scripts/**/*.mjs"],
    extends: [js.configs.recommended],
    // sem `ecmaVersion`: o padrao do flat config ja e o mais novo, e fixar um
    // numero aqui so rebaixa o parser para os scripts que vierem depois
    languageOptions: { globals: globals.node },
  },
  {
    // os componentes do shadcn saem do CLI com o helper do cva exportado ao
    // lado do componente: e codigo gerado, e o aviso nao tem o que consertar
    files: ["src/components/ui/**/*.tsx"],
    rules: { "react-refresh/only-export-components": "off" },
  },
])
