import { expect, test } from "@playwright/test"

const APELIDO = `E2E${Date.now().toString().slice(-6)}`

// O prefixo de cada peer novo e um so por fluxo: o validate recusa prefixo de
// downstream que sobrepoe o de outro, entao dois fluxos no mesmo /24 fariam o
// segundo esbarrar no peer que o primeiro gravou.
const PREFIXO_CRIAR = "203.0.113.0/24"
const PREFIXO_ERRAR = "192.0.2.0/24"
const PREFIXO_DUPLICAR = "198.18.0.0/24"

test("criar um peer do zero", async ({ page }) => {
  await page.goto("/peers")
  await page.getByRole("button", { name: /novo/ }).click()
  await page.getByRole("menuitem", { name: /^peer cliente$/ }).click()

  await expect(page).toHaveURL(/\/peers\/novo\?tipo=cliente/)
  await page.getByLabel("Apelido").fill(APELIDO)
  await page.getByLabel("Nome").fill(`Cliente ${APELIDO}`)
  await page.getByLabel("ASN").fill("64500")
  // Classe e POP sao campos do cliente e nenhum dos dois nasce preenchido no
  // peer novo: sem eles o salvar recusa com "cliente exige uma classe"
  await page.getByLabel("Classe").click()
  await page.getByRole("option", { name: /^residencial/ }).click()
  await page.getByLabel("POP").fill("2001")
  // o rotulo da lista carrega a contagem ("IPv4 (0)"): o /^IPv4 \(/ acha o
  // campo com qualquer contagem, e nao derruba o fluxo quando a linha muda
  await page.getByLabel(/^IPv4 \(/).fill(PREFIXO_CRIAR)
  await page.getByLabel("IPv4 local").fill("198.51.100.30")
  await page.getByLabel("IPv4 remoto").fill("198.51.100.31")

  // a previa aparece sozinha antes de salvar, e o filtro do import leva o
  // token do peer, que aqui e o apelido
  await expect(page.getByRole("tabpanel")).toContainText(`CUST-${APELIDO}-IMPORT-V4`)

  await page.getByRole("button", { name: /^salvar$/ }).click()
  await expect(page).toHaveURL(/\/peers\/\d+$/)
  await expect(page.getByText(new RegExp(`gravado em out/${APELIDO}`))).toBeVisible()
  await expect(page.getByRole("link", { name: new RegExp(APELIDO) })).toBeVisible()
})

test("errar e corrigir pelo resumo", async ({ page }) => {
  // O endereco remoto do peer 1 do cadastro do e2e: o validate recusa duas
  // sessoes no mesmo endereco. O ASN 268127 tambem e do peer 1, mas repeti-lo
  // nao e erro: a identidade do peer e o token (o apelido, quando ele tem um),
  // e o peer 1 se chama ACME. O dado duplicado que o app recusa aqui e o
  // endereco.
  await page.goto("/peers/novo?tipo=cliente")
  await page.getByLabel("Nome").fill("Cliente repetido")
  await page.getByLabel("ASN").fill("268127")
  await page.getByLabel("Classe").click()
  await page.getByRole("option", { name: /^residencial/ }).click()
  await page.getByLabel("POP").fill("2001")
  await page.getByLabel(/^IPv4 \(/).fill(PREFIXO_ERRAR)
  await page.getByLabel("IPv4 local").fill("198.51.100.40")
  await page.getByLabel("IPv4 remoto").fill("198.51.100.2")
  await page.getByRole("button", { name: /^salvar$/ }).click()

  const resumo = page.getByRole("alert").first()
  await expect(resumo).toContainText("endereco ja usado pelo peer")

  // o link do resumo rola ate o campo e poe o foco nele
  await resumo.getByRole("button", { name: /endereco ja usado/ }).click()
  await expect(page.getByLabel("IPv4 remoto")).toBeFocused()

  await page.getByLabel("IPv4 remoto").fill("198.51.100.41")
  await page.getByRole("button", { name: /^salvar$/ }).click()
  await expect(page).toHaveURL(/\/peers\/\d+$/)
})

test("duplicar e ajustar", async ({ page }) => {
  await page.goto("/peers/1")
  await page.getByRole("button", { name: /duplicar/ }).click()

  await expect(page).toHaveURL(/\/peers\/novo\?de=1/)
  await expect(page.getByText(/cópia de ACME/)).toBeVisible()
  // a copia vem com o que o salvar recusaria enquanto nao for ajustado: o
  // token (o apelido), o endereco remoto e o prefixo do peer 1
  await expect(page.getByRole("alert").first()).toContainText("ASN ja usado")

  await page.getByLabel("Apelido").fill(`${APELIDO}2`)
  await page.getByLabel("ASN").fill("64502")
  await page.getByLabel(/^IPv4 \(/).fill(PREFIXO_DUPLICAR)
  await page.getByLabel("IPv4 remoto").fill("198.51.100.99")
  await page.getByRole("button", { name: /^salvar$/ }).click()
  await expect(page).toHaveURL(/\/peers\/\d+$/)
})

test("editar e usar o salvar e copiar", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"])

  // O out/ do e2e nasce vazio, e sem arquivo em out/ o painel esta no estado
  // "arquivo novo": o botao nasce "salvar e copiar", e nao "copiar". Gravar
  // uma vez e recarregar cria o estado de repouso, que e o que este fluxo
  // compara com o de depois da edicao
  await page.goto("/peers/1")
  await page.getByRole("button", { name: /^salvar$/ }).click()
  await expect(page.getByText(/gravado em out\//)).toBeVisible()
  await page.reload()

  // sem edicao, o botao e copiar
  await expect(page.getByRole("button", { name: /^copiar$/ })).toBeVisible()

  await page.getByLabel("Descrição").fill("CLIENTE-AS268127 editado")
  await expect(page.getByRole("button", { name: /salvar e copiar/ })).toBeVisible()
  await page.getByRole("button", { name: /salvar e copiar/ }).click()

  // o salvar aconteceu de verdade: o toast so sai depois do 200 da API
  await expect(page.getByText(/gravado em out\//)).toBeVisible()
  await expect(page.getByRole("button", { name: /copiado/ })).toBeVisible()
  const area = await page.evaluate(() => navigator.clipboard.readText())
  // o que chegou na area de transferencia e o bloco do registro GRAVADO: o
  // filtro leva o token do peer (o apelido ACME) e a descricao recem-salva
  expect(area).toContain("xpl route-filter CUST-ACME-IMPORT-V4")
  expect(area).toContain("description CLIENTE-AS268127 editado")
  expect(area).toContain("end-filter")
})

test("trocar de registro com alteracao nao salva", async ({ page }) => {
  // A rota por id usa o `TelaDoPeer` com chave: sem ela o React Router reusa o
  // elemento, o formulario fica com os valores do registro ANTERIOR e o salvar
  // grava eles no registro novo. A chave tem teste de unidade, mas a LIGACAO da
  // rota nao tem teste nenhum no front, e e aqui que ela fica presa
  await page.goto("/peers/1")
  await page.getByLabel("ASN").fill("64500")
  await page.locator('a[href="/peers/3"]').click()
  await page.getByRole("button", { name: /sair sem salvar/i }).click()

  await expect(page).toHaveURL(/\/peers\/3/)
  await expect(page.getByLabel("ASN")).not.toHaveValue("64500")
})

test("editar grupo e tentar excluir com membro", async ({ page }) => {
  await page.goto("/grupos/2")
  // o exact e porque a barra lateral tem o mesmo peer no link "CDN-ALFA
  // parceiro": sem ele o localizador resolve para dois elementos
  await expect(page.getByRole("link", { name: "CDN-ALFA", exact: true })).toBeVisible()

  await page.getByLabel("Nome").fill("PARCEIROS")
  await page.getByRole("button", { name: /mais ações/ }).click()
  await page.getByRole("menuitem", { name: /excluir/ }).click()

  await expect(page.getByRole("dialog")).toContainText("PARCEIROS")
  await page.getByRole("button", { name: /^excluir$/ }).last().click()
  await expect(page.getByText(/ainda tem peers membros: CDN-ALFA/)).toBeVisible()
})

test("a lista convida a escolher quando nada esta aberto", async ({ page }) => {
  await page.goto("/peers")
  await expect(page.getByText(/escolha um peer ou crie um/)).toBeVisible()
  await page.goto("/grupos")
  await expect(page.getByText(/escolha um grupo ou crie um/)).toBeVisible()
})

test("a raiz cai na lista", async ({ page }) => {
  // o unico caso que exercita o 307 do uvicorn com um navegador de verdade: o
  // webServer do Playwright sobe o uvicorn servindo o web/dist
  await page.goto("/")
  await expect(page).toHaveURL(/\/peers$/)
  await expect(page.getByText(/escolha um peer ou crie um/)).toBeVisible()
})
