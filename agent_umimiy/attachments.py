"""Rasm, PDF, Word va matn fayllarini agentga biriktirish."""
from __future__ import annotations

import base64
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
MAX_IMAGE, MAX_PDF, MAX_TEXT = 5 * 1024 * 1024, 20 * 1024 * 1024, 300_000
FILETYPES = [("Rasm, PDF, Word va matn", "*.png *.jpg *.jpeg *.gif *.webp *.pdf *.docx *.txt *.md *.csv *.json *.py *.js *.html *.log"),
             ("Hamma fayllar", "*.*")]


class AttachError(Exception):
    pass


@dataclass
class Attachment:
    name: str
    path: str
    kind: str  # image | pdf | text
    mime: str
    data: bytes = b""
    text: str = ""

    @property
    def b64(self) -> str:
        return base64.b64encode(self.data).decode()


def pdf_text(data_or_path, limit: int = MAX_TEXT) -> str:
    try:
        import pypdf
    except ImportError:
        raise AttachError("PDF matnini o'qish uchun pypdf kerak (pip install pypdf).")
    import io
    src = io.BytesIO(data_or_path) if isinstance(data_or_path, bytes) else str(data_or_path)
    try:
        reader = pypdf.PdfReader(src)
        out = []
        for i, page in enumerate(reader.pages, 1):
            out.append(f"[{i}-sahifa]\n{page.extract_text() or ''}")
            if sum(map(len, out)) > limit:
                break
    except Exception as exc:
        raise AttachError(f"PDF o'qilmadi: {exc}")
    text = "\n\n".join(out).strip()
    return text[:limit] or "(PDF ichida matn topilmadi — skaner qilingan rasm bo'lishi mumkin)"


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    except Exception as exc:
        raise AttachError(f"Word fayli o'qilmadi: {exc}")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml).strip()[:MAX_TEXT]


def load(path: str) -> Attachment:
    p = Path(path)
    if not p.is_file():
        raise AttachError(f"Fayl topilmadi: {path}")
    ext, size = p.suffix.lower(), p.stat().st_size
    if ext in IMAGES:
        if size > MAX_IMAGE:
            raise AttachError(f"{p.name}: rasm 5 MB dan katta. Kichikroq rasm tanlang.")
        return Attachment(p.name, str(p), "image", IMAGES[ext], data=p.read_bytes())
    if ext == ".pdf":
        if size > MAX_PDF:
            raise AttachError(f"{p.name}: PDF 20 MB dan katta.")
        return Attachment(p.name, str(p), "pdf", "application/pdf", data=p.read_bytes())
    if ext == ".docx":
        return Attachment(p.name, str(p), "text", "text/plain", text=_docx_text(p))
    raw = p.read_bytes()[:MAX_TEXT * 2]
    if b"\x00" in raw[:4096]:
        raise AttachError(f"{p.name}: bu fayl turini o'qib bo'lmaydi (rasm, PDF, Word yoki matn fayl tanlang).")
    return Attachment(p.name, str(p), "text", "text/plain", text=raw.decode("utf-8", errors="replace")[:MAX_TEXT])


def note(atts: list[Attachment]) -> str:
    return f"\n[Biriktirilgan: {', '.join(a.name for a in atts)}]" if atts else ""


def text_with_files(prompt: str, atts: list[Attachment], native_pdf: bool) -> str:
    parts = [prompt]
    for a in atts:
        if a.kind == "text":
            parts.append(f"\n\n--- {a.name} ---\n{a.text}")
        elif a.kind == "pdf" and not native_pdf:
            parts.append(f"\n\n--- {a.name} (PDF matni) ---\n{pdf_text(a.data)}")
    return "".join(parts)


def anthropic_content(prompt: str, atts: list[Attachment]):
    media = [a for a in atts if a.kind in ("image", "pdf")]
    if not media:
        return text_with_files(prompt, atts, True)
    blocks = [{"type": "image" if a.kind == "image" else "document",
               "source": {"type": "base64", "media_type": a.mime, "data": a.b64}} for a in media]
    return blocks + [{"type": "text", "text": text_with_files(prompt, atts, True)}]


def openai_content(prompt: str, atts: list[Attachment]):
    text = text_with_files(prompt, atts, False)
    imgs = [a for a in atts if a.kind == "image"]
    if not imgs:
        return text
    return [{"type": "text", "text": text}] + [
        {"type": "image_url", "image_url": {"url": f"data:{a.mime};base64,{a.b64}"}} for a in imgs]


def gemini_parts(prompt: str, atts: list[Attachment]) -> list[dict]:
    parts = [{"inline_data": {"mime_type": a.mime, "data": a.b64}} for a in atts if a.kind in ("image", "pdf")]
    return parts + [{"text": text_with_files(prompt, atts, True)}]


def ollama_message(prompt: str, atts: list[Attachment]) -> dict:
    msg = {"role": "user", "content": text_with_files(prompt, atts, False)}
    imgs = [a.b64 for a in atts if a.kind == "image"]
    if imgs:
        msg["images"] = imgs
    return msg
