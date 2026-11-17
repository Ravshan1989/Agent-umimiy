"""Monitoring dashboardi: kichik alohida oynada ochiladigan, o'zi yangilanib turadigan sahifa.

Ma'lumot /api/desktop/monitor dan olinadi. Foydalanuvchi nomi va yo'llar tashqaridan keladi,
shuning uchun sahifa ularni faqat textContent orqali chizadi (innerHTML ishlatilmaydi).
"""

MONITOR_PAGE = """<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RMS AI — Monitoring</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; padding: 14px; background: #04061a; color: #e6edf7;
         font: 13px/1.45 "Segoe UI", system-ui, sans-serif; }
  h1 { font-size: 15px; margin: 0 0 10px; display: flex; justify-content: space-between; align-items: center; }
  h2 { font-size: 12px; margin: 16px 0 6px; color: #9fb0c7; text-transform: uppercase; letter-spacing: .04em; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: #34d399; display: inline-block; margin-right: 6px; }
  .dot.off { background: #f87171; }
  .cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .card { background: #101832; border: 1px solid rgba(148,163,184,.2); border-radius: 10px; padding: 10px; }
  .card b { display: block; font-size: 20px; font-variant-numeric: tabular-nums; }
  .card span { color: #9fb0c7; font-size: 11px; }
  .scroll { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th, td { padding: 4px 6px; text-align: left; border-bottom: 1px solid rgba(148,163,184,.12); white-space: nowrap; }
  th { color: #9fb0c7; font-weight: 500; font-size: 11px; }
  td.n, th.n { text-align: right; }
  .slow { color: #fbbf24; } .bad { color: #f87171; }
  .muted { color: #6b7a93; }
  #log { color: #6b7a93; font-size: 11px; margin-top: 14px; word-break: break-all; }
</style>
</head>
<body>
<h1><span><i class="dot" id="dot"></i>Monitoring</span><span class="muted" id="uptime"></span></h1>
<div class="cards">
  <div class="card"><b id="minute">–</b><span>so‘rov / oxirgi daqiqa</span></div>
  <div class="card"><b id="total">–</b><span>jami so‘rov</span></div>
  <div class="card"><b id="online">–</b><span>faol (5 daqiqa)</span></div>
</div>
<h2>Kim ulangan (oxirgi 5 daqiqa)</h2>
<div class="scroll"><table id="users"></table></div>
<h2>Javob vaqti, ms (yo‘llar bo‘yicha)</h2>
<div class="scroll"><table id="paths"></table></div>
<h2>Oxirgi so‘rovlar</h2>
<div class="scroll"><table id="recent"></table></div>
<div id="log"></div>
<script>
const $ = (id) => document.getElementById(id);
function ago(s) { return s < 60 ? s + " s" : s < 3600 ? Math.floor(s / 60) + " daq" : Math.floor(s / 3600) + " soat"; }
function fill(table, head, rows) {
  table.replaceChildren();
  const tr = table.insertRow();
  for (const [label, num] of head) {
    const th = document.createElement("th"); th.textContent = label; if (num) th.className = "n"; tr.appendChild(th);
  }
  if (!rows.length) {
    const td = table.insertRow().insertCell(); td.colSpan = head.length; td.className = "muted"; td.textContent = "Hali ma'lumot yo'q";
  }
  for (const row of rows) {
    const r = table.insertRow();
    row.forEach((cell, i) => {
      const td = r.insertCell();
      const [text, cls] = Array.isArray(cell) ? cell : [cell, ""];
      td.textContent = text; td.className = ((head[i][1] ? "n " : "") + cls).trim();
    });
  }
}
function tone(ms) { return ms >= 1000 ? "bad" : ms >= 200 ? "slow" : ""; }
async function tick() {
  try {
    const res = await fetch("/api/desktop/monitor", { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const d = await res.json();
    $("dot").className = "dot";
    $("uptime").textContent = "ishlayapti: " + ago(d.uptime);
    $("minute").textContent = d.last_minute;
    $("total").textContent = d.total;
    $("online").textContent = d.users.length;
    fill($("users"), [["Foydalanuvchi"], ["IP"], ["So'rov", 1], ["Oxirgi", 1]],
      d.users.map((u) => [u.user, u.ip, u.requests, ago(u.idle) + " oldin"]));
    fill($("paths"), [["Yo'l"], ["Soni", 1], ["O'rtacha", 1], ["95%", 1], ["Eng sekin", 1]],
      d.paths.map((p) => [p.path, p.count, [p.median, tone(p.median)], [p.p95, tone(p.p95)], [p.max, tone(p.max)]]));
    fill($("recent"), [["Qachon"], ["Kim"], ["Yo'l"], ["Kod", 1], ["ms", 1]],
      d.recent.map((r) => [ago(r.at), r.user, r.path, [r.code, r.code >= 500 ? "bad" : r.code >= 400 ? "slow" : ""], [r.ms, tone(r.ms)]]));
    $("log").textContent = "To'liq tarix: " + d.log;
  } catch (e) {
    $("dot").className = "dot off";
  }
}
tick();
setInterval(tick, 2000);
</script>
</body>
</html>
"""
