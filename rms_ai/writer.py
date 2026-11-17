"""Fayl yaratish: Word (.docx) markdown matndan, Excel (.xlsx) jadval qatorlaridan, oddiy matn fayllari.

Fayllar berilgan papkaga yoziladi va hech qachon mavjud faylni almashtirmaydi (nom band bo'lsa, raqam qo'shiladi).
"""
from __future__ import annotations

import re
from pathlib import Path

from . import markdown

TEXT_TYPES = (".txt", ".md", ".csv", ".html", ".json")
MAX_ROWS, MAX_SHEETS = 100_000, 50
FENCE = re.compile(r"^```")
BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


class WriteError(Exception):
    pass


def target(folder: Path | str, name: str, suffix: str) -> Path:
    """Xavfsiz va band bo'lmagan fayl yo'li: nom tozalanadi, kengaytma to'g'rilanadi, takror bo'lsa raqam qo'shiladi."""
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", Path(str(name).strip()).name)
    stem = (stem[: -len(suffix)] if stem.lower().endswith(suffix) else stem).strip(" .")[:80] or "hujjat"
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path, n = folder / (stem + suffix), 2
    while path.exists():
        path, n = folder / f"{stem} ({n}){suffix}", n + 1
    return path


def text_file(folder: Path | str, name: str, content: str) -> Path:
    suffix = Path(str(name)).suffix.lower()
    if suffix not in TEXT_TYPES:
        raise WriteError(f"Matn fayli uchun kengaytma {', '.join(TEXT_TYPES)} dan biri bo'lsin.")
    path = target(folder, name, suffix)
    # Excel CSV'dagi kirill va o'zbek harflarini to'g'ri ochishi uchun BOM kerak
    path.write_text(content, encoding="utf-8-sig" if suffix == ".csv" else "utf-8")
    return path


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _runs(paragraph, text: str, bold: bool = False) -> None:
    from docx.shared import Pt

    for piece, tags in markdown.inline(text):
        run = paragraph.add_run(piece)
        run.bold = bold or "b" in tags
        if "ic" in tags:
            run.font.name, run.font.size = "Consolas", Pt(10)
        link = next((t[5:] for t in tags if t.startswith("link:")), "")
        if link:
            run.underline = True
            paragraph.add_run(f" ({link})")


def docx(folder: Path | str, name: str, text: str) -> Path:
    """Markdown matndan Word hujjati: sarlavhalar, ro'yxatlar, jadvallar, qalin matn, kod bloklari."""
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError:
        raise WriteError("Word fayl yaratish uchun python-docx kerak (pip install python-docx).")
    doc = Document()
    lines, i = str(text).replace("\r\n", "\n").split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if FENCE.match(line.strip()):
            code = []
            i += 1
            while i < len(lines) and not FENCE.match(lines[i].strip()):
                code.append(lines[i])
                i += 1
            run = doc.add_paragraph().add_run("\n".join(code))
            run.font.name, run.font.size = "Consolas", Pt(10)
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and TABLE_RULE.match(lines[i + 1]):
            rows = [_cells(line)]
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            table = doc.add_table(rows=len(rows), cols=max(len(r) for r in rows))
            table.style = "Table Grid"
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    _runs(table.cell(r, c).paragraphs[0], value, bold=r == 0)
            doc.add_paragraph()
            continue
        elif HEADING.match(line):
            m = HEADING.match(line)
            _runs(doc.add_heading(level=min(len(m.group(1)), 4)), m.group(2))
        elif BULLET.match(line):
            _runs(doc.add_paragraph(style="List Bullet"), BULLET.match(line).group(1))
        elif NUMBERED.match(line):
            _runs(doc.add_paragraph(style="List Number"), NUMBERED.match(line).group(1))
        elif line.strip():
            _runs(doc.add_paragraph(), line.strip())
        i += 1
    path = target(folder, name, ".docx")
    doc.save(str(path))
    return path


def xlsx(folder: Path | str, name: str, sheets: list[dict]) -> Path:
    """Jadval(lar)dan Excel fayli. sheets: [{"name": "...", "rows": [[...], ...]}]; "=" bilan boshlangan katak formula."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise WriteError("Excel fayl yaratish uchun openpyxl kerak (pip install openpyxl).")
    if not isinstance(sheets, list) or not sheets or len(sheets) > MAX_SHEETS:
        raise WriteError(f"sheets: 1 dan {MAX_SHEETS} gacha varaq ro'yxati bo'lsin.")
    book = Workbook()
    book.remove(book.active)
    for n, sheet in enumerate(sheets, 1):
        rows = sheet.get("rows") if isinstance(sheet, dict) else None
        if not isinstance(rows, list) or not all(isinstance(r, list) for r in rows):
            raise WriteError("Har bir varaqda rows: qatorlar ro'yxati (har qator kataklar ro'yxati) bo'lsin.")
        if len(rows) > MAX_ROWS:
            raise WriteError(f"Bitta varaqda {MAX_ROWS} dan ortiq qator bo'lmasin.")
        title = re.sub(r"[\[\]:*?/\\]", "_", str(sheet.get("name") or f"Varaq{n}"))[:31] or f"Varaq{n}"
        if title in book.sheetnames:
            raise WriteError(f"Varaq nomi takrorlangan: {title}")
        ws = book.create_sheet(title)
        widths: dict[int, int] = {}
        for row in rows:
            ws.append([v if isinstance(v, (int, float, bool)) or v is None else str(v) for v in row])
            for c, v in enumerate(row, 1):
                widths[c] = max(widths.get(c, 0), len(str(v)) if v is not None else 0)
        if rows:
            for cell in ws[1]:
                cell.font = Font(bold=True)
            ws.freeze_panes = "A2"
        for c, w in widths.items():
            ws.column_dimensions[get_column_letter(c)].width = min(max(w + 2, 8), 60)
    path = target(folder, name, ".xlsx")
    book.save(str(path))
    return path


def _load_pdf_font(size: int, bold: bool = False):
    from PIL import ImageFont
    names = (["arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"])
    dirs = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts")]
    for d in dirs:
        for n in names:
            p = d / n
            if p.is_file():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    pass
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_w: int) -> list[str]:
    out: list[str] = []
    for raw in str(text or "").splitlines() or [""]:
        if not raw.strip():
            out.append("")
            continue
        cur = ""
        for word in raw.split(" "):
            cand = f"{cur} {word}".strip() if cur else word
            if draw.textlength(cand, font=font) <= max_w:
                cur = cand
            else:
                if cur:
                    out.append(cur)
                cur = word
        if cur:
            out.append(cur)
    return out


def pdf(folder: Path | str, name: str, text: str) -> Path:
    """Matndan ko'p sahifali A4 PDF fayl yaratadi (kirill va lotin harflarini to'liq qo'llab-quvvatlaydi)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise WriteError("PDF yaratish uchun pillow kutubxonasi kerak.")
    w, h, margin = 1240, 1754, 100
    body_font = _load_pdf_font(26, bold=False)
    head_font = _load_pdf_font(32, bold=True)
    pages: list[Image.Image] = []
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    y = margin
    for line in (text or "").splitlines():
        m = HEADING.match(line)
        is_head = bool(m)
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", m.group(2) if m else line)
        font = head_font if is_head else body_font
        step = 44 if is_head else 36
        wrapped = _wrap_text(draw, clean, font, w - 2 * margin) or [""]
        for seg in wrapped:
            if y + step > h - margin:
                pages.append(img)
                img = Image.new("RGB", (w, h), "white")
                draw = ImageDraw.Draw(img)
                y = margin
            if seg:
                draw.text((margin, y), seg, fill="#111827", font=font)
            y += step
        if is_head:
            y += 8
    pages.append(img)
    path = target(folder, name, ".pdf")
    pages[0].save(str(path), "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    return path
