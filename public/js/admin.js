/* Admin dashboard: stats, users, staff accounts, pharmacies, audit log. */
(async () => {
  const { api, esc, toast } = PF;
  const me = await PF.requireRole("admin");
  if (!me) return;

  PF.sections((name) => ({ overview: loadStats, users: loadUsers, staff: loadPharmacyOptions,
    pharmacies: loadPharmacies, audit: loadAudit }[name]?.()));

  async function loadStats() {
    const s = await api("/api/admin/stats");
    const tile = (n, label) => `<div class="col-6 col-md-3"><div class="pf-stat"><b>${esc(n ?? 0)}</b>${esc(label)}</div></div>`;
    document.getElementById("stats").innerHTML =
      tile(s.users.patient, "patients") + tile(s.users.doctor, "doctors") + tile(s.users.pharmacist, "pharmacists") +
      tile(s.pharmacies, "pharmacies") + tile(s.prescriptions.active, "active prescriptions") +
      tile(s.prescriptions.filled, "filled prescriptions") + tile(s.medicines, "medicines in catalogue") +
      tile(s.audit_events_24h, "audit events in 24 h");
  }

  // ---------------------------------------------------------------- users
  async function loadUsers() {
    const q = encodeURIComponent(document.getElementById("user-q").value);
    const role = document.getElementById("user-role").value;
    const rows = await api(`/api/admin/users?q=${q}${role ? `&role=${role}` : ""}`);
    document.getElementById("user-rows").innerHTML = rows.map((u) => `<tr>
      <td><strong>${esc(u.full_name)}</strong><div class="small text-muted">${esc(u.email)}</div></td>
      <td>${esc(u.role)}</td>
      <td class="small">${u.doctor_license ? `Licence ${esc(u.doctor_license)}, ${esc(u.facility || "")}` : u.pharmacy_name ? esc(u.pharmacy_name) : ""}</td>
      <td>${u.is_active ? `<span class="status status-active">Active</span>` : `<span class="status status-revoked">Deactivated</span>`}</td>
      <td>${u.user_id === me.user_id ? "" : `<button class="btn btn-sm ${u.is_active ? "btn-outline-danger" : "btn-outline-primary"}" data-user="${u.user_id}" data-active="${u.is_active ? 0 : 1}">${u.is_active ? "Deactivate" : "Reactivate"}</button>`}</td></tr>`).join("")
      || `<tr><td colspan="5" class="pf-empty">No users match.</td></tr>`;
  }
  let t;
  document.getElementById("user-q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(loadUsers, 250); });
  document.getElementById("user-role").addEventListener("change", loadUsers);
  document.getElementById("user-rows").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-user]");
    if (!b) return;
    const activate = b.dataset.active === "1";
    if (!activate && !confirm("Deactivate this account? The user is logged out and cannot log in.")) return;
    try {
      await api(`/api/admin/users/${b.dataset.user}/status`, { method: "POST", body: { is_active: activate } });
      toast(activate ? "Account reactivated" : "Account deactivated");
      loadUsers();
    } catch (err) { toast(err.message, "error"); }
  });

  // ---------------------------------------------------------------- staff
  async function loadPharmacyOptions() {
    const rows = await api("/api/admin/pharmacies");
    document.getElementById("p-pharm").innerHTML = rows.map((p) => `<option value="${p.pharmacy_id}">${esc(p.name)}</option>`).join("");
  }
  function bindForm(id, url, label, transform = (b) => b) {
    document.getElementById(id).addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const body = transform(Object.fromEntries(new FormData(f).entries()));
      try {
        await api(url, { method: "POST", body });
        toast(`${label} created`);
        f.reset();
        if (id === "pharmacy-form") loadPharmacies();
      } catch (err) { toast(err.message, "error"); PF.formErrors(f, err); }
    });
  }
  bindForm("doctor-form", "/api/admin/doctors", "Doctor account");
  bindForm("pharmacist-form", "/api/admin/pharmacists", "Pharmacist account", (b) => ({ ...b, pharmacy_id: Number(b.pharmacy_id) }));
  bindForm("pharmacy-form", "/api/admin/pharmacies", "Pharmacy",
    (b) => ({ ...b, latitude: Number(b.latitude), longitude: Number(b.longitude) }));

  async function loadPharmacies() {
    const rows = await api("/api/admin/pharmacies");
    document.getElementById("pharmacy-rows").innerHTML = rows.map((p) => `<tr><td><strong>${esc(p.name)}</strong><div class="small text-muted">${esc(p.address)}</div></td>
      <td>${esc(p.license_number)}</td><td class="small">${esc(p.open_days)} ${esc(p.opens_at)}-${esc(p.closes_at)}</td>
      <td class="small">${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}</td><td>${esc(p.staff)}</td><td>${esc(p.stock_lines)}</td></tr>`).join("");
  }

  // ---------------------------------------------------------------- audit
  const actionSel = document.getElementById("audit-action");
  async function loadAudit() {
    const action = actionSel.value;
    const data = await api(`/api/admin/audit?limit=200${action ? `&action=${encodeURIComponent(action)}` : ""}`);
    if (actionSel.options.length === 1) {
      actionSel.insertAdjacentHTML("beforeend", data.actions.map((a) => `<option>${esc(a)}</option>`).join(""));
    }
    document.getElementById("audit-rows").innerHTML = data.entries.map((r) => `<tr>
      <td class="small text-nowrap">${esc(r.created_at)}</td><td class="small">${esc(r.full_name || "Unknown")} <span class="text-muted">${esc(r.role || "")}</span></td>
      <td><code>${esc(r.action)}</code></td><td class="small">${r.target_type && r.target_id != null ? `${esc(r.target_type)} #${esc(r.target_id)}` : ""}</td>
      <td class="small text-muted">${esc(r.details || "")}</td></tr>`).join("")
      || `<tr><td colspan="5" class="pf-empty">No entries.</td></tr>`;
  }
  actionSel.addEventListener("change", loadAudit);
})();
