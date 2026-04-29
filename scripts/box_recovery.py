"""Cross-reference recovery for □ chars in NiuTrans sources.

For 5 NiuTrans books that have a clean chtxt counterpart, recover □ chars by
context matching. For other □ records, leave as-is and let downstream code
add a `_has_box: true` flag.

Output: box_recovery.json — map of (book, original_sentence) → recovered_sentence
"""

import json
import re
from collections import Counter
from pathlib import Path
from opencc import OpenCC

T2S = OpenCC("t2s")
NIUTRANS = Path(
    "/Users/zion/Documents/zion/reference/Chinese/classical/corpora/Classical-Modern/双语数据"
)
CHTXT = Path("/Users/zion/Documents/zion/reference/Chinese/classical/corpora/chtxt")
OUT_MAP = Path("/Users/zion/Documents/zion/classical-corpus/output/box_recovery.json")

# NiuTrans book name → chtxt 繁体 file
RECOVERY_PAIRS = {
    "北齐书": "j.史書/北齊書.txt",
    "宋书": "j.史書/宋書.txt",
    "梁书": "j.史書/梁書.txt",
    "魏书": "j.史書/魏書.txt",
    "三国志": "j.史書/三國志.txt",
}


def recover_one(sentence: str, chtxt: str, ctx_radius: int = 6) -> str | None:
    """Recover all □ in sentence by context match against chtxt. Returns
    recovered sentence if all positions resolve unambiguously, else None."""
    box_positions = [i for i, c in enumerate(sentence) if c == "□"]
    if not box_positions:
        return sentence

    recovered = list(sentence)
    for pos in box_positions:
        left = sentence[max(0, pos - ctx_radius) : pos]
        right = sentence[pos + 1 : min(len(sentence), pos + ctx_radius + 1)]
        if sum(1 for c in left if c != "□") < 3 and sum(1 for c in right if c != "□") < 3:
            return None

        def to_pat(s: str) -> str:
            return "".join("." if c == "□" else re.escape(c) for c in s)

        pattern = to_pat(left) + "(.)" + to_pat(right)
        candidates = Counter()
        for m in re.finditer(pattern, chtxt):
            ch = m.group(1)
            if ch and ch != "□":
                candidates[ch] += 1

        if not candidates:
            return None
        top = candidates.most_common(2)
        if len(top) == 1 or top[0][1] >= 3 * top[1][1]:
            recovered[pos] = top[0][0]
        else:
            return None
    return "".join(recovered)


def main() -> None:
    recovery_map: dict[str, str] = {}
    stats: dict[str, dict] = {}

    for niu_book, chtxt_path in RECOVERY_PAIRS.items():
        chtxt_full = CHTXT / chtxt_path
        if not chtxt_full.exists():
            print(f"  {niu_book}: chtxt not found, skip")
            continue

        chtxt = T2S.convert(chtxt_full.read_text(encoding="utf-8"))
        print(f"\n{niu_book}: chtxt loaded ({len(chtxt):,} chars)")

        book_dir = NIUTRANS / niu_book
        if not book_dir.exists():
            print(f"  {niu_book}: not in NiuTrans")
            continue

        # collect every □-containing sentence from this book's source.txt files
        sentences = set()
        for src in book_dir.rglob("source.txt"):
            for line in src.read_text(encoding="utf-8").split("\n"):
                if "□" in line:
                    sentences.add(line.strip())

        recovered = 0
        for s in sentences:
            r = recover_one(s, chtxt)
            if r and r != s and "□" not in r:
                # key is (book, original sentence) — using book::sentence as flat key
                recovery_map[f"{niu_book}::{s}"] = r
                recovered += 1

        stats[niu_book] = {"total": len(sentences), "recovered": recovered}
        print(f"  recovered {recovered}/{len(sentences)} ({100*recovered/max(1,len(sentences)):.0f}%)")

    OUT_MAP.write_text(json.dumps(recovery_map, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== Summary ===")
    total_in = sum(s["total"] for s in stats.values())
    total_out = sum(s["recovered"] for s in stats.values())
    print(f"  total □ sentences across {len(stats)} books: {total_in}")
    print(f"  recovered: {total_out} ({100*total_out/max(1,total_in):.1f}%)")
    print(f"  saved map: {OUT_MAP}")


if __name__ == "__main__":
    main()
