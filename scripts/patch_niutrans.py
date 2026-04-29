"""Patch 南史 from NiuTrans/Classical-Modern.

殆知阁 南史.txt body has only TOC + unmarked prose (impossible to chapter-split).
chtxt repo doesn't include 南史. wikisource has no 南史 sub-pages.

NiuTrans 双语数据/南史/{本纪|列传}/<卷N>/source.txt provides 76 of 80 卷
properly organized — the only viable source for 南史 chapter-level data.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path("/Users/zion/Documents/zion/classical-corpus")
NIUTRANS = Path(
    "/Users/zion/Documents/zion/reference/Chinese/classical/corpora/Classical-Modern/双语数据"
)

CN_NUM = {c: i for i, c in enumerate("零一二三四五六七八九", 0)}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn_to_int(s: str) -> int:
    if not s:
        return 0
    if s in CN_NUM:
        return CN_NUM[s]
    total, current = 0, 0
    for ch in s:
        if ch in CN_NUM:
            current = CN_NUM[ch]
        elif ch in CN_UNIT:
            unit = CN_UNIT[ch]
            total += (current or 1) * unit
            current = 0
    return total + current


def parse_juan_name(name: str) -> tuple[int, str]:
    m = re.match(r"卷([一二三四五六七八九十百千零]+)([上中下])?", name)
    if not m:
        return (0, "")
    return (cn_to_int(m.group(1)), m.group(2) or "")


def main() -> None:
    target = REPO_ROOT / "output" / "histories" / "nanshi.json"
    book_dir = NIUTRANS / "南史"

    records = []
    seq = 0
    for section_dir in sorted(book_dir.iterdir()):
        if not section_dir.is_dir():
            continue
        for juan_dir in sorted(section_dir.iterdir()):
            if not juan_dir.is_dir():
                continue
            src = juan_dir / "source.txt"
            if not src.exists():
                continue
            vol_num, suffix = parse_juan_name(juan_dir.name)
            content = src.read_text(encoding="utf-8").strip()
            if not content:
                continue
            seq += 1
            records.append(
                {
                    "id": f"nanshi#{seq}",
                    "source": "南史",
                    "author": "李延寿",
                    "era": "唐",
                    "category": "史",
                    "volume": vol_num,
                    "volume_suffix": suffix,
                    "section": section_dir.name,
                    "chapter": juan_dir.name,
                    "content": content,
                    "_source": "NiuTrans/Classical-Modern",
                }
            )

    records.sort(key=lambda d: (d["volume"], d["volume_suffix"]))
    with target.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    chars = sum(len(r["content"]) for r in records)
    print(f"南史: {len(records)} 卷, {chars:,} 字 (was 1)")


if __name__ == "__main__":
    main()
