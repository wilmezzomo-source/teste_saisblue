let followupFilter='work';
let currentCallId=null;
const followupModes={unset:'Sem acompanhamento definido',identification:'Identificação em até 24 horas',awaiting:'Identificado · aguardando resposta',promised:'Retorno em data combinada',negotiation:'Conversa ativa / negociação',customer:'Cliente que já comprou',paused:'Pausado / revisão interna',closed:'Tentativa encerrada',blocked:'Não receber contato'};
const shortDay=value=>value ? value.split('-').reverse().join('/') : '—';
const followupToday=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const boardStage=c=>c.followup?.crm_stage || c.stage;
const followupDue=f=>Boolean(f?.due_on && f.due_on<=followupToday() && f.queue==='active');
const bellIcon='<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
function callState(f) {
  if(f.queue==='blocked')return {tone:'muted',title:'Não contatar',subtitle:'Abordagem interrompida'};
  if(f.queue==='decision')return {tone:'review',title:'Avaliar resultado',subtitle:'Defina Ganho ou Perdido na ficha'};
  if(f.queue==='closed')return {tone:'muted',title:'Acompanhamento encerrado',subtitle:'Sem próxima chamada'};
  if(f.queue==='conversation')return {tone:'reply',title:'Cliente respondeu',subtitle:'Combine a próxima chamada'};
  if(f.review)return {tone:'review',title:f.overdue?'Revisão pendente':'Revisão interna',subtitle:shortDay(f.due_on)};
  if(f.queue==='active' && f.due_on) {
    const phase=f.next_key ? ' · '+f.next_key : '';
    if(f.overdue)return {tone:'late',title:'ATRASADO'+phase,subtitle:shortDay(f.due_on)+' · '+f.overdue_days+' dia(s)'};
    if(f.due_on===followupToday())return {tone:'today',title:'CHAMAR HOJE'+phase,subtitle:shortDay(f.due_on)};
    return {tone:'planned',title:'Próxima chamada'+phase,subtitle:shortDay(f.due_on)};
  }
  return {tone:'muted',title:'Agendar chamada',subtitle:'Toque no sino para definir'};
}
function stepControls(c,compact=false) {
  const f=c.followup;
  if(!f?.available_steps?.length || ['blocked','closed','customer'].includes(f.queue) || c.stage==='Ganho')return '';
  const progress=f.progress||{},completed=Object.keys(progress).filter(k=>f.available_steps.includes(k)).map(k=>Number(k.slice(1)));
  const latest=completed.length?Math.max(...completed):-1;
  return `<div class="call-steps ${compact?'compact':''}" style="--call-step-count:${f.available_steps.length-1}" aria-label="Etapas do atendimento de ${esc(c.name)}">${f.available_steps.map((key,index)=>{
    const done=Boolean(progress[key]),earlier=Number(key.slice(1))<Math.max(latest,f.start_step||0);
    const final=index===f.available_steps.length-1;
    return `<label class="call-step ${final?'final-return':''} ${done?'done':''} ${earlier&&!done?'skipped':''}" title="${done?'Realizado em '+shortDay(progress[key]):earlier?'Etapa anterior sem registro':final?'Registrar o último retorno. O resultado da oportunidade será definido manualmente.':'Registrar '+key+' realizado hoje e agendar a próxima chamada'}"><input type="checkbox" data-quick-step="${key}" data-lead-id="${esc(c.id)}" aria-label="Registrar atendimento ${key} de ${esc(c.name)}" ${done?'checked':''} ${done||earlier?'disabled':''}><span>${key}</span>${final?'<small>Último retorno</small>':''}</label>`;
  }).join('')}</div>`;
}
function followupCard(c) {
  const f=c.followup;if(!f)return '';
  const state=callState(f);
  return `<div class="card-next-call"><button type="button" class="call-bell ${state.tone}" data-call-bell="${esc(c.id)}" aria-label="Próxima chamada de ${esc(c.name)}: ${esc(state.title)}"><span class="call-bell-icon">${bellIcon}</span><span><strong>${esc(state.title)}</strong><small>${esc(state.subtitle)}</small></span><span class="call-bell-edit" aria-hidden="true">›</span></button>${stepControls(c,true)}</div>`;
}
function followupView(list) {
  const filters={all:['Todos',()=>true],work:['Hoje e atrasados',c=>followupDue(c.followup)],today:['Só hoje',c=>c.followup.queue==='active'&&c.followup.due_on===followupToday()],late:['Só atrasados',c=>c.followup.queue==='active'&&c.followup.overdue],scheduled:['Agendados',c=>c.followup.queue==='active'&&!followupDue(c.followup)],unscheduled:['Sem chamada definida',c=>['unscheduled','identification','conversation'].includes(c.followup.queue)],decision:['Avaliar resultado',c=>c.followup.queue==='decision'],review:['Revisões manuais',c=>c.followup.queue==='review'],customer:['Recompra',c=>c.followup.queue==='customer'],paused:['Pausados',c=>c.followup.queue==='paused'],closed:['Encerrados / perdidos',c=>c.followup.queue==='closed'],blocked:['Não contatar',c=>c.followup.queue==='blocked']};
  if(!filters[followupFilter])followupFilter='work';
  const totals=contacts.filter(c=>matchesSelection(c,false));
  const rows=list.filter(filters[followupFilter][1]).sort((a,b)=>(a.followup.due_at||Infinity)-(b.followup.due_at||Infinity));
  return toolbar('Quem chamar agora','Marque a etapa realizada; a próxima data é calculada automaticamente.')+`<div class="call-dashboard">${[['late','Atrasados'],['today','Para hoje'],['unscheduled','Sem próxima chamada']].map(([key,label])=>`<button type="button" data-followup-filter="${key}" class="call-total ${key}"><span>${label}</span><strong>${totals.filter(filters[key][1]).length}</strong></button>`).join('')}</div>${followupTabs(filters,totals)}${rows.length?`<div class="followup-list">${rows.map(c=>`<article class="followup-item ${c.followup.overdue?'overdue':''}" data-contact="${esc(c.id)}" tabindex="0"><div class="followup-person"><strong>${esc(c.name)}</strong><div class="card-tags">${profileTag(c.lead_profile)}${ownerTag(c)}</div><small>${esc(c.city||'Cidade pendente')}${c.state?' / '+esc(c.state):''}</small></div><div class="followup-task">${followupCard(c)}</div></article>`).join('')}</div>`:'<div class="panel"><p>Nenhum contato nesta fila. Consulte Agendados ou Sem chamada definida.</p></div>'}`;
}
function followupTabs(filters,totals) {
  const primary=['work','scheduled','unscheduled','all'];
  const buttons=primary.map(key=>{const[label,predicate]=filters[key];return `<button type="button" data-followup-filter="${key}" class="${followupFilter===key?'active':''}">${label} <b>${totals.filter(predicate).length}</b></button>`;}).join('');
  const extra=Object.entries(filters).filter(([key])=>!primary.includes(key)&&!['late','today'].includes(key));
  return `<div class="followup-tabs" aria-label="Filtrar retornos">${buttons}<select id="more-followup-queues" aria-label="Outras filas de acompanhamento"><option value="">Outras filas…</option>${extra.map(([key,[label,predicate]])=>`<option value="${key}" ${followupFilter===key?'selected':''}>${label} (${totals.filter(predicate).length})</option>`).join('')}</select></div>`;
}
function activateFollowupFilter(key) {
  followupFilter=key;callDateFilter='all';dateFrom='';dateTo='';
  $('#call-date-filter').value='all';$('#date-from').value='';$('#date-to').value='';$('#date-to').setCustomValidity('');
  $('#custom-call-period').hidden=true;$('#clear-dates').hidden=true;render();
}
function bindFollowupView() {
  document.querySelectorAll('[data-followup-filter]').forEach(b=>b.onclick=()=>activateFollowupFilter(b.dataset.followupFilter));
  $('#more-followup-queues').onchange=e=>{if(e.target.value)activateFollowupFilter(e.target.value);};
}
async function recordCallStep(c,key,input) {
  input.disabled=true;
  try {
    const result=await api('/api/followups',{id:c.id,version:c.followup.version,action:'record_step',step:key});
    await load();
    if($('#call-dialog').open)openCallReminder(c.id);
    refreshFollowupDetail(c.id);
    const f=result.followup;
    toast(key+' registrado. '+(f.due_on?(f.review?'Revisão: ':'Próxima chamada: ')+shortDay(f.due_on):f.label));
  } catch(e) {toast(e.message);if(e.status===409||e.status===404)await load();}
  finally {if(input.isConnected){input.checked=false;input.disabled=false;}}
}
function bindCallControls(root=document) {
  root.querySelectorAll('[data-call-bell]').forEach(b=>b.onclick=e=>{e.stopPropagation();openCallReminder(b.dataset.callBell);});
  root.querySelectorAll('[data-quick-step]').forEach(input=>input.onchange=e=>{
    e.stopPropagation();const c=contacts.find(c=>c.id===input.dataset.leadId);if(c)recordCallStep(c,input.dataset.quickStep,input);
  });
}
function openCallReminder(id) {
  const c=contacts.find(c=>c.id===id);if(!c)return;
  currentCallId=id;
  const f=c.followup,state=callState(f),locked=['blocked','closed'].includes(f.queue);
  $('#call-dialog-content').innerHTML=`<div class="dialog-header"><div><p class="eyebrow">PRÓXIMA CHAMADA</p><h2>${esc(c.name)}</h2></div><button type="button" id="close-call" class="close" aria-label="Fechar próxima chamada">×</button></div><div class="call-summary ${state.tone}">${bellIcon}<div><strong>${esc(state.title)}</strong><p>${esc(state.subtitle)}</p></div></div>${!locked?`<h3>Qual atendimento você fez hoje?</h3>${stepControls(c)}<p class="followup-help">Marque D3, por exemplo: o CRM registra hoje e agenda D7 pelo intervalo da sequência. Etapas anteriores não são marcadas como realizadas.</p><form id="call-date-form"><label>Ou escolha a próxima chamada<input type="date" name="next_on" value="${esc(f.queue==='active'?f.due_on:'')}" required></label><label>Motivo (opcional)<input name="next_step" maxlength="500" value="${esc(f.next_step)}" placeholder="Ex.: retorno combinado com a cliente"></label><div class="call-date-shortcuts"><button type="button" class="secondary" data-call-days="0">Hoje</button><button type="button" class="secondary" data-call-days="1">Amanhã</button></div><div class="dialog-actions"><button class="primary">Agendar chamada</button></div><p class="field-error" id="call-error" role="alert" hidden></p></form>`:'<p class="followup-help">Revise a situação na ficha antes de agendar uma abordagem.</p>'}<button type="button" class="call-open-detail" id="call-open-detail">Abrir ficha completa</button>`;
  $('#close-call').onclick=()=>$('#call-dialog').close();
  $('#call-dialog').onclose=()=>currentCallId=null;
  $('#call-open-detail').onclick=()=>{$('#call-dialog').close();detail(id);};
  bindCallControls($('#call-dialog'));
  const form=$('#call-date-form');
  if(form) {
    document.querySelectorAll('[data-call-days]').forEach(b=>b.onclick=()=>form.elements.next_on.value=callDatePlus(Number(b.dataset.callDays)));
    form.onsubmit=async e=>{
      e.preventDefault();const error=$('#call-error');error.hidden=true;
      try {await api('/api/followups',{id,version:f.version,mode:'promised',...Object.fromEntries(new FormData(form))});await load();$('#call-dialog').close();refreshFollowupDetail(id);toast('Próxima chamada agendada.');}
      catch(e){error.textContent=e.message;error.hidden=false;if(e.status===409||e.status===404)await load();}
    };
  }
  if(!$('#call-dialog').open)$('#call-dialog').showModal();
}
function refreshFollowupDetail(id) {
  if(!$('#detail-dialog').open||currentDetailId!==id)return;
  const c=contacts.find(c=>c.id===id),section=$('#followup-title')?.closest('.followup-detail');
  if(c&&section){section.outerHTML=followupDetail(c);bindFollowupDetail(c);}
}
function followupDetail(c) {
  const f=c.followup;if(!f)return '';
  const selectedMode=f.mode==='unset' ? c.stage==='Ganho'?'customer':['Lojista','Revenda','Consumidor Final'].includes(c.lead_profile)?'awaiting':'identification' : f.mode;
  return `<section class="followup-detail" aria-labelledby="followup-title"><h3 id="followup-title">Próxima chamada</h3>${followupCard(c)}<details id="followup-advanced"><summary>Mais opções de acompanhamento</summary><form id="followup-form"><div class="detail-grid"><label>Situação do acompanhamento<select name="mode">${Object.entries(followupModes).map(([key,label])=>`<option value="${key}" ${selectedMode===key?'selected':''}>${label}</option>`).join('')}</select></label><label>Data da última conversa<input type="date" name="last_conversation_on" value="${esc(f.last_conversation_on)}"></label><label data-followup-for="promised negotiation">Data do próximo contato<input type="date" name="next_on" value="${esc(f.next_on)}"></label><label data-followup-for="promised negotiation">Próximo passo<input name="next_step" maxlength="500" value="${esc(f.next_step)}"></label><label data-followup-for="paused awaiting">Data de revisão (opcional)<input type="date" name="review_on" value="${esc(f.review_on)}"></label><label data-followup-for="customer">Data da última compra<input type="date" name="last_purchase_on" value="${esc(f.last_purchase_on)}"></label><label data-followup-for="customer">Ciclo de recompra (dias)<input type="number" min="1" max="730" name="cycle_days" value="${f.cycle_days}"></label></div><p class="followup-help" id="followup-mode-help"></p><div class="dialog-actions"><button type="button" class="secondary" id="restart-followup">Nova tentativa a partir da última conversa</button><button class="primary">Salvar acompanhamento</button></div><p id="followup-error" role="alert" class="field-error" hidden></p></form></details></section>`;
}
function bindFollowupDetail(c) {
  bindCallControls($('#detail'));
  const form=$('#followup-form');if(!form)return;
  const help={awaiting:'Marque a etapa realizada. O último retorno é D30 para lojista, D45 para revenda e D15 para consumidor. Depois, defina Ganho ou Perdido na ficha.',promised:'A data combinada substitui a sequência anterior.',negotiation:'Informe o próximo passo e a data.',customer:'Ajuste o ciclo de recompra à reposição ou coleção.',blocked:'Sem novos lembretes de abordagem comercial.',identification:'Lead sem resposta à pergunta enviada pelo assistente virtual por 24h vai para Perdido — Sem Resposta, preservando atendimentos humanos e falhas de envio.'};
  const modeChanged=()=>{
    const mode=form.elements.mode.value;
    form.querySelectorAll('[data-followup-for]').forEach(label=>{const show=label.dataset.followupFor.split(' ').includes(mode);label.hidden=!show;label.querySelectorAll('input').forEach(input=>input.disabled=!show);});
    $('#restart-followup').hidden=mode!=='awaiting';$('#followup-mode-help').textContent=help[mode]||'Lembretes internos; nenhuma mensagem é enviada.';
  };
  modeChanged();form.elements.mode.onchange=modeChanged;
  const persist=async fields=>{
    const error=$('#followup-error');error.hidden=true;
    try {await api('/api/followups',{id:c.id,version:c.followup.version,...fields});await load();refreshFollowupDetail(c.id);$('#followup-advanced').open=true;toast('Acompanhamento salvo.');}
    catch(e){error.textContent=e.message;error.hidden=false;if(e.status===409)await load();}
  };
  form.onsubmit=e=>{e.preventDefault();persist(Object.fromEntries(new FormData(form)));};
  $('#restart-followup').textContent='Reiniciar sequência hoje';
  $('#restart-followup').onclick=()=>persist({...Object.fromEntries(new FormData(form)),restart:true});
}
