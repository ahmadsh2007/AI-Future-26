"""Arabic text cleaning + sentence-aware chunking."""
import re
import unicodedata

DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
TATWEEL = "ـ"
# Sentence end: Arabic/Latin terminators followed by whitespace, or a newline.
_SENT_SPLIT = re.compile(r"(?<=[.!?؟۔؛;])\s+|\n+")


def clean_text(text: str) -> str:
    """Light normalization safe for embeddings (keeps letters/numbers intact).
    NFKC converts PDF 'presentation form' glyphs (ﻣﺮﺣﺒﺎ) back to normal letters."""
    text = unicodedata.normalize("NFKC", text)
    text = DIACRITICS.sub("", text)
    text = text.replace(TATWEEL, "")
    text = text.replace("‏", "").replace("‎", "").replace("﻿", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def normalize_for_match(text: str) -> str:
    """Aggressive normalization, ONLY for string comparison (never stored/embedded)."""
    text = clean_text(text)
    text = re.sub("[إأآٱ]", "ا", text).replace("ى", "ي").replace("ة", "ه")
    return text


def _split_long(sentence: str, size: int) -> list[str]:
    """A single sentence longer than `size`: split on commas, then words."""
    parts = re.split(r"(?<=[،,:])\s+", sentence)
    out, cur = [], ""
    for p in parts:
        for w in p.split(" "):
            if cur and len(cur) + len(w) + 1 > size:
                out.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_text(text: str, size: int = 700, overlap_sentences: int = 1, min_chars: int = 40) -> list[str]:
    """Pack whole sentences into chunks of ~`size` chars; never cut a sentence in the middle
    (unless one sentence alone exceeds `size`). Consecutive chunks share `overlap_sentences`
    sentences so facts that straddle a boundary are still retrievable."""
    sentences: list[str] = []
    for s in _SENT_SPLIT.split(clean_text(text)):
        s = s.strip()
        if not s:
            continue
        sentences.extend(_split_long(s, size) if len(s) > size else [s])

    chunks, cur = [], []
    cur_len = 0
    for s in sentences:
        if cur and cur_len + len(s) + 1 > size:
            chunks.append(" ".join(cur))
            cur = cur[-overlap_sentences:] if overlap_sentences else []
            cur_len = sum(len(x) + 1 for x in cur)
        cur.append(s)
        cur_len += len(s) + 1
    if cur:
        chunks.append(" ".join(cur))

    # Merge a tiny trailing chunk into the previous one instead of dropping information.
    if len(chunks) > 1 and len(chunks[-1]) < min_chars:
        chunks[-2] = chunks[-2] + " " + chunks.pop()
    return [c for c in chunks if len(c) >= min_chars or len(chunks) == 1]
