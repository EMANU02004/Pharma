/* Shared frontend helpers: API calls, login guard, escaping, small UI bits. */
const PF = (() => {
  async function api(path, { method = "GET", body } = {}) {
    const opts = { method, headers: {}, credentials: "same-origin" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    let res;
    try {
      res = await fetch(path, opts);
    } catch {
      throw new Error("Can't reach the server. Check your connection and try again.");
    }
    const data = await res.json().catch(() => ({}));
    const onLoginPage = ["/", "/index.html"].includes(window.location.pathname);
    if (res.status === 401 && !onLoginPage) {
      window.location.href = "/index.html";
      throw new Error("Please log in again.");
    }
    if (!res.ok) {
      const err = new Error(data.error || `Request failed (${res.status})`);
      err.status = res.status;
      err.fields = data.fields;
      throw err;
    }
    return data;
  }

  // Escape anything that came from the server before putting it in innerHTML.
  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function toast(message, kind = "success") {
    const el = document.createElement("div");
    el.className = `alert alert-${kind === "error" ? "danger" : kind} pf-toast shadow-sm`;
    el.setAttribute("role", kind === "error" ? "alert" : "status");
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), kind === "error" ? 6000 : 3500);
  }

  async function requireRole(role) {
    let me;
    try { me = await api("/api/auth/me"); } catch { return null; }
    if (me.role !== role) {
      window.location.href = `/${me.role}.html`;
      return null;
    }
    const who = document.getElementById("who-name");
    if (who) who.textContent = me.full_name;
    const sub = document.getElementById("who-sub");
    if (sub) sub.textContent = me.pharmacy_name || me.email;
    document.getElementById("logout")?.addEventListener("click", async () => {
      await api("/api/auth/logout", { method: "POST" });
      window.location.href = "/index.html";
    });
    return me;
  }

  // Sidebar sections: links with data-section toggle .pf-section panels.
  function sections(onShow) {
    const links = document.querySelectorAll("[data-section]");
    const show = (name) => {
      links.forEach((a) => a.classList.toggle("active", a.dataset.section === name));
      document.querySelectorAll(".pf-section").forEach((s) => s.classList.toggle("active", s.id === name));
      if (onShow) onShow(name);
    };
    links.forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); show(a.dataset.section); history.replaceState(null, "", `#${a.dataset.section}`); }));
    const start = location.hash.slice(1);
    show(document.getElementById(start)?.classList.contains("pf-section") ? start : links[0].dataset.section);
    return show;
  }

  function statusBadge(status) {
    const label = { active: "Active", filled: "Filled", expired: "Expired", cancelled: "Cancelled", revoked: "Revoked" }[status] || status;
    return `<span class="status status-${esc(status)}">${esc(label)}</span>`;
  }

  function stockLabel(level, qty) {
    const text = level === "out" ? "Out of stock" : level === "low" ? `Low: ${qty} left` : `${qty} in stock`;
    return `<span class="stock-${esc(level)}">${esc(text)}</span>`;
  }

  const kes = (n) => (n == null ? "-" : `KES ${Number(n).toLocaleString("en-KE", { maximumFractionDigits: 2 })}`);

  function itemsList(items) {
    return `<ul class="rx-items">${items.map((it) => `
      <li><div><strong>${esc(it.brand_name)}</strong> <span class="text-muted">(${esc(it.generic_name)}, ${esc(it.strength_form)})</span>
      <div class="dose">${esc(it.dose)}, ${esc(it.frequency)}, for ${esc(it.duration_days)} days</div></div>
      <div>Qty ${esc(it.quantity)}</div></li>`).join("")}</ul>`;
  }

  function formErrors(form, err) {
    form.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
    Object.keys(err.fields || {}).forEach((name) => form.querySelector(`[name="${name}"]`)?.classList.add("is-invalid"));
  }

  // Patient location: the browser's geolocation, or Eldoret CBD for the demo.
  const DEMO_LOCATION = { lat: 0.5143, lng: 35.2698, label: "Eldoret CBD (demo location)" };
  function locate() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(DEMO_LOCATION);
      navigator.geolocation.getCurrentPosition(
        (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, label: "Your location" }),
        () => resolve(DEMO_LOCATION), { timeout: 6000, maximumAge: 300000 });
    });
  }

  return { api, esc, toast, requireRole, sections, statusBadge, stockLabel, kes, itemsList, formErrors, locate, DEMO_LOCATION };
})();
