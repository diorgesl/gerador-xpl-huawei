import { expect, test } from "@playwright/test"
import { SENHA } from "./senha"

// sem o cookie do setup: este arquivo testa justamente a entrada
test.use({ storageState: { cookies: [], origins: [] } })

test("a senha errada nao entra e a certa entra", async ({ page }) => {
  await page.goto("/peers")
  await expect(page).toHaveURL(/\/login/)

  await page.getByLabel("Senha").fill("chute")
  await page.getByRole("button", { name: /^entrar$/ }).click()
  await expect(page.getByRole("alert")).toContainText("usuario ou senha invalidos")
  await expect(page).toHaveURL(/\/login/)

  await page.getByLabel("Senha").fill(SENHA)
  await page.getByRole("button", { name: /^entrar$/ }).click()
  await expect(page).toHaveURL(/\/peers/)
})

test("o sair volta para a tela de login", async ({ page }) => {
  await page.goto("/login")
  await page.getByLabel("Senha").fill(SENHA)
  await page.getByRole("button", { name: /^entrar$/ }).click()
  await expect(page).toHaveURL(/\/peers/)

  await page.getByRole("button", { name: /^sair$/ }).click()

  await expect(page).toHaveURL(/\/login/)
  await page.goto("/peers")
  await expect(page).toHaveURL(/\/login/)
})
