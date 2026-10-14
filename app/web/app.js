const root = document.querySelector("#app");
const modal = document.querySelector("#modal");
const stages = {
  lead: "Lead mới",
  qualified: "Đủ điều kiện",
  demo_scheduled: "Đã hẹn demo",
  demo_completed: "Hoàn tất demo",
  proposal: "Đề xuất",
  negotiation: "Đàm phán",
  contract: "Hợp đồng",
  won: "Đã thắng",
  lost: "Đã mất",
  on_hold: "Tạm dừng",
};
const statuses = {
  new: "Mới",
  enriched: "Đã bổ sung",
  contacted: "Đã liên hệ",
  replied: "Đã phản hồi",
  interested: "Quan tâm",
  demo_scheduled: "Đã hẹn demo",
  demo_completed: "Hoàn tất demo",
  proposal_sent: "Đã gửi đề xuất",
  negotiating: "Đàm phán",
  won: "Đã thắng",
  lost: "Đã mất",
  unqualified: "Không phù hợp",
  bounced: "Email lỗi",
  opted_out: "Ngừng liên hệ",
};
const state = {
  token: sessionStorage.getItem("chatask-token"),
  user: null,
  view: "dashboard",
  page: 1,
  search: "",
  status: "",
  leads: [],
  pipeline: null,
};
let renderVersion = 0;
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const money = (value, currency = "VND") =>
  new Intl.NumberFormat("vi-VN", { style: "currency", currency }).format(
    value || 0,
  );
const date = (value) => (value ? new Date(value).toLocaleString("vi-VN") : "—");
const options = (values, selected) =>
  Object.entries(values)
    .map(
      ([key, label]) =>
        `<option value="${escape(key)}" ${key === selected ? "selected" : ""}>${escape(label)}</option>`,
    )
    .join("");
const badge = (value) =>
  `<span class="badge ${value === "lost" ? "lost" : ""}">${escape(statuses[value] || stages[value] || value)}</span>`;
function toast(message) {
  const el = document.querySelector("#toast");
  el.textContent = message;
  el.style.display = "block";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.style.display = "none"), 3500);
}
function logout() {
  state.token = null;
  state.user = null;
  sessionStorage.removeItem("chatask-token");
  modal.close();
  renderVersion++;
  login();
}
async function api(path, method = "GET", data) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (data && !(data instanceof URLSearchParams))
    headers["Content-Type"] = "application/json";
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body:
      data instanceof URLSearchParams
        ? data
        : data
          ? JSON.stringify(data)
          : undefined,
  });
  if (response.status === 401 && path !== "/auth/login") {
    logout();
    throw new Error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
  }
  const result = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    let detail =
      result.detail || result.message || "Không thể thực hiện yêu cầu.";
    if (Array.isArray(detail))
      detail = detail
        .map((x) => `${x.loc.slice(1).join(".")}: ${x.msg}`)
        .join("\n");
    throw new Error(
      typeof detail === "string" ? detail : "Dữ liệu không hợp lệ.",
    );
  }
  return result;
}
function login() {
  root.innerHTML = `<div class="login"><section class="login-story"><div class="brand">ChaTask<span>.</span></div><div><div class="eyebrow">Sales workspace</div><h1>Biến cơ hội thành<br><em>mối quan hệ.</em></h1><p>Một không gian chung cho khách hàng, cơ hội và những bước tiến mỗi ngày của đội ngũ bán hàng.</p></div><footer class="muted">B2B Sales Pipeline · ChaTask</footer></section><section class="login-form"><div class="eyebrow">Chào mừng trở lại</div><h1>Đăng nhập workspace</h1><p class="muted">Tiếp tục hành trình cùng khách hàng của bạn.</p><form id="login-form"><label>Email<input name="username" type="email" autocomplete="username" required placeholder="ban@congty.vn"></label><label>Mật khẩu<input name="password" type="password" autocomplete="current-password" required></label><div class="error" id="login-error" role="alert"></div><button class="primary">Đăng nhập →</button></form><small>Chưa có tài khoản? Liên hệ quản trị viên để được cấp quyền truy cập.</small></section></div>`;
  document.querySelector("#login-form").onsubmit = async (event) => {
    event.preventDefault();
    const button = event.target.querySelector("button");
    button.disabled = true;
    document.querySelector("#login-error").textContent = "";
    try {
      const result = await api(
        "/auth/login",
        "POST",
        new URLSearchParams(new FormData(event.target)),
      );
      state.token = result.access_token;
      sessionStorage.setItem("chatask-token", state.token);
      state.user = await api("/auth/me");
      state.view = "dashboard";
      await render();
    } catch (error) {
      const target = document.querySelector("#login-error");
      if (target) target.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
}
function shell() {
  root.innerHTML = `<div class="shell"><aside class="sidebar"><div><div class="brand">ChaTask<span>.</span></div><p class="eyebrow" style="margin-top:8px">Sales workspace</p></div><nav aria-label="Điều hướng chính">${[
    ["dashboard", "◈ Tổng quan"],
    ["leads", "▤ Khách hàng"],
    ["pipeline", "▥ Pipeline"],
  ]
    .map(
      ([key, label]) =>
        `<button data-nav="${key}" class="${state.view === key ? "active" : ""}" ${state.view === key ? 'aria-current="page"' : ""}>${label}</button>`,
    )
    .join(
      "",
    )}</nav><div class="account"><div><strong>${escape(state.user.full_name)}</strong><div class="secondary-text" style="color:#bed0c3">${escape(state.user.email)}</div></div><button id="logout">Đăng xuất</button></div></aside><main class="main"><div class="topbar"><span class="muted">WORKSPACE / BÁN HÀNG B2B</span><span><i class="dot"></i>${escape(state.user.role)}</span></div><div id="content" aria-live="polite"><div class="loading">Đang tải dữ liệu…</div></div></main></div>`;
  root.querySelectorAll("[data-nav]").forEach(
    (button) =>
      (button.onclick = () => {
        state.view = button.dataset.nav;
        render();
      }),
  );
  document.querySelector("#logout").onclick = logout;
}
async function render() {
  const version = ++renderVersion;
  shell();
  try {
    let html;
    if (state.view === "dashboard") html = await dashboard();
    else if (state.view === "leads") html = await leadList();
    else html = await pipeline();
    if (version !== renderVersion || !state.token) return;
    document.querySelector("#content").innerHTML = html;
    bind();
  } catch (error) {
    if (version !== renderVersion || !state.token) return;
    document.querySelector("#content").innerHTML =
      `<div class="panel"><h2>Chưa thể tải dữ liệu</h2><p class="error">${escape(error.message)}</p><button id="retry">Thử lại</button></div>`;
    document.querySelector("#retry").onclick = render;
  }
}
const heading = (title, subtitle, button) =>
  `<header class="heading"><div><div class="eyebrow">Sales workspace</div><h1>${title}</h1><p>${subtitle}</p></div>${button || ""}</header>`;
const newLeadButton =
  '<button class="primary" data-action="new-lead">＋ Thêm khách hàng</button>';
function rows(leads) {
  return leads
    .map(
      (lead) =>
        `<tr><td><button class="link-button" data-lead="${lead.id}">${escape(lead.company_name)}</button><span class="secondary-text">${escape(lead.domain || "Chưa có website")}</span></td><td>${escape(lead.industry || "—")}</td><td>${escape(lead.city || "—")}</td><td>${badge(lead.status)}</td><td>${escape(lead.primary_email || "—")}</td></tr>`,
    )
    .join("");
}
function table(leads) {
  return leads.length
    ? `<div class="table-wrap"><table><thead><tr><th>Doanh nghiệp</th><th>Ngành</th><th>Địa điểm</th><th>Trạng thái</th><th>Email</th></tr></thead><tbody>${rows(leads)}</tbody></table></div>`
    : '<div class="empty"><h3>Chưa có khách hàng</h3><p>Thêm doanh nghiệp đầu tiên để bắt đầu quản lý cơ hội.</p></div>';
}
async function dashboard() {
  const [leads, stats, p] = await Promise.all([
    api("/leads?page_size=5"),
    api("/deals/stats"),
    api("/deals/pipeline"),
  ]);
  return (
    heading(
      "Một ngày tốt để kết nối.",
      "Theo dõi khách hàng và các cơ hội đang tiến triển.",
      newLeadButton,
    ) +
    `<div class="metrics"><article class="metric"><span class="muted">Khách hàng tiềm năng</span><strong>${leads.total}</strong><small>Trong phạm vi bạn quản lý</small></article><article class="metric"><span class="muted">Cơ hội bán hàng</span><strong>${stats.total_deals}</strong><small>${stats.won} đã thắng · ${stats.lost} đã mất</small></article><article class="metric"><span class="muted">Giá trị cơ hội · VND</span><strong>${money(stats.total_value)}</strong><small>Tổng giá trị deal</small></article></div><div class="split"><section class="panel"><div class="panel-title"><h2>Khách hàng gần đây</h2><button data-nav="leads">Xem tất cả →</button></div>${table(leads.items)}</section><section class="panel"><div class="panel-title"><h2>Tiến độ pipeline</h2></div><div class="bars">${Object.entries(
      stages,
    )
      .map(
        ([key, label]) =>
          `<div><div class="bar-label"><span>${label}</span><strong>${p.totals[key] || 0}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${stats.total_deals ? ((p.totals[key] || 0) / stats.total_deals) * 100 : 0}%"></div></div></div>`,
      )
      .join("")}</div></section></div>`
  );
}
async function leadList() {
  const query = new URLSearchParams({ page: state.page, page_size: 15 });
  if (state.search) query.set("search", state.search);
  if (state.status) query.set("status", state.status);
  const data = await api("/leads?" + query);
  state.leads = data.items;
  return (
    heading(
      "Khách hàng tiềm năng",
      "Hiểu khách hàng. Tìm cơ hội. Xây dựng kết nối.",
      newLeadButton,
    ) +
    `<section class="panel"><div class="toolbar"><form id="search-form"><input name="search" value="${escape(state.search)}" aria-label="Tìm khách hàng" placeholder="Tìm tên công ty, domain hoặc email…"><button>Tìm kiếm</button></form><select id="status-filter" aria-label="Lọc trạng thái" style="width:180px"><option value="">Tất cả trạng thái</option>${options(statuses, state.status)}</select></div>${table(data.items)}<div class="pager"><span>${data.total} khách hàng · Trang ${data.page}/${Math.max(1, data.total_pages)}</span><div><button data-page="${state.page - 1}" ${state.page <= 1 ? "disabled" : ""}>← Trước</button> <button data-page="${state.page + 1}" ${state.page >= data.total_pages ? "disabled" : ""}>Sau →</button></div></div></section>`
  );
}
async function pipeline() {
  const data = await api("/deals/pipeline");
  state.pipeline = data;
  return (
    heading(
      "Pipeline bán hàng",
      "Kéo cơ hội sang giai đoạn mới hoặc mở để cập nhật.",
      '<button class="primary" data-action="new-deal">＋ Tạo cơ hội</button>',
    ) +
    `<div class="board">${Object.entries(stages)
      .map(
        ([key, label]) =>
          `<section class="column" data-stage="${key}" aria-label="${label}"><div class="column-head"><span>${label}</span><span class="badge">${data.totals[key] || 0}</span></div>${(data.stages[key] || []).map((deal) => `<button class="deal-card" draggable="true" data-deal="${deal.id}"><h3>${escape(deal.name)}</h3><p>${escape(deal.lead_name || "Xem thông tin khách hàng →")}</p><strong>${money(deal.value, deal.currency)}</strong><small>${deal.probability}%</small></button>`).join("")}${!data.totals[key] ? '<div class="empty" style="padding:22px 0;font-size:12px">Chưa có cơ hội</div>' : ""}</section>`,
      )
      .join("")}</div>`
  );
}
function bind() {
  root.querySelectorAll("[data-nav]").forEach(
    (button) =>
      (button.onclick = () => {
        state.view = button.dataset.nav;
        render();
      }),
  );
  root
    .querySelectorAll('[data-action="new-lead"]')
    .forEach((button) => (button.onclick = () => leadForm()));
  root
    .querySelectorAll('[data-action="new-deal"]')
    .forEach((button) => (button.onclick = () => dealForm()));
  root
    .querySelectorAll("[data-lead]")
    .forEach(
      (button) => (button.onclick = () => showLead(button.dataset.lead)),
    );
  root.querySelectorAll("[data-deal]").forEach((button) => {
    button.onclick = () => showDeal(button.dataset.deal);
    button.ondragstart = (event) => {
      event.dataTransfer.setData("text/plain", button.dataset.deal);
      event.dataTransfer.effectAllowed = "move";
    };
  });
  root.querySelectorAll("[data-page]").forEach(
    (button) =>
      (button.onclick = () => {
        state.page = Number(button.dataset.page);
        render();
      }),
  );
  const search = root.querySelector("#search-form");
  if (search)
    search.onsubmit = (event) => {
      event.preventDefault();
      state.search = new FormData(search).get("search").trim();
      state.page = 1;
      render();
    };
  const filter = root.querySelector("#status-filter");
  if (filter)
    filter.onchange = () => {
      state.status = filter.value;
      state.page = 1;
      render();
    };
  root.querySelectorAll("[data-stage]").forEach((column) => {
    column.ondragover = (event) => {
      event.preventDefault();
      column.classList.add("drag-over");
    };
    column.ondragleave = () => column.classList.remove("drag-over");
    column.ondrop = async (event) => {
      event.preventDefault();
      column.classList.remove("drag-over");
      const id = event.dataTransfer.getData("text/plain");
      if (
        !Object.values(state.pipeline.stages)
          .flat()
          .some((d) => d.id === id)
      )
        return;
      try {
        await api(`/deals/${id}/stage`, "PATCH", {
          stage: column.dataset.stage,
        });
        toast("Đã cập nhật giai đoạn");
        await render();
      } catch (error) {
        toast(error.message);
      }
    };
  });
}
function openModal(title, body) {
  modal.innerHTML = `<div class="modal-head"><h2 id="modal-title">${escape(title)}</h2><button class="close" aria-label="Đóng">✕</button></div>${body}`;
  modal.querySelector(".close").onclick = () => modal.close();
  if (!modal.open) modal.showModal();
}
const field = (name, label, value = "", type = "text", required = false) =>
  `<label>${label}<input name="${name}" type="${type}" value="${escape(value)}" ${required ? "required" : ""} ${type === "number" ? 'min="0" step="any"' : ""}></label>`;
function formActions() {
  return '<div class="error full" role="alert"></div><div class="form-actions full"><button type="button" data-cancel>Hủy</button><button class="primary" type="submit">Lưu thay đổi</button></div>';
}
function bindForm(save) {
  const form = modal.querySelector("form");
  form.querySelector("[data-cancel]").onclick = () => modal.close();
  form.onsubmit = async (event) => {
    event.preventDefault();
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    form.querySelector(".error").textContent = "";
    try {
      await save(Object.fromEntries(new FormData(form)));
    } catch (error) {
      form.querySelector(".error").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
}
function leadForm(lead) {
  openModal(
    lead ? "Chỉnh sửa khách hàng" : "Thêm khách hàng",
    `<form class="form-grid">${field("company_name", "Tên doanh nghiệp", lead?.company_name, "text", true)}${field("industry", "Ngành nghề", lead?.industry)}${field("city", "Tỉnh / thành phố", lead?.city)}${field("domain", "Domain", lead?.domain)}${field("primary_contact_name", "Người liên hệ", lead?.primary_contact_name)}${field("primary_email", "Email liên hệ", lead?.primary_email, "email")}${field("primary_phone", "Số điện thoại", lead?.primary_phone)}<label>Trạng thái<select name="status" aria-label="Trạng thái">${options(statuses, lead?.status || "new")}</select></label><label class="full">Ghi chú<textarea name="notes">${escape(lead?.notes)}</textarea></label>${formActions()}</form>`,
  );
  bindForm(async (data) => {
    Object.keys(data).forEach((key) => {
      if (data[key] === "") data[key] = null;
    });
    if (!lead) delete data.status;
    const result = await api(
      lead ? `/leads/${lead.id}` : "/leads",
      lead ? "PATCH" : "POST",
      data,
    );
    modal.close();
    toast("Đã lưu khách hàng");
    await render();
    await showLead(result.id);
  });
}
async function showLead(id) {
  try {
    const [lead, deals] = await Promise.all([
      api(`/leads/${id}`),
      api(`/deals?lead_id=${id}&page_size=30`),
    ]);
    openModal(
      lead.company_name,
      `<div class="details"><dl><div><dt>NGƯỜI LIÊN HỆ</dt><dd>${escape(lead.primary_contact_name || "Chưa có")}</dd></div><div><dt>EMAIL</dt><dd>${escape(lead.primary_email || "Chưa có")}</dd></div><div><dt>SỐ ĐIỆN THOẠI</dt><dd>${escape(lead.primary_phone || "Chưa có")}</dd></div></dl><dl><div><dt>TRẠNG THÁI</dt><dd>${badge(lead.status)}</dd></div><div><dt>NGÀNH / ĐỊA ĐIỂM</dt><dd>${escape(lead.industry || "—")} · ${escape(lead.city || "—")}</dd></div><div><dt>ĐƯỢC THÊM</dt><dd>${date(lead.created_at)}</dd></div></dl></div><hr style="border:0;border-top:1px solid var(--line);margin:24px 0"><h3>Ghi chú</h3><p class="note muted">${escape(lead.notes || "Chưa có ghi chú cho khách hàng này.")}</p><h3>Cơ hội bán hàng · ${deals.total}</h3>${deals.items.length ? deals.items.map((d) => `<button class="deal-card" data-related-deal="${d.id}"><h3>${escape(d.name)}</h3><p>${stages[d.stage] || escape(d.stage)}</p><strong>${money(d.value, d.currency)}</strong></button>`).join("") : `<p class="muted">Chưa có cơ hội. Tạo deal sau khi xác định nhu cầu của khách hàng.</p>`}<div class="form-actions"><button id="edit-lead">Chỉnh sửa</button><button class="primary" id="lead-deal">＋ Tạo cơ hội</button></div>`,
    );
    modal
      .querySelectorAll("[data-related-deal]")
      .forEach(
        (button) =>
          (button.onclick = () => showDeal(button.dataset.relatedDeal)),
      );
    modal.querySelector("#edit-lead").onclick = () => leadForm(lead);
    modal.querySelector("#lead-deal").onclick = () => dealForm(lead);
  } catch (error) {
    toast(error.message);
  }
}
async function dealForm(lead) {
  try {
    openModal(
      "Tạo cơ hội bán hàng",
      '<div class="loading">Đang tải khách hàng…</div>',
    );
    let selected = lead;
    openModal(
      "Tạo cơ hội bán hàng",
      `<form class="form-grid">${field("name", "Tên cơ hội", "", "text", true)}${field("value", "Giá trị · VND", 0, "number")}<label class="full">Khách hàng<input id="deal-lead-search" placeholder="Nhập tên để tìm khách hàng" aria-label="Tìm khách hàng cho deal"><select name="lead_id" id="deal-leads" aria-label="Khách hàng cho deal" required>${selected ? `<option value="${selected.id}">${escape(selected.company_name)}</option>` : '<option value="">Chọn khách hàng</option>'}</select></label><label>Giai đoạn<select name="stage" aria-label="Giai đoạn">${options(stages, "lead")}</select></label>${field("probability", "Xác suất thành công · %", 10, "number")}<label class="full">Mô tả<textarea name="description"></textarea></label>${formActions()}</form>`,
    );
    modal.querySelector('[name="probability"]').max = 100;
    const input = modal.querySelector("#deal-lead-search");
    const select = modal.querySelector("#deal-leads");
    let searchVersion = 0;
    async function searchLeads() {
      const version = ++searchVersion;
      try {
        const results = await api(
          "/leads?" +
            new URLSearchParams({ page_size: 30, search: input.value }),
        );
        if (version !== searchVersion || !select.isConnected) return;
        select.innerHTML =
          (selected
            ? `<option value="${selected.id}">${escape(selected.company_name)}</option>`
            : '<option value="">Chọn khách hàng</option>') +
          results.items
            .filter((x) => x.id !== selected?.id)
            .map(
              (x) =>
                `<option value="${x.id}">${escape(x.company_name)}</option>`,
            )
            .join("");
      } catch (error) {
        toast(error.message);
      }
    }
    let timer;
    input.oninput = () => {
      clearTimeout(timer);
      timer = setTimeout(searchLeads, 250);
    };
    await searchLeads();
    bindForm(async (data) => {
      data.value = Number(data.value);
      data.probability = Number(data.probability);
      data.description = data.description || null;
      await api("/deals", "POST", data);
      modal.close();
      state.view = "pipeline";
      toast("Đã tạo cơ hội bán hàng");
      await render();
    });
  } catch (error) {
    toast(error.message);
  }
}
function editDeal(deal) {
  openModal(
    "Chỉnh sửa cơ hội",
    `<form class="form-grid">${field("name", "Tên cơ hội", deal.name, "text", true)}${field("value", `Giá trị · ${escape(deal.currency)}`, deal.value || 0, "number")}${field("probability", "Xác suất thành công · %", deal.probability, "number")}<label class="full">Mô tả<textarea name="description">${escape(deal.description)}</textarea></label>${formActions()}</form>`,
  );
  modal.querySelector('[name="probability"]').max = 100;
  bindForm(async (data) => {
    data.value = Number(data.value);
    data.probability = Number(data.probability);
    data.description = data.description || null;
    await api(`/deals/${deal.id}`, "PATCH", data);
    await render();
    await showDeal(deal.id);
    toast("Đã lưu cơ hội");
  });
}
async function showDeal(id) {
  try {
    const [deal, activities] = await Promise.all([
      api(`/deals/${id}`),
      api(`/deals/${id}/activities`),
    ]);
    const lead = await api(`/leads/${deal.lead_id}`);
    openModal(
      deal.name,
      `<p class="muted">${escape(lead.company_name)}</p><div class="details"><div><div class="eyebrow">Giá trị cơ hội</div><h2>${money(deal.value, deal.currency)}</h2></div><div><div class="eyebrow">Giai đoạn</div><p>${badge(deal.stage)}</p></div></div><button id="edit-deal" style="margin-bottom:18px">Chỉnh sửa cơ hội</button><form id="stage-form" class="toolbar"><select name="stage" aria-label="Giai đoạn deal">${options(stages, deal.stage)}</select><button class="primary">Cập nhật giai đoạn</button></form><h3>Lịch sử hoạt động</h3><div class="timeline">${activities.length ? activities.map((a) => `<article><strong>${escape(a.subject || "Ghi chú")}</strong><p class="note">${escape(a.description || "")}</p><small>${date(a.created_at)}</small></article>`).join("") : '<p class="muted">Chưa có hoạt động. Thêm ghi chú sau lần trao đổi đầu tiên.</p>'}</div><form id="note-form"><label>Thêm ghi chú<textarea name="description" required placeholder="Kết quả cuộc gọi, bước tiếp theo…"></textarea></label><div class="error" role="alert"></div><div class="form-actions"><button id="customer" type="button">Xem khách hàng</button><button class="primary">Lưu ghi chú</button></div></form>`,
    );
    modal.querySelector("#customer").onclick = () => showLead(lead.id);
    modal.querySelector("#edit-deal").onclick = () => editDeal(deal);
    modal.querySelector("#stage-form").onsubmit = async (event) => {
      event.preventDefault();
      const form = event.target;
      const selectedStage = new FormData(form).get("stage");
      const controls = [
        ...modal.querySelectorAll("input,textarea,select,button:not(.close)"),
      ];
      controls.forEach((control) => (control.disabled = true));
      try {
        await api(`/deals/${id}/stage`, "PATCH", {
          stage: selectedStage,
        });
        toast("Đã cập nhật giai đoạn");
        await render();
        if (modal.open && form.isConnected) await showDeal(id);
      } catch (error) {
        toast(error.message);
      } finally {
        controls.forEach((control) => (control.disabled = false));
      }
    };
    modal.querySelector("#note-form").onsubmit = async (event) => {
      event.preventDefault();
      const form = event.target;
      const description = new FormData(form).get("description");
      const controls = [
        ...modal.querySelectorAll("input,textarea,select,button:not(.close)"),
      ];
      controls.forEach((control) => (control.disabled = true));
      try {
        await api(`/deals/${id}/activities`, "POST", {
          deal_id: id,
          type: "note",
          subject: "Ghi chú trao đổi",
          description,
        });
        if (modal.open && form.isConnected) await showDeal(id);
        toast("Đã lưu ghi chú");
      } catch (error) {
        form.querySelector(".error").textContent = error.message;
      } finally {
        controls.forEach((control) => (control.disabled = false));
      }
    };
  } catch (error) {
    toast(error.message);
  }
}
if (state.token) {
  try {
    state.user = await api("/auth/me");
    await render();
  } catch (error) {
    logout();
  }
} else login();
