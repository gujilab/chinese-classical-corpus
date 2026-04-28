"""Extract 说文解字 raw text → structured JSON.

Source format (each entry one line):
    编号:N   部首   字   pinyin   释义   反切
Fields are separated by exactly 3 spaces.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    Path.home()
    / "Documents/zion/reference/Chinese/classical/corpora/daizhigev20/儒藏/小学/说文解字.txt"
)
OUTPUT = REPO_ROOT / "output" / "shuowen.json"

ENTRY_RE = re.compile(r"^编号:(\d+)\s+(.*)$")


def parse(line: str) -> dict | None:
    m = ENTRY_RE.match(line.rstrip())
    if not m:
        return None
    seq, rest = m.group(1), m.group(2)
    # 5 fields separated by exactly 3 spaces; empty fields appear as ''
    parts = rest.rstrip().split("   ")
    parts = [p.strip() for p in parts]
    # original text marks missing 反切 with terminal "闕"; record as empty
    if len(parts) == 4:
        radical, char, pinyin, explanation = parts
        fanqie = ""
    elif len(parts) == 5:
        radical, char, pinyin, explanation, fanqie = parts
    else:
        return {"_raw": line.rstrip(), "_seq": int(seq), "_malformed": True}
    return {
        "id": f"shuowen#{seq}",
        "source": "说文解字",
        "author": "许慎",
        "era": "汉",
        "category": "字书",
        "char": char,
        "radical": radical,
        "pinyin": pinyin,
        "fanqie": fanqie.strip(),
        "content": explanation,
    }


def main() -> None:
    entries: list[dict] = []
    malformed: list[dict] = []
    with SOURCE.open(encoding="utf-8") as f:
        for line in f:
            rec = parse(line)
            if rec is None:
                continue
            if rec.get("_malformed"):
                malformed.append(rec)
            else:
                entries.append(rec)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"parsed:    {len(entries)}")
    print(f"malformed: {len(malformed)}")
    print(f"output:    {OUTPUT}")
    if malformed[:3]:
        print("first malformed samples:")
        for m in malformed[:3]:
            print(" ", m)


if __name__ == "__main__":
    main()
