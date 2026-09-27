import { expect, test as setup } from "@playwright/test"
import { fileURLToPath } from "node:url"
import { SENHA } from "./senha"

const ARQUIVO = fileURLToPath(new URL("./.tmp/sessao.json", import.meta.url))

/**
 * O login de uma vez so, guardado no storageState.
 *
 * Ele e um projeto, e nao um globalSetup, porque o globalSetup do Playwright
 * roda depois do webServer nesta versao: na hora dele nao ha servidor para
 * responder o POST... e aqui ha. O cookie e httpOnly, e o storageState o
 * guarda do mesmo jeito.
 */
setup("entra e guarda a sessao", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("Senha").fill(SENHA)
  await page.getByRole("button", { name: /^entrar$/ }).click()
  await expect(page).toHaveURL(/\/peers/)
  await page.context().storageState({ path: ARQUIVO })
})
