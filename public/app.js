let contacts = [],
  trashContacts = [],
  stages = [],
  view = "pipeline",
  query = "",
  simulate = false,
  currentUser = null,
  csrf = "",
  teamUsers = [],
  systemStatus = {};
const colors = [
  "#5d91f6",
  "#a68ae9",
  "#edb65d",
  "#ef9177",
  "#48b49b",
  "#a0a9b7",
];
let cities = [],
  profileFilter = "",
  ownerFilter = "",
  states = [],
  leadMap = null,
  pinLayer = null,
  mapStage = "",
  mapState = "",
  boundaryData = null,
  mapSignature = "",
  currentDetailId = null;
const titles = {
  map: [
    "Mapa de leads",
    "Veja onde estão seus clientes e encontre novas oportunidades por região.",
  ],
  team: [
    "Nossa equipe",
    "Cada atendente acompanha suas oportunidades. O administrador acompanha toda a equipe.",
  ],
  pipeline: [
    "Funil de vendas",
    "Cada conversa é o começo de uma nova oportunidade.",
  ],
  inbox: [
    "Atendimento",
    "O histórico dos seus relacionamentos, em um só lugar.",
  ],
  contacts: ["Contatos", "Conheça as pessoas por trás de cada oportunidade."],
  reports: ["Visão geral", "Um olhar sobre o movimento do seu comercial."],
  trash: ["Lixeira", "Recupere oportunidades excluídas por engano."],
  settings: ["Integrações", "Conecte os canais que aproximam seus clientes."],
};
const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const money = (v) =>
  new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(v);
const initials = (n) =>
  n
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((x) => x[0] || "")
    .join("")
    .toUpperCase();
const date = (t) =>
  new Date(t * 1000).toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
function toast(s) {
  $("#toast").textContent = s;
  $("#toast").style.display = "block";
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(
    () => ($("#toast").style.display = "none"),
    4000,
  );
}
async function api(path, data) {
  const r = await fetch(
    path,
    data
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify(data),
        }
      : {},
  );
  const json = await r.json();
  if (!r.ok) {
    if (r.status === 401) {
      location.replace("/login");
      throw Error("Entre novamente.");
    }
    const error = Error(json.error || "Não foi possível carregar os dados.");
    error.status = r.status;
    throw error;
  }
  return json;
}
async function load() {
  try {
    const data = await api("/api/contacts");
    contacts = data.contacts;
    if(view==="trash" && currentUser.role==="admin") trashContacts=(await api("/api/trash")).contacts;
    if (currentDetailId && !contacts.some(c=>c.id===currentDetailId)) {
      $("#detail-dialog").close();
      $("#detail").innerHTML = "";
      currentDetailId = null;
      toast("Esta oportunidade não está mais disponível para sua conta.");
    }
    stages = data.stages;
    syncOwnerFilter();
    if (view === "map" && leadMap) {
      stats();
      refreshPins();
    } else render();
  } catch (e) {
    toast(e.message);
  }
}
async function bootstrap() {
  try {
    const me = await api("/api/me");
    currentUser = me.user;
    csrf = me.csrf;
    const [team, status, catalog] = await Promise.all([
      api("/api/team"),
      api("/api/status"),
      api("/api/cities"),
    ]);
    cities = catalog.cities;
    states = catalog.states;
    teamUsers = team.users;
    systemStatus = status;
    $("#release-version").textContent="Sais Blue CRM · "+(status.version||"versão anterior");
    $("#profile-name").textContent = currentUser.name;
    $("#profile-role").textContent =
      currentUser.role === "admin" ? "Administrador" : "Membro da equipe";
    $("#simulate").hidden = !status.simulation;
    $("#new-contact").hidden = !status.manual_contacts_enabled;
    $("#trash-nav").hidden = currentUser.role!=="admin";
    document.body.dataset.auth = "ready";
    await load();
  } catch (e) {
    toast(e.message);
  }
}
function matchesProfile(c) {
  return !profileFilter || (profileFilter === "__pending__" ? !c.lead_profile : c.lead_profile === profileFilter);
}
function syncOwnerFilter() {
  const select=$("#owner-filter");
  select.hidden=currentUser.role!=="admin" || ["team","settings","trash"].includes(view);
  if(currentUser.role!=="admin") {
    ownerFilter="";
    return;
  }
  const people=new Map(teamUsers.map(u=>[u.id,u.name+(u.active?"":" · desativada")]));
  for(const c of contacts) if(c.owner_id && !people.has(c.owner_id)) people.set(c.owner_id,c.owner);
  if(ownerFilter && ownerFilter!=="__unassigned__" && !people.has(ownerFilter)) ownerFilter="";
  select.innerHTML='<option value="">Todos os responsáveis</option><option value="__unassigned__">Sem responsável</option>'+[...people].sort((a,b)=>a[1].localeCompare(b[1],"pt-BR")).map(([id,name])=>`<option value="${esc(id)}">${esc(name)}</option>`).join("");
  select.value=ownerFilter;
}
function matchesSelection(c) {
  const ownerMatches=currentUser.role!=="admin" || !ownerFilter || (ownerFilter==="__unassigned__" ? !c.owner_id : c.owner_id===ownerFilter);
  return ownerMatches && matchesProfile(c);
}
function profileTag(profile) {
  const kind=({Lojista:"lojista",Revenda:"revenda","Consumidor Final":"consumidor"})[profile] || "pending";
  return `<span class="profile-tag ${kind}">${esc(profile || "Perfil pendente")}</span>`;
}
function ownerTag(c) {
  let tone="pending";
  if(c.owner_id) {
    const owners=systemStatus.automation?.regional_owners || {};
    let hash=0;
    for(const ch of c.owner_id) hash=(hash*31+ch.charCodeAt(0))>>>0;
    tone=c.owner_id===owners.chai ? "blue" : c.owner_id===owners.grasi ? "rose" : ["blue","rose","teal","amber","lavender"][hash%5];
  }
  return `<span class="owner-tag owner-${tone}" title="Responsável: ${esc(c.owner)}" aria-label="Responsável: ${esc(c.owner)}">${esc(c.owner)}</span>`;
}
function matches(c) {
  return matchesSelection(c) && [
    c.name,
    c.phone,
    c.source,
    c.owner,
    c.city || "",
    c.state || "",
    c.instagram || "",
    c.lead_profile || "",
  ].some((x) => x.toLowerCase().includes(query.toLowerCase()));
}
function stats() {
  const selected = contacts.filter(matchesSelection);
  const open = selected.filter((c) => !["Ganho", "Perdido"].includes(c.stage));
  const won = selected.filter((c) => c.stage === "Ganho");
  const withMessages = selected.filter((c) =>
    c.messages.some((m) => m.direction === "in"),
  );
  $("#stats").innerHTML = [
    ["Contatos no CRM", selected.length, ownerFilter && profileFilter ? "Responsável e perfil selecionados" : ownerFilter ? "Responsável selecionado" : profileFilter ? "Perfil selecionado" : "Todos os perfis", "♧"],
    ["Oportunidades abertas", open.length, "Em acompanhamento no funil", "▥"],
    [
      "Valor em negociação",
      money(open.reduce((a, c) => a + c.value, 0)),
      "Total das oportunidades abertas",
      "↑",
    ],
    [
      "Vendas conquistadas",
      money(won.reduce((a, c) => a + c.value, 0)),
      `${won.length} oportunidade(s) na etapa Ganho`,
      "✓",
    ],
  ]
    .map(
      ([label, value, note, icon]) =>
        `<div class="stat"><div class="stat-label">${label}<span class="stat-icon">${icon}</span></div><div class="stat-number">${value}</div><div class="stat-note">${note}</div></div>`,
    )
    .join("");
  $("#inbox-count").textContent = withMessages.length;
}
function toolbar(title, subtitle = "") {
  return `<div class="toolbar"><div class="toolbar-title">${title}<span>${subtitle}</span></div><input id="search" class="search" aria-label="Buscar contatos" placeholder="⌕  Buscar nome, telefone ou origem" value="${esc(query)}"></div>`;
}
function card(c) {
  return `<button class="card" data-contact="${c.id}" draggable="true"><div class="card-top"><span class="avatar">${esc(initials(c.name))}</span>${esc(c.name)}</div><div class="card-phone">+${esc(c.phone)}</div><div class="card-location ${c.location_pending ? "missing-location" : ""}">${c.location_pending ? "⚑ Cidade/UF pendentes" : "⌖ " + esc(c.city) + " / " + esc(c.state)}</div><div class="card-tags">${profileTag(c.lead_profile)}${ownerTag(c)}</div><div class="card-bottom"><strong>${money(c.value)}</strong><span>${c.messages.filter((m) => m.direction === "in").length} conversa(s)</span></div></button>`;
}
function banner() {
  if (!systemStatus.simulation)
    return `<div class="info-banner"><span>✓</span><div><strong>Entrada automática somente por anúncios.</strong><p>A origem é identificada pela Meta. Para outros clientes, use Nova oportunidade. As próximas mensagens dos contatos admitidos continuam no histórico. Cada atendente vê e edita somente suas oportunidades. O administrador vê todas, inclusive as sem responsável.</p></div></div>`;
  return `<div class="info-banner"><span>↓</span><div><strong>Seu próximo cliente pode chegar de um anúncio.</strong><p>Simule uma mensagem do WhatsApp e veja o contato entrar automaticamente no funil. Nenhuma mensagem real será enviada.</p></div></div>`;
}
function render() {
  if (leadMap) {
    leadMap.remove();
    leadMap = null;
    pinLayer = null;
  }
  syncOwnerFilter();
  stats();
  $("#stats").hidden = view==="trash";
  $("#page-title").textContent = titles[view][0];
  $("#profile-filter").hidden = ["team", "settings", "trash"].includes(view);
  $("#breadcrumb-current").textContent = titles[view][0];
  $("#page-subtitle").textContent = titles[view][1];
  document
    .querySelectorAll("nav button")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  const list = contacts.filter(matches);
  let html = "";
  if (view === "pipeline") {
    html =
      toolbar("Pipeline comercial", "Uma visão clara de cada próxima etapa") +
      `<div class="board">${stages
        .map((stage, i) => {
          const rows = list.filter((c) => c.stage === stage);
          return `<section class="column" data-stage="${esc(stage)}" style="--stage:${colors[i]}"><div class="column-head"><span>${esc(stage)}</span><b>${rows.length}</b></div><div class="column-value">${money(rows.reduce((a, c) => a + c.value, 0))}</div>${rows.map(card).join("") || '<div class="empty-column"><span>＋</span>Nenhuma oportunidade<br>nesta etapa</div>'}</section>`;
        })
        .join("")}</div>` +
      banner();
  } else if (view === "contacts") {
    html =
      toolbar(
        "Sua base de contatos",
        `${list.length} contatos encontrados`,
      ) +
      (list.length
        ? `<div class="table-wrap"><table><thead><tr><th>CONTATO</th><th>WHATSAPP</th><th>CIDADE / UF</th><th>INSTAGRAM</th><th>PERFIL</th><th>ETAPA</th><th>ORIGEM</th><th>RESPONSÁVEL</th></tr></thead><tbody>${list.map((c) => `<tr data-contact="${c.id}" tabindex="0"><td><strong>${esc(c.name)}</strong></td><td>+${esc(c.phone)}</td><td>${c.location_pending ? '<span class="missing-location">Preencher localização</span>' : esc(c.city) + " / " + esc(c.state)}</td><td>${c.instagram ? `<a href="https://www.instagram.com/${esc(c.instagram)}/" target="_blank" rel="noopener noreferrer">@${esc(c.instagram)}</a>` : "—"}</td><td>${profileTag(c.lead_profile)}</td><td><span class="tag">${esc(c.stage)}</span></td><td>${esc(c.source)}</td><td>${esc(c.owner)}</td></tr>`).join("")}</tbody></table></div>`
        : empty(
            "Sua base começa com uma conversa.",
            "Os novos contatos entram pelos anúncios identificados pela Meta.",
          ));
  } else if (view === "inbox") {
    const rows = list.filter((c) => c.messages.length);
    html =
      toolbar("Conversas e notas", "Histórico por contato") +
      (rows.length
        ? `<div class="panel" style="padding:0">${rows.map((c) => `<button class="inbox-item" data-contact="${c.id}"><span class="avatar">${esc(initials(c.name))}</span><div><strong>${esc(c.name)}</strong><p>${esc(c.messages.at(-1).body)}</p></div><small>${date(c.messages.at(-1).created)}</small></button>`).join("")}</div>`
        : empty(
            "Pronto para o primeiro oi.",
            "As mensagens dos leads vindos de anúncios aparecerão aqui.",
          ));
  } else if (view === "reports") {
    html = reportsView();
  } else if (view === "map") {
    html = mapView();
  } else if (view === "team") {
    html = teamView();
  } else if (view === "trash") {
    html = trashView();
  } else {
    html = settingsView();
  }
  $("#content").innerHTML = html;
  if (view === "team") bindTeam();
  if (view === "map") initMap();
  if (view === "settings") bindAutomation();
  if (view === "trash") bindTrash();
  $("#empty-simulate")?.addEventListener("click", () => openCreate(true));
  $("#search")?.addEventListener("input", (e) => {
    const pos = e.target.selectionStart;
    query = e.target.value;
    render();
    $("#search").focus();
    $("#search").setSelectionRange(pos, pos);
  });
  document.querySelectorAll("[data-contact]").forEach((b) => {
    b.addEventListener("click", (e) => {
      if (!e.target.closest("a")) detail(b.dataset.contact);
    });
    b.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && b.tagName === "TR") detail(b.dataset.contact);
    });
  });
  document
    .querySelectorAll(".card")
    .forEach((b) =>
      b.addEventListener("dragstart", (e) =>
        e.dataTransfer.setData("text/plain", b.dataset.contact),
      ),
    );
  document.querySelectorAll(".column").forEach((col) => {
    col.addEventListener("dragover", (e) => e.preventDefault());
    col.addEventListener("drop", async (e) => {
      e.preventDefault();
      const c = contacts.find(
        (c) => c.id === e.dataTransfer.getData("text/plain"),
      );
      if (c)
        try {
          await api("/api/update", {
            id: c.id,
            revision: c.revision,
            stage: col.dataset.stage,
          });
          await load();
          toast("Etapa atualizada.");
        } catch (err) {
          toast(err.message);
          if (err.status === 409) await load();
        }
    });
  });
}
function empty(title, body) {
  return `<div class="panel empty-state"><div class="empty-icon">◌</div><h3>${title}</h3><p>${body}</p>${systemStatus.simulation ? '<button class="secondary" id="empty-simulate">↓ Simular primeiro contato</button>' : ""}</div>`;
}
function ownerInput(c={owner_id:currentUser.id}) {
  const people=teamUsers.filter(u=>u.active && (currentUser.role==="admin" || u.id===currentUser.id));
  const empty=currentUser.role==="admin" ? '<option value="">Sem responsável</option>' : "";
  const inactive=c.owner_id && !people.some(u=>u.id===c.owner_id) && currentUser.role==="admin" ? `<option value="${esc(c.owner_id)}" selected>${esc(c.owner)} · indisponível</option>` : "";
  return `<label>Responsável<select name="owner_id">${empty}${people.map(u=>`<option value="${esc(u.id)}" ${u.id===c.owner_id?"selected":""}>${esc(u.name)}</option>`).join("")}${inactive}</select></label>`;
}
function openCreate(sim) {
  simulate = sim;
  $("#create-form").reset();
  $("#create-location-fields").innerHTML = locationInputs();
  bindLocationFields($("#create-location-fields"));
  $("#form-title").textContent = sim
    ? "Simular lead do anúncio"
    : "Nova oportunidade";
  $("#form-description").textContent = sim
    ? "Teste o recebimento de uma mensagem. O telefone identifica o contato e evita duplicações."
    : "Cadastro manual, sem iniciar o assistente. As próximas mensagens desse número aparecerão no CRM. As demais conversas comuns continuam fora.";
  $("#create-opportunity-fields").innerHTML = sim ? "" : `${profileInput({})}<label>Etapa do funil<select name="stage">${stages.map(s=>`<option>${esc(s)}</option>`).join("")}</select></label>${ownerInput()}<label>Valor da oportunidade (R$)<input type="number" name="value" value="0" min="0" max="1000000000000" step="0.01" required></label><label>Observação<input name="note" maxlength="5000"></label>`;
  $("#body-field").hidden = !sim;
  $("#create-form").elements.body.required = sim;
  $("#create-dialog").showModal();
}
function qualificationLabel(state) {
  return ({not_started:"Aguardando atendimento",waiting_profile:"Perguntando perfil",waiting_city:"Perguntando cidade/UF",completed:"Qualificação concluída",human:"Atendimento humano"})[state] || "Aguardando atendimento";
}
function profileInput(c) {
  return `<label>Perfil do cliente<select name="lead_profile"><option value="">A identificar</option>${(systemStatus.lead_profiles || ["Lojista","Revenda","Consumidor Final"]).map(p => `<option ${c.lead_profile === p ? "selected" : ""}>${esc(p)}</option>`).join("")}</select></label>`;
}
function qualificationTools(c) {
  const choices=teamUsers.filter(u=>u.active);
  const selected=c.owner_id || currentUser.id;
  const transfer=currentUser.role==="admin" ? `<label>Encaminhar para<select id="handoff-owner">${choices.map(u=>`<option value="${esc(u.id)}" ${u.id===selected?"selected":""}>${esc(u.name)}</option>`).join("")}</select></label><button class="secondary" id="handoff-contact">Encaminhar atendimento</button>` : "";
  return `<section class="qualification-panel"><strong>${esc(qualificationLabel(c.qualification_state))}</strong><p>Ao assumir, as perguntas automáticas são pausadas. Complete os dados pendentes na ficha.</p><div class="handoff-actions">${transfer}<button class="primary" id="claim-contact">Assumir atendimento</button></div></section>`;
}
function bindQualification(c) {
  const claim=async owner_id=>{
    try {
      await api("/api/claim",{id:c.id,revision:c.revision,owner_id});
      await load(); detail(c.id); toast("Responsável atualizado. Assistente pausado neste contato.");
    } catch(e) { toast(e.message); if(e.status===409 || e.status===404) { await load(); detail(c.id); } }
  };
  $("#claim-contact").onclick=()=>claim(currentUser.id);
  if($("#handoff-contact")) $("#handoff-contact").onclick=()=>claim($("#handoff-owner").value);
}
function detail(id) {
  const c = contacts.find((c) => c.id === id);
  if (!c) return;
  currentDetailId = id;
  let ref = null;
  try {
    ref = JSON.parse(c.referral);
  } catch {}
  $("#detail").innerHTML =
    `<div class="dialog-header"><div><p class="eyebrow">CONTATO · +${esc(c.phone)}</p><h2>${esc(c.name)}</h2></div><button class="close" id="close-detail" aria-label="Fechar">×</button></div><span class="source">${esc(c.source)}</span>${c.location_pending ? '<div class="location-warning">Preencha cidade e estado para mapear este cliente. O WhatsApp não informa a cidade automaticamente.</div>' : ""}${qualificationTools(c)}<form id="detail-form"><div class="detail-grid">${profileInput(c)}${locationInputs(c)}<label>Instagram<input name="instagram" value="${esc(c.instagram || "")}" placeholder="@usuario ou link do perfil" maxlength="180"></label>${c.instagram ? `<div class="instagram-link"><a href="https://www.instagram.com/${esc(c.instagram)}/" target="_blank" rel="noopener noreferrer">Abrir @${esc(c.instagram)} ↗</a></div>` : ""}<label>Etapa do funil<select name="stage">${stages.map((s) => `<option ${c.stage === s ? "selected" : ""}>${esc(s)}</option>`).join("")}</select></label><label>Valor da oportunidade (R$)<input type="number" name="value" value="${c.value}" min="0" max="1000000000000" step="0.01" required></label>${ownerInput(c)}<label>Observação<input name="note" value="${esc(c.note)}" maxlength="5000"></label></div><div class="dialog-actions"><button type="button" class="secondary" id="refresh-detail">Recarregar card</button><button class="primary">Salvar oportunidade</button></div></form>${ref ? `<div class="referral">↓ Origem do anúncio: ${esc(ref.headline || ref.source_id || "Anúncio Meta")}${ref.ctwa_clid ? "<br>Identificador de clique recebido da Meta." : ""}</div>` : ""}<h3>Histórico do contato</h3><div class="conversation">${c.messages.length ? c.messages.map((m) => `<div class="message ${m.direction === "note" ? "note" : ""}">${esc(m.body)}<small>${esc(m.author || "")}${m.author ? " · " : ""}${m.direction === "note" ? "Nota interna" : m.direction === "out" ? "WhatsApp enviado" : "Mensagem recebida"}${m.channel === "simulation" ? " · Simulação" : ""}${m.direction === "out" ? " · " + esc(statusLabel(m.status)) : ""}${m.error_code ? " · Código " + esc(m.error_code) + ": " + esc(m.error_detail) : ""} · ${date(m.created)}</small></div>`).join("") : "<p>Nenhuma mensagem ou nota registrada.</p>"}</div><form id="note-form"><label>Nova nota interna<textarea name="body" required maxlength="5000" placeholder="Registre o próximo passo ou detalhes do atendimento."></textarea></label><p>Notas ficam no CRM. Não são enviadas pelo WhatsApp.</p><div class="dialog-actions"><button class="secondary">Adicionar nota</button></div></form>${sendView(c)}${auditView(c)}`;
  $("#close-detail").onclick = () => $("#detail-dialog").close();
  $("#refresh-detail").onclick = async () => {
    await load();
    detail(id);
  };
  bindLocationFields($("#detail-form"));
  bindSend(c);
  bindQualification(c);
  if(currentUser.role==="admin") {
    const button=document.createElement("button");
    button.type="button";
    button.className="danger";
    button.id="delete-contact";
    button.textContent="Excluir card";
    $("#detail-form .dialog-actions").prepend(button);
    button.onclick=async()=>{
      if(!confirm(`Mover o card de ${c.name} para a lixeira? O atendimento automático será interrompido. Você poderá restaurar o card depois.`)) return;
      button.disabled=true;
      try {
        await api("/api/contacts/delete",{id:c.id,revision:c.revision});
        await load();
        toast("Card movido para a lixeira.");
      } catch(err) {
        toast(err.message);
        if(err.status===409 || err.status===404) { await load(); detail(id); }
      } finally {button.disabled=false;}
    };
  }
  $("#detail-form").onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    try {
      const result = await api("/api/update", {
        id,
        revision: c.revision,
        ...data,
      });
      c.revision = result.revision;
      await load();
      detail(id);
      toast("Oportunidade atualizada.");
    } catch (err) {
      toast(err.message);
      if (err.status === 409) await load();
    }
  };
  $("#note-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/api/messages", {
        id,
        body: new FormData(e.target).get("body"),
      });
      await load();
      detail(id);
      toast("Nota adicionada.");
    } catch (err) {
      toast(err.message);
    }
  };
  if (!$("#detail-dialog").open) $("#detail-dialog").showModal();
}
$("#profile-filter").onchange = (e) => {profileFilter=e.target.value; render();};
$("#owner-filter").onchange = (e) => {ownerFilter=e.target.value; render();};
$("#new-contact").onclick = () => openCreate(false);
$("#simulate").onclick = () => openCreate(true);
document
  .querySelectorAll("[data-close]")
  .forEach(
    (b) => (b.onclick = () => document.getElementById(b.dataset.close).close()),
  );
document.querySelectorAll("[data-view]").forEach(
  (b) =>
    (b.onclick = async () => {
      view = b.dataset.view;
      query = "";
      if(view==="trash") { await load(); return; }
      if (view === "team" || view === "settings") {
        try {
          teamUsers = (await api("/api/team")).users;
          systemStatus = await api("/api/status");
        } catch (e) {
          toast(e.message);
        }
      }
      render();
    }),
);
$("#create-form").onsubmit = async (e) => {
  e.preventDefault();
  const button = e.target.querySelector("[type=submit]");
  button.disabled = true;
  try {
    const created = await api(
      simulate ? "/api/simulate" : "/api/contacts",
      Object.fromEntries(new FormData(e.target)),
    );
    $("#create-dialog").close();
    await load();
    toast(
      simulate
        ? "Mensagem recebida e contato registrado no CRM."
        : "Oportunidade criada. Atendimento humano, sem mensagens automáticas.",
    );
    if (!simulate && created.id) detail(created.id);
  } catch (err) {
    toast(err.message);
  } finally {
    button.disabled = false;
  }
};
$("#logout").onclick = async () => {
  try {
    await api("/api/logout", {});
    location.replace("/login");
  } catch (e) {
    toast(e.message);
  }
};
bootstrap();
setInterval(() => {
  if (
    currentUser &&
    view !== "team" &&
    !document.querySelector("input:focus") &&
    !document.querySelector("textarea:focus") &&
    !document.querySelector("select:focus")
  )
    load();
}, 5000);

function trashView() {
  if(currentUser.role!=="admin") return '<div class="panel">Apenas o administrador acessa a lixeira.</div>';
  return `<div class="panel"><h3>Cards excluídos</h3><p>Cards na lixeira ficam fora do funil, mapa, indicadores e atendimento. Novas mensagens desses números não são gravadas enquanto estiverem excluídos. Ao restaurar, o histórico e o responsável são preservados e o atendimento continua humano.</p>${trashContacts.length?`<div class="table-wrap"><table><thead><tr><th>CLIENTE</th><th>PERFIL</th><th>RESPONSÁVEL</th><th>EXCLUÍDO EM</th><th>AÇÃO</th></tr></thead><tbody>${trashContacts.map(c=>`<tr><td><strong>${esc(c.name)}</strong><br>+${esc(c.phone)}</td><td>${profileTag(c.lead_profile)}</td><td>${ownerTag(c)}</td><td>${date(c.deleted_at)}</td><td><button class="secondary" data-restore="${esc(c.id)}">Restaurar card</button></td></tr>`).join("")}</tbody></table></div>`:'<p>A lixeira está vazia.</p>'}</div>`;
}
function bindTrash() {
  document.querySelectorAll("[data-restore]").forEach(button=>{
    button.onclick=async()=>{
      const c=trashContacts.find(c=>c.id===button.dataset.restore);
      button.disabled=true;
      try {
        await api("/api/contacts/restore",{id:c.id,revision:c.revision});
        await load();
        toast("Card restaurado. Atendimento humano mantido.");
      } catch(err) {toast(err.message); await load();}
      finally {button.disabled=false;}
    };
  });
}
function teamView() {
  return `<div class="panel"><h3>Pessoas com acesso</h3><p>Somente o administrador vê todas as oportunidades e as que estão sem responsável. Cada atendente vê e edita apenas as atribuídas à sua conta, inclusive no mapa, atendimento e indicadores.</p><div class="table-wrap"><table><thead><tr><th>PESSOA</th><th>E-MAIL</th><th>PERFIL</th><th>SITUAÇÃO</th>${currentUser.role === "admin" ? "<th>AÇÕES</th>" : ""}</tr></thead><tbody>${teamUsers.map((u) => `<tr><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>${u.role === "admin" ? "Administrador" : "Membro"}</td><td>${u.active ? "Ativo" : "Desativado"}</td>${currentUser.role === "admin" ? `<td><button class="secondary" data-reset-user="${u.id}" ${!u.active ? "disabled" : ""}>Redefinir senha</button> ${u.id !== currentUser.id ? `<button class="secondary" data-toggle-user="${u.id}">${u.active ? "Desativar" : "Reativar"}</button>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table></div></div>${currentUser.role === "admin" ? `<div class="panel" style="margin-top:20px"><h3>Convidar alguém para a equipe</h3><p>Gere um link individual e compartilhe com a pessoa. O convite vale por 48 horas e só pode ser usado uma vez. O link não é enviado por e-mail automaticamente.</p><form id="invite-form"><div class="detail-grid"><label>E-mail da pessoa<input type="email" name="email" required autocomplete="off"></label><label>Perfil<select name="role"><option value="member">Atendente · somente suas oportunidades</option></select></label></div><div class="dialog-actions"><button class="primary">Gerar convite</button></div></form><div id="invite-result" hidden><label>Link de acesso individual<input id="invite-link" readonly></label><p>Compartilhe somente com a pessoa convidada.</p><button id="copy-invite" class="secondary">Copiar link</button></div></div>` : '<div class="info-banner"><span>✓</span><div><strong>Você acessa somente suas oportunidades.</strong><p>Você também pode cadastrar oportunidades manuais para sua conta. Para transferir atendimentos ou recuperar senhas, fale com o administrador.</p></div></div>'}`;
}
function showInvite(path) {
  $("#invite-result").hidden = false;
  $("#invite-link").value = (systemStatus.team_url || location.origin) + path;
  $("#invite-link").focus();
  $("#invite-link").select();
}
function bindTeam() {
  if (currentUser.role !== "admin") return;
  $("#invite-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const result = await api(
        "/api/invites",
        Object.fromEntries(new FormData(e.target)),
      );
      showInvite(result.path);
      toast("Convite criado. Compartilhe o link individual.");
    } catch (err) {
      toast(err.message);
    }
  };
  $("#copy-invite").onclick = async () => {
    try {
      await navigator.clipboard.writeText($("#invite-link").value);
      toast("Link copiado.");
    } catch {
      $("#invite-link").select();
      toast("Selecione e copie o link.");
    }
  };
  document.querySelectorAll("[data-toggle-user]").forEach(
    (b) =>
      (b.onclick = async () => {
        const user = teamUsers.find((u) => u.id === b.dataset.toggleUser);
        try {
          await api("/api/team/update", { id: user.id, active: !user.active });
          teamUsers = (await api("/api/team")).users;
          render();
          toast("Acesso atualizado.");
        } catch (e) {
          toast(e.message);
        }
      }),
  );
  document.querySelectorAll("[data-reset-user]").forEach(
    (b) =>
      (b.onclick = async () => {
        try {
          const result = await api("/api/team/reset", {
            id: b.dataset.resetUser,
          });
          showInvite(result.path);
          toast("Link de redefinição criado. Válido por uma hora.");
        } catch (e) {
          toast(e.message);
        }
      }),
  );
}
function reportsView() {
  const selected=contacts.filter(matchesSelection);
  const profiles=["Lojista","Revenda","Consumidor Final",""];
  const profileRows=profiles.filter(p=>!profileFilter || (profileFilter==="__pending__"?!p:p===profileFilter)).map(profile=>{
    const rows=selected.filter(c=>(c.lead_profile || "")===profile);
    const open=rows.filter(c=>!["Ganho","Perdido"].includes(c.stage));
    const won=rows.filter(c=>c.stage==="Ganho");
    return `<tr data-profile-summary="${esc(profile || "pending")}"><td>${profileTag(profile)}</td><td>${rows.length}</td><td>${open.length}</td><td>${money(open.reduce((sum,c)=>sum+c.value,0))}</td><td>${won.length}</td><td>${money(won.reduce((sum,c)=>sum+c.value,0))}</td></tr>`;
  }).join("");
  return `<div class="panel"><h3>Resultados por perfil</h3><p>Compare os leads, oportunidades abertas e vendas de cada perfil. Os filtros no topo combinam perfil e responsável no funil, contatos, atendimento, mapa e indicadores.</p><div class="table-wrap"><table><thead><tr><th>PERFIL</th><th>LEADS</th><th>OPORTUNIDADES ABERTAS</th><th>VALOR EM NEGOCIAÇÃO</th><th>VENDAS</th><th>VALOR GANHO</th></tr></thead><tbody>${profileRows}</tbody></table></div></div><div class="grid-two automation-panel"><div class="panel"><h3>Distribuição no funil</h3>${stages.map((stage,i)=>{const count=selected.filter(c=>c.stage===stage).length;return `<div class="report-row"><span>${esc(stage)}</span><div class="bar"><div style="width:${selected.length?count/selected.length*100:0}%;background:${colors[i]}"></div></div><strong>${count}</strong></div>`;}).join("")}</div><div class="panel"><h3>Origem dos contatos</h3>${[...new Set(selected.map(c=>c.source))].map(source=>{const count=selected.filter(c=>c.source===source).length;return `<div class="report-row"><span>${esc(source)}</span><strong>${count}</strong></div>`;}).join("") || "<p>Os dados aparecerão após o primeiro lead.</p>"}</div></div>`;
}
function settingsView() {
  const a=systemStatus.automation || {enabled:false,assignment_mode:"regional",regional_owners:{}};
  const people=teamUsers.filter(u=>u.active);
  const select=(group,label)=>`<label>${label}<select name="${group}"><option value="">Selecione a conta da equipe</option>${people.map(u=>`<option value="${esc(u.id)}" ${a.regional_owners?.[group]===u.id?"selected":""}>${esc(u.name)}</option>`).join("")}</select></label>`;
  return `<div class="panel"><h3>Entrada automática somente por anúncios</h3><p>Novos leads entram quando a Meta envia a identificação de um anúncio para o WhatsApp oficial <strong>+55 (54) 3443-6405</strong>. Conversas comuns e o texto “vim do anúncio” não criam novos cards. As próximas mensagens de um lead já identificado continuam no histórico. Para uma indicação ou outro cliente, use <strong>Nova oportunidade</strong>: a origem será Manual, com atendimento humano e recebimento das próximas mensagens apenas desse número.</p><p>Os cadastros anteriores à atualização são preservados. Um link comum para o WhatsApp pode não trazer identificação de anúncio; valide a entrada pelo anúncio publicado.</p></div><div class="panel automation-panel"><h3>Primeiro atendimento automático</h3><p>O assistente se apresenta, pergunta Lojista, Revenda ou Consumidor Final e depois cidade/UF. As respostas confirmadas são salvas na ficha e no mapa. O cliente pode pedir ATENDENTE.</p>${currentUser.role==="admin"?`<form id="automation-form"><label class="check-option"><input type="checkbox" name="enabled" ${a.enabled?"checked":""}>Ativar o roteiro para leads de anúncios</label><label>Distribuição após qualificar<select name="assignment_mode"><option value="regional" ${a.assignment_mode==="regional"?"selected":""}>Por perfil e estado · Chai / Grasi</option><option value="manual" ${a.assignment_mode==="manual"?"selected":""}>Escolher manualmente no card</option></select></label><div class="detail-grid">${select("chai","Chai · Lojista ou Revenda de RS e SC")}${select("grasi","Grasi · demais estados e todo Consumidor Final")}</div><p>Convide Chai e Grasi em Equipe e aguarde ambas criarem suas contas para selecioná-las aqui.</p><div class="dialog-actions"><button class="primary">Salvar primeiro atendimento</button></div></form>`:`<p>Roteiro: <strong>${a.enabled?"Ativado":"Desativado"}</strong>. Um administrador configura o atendimento automático e a distribuição.</p>`}<p>Em caso de resposta não reconhecida, pedido de atendimento humano ou falha de envio, a equipe deve assumir. O roteiro usa regras fixas e funciona na janela de atendimento de 24 horas.</p></div><div class="panel automation-panel"><h3>Acesso da equipe</h3><p>Endereço do CRM: <a href="${esc(systemStatus.team_url || location.origin)}">${esc(systemStatus.team_url || location.origin)}</a></p><p>Gere um convite individual em <strong>Equipe</strong>. Cada pessoa cria sua senha e acessa pelo navegador na rede da empresa. Cada atendente vê e edita somente suas oportunidades. O administrador vê todas, inclusive as sem responsável.</p><p>Credenciais de envio: ${systemStatus.sending_configured?"configuradas":"pendentes"}. Recebimento: ${systemStatus.webhook_configured?"configurado":"pendente"}.</p></div>`;
}
function bindAutomation() {
  const form=$("#automation-form");
  if(!form) return;
  form.onsubmit=async(e)=>{
    e.preventDefault();
    const fields=new FormData(form);
    try {
      const result=await api("/api/automation",{enabled:form.elements.enabled.checked,assignment_mode:fields.get("assignment_mode"),regional_owners:{chai:fields.get("chai"),grasi:fields.get("grasi")}});
      systemStatus.automation=result.automation;
      toast("Primeiro atendimento salvo.");
    } catch(err) {toast(err.message);}
  };
}
function statusLabel(status) {
  return (
    {
      queued: "Aguardando envio",
      sending: "Enviando",
      cancelled: "Cancelada · equipe assume",
      pending: "Em processamento",
      accepted: "Aceita pela Meta",
      sent: "Enviada",
      delivered: "Entregue",
      read: "Lida",
      failed: "Falhou",
      uncertain: "Sem confirmação",
    }[status] || status
  );
}
function sendView(c) {
  if (!systemStatus.sending_configured)
    return '<p class="send-info">O envio de mensagens estará disponível após conectar a conta oficial do WhatsApp.</p>';
  const last = c.messages
    .filter((m) => m.direction === "in" && m.channel === "meta")
    .reduce((a, m) => Math.max(a, m.created), 0);
  if (Date.now() / 1000 - last >= 86400)
    return '<p class="send-info">Janela de atendimento encerrada. Aguarde nova mensagem do cliente para responder por texto. Templates ainda não estão disponíveis.</p>';
  return `<form id="send-form"><label>Responder pelo WhatsApp<textarea name="body" required maxlength="4096" placeholder="Escreva a mensagem para o cliente."></textarea></label><p>Esta mensagem será enviada ao WhatsApp do contato pela conta conectada.</p><div class="dialog-actions"><button class="primary">Enviar pelo WhatsApp</button></div></form>`;
}
function bindSend(c) {
  const form = $("#send-form");
  if (!form) return;
  const requestId = requestKey();
  form.onsubmit = async (e) => {
    e.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    try {
      const response = await api("/api/send", {
        id: c.id,
        body: form.elements.body.value,
        request_id: requestId,
      });
      await load();
      detail(c.id);
      toast(
        response.status === "accepted"
          ? "Mensagem aceita pela Meta."
          : "Situação do envio: " + statusLabel(response.status),
      );
    } catch (err) {
      toast(err.message);
      await load();
      button.disabled = false;
    }
  };
}
function auditView(c) {
  return `<h3>Atividade da equipe</h3><div class="activity">${c.audit?.length ? c.audit.map((a) => `<div><strong>${esc(a.actor)}</strong> · ${esc(a.action)}<small>${date(a.created)}</small>${auditDetails(a.details)}</div>`).join("") : "<p>As próximas alterações serão registradas aqui.</p>"}</div>`;
}
function auditDetails(raw) {
  let details;
  try {
    details = JSON.parse(raw);
  } catch {
    return "";
  }
  return Object.entries(details)
    .filter(
      ([k, v]) => k !== "city_id" && v && typeof v === "object" && "antes" in v,
    )
    .map(
      ([k, v]) =>
        `<p>${esc({ stage: "Etapa", owner: "Responsável", value: "Valor", note: "Observação", city: "Cidade", state: "Estado", instagram: "Instagram", city_id: "Município" }[k] || k)}: ${esc(v.antes)} → ${esc(v.depois)}</p>`,
    )
    .join("");
}

// getRandomValues works on a private HTTP LAN address, where randomUUID may be unavailable.
function requestKey() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function locationInputs(c = {}) {
  return `<label>Estado / UF <span class="required">*</span><select name="state_picker" data-location-state required><option value="">Selecione o estado</option>${states.map((s) => `<option value="${s}" ${s === c.state ? "selected" : ""}>${s}</option>`).join("")}</select></label><label>Cidade <span class="required">*</span><select name="city_id" data-location-city required ${!c.state ? "disabled" : ""}><option value="">Selecione a cidade</option>${cities
    .filter((city) => city.state === c.state)
    .map(
      (city) =>
        `<option value="${city.id}" ${city.id === c.city_id ? "selected" : ""}>${esc(city.name)}</option>`,
    )
    .join("")}</select></label>`;
}
function bindLocationFields(container) {
  const state = container.querySelector("[data-location-state]"),
    city = container.querySelector("[data-location-city]");
  state.onchange = () => {
    city.disabled = !state.value;
    city.innerHTML =
      '<option value="">Selecione a cidade</option>' +
      cities
        .filter((c) => c.state === state.value)
        .map((c) => `<option value="${c.id}">${esc(c.name)}</option>`)
        .join("");
  };
}
function mapView() {
  return `<div class="toolbar map-toolbar"><div class="toolbar-title">Onde estão seus clientes<span>Pins na sede do município; não representam o endereço exato.</span></div><div class="map-filters"><select id="map-state" aria-label="Filtrar mapa por estado"><option value="">Todos os estados</option>${states.map((s) => `<option ${s === mapState ? "selected" : ""}>${s}</option>`).join("")}</select><select id="map-stage" aria-label="Filtrar mapa por etapa"><option value="">Todas as etapas</option>${stages.map((s) => `<option ${s === mapStage ? "selected" : ""}>${esc(s)}</option>`).join("")}</select><button class="secondary" id="fit-map">Enquadrar pins</button></div></div><div class="map-layout"><section class="map-canvas-wrap"><div id="lead-map" aria-label="Mapa geográfico dos leads"></div><div id="map-status" role="status">Mapa por município · carregando cartografia</div></section><section class="panel map-summary"><p class="eyebrow">COBERTURA COMERCIAL</p><h3 id="map-count">Localizando clientes</h3><p id="map-pending-count"></p><div id="map-city-list"></div><div id="map-pending-list"></div></section></div><p class="map-footnote">A cidade é selecionada de um catálogo de municípios brasileiros. Contatos e nomes não são enviados a serviços de geocodificação. O mapa inicia com cartografia local. Para ver ruas, use o seletor de camadas no canto superior direito; essa opção depende do OpenStreetMap e de internet.</p>`;
}
async function initMap() {
  if (!window.L) {
    $("#lead-map").textContent =
      "Não foi possível carregar o mapa. Recarregue a página.";
    return;
  }
  const instance = L.map("lead-map", { scrollWheelZoom: true }).setView(
    [-14.2, -51.9],
    4,
  );
  leadMap = instance;
  mapSignature = "",
  currentDetailId = null;
  const localBase = L.layerGroup().addTo(instance);
  pinLayer = L.layerGroup().addTo(instance);
  const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    referrerPolicy: "strict-origin-when-cross-origin",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
  });
  const tileStatus = () => {
    if (leadMap === instance && $("#map-status"))
      $("#map-status").textContent = "OpenStreetMap · pins por município";
  };
  let unavailable = false;
  tiles.on("load", () => {
    if (!unavailable) tileStatus();
  });
  tiles.on("tileerror", () => {
    if (leadMap !== instance || unavailable) return;
    unavailable = true;
    if (instance.hasLayer(tiles)) instance.removeLayer(tiles);
    if (!instance.hasLayer(localBase)) localBase.addTo(instance);
    if (leadMap === instance && $("#map-status"))
      $("#map-status").textContent =
        "Limites estaduais locais · camada de ruas indisponível";
  });
  instance.on("baselayerchange", event => {
    if(leadMap!==instance)return;
    if(event.layer===tiles){unavailable=false;$("#map-status").textContent="Carregando ruas · OpenStreetMap";}
    else $("#map-status").textContent="Mapa local · municípios e limites estaduais";
  });
  try {
    if (!boundaryData) {
      const response = await fetch("/data/brazil-states.geojson");
      if (!response.ok) throw Error("Cartografia indisponível");
      boundaryData = await response.json();
    }
    if (leadMap !== instance) return;
    const outline = L.geoJSON(boundaryData, {
      style: {
        color: "#819cbe",
        weight: 1,
        fillColor: "#eaf1f8",
        fillOpacity: 0.35,
      },
      onEachFeature: (feature, layer) =>
        layer.bindTooltip(feature.properties.sigla, { permanent: true, direction: "center", className: "state-label" }),
    }).addTo(instance);
    outline.bringToBack();
    L.control
      .layers(
        { "Mapa local": localBase, "Ruas · OpenStreetMap": tiles },
        { "Limites estaduais": outline },
        { collapsed: true },
      )
      .addTo(instance);
  } catch {
    if (leadMap === instance)
      toast(
        "Limites estaduais não carregaram. Verifique a instalação dos arquivos de dados.",
      );
  }
  if (leadMap !== instance) return;
  $("#map-status").textContent="Mapa local · municípios e limites estaduais";
  $("#map-state").onchange = (e) => {
    mapState = e.target.value;
    refreshPins(true);
  };
  $("#map-stage").onchange = (e) => {
    mapStage = e.target.value;
    refreshPins(true);
  };
  $("#fit-map").onclick = () => refreshPins(true);
  refreshPins(true);
  requestAnimationFrame(() => instance.invalidateSize());
}
function mapContacts() {
  return contacts.filter(
    (c) =>
      matchesSelection(c) &&
      (!mapState || c.state === mapState) &&
      (!mapStage || c.stage === mapStage),
  );
}
function refreshPins(fit = false) {
  if (!leadMap || !pinLayer) return;
  const signature = JSON.stringify([
    mapState,
    mapStage,
    profileFilter,
    ownerFilter,
    contacts.map((c) => [c.id, c.revision, c.city_id, c.location_pending]),
  ]);
  if (!fit && signature === mapSignature) return;
  mapSignature = signature;
  pinLayer.clearLayers();
  const list = mapContacts(),
    located = list.filter((c) => !c.location_pending),
    pending = list.filter((c) => c.location_pending);
  const groups = new Map();
  for (const c of located) {
    if (!groups.has(c.city_id)) groups.set(c.city_id, []);
    groups.get(c.city_id).push(c);
  }
  const bounds = [];
  for (const rows of groups.values()) {
    const c = rows[0],
      label = c.city + " / " + c.state;
    const icon = L.divIcon({
      className: "lead-pin-wrap",
      html: `<div class="lead-pin"><span>${rows.length}</span></div>`,
      iconSize: [36, 44],
      iconAnchor: [18, 43],
    });
    const marker = L.marker([c.latitude, c.longitude], {
      icon,
      title: label + " · " + rows.length + " lead(s)",
    }).addTo(pinLayer);
    const popup = document.createElement("div");
    popup.className = "city-popup";
    const heading = document.createElement("strong");
    heading.textContent = label;
    popup.append(heading);
    const note = document.createElement("p");
    note.textContent = rows.length + " lead(s) neste município";
    popup.append(note);
    for (const contact of rows) {
      const button = document.createElement("button");
      button.className = "popup-lead";
      button.textContent = contact.name + " · " + contact.stage;
      button.onclick = () => detail(contact.id);
      popup.append(button);
    }
    marker.bindPopup(popup, { maxWidth: 320 });
    marker.bindTooltip(label, {
      permanent: groups.size <= 12,
      direction: "top",
      offset: [0, -36],
      className: "map-city-label",
    });
    bounds.push([c.latitude, c.longitude]);
  }
  $("#map-count").textContent =
    located.length + " lead(s) em " + groups.size + " cidade(s)";
  const allPending = contacts.filter((c) => matchesSelection(c) && c.location_pending);
  $("#map-pending-count").textContent = allPending.length
    ? allPending.length + " contato(s) ainda precisam de cidade/UF."
    : "Todos os contatos têm cidade e estado preenchidos.";
  $("#map-city-list").innerHTML =
    [...groups.values()]
      .sort((a, b) => b.length - a.length)
      .map(
        (rows) =>
          `<button class="map-city" data-city="${rows[0].city_id}"><span>${esc(rows[0].city)} / ${esc(rows[0].state)}</span><b>${rows.length}</b></button>`,
      )
      .join("") || "<p>Nenhum lead localizado para este filtro.</p>";
  // Keep unlocated contacts visible even when a state filter excludes them: no lead is silently hidden.
  $("#map-pending-list").innerHTML = allPending.length
    ? `<h4>Localização pendente</h4>${allPending.map((c) => `<button class="pending-lead" data-pending="${c.id}">${esc(c.name)}<small>Preencher cidade / UF</small></button>`).join("")}`
    : "";
  document.querySelectorAll("[data-city]").forEach(
    (b) =>
      (b.onclick = () => {
        const c = groups.get(b.dataset.city)[0];
        leadMap.setView([c.latitude, c.longitude], 9);
      }),
  );
  document
    .querySelectorAll("[data-pending]")
    .forEach((b) => (b.onclick = () => detail(b.dataset.pending)));
  if (fit && bounds.length) {
    leadMap.fitBounds(bounds, { padding: [45, 45], maxZoom: 8, animate: false });
  } else if (fit) {
    leadMap.setView([-14.2, -51.9], 4);
  }
}
