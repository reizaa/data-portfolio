(function () {
  "use strict";
  const D = window.PORTFOLIO || {};
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const pct = (v, d = 0) => (v * 100).toFixed(d) + "%";
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const el = (tag, attrs = {}, html = "") => { const e = document.createElement(tag); Object.assign(e, attrs); if (html) e.innerHTML = html; return e; };
  const metric = (before, after, label) =>
    `<div class="metric"><div class="v">${before != null ? `<s>${before}</s>` : ""}<b>${after}</b></div><div class="k">${label}</div></div>`;

  // ---------- theme ----------
  try { const t = localStorage.getItem("theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
  $("#theme").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("theme", document.documentElement.dataset.theme); } catch (e) {}
    renderAll();
  });

  // ---------- tooltip ----------
  const tip = $("#tip");
  const showTip = (e, html) => { tip.innerHTML = html; tip.style.opacity = 1;
    tip.style.left = Math.min(e.clientX + 12, innerWidth - 250) + "px"; tip.style.top = e.clientY + 12 + "px"; };
  const hideTip = () => (tip.style.opacity = 0);

  // ---------- filters ----------
  $$(".chip").forEach((c) => c.addEventListener("click", () => {
    $$(".chip").forEach((x) => x.setAttribute("aria-pressed", x === c));
    const f = c.dataset.f;
    $$("#projects .card").forEach((card) => { card.hidden = f !== "all" && !card.dataset.tags.split(" ").includes(f); });
  }));

  // ---------- before / after toggles ----------
  $$("#projects .card").forEach((card) => {
    const btns = $$(".card-head .seg button", card);
    const set = (m) => {
      card.dataset.mode = m;
      btns.forEach((b) => b.setAttribute("aria-pressed", b.dataset.m === m));
      $$(".flow-row, .impact, .msg", card).forEach((x) => { x.classList.remove("fade"); void x.offsetWidth; x.classList.add("fade"); });
      card.dispatchEvent(new CustomEvent("mode", { detail: m }));
    };
    btns.forEach((b) => b.addEventListener("click", () => set(b.dataset.m)));
    set("after");
  });

  // ---------- headline stats ----------
  function stats() {
    const q = D["03"].runs, s = q[0].ms / q[q.length - 1].ms;
    const a = D["05"], i = a.budgets.indexOf(300);
    $("#stats").innerHTML = [
      [D["01"].before_after[0].before + " → " + D["01"].before_after[0].after, "client records merged into real clients"],
      [pct(D["02"].explained), "of changed cohort numbers explained automatically"],
      [Math.round(s) + "x", "faster query, identical result"],
      [(a.scored[i] / a.random[i]).toFixed(1) + "x", "more leads won back per contact (simulated)"],
    ].map(([v, k]) => `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");
  }

  // ---------- 01: cleaning ----------
  function p01() {
    const d = D["01"], rows = d.before_after;
    $("#p01-impact").innerHTML =
      metric(rows[0].before, rows[0].after, "real clients (name variants merged)") +
      metric(pct(d.revenue_error), "0%", "revenue error") +
      metric(rows[3].before, rows[3].after, "payments booked in the wrong month") +
      metric(rows[4].before, rows[4].after, "clients split across several owners");
    const keys = ["new", "active", "reactivated", "churned", "churned_again"].filter((k) => d.status[k]);
    const col = { new: css("--accent"), active: "#64a8a0", reactivated: "#8fb7e8", churned: "#e8a07a", churned_again: "#c2554b" };
    const W = 640, H = 200, P = 26, n = d.status_months.length, bw = (W - P) / n - 6;
    const tot = d.status_months.map((_, i) => keys.reduce((s, k) => s + d.status[k][i], 0));
    const max = Math.max(...tot);
    let svg = `<svg viewBox="0 0 ${W} ${H + 20}" width="100%" role="img" aria-label="Stacked bar chart of subscription status per month">`;
    d.status_months.forEach((m, i) => {
      let y = H; const x = P + i * ((W - P) / n) + 3;
      keys.forEach((k) => {
        const v = d.status[k][i]; if (!v) return; const h = (v / max) * (H - 10); y -= h;
        svg += `<rect x="${x}" y="${y}" width="${bw}" height="${h}" rx="2" fill="${col[k]}" data-tip="<b>${m}</b><br>${k.replace("_", " ")}: ${v}"/>`;
      });
      svg += `<text x="${x + bw / 2}" y="${H + 14}" text-anchor="middle">${m.slice(2)}</text>`;
    });
    $("#p01-chart").innerHTML = svg + "</svg>";
    $("#p01-legend").innerHTML = keys.map((k) => `<span><i style="background:${col[k]}"></i>${k.replace("_", " ")}</span>`).join("");
    $$("#p01-chart rect").forEach((r) => { r.addEventListener("mousemove", (e) => showTip(e, r.dataset.tip)); r.addEventListener("mouseleave", hideTip); });
  }

  // ---------- 02: cohort heatmap ----------
  let p02View = "customer";
  function p02() {
    const d = D["02"];
    $("#p02-impact").innerHTML =
      metric("by eye", pct(d.explained), `of ${d.changed_cells} changed cells explained automatically`) +
      metric("manual", d.seconds < 1 ? "< 1 s" : d.seconds + " s", "to validate a full refresh");
    const m = d[p02View], vmax = p02View === "customer" ? 0.6 : 1, acc = css("--accent");
    const grid = $("#p02-heat");
    grid.style.gridTemplateColumns = `64px repeat(${d.ages.length}, minmax(34px, 1fr))`;
    let html = `<div class="h"></div>` + d.ages.map((a) => `<div class="h">M${a}</div>`).join("");
    d.cohorts.forEach((c, i) => {
      html += `<div class="h">${c}</div>`;
      m[i].forEach((v, j) => {
        if (v == null) { html += `<div></div>`; return; }
        const a = Math.min(v / vmax, 1), light = a < 0.55;
        html += `<div class="c" style="background:color-mix(in srgb, ${acc} ${Math.round(a * 100)}%, transparent);color:${light ? "inherit" : "#fff"}"
                  data-tip="<b>Cohort ${c}</b> · month ${j}<br>${p02View === "customer" ? "Customers retained" : "Revenue kept"}: ${pct(v, 1)}">${j ? pct(v) : "—"}</div>`;
      });
    });
    grid.innerHTML = html;
    $$(".c", grid).forEach((x) => { x.addEventListener("mousemove", (e) => showTip(e, x.dataset.tip)); x.addEventListener("mouseleave", hideTip); });
  }
  $$("#p02-toggle button").forEach((b) => b.addEventListener("click", () => {
    p02View = b.dataset.v; $$("#p02-toggle button").forEach((x) => x.setAttribute("aria-pressed", x === b)); p02();
  }));

  // ---------- 03: benchmark ----------
  function p03(animate) {
    const d = D["03"], runs = d.runs, max = runs[0].ms, best = runs[runs.length - 1];
    $("#p03-q").textContent = `Query time on ${d.rows.toLocaleString("en")} rows`;
    $("#p03-impact").innerHTML =
      metric(Math.round(runs[0].ms) + " ms", best.ms + " ms", `query time (${Math.round(runs[0].ms / best.ms)}x faster)`) +
      metric("unchecked", runs.every((r) => r.same) ? "identical" : "MISMATCH", "result vs the original query");
    $("#p03-bars").innerHTML = runs.map((r, i) =>
      `<div class="row"><span class="name">${r.name}</span><div class="track"><div class="fill ${i ? "" : "slow"}" data-w="${Math.max((r.ms / max) * 100, 1.2)}"></div></div>
       <span class="val">${animate ? "…" : r.ms + " ms"}</span></div>`).join("");
    const fills = $$("#p03-bars .fill"), vals = $$("#p03-bars .val");
    if (!animate) { fills.forEach((f) => (f.style.width = f.dataset.w + "%")); return; }
    $("#p03-run").disabled = true;
    runs.forEach((r, i) => setTimeout(() => {
      fills[i].style.width = fills[i].dataset.w + "%"; vals[i].textContent = r.ms + " ms";
      if (i === runs.length - 1) $("#p03-run").disabled = false;
    }, 250 + i * 650));
  }
  $("#p03-run").addEventListener("click", () => p03(true));

  // ---------- 04: alert ----------
  const p04card = $("#p04-msg").closest(".card");
  function p04() {
    const d = D["04"], after = p04card.dataset.mode === "after";
    $("#p04-msg").textContent = after ? d.after : d.before;
    $("#p04-hint").textContent = after ? "Names the contributors and flags anomalies" : "Total only — the team has to ask why";
    $("#p04-impact").innerHTML = metric("0", "5", "contributors named per message") + metric("0", d.anomalies, "anomalies flagged automatically");
  }
  p04card.addEventListener("mode", p04);

  // ---------- 05: lead budget ----------
  function p05() {
    const d = D["05"], i = +$("#p05-range").value, b = d.budgets[i];
    $("#p05-range").max = d.budgets.length - 1;
    $("#p05-rand").textContent = Math.round(d.random[i]);
    $("#p05-score").textContent = d.scored[i];
    $("#p05-range").setAttribute("aria-valuetext", b + " contacts");
    $("#p05-range").previousElementSibling.querySelector("h4").textContent = `Leads won back with ${b} contacts (of ${d.pool.toLocaleString("en")} in the pool)`;
    const W = 640, H = 150, P = 30, n = d.budgets.length, max = Math.max(...d.scored);
    const x = (k) => P + (k / (n - 1)) * (W - P - 10), y = (v) => H - (v / max) * (H - 12);
    const line = (arr) => arr.map((v, k) => `${k ? "L" : "M"}${x(k)},${y(v)}`).join("");
    $("#p05-chart").innerHTML = `<svg viewBox="0 0 ${W} ${H + 18}" width="100%" role="img" aria-label="Leads won back by budget">
      <line x1="${x(i)}" x2="${x(i)}" y1="4" y2="${H}" stroke="${css("--border")}" stroke-width="2"/>
      <path d="${line(d.random)}" fill="none" stroke="${css("--old-text")}" stroke-width="2" stroke-dasharray="5 4"/>
      <path d="${line(d.scored)}" fill="none" stroke="${css("--accent")}" stroke-width="2.5"/>
      <circle cx="${x(i)}" cy="${y(d.scored[i])}" r="4.5" fill="${css("--accent")}"/>
      <circle cx="${x(i)}" cy="${y(d.random[i])}" r="4" fill="${css("--old-text")}"/>
      ${d.budgets.map((v, k) => (k % 3 ? "" : `<text x="${x(k)}" y="${H + 14}" text-anchor="middle">${v}</text>`)).join("")}</svg>`;
  }
  $("#p05-range").addEventListener("input", p05);

  // ---------- 06: classification ----------
  function p06() {
    const d = D["06"];
    $("#p06-impact").innerHTML = metric(pct(d.naive_acc), pct(d.rule_acc), "accuracy (first keyword → scored rules)") +
      metric("0%", pct(1 - d.coverage), "ambiguous cases routed to LLM, not guessed");
    $("#p06-bars").innerHTML = d.topics.map((t) =>
      `<div class="row"><span class="name">${t.topic}</span><div class="track"><div class="fill" style="width:${t.precision * 100}%"></div></div><span class="val">P ${pct(t.precision)}</span></div>
       <div class="row"><span class="name"></span><div class="track"><div class="fill slow" style="width:${t.recall * 100}%"></div></div><span class="val">R ${pct(t.recall)}</span></div>`).join("");
  }

  function renderAll() { stats(); p01(); p02(); p03(false); p04(); p05(); p06(); }
  if (!D["01"]) { $("#projects").insertAdjacentHTML("beforebegin", "<p>Data not built yet. Run <code>python run_all.py</code>.</p>"); return; }
  renderAll();
})();
