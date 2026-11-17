let followupFilter='today';
const followupModes={unset:'Sem acompanhamento definido',identification:'Identificação em até 24 horas',awaiting:'Identificado · aguardando resposta',promised:'Retorno em data combinada',negotiation:'Conversa ativa / negociação',customer:'Cliente que já comprou',paused:'Pausado / revisão interna',closed:'Tentativa encerrada',blocked:'Não receber contato'};
const shortDay=value=>value ? value.split('-').reverse().join('/') : '—';
const followupToday=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const boardStage=c=>c.followup?.crm_stage || c.stage;
const followupDue=f=>Boolean(f?.due_at && f.due_at<=Date.now()/1000 && ['active','review','customer'].includes(f.queue));
function followupCard(c) {
  const f=c.followup;
  if(!f || (f.mode==='unset' && f.queue!=='qualification_pending'))return '';
  return `<div class="followup-card ${followupDue(f)?'due':''}">${esc(f.label)}${f.due_on?`<strong>${f.review?'Revisar':'Retornar'}: ${shortDay(f.due_on)}</strong>`:''}</div>`;
}
function followupView(list) {
  const filters={today:['Hoje / atrasados',c=>followupDue(c.followup)],scheduled:['Agendados',c=>c.followup.queue==='active' && !followupDue(c.followup)],review:['Revisões',c=>c.followup.queue==='review'],conversation:['Cliente respondeu',c=>c.followup.queue==='conversation'],qualification_pending:['Qualificação pendente',c=>c.followup.queue==='qualification_pending'],customer:['Clientes / recompra',c=>c.followup.queue==='customer'],unscheduled:['Sem agenda',c=>['unscheduled','identification'].includes(c.followup.queue)],paused:['Pausados',c=>c.followup.queue==='paused'],closed:['Encerrados',c=>c.followup.queue==='closed'],blocked:['Não contatar',c=>c.followup.queue==='blocked']};
  const rows=list.filter(filters[followupFilter][1]).sort((a,b)=>(a.followup.due_at||Infinity)-(b.followup.due_at||Infinity));
  return toolbar('Agenda de retornos','Abra o card para registrar a última conversa e definir a próxima ação')+`<div class="followup-tabs" aria-label="Filtrar retornos">${Object.entries(filters).map(([key,[label,predicate]])=>`<button type="button" data-followup-filter="${key}" class="${followupFilter===key?'active':''}">${label} <b>${list.filter(predicate).length}</b></button>`).join('')}</div><p class="followup-help">Lembretes internos. Revisão não significa enviar mensagem. Dias corridos; lembretes em dias úteis, das 9h às 18h (Brasília). Datas combinadas ficam preservadas.</p>${rows.length?`<div class="followup-list">${rows.map(c=>`<button type="button" class="followup-item ${followupDue(c.followup)?'due':''}" data-contact="${esc(c.id)}"><div><strong>${esc(c.name)}</strong><div class="card-tags">${profileTag(c.lead_profile)}${ownerTag(c)}</div><span>${esc(c.followup.label)}</span></div><div class="followup-when"><strong>${shortDay(c.followup.due_on)}</strong><small>${c.followup.last_conversation_on?'Última conversa: '+shortDay(c.followup.last_conversation_on):'Defina a última conversa'}</small></div></button>`).join('')}</div>`:'<div class="panel"><p>Nenhum contato nesta fila para os filtros selecionados.</p></div>'}`;
}
function bindFollowupView() {
  document.querySelectorAll('[data-followup-filter]').forEach(b=>b.onclick=()=>{followupFilter=b.dataset.followupFilter;render();});
}
function followupDetail(c) {
  const f=c.followup;if(!f)return '';
  const selectedMode=f.mode==='unset' ? c.stage==='Ganho'?'customer':['Lojista','Revenda','Consumidor Final'].includes(c.lead_profile)?'awaiting':'identification' : f.mode;
  const plan=f.plan.map(p=>`<label class="followup-check"><input type="checkbox" data-followup-step="${p.key}" ${p.done_on?'checked':''} ${!p.done_on && !p.covered && p.key===f.next_key && f.due_on<=followupToday()?'':'disabled'}><span><strong>${p.key}</strong> · ${shortDay(p.on)}<small>${p.done_on?'Realizado em '+shortDay(p.done_on):p.covered?'Coberto pelo contato da mesma data':p.missed?'Prazo passado · não registrado':p.key===f.next_key?'Próxima tentativa':'Prazo da sequência'}</small></span></label>`).join('');
  return `<section class="followup-detail" aria-labelledby="followup-title"><h3 id="followup-title">Acompanhamento e lembretes</h3><p class="followup-status ${followupDue(f)?'due':''}">${esc(f.label)}${f.due_on?' · '+shortDay(f.due_on):''}</p><p class="followup-help">Registre a última conversa com resposta do cliente. Marcar uma tentativa não muda D0. Se o cliente respondeu, combine o próximo passo e uma data.</p><form id="followup-form"><div class="detail-grid"><label>Situação do acompanhamento<select name="mode">${Object.entries(followupModes).map(([key,label])=>`<option value="${key}" ${selectedMode===key?'selected':''}>${label}</option>`).join('')}</select></label><label>Data da última conversa<input type="date" name="last_conversation_on" value="${esc(f.last_conversation_on)}"></label><label data-followup-for="promised negotiation">Data do próximo contato<input type="date" name="next_on" value="${esc(f.next_on)}"></label><label data-followup-for="promised negotiation">Próximo passo<input name="next_step" maxlength="500" value="${esc(f.next_step)}" placeholder="Ex.: confirmar tamanhos do pedido"></label><label data-followup-for="paused awaiting">Data de revisão interna (opcional)<input type="date" name="review_on" value="${esc(f.review_on)}"></label><label data-followup-for="customer">Data da última compra<input type="date" name="last_purchase_on" value="${esc(f.last_purchase_on)}"></label><label data-followup-for="customer">Ciclo real de recompra (dias)<input type="number" min="1" max="730" name="cycle_days" value="${f.cycle_days}"></label></div><p class="followup-help" id="followup-mode-help"></p><div class="dialog-actions"><button type="button" class="secondary" id="restart-followup">Nova tentativa a partir da última conversa</button><button class="primary">Salvar acompanhamento</button></div><p id="followup-error" role="alert" class="field-error" hidden></p></form>${f.anchor_on?`<p class="followup-help">D0: ${shortDay(f.anchor_on)}${f.last_attempt_on?' · Última tentativa: '+shortDay(f.last_attempt_on):''}</p>`:''}${plan?`<div class="followup-progress" aria-label="Progresso das tentativas">${plan}</div>`:''}<p class="followup-help">Lojista: D0, D1, D3, D7, D14; revisão em D30. Revenda: D0, D2, D5, D10; revisão padrão D45 (janela D30–D60). Consumidor Final: D0, D1, D3, D7; depois encerra. Uma resposta suspende a sequência. Negociação ativa não encerra por idade.</p></section>`;
}
function bindFollowupDetail(c) {
  const form=$('#followup-form');if(!form)return;
  const help={awaiting:'A última conversa inicia D0. O avanço é marcado nas caixinhas abaixo. Para reiniciar no mesmo dia, use Nova tentativa.',promised:'A data combinada substitui a sequência anterior.',negotiation:'Informe a próxima ação e a data. Não há encerramento automático por idade.',customer:'Referência de 30 dias: 31–45 atenção; 46–60 risco; 61–90 inativo; acima de 90 dormente. Ajuste o ciclo conforme a reposição ou coleção.',blocked:'Sem novos lembretes de abordagem comercial para este contato.',identification:'Após 24h sem os dados, o contato fica em Qualificação pendente e sai da fila ativa.'};
  const modeChanged=()=>{
    const mode=form.elements.mode.value;
    form.querySelectorAll('[data-followup-for]').forEach(label=>{
      const show=label.dataset.followupFor.split(' ').includes(mode);label.hidden=!show;
      label.querySelectorAll('input').forEach(input=>input.disabled=!show);
    });
    $('#restart-followup').hidden=mode!=='awaiting';$('#followup-mode-help').textContent=help[mode]||'Acompanhamento interno da equipe; nenhuma mensagem é enviada por este formulário.';
  };
  modeChanged();form.elements.mode.onchange=modeChanged;
  const persist=async fields=>{
    const error=$('#followup-error');error.hidden=true;
    try {
      await api('/api/followups',{id:c.id,version:c.followup.version,...fields});
      await load();detail(c.id);toast('Acompanhamento salvo.');
    } catch(e) {error.textContent=e.message;error.hidden=false;if(e.status===409)await load();}
  };
  form.onsubmit=e=>{e.preventDefault();persist(Object.fromEntries(new FormData(form)));};
  $('#restart-followup').onclick=()=>persist({...Object.fromEntries(new FormData(form)),restart:true});
  document.querySelectorAll('[data-followup-step]').forEach(input=>input.onchange=async()=>{
    input.disabled=true;await persist({complete:input.dataset.followupStep});
    if(input.isConnected){input.checked=false;input.disabled=false;}
  });
}
