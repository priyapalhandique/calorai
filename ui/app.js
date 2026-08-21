/* calorai UI — 4-act dashboard, vanilla JS + canvas (no frameworks, no CDN).
   Acts: Overview (24 h heatmap slider + diurnal) · Physics (circulation +
   energy + downburst) · Analytics (distribution, hourly spread, radial UHI,
   percentiles, anomalies, equity, alerts) · Ask (voice + text agent chat). */

"use strict";

const $ = (id) => document.getElementById(id);
const state = { data: null, auditHour: 14 };

/* ------------------------------------------------------------- utilities */

const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(d));
const fmtMoney = (v) => (v === null || v === undefined || Number.isNaN(v) ? "—" : "$" + Math.round(v).toLocaleString("en-US"));
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function md(s) {
  return esc(s)
    .replace(/^###### (.*)$/gm, "<h6>$1</h6>").replace(/^##### (.*)$/gm, "<h5>$1</h5>")
    .replace(/^#### (.*)$/gm, "<h4>$1</h4>").replace(/^### (.*)$/gm, "<h3>$1</h3>")
    .replace(/^## (.*)$/gm, "<h2>$1</h2>").replace(/^# (.*)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/^> (.*)$/gm, "<blockquote>$1</blockquote>")
    .replace(/\|([^\n]+)\|\n/g, (row) => {
      const cells = row.split("|").slice(1, -2).map((c) => c.trim());
      if (!cells.length || /^[-: ]+$/.test(cells.join(""))) return "";
      return "<tr>" + cells.map((c) => `<td>${c}</td>`).join("") + "</tr>";
    });
}

function canvasCtx(id) {
  const canvas = $(id);
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || canvas.parentElement.clientWidth || 320;
  const h = canvas.clientHeight || 240;
  canvas.width = Math.max(1, Math.round(w * dpr));
  canvas.height = Math.max(1, Math.round(h * dpr));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

function setupCanvas(id) { return canvasCtx(id); }

function clear(c) {
  c.ctx.clearRect(0, 0, c.w, c.h);
  c.ctx.fillStyle = "transparent";
}

/* temperature colormap: cyan (cool) -> amber (hot) -> red (extreme) */
function tempColor(t, min, max) {
  const span = Math.max(max - min, 1e-6);
  const x = Math.min(1, Math.max(0, (t - min) / span));
  const hue = 200 - 185 * x;
  return `hsl(${hue}, 88%, 56%)`;
}

function drawLegend() {
  const el = $("hmLegend");
  const d = state.data;
  const min = d.heatmap.min_c, max = d.heatmap.max_c;
  const stops = [];
  for (let i = 0; i <= 12; i++) {
    const t = min + (max - min) * i / 12;
    stops.push(`${tempColor(t, min, max)} ${(i * 100 / 12).toFixed(1)}%`);
  }
  el.style.background = `linear-gradient(90deg, ${stops.join(", ")})`;
  $("hmMin").textContent = fmt(min) + " °C";
  $("hmMax").textContent = fmt(max) + " °C";
}

/* ------------------------------------------------------------ starfield */

function starfield() {
  const canvas = $("starfield");
  const ctx = canvas.getContext("2d");
  let stars = [], w = 0, h = 0;
  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
    const n = Math.min(220, Math.floor((w * h) / 9000));
    stars = Array.from({ length: n }, () => ({
      x: Math.random() * w, y: Math.random() * h,
      r: Math.random() * 1.2 + 0.3,
      a: Math.random() * 0.5 + 0.15,
      v: Math.random() * 0.03 + 0.004,
      tw: Math.random() * Math.PI * 2,
    }));
  }
  resize();
  window.addEventListener("resize", resize);
  function tick() {
    ctx.clearRect(0, 0, w, h);
    for (const s of stars) {
      s.tw += 0.02;
      s.y -= s.v;
      if (s.y < -2) { s.y = h + 2; s.x = Math.random() * w; }
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(190, 210, 255, ${s.a * (0.55 + 0.45 * Math.sin(s.tw))})`;
      ctx.fill();
    }
    requestAnimationFrame(tick);
  }
  tick();
}

/* -------------------------------------------------------------- controls */

const PROFILE_KEY = "calorai.profile";

function readProfile() {
  let p = { units: "c", intensity: "moderate", home_district: "", voice: false };
  try { p = Object.assign(p, JSON.parse(localStorage.getItem(PROFILE_KEY) || "{}")); } catch (_) { /* ignore */ }
  return p;
}

function saveProfile() {
  const p = readProfile();
  p.units = $("units").value;
  p.intensity = $("intensity").value;
  p.home_district = $("homeDistrict").value;
  localStorage.setItem(PROFILE_KEY, JSON.stringify(p));
}

function applyProfile() {
  const p = readProfile();
  $("units").value = p.units;
  $("intensity").value = p.intensity;
  $("homeDistrict").value = p.home_district || "";
  $("voiceState").textContent = p.voice ? "on" : "off";
}

function profilePayload() {
  const p = readProfile();
  return {
    units: $("units").value,
    intensity: $("intensity").value,
    home_district: $("homeDistrict").value || null,
    voice: p.voice,
  };
}

async function loadDistricts() {
  try {
    const res = await fetch("/api/districts");
    const list = await res.json();
    $("district").innerHTML = list.map((d) =>
      `<option value="${esc(d.key)}">${esc(d.name)} (mean ${fmt(d.base_mean_c)} °C)</option>`).join("");
    $("homeDistrict").innerHTML = "<option value=\"\">— none —</option>" +
      list.map((d) => `<option value="${esc(d.key)}">${esc(d.name)}</option>`).join("");
  } catch (e) {
    $("status").textContent = "failed to load districts";
  }
}

for (let h = 0; h <= 23; h++) {
  $("hour").innerHTML += `<option value="${h}"${h === 14 ? " selected" : ""}>${String(h).padStart(2, "0")}:00</option>`;
}

function auditParams() {
  return new URLSearchParams({
    district: $("district").value,
    date: $("date").value,
    hour: $("hour").value,
    threshold_c: $("threshold").value,
    source: $("source").value,
  });
}

async function runAudit() {
  const btn = $("run");
  btn.disabled = true;
  $("status").innerHTML = '<span class="spinner"></span> computing…';
  try {
    const res = await fetch("/api/analysis?" + auditParams().toString());
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      $("status").innerHTML = `error: ${esc(err.detail || res.status)}`;
      return;
    }
    state.data = await res.json();
    state.auditHour = state.data.hour;
    renderAll();
    $("status").textContent =
      `source: ${state.data.source} · ${state.data.tile_count_total} tiles shown ×${Math.ceil(state.data.tile_count_total / Math.max(1, state.data.tile_count_shown))} ` +
      `· ${state.data.district} ${state.data.date} ${String(state.data.hour).padStart(2, "0")}:00`;
    $("pdf").disabled = false;
    $("export").disabled = false;
  } catch (e) {
    $("status").textContent = "network error: " + e;
  } finally {
    btn.disabled = false;
  }
}

/* ------------------------------------------------------------------ acts */

function renderAll() {
  renderOverview();
  renderPhysics();
  renderAnalytics();
}

function renderOverview() {
  const d = state.data;
  $("sMax").textContent = fmt(d.snapshotMax ?? d.heatmap.max_c) + " °C";
  $("sWbgt").textContent = fmt(d.exposure.wbgt_c) + " °C";
  $("sHrs").textContent = fmt(d.exposure.exceedance_hours, 1) + " h";
  $("sCost").textContent = fmtMoney(d.analysis.economy.total_usd_per_year) + "/yr";
  $("sRisk").textContent = String(d.vulnerability.score.band || "—").toUpperCase();
  drawLegend();
  updateHeatmap();
  drawDiurnal();
}

function shiftFor(hour) {
  const d = state.data;
  const app = d.diurnal && d.diurnal.apparent_c;
  const base = app && app[d.hour];
  const target = app && app[hour];
  return app && base !== null && target !== null ? target - base : 0;
}

function updateHeatmap() {
  const d = state.data;
  const hour = +$("hmSlider").value;
  const shift = shiftFor(hour);
  $("hmLabel").textContent = `${String(hour).padStart(2, "0")}:00 local · field shifted ${shift >= 0 ? "+" : ""}${fmt(shift, 2)} °C from ${String(d.hour).padStart(2, "0")}:00`;
  const { ctx, w, h } = setupCanvas("heatmap");
  clear({ ctx, w, h });
  const tiles = d.tiles || [];
  if (!tiles.length) return;
  const lats = tiles.map((t) => t.lat), lons = tiles.map((t) => t.lon);
  const latMin = Math.min(...lats), latMax = Math.max(...lats);
  const lonMin = Math.min(...lons), lonMax = Math.max(...lons);
  const span = Math.max(latMax - latMin, lonMax - lonMin, 1e-6);
  const pad = 18;
  const cell = Math.max(2, Math.min(9, Math.sqrt((w - pad * 2) * (h - pad * 2) / tiles.length)));
  const min = d.heatmap.min_c, max = d.heatmap.max_c;
  for (const t of tiles) {
    const x = pad + ((t.lon - lonMin) / span) * (w - pad * 2);
    const y = pad + (1 - (t.lat - latMin) / span) * (h - pad * 2);
    ctx.fillStyle = tempColor(t.value + shift, min, max);
    ctx.fillRect(x - cell / 2, y - cell / 2, cell, cell);
  }
}

function drawDiurnal() {
  const d = state.data;
  const { ctx, w, h } = setupCanvas("diurnal");
  clear({ ctx, w, h });
  const hours = d.diurnal && d.diurnal.hours ? d.diurnal.hours : Array.from({ length: 24 }, (_, i) => i);
  const app = d.diurnal && d.diurnal.apparent_c ? d.diurnal.apparent_c : [];
  const solar = d.diurnal && d.diurnal.solar_w_m2 ? d.diurnal.solar_w_m2 : [];
  const pad = { l: 30, r: 8, t: 10, b: 22 };
  const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
  const maxSolar = Math.max(...solar.filter((v) => v !== null).map(Math.abs), 1);
  const minA = Math.min(...app.filter((v) => v !== null), 0);
  const maxA = Math.max(...app.filter((v) => v !== null), 1);
  for (const [i, v] of solar.entries()) {
    if (v === null || v === undefined) continue;
    const x = pad.l + (hours[i] / 23) * pw;
    const bh = (Math.abs(v) / maxSolar) * ph * 0.6;
    ctx.fillStyle = "rgba(255, 134, 0, 0.35)";
    ctx.fillRect(x - pw / 48, h - pad.b - bh, pw / 24, bh);
  }
  ctx.strokeStyle = "#7dd3fc";
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  let started = false;
  for (const [i, v] of app.entries()) {
    if (v === null || v === undefined) { started = false; continue; }
    const x = pad.l + (hours[i] / 23) * pw;
    const y = pad.t + (1 - (v - minA) / Math.max(maxA - minA, 1e-6)) * ph;
    if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.strokeStyle = "rgba(145, 168, 214, 0.5)";
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  const ax = pad.l + (d.hour / 23) * pw;
  ctx.moveTo(ax, pad.t); ctx.lineTo(ax, h - pad.b);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#a7b3cc";
  ctx.font = "10px sans-serif";
  ctx.fillText("apparent °C", pad.l + 2, 10);
  ctx.fillText("solar W/m²", pad.l + 2, 20);
}

/* ---------------------------------------------------------------- physics */

function renderPhysics() {
  const d = state.data;
  drawCirculation();
  drawEnergy();
  drawDownburst();
  renderResponse();
}

function drawCirculation() {
  const d = state.data;
  const { ctx, w, h } = setupCanvas("circulation");
  clear({ ctx, w, h });
  const tw = d.thermal_wind || {};
  const gl = tw.gradient_lines || {};
  const lines = gl.lines || [];
  const core = gl.core;
  const pad = 44;
  let pts = [];
  for (const ln of lines) for (const p of ln.path) pts.push(p);
  if (core) pts.push([core.lat, core.lon]);
  const note = $("circNote");
  if (!pts.length) {
    note.textContent = "no trajectories";
    return;
  }
  const lats = pts.map((p) => p[0]), lons = pts.map((p) => p[1]);
  const latMin = Math.min(...lats), latMax = Math.max(...lats);
  const lonMin = Math.min(...lons), lonMax = Math.max(...lons);
  const span = Math.max(latMax - latMin, lonMax - lonMin, 1e-6);
  const X = (lon) => pad + ((lon - lonMin) / span) * (w - pad * 2);
  const Y = (lat) => pad + (1 - (lat - latMin) / span) * (h - pad * 2);
  const colors = { "reached core": "#ff8600", "exited bounds": "#4cd98d", "stalled (flat field)": "#a7b3cc" };
  for (const ln of lines) {
    const path = ln.path;
    const color = colors[ln.termination] || "#a7b3cc";
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.4;
    ctx.globalAlpha = 0.85;
    ctx.beginPath();
    path.forEach((p, i) => { const x = X(p[1]), y = Y(p[0]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
    ctx.stroke();
    const s = path[0], e = path[path.length - 1];
    ctx.fillStyle = color;
    ctx.beginPath(); ctx.arc(X(s[1]), Y(s[0]), 2.6, 0, Math.PI * 2); ctx.fill();
    if (path.length > 1) {
      const x1 = X(e[1]), y1 = Y(e[0]), x0 = X(path[path.length - 2][1]), y0 = Y(path[path.length - 2][0]);
      const ang = Math.atan2(y1 - y0, x1 - x0);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x1 - 7 * Math.cos(ang - 0.42), y1 - 7 * Math.sin(ang - 0.42));
      ctx.moveTo(x1, y1);
      ctx.lineTo(x1 - 7 * Math.cos(ang + 0.42), y1 - 7 * Math.sin(ang + 0.42));
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  if (core) {
    const cx = X(core.lon), cy = Y(core.lat);
    ctx.fillStyle = "#ff8600";
    ctx.beginPath(); ctx.arc(cx, cy, 6, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#08111f";
    ctx.font = "bold 8px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("CORE", cx, cy + 2.5);
    ctx.textAlign = "left";
  }
  // inflow (street level) + aloft thermal wind arrows (schematic corners)
  const inflow = tw.inflow_direction_deg;
  if (inflow !== null && inflow !== undefined) {
    arrow(ctx, w * 0.16, h * 0.78, inflow, 34, "#ff8600", 2.2);
  }
  const twDeg = tw.thermal_wind_direction_deg;
  if (twDeg !== undefined) {
    arrow(ctx, w * 0.84, h * 0.22, twDeg, 34, "#4cd98d", 2.2, true);
  }
  note.textContent = `${lines.length} gradient lines · inflow ${tw.inflow_direction || "uniform"} · Δp ${fmt(tw.pressure_deficit_hpa, 2)} hPa`;
  $("circKv").innerHTML = [
    ["Inflow speed scale", `${fmt(tw.inflow_speed_scale_m_s, 2)} m/s`],
    ["Core excess vs district mean", `${fmt(tw.core_excess_k, 2)} K`],
    ["Ventilation corridors", String(tw.ventilation_corridors ?? "—")],
    ["Thermal wind aloft", `${fmt(twDeg)}° (warm air right, NH)`],
    ["Gradient", `${fmt(tw.gradient_k_per_km, 2)} K/km`],
  ].map(([k, v]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");
}

function arrow(ctx, x, y, bearingDeg, len, color, lw, dashed = false) {
  const rad = (bearingDeg * Math.PI) / 180;
  const dx = Math.sin(rad), dy = -Math.cos(rad);
  ctx.strokeStyle = color;
  ctx.lineWidth = lw;
  ctx.setLineDash(dashed ? [5, 4] : []);
  ctx.beginPath();
  ctx.moveTo(x - dx * len, y - dy * len);
  ctx.lineTo(x + dx * len, y + dy * len);
  ctx.stroke();
  const ang = Math.atan2(dy, dx);
  ctx.beginPath();
  ctx.moveTo(x + dx * len, y + dy * len);
  ctx.lineTo(x + dx * len - 9 * Math.cos(ang - 0.45), y + dy * len - 9 * Math.sin(ang - 0.45));
  ctx.moveTo(x + dx * len, y + dy * len);
  ctx.lineTo(x + dx * len - 9 * Math.cos(ang + 0.45), y + dy * len - 9 * Math.sin(ang + 0.45));
  ctx.stroke();
  ctx.setLineDash([]);
}

function drawEnergy() {
  const d = state.data;
  const { ctx, w, h } = setupCanvas("energy");
  clear({ ctx, w, h });
  const a = d.attribution || {};
  const rows = [
    ["Solar absorbed", a.solar_flux, "#ff8600"],
    ["Net longwave", -Math.abs(a.longwave_flux || 0), "#7dd3fc"],
    ["Convection", -Math.abs(a.convection_flux || 0), "#a7b3cc"],
    ["Storage", a.storage_flux, "#8a8af0"],
    ["Latent cooling", -Math.abs(a.latent_flux || 0), "#4cd98d"],
  ];
  const maxAbs = Math.max(...rows.map((r) => Math.abs(r[1])), 1);
  const pad = { l: 92, r: 14, t: 6, b: 20 };
  const bw = w - pad.l - pad.r;
  const bh = (h - pad.t - pad.b) / rows.length;
  for (const [i, [label, v, color]] of rows.entries()) {
    const y = pad.t + i * bh + bh * 0.18;
    const frac = Math.abs(v) / maxAbs;
    const barW = frac * bw * 0.92;
    const x0 = v >= 0 ? pad.l + bw / 2 : pad.l + bw / 2 - barW;
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.85;
    ctx.fillRect(x0, y, barW, bh * 0.64);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "rgba(145, 168, 214, 0.5)";
    ctx.beginPath();
    ctx.moveTo(pad.l + bw / 2, pad.t); ctx.lineTo(pad.l + bw / 2, pad.t + rows.length * bh);
    ctx.stroke();
    ctx.fillStyle = "#a7b3cc";
    ctx.font = "10.5px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(label, pad.l - 6, y + bh * 0.42);
    ctx.textAlign = "left";
    ctx.fillStyle = "#eff4ff";
    ctx.fillText(`${v >= 0 ? "+" : "−"}${fmt(Math.abs(v), 0)}`, x0 + barW + (v >= 0 ? 6 : -barW - 6), y + bh * 0.42);
  }
}

function drawDownburst() {
  const d = state.data;
  const { ctx, w, h } = setupCanvas("downburst");
  clear({ ctx, w, h });
  const db = d.downburst || {};
  const series = db.series || [];
  if (!series.length) return;
  const pad = { l: 8, r: 8, t: 8, b: 20 };
  const bw = (w - pad.l - pad.r) / series.length;
  for (const [i, v] of series.entries()) {
    if (v === null || v === undefined) continue;
    ctx.fillStyle = v >= 14 ? "#ff5d5d" : v >= 8 ? "#ff8600" : "rgba(125, 211, 252, 0.75)";
    ctx.fillRect(pad.l + i * bw, pad.t, bw - 2, h - pad.t - pad.b);
    ctx.fillStyle = "#a7b3cc";
    ctx.font = "9px sans-serif";
    ctx.textAlign = "center";
    if (i % 3 === 0) ctx.fillText(String(i), pad.l + i * bw + bw / 2, h - 6);
  }
  ctx.textAlign = "left";
  if (db.peak_hour !== undefined) {
    ctx.strokeStyle = "#eff4ff";
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    const x = pad.l + db.peak_hour * bw + bw / 2;
    ctx.moveTo(x, pad.t); ctx.lineTo(x, h - pad.b);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#eff4ff";
    ctx.fillText(`peak ${fmt(db.peak_depression_k, 1)} K @ ${db.peak_hour}:00 (${db.peak_risk})`, pad.l + 2, 12);
  }
}

function renderResponse() {
  const d = state.data;
  const r = d.response || {};
  const parts = [];
  const m = r.misting || {};
  if (m.headline) {
    parts.push(`<div class="response-card"><h3>Misting — ${esc(m.level || "")}</h3>` +
      `<p>${esc(m.headline)}</p>` +
      `<p>Placement: <b>${esc(m.placement || "—")}</b> side · water <b>${esc(fmt(m.water_m3_per_hour, 1))} m³/h</b> · energy <b>${esc(fmt(m.energy_kwh_per_hour, 1))} kWh/h</b></p>` +
      (m.efficiency_pct !== undefined ? `<p>Evaporative efficiency: <b>${esc(fmt(m.efficiency_pct, 0))}%</b> (humidity-limited)</p>` : "") +
      `</div>`);
  }
  const hr = r.heat_response || {};
  if (hr.band) {
    const actions = (hr.actions || []).slice(0, 4).map((a) => `<p>• ${esc(a.action)}</p>`).join("");
    parts.push(`<div class="response-card"><h3>Heat-response — ${esc(hr.band)}</h3>${actions}</div>`);
  }
  $("responseBody").innerHTML = parts.join("") || "<p class='hint'>no response plan computed</p>";
}

/* --------------------------------------------------------------- analytics */

function renderAnalytics() {
  const d = state.data;
  const st = (d.analysis && d.analysis.statistics) || {};
  drawHistogram(st);
  drawHourly(st.hourly_spread || []);
  drawRadial(st.radial_profile || {});
  renderPercentiles(st);
  renderAnomalies((d.analysis && d.analysis.anomaly) || {});
  renderEquity((d.analysis && d.analysis.equity) || {});
  renderAlerts(d.alerts || []);
  renderSynoptic(d.synoptic || {});
  renderLandcover(d.landcover || {});
  renderElevation(d.elevation || {});
  renderWhatif(d.whatif || {});
  renderSchedule(d.schedule || {});
  renderTerrain(d.terrain || {}, d.thermal_wind || {});
  renderFlight(d.flight || {});
  renderUhi(d.uhi || {});
  renderGeo(d.geomorphology || {});
  renderLake(d.lake_effect || {});
}

function renderUhi(u) {
  if (!u || !u.present) { $("uhiBody").innerHTML = "<p class='hint'>UHI prevalence unavailable</p>"; return; }
  const rows = [
    ["Score / band", `<b>${fmt(u.score,1)}/100 — ${esc(u.band)}</b> · ${esc(u.why||"")}`],
    ["Components (0-1)", `intensity ${fmt(u.components.intensity,2)} · extent ${fmt(u.components.extent,2)} · dist ${fmt(u.components.distribution,2)} · morph ${fmt(u.components.morphology,2)} · persist ${fmt(u.components.persistence,2)}`],
    ["Core excess / max-mean", `${fmt(u.metrics.core_excess_k,1)} K / ${fmt(u.metrics.max_minus_mean_k,1)} K`],
    ["Hot-core share / gini / gap", `${fmt(u.metrics.hot_core_share_pct,1)}% / ${fmt(u.metrics.gini,3)} / ${fmt(u.metrics.quintile_gap_c,1)} K`],
    ["h/w / radial slope / exceedance / retention", `${fmt(u.metrics.h_over_w,2)} / ${fmt(u.metrics.radial_slope_c_per_km,2)}°C/km / ${fmt(u.metrics.exceedance_hours,1)}h / ${fmt(u.metrics.overnight_retention,3)}`],
  ];
  $("uhiBody").innerHTML = rows.map(([k,v])=>`<div><span>${esc(k)}</span><b>${v}</b></div>`).join("");
}

function renderTerrain(t, tw) {
  if (!t || !t.present) { $("terrainBody").innerHTML = "<p class='hint'>terrain unavailable</p>"; return; }
  const rows = [
    ["Renderer", esc(t.renderers ? t.renderers.join(" + ") : "—")],
    ["Elevation (m)", fmt(t.elevation_m,0)],
    ["Slope / aspect", `${fmt(t.slope_deg,1)}° / ${fmt(t.aspect_deg,0)}°`],
    ["Hillshade", fmt(t.hillshade,3)],
    ["TileJSON (MapLibre)", `<a href="${esc(t.tilejson_url)}" target="_blank" rel="noopener">Re:Earth raster-dem</a>`],
    ["Cesium mesh", `<a href="${esc(t.cesium_url)}" target="_blank" rel="noopener">Re:Earth quantized-mesh</a>`],
    ["Thermal wind — gradient", tw.gradient_k_per_km ? fmt(tw.gradient_k_per_km,2)+" K/km → inflow "+esc(tw.inflow_direction||"")+" "+fmt(tw.inflow_direction_deg)+"°" : "—"],
    ["Attribution", esc(t.attribution||"")],
  ];
  $("terrainBody").innerHTML = rows.map(([k,v])=>`<div><span>${esc(k)}</span><b>${v}</b></div>`).join("") + (t.note?`<p class="hint">${esc(t.note)}</p>`:"");
  // preview: tiny hillshade bar + heat drape proxy
  const c = setupCanvas("terrainPreview");
  const pad={l:36,r:12,t:12,b:18}; const pw=c.w-pad.l-pad.r, ph=c.h-pad.t-pad.b;
  c.ctx.fillStyle="#0f1f3a"; c.ctx.fillRect(pad.l,pad.t,pw,ph);
  // hillshade gradient
  const grad=c.ctx.createLinearGradient(pad.l,0,pad.l+pw,0);
  grad.addColorStop(0,"#16283f"); grad.addColorStop(0.5, `rgba(255,255,255,${t.hillshade})`); grad.addColorStop(1,"#c2600a");
  c.ctx.fillStyle=grad; c.ctx.fillRect(pad.l,pad.t,pw,ph*0.55);
  c.ctx.fillStyle="#7dd3fc"; c.ctx.font="10px sans-serif";
  c.ctx.fillText(`Phoenix 2.5D default — toggle to Manhattan 3D`, pad.l+6, pad.t+ph-8);
  c.ctx.fillStyle="#a7b3cc"; c.ctx.font="9px sans-serif";
  c.ctx.fillText("heat drape = tcm tiles; terrain = Re:Earth (free, no key)", pad.l, pad.t-2);
}

function renderFlight(f) {
  if (!f || f.density_altitude_ft==null) { $("flightBody").innerHTML = "<p class='hint'>flight overlay unavailable</p>"; return; }
  const rows = [
    ["ISA temp at field", fmt(f.isa_temp_c,1)+" °C"],
    ["ΔISA (hot day)", fmt(f.delta_isa_c,1)+" K"],
    ["Density altitude", fmt(f.density_altitude_ft,0)+" ft"],
    ["Geostrophic ref — inflow", f.thermal_wind_ref ? esc(f.thermal_wind_ref.inflow_deg||"")+" "+fmt(f.thermal_wind_ref.inflow_deg||f.thermal_wind_ref.inflow_deg) : "—"],
    ["Gradient", f.thermal_wind_ref ? fmt(f.thermal_wind_ref.gradient_k_per_km,2)+" K/km" : "—"],
  ];
  $("flightBody").innerHTML = rows.map(([k,v])=>`<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("") + (f.note?`<p class="hint">${esc(f.note)}</p>`:"");
}

function renderGeo(g) {
  if (!g || !g.present) { $("geoBody").innerHTML = "<p class='hint'>geomorphology unavailable</p>"; return; }
  const rows = [
    ["Landform", esc(g.landform||"—")],
    ["Slope / aspect / hillshade", `${fmt(g.slope_deg,1)}° / ${fmt(g.aspect_deg,0)}° / ${fmt(g.hillshade,3)}`],
    ["h/w", fmt(g.h_over_w,2)],
    ["Cold-air pooling risk", esc(g.cold_air_pooling_risk||"—")],
    ["Ventilated", g.ventilated ? "yes" : "no"],
  ];
  $("geoBody").innerHTML = rows.map(([k,v])=>`<div><span>${esc(k)}</span><b>${v}</b></div>`).join("") + (g.caveat?`<p class="hint">${esc(g.caveat)}</p>`:"");
}

function renderLake(l) {
  if (!l || !l.present) { $("lakeBody").innerHTML = "<p class='hint'>lake effect unavailable</p>"; return; }
  if (!l.lake_detected) { $("lakeBody").innerHTML = `<p class='hint'>no lake detected — ${esc(l.reason||"land-locked")}</p>`; return; }
  const rows = [
    ["Lake", esc(l.lake_name||"—")],
    ["Lake cool ΔT", fmt(l.lake_cool_K,1)+" K"],
    ["Lake share", fmt(l.lake_tile_share_pct,1)+" %"],
    ["Breeze", `${fmt(l.breeze_proxy.speed_m_s,1)} m/s @ ${fmt(l.breeze_proxy.bearing_deg,0)}° from ${esc(l.breeze_proxy.from_lake||"")}`],
    ["Evaporative boost", fmt(l.evaporative_boost,3)],
    ["Cooling lever", fmt(l.cooling_lever_K,1)+" K (diagnostic)"],
  ];
  $("lakeBody").innerHTML = rows.map(([k,v])=>`<div><span>${esc(k)}</span><b>${v}</b></div>`).join("") + (l.caveat?`<p class="hint">${esc(l.caveat)}</p>`:"");
}

function renderWhatif(w) {
  if (!w || !w.present) { $("whatifBody").innerHTML = "<p class='hint'>what-if unavailable</p>"; return; }
  const rows = [
    ["Albedo before → after", `${fmt(w.albedo_before,2)} → ${fmt(w.albedo_after,2)}`],
    ["ΔT on hottest 20%", fmt(w.delta_t_c) + " °C"],
    ["Removed flux", fmt(w.removed_flux_w_m2,0) + " W/m²"],
    ["Annual saving (one 400m² tile)", fmtMoney(w.annual_saving_usd)],
    ["Payback", w.payback_years ? fmt(w.payback_years,1) + " yr" : "—"],
    ["Scope", esc(w.scope || "")],
  ];
  $("whatifBody").innerHTML = rows.map(([k,v])=>`<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");
}

function renderSchedule(sc) {
  if (!sc || !sc.present) { $("scheduleBody").innerHTML = "<p class='hint'>schedule unavailable</p>"; return; }
  const rows = sc.rows || [];
  const head = "<div class='row header'><span>Hour</span><span>WBGT</span><span>Work%</span></div>";
  const body = rows.map(r=> r.present===false ? `<div class="row"><span>${r.hour}:00</span><span>—</span></div>` : `<div class="row"><span>${r.hour}:00</span><span>${fmt(r.wbgt_c)}°C ${esc(r.band)}</span><span>${r.work_pct}%</span></div>`).join("");
  $("scheduleBody").innerHTML = head + body + (sc.note ? `<p class="hint">${esc(sc.note)}</p>` : "");
}

function drawHistogram(st) {
  const { ctx, w, h } = setupCanvas("histogram");
  clear({ ctx, w, h });
  const hist = st.histogram || {};
  const edges = hist.bin_edges_c || [], counts = hist.counts || [];
  const pad = { l: 30, r: 8, t: 14, b: 22 };
  const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
  const maxC = Math.max(...counts, 1);
  const bw = pw / Math.max(edges.length - 1, 1);
  for (const [i, c] of counts.entries()) {
    ctx.fillStyle = "rgba(255, 134, 0, 0.75)";
    ctx.fillRect(pad.l + i * bw + 1, pad.t + ph - (c / maxC) * ph, bw - 2, (c / maxC) * ph);
  }
  const s = st.summary || {};
  if (s.mean_c !== undefined && s.std_c !== undefined) {
    const mu = s.mean_c, sd = Math.max(s.std_c, 1e-9);
    ctx.strokeStyle = "#7dd3fc";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    const n = hist.n || 1, binW = edges.length > 1 ? edges[1] - edges[0] : 1;
    for (let i = 0; i <= 160; i++) {
      const x = edges[0] + ((edges[edges.length - 1] - edges[0]) * i) / 160;
      const t = (x - mu) / sd;
      const y = (Math.exp(-0.5 * t * t) / (sd * Math.sqrt(2 * Math.PI))) * n * binW;
      const px = pad.l + ((x - edges[0]) / Math.max(edges[edges.length - 1] - edges[0], 1e-9)) * pw;
      const py = pad.t + ph - (y / maxC) * ph;
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.stroke();
  }
  ctx.fillStyle = "#a7b3cc";
  ctx.font = "10px sans-serif";
  ctx.textAlign = "left";
  const nm = st.normality || {};
  $("histNote").textContent =
    `${hist.n ?? "—"} tiles · skew ${fmt(s.skewness, 2)} · kurt ${fmt(s.kurtosis, 2)} · ${nm.test || ""} p=${nm.p_value ?? "—"}`;
}

function drawHourly(hourly) {
  const { ctx, w, h } = setupCanvas("hourly");
  clear({ ctx, w, h });
  const rows = hourly.filter((x) => x !== null);
  if (!rows.length) return;
  const pad = { l: 26, r: 6, t: 10, b: 22 };
  const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
  const all = rows.flatMap((r) => [r.min_c, r.q1_c, r.median_c, r.q3_c, r.max_c]);
  const min = Math.min(...all), max = Math.max(...all);
  const Y = (v) => pad.t + (1 - (v - min) / Math.max(max - min, 1e-6)) * ph;
  const bw = pw / 24;
  for (const r of rows) {
    const x = pad.l + r.hour * bw + bw / 2;
    ctx.strokeStyle = "#a7b3cc";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, Y(r.min_c)); ctx.lineTo(x, Y(r.max_c));
    ctx.stroke();
    ctx.fillStyle = "rgba(255, 134, 0, 0.25)";
    ctx.fillRect(x - bw * 0.32, Y(r.q3_c), bw * 0.64, Y(r.q1_c) - Y(r.q3_c));
    ctx.strokeStyle = "#ff8600";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(x - bw * 0.32, Y(r.median_c)); ctx.lineTo(x + bw * 0.32, Y(r.median_c));
    ctx.stroke();
  }
  ctx.fillStyle = "#a7b3cc";
  ctx.font = "9px sans-serif";
  ctx.textAlign = "center";
  for (let hh = 0; hh < 24; hh += 4) ctx.fillText(String(hh), pad.l + hh * bw + bw / 2, h - 6);
  ctx.textAlign = "left";
}

function drawRadial(prof) {
  const { ctx, w, h } = setupCanvas("radial");
  clear({ ctx, w, h });
  const pad = { l: 34, r: 10, t: 12, b: 22 };
  const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;
  const dist = prof.dist_km || [], means = prof.mean_c || [];
  if (!dist.length) return;
  const minD = Math.min(...dist), maxD = Math.max(...dist);
  const minT = Math.min(...means), maxT = Math.max(...means);
  const X = (v) => pad.l + ((v - minD) / Math.max(maxD - minD, 1e-9)) * pw;
  const Y = (v) => pad.t + (1 - (v - minT) / Math.max(maxT - minT, 1e-9)) * ph;
  ctx.fillStyle = "rgba(255, 134, 0, 0.85)";
  for (const [i, v] of means.entries()) {
    ctx.beginPath();
    ctx.arc(X(dist[i]), Y(v), 3.4, 0, Math.PI * 2);
    ctx.fill();
  }
  if (prof.slope_c_per_km !== undefined) {
    ctx.strokeStyle = "#7dd3fc";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(X(minD), Y(prof.slope_c_per_km * minD + prof.intercept_c));
    ctx.lineTo(X(maxD), Y(prof.slope_c_per_km * maxD + prof.intercept_c));
    ctx.stroke();
  }
  ctx.fillStyle = "#a7b3cc";
  ctx.font = "10px sans-serif";
  $("radialNote").textContent =
    `slope ${fmt(prof.slope_c_per_km, 2)} °C/km · R² ${fmt(prof.r2, 2)}`;
}

function renderPercentiles(st) {
  const s = st.summary || {};
  const o = st.outliers || {};
  const nm = st.normality || {};
  const rows = [
    ["Min / Max", `${fmt(s.min_c)} / ${fmt(s.max_c)} °C`],
    ["Mean ± std", `${fmt(s.mean_c)} ± ${fmt(s.std_c, 2)} °C`],
    ["Median / IQR", `${fmt(s.median_c)} / ${fmt(s.iqr_c, 2)} °C`],
    ["P05 / P25 / P75 / P95", `${fmt(s.p05_c)} / ${fmt(s.p25_c)} / ${fmt(s.p75_c)} / ${fmt(s.p95_c)} °C`],
    ["Skewness / kurtosis", `${fmt(s.skewness, 2)} / ${fmt(s.kurtosis, 2)}`],
    ["Tukey outliers (1.5×IQR)", `${o.count ?? 0} (${fmt(o.pct, 1)}%)`],
    ["Outlier fences", `${fmt(o.low_fence_c)} … ${fmt(o.high_fence_c)} °C`],
    ["Normality", `${nm.test || "—"} · p=${nm.p_value ?? "—"} → ${nm.normal ? "normal" : "not normal"}`],
  ];
  $("percentileBody").innerHTML = rows.map(([k, v]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("") +
    (nm.advisory ? `<p class="hint">${esc(nm.advisory)}</p>` : "");
}

function renderAnomalies(an) {
  if (!an.present) {
    $("anomalyBody").innerHTML = "<p class='hint'>anomaly layer unavailable</p>";
    return;
  }
  const head = `<p class="hint">${esc(an.n_flagged)}/${esc(an.n_tiles)} tiles flagged (${esc(fmt(an.flagged_pct, 0))}%)</p>`;
  const rows = (an.tiles || []).slice(0, 5).map((t) =>
    `<div class="row"><span>${fmt(t.value_c)} °C · z=${fmt(t.z_score, 1)}</span>` +
    `<span class="why">${esc((t.reasons || []).join("; "))}</span></div>`).join("");
  $("anomalyBody").innerHTML = head + rows;
}

function renderEquity(eq) {
  if (!eq.present) {
    $("equityBody").innerHTML = "<p class='hint'>equity layer unavailable</p>";
    return;
  }
  const rows = [
    ["Gini coefficient", fmt(eq.gini, 3)],
    ["Quintile gap", `${fmt(eq.quintile_gap_c, 1)} K`],
    ["Above threshold", `${fmt(eq.share_above_threshold_pct, 1)}% (${fmt(eq.threshold_c, 0)} °C)`],
    ["Hot-core share", `${fmt(eq.hot_core_share_pct, 1)}%`],
    ["Field mean / max", `${fmt(eq.mean_c)} / ${fmt(eq.max_c)} °C`],
  ];
  $("equityBody").innerHTML = rows.map(([k, v]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("") +
    (eq.note ? `<p class="hint">${esc(eq.note)}</p>` : "");
}

function renderAlerts(alerts) {
  if (!alerts.length) {
    $("alertsBody").innerHTML = "<p class='hint'>no alerts raised</p>";
    return;
  }
  $("alertsBody").innerHTML = alerts.map((a) =>
    `<div class="alert"><span class="sev">${esc(a.severity || "INFO")}</span> — ${esc(a.rule || "")}: ${esc(a.message || "")}</div>`).join("");
}

function renderSynoptic(syn) {
  if (!syn || !syn.present) {
    $("synopticBody").innerHTML = "<p class='hint'>synoptic layer unavailable — " + esc(syn && syn.reason || "no diurnal series") + "</p>";
    return;
  }
  const rows = [
    ["Heat-wave-day", `${syn.heat_wave_day ? "yes" : "no"} (${esc(syn.heat_wave_band)}) · longest stretch ${fmt(syn.longest_hot_stretch_hours, 0)} h`],
    ["Heat-dome / omega-block", esc(syn.dome_band) + (syn.dome_detail && syn.dome_detail.clear_hot_hours != null ? ` · ${syn.dome_detail.clear_hot_hours} clear-hot hours` : "")],
    ["Fire-weather band", `${esc(syn.fire_band)} · max VPD ${fmt(syn.max_vpd_kpa, 2)} kPa · mean ${fmt(syn.mean_vpd_kpa, 2)} kPa`],
  ];
  $("synopticBody").innerHTML = rows.map(([k, v]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("") +
    (syn.caveat ? `<p class="hint">${esc(syn.caveat)}</p>` : "");
  // VPD bar chart
  const series = syn.vpd_series_kpa || [];
  if (!series.length) return;
  const c = setupCanvas("synopticChart");
  const pad = { l: 38, r: 12, t: 16, b: 22 };
  const plotW = c.w - pad.l - pad.r;
  const plotH = c.h - pad.t - pad.b;
  const maxV = Math.max(...series, 4.5);
  c.ctx.strokeStyle = "#2a3a52"; c.ctx.lineWidth = 0.7;
  c.ctx.beginPath(); c.ctx.moveTo(pad.l, pad.t); c.ctx.lineTo(pad.l, pad.t + plotH); c.ctx.lineTo(pad.l + plotW, pad.t + plotH); c.ctx.stroke();
  const bandColor = { low: "#4a7a5a", moderate: "#c2600a", high: "#a02020" }[syn.fire_band] || "#4a7a5a";
  const bw = plotW / series.length * 0.82;
  series.forEach((v, i) => {
    const x = pad.l + (i + 0.5) * plotW / series.length - bw / 2;
    const h = (v / maxV) * plotH;
    c.ctx.fillStyle = bandColor; c.ctx.fillRect(x, pad.t + plotH - h, bw, h);
  });
  [2.5, 4.0].forEach((th) => {
    const y = pad.t + plotH - (th / maxV) * plotH;
    c.ctx.strokeStyle = "#7dd3fc"; c.ctx.setLineDash([3, 3]); c.ctx.beginPath(); c.ctx.moveTo(pad.l, y); c.ctx.lineTo(pad.l + plotW, y); c.ctx.stroke(); c.ctx.setLineDash([]);
    c.ctx.fillStyle = "#7dd3fc"; c.ctx.font = "9px sans-serif"; c.ctx.fillText(th + " kPa", pad.l + plotW - 38, y - 3);
  });
  c.ctx.fillStyle = "#a7b3cc"; c.ctx.font = "9px sans-serif";
  c.ctx.fillText("Hour →", pad.l + plotW / 2 - 16, pad.t + plotH + 16);
  c.ctx.fillText("VPD (kPa)", 4, pad.t + 10);
}

function renderLandcover(lc) {
  if (!lc || !lc.present) {
    $("landcoverBody").innerHTML = "<p class='hint'>" + esc(lc && lc.reason || "no parcel imagery for this district") + "</p>";
    return;
  }
  const rows = [
    ["Parcel", esc(lc.parcel || "—")],
    ["Sky-view factor — sky % (street)", fmt(lc.svf_sky_pct, 1) + "%"],
    ["Shade — tree+building % (street)", fmt(lc.shade_pct, 1) + "%"],
    ["Green — tree+plant % (satellite)", fmt(lc.green_pct, 1) + "%"],
    ["Impervious — building+ground %", fmt(lc.impervious_pct, 1) + "%"],
  ];
  $("landcoverBody").innerHTML = rows.map(([k, v]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("") +
    `<p class="hint">satellite ${esc((lc.satellite && lc.satellite.file) || "")} · street-view ${esc((lc.streetview && lc.streetview.file) || "")}</p>` +
    (lc.note ? `<p class="hint">${esc(lc.note)}</p>` : "");
}

function renderElevation(ev) {
  if (!ev || ev.elevation_m == null) {
    $("elevationBody").innerHTML = "<p class='hint'>elevation unavailable</p>";
    return;
  }
  const rows = [
    ["Elevation (m a.s.l.)", fmt(ev.elevation_m, 0)],
    ["ISA lapse correction 6.5 K/km", fmt(ev.lapse_correction_c, 2) + " °C"],
    ["Air — raw (°C)", fmt(ev.air_raw_c, 1)],
    ["Air — sea-level equivalent (°C)", fmt(ev.air_sea_level_c, 1)],
  ];
  $("elevationBody").innerHTML = rows.map(([k, v]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("") +
    (ev.note ? `<p class="hint">${esc(ev.note)}</p>` : "");
}

/* ------------------------------------------------------------------- ask */

function appendChat(role, html) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  div.innerHTML = html;
  $("chatLog").appendChild(div);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
  return div;
}

function typewriter(el, html, done) {
  const text = html;
  const caret = `<span class="caret"></span>`;
  el.innerHTML = caret;
  let i = 0;
  const step = () => {
    if (i >= text.length) {
      el.innerHTML = text;
      if (done) done();
      return;
    }
    i += 3;
    el.innerHTML = text.slice(0, i) + caret;
    setTimeout(step, 8);
  };
  step();
}

async function sendAsk(query) {
  const q = (query || $("ask").value || "").trim();
  if (q.length < 3) return;
  $("ask").value = "";
  appendChat("user", esc(q));
  const bubble = appendChat("agent", '<span class="spinner"></span> planning…');
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: q,
        district: $("district").value,
        date: $("date").value,
        hour: +$("hour").value,
        threshold_c: +$("threshold").value,
        source: $("source").value,
        profile: profilePayload(),
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      bubble.innerHTML = `<strong>error</strong> ${esc(data.detail || res.status)}`;
      return;
    }
    const rows = (data.trace || []).map((t) =>
      `<tr><td>${esc(t.tool)}</td><td class="${t.ok ? "ok" : "err"}">${t.ok ? "ok" : "fail"}</td>` +
      `<td>${esc(String(t.summary || ""))}</td><td>${t.duration_ms}ms</td></tr>`).join("");
    const traceHtml = `<details><summary>trace · ${esc(data.mode)} · refinement ${esc(data.refinement || "n/a")} · ${data.duration_ms}ms</summary>` +
      `<table><tr><th>tool</th><th>status</th><th>summary</th><th>ms</th></tr>${rows}</table></details>`;
    typewriter(bubble, md(data.answer) + `<div class="trace">${traceHtml}</div>`, () => {
      if (readProfile().voice) speak(data.answer_tldr);
    });
  } catch (e) {
    bubble.innerHTML = `<strong>network error</strong> ${esc(String(e))}`;
  }
}

/* ------------------------------------------------------------------ voice */

let recognition = null;
try {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SR) {
    recognition = new SR();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (ev) => {
      const q = ev.results[0][0].transcript;
      $("ask").value = q;
      setMic(false);
      sendAsk(q);
    };
    recognition.onerror = () => setMic(false);
    recognition.onend = () => setMic(false);
  } else {
    $("voiceHint").textContent = "Voice input needs a Chromium/Safari browser; typing works everywhere.";
  }
} catch (_) { /* SpeechRecognition constructor may throw on some builds */ }

function setMic(on) {
  $("mic").classList.toggle("listening", on);
  $("mic").textContent = on ? "⏹" : "🎙";
}

$("mic").onclick = () => {
  if (!recognition) return;
  if ($("mic").classList.contains("listening")) { recognition.stop(); return; }
  try {
    recognition.start();
    setMic(true);
  } catch (_) { /* already started */ }
};

function speak(text) {
  if (!("speechSynthesis" in window) || !text) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1.04;
  u.pitch = 1.0;
  window.speechSynthesis.speak(u);
}

/* ------------------------------------------------------------------- init */

$("run").onclick = runAudit;
$("askbtn").onclick = () => sendAsk();
$("ask").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); sendAsk(); }
});
$("hmSlider").oninput = updateHeatmap;
$("theme").onclick = () => {
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === "dark" ? "light" : "dark";
  try { localStorage.setItem("calorai.theme", html.dataset.theme); } catch (_) { /* ignore */ }
  renderAll();
};
$("voiceToggle").onclick = () => {
  const p = readProfile();
  p.voice = !p.voice;
  localStorage.setItem(PROFILE_KEY, JSON.stringify(p));
  applyProfile();
};
["units", "intensity", "homeDistrict"].forEach((id) => $(id).addEventListener("change", saveProfile));

$("pdf").onclick = () => { window.location.href = "/api/report?" + auditParams().toString(); };
$("export").onclick = () => { window.location.href = "/api/export?" + auditParams().toString(); };
$("brief").onclick = async () => {
  $("status").textContent = "briefing all districts…";
  try {
    const qs = new URLSearchParams({ date: $("date").value, threshold_c: $("threshold").value, source: $("source").value });
    const res = await fetch("/api/brief?" + qs.toString());
    const j = await res.json();
    const rows = (j.districts || []).map(d=> `<div class="row"><span>${esc(d.district || d.key)}</span><span>${d.vuln_score!=null?fmt(d.vuln_score,0)+" "+esc(d.vuln_band||""):"—"}</span><span>${fmt(d.wbgt_c)}°C max ${fmt(d.max_c)}°C</span></div>`).join("");
    appendChat("agent", `<strong>Morning brief ${esc(j.date)}</strong><div class="kv-table">${rows}</div>`);
    document.querySelector('[data-act=\"ask\"]').click();
  } catch(e) { $("status").textContent = "brief error: "+e; }
};
$("modeMaplibre").onclick = () => { $("district").value="phoenix"; $("modeMaplibre").className="pill primary"; $("modeCesium").className="pill ghost"; runAudit(); };
$("modeCesium").onclick = () => { $("district").value="manhattan"; $("modeCesium").className="pill primary"; $("modeMaplibre").className="pill ghost"; runAudit(); };

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    document.querySelectorAll(".act").forEach((s) => { s.hidden = s.id !== `act-${tab.dataset.act}`; });
    if (tab.dataset.act !== "ask") renderAll();
  };
});

(function init() {
  starfield();
  try {
    const theme = localStorage.getItem("calorai.theme");
    if (theme) document.documentElement.dataset.theme = theme;
  } catch (_) { /* ignore */ }
  applyProfile();
  loadDistricts().then(runAudit);
})();