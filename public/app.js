let contacts = [],
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
const titles = {
  team: [
    "Nossa equipe",
    "Todos os membros ativos podem editar os cards e acompanhar as conversas.",
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
    stages = data.stages;
    render();
  } catch (e) {
    toast(e.message);
  }
}
async function bootstrap() {
  try {
    const me = await api("/api/me");
    currentUser = me.user;
    csrf = me.csrf;
    const [team, status] = await Promise.all([
      api("/api/team"),
      api("/api/status"),
    ]);
    teamUsers = team.users;
    systemStatus = status;
    $("#profile-name").textContent = currentUser.name;
    $("#profile-role").textContent =
      currentUser.role === "admin" ? "Administrador" : "Membro da equipe";
    $("#simulate").hidden = !status.simulation;
    document.body.dataset.auth = "ready";
    await load();
  } catch (e) {
    toast(e.message);
  }
}
function matches(c) {
  return [c.name, c.phone, c.source, c.owner].some((x) =>
    x.toLowerCase().includes(query.toLowerCase()),
  );
}
function stats() {
  const open = contacts.filter((c) => !["Ganho", "Perdido"].includes(c.stage));
  const won = contacts.filter((c) => c.stage === "Ganho");
  const withMessages = contacts.filter((c) =>
    c.messages.some((m) => m.direction === "in"),
  );
  $("#stats").innerHTML = [
    ["Contatos no CRM", contacts.length, "Todos os seus relacionamentos", "♧"],
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
  return `<button class="card" data-contact="${c.id}" draggable="true"><div class="card-top"><span class="avatar">${esc(initials(c.name))}</span>${esc(c.name)}</div><div class="card-phone">+${esc(c.phone)}</div><span class="source">${esc(c.source)}</span><div class="card-bottom"><strong>${money(c.value)}</strong><span>${c.messages.filter((m) => m.direction === "in").length} conversa(s)</span></div></button>`;
}
function banner() {
  if (!systemStatus.simulation)
    return `<div class="info-banner"><span>✓</span><div><strong>Um funil para toda a equipe.</strong><p>Todos os membros ativos podem editar os cards. As alterações são sincronizadas a cada 5 segundos; edições simultâneas são verificadas ao salvar.</p></div></div>`;
  return `<div class="info-banner"><span>↓</span><div><strong>Seu próximo cliente pode chegar de um anúncio.</strong><p>Simule uma mensagem do WhatsApp e veja o contato entrar automaticamente no funil. Nenhuma mensagem real será enviada.</p></div></div>`;
}
function render() {
  stats();
  $("#page-title").textContent = titles[view][0];
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
        `${contacts.length} contatos cadastrados`,
      ) +
      (list.length
        ? `<div class="table-wrap"><table><thead><tr><th>CONTATO</th><th>WHATSAPP</th><th>ETAPA</th><th>ORIGEM</th><th>RESPONSÁVEL</th></tr></thead><tbody>${list.map((c) => `<tr data-contact="${c.id}" tabindex="0"><td><strong>${esc(c.name)}</strong></td><td>+${esc(c.phone)}</td><td><span class="tag">${esc(c.stage)}</span></td><td>${esc(c.source)}</td><td>${esc(c.owner)}</td></tr>`).join("")}</tbody></table></div>`
        : empty(
            "Sua base começa com uma conversa.",
            "Cadastre um contato ou simule a chegada de um lead pelo WhatsApp.",
          ));
  } else if (view === "inbox") {
    const rows = list.filter((c) => c.messages.length);
    html =
      toolbar("Conversas e notas", "Histórico por contato") +
      (rows.length
        ? `<div class="panel" style="padding:0">${rows.map((c) => `<button class="inbox-item" data-contact="${c.id}"><span class="avatar">${esc(initials(c.name))}</span><div><strong>${esc(c.name)}</strong><p>${esc(c.messages.at(-1).body)}</p></div><small>${date(c.messages.at(-1).created)}</small></button>`).join("")}</div>`
        : empty(
            "Pronto para o primeiro oi.",
            "As mensagens recebidas aparecerão aqui. Use “Simular lead do anúncio” para experimentar.",
          ));
  } else if (view === "reports") {
    html = `<div class="grid-two"><div class="panel"><h3>Distribuição no funil</h3><p>Acompanhe em que etapa estão suas oportunidades.</p>${stages
      .map((s, i) => {
        const n = contacts.filter((c) => c.stage === s).length;
        return `<div class="report-row"><span>${esc(s)}</span><div class="bar"><div style="width:${contacts.length ? (n / contacts.length) * 100 : 0}%;background:${colors[i]}"></div></div><strong>${n}</strong></div>`;
      })
      .join(
        "",
      )}</div><div class="panel"><h3>Origem dos contatos</h3><p>Origem registrada no momento do cadastro.</p>${[...new Set(contacts.map((c) => c.source))].map((s) => `<div class="report-row"><span>${esc(s)}</span><div class="bar"><div style="width:${(contacts.filter((c) => c.source === s).length / contacts.length) * 100}%;background:#1269ef"></div></div><strong>${contacts.filter((c) => c.source === s).length}</strong></div>`).join("") || "<p>Os dados aparecerão após o primeiro cadastro.</p>"}</div></div>`;
  } else if (view === "team") {
    html = teamView();
  } else {
    html = settingsView();
  }
  $("#content").innerHTML = html;
  if (view === "team") bindTeam();
  $("#empty-simulate")?.addEventListener("click", () => openCreate(true));
  $("#search")?.addEventListener("input", (e) => {
    const pos = e.target.selectionStart;
    query = e.target.value;
    render();
    $("#search").focus();
    $("#search").setSelectionRange(pos, pos);
  });
  document.querySelectorAll("[data-contact]").forEach((b) => {
    b.addEventListener("click", () => detail(b.dataset.contact));
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
function openCreate(sim) {
  simulate = sim;
  $("#create-form").reset();
  $("#form-title").textContent = sim
    ? "Simular lead do anúncio"
    : "Novo contato";
  $("#form-description").textContent = sim
    ? "Teste o recebimento de uma mensagem. O telefone identifica o contato e evita duplicações."
    : "Adicione um contato ao seu funil comercial.";
  $("#body-field").hidden = !sim;
  $("#create-form").elements.body.required = sim;
  $("#create-dialog").showModal();
}
function detail(id) {
  const c = contacts.find((c) => c.id === id);
  if (!c) return;
  let ref = null;
  try {
    ref = JSON.parse(c.referral);
  } catch {}
  $("#detail").innerHTML =
    `<div class="dialog-header"><div><p class="eyebrow">CONTATO · +${esc(c.phone)}</p><h2>${esc(c.name)}</h2></div><button class="close" id="close-detail" aria-label="Fechar">×</button></div><span class="source">${esc(c.source)}</span><form id="detail-form"><div class="detail-grid"><label>Etapa do funil<select name="stage">${stages.map((s) => `<option ${c.stage === s ? "selected" : ""}>${esc(s)}</option>`).join("")}</select></label><label>Valor da oportunidade (R$)<input type="number" name="value" value="${c.value}" min="0" max="1000000000000" step="0.01" required></label><label>Responsável<select name="owner"><option>Sem responsável</option>${teamUsers
      .filter((u) => u.active)
      .map(
        (u) =>
          `<option ${u.name === c.owner ? "selected" : ""}>${esc(u.name)}</option>`,
      )
      .join(
        "",
      )}${c.owner !== "Sem responsável" && !teamUsers.some((u) => u.active && u.name === c.owner) ? `<option selected>${esc(c.owner)}</option>` : ""}</select></label><label>Observação<input name="note" value="${esc(c.note)}" maxlength="5000"></label></div><div class="dialog-actions"><button type="button" class="secondary" id="refresh-detail">Recarregar card</button><button class="primary">Salvar oportunidade</button></div></form>${ref ? `<div class="referral">↓ Origem do anúncio: ${esc(ref.headline || ref.source_id || "Anúncio Meta")}${ref.ctwa_clid ? "<br>Identificador de clique recebido da Meta." : ""}</div>` : ""}<h3>Histórico do contato</h3><div class="conversation">${c.messages.length ? c.messages.map((m) => `<div class="message ${m.direction === "note" ? "note" : ""}">${esc(m.body)}<small>${esc(m.author || "")}${m.author ? " · " : ""}${m.direction === "note" ? "Nota interna" : m.direction === "out" ? "WhatsApp enviado" : "Mensagem recebida"}${m.channel === "simulation" ? " · Simulação" : ""}${m.direction === "out" ? " · " + esc(statusLabel(m.status)) : ""} · ${date(m.created)}</small></div>`).join("") : "<p>Nenhuma mensagem ou nota registrada.</p>"}</div><form id="note-form"><label>Nova nota interna<textarea name="body" required maxlength="5000" placeholder="Registre o próximo passo ou detalhes do atendimento."></textarea></label><p>Notas ficam no CRM. Não são enviadas pelo WhatsApp.</p><div class="dialog-actions"><button class="secondary">Adicionar nota</button></div></form>${sendView(c)}${auditView(c)}`;
  $("#close-detail").onclick = () => $("#detail-dialog").close();
  $("#refresh-detail").onclick = async () => {
    await load();
    detail(id);
  };
  bindSend(c);
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
      if (view === "team") {
        try {
          teamUsers = (await api("/api/team")).users;
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
    await api(
      simulate ? "/api/simulate" : "/api/contacts",
      Object.fromEntries(new FormData(e.target)),
    );
    $("#create-dialog").close();
    await load();
    toast(
      simulate
        ? "Mensagem recebida e contato registrado no CRM."
        : "Contato criado.",
    );
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

function teamView() {
  return `<div class="panel"><h3>Pessoas com acesso</h3><p>Administradores e membros ativos podem ver todos os contatos, mover cards, editar oportunidades e registrar notas. Cada pessoa usa sua própria senha.</p><div class="table-wrap"><table><thead><tr><th>PESSOA</th><th>E-MAIL</th><th>PERFIL</th><th>SITUAÇÃO</th>${currentUser.role === "admin" ? "<th>AÇÕES</th>" : ""}</tr></thead><tbody>${teamUsers.map((u) => `<tr><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>${u.role === "admin" ? "Administrador" : "Membro"}</td><td>${u.active ? "Ativo" : "Desativado"}</td>${currentUser.role === "admin" ? `<td><button class="secondary" data-reset-user="${u.id}" ${!u.active ? "disabled" : ""}>Redefinir senha</button> ${u.id !== currentUser.id ? `<button class="secondary" data-toggle-user="${u.id}">${u.active ? "Desativar" : "Reativar"}</button>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table></div></div>${currentUser.role === "admin" ? `<div class="panel" style="margin-top:20px"><h3>Convidar alguém para a equipe</h3><p>Gere um link individual e compartilhe com a pessoa. O convite vale por 48 horas e só pode ser usado uma vez. O link não é enviado por e-mail automaticamente.</p><form id="invite-form"><div class="detail-grid"><label>E-mail da pessoa<input type="email" name="email" required autocomplete="off"></label><label>Perfil<select name="role"><option value="member">Membro · pode editar todos os cards</option><option value="admin">Administrador · também gerencia acessos</option></select></label></div><div class="dialog-actions"><button class="primary">Gerar convite</button></div></form><div id="invite-result" hidden><label>Link de acesso individual<input id="invite-link" readonly></label><p>Compartilhe somente com a pessoa convidada.</p><button id="copy-invite" class="secondary">Copiar link</button></div></div>` : '<div class="info-banner"><span>✓</span><div><strong>Você pode editar qualquer card.</strong><p>Para incluir outras pessoas ou recuperar senhas, fale com um administrador.</p></div></div>'}`;
}
function showInvite(path) {
  $("#invite-result").hidden = false;
  $("#invite-link").value = location.origin + path;
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
function settingsView() {
  return `<div class="grid-two"><div class="panel"><div class="connection"><span class="connection-icon">◉</span><div><h3>WhatsApp Business</h3><span class="status-off">${systemStatus.sending_configured ? "Credenciais configuradas · validar na Meta" : "Aguardando conexão da conta Meta"}</span></div></div><p>Número informado pela Sais Blue: <strong>+55 (54) 3443-6405</strong>. O número ainda precisa ser vinculado e validado na plataforma oficial da Meta.</p><ul class="check-list"><li>Cadastro automático por telefone</li><li>Origem do anúncio quando recebida da Meta</li><li>Recebimento com assinatura verificada</li><li>Respostas de texto dentro da janela de 24 horas</li><li>Histórico de envio, entrega e leitura</li></ul><p>As credenciais são configuradas apenas no servidor. Configuração presente não confirma conexão real. Mídias e templates ainda não estão disponíveis nesta versão.</p></div><div class="panel"><h3>Publicação e acesso da equipe</h3><p>O sistema está preparado para servidor Windows com serviço de aplicação e proxy HTTPS. O domínio, a instalação no servidor e a conta Meta precisam ser configurados para disponibilizar o acesso externo.</p><ul class="check-list"><li>Login individual e acesso por convite</li><li>Todos os membros podem editar os cards</li><li>Histórico de quem fez cada alteração</li><li>Verificação de edições simultâneas</li><li>Backup do banco por comando</li></ul><p>Webhook: <strong>/webhooks/whatsapp</strong></p><p>${systemStatus.webhook_configured ? "Recebimento configurado no servidor; falta validar eventos reais." : "Recebimento ainda sem configuração Meta."}</p></div></div>`;
}
function statusLabel(status) {
  return (
    {
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
    .filter(([, v]) => v && typeof v === "object" && "antes" in v)
    .map(
      ([k, v]) =>
        `<p>${esc({ stage: "Etapa", owner: "Responsável", value: "Valor", note: "Observação" }[k] || k)}: ${esc(v.antes)} → ${esc(v.depois)}</p>`,
    )
    .join("");
}

// getRandomValues works on a private HTTP LAN address, where randomUUID may be unavailable.
function requestKey() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
}
