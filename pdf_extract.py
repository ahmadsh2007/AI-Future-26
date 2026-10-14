"""PDF text extraction that is robust to Arabic visual-order PDFs.

Problem: many Arabic PDFs store glyphs in *visual* order (left->right on the page). PyMuPDF's
plain/sorted text then gives reversed word order, reversed digit runs ("١٩٩٨" -> "٨٩٩١") and
misplaced punctuation. Fix: rebuild each line from glyph x-positions (geometry never lies):
visual string -> reverse -> re-reverse embedded LTR runs (digits/Latin) = logical order.
Set PDF_EXTRACT_MODE=plain to fall back to PyMuPDF's own ordering.
"""
import os
import re

import pymupdf

_ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_LATIN = re.compile(r"[A-Za-z]")
_LTR_RUN = re.compile(r"[0-9٠-٩A-Za-z]+(?:[.,:/%\-٫٬][0-9٠-٩A-Za-z]+)*")


def _visual_to_logical(visual: str) -> str:
    if len(_ARABIC.findall(visual)) < len(_LATIN.findall(visual)) or not _ARABIC.search(visual):
        return visual  # LTR-dominant line: visual order == logical order
    rev = visual[::-1]
    return _LTR_RUN.sub(lambda m: m.group(0)[::-1], rev)


def _block_lines(block) -> list[str]:
    chars = []  # (x0, x1, ycenter, height, char)
    for line in block.get("lines", []):
        for span in line["spans"]:
            for ch in span["chars"]:
                x0, y0, x1, y1 = ch["bbox"]
                chars.append((x0, x1, (y0 + y1) / 2, max(y1 - y0, 1.0), ch["c"]))
    if not chars:
        return []
    chars.sort(key=lambda c: c[2])
    rows, cur = [], [chars[0]]
    for c in chars[1:]:
        if abs(c[2] - cur[-1][2]) > 0.5 * cur[-1][3]:
            rows.append(cur)
            cur = []
        cur.append(c)
    rows.append(cur)

    out = []
    for row in rows:
        row.sort(key=lambda c: c[0])
        s, prev_x1 = "", None
        for x0, x1, _, h, c in row:
            if prev_x1 is not None and x0 - prev_x1 > 0.25 * h and not s.endswith(" ") and c != " ":
                s += " "  # gap without a space glyph
            s += c
            prev_x1 = x1
        out.append(_visual_to_logical(s.strip()))
    return out


def extract_page_text(page) -> str:
    if os.getenv("PDF_EXTRACT_MODE", "geometric") == "plain":
        return page.get_text("text")
    blocks = [b for b in page.get_text("rawdict")["blocks"] if b.get("type") == 0]
    blocks.sort(key=lambda b: (round(b["bbox"][1] / 8), -b["bbox"][2]))  # top->bottom, then right->left
    return "\n".join("\n".join(_block_lines(b)) for b in blocks)
