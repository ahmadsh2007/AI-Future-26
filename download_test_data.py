"""Download a small Arabic financial-news subset and save each article as data/raw_docs/*.txt
to simulate the hackathon document folder.

    python download_test_data.py            # 30 articles
    python download_test_data.py -n 20 --dataset drelhaj/AraFinNews
"""
import argparse
import re

from datasets import load_dataset

import config

CANDIDATES = ["drelhaj/AraFinNews", "arbml/AraFinNews", "arbml/Arabic_Financial_News"]
TEXT_KEYS = ["text", "article", "content", "body", "Article", "News", "description"]
TITLE_KEYS = ["title", "headline", "Title"]


def pick(row: dict, keys):
    for k in keys:
        if isinstance(row.get(k), str) and row[k].strip():
            return row[k].strip()
    return ""


def load_stream(name: str):
    ds = load_dataset(name, split="train", streaming=True)  # streaming: don't download the whole corpus
    return ds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=30)
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--min-chars", type=int, default=300)
    a = ap.parse_args()

    stream = None
    for name in ([a.dataset] if a.dataset else CANDIDATES):
        try:
            print(f"Trying {name} ...")
            stream = load_stream(name)
            next(iter(stream))  # force a real fetch to validate
            break
        except Exception as e:
            print(f"  failed: {type(e).__name__}: {str(e)[:150]}")
            stream = None
    if stream is None:
        raise SystemExit("No dataset could be loaded. Pass --dataset <hf_name> or check your connection.")

    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0
    for row in stream:
        body, title = pick(row, TEXT_KEYS), pick(row, TITLE_KEYS)
        if len(body) < a.min_chars:
            continue
        saved += 1
        (config.DOCS_DIR / f"article_{saved:03d}.txt").write_text(
            (f"{title}\n\n" if title and title not in body[:len(title) + 5] else "") + re.sub(r"\r\n?", "\n", body),
            encoding="utf-8")
        if saved >= a.n:
            break
    print(f"Saved {saved} articles to {config.DOCS_DIR}")


if __name__ == "__main__":
    main()
