const PUBLIC_CACHE="saisblue-public-v1";
self.addEventListener("install",event=>{
  event.waitUntil(caches.open(PUBLIC_CACHE).then(cache=>cache.addAll(["/offline.html","/brand/app-icon.png"])).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith("saisblue-public-") && k!==PUBLIC_CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener("fetch",event=>{
  // Only public offline content is cached. Authenticated pages and API data are never stored.
  if(event.request.mode==="navigate" && new URL(event.request.url).origin===self.location.origin) {
    event.respondWith(fetch(event.request).catch(()=>caches.match("/offline.html")));
  }
});
self.addEventListener("push",event=>{
  let payload={};
  try {payload=event.data?.json() || {};} catch {}
  const notice=Number.isSafeInteger(payload.notice) && payload.notice>0 ? payload.notice : null;
  const test=payload.title==="Teste Sais Blue CRM";
  event.waitUntil(self.registration.showNotification(test?"Teste Sais Blue CRM":"Novo lead no CRM",{
    body:test?"As notificações deste aparelho estão funcionando.":"Há uma nova oportunidade para acompanhar. Toque para abrir o CRM.",
    icon:"/brand/app-icon.png",badge:"/brand/app-icon.png",tag:notice?"crm-notice:"+notice:String(payload.tag || "crm-notice").slice(0,100),
    data:{notice}
  }));
});
self.addEventListener("notificationclick",event=>{
  event.notification.close();
  const notice=event.notification.data?.notice;
  const target=new URL(Number.isSafeInteger(notice) && notice>0 ? "/?notice="+notice : "/",self.location.origin);
  event.waitUntil(self.clients.matchAll({type:"window",includeUncontrolled:true}).then(async windows=>{
    const existing=windows.find(client=>new URL(client.url).origin===self.location.origin);
    if(existing) {await existing.navigate(target.href);return existing.focus();}
    return self.clients.openWindow(target.href);
  }));
});
