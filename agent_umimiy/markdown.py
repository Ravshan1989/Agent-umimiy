"""Yengil markdown: sarlavha, ro'yxat, **qalin**, `kod`, [havola](url), jadval, ``` kod bloklari.
Natija — (matn, teglar) bo'laklari; Tk bog'liqligi yo'q, shuning uchun alohida test qilinadi."""
from __future__ import annotations

import re

INLINE = re.compile(r"(\*\*.+?\*\*|`[^`\n]+`|\[[^\]\n]+\]\(https?://[^)\s]+\))")
FENCE = re.compile(r"```[\w+-]*\n?(.*?)```", re.S)


def inline(s: str, base: tuple = ()) -> list[tuple[str, tuple]]:
    out = []
    for piece in INLINE.split(s):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**") and len(piece) > 4:
            out.append((piece[2:-2], base + ("b",)))
        elif piece.startswith("`") and piece.endswith("`") and len(piece) > 2:
            out.append((piece[1:-1], base + ("ic",)))
        elif piece.startswith("["):
            m = re.match(r"\[(.*?)\]\((.*?)\)$", piece)
            out.append((m.group(1), base + ("link:" + m.group(2),)) if m else (piece, base))
        else:
            out.append((piece, base))
    return out


def parse(text: str) -> list[tuple[str, tuple]]:
    segs: list[tuple[str, tuple]] = []
    for i, part in enumerate(FENCE.split(text)):
        if i % 2:
            segs.append((part.strip("\n") + "\n", ("code",)))
            continue
        for line in part.split("\n"):
            m = re.match(r"^(#{1,3})\s+(.*)$", line)
            if m:
                segs += inline(m.group(2), ("h%d" % len(m.group(1)),))
            elif line.lstrip().startswith("|") and line.rstrip().endswith("|"):
                segs.append((line, ("table",)))
            else:
                line = re.sub(r"^(\s*)[-*+]\s+", r"\1• ", line)
                segs += inline(line)
            segs.append(("\n", ()))
    while segs and segs[-1][0] == "\n":  # oxiridagi ortiqcha qatorlar
        segs.pop()
    return segs


def plain(segs) -> str:
    return "".join(s for s, _ in segs)
