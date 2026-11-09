const phonePush={registration:null,subscription:null,config:null};
const pwaRegistration=window.isSecureContext && "serviceWorker" in navigator
  ? Promise.race([
      navigator.serviceWorker.register("/service-worker.js",{scope:"/",updateViaCache:"none"}).then(()=>navigator.serviceWorker.ready).catch(()=>null),
      new Promise(resolve=>setTimeout(()=>resolve(null),4000))
    ]) : Promise.resolve(null);
function isIphoneApp() {
  const ios=/iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform==="MacIntel" && navigator.maxTouchPoints>1);
  return {ios,installed:window.matchMedia("(display-mode: standalone)").matches || navigator.standalone===true};
}
function renderPhonePush() {
  const c=phonePush.config,{ios,installed}=isIphoneApp();
  const supported="PushManager" in window && "Notification" in window;
  const status=$("#phone-push-status");
  $("#prepare-phone-push").hidden=currentUser.role!=="admin" || !!c?.configured;
  let message="Preparando notificações do aparelho…";
  let allowed=false;
  if(!c?.secure || !window.isSecureContext) message="Para avisos na tela bloqueada, abra o CRM pelo endereço HTTPS após configurar o acesso externo.";
  else if(ios && !installed) message="No Safari, toque em Compartilhar → Adicionar à Tela de Início. Abra o app instalado e volte aqui para ativar as notificações.";
  else if(!supported || !phonePush.registration) message="Este navegador ainda não oferece notificações para o app. No iPhone, use iOS 16.4 ou superior e abra o ícone instalado na tela inicial.";
  else if(!c?.configured) message="O administrador precisa preparar as notificações no servidor. Depois, ative neste aparelho.";
  else if(Notification.permission==="denied") message="As notificações estão bloqueadas. No iPhone, revise Ajustes → Notificações → Sais Blue CRM.";
  else if(phonePush.subscription) message="Notificações deste aparelho ativadas. Para conferir a tela bloqueada, envie o teste e bloqueie o iPhone.";
  else {message="Ative para receber avisos de novos leads mesmo com o app fechado. O iPhone pedirá sua permissão.";allowed=true;}
  status.textContent=message;
  $("#enable-phone-push").disabled=!allowed;
  $("#enable-phone-push").hidden=!!phonePush.subscription;
  $("#disable-phone-push").hidden=!phonePush.subscription;
  $("#test-phone-push").hidden=!phonePush.subscription;
  const link=$("#phone-app-url");
  link.href=c?.public_url || "https://crm.saisblue.com.br";
  link.textContent=c?.public_url || "https://crm.saisblue.com.br";
}
function pushKeyBytes(value) {
  const base64=value.replace(/-/g,"+").replace(/_/g,"/");
  const raw=atob(base64+"=".repeat((4-base64.length%4)%4));
  return Uint8Array.from(raw,c=>c.charCodeAt(0));
}
async function stopPhonePush() {
  const registration=phonePush.registration || await pwaRegistration;
  const subscription=phonePush.subscription || await registration?.pushManager?.getSubscription();
  if(subscription) {
    try {await api("/api/push/unsubscribe",{endpoint:subscription.endpoint});}
    finally {await subscription.unsubscribe();phonePush.subscription=null;}
  }
}
async function initPhonePush() {
  phonePush.registration=await pwaRegistration;
  try {
    phonePush.config=await api("/api/push/config");
    const {ios,installed}=isIphoneApp();
    if(phonePush.config.secure && (!ios || installed) && "Notification" in window && Notification.permission==="granted" && phonePush.registration && "PushManager" in window) {
      const sub=await phonePush.registration.pushManager.getSubscription();
      if(sub && phonePush.config.configured) {await api("/api/push/subscribe",{subscription:sub.toJSON()});phonePush.subscription=sub;}
    }
  } catch {}
  $("#prepare-phone-push").onclick=async()=>{
    try {await api("/api/push/prepare",{});phonePush.config=await api("/api/push/config");renderPhonePush();toast("Notificações preparadas no servidor.");}
    catch(e){toast(e.message);}
  };
  $("#enable-phone-push").onclick=async()=>{
    try {
      const permission=await Notification.requestPermission();
      if(permission!=="granted") {renderPhonePush();return;}
      const sub=await phonePush.registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:pushKeyBytes(phonePush.config.public_key)});
      await api("/api/push/subscribe",{subscription:sub.toJSON()});phonePush.subscription=sub;
      renderPhonePush();toast("Notificações deste aparelho ativadas.");
    } catch(e){toast(e.message || "Não foi possível ativar as notificações neste aparelho.");}
  };
  $("#disable-phone-push").onclick=async()=>{try {await stopPhonePush();renderPhonePush();toast("Notificações deste aparelho desativadas.");}catch(e){toast(e.message);}};
  $("#test-phone-push").onclick=async()=>{
    try {await api("/api/push/test",{endpoint:phonePush.subscription.endpoint});toast("Teste agendado para 10 segundos. Bloqueie o iPhone para conferir.");}
    catch(e){toast(e.message);}
  };
  renderPhonePush();
}
