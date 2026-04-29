"""Build 断句/标点 instruction dataset from existing corpus.jsonl.

Task: given 古文 with all punctuation stripped, restore proper punctuation.
Useful for OCR post-processing, ancient text digitization, and as a
fundamental NLP capability for classical Chinese.

Source: corpus.jsonl (excludes 说文 字头 entries which are too short).

Output format:
  {"id": "punct#N", "task": "punctuate", "instruction": "...",
   "input": "<no-punct>", "output": "<with-punct>", "source": "..."}
"""

import json
import random
import re
from pathlib import Path

REPO_ROOT = Path("/Users/zion/Documents/zion/classical-corpus")
SOURCE = REPO_ROOT / "output" / "corpus.jsonl"
OUT_PATH = REPO_ROOT / "output" / "instruct" / "punctuate.jsonl"

PROMPTS = [
    "为下列古文添加标点：",
    "给这段古文断句：",
    "请为这段未标点的古文加上标点符号：",
    "给古文加标点：",
    "断句并加标点：",
]

# punctuation we strip from input
PUNCT_RE = re.compile(r"[，。：；、！？「」『』《》（）()【】　 \s]+")

# Skip these source types (too short or already stripped)
SKIP_SOURCES = {"说文解字"}


def split_into_chunks(text: str, target_chars: int = 200) -> list[str]:
    """Split a long passage into ~target_chars chunks at sentence boundaries."""
    # split on punctuation followed by space or after specific punctuation
    sentences = re.split(r"([。！？\n])", text)
    chunks: list[str] = []
    cur = ""
    for piece in sentences:
        cur += piece
        if len(cur) >= target_chars:
            chunks.append(cur.strip())
            cur = ""
    if cur.strip():
        chunks.append(cur.strip())
    return [c for c in chunks if 30 <= len(c) <= 500]


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    random.seed(42)

    n_records = 0
    by_source: dict[str, int] = {}

    with OUT_PATH.open("w", encoding="utf-8") as out:
        for line in SOURCE.open(encoding="utf-8"):
            rec = json.loads(line)
            src = rec.get("source", "?")
            if src in SKIP_SOURCES:
                continue
            content = rec.get("content", "")
            if not content or len(content) < 50:
                continue

            chunks = split_into_chunks(content)
            for chunk in chunks:
                stripped = PUNCT_RE.sub("", chunk)
                if len(stripped) < 20 or len(stripped) > 400:
                    continue
                # skip if barely changed (means input already lacked punct)
                if len(chunk) - len(stripped) < 3:
                    continue
                # drop chunks with □ placeholders (unrenderable CJK chars)
                if "□" in chunk:
                    continue

                n_records += 1
                out.write(
                    json.dumps(
                        {
                            "id": f"punct#{n_records}",
                            "task": "punctuate",
                            "instruction": random.choice(PROMPTS),
                            "input": stripped,
                            "output": chunk,
                            "source": src,
                            "category": rec.get("category", ""),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                by_source[src] = by_source.get(src, 0) + 1

    size_mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"written {n_records:,} records, {size_mb:.1f} MB")
    print(f"output: {OUT_PATH.relative_to(REPO_ROOT)}")
    print()
    print("=== top 15 sources ===")
    for src, n in sorted(by_source.items(), key=lambda x: -x[1])[:15]:
        print(f"  {src:15s}: {n:>6,}")


if __name__ == "__main__":
    main()
