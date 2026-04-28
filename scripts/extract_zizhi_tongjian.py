"""Extract 资治通鉴 raw text → structured JSON, split by volume (卷)."""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    Path.home()
    / "Documents/zion/reference/Chinese/classical/corpora/daizhigev20"
    / "史藏/编年/资治通鉴四库.txt"
)
OUTPUT = REPO_ROOT / "output" / "zizhi-tongjian.json"

# Volume start marker: appears immediately after either "钦定四库全书" preamble or
# the "<史部,编年类,资治通鉴>" tag. We use the preceding "钦定四库全书" as the anchor
# since every real volume start has it; this naturally excludes end-of-volume markers
# and TOC references that lack the preamble.
VOLUME_START_RE = re.compile(
    r"钦定四库全书\s*\n\s*资治通鉴[卷巻]([一-鿿]+?)(?:\s|$)"
)

# Era marker (周纪一, 秦纪二, 汉纪三, etc.) usually appears 1-2 lines after volume start.
ERA_RE = re.compile(r"^[\s　]*([一-鿿]纪[一-鿿]+)")

CN_NUM = {c: i for i, c in enumerate("零一二三四五六七八九", 0)}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn_to_int(s: str) -> int:
    """Convert Chinese numeral (up to thousands) to int. Handles forms like
    一, 十, 十一, 二十, 二十一, 一百, 一百二十三, 二百九十四."""
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


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    # Find all volume-start positions
    matches = list(VOLUME_START_RE.finditer(text))
    print(f"found {len(matches)} volume markers")

    volumes = []
    for i, m in enumerate(matches):
        vol_str = m.group(1)
        vol_num = cn_to_int(vol_str)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]

        # Try to extract era marker (周纪/秦纪/etc.) from first ~5 lines after header
        era = ""
        for line in body.split("\n")[1:6]:
            em = ERA_RE.search(line)
            if em:
                era = em.group(1)
                break

        volumes.append({"num": vol_num, "raw_num": vol_str, "era": era, "body": body.strip()})

    # Source text has occasional duplicated headers (殆知阁瑕疵 at vols 150, 170);
    # dedupe by volume number, keep the first (and longest body if tied).
    by_num: dict[int, dict] = {}
    for v in volumes:
        prev = by_num.get(v["num"])
        if prev is None or len(v["body"]) > len(prev["body"]):
            by_num[v["num"]] = v
    volumes = sorted(by_num.values(), key=lambda v: v["num"])
    nums = [v["num"] for v in volumes]
    duplicates: list[int] = []  # deduplication handled above
    expected = set(range(1, max(nums) + 1)) if nums else set()
    missing = sorted(expected - set(nums))

    out = []
    for i, v in enumerate(volumes, 1):
        out.append(
            {
                "id": f"zizhi-tongjian#{v['num']}",
                "source": "资治通鉴",
                "author": "司马光",
                "era": "宋",
                "category": "史",
                "volume": v["num"],
                "period": v["era"],
                "content": v["body"],
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"volumes parsed: {len(volumes)}")
    print(f"  range: 卷{min(nums)} – 卷{max(nums)}")
    print(f"  unique periods: {len({v['era'] for v in volumes if v['era']})}")
    if missing:
        print(
            f"  ⚠ missing volumes: {missing}"
            f"  (these are empty in 殆知阁 source — placeholder header only)"
        )
    total_chars = sum(len(v["body"]) for v in volumes)
    print(f"  total chars: {total_chars:,}")
    print(f"output: {OUTPUT}")


if __name__ == "__main__":
    main()
