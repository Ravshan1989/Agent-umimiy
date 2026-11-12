"""Rasm, PDF, Word va matn fayllarini agentga biriktirish."""
from __future__ import annotations

import base64
import binascii
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from . import docs

IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
MAX_IMAGE, MAX_PDF, MAX_TEXT = 5 * 1024 * 1024, 20 * 1024 * 1024, 300_000
MAX_UPLOAD = 20 * 1024 * 1024
MAX_PDF_PAGES = 200
FILETYPES = [("Rasm, PDF, Word, Excel, PowerPoint va matn",
              "*.png *.jpg *.jpeg *.gif *.webp *.pdf *.docx *.xlsx *.pptx *.csv *.tsv *.txt *.md *.json *.py *.js *.html *.log"),
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
    return text[:limit] or ("(PDF ichida matn topilmadi: bu skaner qilingan rasm bo'lishi mumkin. Sahifalarni rasm sifatida yuboring — "
                            "ko'ra oladigan model (Claude, GPT-4, Gemini) matnni o'zi o'qiydi)")


def load(path: str) -> Attachment:
    p = Path(path)
    if not p.is_file():
        raise AttachError(f"Fayl topilmadi: {path}")
    ext, size = p.suffix.lower(), p.stat().st_size
    if size > MAX_UPLOAD:
        raise AttachError(f"{p.name}: fayl 20 MB dan katta.")
    if ext in IMAGES:
        if size > MAX_IMAGE:
            raise AttachError(f"{p.name}: rasm 5 MB dan katta. Kichikroq rasm tanlang.")
        return Attachment(p.name, str(p), "image", IMAGES[ext], data=p.read_bytes())
    if ext == ".pdf":
        if size > MAX_PDF:
            raise AttachError(f"{p.name}: PDF 20 MB dan katta.")
        return Attachment(p.name, str(p), "pdf", "application/pdf", data=p.read_bytes())
    if ext in docs.OLD_FORMATS:
        raise AttachError(f"{p.name}: eski {ext} format. Faylni {docs.OLD_FORMATS[ext]} sifatida saqlab qayta yuboring.")
    if ext in (".docx", ".xlsx", ".pptx", ".csv", ".tsv"):
        try:
            return Attachment(p.name, str(p), "text", "text/plain", text=docs.extract_text(p, MAX_TEXT))
        except docs.DocError as exc:
            raise AttachError(f"{p.name}: {exc}")
    with p.open("rb") as fh:
        raw = fh.read(MAX_TEXT * 2)
    if b"\x00" in raw[:4096]:
        raise AttachError(f"{p.name}: bu fayl turini o'qib bo'lmaydi (rasm, PDF, Word yoki matn fayl tanlang).")
    return Attachment(p.name, str(p), "text", "text/plain", text=raw.decode("utf-8", errors="replace")[:MAX_TEXT])


def save_upload(save_dir: Path, name: str, data_b64: str) -> Attachment:
    """Brauzerdan yuborilgan (base64) faylni saqlab, biriktirma qiladi."""
    name = re.sub(r"[^\w.\- ]", "_", str(name))[-80:] or "fayl"
    if not isinstance(data_b64, str) or len(data_b64) > ((MAX_UPLOAD + 2) // 3) * 4:
        raise AttachError(f"{name}: fayl 20 MB dan katta yoki noto'g'ri yuborilgan.")
    try:
        data = base64.b64decode(data_b64, validate=True)
    except (binascii.Error, ValueError):
        raise AttachError(f"{name}: fayl buzilgan holda keldi.")
    if len(data) > MAX_UPLOAD:
        raise AttachError(f"{name}: fayl 20 MB dan katta.")
    folder = Path(save_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{time.time_ns() // 1_000_000}_{name}"
    try:
        path.write_bytes(data)
        att = load(str(path))
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    att.name = name  # vaqt belgisisiz asl nom ko'rinsin
    return att


def from_clipboard(save_dir: Path) -> list[Attachment]:
    """Clipboard'dagi skrinshot (rasm) yoki nusxalangan fayllarni biriktirma qiladi; mos narsa bo'lmasa []."""
    try:
        from PIL import Image, ImageGrab
    except ImportError:
        raise AttachError("Skrinshot qo'yish uchun Pillow kerak (pip install pillow).")
    try:
        grab = ImageGrab.grabclipboard()
    except Exception:  # Linux'da xclip/wl-paste yo'q yoki clipboard band
        return []
    if isinstance(grab, list):  # Explorer'da nusxalangan fayllar
        return [load(str(f)) for f in grab if Path(str(f)).is_file()]
    if not isinstance(grab, Image.Image):
        return []
    path = Path(save_dir) / f"skrinshot-{time.strftime('%Y%m%d-%H%M%S')}.png"
    grab.save(path, "PNG")
    if path.stat().st_size > MAX_IMAGE:  # juda katta ekran: JPEG ixchamroq
        path.unlink()
        path = path.with_suffix(".jpg")
        grab.convert("RGB").save(path, "JPEG", quality=85)
    return [load(str(path))]


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


def openai_model_for(options: dict, atts: list[Attachment]) -> str:
    """OpenRouter free alias sometimes resolves to text-only capacity; use a vision free route for images."""
    model = str(options.get("model", "gpt-4o"))
    host = urlparse(str(options.get("base_url", ""))).hostname or ""
    if host == "openrouter.ai" and model.strip().lower() == "openrouter/free" and any(a.kind == "image" for a in atts):
        return str(options.get("vision_model") or "nvidia/nemotron-3.5-super-vl:free")
    return model


def gemini_parts(prompt: str, atts: list[Attachment]) -> list[dict]:
    parts = [{"inline_data": {"mime_type": a.mime, "data": a.b64}} for a in atts if a.kind in ("image", "pdf")]
    return parts + [{"text": text_with_files(prompt, atts, True)}]


def ollama_message(prompt: str, atts: list[Attachment]) -> dict:
    msg = {"role": "user", "content": text_with_files(prompt, atts, False)}
    imgs = [a.b64 for a in atts if a.kind == "image"]
    if imgs:
        msg["images"] = imgs
    return msg
