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
  await member.addInitScript(()=>{
    window.__alertToneStarts=0;
    if(window.OscillatorNode) {
      const original=OscillatorNode.prototype.start;
      OscillatorNode.prototype.start=function(...args){window.__alertToneStarts++;return original.apply(this,args);};
    }
  });
  await member.goto(base + "/");
  await member.waitForURL(url=>url.pathname==="/login");
  await login(admin, "admin@example.test", secret);
  await admin.locator("#release-version").filter({hasText:"2026.11.09.5"}).waitFor();
  assert.equal(await admin.locator("#new-contact").isVisible(), true);
  const appManifest=await admin.evaluate(async()=>(await fetch('/manifest.webmanifest')).json());
  assert.equal(appManifest.display,'standalone');
  assert.equal(appManifest.scope,'/');
  await admin.evaluate(()=>navigator.serviceWorker.ready);
  const publicCache=await admin.evaluate(async()=>{
    const cache=await caches.open('saisblue-public-v1');
    await fetch('/api/contacts');
    return (await cache.keys()).map(r=>new URL(r.url).pathname).sort();
  });
  assert.deepEqual(publicCache,['/brand/app-icon.png','/offline.html']);

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
  assert.equal(await member.locator('#owner-filter').isHidden(),true);
  assert.equal(await member.locator('#trash-nav').isHidden(),true);
  await member.getByRole('button',{name:'Avisos de oportunidades',exact:true}).click();
  await member.getByRole('button',{name:'Ativar avisos com som',exact:true}).click();
  await member.getByRole('status').filter({hasText:'Avisos com som ativados.'}).waitFor();
  const initialTones=await member.evaluate(()=>window.__alertToneStarts);
  assert.equal(initialTones,2);
  await member.getByRole('button',{name:'Fechar avisos',exact:true}).click();
  await admin.locator("[data-view=pipeline]").click();
  assert.equal(await admin.locator('#owner-filter').isVisible(),true);
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
  assert.equal((await member.evaluate(async()=> (await api('/api/contacts')).contacts)).length,0);
  await admin.evaluate(async()=>{
    const row=(await api('/api/contacts')).contacts.find(c=>c.name==='Cliente de demonstração');
    const person=(await api('/api/team')).users.find(u=>u.email==='vendas@example.test');
    await api('/api/update',{id:row.id,revision:row.revision,owner_id:person.id});
    await load();
  });
  await admin
    .locator(".card")
    .filter({ hasText: "Cliente de demonstração" })
    .click();
  await member
    .locator(".card")
    .filter({ hasText: "Cliente de demonstração" })
    .waitFor({ timeout: 15000 });
  const firstAlert=member.locator('[data-notification-popup]').filter({hasText:'Cliente de demonstração'});
  await firstAlert.waitFor({timeout:15000});
  assert.ok((await member.evaluate(()=>window.__alertToneStarts))>initialTones);
  await firstAlert.getByRole('button',{name:'Ver oportunidade',exact:true}).click();
  await member.locator('#detail h2').filter({hasText:'Cliente de demonstração'}).waitFor();
  await member.locator('#notification-count').waitFor({state:'hidden'});
  const noticeId=await member.evaluate(async()=>(await api('/api/notifications')).notifications[0].id);
  const deeplink=await b.newPage();
  await deeplink.goto(base+'/?notice='+noticeId);
  await deeplink.locator('#detail h2').filter({hasText:'Cliente de demonstração'}).waitFor();
  await deeplink.close();
  const freshContext=await browser.newContext();
  const afterLogin=await freshContext.newPage();
  await afterLogin.goto(base+'/?notice='+noticeId);
  await afterLogin.waitForURL(url=>url.pathname==='/login');
  assert.equal(new URL(afterLogin.url()).searchParams.get('next'),'/?notice='+noticeId);
  await afterLogin.locator('[name=email]').fill('vendas@example.test');
  await afterLogin.locator('[name=password]').fill(secret);
  await afterLogin.getByRole('button',{name:'Entrar',exact:true}).click();
  await afterLogin.locator('#detail h2').filter({hasText:'Cliente de demonstração'}).waitFor();
  await afterLogin.locator('#close-detail').click();
  await afterLogin.getByRole('button',{name:'Avisos de oportunidades',exact:true}).click();
  await afterLogin.locator('#phone-push-status').filter({hasText:'endereço HTTPS'}).waitFor();
  assert.equal(await afterLogin.locator('#enable-phone-push').isDisabled(),true);
  await freshContext.setOffline(true);
  await afterLogin.goto(base+'/');
  await afterLogin.getByRole('heading',{name:'Vamos reconectar.'}).waitFor();
  assert.equal(await afterLogin.locator('.card').count(),0);
  await freshContext.close();

  const tonesAfterAlert=await member.evaluate(()=>window.__alertToneStarts);
  await member.evaluate(async()=>{await refreshNotifications();await refreshNotifications();});
  assert.equal(await member.evaluate(()=>window.__alertToneStarts),tonesAfterAlert);
  assert.equal(await member.locator('#delete-contact').count(),0);
  await member.getByRole('button',{name:'Editar nome',exact:true}).click();
  await member.locator('#contact-name-form [name=contact_name]').fill('Cliente com nome confirmado');
  await member.getByRole('button',{name:'Salvar nome',exact:true}).click();
  await member.locator('#detail h2').filter({hasText:'Cliente com nome confirmado'}).waitFor();
  assert.equal(await member.locator('#contact-name-form').isHidden(),true);

  const whatsappLink=member.getByRole('link',{name:'Chamar no WhatsApp',exact:true});
  assert.equal(await whatsappLink.getAttribute('href'),'https://wa.me/5511999991234');
  assert.equal(await whatsappLink.getAttribute('target'),'_blank');
  assert.match(await whatsappLink.getAttribute('rel'),/noopener/);
  await b.route('https://wa.me/**',route=>route.fulfill({contentType:'text/html',body:'WhatsApp navigation fixture'}));
  const whatsappPopup=b.waitForEvent('page');
  await whatsappLink.click();
  const chatPage=await whatsappPopup;
  await chatPage.waitForURL('https://wa.me/5511999991234');
  await chatPage.close();
  await b.unroute('https://wa.me/**');
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
    .getByText("Você acessa somente suas oportunidades.", { exact: true })
    .waitFor();
  assert.equal(await member.locator("#invite-form").count(), 0);
  await member.locator("[data-view=contacts]").click();
  await member
    .getByRole("cell", { name: "Cliente com nome confirmado", exact: true })
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
    const person=(await api('/api/team')).users.find(u=>u.email==='vendas@example.test');
    for(const row of (await api('/api/contacts')).contacts.filter(c=>c.owner_id!==person.id)) {
      if(row.city_id) await api('/api/update',{id:row.id,revision:row.revision,owner_id:person.id});
      else await api('/api/claim',{id:row.id,revision:row.revision,owner_id:person.id});
    }
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
  assert.equal(await admin.locator('.card .source').count(),0);
  assert.equal(await admin.locator('.card .owner-tag').textContent(),'Admin de demonstração');
  assert.equal(await admin.locator('.card').getByText('Qualificação concluída',{exact:true}).count(),0);
  await admin.locator('.card').click();
  assert.equal(await admin.locator('#detail-form [name=lead_profile]').inputValue(),'Revenda');
  assert.equal(await admin.locator('#detail-form [name=city_id]').inputValue(),'4309407');
  assert.equal(await admin.locator('#detail-form [name=owner_id]').inputValue(),'admin-test');
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
  await member.locator('[data-view=pipeline]').click();
  await member.getByRole('button',{name:'Nova oportunidade'}).click();
  const manual=member.locator('#create-form');
  await manual.locator('[name=name]').fill('Oportunidade por indicação');
  await manual.locator('[name=phone]').fill('5554999997666');
  await manual.locator('[name=state_picker]').selectOption('SC');
  const cityOption=await manual.locator('[name=city_id] option').evaluateAll(options=>options.find(o=>o.textContent==='Florianópolis')?.value);
  await manual.locator('[name=city_id]').selectOption(cityOption);
  await manual.locator('[name=lead_profile]').selectOption('Lojista');
  await manual.locator('[name=stage]').selectOption('Negociação');
  await manual.locator('[name=value]').fill('1250.50');
  await manual.locator('[name=owner_id]').selectOption({label:'Vendedora de demonstração'});
  await member.screenshot({path:__dirname+'/preview-manual-form.png',fullPage:true});
  await manual.getByRole('button',{name:'Adicionar ao CRM'}).click();
  await member.locator('#detail-dialog').getByRole('heading',{name:'Oportunidade por indicação',exact:true}).waitFor();
  assert.equal(await member.locator('#detail .source').textContent(),'Manual');
  assert.equal(await member.locator('#detail-form [name=city_id]').inputValue(),cityOption);
  assert.equal(await member.locator('#detail-form [name=value]').inputValue(),'1250.5');
  assert.equal(await member.getByRole('link',{name:'Chamar no WhatsApp',exact:true}).getAttribute('href'),'https://wa.me/5554999997666');
  await member.locator('#close-detail').click();
  await whatsapp('Mensagem recebida do cadastro manual',false,'5554999997666');
  const manualData=await member.evaluate(async()=> (await api('/api/contacts')).contacts.find(c=>c.phone==='5554999997666'));
  assert.equal(manualData.manual_origin,1);
  assert.equal(manualData.ad_origin,0);
  assert.equal(manualData.qualification_state,'human');
  assert.equal(manualData.messages.length,1);
  assert.equal(manualData.messages[0].body,'Mensagem recebida do cadastro manual');
  await member.screenshot({path:__dirname+'/preview-manual.png',fullPage:true});
  assert.equal((await member.evaluate(async()=> (await api('/api/contacts')).contacts)).some(c=>c.phone==='5554999997444'),false);
  await admin.evaluate(async()=>{
    await api('/api/contacts',{name:'Sem responsável privado',phone:'5554999997888',city_id:'4309407',owner_id:''});
  });
  await member.evaluate(async()=>await load());
  assert.equal(await member.getByText('Sem responsável privado',{exact:true}).count(),0);
  await member.locator('.card').filter({hasText:'Oportunidade por indicação'}).click();
  await admin.evaluate(async()=>{
    const row=(await api('/api/contacts')).contacts.find(c=>c.phone==='5554999997666');
    await api('/api/update',{id:row.id,revision:row.revision,owner_id:'admin-test'});
  });
  await member.evaluate(async()=>await load());
  assert.equal(await member.locator('#detail-dialog').isVisible(),false);
  assert.equal(await member.locator('#detail').textContent(),'');
  assert.equal((await member.evaluate(async()=> (await api('/api/contacts')).contacts)).some(c=>c.phone==='5554999997666'),false);
  // Admin combines stable account IDs and profiles across every opportunity view.
  await admin.evaluate(async()=>{
    const row=(await api('/api/contacts')).contacts.find(c=>c.name==='Cliente com nome confirmado');
    await api('/api/update',{id:row.id,revision:row.revision,lead_profile:'Revenda'});
    await load();
  });
  await admin.locator('[data-view=pipeline]').click();
  await admin.locator('#owner-filter').selectOption(seller.id);
  await admin.locator('#profile-filter').selectOption('Revenda');
  assert.equal(await admin.locator('#owner-filter').inputValue(),seller.id);
  assert.equal(await admin.locator('.card').count(),1);
  assert.match(await admin.locator('.card').textContent(),/Cliente com nome confirmado/);
  assert.equal(await admin.locator('.card .profile-tag').textContent(),'Revenda');
  assert.equal(await admin.locator('.card .owner-tag').textContent(),'Vendedora de demonstração');
  assert.equal(await admin.locator('.card .source').count(),0);
  assert.equal((await admin.locator('.stat-number').first().textContent()).trim(),'1');
  await admin.screenshot({path:__dirname+'/preview-owner-filter.png',fullPage:true});
  await admin.locator('[data-view=contacts]').click();
  assert.equal(await admin.getByRole('cell',{name:'Cliente com nome confirmado',exact:true}).count(),1);
  assert.equal(await admin.getByRole('cell',{name:'Lead qualificado UI',exact:true}).count(),0);
  await admin.locator('[data-view=inbox]').click();
  assert.equal(await admin.locator('.inbox-item').count(),1);
  await admin.locator('[data-view=reports]').click();
  assert.equal(await admin.locator('[data-profile-summary=Revenda] td').nth(1).textContent(),'1');
  await admin.locator('[data-view=map]').click();
  await admin.locator('#map-count').filter({hasText:'1 lead(s) em 1 cidade(s)'}).waitFor();
  assert.equal(await admin.locator('.lead-pin').count(),1);
  await admin.locator('#profile-filter').selectOption('Lojista');
  await admin.locator('#map-count').filter({hasText:'0 lead(s)'}).waitFor();
  assert.equal(await admin.locator('.lead-pin').count(),0);
  await admin.locator('#owner-filter').selectOption('admin-test');
  await admin.locator('#map-count').filter({hasText:'1 lead(s) em 1 cidade(s)'}).waitFor();
  await admin.locator('[data-view=pipeline]').click();
  assert.equal(await admin.locator('.card').count(),1);
  assert.match(await admin.locator('.card').textContent(),/Oportunidade por indicação/);
  await admin.locator('#owner-filter').selectOption('__unassigned__');
  assert.equal(await admin.locator('.card').count(),0);
  await admin.locator('#profile-filter').selectOption('__pending__');
  assert.equal(await admin.locator('.card').count(),1);
  assert.match(await admin.locator('.card').textContent(),/Sem responsável privado/);
  await admin.locator('#owner-filter').selectOption(seller.id);
  assert.equal(await admin.locator('.card').count(),3);
  await admin.locator('#profile-filter').selectOption('Revenda');
  await admin.locator('#owner-filter').selectOption('');
  assert.equal(await admin.locator('#profile-filter').inputValue(),'Revenda');
  assert.equal(await admin.locator('.card').count(),2);
  await admin.locator('#profile-filter').selectOption('');
  await admin.locator('[data-view=team]').click();
  await admin.locator('#owner-filter').waitFor({state:'hidden'});
  await admin.locator('[data-view=pipeline]').click();
  await admin.setViewportSize({width:390,height:844});
  assert.equal(await admin.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.equal(await admin.locator('#owner-filter').isVisible(),true);
  await admin.screenshot({path:__dirname+'/preview-owner-filter-mobile.png',fullPage:true});
  await admin.setViewportSize({width:1440,height:1000});
  await admin.locator('.card').filter({hasText:'Oportunidade por indicação'}).click();
  admin.once('dialog',dialog=>dialog.dismiss());
  await admin.getByRole('button',{name:'Excluir card',exact:true}).click();
  assert.equal(await admin.locator('#detail-dialog').isVisible(),true);
  admin.once('dialog',dialog=>dialog.accept());
  await admin.getByRole('button',{name:'Excluir card',exact:true}).click();
  await admin.locator('#detail-dialog').waitFor({state:'hidden'});
  assert.equal(await admin.locator('.card').filter({hasText:'Oportunidade por indicação'}).count(),0);
  await admin.locator('#trash-nav').click();
  await admin.getByRole('heading',{name:'Cards excluídos',exact:true}).waitFor();
  const deletedRow=admin.locator('tbody tr').filter({hasText:'Oportunidade por indicação'});
  await deletedRow.getByRole('button',{name:'Restaurar card'}).click();
  await admin.getByRole('status').filter({hasText:'Card restaurado.'}).waitFor();
  assert.equal(await admin.locator('tbody tr').filter({hasText:'Oportunidade por indicação'}).count(),0);
  await admin.locator('[data-view=pipeline]').click();
  assert.equal(await admin.locator('.card').filter({hasText:'Oportunidade por indicação'}).count(),1);
  await member.locator('[data-view=pipeline]').click();
  await member.locator('.card').filter({hasText:'Cliente com nome confirmado'}).click();
  await member.locator('#note-form [name=body]').fill('Rascunho que deve permanecer enquanto chega um aviso');
  const tonesBeforeTyping=await member.evaluate(()=>window.__alertToneStarts);
  await admin.evaluate(async owner_id=>{
    await api('/api/contacts',{name:'Novo cliente para aviso',phone:'5554999997991',city_id:'4309407',lead_profile:'Consumidor Final',owner_id});
  },seller.id);
  const typingAlert=member.locator('#detail-dialog [data-notification-popup]').filter({hasText:'Novo cliente para aviso'});
  await typingAlert.waitFor({timeout:15000});
  assert.equal(await member.locator('#note-form [name=body]').inputValue(),'Rascunho que deve permanecer enquanto chega um aviso');
  assert.ok((await member.evaluate(()=>window.__alertToneStarts))>tonesBeforeTyping);
  await typingAlert.getByRole('button',{name:'Dispensar aviso'}).click();
  await member.locator('#close-detail').click();
  const returningContext=await browser.newContext();
  const returning=await returningContext.newPage();
  await login(returning,'vendas@example.test',secret);
  await returning.locator('#notification-count').waitFor();
  assert.equal(await returning.locator('[data-notification-popup]').count(),0,'Old unread alerts must not flood the screen on login');
  await returningContext.close();
  await member.getByRole('button',{name:'Avisos de oportunidades',exact:true}).click();
  await member.locator('#notifications-list').getByText('Novo cliente para aviso',{exact:true}).waitFor();
  assert.equal(await member.locator('#notifications-list').getByText('Sem responsável privado',{exact:true}).count(),0);
  await member.getByRole('button',{name:'Marcar todas como lidas',exact:true}).click();
  await member.locator('#notification-count').waitFor({state:'hidden'});
  await member.screenshot({path:__dirname+'/preview-notifications.png',fullPage:true});
  await member.getByRole('button',{name:'Fechar avisos',exact:true}).click();
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
  await member.waitForURL(url=>url.pathname==="/login");
  await member.screenshot({
    path: __dirname + "/preview-login.png",
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  console.log(
    "UI OK: editar nome, avisos privados com som e sem perder rascunhos, abrir WhatsApp pelo número do contato, filtros combinados de responsável e perfil, etiquetas dos cards, exclusão e restauração, acesso restrito, mapa, anúncios, qualificação, distribuição, indicadores e mobile.",
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
