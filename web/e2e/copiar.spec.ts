import { expect, test } from "@playwright/test"

test.describe("a copia do bloco", () => {
  // O out/ do e2e nasce vazio, e sem arquivo em out/ o painel esta no estado
  // "arquivo novo": o botao do painel nasce "salvar e copiar", e nao
  // "copiar". Gravar o peer 1 uma vez e recarregar e o que cria o estado de
  // repouso que os dois casos abaixo exercitam, em que copiar nao grava nada.
  test.beforeEach(async ({ page }) => {
    await page.goto("/peers/1")
    await page.getByRole("button", { name: /^salvar$/ }).click()
    await expect(page.getByText(/gravado em out\//)).toBeVisible()
    await page.reload()
    await expect(page.getByRole("button", { name: /^copiar$/ })).toBeVisible()
  })

  test("em origem segura vai pelo clipboard", async ({ page, context, browserName }) => {
    test.skip(browserName === "webkit", "o webkit do Playwright nao expoe clipboard-read")
    await context.grantPermissions(["clipboard-read", "clipboard-write"])
    await page.getByRole("button", { name: /^copiar$/ }).click()
    await expect(page.getByRole("button", { name: /copiado/ })).toBeVisible()
    const texto = await page.evaluate(() => navigator.clipboard.readText())
    expect(texto).toContain("end-filter")
  })

  test("o botao volta ao rotulo normal depois de um segundo e meio", async ({ page }) => {
    await page.getByRole("button", { name: /^copiar$/ }).click()
    await expect(page.getByRole("button", { name: /copiado/ })).toBeVisible()
    await expect(page.getByRole("button", { name: /^copiar$/ })).toBeVisible({ timeout: 3000 })
  })
})
