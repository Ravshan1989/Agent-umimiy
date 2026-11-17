"""Lokal Bilimlar Bazasi (RAG — SQLite FTS5): loyiha hujjatlarini (PDF, DOCX, XLSX, MD, TXT, PY)
indeksatsiya qiladi va millisoniyalarda matn qidiradi."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from . import config, docs

TEXT_EXTS = {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".json", ".csv", ".html", ".yaml", ".yml"}
DOC_EXTS = {".pdf", ".docx", ".xlsx", ".pptx"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode"}
MAX_FILES = 500
MAX_CHARS_PER_FILE = 50_000


def _db_path() -> Path:
    return config.user_dir() / "rag_index.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), timeout=10)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(path, name, content, updated UNINDEXED)"
    )
    return conn


def _extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in TEXT_EXTS:
            return path.read_text(encoding="utf-8", errors="replace")[:MAX_CHARS_PER_FILE]
        if ext == ".docx":
            return docs.read_docx(path)[:MAX_CHARS_PER_FILE]
        if ext == ".pptx":
            return docs.read_pptx(path)[:MAX_CHARS_PER_FILE]
        if ext == ".xlsx":
            return docs.analyze_table(path)[:MAX_CHARS_PER_FILE]
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages[:25]]
            return "\n".join(pages)[:MAX_CHARS_PER_FILE]
    except Exception:
        return ""
    return ""


def index_project(root: str | Path | None) -> dict:
    if not root or not Path(root).is_dir():
        return {"indexed": 0, "error": "Loyiha papkasi topilmadi"}
    base = Path(root).resolve()
    files: list[Path] = []
    for p in base.rglob("*"):
        if len(files) >= MAX_FILES:
            break
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and not p.is_symlink() and p.suffix.lower() in (TEXT_EXTS | DOC_EXTS):
            try:
                if p.stat().st_size <= 15 * 1024 * 1024:
                    files.append(p)
            except OSError:
                continue
    now = str(int(time.time()))
    count = 0
    with _connect() as conn:
        conn.execute("DELETE FROM docs_fts")
        for f in files:
            text = _extract_text(f).strip()
            if not text:
                continue
            rel = str(f.relative_to(base)).replace("\\", "/")
            conn.execute(
                "INSERT INTO docs_fts (path, name, content, updated) VALUES (?, ?, ?, ?)",
                (rel, f.name, text, now),
            )
            count += 1
    return {"indexed": count, "project": base.name}


def search(query: str, limit: int = 6) -> list[dict]:
    tokens = [w for w in "".join(ch if ch.isalnum() else " " for ch in (query or "")).split() if len(w) >= 2]
    if not tokens:
        return []
    fts_query = " OR ".join(f'"{t}"*' for t in tokens[:8])
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT path, name, snippet(docs_fts, 2, '[', ']', ' … ', 24) "
                "FROM docs_fts WHERE docs_fts MATCH ? ORDER BY rank LIMIT ?",
                (fts_query, max(1, min(limit, 20))),
            ).fetchall()
        return [{"path": r[0], "name": r[1], "snippet": r[2]} for r in rows]
    except Exception:
        return []


def stats() -> dict:
    try:
        with _connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM docs_fts").fetchone()
            return {"indexed": int(row[0]) if row else 0}
    except Exception:
        return {"indexed": 0}
