/* Pharmacist dashboard: verify and dispense, shared list, stock management, history. */
(async () => {
  const { api, esc, toast, statusBadge, stockLabel, kes } = PF;
  const me = await PF.requireRole("pharmacist");
  if (!me) return;

  PF.sections((name) => {
    if (name === "shared") loadShared();
    if (name === "stock") loadStock();
    if (name === "history") loadHistory();
  });

  // ------------------------------------------------------ verify / dispense
  const result = document.getElementById("verify-result");
  async function verify(code) {
    result.innerHTML = "";
    try {
      const rx = await api("/api/pharmacy/verify", { method: "POST", body: { code } });
      result.innerHTML = `<article class="rx-slip is-${esc(rx.status)}">
        <div class="rx-head"><div><div class="d-flex align-items-baseline"><span class="rx-mark">Rx</span><span class="rx-code">${esc(rx.code)}</span></div>
          <div class="rx-meta">Patient: ${esc(rx.patient_name)} (born ${esc(rx.patient_dob || "?")})</div>
          <div class="rx-meta">Prescriber: ${esc(rx.doctor_name)}, licence ${esc(rx.doctor_license)}, ${esc(rx.doctor_facility || "")}</div></div>
          <div class="text-end">${statusBadge(rx.status)}<div class="rx-meta mt-1">Valid until ${esc(rx.expiry_date)}</div></div></div>
        <div class="table-responsive"><table class="table mt-3 mb-2"><thead><tr><th>Medicine</th><th>Directions</th><th>Qty</th><th>Your stock</th><th>Cost</th></tr></thead><tbody>
        ${rx.items.map((it) => `<tr class="${it.enough || rx.status !== "active" ? "" : "row-out"}"><td><strong>${esc(it.brand_name)}</strong><div class="small text-muted">${esc(it.generic_name)}, ${esc(it.strength_form)}</div></td>
          <td class="small">${esc(it.dose)}, ${esc(it.frequency)}, ${esc(it.duration_days)} days</td><td>${esc(it.quantity)}</td>
          <td>${rx.status !== "active" ? "-" : it.enough ? `<span class="stock-ok">${it.in_stock}</span>` : `<span class="stock-out">${it.in_stock} (not enough)</span>`}</td>
          <td>${rx.status === "active" && it.enough ? kes(it.unit_price_kes * it.quantity) : "-"}</td></tr>`).join("")}</tbody></table></div>
        ${rx.notes ? `<p class="rx-meta">Note: ${esc(rx.notes)}</p>` : ""}
        <div class="d-flex flex-wrap align-items-center gap-3">
          ${rx.can_dispense ? `<button class="btn btn-primary btn-lg" id="dispense" data-code="${esc(rx.code)}">Dispense all and mark filled</button>
            <span>Total: <strong>${kes(rx.total_price_kes)}</strong></span>`
            : `<div class="alert alert-warning mb-0">${esc(rx.blocked_reason)}</div>`}
        </div></article>`;
    } catch (err) {
      result.innerHTML = `<div class="alert ${err.status === 409 ? "alert-warning" : "alert-danger"}" role="alert">${esc(err.message)}</div>`;
    }
  }

  document.getElementById("code-form").addEventListener("submit", (e) => {
    e.preventDefault();
    verify(e.target.code.value);
  });

  result.addEventListener("click", async (e) => {
    const t = e.target.closest("#dispense");
    if (!t) return;
    if (!confirm("Dispense every item? Stock will be reduced and the prescription marked filled.")) return;
    t.disabled = true;
    try {
      const r = await api("/api/pharmacy/dispense", { method: "POST", body: { code: t.dataset.code } });
      toast(`Dispensed ${r.items_dispensed} item(s). Prescription ${r.code} is now filled.`);
      verify(r.code);
    } catch (err) {
      t.disabled = false;
      toast(err.message, "error");
    }
  });

  // ------------------------------------------------------ shared
  async function loadShared() {
    const rows = await api("/api/pharmacy/shared");
    document.getElementById("shared-list").innerHTML = rows.length ? `<div class="table-responsive"><table class="table align-middle mb-0">
      <thead><tr><th>Code</th><th>Patient</th><th>Medicines</th><th>Status</th><th>Access ends</th><th></th></tr></thead><tbody>
      ${rows.map((r) => `<tr><td class="rx-code" style="font-size:1rem">${esc(r.code)}</td><td>${esc(r.patient_name)}</td><td>${esc(r.item_count)}</td>
        <td>${statusBadge(r.status)}</td><td>${esc(r.access_expires_at)}</td>
        <td><button class="btn btn-sm btn-outline-primary" data-open="${esc(r.code)}">Open</button></td></tr>`).join("")}</tbody></table></div>`
      : `<p class="pf-empty mb-0">No prescriptions are shared with your pharmacy right now.</p>`;
  }
  document.getElementById("shared-list").addEventListener("click", (e) => {
    const t = e.target.closest("[data-open]");
    if (!t) return;
    document.getElementById("code").value = t.dataset.open;
    document.querySelector('[data-section="counter"]').click();
    verify(t.dataset.open);
  });

  // ------------------------------------------------------ stock
  let stock = [];
  async function loadStock() {
    const data = await api("/api/pharmacy/stock");
    stock = data.items;
    document.getElementById("stock-stats").innerHTML = `
      <div class="col-6 col-md-3"><div class="pf-stat"><b>${data.summary.total}</b>medicines stocked</div></div>
      <div class="col-6 col-md-3"><div class="pf-stat"><b class="stock-low">${data.summary.low}</b>low stock</div></div>
      <div class="col-6 col-md-3"><div class="pf-stat"><b class="stock-out">${data.summary.out}</b>out of stock</div></div>
      <div class="col-6 col-md-3"><div class="pf-stat"><b style="font-size:1.05rem">${esc(data.last_updated || "-")}</b>last update</div></div>`;
    renderStock();
    const meds = await api("/api/medicines?q=");
    const have = new Set(stock.map((s) => s.medicine_id));
    document.getElementById("add-med").innerHTML = meds.filter((m) => !have.has(m.medicine_id))
      .map((m) => `<option value="${m.medicine_id}">${esc(m.brand_name)} (${esc(m.generic_name)}) ${esc(m.strength_form)}</option>`).join("");
  }

  function renderStock() {
    const q = document.getElementById("stock-filter").value.toLowerCase();
    const level = document.getElementById("stock-level").value;
    const rows = stock.filter((s) => (!q || `${s.brand_name} ${s.generic_name}`.toLowerCase().includes(q)) && (!level || s.stock_level === level));
    document.getElementById("stock-rows").innerHTML = rows.map((s) => `<tr class="${s.stock_level === "low" ? "row-low" : s.stock_level === "out" ? "row-out" : ""}">
      <td><strong>${esc(s.brand_name)}</strong><div class="small text-muted">${esc(s.generic_name)}, ${esc(s.strength_form)}</div><div class="small">${stockLabel(s.stock_level, s.quantity)}</div></td>
      <td><input class="form-control form-control-sm" type="number" min="0" value="${s.quantity}" data-qty="${s.stock_id}" aria-label="Quantity of ${esc(s.brand_name)}" style="width:6.5rem"></td>
      <td><input class="form-control form-control-sm" type="number" min="0.01" step="0.01" value="${s.price_kes}" data-price="${s.stock_id}" aria-label="Price of ${esc(s.brand_name)}" style="width:7rem"></td>
      <td class="small text-muted">${esc(s.updated_at)}</td>
      <td><button class="btn btn-sm btn-outline-primary" data-save="${s.stock_id}">Save</button></td></tr>`).join("")
      || `<tr><td colspan="5" class="pf-empty">No stock matches.</td></tr>`;
  }
  document.getElementById("stock-filter").addEventListener("input", renderStock);
  document.getElementById("stock-level").addEventListener("change", renderStock);

  document.getElementById("stock-rows").addEventListener("click", async (e) => {
    const t = e.target.closest("[data-save]");
    if (!t) return;
    const id = t.dataset.save;
    const qty = document.querySelector(`[data-qty="${id}"]`).value;
    const price = document.querySelector(`[data-price="${id}"]`).value;
    try {
      await api(`/api/pharmacy/stock/${id}`, { method: "PATCH", body: { quantity: qty === "" ? null : Number(qty), price_kes: Number(price) } });
      toast("Stock saved");
      loadStock();
    } catch (err) { toast(err.message, "error"); }
  });

  document.getElementById("add-stock").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      await api("/api/pharmacy/stock", { method: "POST", body: {
        medicine_id: Number(f.medicine_id.value), quantity: Number(f.quantity.value), price_kes: Number(f.price_kes.value) } });
      toast("Added to stock");
      f.reset();
      loadStock();
    } catch (err) { toast(err.message, "error"); }
  });

  document.getElementById("add-medicine").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      await api("/api/pharmacy/medicines", { method: "POST", body: {
        brand_name: f.brand_name.value, generic_name: f.generic_name.value, strength_form: f.strength_form.value,
        requires_prescription: f.requires_prescription.checked } });
      toast("Added to catalogue. You can now add it to stock.");
      f.reset();
      loadStock();
    } catch (err) { toast(err.message, "error"); }
  });

  // ------------------------------------------------------ history
  async function loadHistory() {
    const rows = await api("/api/pharmacy/dispensed");
    document.getElementById("history-list").innerHTML = rows.length ? `<table class="table mb-0"><thead><tr><th>Code</th><th>Patient</th><th>Items</th><th>Dispensed</th></tr></thead><tbody>
      ${rows.map((r) => `<tr><td class="rx-code" style="font-size:1rem">${esc(r.code)}</td><td>${esc(r.patient_name)}</td><td>${esc(r.item_count)}</td><td>${esc(r.filled_at)}</td></tr>`).join("")}</tbody></table>`
      : `<p class="pf-empty mb-0">Nothing dispensed yet.</p>`;
  }
})();
