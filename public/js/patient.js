/* Patient Health Passport: prescriptions, sharing, search with map, alerts. */
(async () => {
  const { api, esc, toast, statusBadge, stockLabel, kes, itemsList } = PF;
  const me = await PF.requireRole("patient");
  if (!me) return;

  let prescriptions = [];
  let pharmacies = [];
  let map, markerLayer, youMarker;
  let here = PF.DEMO_LOCATION;
  const shareModal = new bootstrap.Modal(document.getElementById("share-modal"));

  PF.sections((name) => {
    if (name === "find") setTimeout(() => { initMap(); map.invalidateSize(); }, 50);
    if (name === "alerts") loadAlerts();
  });

  // ---------------------------------------------------------- prescriptions
  async function loadPrescriptions() {
    prescriptions = await api("/api/patient/prescriptions");
    const box = document.getElementById("rx-list");
    if (!prescriptions.length) {
      box.innerHTML = `<p class="pf-empty">No prescriptions yet. When a doctor issues one, it appears here and you get an alert.</p>`;
    } else {
      box.innerHTML = prescriptions.map(slip).join("");
    }
    const active = prescriptions.filter((p) => p.status === "active");
    document.getElementById("rx-pick").innerHTML = active.length
      ? active.map((p) => `<option value="${p.prescription_id}">${esc(p.code)}: ${p.items.map((i) => esc(i.brand_name)).join(", ")}</option>`).join("")
      : `<option value="">No active prescriptions</option>`;
  }

  function slip(rx) {
    const live = rx.grants.filter((g) => g.state === "active");
    const grants = rx.grants.length ? `<div class="mt-3"><h3 class="h6">Pharmacy access</h3>
      <ul class="list-unstyled mb-0 small">${rx.grants.map((g) => `<li class="d-flex justify-content-between align-items-center py-1 gap-2">
        <span>${esc(g.pharmacy_name)}: ${rx.status === "filled" && g.state === "revoked" ? `<span class="status status-filled">Closed after dispensing</span>` : statusBadge(g.state)}
        <span class="text-muted">${g.state === "active" ? `until ${esc(g.expires_at)}` : ""}</span></span>
        ${g.state === "active" ? `<button class="btn btn-sm btn-outline-danger" data-revoke="${g.grant_id}">Revoke</button>` : ""}</li>`).join("")}</ul></div>` : "";
    const actions = rx.status === "active" ? `<div class="mt-3 d-flex flex-wrap gap-2">
        <button class="btn btn-primary btn-sm" data-find="${rx.prescription_id}">Find pharmacies with this</button>
        <button class="btn btn-outline-primary btn-sm" data-share="${rx.prescription_id}">Share with a pharmacy</button></div>` : "";
    const filled = rx.status === "filled" ? `<div class="rx-meta mt-2">Dispensed at ${esc(rx.filled_by_pharmacy)} on ${esc(rx.filled_at)}</div>` : "";
    return `<article class="rx-slip is-${esc(rx.status)}">
      <div class="rx-head">
        <div><div class="d-flex align-items-baseline"><span class="rx-mark">Rx</span><span class="rx-code">${esc(rx.code)}</span></div>
          <div class="rx-meta">${esc(rx.doctor_name)}, ${esc(rx.doctor_facility || "")}</div></div>
        <div class="text-end">${statusBadge(rx.status)}
          <div class="rx-meta mt-1">Issued ${esc(rx.issue_date)}<br>Valid until ${esc(rx.expiry_date)}</div></div>
      </div>
      ${itemsList(rx.items)}
      ${rx.notes ? `<p class="rx-meta mb-0">Note: ${esc(rx.notes)}</p>` : ""}
      ${filled}${grants}${actions}
      ${live.length ? "" : rx.status === "active" ? `<p class="small text-muted mt-2 mb-0">Not shared with any pharmacy yet. A pharmacy can only open it after you share it.</p>` : ""}
    </article>`;
  }

  document.getElementById("rx-list").addEventListener("click", async (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.dataset.share) openShare(t.dataset.share);
    if (t.dataset.find) {
      document.getElementById("rx-pick").value = t.dataset.find;
      document.querySelector('[data-section="find"]').click();
      bootstrap.Tab.getOrCreateInstance(document.querySelector('[data-bs-target="#by-rx"]')).show();
      searchByPrescription(t.dataset.find);
    }
    if (t.dataset.revoke) {
      if (!confirm("Revoke this pharmacy's access? It will no longer be able to open the prescription.")) return;
      try {
        await api(`/api/patient/grants/${t.dataset.revoke}/revoke`, { method: "POST" });
        toast("Access revoked");
        loadPrescriptions();
      } catch (err) { toast(err.message, "error"); }
    }
  });

  async function openShare(rxId, pharmacyId) {
    if (!pharmacies.length) pharmacies = await api("/api/pharmacies");
    const f = document.getElementById("share-form");
    f.rx_id.value = rxId;
    f.pharmacy_id.innerHTML = pharmacies.map((p) => `<option value="${p.pharmacy_id}">${esc(p.name)}</option>`).join("");
    if (pharmacyId) f.pharmacy_id.value = pharmacyId;
    shareModal.show();
  }

  document.getElementById("share-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      const g = await api(`/api/patient/prescriptions/${f.rx_id.value}/grants`, {
        method: "POST", body: { pharmacy_id: Number(f.pharmacy_id.value), hours: Number(f.hours.value) } });
      shareModal.hide();
      toast(`Shared with ${g.pharmacy_name}`);
      loadPrescriptions();
    } catch (err) { toast(err.message, "error"); }
  });

  // ---------------------------------------------------------------- map
  function initMap() {
    if (map) return;
    map = L.map("map").setView([here.lat, here.lng], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
    showPharmacies();
  }

  function setYou() {
    if (!map) return;
    if (youMarker) youMarker.remove();
    youMarker = L.circleMarker([here.lat, here.lng], { radius: 8, color: "#b26b00", fillColor: "#e8a33d", fillOpacity: 1 })
      .addTo(map).bindTooltip(here.label);
  }

  async function showPharmacies() {
    if (!pharmacies.length) pharmacies = await api("/api/pharmacies");
    markerLayer.clearLayers();
    pharmacies.forEach((p) => L.marker([p.latitude, p.longitude]).addTo(markerLayer)
      .bindPopup(`<strong>${esc(p.name)}</strong><br>${esc(p.address)}<br>${esc(p.open_days)} ${esc(p.opens_at)}-${esc(p.closes_at)}`));
    setYou();
  }

  function plot(points) {
    markerLayer.clearLayers();
    const bounds = [[here.lat, here.lng]];
    points.forEach((p) => {
      L.marker([p.lat, p.lng]).addTo(markerLayer).bindPopup(p.popup);
      bounds.push([p.lat, p.lng]);
    });
    setYou();
    if (bounds.length > 1) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
  }

  // ---------------------------------------------------------------- search
  const locLabel = document.getElementById("loc-label");
  PF.locate().then((loc) => { here = loc; locLabel.textContent = `Distances from: ${loc.label}`; setYou(); });

  document.getElementById("search-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    const params = new URLSearchParams({ q: f.q.value.trim(), sort: f.sort.value, lat: here.lat, lng: here.lng });
    if (f.max_km.value) params.set("max_km", f.max_km.value);
    if (f.open_now.checked) params.set("open_now", "1");
    const box = document.getElementById("results");
    try {
      const data = await api(`/api/search/medicine?${params}`);
      initMap();
      if (!data.results.length) {
        box.innerHTML = `<p class="pf-empty mb-0">No pharmacy has "${esc(data.query)}" in stock with these filters. Try another name or widen the distance.</p>`;
        plot([]);
        return;
      }
      box.innerHTML = `<h2 class="h5">${data.count} result${data.count === 1 ? "" : "s"} for "${esc(data.query)}"</h2>` +
        data.results.map((r) => `<div class="pf-result"><div>
          <strong>${esc(r.pharmacy_name)}</strong>
          <div class="small">${esc(r.brand_name)} (${esc(r.generic_name)}, ${esc(r.strength_form)})</div>
          <div class="small text-muted">${r.open_now ? "Open now" : "Closed now"}, ${esc(r.open_days)} ${esc(r.opens_at)}-${esc(r.closes_at)}</div>
          <div class="small text-muted">Stock updated ${esc(r.updated_at)}</div></div>
          <div class="text-end"><div><strong>${kes(r.price_kes)}</strong></div><div class="small">${stockLabel(r.stock_level, r.quantity)}</div>
          <div class="small text-muted">${r.distance_km != null ? `${r.distance_km} km` : ""}</div></div></div>`).join("");
      plot(data.results.map((r) => ({ lat: r.latitude, lng: r.longitude,
        popup: `<strong>${esc(r.pharmacy_name)}</strong><br>${esc(r.brand_name)}: ${kes(r.price_kes)}<br>${r.distance_km} km` })));
    } catch (err) { toast(err.message, "error"); }
  });

  document.getElementById("rx-search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const id = document.getElementById("rx-pick").value;
    if (id) searchByPrescription(id);
  });

  async function searchByPrescription(rxId) {
    const box = document.getElementById("results");
    try {
      const data = await api(`/api/patient/prescriptions/${rxId}/pharmacies?lat=${here.lat}&lng=${here.lng}`);
      initMap();
      box.innerHTML = `<h2 class="h5">Pharmacies for ${esc(data.code)}</h2>
        <p class="small text-muted">Pharmacies that can supply every medicine are listed first, nearest first.</p>` +
        data.results.map((r, i) => `<div class="pf-result ${i === 0 && r.can_fill_all ? "is-best" : ""}"><div>
          <strong>${esc(r.name)}</strong>
          <div class="small">${r.can_fill_all ? "Has everything on your prescription" : `Has ${r.items_available} of ${r.items_needed} medicines`}</div>
          <ul class="small mb-1 ps-3">${r.lines.map((l) => `<li>${esc(l.brand_name)}: ${l.enough ? `<span class="stock-ok">enough</span> at ${kes(l.unit_price_kes)} each` : `<span class="stock-out">${l.in_stock ? `only ${l.in_stock}` : "none"}</span>`}</li>`).join("")}</ul>
          <div class="small text-muted">${r.open_now ? "Open now" : "Closed now"}, ${esc(r.open_days)} ${esc(r.opens_at)}-${esc(r.closes_at)}</div></div>
          <div class="text-end"><div><strong>${r.can_fill_all ? kes(r.total_price_kes) : ""}</strong></div>
          <div class="small text-muted">${r.distance_km != null ? `${r.distance_km} km` : ""}</div>
          ${data.status === "active" ? `<button class="btn btn-sm btn-outline-primary mt-2" data-share-to="${r.pharmacy_id}" data-rx="${data.prescription_id}">Share here</button>` : ""}</div></div>`).join("");
      plot(data.results.map((r) => ({ lat: r.latitude, lng: r.longitude,
        popup: `<strong>${esc(r.name)}</strong><br>${r.items_available}/${r.items_needed} medicines<br>${r.distance_km} km` })));
    } catch (err) { toast(err.message, "error"); }
  }

  document.getElementById("results").addEventListener("click", (e) => {
    const t = e.target.closest("[data-share-to]");
    if (t) openShare(t.dataset.rx, t.dataset.shareTo);
  });

  // ---------------------------------------------------------------- alerts
  async function loadAlerts() {
    const rows = await api("/api/notifications");
    const unread = rows.filter((n) => !n.read_at).length;
    document.getElementById("alert-count").textContent = unread || "";
    const box = document.getElementById("alert-list");
    box.innerHTML = rows.length ? rows.map((n) => `<div class="pf-result"><div>
        <strong>${esc(n.subject)}</strong> ${n.read_at ? "" : `<span class="status status-active">New</span>`}
        <div>${esc(n.body)}</div>
        <div class="small text-muted">${esc(n.created_at)}, ${n.delivery_status === "simulated" ? "in-app only (email simulated)" : esc(n.delivery_status)}</div></div>
        ${n.read_at ? "" : `<button class="btn btn-sm btn-outline-secondary align-self-start" data-read="${n.notification_id}">Mark read</button>`}</div>`).join("")
      : `<p class="pf-empty mb-0">No alerts yet.</p>`;
  }
  document.getElementById("alert-list").addEventListener("click", async (e) => {
    const t = e.target.closest("[data-read]");
    if (!t) return;
    await api(`/api/notifications/${t.dataset.read}/read`, { method: "POST" });
    loadAlerts();
  });

  // ---------------------------------------------------------------- profile
  document.getElementById("profile-box").innerHTML = `<dl class="row mb-0">
    <dt class="col-sm-3">Name</dt><dd class="col-sm-9">${esc(me.full_name)}</dd>
    <dt class="col-sm-3">Email</dt><dd class="col-sm-9">${esc(me.email)}</dd>
    <dt class="col-sm-3">Phone</dt><dd class="col-sm-9">${esc(me.phone || "-")}</dd>
    <dt class="col-sm-3">Date of birth</dt><dd class="col-sm-9">${esc(me.date_of_birth || "-")}</dd>
    <dt class="col-sm-3">Sub-county</dt><dd class="col-sm-9">${esc(me.sub_county || "-")}</dd></dl>`;

  await loadPrescriptions();
  loadAlerts();
})();
