import { fileURLToPath } from "node:url"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    // o uvicorn da 8000 e o dono da API e do base.txt: em desenvolvimento o
    // front fala com o mesmo caminho relativo que usa em producao
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/base.txt": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/teste/setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
})
