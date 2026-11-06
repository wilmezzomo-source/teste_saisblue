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
import os,time,io,json
from server import app,database,password,start_automation_worker
from waitress import serve
counter=0
def fake_sender(req,timeout):
 global counter
 counter+=1
 return io.BytesIO(json.dumps({'messages':[{'id':'fixture-out-'+str(counter)}]}).encode())
app.config['META_SENDER']=fake_sender
with database(app) as db:
 db.execute('INSERT INTO users VALUES(?,?,?,?,?,1,?)',('admin-test','admin@example.test','Admin de demonstração',password(os.environ['TEST_PASSWORD']),'admin',time.time()))
start_automation_worker(app)
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
        META_APP_SECRET: "ui-fixture-secret",
        META_VERIFY_TOKEN: "ui-fixture-verify",
        META_ACCESS_TOKEN: "ui-fixture-token",
        META_PHONE_NUMBER_ID: "ui-fixture-phone",
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
  await admin.locator("#release-version").filter({hasText:"2026.11.06.4"}).waitFor();
  assert.equal(await admin.locator("#new-contact").isHidden(), true);
  assert.equal(await admin.locator('.column[data-stage="Proposta enviada"]').count(),0);
  await admin.evaluate(() => document.fonts.load("400 14px Montserrat"));
  assert.equal(await admin.locator(".brand-asset img").evaluate(img => img.complete && img.naturalWidth > 0), true);
  assert.match(await admin.evaluate(() => requestKey()), /^[a-f0-9]{32}$/);
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
  await admin.locator("[name=state_picker]").selectOption("RS");
  await admin.locator("[name=city_id]").selectOption("4302105");
  await admin
    .locator("[name=instagram]")
    .fill("https://www.instagram.com/saisblue/");
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
  await member.locator("[name=stage]").selectOption("Em atendimento");
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
    () => document.querySelector("[name=stage]").value === "Em atendimento",
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
    .locator('.column[data-stage="Em atendimento"] .card')
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
  // The map groups clients in the same municipality and keeps unlocated leads visible.
  await admin.evaluate(async () => {
    await api("/api/simulate", {
      name: "Segundo cliente de Bento",
      body: "Mensagem de anúncio",
      phone: "5554999990001",
      city_id: "4302105",
      instagram: "@cliente_bento",
    });
    await api("/api/simulate", {
      name: "Cliente de São Paulo",
      body: "Mensagem de anúncio",
      phone: "5511999990002",
      city_id: "3550308",
    });
    await api("/api/simulate", {
      name: "Lead sem localização",
      phone: "5521999990003",
      body: "Vim do anúncio",
    });
  });
  const mapRequests=[];
  await member.route('https://tile.openstreetmap.org/**',async route=>{
    mapRequests.push(route.request().headers());
    await route.fulfill({status:403,body:'Blocked provider fixture'});
  });
  await member.reload();
  await member.locator("[data-view=map]").click();
  await member
    .locator("#map-count")
    .filter({ hasText: "3 lead(s) em 2 cidade(s)" })
    .waitFor();
  assert.equal(await member.locator(".lead-pin").count(), 2);
  assert.equal(mapRequests.length,0,'Default map must not depend on external tiles');
  await member.locator('.leaflet-control-layers').hover();
  await member.getByText('Ruas · OpenStreetMap',{exact:true}).click();
  await member.locator('#map-status').filter({hasText:'camada de ruas indisponível'}).waitFor();
  assert.ok(mapRequests.length>0);
  assert.ok(mapRequests.every(headers=>headers.referer===base+'/'),'Only the app origin should be sent as Referer');
  assert.equal(await member.locator('.lead-pin').count(),2,'Provider failure must preserve lead pins');
  await member.locator(".lead-pin").filter({ hasText: "2" }).click();
  await member
    .locator(".city-popup")
    .getByRole("button", { name: "Segundo cliente de Bento · Novo contato" })
    .waitFor();
  await member.locator("#map-state").selectOption("RS");
  await member
    .locator("#map-count")
    .filter({ hasText: "2 lead(s) em 1 cidade(s)" })
    .waitFor();
  assert.equal(await member.locator(".lead-pin").count(), 1);
  await member
    .getByRole("button", { name: "Lead sem localização Preencher cidade / UF" })
    .click();
  await member.locator(".location-warning").waitFor();
  await member.locator("[name=state_picker]").selectOption("RS");
  await member.locator("[name=city_id]").selectOption("4302105");
  await member.locator("#detail-form [name=instagram]").fill("@lead_mapeado");
  await member.getByRole("button", { name: "Salvar oportunidade" }).click();
  await member.getByText("Oportunidade atualizada.", { exact: true }).waitFor();
  assert.equal(await member.locator(".location-warning").count(), 0);
  await member.locator("#close-detail").click();
  await member.locator("#map-state").selectOption("");
  await member
    .locator("#map-count")
    .filter({ hasText: "4 lead(s) em 2 cidade(s)" })
    .waitFor();
  await member.screenshot({
    path: __dirname + "/preview-map.png",
    fullPage: true,
  });
  await member.setViewportSize({ width: 390, height: 844 });
  await member.screenshot({
    path: __dirname + "/preview-map-mobile.png",
    fullPage: true,
  });
  assert.equal(
    await member.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await member.setViewportSize({ width: 1440, height: 1000 });
  await member.locator("[data-view=reports]").click();
  await member.getByText("Distribuição no funil", { exact: true }).waitFor();
  await member.locator("[data-view=settings]").click();
  await member
    .getByRole("heading", { name: "Primeiro atendimento automático", exact: true })
    .waitFor();
  assert.equal(await member.locator("#automation-form").count(),0);
  if(await admin.locator('#detail-dialog').isVisible()) await admin.locator('#close-detail').click();
  await admin.locator("[data-view=settings]").click();
  await admin.locator('#automation-form [name=enabled]').check();
  const accounts=await admin.evaluate(async()=> (await api('/api/team')).users);
  const seller=accounts.find(u=>u.email==='vendas@example.test');
  await admin.locator('#automation-form [name=chai]').selectOption('admin-test');
  await admin.locator('#automation-form [name=grasi]').selectOption(seller.id);
  await admin.getByRole('button',{name:'Salvar primeiro atendimento'}).click();
  await admin.getByRole('status').filter({hasText:'Primeiro atendimento salvo.'}).waitFor();
  await admin.screenshot({path:__dirname+'/preview-automation.png',fullPage:true});
  let serial=0;
  async function whatsapp(body,ad=false,number='5554999997444') {
    const message={id:'ui-qualification-'+(++serial),from:number,type:'text',text:{body},timestamp:String(Date.now()/1000)};
    if(ad) message.referral={source_type:'ad',source_id:'ui-ad-fixture'};
    const raw=JSON.stringify({entry:[{changes:[{value:{metadata:{phone_number_id:'ui-fixture-phone'},contacts:[{wa_id:number,profile:{name:'Lead qualificado UI'}}],messages:[message]}}]}]});
    const signature='sha256='+crypto.createHmac('sha256','ui-fixture-secret').update(raw).digest('hex');
    const response=await fetch(base+'/webhooks/whatsapp',{method:'POST',headers:{'Content-Type':'application/json','X-Hub-Signature-256':signature},body:raw});
    assert.equal(response.status,200);
  }
  await whatsapp('Mensagem comum',false,'5554999997555');
  await whatsapp('Vim do anúncio',true);
  await admin.waitForFunction(async()=>{
    const data=await fetch('/api/contacts').then(r=>r.json());
    return data.contacts.find(c=>c.phone==='5554999997444')?.messages.some(m=>m.automation && m.status==='accepted' && m.body.includes('assistente virtual'));
  });
  await whatsapp('Revenda');
  await admin.waitForFunction(async()=>{
    const data=await fetch('/api/contacts').then(r=>r.json());
    return data.contacts.find(c=>c.phone==='5554999997444')?.messages.some(m=>m.automation && m.status==='accepted' && m.body.includes('Qual é sua cidade'));
  });
  await whatsapp('Guaporé/RS');
  await admin.waitForFunction(async()=>{
    const data=await fetch('/api/contacts').then(r=>r.json());
    return data.contacts.find(c=>c.phone==='5554999997444')?.messages.some(m=>m.automation && m.status==='accepted' && m.body.includes('Registrei seu perfil'));
  });
  await admin.locator('[data-view=pipeline]').click();
  await admin.locator('.card').filter({hasText:'Lead qualificado UI'}).waitFor({timeout:15000});
  await admin.locator('#profile-filter').selectOption('Revenda');
  assert.equal(await admin.locator('.card').count(),1);
  assert.equal(await admin.locator('.profile-tag.revenda').count(),1);
  await admin.locator('.card').click();
  assert.equal(await admin.locator('#detail-form [name=lead_profile]').inputValue(),'Revenda');
  assert.equal(await admin.locator('#detail-form [name=city_id]').inputValue(),'4309407');
  assert.equal(await admin.locator('#detail-form [name=owner]').inputValue(),'Admin de demonstração');
  await admin.getByRole('button',{name:'Assumir atendimento',exact:true}).click();
  await admin.getByRole('status').filter({hasText:'Assistente pausado'}).waitFor();
  await admin.locator('#close-detail').click();
  await admin.locator('[data-view=reports]').click();
  await admin.getByRole('heading',{name:'Resultados por perfil'}).waitFor();
  assert.equal(await admin.locator('[data-profile-summary]').count(),1);
  await admin.locator('#profile-filter').selectOption('');
  assert.equal(await admin.locator('[data-profile-summary]').count(),4);
  await admin.screenshot({path:__dirname+'/preview-profiles.png',fullPage:true});
  await admin.locator('#profile-filter').selectOption('Lojista');
  await admin.locator('[data-view=map]').click();
  await admin.locator('#map-count').filter({hasText:'0 lead(s)'}).waitFor();
  await admin.locator('#profile-filter').selectOption('');
  const stored=await admin.evaluate(async()=> (await api('/api/contacts')).contacts);
  assert.equal(stored.some(c=>c.phone==='5554999997555'),false);
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
    "UI OK: equipe, conflitos, mapa, captura de anúncios, qualificação, distribuição, tags, filtros, relatórios e mobile.",
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
