"""Jonli ko'rinish: agent yaratgan faylni brauzerda chat yonida ko'rsatish uchun HTML sahifa.

Sahifa har doim qum qutisida (sandbox) ochiladi: skript ishlashi mumkin, lekin dastur manziliga, cookie'larga,
API'ga yoki tashqi resurs yuklashga yo'l yo'q. Brauzerning o'z iframe navigatsiyasi barcha brauzerlarda to'liq kafolatlanmaydi; maxfiy hujjatlarni ishonchsiz HTML sifatida ochmang.
"""
from __future__ import annotations

import html
from pathlib import Path

from . import docs

CSP = ("sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
       "font-src data:; img-src data: blob:; form-action 'none'; base-uri 'none'; object-src 'none'; "
       "navigate-to 'none'; frame-ancestors 'self'")
TABLES, TEXTS = (".csv", ".xlsx"), (".txt", ".md", ".json")
KINDS = (".html",) + TABLES + TEXTS
MAX_ROWS, MAX_SHEETS = 500, 10
MAX_PREVIEW_BYTES = 10 * 1024 * 1024
STYLE = """<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{margin:0;padding:14px;font:14px/1.45 "Segoe UI",system-ui,Arial,sans-serif;color:#1c2030;background:#fff}
h2{font-size:15px;margin:18px 0 8px}h2:first-child{margin-top:0}.wrap{overflow:auto;border:1px solid #d8dbe6;border-radius:8px}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #e6e8f0;border-right:1px solid #eef0f5;padding:6px 10px;
text-align:left;white-space:nowrap}th{background:#f3f4f9;position:sticky;top:0}td.n{text-align:right;font-variant-numeric:tabular-nums}
tr:hover td{background:#fafbff}p{color:#6b7189;font-size:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 Consolas,monospace}
</style>"""


def _table(rows: list[list[str]]) -> str:
    if not rows:
        return "<p>Bo'sh varaq.</p>"
    width = max(len(r) for r in rows)
    out = ['<div class="wrap"><table>']
    for i, row in enumerate(rows[:MAX_ROWS]):
        cells = []
        for value in list(row) + [""] * (width - len(row)):
            numeric = i > 0 and docs._to_float(value) is not None
            tag = "th" if i == 0 else "td"
            cells.append(f'<{tag}{" class=n" if numeric else ""}>{html.escape(value)}</{tag}>')
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table></div>")
    if len(rows) > MAX_ROWS:
        out.append(f"<p>Birinchi {MAX_ROWS} qator ko'rsatildi (jami {len(rows)}). To'lig'i uchun faylni yuklab oling.</p>")
    return "".join(out)


def _tables(path: Path) -> str:
    name, rows, sheets = docs.table_rows(path, limit=MAX_ROWS + 1)
    if len(sheets) <= 1:
        return _table(rows)
    out = []
    for sheet in sheets[:MAX_SHEETS]:
        rows = rows if sheet == name else docs.table_rows(path, sheet, MAX_ROWS + 1)[1]
        out.append(f"<h2>{html.escape(sheet)}</h2>" + _table(rows))
    return "".join(out)


def page(path: Path) -> str | None:
    """Faylning ko'rinish sahifasi; bu turdagi fayl ko'rsatilmasa None (u faqat yuklab olinadi)."""
    suffix = path.suffix.lower()
    if suffix not in KINDS:
        return None
    if path.stat().st_size > MAX_PREVIEW_BYTES:
        return STYLE + "<p>Ko'rinish uchun fayl 10 MB dan kichik bo'lishi kerak. Faylni yuklab oling.</p>"
    if suffix == ".html":
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        if suffix in TABLES:
            return STYLE + _tables(path)
    except docs.DocError as exc:
        return STYLE + f"<p>{html.escape(str(exc))}</p>"
    if suffix in TEXTS:
        return STYLE + "<pre>" + html.escape(docs.decode_text(path.read_bytes())) + "</pre>"
    return None
