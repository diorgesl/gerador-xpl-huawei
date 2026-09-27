import { expect, test } from "@playwright/test"

test.describe("a copia do bloco", () => {
  // O out/ do e2e nasce vazio, e sem arquivo em out/ o painel esta no estado
  // "arquivo novo": o botao do painel nasce "salvar e copiar", e nao
  // "copiar". Gravar o peer 1 uma vez e recarregar e o que cria o estado de
  // repouso que os dois primeiros casos abaixo exercitam, em que copiar nao
  // grava nada (o terceiro vai no peer 3, e grava).
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
    // "end-filter" casa com qualquer bloco XPL, de qualquer peer: o que prova
    // que a copia e do bloco DESTE peer e o token dele
    expect(texto).toContain("end-filter")
    expect(texto).toContain("268127")
  })

  test("o botao volta ao rotulo normal depois de um segundo e meio", async ({ page }) => {
    await page.getByRole("button", { name: /^copiar$/ }).click()
    await expect(page.getByRole("button", { name: /copiado/ })).toBeVisible()
    await expect(page.getByRole("button", { name: /^copiar$/ })).toBeVisible({ timeout: 3000 })
  })

  test("salvar e copiar leva o bloco gravado, e nao o digitado", async ({ page, context, browserName }) => {
    // O caso que a spec do front deixou em aberto: o writeText acontece depois
    // da requisicao do salvar, e o WebKit poderia recusar. O plano previa o
    // socorro de dois cliques (salvar, trocar o botao para "copiar" e pedir o
    // segundo clique) para esse caso: medido, ele nao e preciso, e o socorro
    // nao entrou. O que este caso mede agora e o que cada navegador permite
    await context.grantPermissions(["clipboard-read", "clipboard-write"]).catch(() => {})
    await page.goto("/peers/3")
    await page.getByLabel("Descrição").fill(`medido em ${browserName}`)
    const botao = page.getByRole("button", { name: /salvar e copiar/i })
    await botao.click()

    await expect(page.getByText(/gravado em out\//)).toBeVisible()
    // O "copiado" e o app dizendo que o writeText passou depois da requisicao
    // do salvar, e e o que o WebKit prova aqui: medido em 2026-09-27, ele chega
    // em "copiado" como o Chromium. O localizador do clique nao serve para
    // isto, porque ele casa pelo rotulo antigo e o rotulo muda exatamente para
    // "copiado" (era o defeito deste caso)
    await expect(page.getByRole("button", { name: /copiado/ })).toBeVisible({ timeout: 3000 })

    // O que cada um consegue provar do CONTEUDO e diferente, e o caso diz qual:
    // o Chromium le a area de transferencia de volta; o WebKit recusa o
    // readText com NotAllowedError ("o clipboard-read nao existe no WebKit"),
    // entao la o conteudo e o do painel, e a area de transferencia em si fica
    // sem prova
    if (browserName === "webkit") {
      await expect(page.getByRole("tabpanel")).toContainText(`medido em ${browserName}`)
    } else {
      const texto = await page.evaluate(() => navigator.clipboard.readText())
      expect(texto).toContain(`medido em ${browserName}`)
    }
  })
})
