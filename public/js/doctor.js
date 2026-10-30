/* Doctor dashboard: pick a patient, build a prescription, review and cancel issued ones. */
(async () => {
  const { api, esc, toast, statusBadge, itemsList } = PF;
  const me = await PF.requireRole("doctor");
  if (!me) return;

  PF.sections((name) => { if (name === "issued") loadIssued(); });

  // Medicine catalogue for the datalist: label -> id
  const medicines = await api("/api/medicines?q=");
  const label = (m) => `${m.brand_name} (${m.generic_name}) ${m.strength_form}`;
  const byLabel = new Map(medicines.map((m) => [label(m), m.medicine_id]));
  document.getElementById("medicine-options").innerHTML = medicines.map((m) => `<option value="${esc(label(m))}">`).join("");

  // ------------------------------------------------------------ patients
  const pq = document.getElementById("patient-q");
  const pick = document.getElementById("patient-id");
  let timer;
  pq.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const rows = await api(`/api/doctor/patients?q=${encodeURIComponent(pq.value.trim())}`);
      pick.innerHTML = rows.length
        ? rows.map((p) => `<option value="${p.patient_id}">${esc(p.full_name)} (born ${esc(p.date_of_birth || "?")}, ${esc(p.email)})</option>`).join("")
        : `<option value="">No matching patients</option>`;
    }, 250);
  });

  // ------------------------------------------------------------ items
  const itemsBox = document.getElementById("items");
  const tpl = document.getElementById("item-row");
  function addItem() {
    const row = tpl.content.firstElementChild.cloneNode(true);
    row.querySelector(".med-input").addEventListener("change", (e) => {
      row.querySelector(".med-id").value = byLabel.get(e.target.value) || "";
      e.target.classList.toggle("is-invalid", !row.querySelector(".med-id").value);
    });
    row.querySelector(".remove").addEventListener("click", () => { if (itemsBox.children.length > 1) row.remove(); });
    itemsBox.appendChild(row);
  }
  document.getElementById("add-item").addEventListener("click", addItem);
  addItem();

  document.getElementById("rx-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const out = document.getElementById("rx-error");
    out.textContent = "";
    const items = [...itemsBox.querySelectorAll(".rx-item")].map((row) => ({
      medicine_id: Number(row.querySelector(".med-id").value) || null,
      dose: row.querySelector(".dose").value,
      frequency: row.querySelector(".frequency").value,
      duration_days: row.querySelector(".duration").value === "" ? null : Number(row.querySelector(".duration").value),
      quantity: row.querySelector(".quantity").value === "" ? null : Number(row.querySelector(".quantity").value),
    }));
    // The server validates everything again; this just gives quicker feedback.
    if (items.some((i) => !i.medicine_id)) { out.textContent = "Choose each medicine from the list."; return; }
    try {
      const rx = await api("/api/doctor/prescriptions", { method: "POST", body: {
        patient_id: Number(pick.value) || null, items,
        valid_days: Number(document.getElementById("valid-days").value),
        notes: document.getElementById("notes").value } });
      toast("Prescription issued and patient alerted");
      document.getElementById("issued-result").innerHTML = `<div class="rx-slip">
        <p class="mb-1">Issued to <strong>${esc(rx.patient_name)}</strong>. Give the patient this code:</p>
        <div class="d-flex align-items-baseline"><span class="rx-mark">Rx</span><span class="rx-code rx-code-lg">${esc(rx.code)}</span></div>
        <div class="rx-meta">Valid until ${esc(rx.expiry_date)}. Patient alert: ${rx.notification === "simulated" ? "in-app (email simulated)" : esc(rx.notification)}</div>
        ${itemsList(rx.items)}</div>`;
      e.target.reset();
      itemsBox.innerHTML = "";
      addItem();
      pick.innerHTML = `<option value="">Search first</option>`;
    } catch (err) {
      out.textContent = err.fields ? `${err.message}: ${Object.keys(err.fields).join(", ")}` : err.message;
    }
  });

  // ------------------------------------------------------------ issued
  async function loadIssued() {
    const rows = await api("/api/doctor/prescriptions");
    const box = document.getElementById("issued-list");
    box.innerHTML = rows.length ? rows.map((rx) => `<article class="rx-slip is-${esc(rx.status)}">
      <div class="rx-head"><div><div class="d-flex align-items-baseline"><span class="rx-mark">Rx</span><span class="rx-code">${esc(rx.code)}</span></div>
        <div class="rx-meta">For ${esc(rx.patient_name)}, issued ${esc(rx.issue_date)}, valid until ${esc(rx.expiry_date)}</div></div>
        <div>${statusBadge(rx.status)}</div></div>
      ${itemsList(rx.items)}
      ${rx.status === "active" ? `<button class="btn btn-sm btn-outline-danger mt-2" data-cancel="${rx.prescription_id}">Cancel prescription</button>` : ""}
      ${rx.status === "filled" ? `<div class="rx-meta mt-2">Dispensed at ${esc(rx.filled_by_pharmacy)} on ${esc(rx.filled_at)}</div>` : ""}
    </article>`).join("") : `<p class="pf-empty">You have not issued any prescriptions yet.</p>`;
  }
  document.getElementById("issued-list").addEventListener("click", async (e) => {
    const t = e.target.closest("[data-cancel]");
    if (!t || !confirm("Cancel this prescription? The patient will no longer be able to use it.")) return;
    try {
      await api(`/api/doctor/prescriptions/${t.dataset.cancel}/cancel`, { method: "POST" });
      toast("Prescription cancelled");
      loadIssued();
    } catch (err) { toast(err.message, "error"); }
  });
})();
