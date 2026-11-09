/* Opportunity alerts do not reload a card while someone is editing it. */
const crmAlerts={items:[],unread:0,cursor:0,ready:false,busy:false,sound:false,audio:null,timer:null,popups:[]};
const alertTitle=kind=>({new:"Novo contato no CRM",assigned:"Oportunidade atribuída a você",restored:"Oportunidade restaurada para você"})[kind] || "Nova oportunidade";
function alertPreference(key,value) {
  const name="saisblue-alerts:"+currentUser.id+":"+key;
  try {
    if(value===undefined) return localStorage.getItem(name);
    localStorage.setItem(name,String(value));
  } catch {}
  return null;
}
function renderAlertSound() {
  const playing=crmAlerts.sound && crmAlerts.audio?.state==="running";
  $("#enable-alert-sound").hidden=playing;
  $("#disable-alert-sound").hidden=!crmAlerts.sound;
  $("#notification-sound-status").textContent=playing ? "Avisos com som ativados neste navegador." : "Clique em Ativar avisos com som para liberar o áudio neste navegador.";
}
async function unlockAlertSound() {
  const Audio=window.AudioContext || window.webkitAudioContext;
  if(!Audio) return false;
  try {
    if(!crmAlerts.audio) crmAlerts.audio=new Audio();
    if(crmAlerts.audio.state!=="running") await crmAlerts.audio.resume();
    renderAlertSound();
    return crmAlerts.audio.state==="running";
  } catch {return false;}
}
function playAlertSound() {
  const audio=crmAlerts.audio;
  if(!crmAlerts.sound || audio?.state!=="running") return;
  const start=audio.currentTime;
  for(const [delay,frequency] of [[0,523.25],[.16,659.25]]) {
    const oscillator=audio.createOscillator(),gain=audio.createGain();
    oscillator.type="sine";oscillator.frequency.value=frequency;
    gain.gain.setValueAtTime(0,start+delay);
    gain.gain.linearRampToValueAtTime(.09,start+delay+.02);
    gain.gain.exponentialRampToValueAtTime(.001,start+delay+.19);
    oscillator.connect(gain);gain.connect(audio.destination);
    oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();};
    oscillator.start(start+delay);oscillator.stop(start+delay+.21);
  }
}
function placeLeadAlerts() {
  const focused=document.activeElement?.closest("dialog[open]");
  const modal=focused || [...document.querySelectorAll("dialog[open]")].at(-1);
  (modal || document.body).append($("#lead-alerts"));
}
function renderLeadPopups() {
  const host=$("#lead-alerts");
  host.innerHTML=crmAlerts.popups.slice(-3).map(n=>`<div class="lead-alert" data-notification-popup="${n.id}"><button type="button" class="alert-dismiss" data-dismiss-alert="${n.id}" aria-label="Dispensar aviso">×</button><strong>${esc(alertTitle(n.kind))}</strong><p>${esc(n.name)}</p><button type="button" class="primary" data-open-alert="${n.id}">Ver oportunidade</button></div>`).join("");
  host.querySelectorAll("[data-open-alert]").forEach(b=>b.onclick=()=>openLeadNotification(Number(b.dataset.openAlert)));
  host.querySelectorAll("[data-dismiss-alert]").forEach(b=>b.onclick=()=>{
    crmAlerts.popups=crmAlerts.popups.filter(n=>n.id!==Number(b.dataset.dismissAlert));renderLeadPopups();
  });
  placeLeadAlerts();
}
function renderNotificationList() {
  const count=$("#notification-count");
  count.hidden=!crmAlerts.unread;count.textContent=crmAlerts.unread>99?"99+":String(crmAlerts.unread);
  $("#open-notifications").title=crmAlerts.unread+" aviso(s) não lido(s)";
  const signature=JSON.stringify(crmAlerts.items.map(n=>[n.id,n.name,n.read_at]));
  const list=$("#notifications-list");
  if(list.dataset.signature!==signature) {
    list.dataset.signature=signature;
    list.innerHTML=crmAlerts.items.length ? crmAlerts.items.map(n=>`<button type="button" class="notification-item ${n.read_at?"":"unread"}" data-notification-id="${n.id}"><strong>${esc(n.name)}</strong><span>${esc(alertTitle(n.kind))}</span><small>${date(n.created)}${n.read_at?" · Lido":" · Não lido"}</small></button>`).join("") : '<p class="notification-empty">Nenhum aviso por enquanto.</p>';
    list.querySelectorAll("[data-notification-id]").forEach(b=>b.onclick=()=>openLeadNotification(Number(b.dataset.notificationId)));
  }
}
async function refreshNotifications(initial=false) {
  if(!currentUser || crmAlerts.busy) return;
  crmAlerts.busy=true;
  try {
    const data=await api("/api/notifications");
    const previous=initial || !crmAlerts.ready ? data.cursor : Math.max(crmAlerts.cursor,Number(alertPreference("cursor"))||0);
    const fresh=initial || !crmAlerts.ready ? [] : data.notifications.filter(n=>n.id>previous && !n.read_at);
    crmAlerts.items=data.notifications;crmAlerts.unread=data.unread;
    crmAlerts.cursor=Math.max(previous,data.cursor);crmAlerts.ready=true;
    alertPreference("cursor",crmAlerts.cursor);
    // Remove a popup promptly if the opportunity was transferred, deleted or read elsewhere.
    const visible=new Map(data.notifications.filter(n=>!n.read_at).map(n=>[n.id,n]));
    crmAlerts.popups=crmAlerts.popups.filter(n=>visible.has(n.id)).map(n=>visible.get(n.id));
    if(fresh.length) {
      crmAlerts.popups.push(...fresh.reverse());
      playAlertSound();
      clearTimeout(crmAlerts.timer);
      crmAlerts.timer=setTimeout(()=>{crmAlerts.popups=[];renderLeadPopups();},15000);
    }
    renderNotificationList();renderLeadPopups();
  } catch {
    // The next poll recovers without clearing unread alerts or repeating sounds.
  } finally {crmAlerts.busy=false;}
}
async function openLeadNotification(id) {
  const n=crmAlerts.items.find(n=>n.id===id);
  if(!n) return;
  try {
    await api("/api/notifications/read",{ids:[id]});
    await load();
    crmAlerts.popups=crmAlerts.popups.filter(item=>item.id!==id);
    $("#notifications-dialog").close();
    if(contacts.some(c=>c.id===n.contact_id)) detail(n.contact_id);
    else toast("Esta oportunidade não está mais disponível para sua conta.");
    await refreshNotifications();
  } catch(e) {toast(e.message);}
}
async function initNotifications() {
  crmAlerts.sound=alertPreference("sound")==="true";
  $("#open-notifications").onclick=()=>{
    $("#notifications-dialog").showModal();renderAlertSound();refreshNotifications();placeLeadAlerts();
  };
  $("#close-notifications").onclick=()=>$("#notifications-dialog").close();
  $("#enable-alert-sound").onclick=async()=>{
    crmAlerts.sound=true;alertPreference("sound",true);
    if(await unlockAlertSound()) {playAlertSound();toast("Avisos com som ativados.");}
    else toast("O navegador não liberou o som. Os avisos visuais continuam disponíveis.");
    renderAlertSound();
  };
  $("#disable-alert-sound").onclick=()=>{crmAlerts.sound=false;alertPreference("sound",false);renderAlertSound();};
  $("#read-all-notifications").onclick=async()=>{
    try {await api("/api/notifications/read",{all:true});await refreshNotifications();}
    catch(e){toast(e.message);}
  };
  document.querySelectorAll("dialog").forEach(dialog=>dialog.addEventListener("close",placeLeadAlerts));
  const unlock=event=>{if(crmAlerts.sound && !event.target?.closest?.("#enable-alert-sound,#disable-alert-sound")) unlockAlertSound();};
  document.addEventListener("pointerdown",unlock,{passive:true});
  document.addEventListener("keydown",unlock);
  renderAlertSound();
  await refreshNotifications(true);
  await initPhonePush();
  const notice=Number(new URLSearchParams(location.search).get("notice"));
  if(Number.isSafeInteger(notice) && notice>0) {
    const url=new URL(location.href);url.searchParams.delete("notice");history.replaceState(null,"",url.pathname+url.search);
    try {
      const result=await api("/api/notifications/"+notice);
      if(!crmAlerts.items.some(n=>n.id===notice)) crmAlerts.items.push(result.notification);
      await openLeadNotification(notice);
    } catch(e) {toast(e.message);}
  }
  setInterval(()=>refreshNotifications(),5000);
}
