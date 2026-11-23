/* Paginated summaries, conditional refresh and lazy private contact details. */
let workspaceState=null,workspaceKey='',workspaceETag='',workspaceFlight=null,workspaceAgain=false;
let workspacePages={},workspacePage=0,workspaceBase='',detailData=null,callData=null,detailRequest=0,callRequest=0;
function workspaceParams() {
  const params=new URLSearchParams({view,profile:profileFilter,owner:ownerFilter,date:callDateFilter,from:dateFrom,to:dateTo,q:query,queue:followupFilter,state:mapState,stage:mapStage});
  const base=params.toString();
  if(base!==workspaceBase){workspacePages={};workspacePage=0;workspaceBase=base;}
  params.set('pages',JSON.stringify(workspacePages));params.set('page',workspacePage);
  return params;
}
function currentContact(id) {return ($('#call-dialog')?.open&&callData?.id===id?callData:null) || contacts.find(c=>c.id===id) || (detailData?.id===id?detailData:null);}
function workspaceReady() {
  if(workspaceState&&workspaceKey===workspaceParams().toString())return true;
  load();return false;
}
async function workspaceLoad() {
  if(workspaceFlight){workspaceAgain=true;return workspaceFlight;}
  workspaceFlight=(async()=>{
    do {
      workspaceAgain=false;
      const params=workspaceParams(),key=params.toString();
      const r=await fetch('/api/workspace?'+key,{headers:key===workspaceKey&&workspaceETag?{'If-None-Match':workspaceETag}:{}});
      if(r.status===401){location.replace('/login');return;}
      if(!r.ok&&r.status!==304){const error=await r.json();throw Error(error.error||'Não foi possível carregar as oportunidades.');}
      if(key!==workspaceParams().toString()){workspaceAgain=true;continue;}
      if(r.status!==304) {
        const data=await r.json();
        // A filter can change while a large response is being decoded.
        if(key!==workspaceParams().toString()){workspaceAgain=true;continue;}
        const sameSelection=workspaceKey===key;
        workspaceState=data;contacts=data.contacts;stages=data.stages;workspaceKey=key;workspaceETag=r.headers.get('ETag')||'';
        if(view==='trash'&&currentUser.role==='admin')trashContacts=(await api('/api/trash')).contacts;
        for(const [id,type] of [[currentDetailId,'detail'],[currentCallId,'call']]) {
          if(!id)continue;
          try {await api('/api/contacts/'+encodeURIComponent(id)+'?access=1');}
          catch(e) {if(e.status===404)unavailableContact(type,id);else throw e;}
        }
        syncOwnerFilter();
        if(view==='map'&&leadMap){stats();refreshPins();}else render(sameSelection);
      }
    } while(workspaceAgain);
  })().catch(e=>toast(e.message)).finally(()=>{workspaceFlight=null;});
  return workspaceFlight;
}
function unavailableContact(type,id) {
  if(type==='detail'&&currentDetailId===id){$('#detail-dialog').close();$('#detail').innerHTML='';currentDetailId=null;detailData=null;++detailRequest;}
  if(type==='call'&&currentCallId===id){$('#call-dialog').close();$('#call-dialog-content').innerHTML='';currentCallId=null;callData=null;++callRequest;}
  toast('Esta oportunidade não está mais disponível para sua conta.');
}
function workspacePager(name='list') {
  const p=workspaceState?.pages?.[name];if(!p||p.total<=p.size)return '';
  return `<div class="workspace-pager" aria-label="Paginação de ${esc(name==='list'?'oportunidades':name)}"><button type="button" class="secondary" data-page-for="${esc(name)}" data-page="${p.page-1}" ${p.page===0?'disabled':''}>‹ Anteriores</button><small>${p.page*p.size+1}–${Math.min(p.total,(p.page+1)*p.size)} de ${p.total}</small><button type="button" class="secondary" data-page-for="${esc(name)}" data-page="${p.page+1}" ${(p.page+1)*p.size>=p.total?'disabled':''}>Próximos ›</button></div>`;
}
function bindWorkspacePages() {
  document.querySelectorAll('[data-page-for]').forEach(button=>button.onclick=async()=>{
    if(button.dataset.pageFor==='list')workspacePage=Number(button.dataset.page);else workspacePages[button.dataset.pageFor]=Number(button.dataset.page);
    button.disabled=true;await load();
    const target=button.dataset.pageFor==='list'?$('#content .toolbar'):[...document.querySelectorAll('.column')].find(c=>c.dataset.stage===button.dataset.pageFor);
    target?.scrollIntoView({block:'start',inline:'nearest'});
  });
}
function patchWorkspaceContent(html,incremental) {
  const root=$('#content');
  if(!incremental||view!=='pipeline'||!root.querySelector('.board')){
    const left=root.querySelector('.board')?.scrollLeft||0;root.innerHTML=html;
    if(view==='pipeline'&&root.querySelector('.board'))root.querySelector('.board').scrollLeft=left;
    return;
  }
  const holder=document.createElement('div');holder.innerHTML=html;
  for(const fresh of holder.querySelectorAll('.column')) {
    const column=[...root.querySelectorAll('.column')].find(c=>c.dataset.stage===fresh.dataset.stage);
    if(!column){root.innerHTML=html;return;}
    for(const selector of ['.column-head','.column-value']) {
      const before=column.querySelector(selector),after=fresh.querySelector(selector);
      if(before.outerHTML!==after.outerHTML)before.replaceWith(after);
    }
    const wanted=[...fresh.querySelectorAll('.card')],ids=new Set(wanted.map(c=>c.dataset.contact));
    for(const card of column.querySelectorAll('.card'))if(!ids.has(card.dataset.contact))card.remove();
    if(wanted.length)column.querySelector('.empty-column')?.remove();
    let cursor=column.children[2];
    for(const card of wanted) {
      const existing=[...column.querySelectorAll('.card')].find(c=>c.dataset.contact===card.dataset.contact);
      let chosen=existing;
      if(!existing)chosen=card;
      else if(existing.outerHTML!==card.outerHTML){existing.replaceWith(card);chosen=card;if(cursor===existing)cursor=chosen;}
      if(chosen!==cursor)column.insertBefore(chosen,cursor||null);
      cursor=chosen.nextElementSibling;
    }
    for(const selector of ['.empty-column','.workspace-pager']) {
      const before=column.querySelector(selector),after=fresh.querySelector(selector);
      if(before&&after){if(before.outerHTML!==after.outerHTML)before.replaceWith(after);}
      else if(before)before.remove();else if(after)column.append(after);
    }
  }
}
function conversationView(c) {
  return `${c.history_cursor?'<button type="button" class="secondary" id="older-messages">Ver mensagens anteriores</button>':''}<div class="conversation">${c.messages.length?c.messages.map(m=>`<div class="message ${m.direction==='note'?'note':''}">${esc(m.body)}<small>${esc(m.author||'')}${m.author?' · ':''}${m.direction==='note'?'Nota interna':m.direction==='out'?'WhatsApp enviado':'Mensagem recebida'}${m.channel==='simulation'?' · Simulação':''}${m.direction==='out'?' · '+esc(statusLabel(m.status)):''}${m.error_code?' · Código '+esc(m.error_code)+': '+esc(m.error_detail):''} · ${date(m.created)}</small></div>`).join(''):'<p>Nenhuma mensagem ou nota registrada.</p>'}</div>`;
}
function bindOlderHistory(c) {
  const button=$('#older-messages');if(!button)return;
  button.onclick=async()=>{
    button.disabled=true;
    try {
      const result=await api('/api/contacts/'+encodeURIComponent(c.id)+'?before='+encodeURIComponent(JSON.stringify(c.history_cursor)));
      if(currentDetailId!==c.id)return;
      const ids=new Set(c.messages.map(m=>m.id));c.messages=[...result.contact.messages.filter(m=>!ids.has(m.id)),...c.messages];c.history_cursor=result.contact.history_cursor;
      const container=$('#detail .conversation'),holder=document.createElement('div');holder.innerHTML=conversationView(c);
      button.remove();container.replaceWith(...holder.childNodes);bindOlderHistory(c);
    }catch(e){if(e.status===404)unavailableContact('detail',c.id);else toast(e.message);}
    finally {button.disabled=false;}
  };
}

function bindOlderAudit(c) {
  const button=$('#older-audit');if(!button)return;
  button.onclick=async()=>{
    button.disabled=true;
    try {
      const result=await api('/api/contacts/'+encodeURIComponent(c.id)+'?audit_before='+c.audit_cursor);
      if(currentDetailId!==c.id)return;
      const ids=new Set(c.audit.map(e=>e.id));c.audit.push(...result.contact.audit.filter(e=>!ids.has(e.id)));c.audit_cursor=result.contact.audit_cursor;
      $('#detail .activity').innerHTML=auditEventsView(c.audit);
      if(c.audit_cursor)button.disabled=false;else button.remove();
    }catch(e){if(e.status===404)unavailableContact('detail',c.id);else toast(e.message);button.disabled=false;}
  };
}
