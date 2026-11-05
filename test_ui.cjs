const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "saisblue-ui-"));
const secret = crypto.randomBytes(24).toString("hex");
const base = "http://127.0.0.1:3001";
let server, browser;
async function login(page, email, password) {
  await page.goto(base + "/login");
  await page.locator("[name=email]").fill(email);
  await page.locator("[name=password]").fill(password);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await page.locator("body[data-auth=ready]").waitFor();
}
(async () => {
  server = spawn(
    path.join(__dirname, ".venv/bin/python"),
    [
      "-c",
      `
import os,time
from server import app,database,password
from waitress import serve
with database(app) as db:
 db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)',('admin-test','admin@example.test','Admin de demonstração',password(os.environ['TEST_PASSWORD']),'admin',time.time()))
serve(app,host='127.0.0.1',port=3001,threads=4)
`,
    ],
    {
      cwd: __dirname,
      env: {
        ...process.env,
        CRM_DB: path.join(temp, "crm.db"),
        TEST_PASSWORD: secret,
        APP_ENV: "development",
        APP_URL: base,
        ALLOW_SIMULATION: "1",
        META_APP_SECRET: "",
        META_ACCESS_TOKEN: "",
        META_PHONE_NUMBER_ID: "",
      },
      stdio: ["ignore", "ignore", "pipe"],
    },
  );
  server.stderr.on("data", (d) => process.stderr.write(d));
  for (let i = 0; i < 80; i++) {
    try {
      if ((await fetch(base + "/healthz")).ok) break;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
    args: ["--no-sandbox"],
  });
  const a = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
    }),
    b = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const admin = await a.newPage(),
    member = await b.newPage();
  const errors = [];
  for (const p of [admin, member])
    p.on("pageerror", (e) => errors.push(e.message));
  await member.goto(base + "/");
  await member.waitForURL("**/login");
  await login(admin, "admin@example.test", secret);
  await admin.locator("[data-view=team]").click();
  await admin.locator("#invite-form [name=email]").fill("vendas@example.test");
  await admin.getByRole("button", { name: "Gerar convite" }).click();
  await admin.locator("#invite-result:not([hidden])").waitFor();
  const invite = await admin.locator("#invite-link").inputValue();
  await member.goto(invite);
  await member.locator("[name=name]").fill("Vendedora de demonstração");
  await member.locator("[name=password]").fill(secret);
  await member.getByRole("button", { name: "Ativar meu acesso" }).click();
  await member.locator("body[data-auth=ready]").waitFor();
  await admin.locator("[data-view=pipeline]").click();
  await admin.getByRole("button", { name: "Simular lead do anúncio" }).click();
  await admin.locator("[name=name]").fill("Cliente de demonstração");
  await admin.locator("[name=phone]").fill("5511999991234");
  await admin
    .locator("[name=body]")
    .fill("Olá, vi o anúncio da Sais Blue. Quero saber mais!");
  await admin.getByRole("button", { name: "Adicionar ao CRM" }).click();
  await admin
    .locator(".card")
    .filter({ hasText: "Cliente de demonstração" })
    .click();
  await member
    .locator(".card")
    .filter({ hasText: "Cliente de demonstração" })
    .waitFor({ timeout: 15000 });
  await member
    .locator(".card")
    .filter({ hasText: "Cliente de demonstração" })
    .click();
  await member.locator("[name=stage]").selectOption("Proposta enviada");
  await member.locator("[name=value]").fill("2500");
  await member.getByRole("button", { name: "Salvar oportunidade" }).click();
  await member.getByText("Oportunidade atualizada.", { exact: true }).waitFor();
  // Admin's old open form must not overwrite the member's update.
  await admin.locator("[name=stage]").selectOption("Negociação");
  await admin.getByRole("button", { name: "Salvar oportunidade" }).click();
  await admin
    .getByRole("status")
    .filter({ hasText: "atualizado por outra pessoa" })
    .waitFor();
  await admin.getByRole("button", { name: "Recarregar card" }).click();
  await admin.waitForFunction(
    () => document.querySelector("[name=stage]").value === "Proposta enviada",
  );
  await member
    .locator("#note-form [name=body]")
    .fill("Demonstração: retornar ao cliente.");
  await member.getByRole("button", { name: "Adicionar nota" }).click();
  await member
    .locator(".message.note")
    .filter({ hasText: "Demonstração: retornar" })
    .waitFor();
  await member
    .locator(".activity")
    .getByText("Vendedora de demonstração", { exact: true })
    .first()
    .waitFor();
  await member.screenshot({
    path: __dirname + "/preview-card.png",
    fullPage: true,
  });
  await member.locator("#close-detail").click();
  await member.reload();
  await member
    .locator('.column[data-stage="Proposta enviada"] .card')
    .waitFor();
  await member.screenshot({ path: __dirname + "/preview.png", fullPage: true });
  await member.locator("[data-view=team]").click();
  await member
    .getByText("Você pode editar qualquer card.", { exact: true })
    .waitFor();
  assert.equal(await member.locator("#invite-form").count(), 0);
  await member.locator("[data-view=contacts]").click();
  await member
    .getByRole("cell", { name: "Cliente de demonstração", exact: true })
    .waitFor();
  await member.locator("[data-view=inbox]").click();
  await member.locator(".inbox-item").first().waitFor();
  await member.locator("[data-view=reports]").click();
  await member.getByText("Distribuição no funil", { exact: true }).waitFor();
  await member.locator("[data-view=settings]").click();
  await member
    .getByText("Aguardando conexão da conta Meta", { exact: true })
    .waitFor();
  await member.setViewportSize({ width: 390, height: 844 });
  await member.locator("[data-view=pipeline]").click();
  await member.screenshot({
    path: __dirname + "/preview-mobile.png",
    fullPage: true,
  });
  assert.equal(
    await member.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await member.getByRole("button", { name: "Sair", exact: true }).click();
  await member.waitForURL("**/login");
  await member.screenshot({
    path: __dirname + "/preview-login.png",
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  console.log(
    "UI OK: dois usuários, convite, edição compartilhada, conflito, histórico, notas, persistência, logout e mobile.",
  );
})()
  .catch((e) => {
    console.error(e);
    process.exitCode = 1;
  })
  .finally(async () => {
    await browser?.close();
    server?.kill();
    fs.rmSync(temp, { recursive: true, force: true });
  });
