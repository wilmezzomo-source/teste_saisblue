const vm=require('node:vm');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const handlers={},shown=[],opened=[],cached=[];
let pending,focused=false,navigated;
const sandbox={
  URL,Number,Promise,String,
  self:{location:{origin:'https://crm.example.test'},addEventListener:(type,fn)=>handlers[type]=fn,
    skipWaiting:async()=>{},registration:{showNotification:async(title,options)=>shown.push({title,options})},
    clients:{claim:async()=>{},matchAll:async()=>[],openWindow:async url=>opened.push(url)}},
  caches:{open:async()=>({addAll:async urls=>cached.push(...urls)}),keys:async()=>[],match:async()=>({offline:true})},
  fetch:async()=>{throw new Error('offline')}
};
vm.runInNewContext(fs.readFileSync('public/service-worker.js','utf8'),sandbox);
function event(extra={}) {return {...extra,waitUntil:p=>pending=p};}
(async()=>{
  handlers.install(event());await pending;
  assert.deepEqual(cached,['/offline.html','/brand/app-icon.png']);
  handlers.push(event({data:{json:()=>({notice:7,title:'Nome privado',body:'5554999991234',url:'https://evil.test'})}}));await pending;
  assert.equal(shown[0].title,'Novo lead no CRM');
  assert.ok(!JSON.stringify(shown).includes('5554999991234'));
  assert.ok(!JSON.stringify(shown).includes('Nome privado'));
  handlers.notificationclick(event({notification:{close:()=>{},data:{notice:7,url:'https://evil.test'}}}));await pending;
  assert.equal(opened[0],'https://crm.example.test/?notice=7');
  sandbox.self.clients.matchAll=async()=>[{url:'https://crm.example.test/login',navigate:async url=>navigated=url,focus:async()=>focused=true}];
  handlers.notificationclick(event({notification:{close:()=>{},data:{notice:'https://evil.test'}}}));await pending;
  assert.equal(navigated,'https://crm.example.test/');assert.equal(focused,true);
  let intercepted=false,offline;
  handlers.fetch({request:{mode:'cors',url:'https://crm.example.test/api/contacts'},respondWith:()=>intercepted=true});
  assert.equal(intercepted,false,'APIs must not be intercepted or cached');
  handlers.fetch({request:{mode:'navigate',url:'https://crm.example.test/'},respondWith:p=>offline=p});
  assert.deepEqual(await offline,{offline:true});
  console.log('Service worker OK: avisos genéricos, links limitados ao CRM e nenhum cache de API.');
})().catch(e=>{console.error(e);process.exitCode=1;});
