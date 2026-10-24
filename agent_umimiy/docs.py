"""Office hujjatlari (xlsx, pptx, docx), CSV va jadval tahlili — qo'shimcha kutubxonasiz (faqat standart kutubxona)."""
from __future__ import annotations

import csv
import datetime
import io
import re
import statistics
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

NS_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
NS_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
MAX_ENTRY = 200 * 1024 * 1024
MAX_ROWS = 200_000
OLD_FORMATS = {".xls": ".xlsx", ".ppt": ".pptx", ".doc": ".docx"}


class DocError(Exception):
    pass


def _open_zip(path) -> zipfile.ZipFile:
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocError(f"Fayl buzilgan yoki Office fayli emas: {exc}")
    if any(i.file_size > MAX_ENTRY for i in z.infolist()):
        raise DocError("Fayl ichida juda katta qism bor (xavfsizlik chegarasi).")
    return z


def _rels(z: zipfile.ZipFile, part: str) -> dict:
    """part ning .rels faylidan {id: (type, target)}."""
    d, name = part.rsplit("/", 1) if "/" in part else ("", part)
    rp = f"{d}/_rels/{name}.rels" if d else f"_rels/{name}.rels"
    if rp not in z.namelist():
        return {}
    out = {}
    for r in ET.fromstring(z.read(rp)).iter(NS_REL + "Relationship"):
        t = r.get("Target", "")
        if r.get("TargetMode") == "External":
            continue
        t = t.lstrip("/") if t.startswith("/") else (f"{d}/{t}" if d else t)
        parts = []
        for seg in t.split("/"):  # ../ ni hal qilish
            if seg == "..":
                parts and parts.pop()
            elif seg not in ("", "."):
                parts.append(seg)
        out[r.get("Id")] = (r.get("Type", ""), "/".join(parts))
    return out


# ============================ XLSX ============================
def col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


BUILTIN_DATE_IDS = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))


def _is_date_format(code: str) -> bool:
    code = re.sub(r'"[^"]*"|\\.|\[[^\]]*\]|_.|\*.', "", code)
    return bool(re.search(r"[ymdhs]", code, re.I)) and not re.fullmatch(r"(general|[0#?.,%\-+() E]*)", code.strip(), re.I)


def _fmt_number(v: float) -> str:
    return str(int(v)) if v == int(v) and abs(v) < 1e15 else ("%.15g" % v)


def _fmt_date(serial: float) -> str:
    base = datetime.datetime(1899, 12, 30)
    try:
        dt = base + datetime.timedelta(days=serial)
    except OverflowError:
        return _fmt_number(serial)
    if serial < 1:
        return dt.strftime("%H:%M:%S")
    return dt.strftime("%Y-%m-%d") if dt.time() == datetime.time(0) else dt.strftime("%Y-%m-%d %H:%M:%S")


class Xlsx:
    def __init__(self, path):
        self.z = _open_zip(path)
        names = self.z.namelist()
        if "xl/workbook.xml" not in names:
            raise DocError("Bu .xlsx fayl emas yoki buzilgan.")
        rels = _rels(self.z, "xl/workbook.xml")
        self.sheets: dict[str, str] = {}
        for s in ET.fromstring(self.z.read("xl/workbook.xml")).iter(NS_M + "sheet"):
            rid = s.get(NS_R + "id")
            if rid in rels:
                self.sheets[s.get("name", f"Varaq{len(self.sheets) + 1}")] = rels[rid][1]
        self.shared = self._shared_strings() if "xl/sharedStrings.xml" in names else []
        self.date_styles = self._date_styles() if "xl/styles.xml" in names else set()

    def _shared_strings(self) -> list[str]:
        out = []
        for si in ET.fromstring(self.z.read("xl/sharedStrings.xml")).iter(NS_M + "si"):
            out.append("".join(t.text or "" for t in si.iter(NS_M + "t")))
        return out

    def _date_styles(self) -> set[int]:
        root = ET.fromstring(self.z.read("xl/styles.xml"))
        custom = {int(n.get("numFmtId")): n.get("formatCode", "") for n in root.iter(NS_M + "numFmt")}
        dates = set()
        xfs = root.find(NS_M + "cellXfs")
        for i, xf in enumerate(xfs if xfs is not None else []):
            fid = int(xf.get("numFmtId", 0))
            if fid in BUILTIN_DATE_IDS or (fid in custom and _is_date_format(custom[fid])):
                dates.add(i)
        return dates

    def rows(self, sheet: str, limit: int | None = None):
        if sheet not in self.sheets:
            raise DocError(f"Varaq topilmadi: {sheet}. Mavjud: {', '.join(self.sheets)}")
        n = 0
        with self.z.open(self.sheets[sheet]) as fh:
            for _, el in ET.iterparse(fh, events=("end",)):
                if el.tag != NS_M + "row":
                    continue
                cells: dict[int, str] = {}
                for c in el.iter(NS_M + "c"):
                    ci = col_index(c.get("r", "A1"))
                    cells[ci] = self._value(c)
                width = (max(cells) + 1) if cells else 0
                row = [cells.get(i, "") for i in range(width)]
                rnum = int(el.get("r", n + 1))
                while n + 1 < rnum:  # bo'sh qatorlarni saqlab qolamiz (qator raqamlari mos tushishi uchun)
                    n += 1
                    yield []
                    if limit and n >= limit:
                        return
                n += 1
                yield row
                el.clear()
                if limit and n >= limit:
                    return

    def _value(self, c) -> str:
        t, v = c.get("t"), c.find(NS_M + "v")
        if t == "inlineStr":
            return "".join(x.text or "" for x in c.iter(NS_M + "t"))
        if v is None or v.text is None:
            return ""
        if t == "s":
            i = int(v.text)
            return self.shared[i] if i < len(self.shared) else ""
        if t == "b":
            return "TRUE" if v.text.strip() == "1" else "FALSE"
        if t in ("str", "e", "d"):
            return v.text
        try:
            f = float(v.text)
        except ValueError:
            return v.text
        return _fmt_date(f) if int(c.get("s", 0)) in self.date_styles else _fmt_number(f)


# ============================ DOCX ============================
def read_docx(path) -> str:
    z = _open_zip(path)
    if "word/document.xml" not in z.namelist():
        raise DocError("Bu .docx fayl emas yoki buzilgan.")
    body = ET.fromstring(z.read("word/document.xml")).find(NS_W + "body")
    out: list[str] = []

    def para(p) -> str:
        parts = []
        for el in p.iter():
            if el.tag == NS_W + "t":
                parts.append(el.text or "")
            elif el.tag == NS_W + "tab":
                parts.append("\t")
            elif el.tag in (NS_W + "br", NS_W + "cr"):
                parts.append("\n")
        text = "".join(parts)
        ppr = p.find(NS_W + "pPr")
        style = ""
        if ppr is not None:
            st = ppr.find(NS_W + "pStyle")
            style = (st.get(NS_W + "val", "") if st is not None else "").lower()
            if text.strip() and (ppr.find(NS_W + "numPr") is not None or style.startswith("list")):
                return "• " + text
        m = re.match(r"heading\s*(\d)", style)
        if text.strip() and m:
            return "#" * min(int(m.group(1)), 4) + " " + text
        if text.strip() and style == "title":
            return "# " + text
        return text

    def table(t) -> str:
        rows = []
        for tr in t.findall(NS_W + "tr"):
            cells = [" ".join(para(p).strip() for p in tc.iter(NS_W + "p") if para(p).strip())
                     for tc in tr.findall(NS_W + "tc")]
            rows.append("| " + " | ".join(cells) + " |")
        return "\n".join(rows)

    for el in body:
        if el.tag == NS_W + "p":
            out.append(para(el))
        elif el.tag == NS_W + "tbl":
            out.append(table(el))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


# ============================ PPTX ============================
def read_pptx(path) -> str:
    z = _open_zip(path)
    if "ppt/presentation.xml" not in z.namelist():
        raise DocError("Bu .pptx fayl emas yoki buzilgan.")
    rels = _rels(z, "ppt/presentation.xml")
    pres = ET.fromstring(z.read("ppt/presentation.xml"))
    slides = [rels[s.get(NS_R + "id")][1] for s in pres.iter(NS_P + "sldId") if s.get(NS_R + "id") in rels]

    def shape_text(sp) -> list[str]:
        return [t for t in ("".join(x.text or "" for x in p.iter(NS_A + "t")).strip() for p in sp.iter(NS_A + "p")) if t]

    def walk(el, title: list, body: list):
        for ch in el:
            if ch.tag == NS_P + "sp":
                ph = ch.find(f"{NS_P}nvSpPr/{NS_P}nvPr/{NS_P}ph")
                lines = shape_text(ch)
                if ph is not None and ph.get("type") in ("title", "ctrTitle") and lines:
                    title.append(" ".join(lines))
                else:
                    body += lines
            elif ch.tag == NS_P + "grpSp":
                walk(ch, title, body)
            elif ch.tag == NS_P + "graphicFrame":
                for tr in ch.iter(NS_A + "tr"):
                    cells = ["".join(x.text or "" for x in tc.iter(NS_A + "t")).strip() for tc in tr.findall(NS_A + "tc")]
                    body.append("| " + " | ".join(cells) + " |")
            elif ch.tag == NS_P + "pic":
                body.append("[rasm]")

    out = []
    for i, part in enumerate(slides, 1):
        if part not in z.namelist():
            continue
        root = ET.fromstring(z.read(part))
        title, body = [], []
        tree = root.find(f"{NS_P}cSld/{NS_P}spTree")
        if tree is not None:
            walk(tree, title, body)
        note = ""
        for _, (rtype, target) in _rels(z, part).items():
            if rtype.endswith("/notesSlide") and target in z.namelist():
                n = [t for sp in ET.fromstring(z.read(target)).iter(NS_P + "sp")
                     if (ph := sp.find(f"{NS_P}nvSpPr/{NS_P}nvPr/{NS_P}ph")) is not None and ph.get("type") == "body"
                     for t in shape_text(sp)]
                note = "\n[Izoh: " + " ".join(n) + "]" if n else ""
        out.append(f"--- Slayd {i}" + (f": {' '.join(title)}" if title else "") + " ---\n" + "\n".join(body) + note)
    return "\n\n".join(out).strip() or "(slaydlarda matn topilmadi)"


# ============================ CSV / jadvallar ============================
def decode_text(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def read_csv_rows(path, limit: int | None = None) -> list[list[str]]:
    text = decode_text(Path(path).read_bytes())
    try:
        dialect = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = []
    for row in csv.reader(io.StringIO(text), dialect):
        rows.append(row)
        if limit and len(rows) >= limit:
            break
    return rows


def _table_rows(path, sheet: str = "", limit: int | None = MAX_ROWS) -> tuple[str, list[list[str]], list[str]]:
    """(varaq nomi, qatorlar, barcha varaqlar) — csv/tsv/xlsx uchun."""
    ext = Path(path).suffix.lower()
    if ext in (".csv", ".tsv", ".txt"):
        return "", read_csv_rows(path, limit), []
    if ext == ".xlsx":
        book = Xlsx(path)
        name = sheet or next(iter(book.sheets), "")
        if not name:
            raise DocError("Faylda varaq yo'q")
        return name, list(book.rows(name, limit)), list(book.sheets)
    if ext in OLD_FORMATS:
        raise DocError(f"Eski {ext} format. Faylni {OLD_FORMATS[ext]} sifatida saqlab qayta urining.")
    raise DocError("Jadval sifatida faqat .csv, .tsv va .xlsx o'qiladi.")


def rows_text(rows: list[list[str]], start: int = 1, sep: str = "\t") -> str:
    return "\n".join(f"{start + i:>6}  " + sep.join(c.replace("\n", " ") for c in r) for i, r in enumerate(rows))


_NUM = re.compile(r"^[-+]?\d{1,3}(?:[ ,]\d{3})*(?:\.\d+)?$|^[-+]?\d+(?:[.,]\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$|^\d{1,2}[./]\d{1,2}[./]\d{2,4}$")


def _to_float(s: str):
    s = s.strip().replace(" ", "")
    if not _NUM.match(s):
        return None
    if s.count(",") == 1 and "." not in s and len(s.split(",")[1]) != 3:
        s = s.replace(",", ".")
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def analyze(rows: list[list[str]], title: str = "") -> str:
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return "Jadval bo'sh."
    header, data = rows[0], rows[1:]
    width = max(len(r) for r in rows)
    header = [h.strip() or f"ustun{i + 1}" for i, h in enumerate(header + [""] * (width - len(header)))]
    lines = [f"{title}Jadval: {len(data)} qator × {width} ustun" + (" (birinchi qator — sarlavha)" if data else "")]
    for ci in range(min(width, 60)):
        vals = [(r[ci].strip() if ci < len(r) else "") for r in data]
        filled = [v for v in vals if v != ""]
        head = f'{ci + 1}. "{header[ci]}": to\'ldirilgan {len(filled)}/{len(vals)}'
        if not filled:
            lines.append(head + " (bo'sh ustun)")
            continue
        nums = [_to_float(v) for v in filled]
        if sum(n is not None for n in nums) >= 0.9 * len(filled):
            ns = [n for n in nums if n is not None]
            sd = f", std {statistics.stdev(ns):.4g}" if len(ns) > 1 else ""
            lines.append(f"{head}; son: min {min(ns):.6g}, maks {max(ns):.6g}, o'rtacha {statistics.fmean(ns):.6g}, "
                         f"median {statistics.median(ns):.6g}, jami {sum(ns):.6g}{sd}")
        elif sum(bool(_DATE.match(v)) for v in filled) >= 0.9 * len(filled):
            lines.append(f"{head}; sana: {min(filled)} … {max(filled)}")
        else:
            top = Counter(filled).most_common(5)
            uniq = len(set(filled))
            lines.append(f"{head}; matn: {uniq} xil; ko'p uchraydi: " + ", ".join(f"{v[:30]} ({n})" for v, n in top))
    if width > 60:
        lines.append(f"... yana {width - 60} ustun ko'rsatilmadi")
    lines += ["", "Birinchi qatorlar:", rows_text(rows[:6])]
    return "\n".join(lines)


# ============================ umumiy ============================
def _extract_text(path, max_chars: int = 300_000) -> str:
    """Hujjatdan matn: docx, pptx, xlsx, csv/tsv. Katta jadvallar uchun tahlil + birinchi qatorlar beriladi."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in OLD_FORMATS:
        raise DocError(f"Eski {ext} format qo'llanmaydi. Faylni {OLD_FORMATS[ext]} sifatida saqlab qayta urining.")
    if ext == ".docx":
        return read_docx(p)[:max_chars]
    if ext == ".pptx":
        return read_pptx(p)[:max_chars]
    if ext in (".xlsx", ".csv", ".tsv"):
        parts = []
        if ext == ".xlsx":
            book = Xlsx(p)
            for name in book.sheets:
                rows = list(book.rows(name, MAX_ROWS))
                parts.append(_table_block(rows, f"=== Varaq: {name} ===\n", max_chars // max(1, len(book.sheets))))
        else:
            parts.append(_table_block(read_csv_rows(p, MAX_ROWS), "", max_chars))
        return "\n\n".join(parts)[:max_chars * 2]
    raise DocError("Bu fayl turi qo'llanmaydi")


def _table_block(rows, title, budget):
    full = rows_text(rows)
    if len(full) <= min(budget, 60_000):
        return title + full
    return (title + analyze(rows) + f"\n\n[Jadval katta ({len(rows)} qator): to'liq matn o'rniga tahlil va birinchi qatorlar berildi. "
            "Aniq qatorlarni o'qish uchun fayl loyiha papkasida bo'lsa, read_table/analyze_data asboblaridan foydalaning.]\n"
            + rows_text(rows[6:150], start=7))


_BROKEN = (ET.ParseError, KeyError, zipfile.BadZipFile, ValueError, IndexError, AttributeError)


def extract_text(path, max_chars: int = 300_000) -> str:
    try:
        return _extract_text(path, max_chars)
    except _BROKEN as exc:
        raise DocError(f"Fayl ichki tuzilishi buzilgan yoki g'ayrioddiy ({type(exc).__name__}).")


def table_rows(path, sheet: str = "", limit: int | None = MAX_ROWS) -> tuple[str, list[list[str]], list[str]]:
    try:
        return _table_rows(path, sheet, limit)
    except _BROKEN as exc:
        raise DocError(f"Jadval o'qilmadi: fayl buzilgan yoki g'ayrioddiy ({type(exc).__name__}).")
