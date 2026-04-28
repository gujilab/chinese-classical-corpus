"""Extract 孝经/尔雅/春秋公羊传 from 殆知阁 → unified schema.

Completes 12 of 13 of the 十三经. 春秋穀梁传 needs external source
(殆知阁 only has 注疏 version with text interleaved with commentary).
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DAIZHI = (
    Path.home() / "Documents/zion/reference/Chinese/classical/corpora/daizhigev20"
)


def split_with_matches(text: str, matches: list[re.Match]) -> list[tuple[str, str]]:
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = m.group("title") if "title" in m.groupdict() else m.group(0).strip()
        body = text[m.end():end].strip()
        if body:
            out.append((title.strip(), body))
    return out


def find_body_markers(text: str, marker: re.Pattern, gap: int = 200) -> list[re.Match]:
    matches = list(marker.finditer(text))
    if len(matches) < 2:
        return matches
    for i in range(len(matches) - 1):
        if matches[i + 1].start() - matches[i].end() > gap:
            return matches[i:]
    return matches


def extract_xiaojing() -> list[dict]:
    """孝经: 18 章, marked with ○XX章第N"""
    text = (DAIZHI / "儒藏/孝经/孝经.txt").read_text(encoding="utf-8")
    marker = re.compile(r"○(?P<title>[一-鿿]+章第[一-鿿]+)")
    matches = list(marker.finditer(text))
    return [
        {
            "id": f"xiaojing#{i}",
            "source": "孝经",
            "author": "孔子门徒（传）",
            "era": "春秋",
            "category": "经",
            "chapter": title,
            "section": i,
            "content": body,
        }
        for i, (title, body) in enumerate(split_with_matches(text, matches), 1)
    ]


def extract_erya() -> list[dict]:
    """尔雅: 19 篇, marked with 释XX第N — TOC + body share format, use gap filter"""
    text = (DAIZHI / "儒藏/小学/尔雅.txt").read_text(encoding="utf-8")
    marker = re.compile(r"^　*(?P<title>释[一-鿿]+第[一-鿿]+)", re.M)
    matches = find_body_markers(text, marker)
    return [
        {
            "id": f"erya#{i}",
            "source": "尔雅",
            "author": "佚名（先秦）",
            "era": "周",
            "category": "经",
            "chapter": title,
            "section": i,
            "content": body,
        }
        for i, (title, body) in enumerate(split_with_matches(text, matches), 1)
    ]


def extract_gongyang() -> list[dict]:
    """春秋公羊传: 12 公, marked with 公羊传XX公 on its own line"""
    text = (DAIZHI / "儒藏/春秋/春秋公羊传.txt").read_text(encoding="utf-8")
    marker = re.compile(
        r"^　*公羊传(?P<title>[隐桓庄闵僖文宣成襄昭定哀]公)\s*$", re.M
    )
    matches = list(marker.finditer(text))
    return [
        {
            "id": f"gongyang#{i}",
            "source": "春秋公羊传",
            "author": "公羊高",
            "era": "战国",
            "category": "经",
            "chapter": title,
            "section": i,
            "content": body,
        }
        for i, (title, body) in enumerate(split_with_matches(text, matches), 1)
    ]


EXTRACTORS = [
    ("xiaojing", "孝经", extract_xiaojing),
    ("erya", "尔雅", extract_erya),
    ("gongyang", "春秋公羊传", extract_gongyang),
]


def main() -> None:
    out_dir = REPO_ROOT / "output" / "shisanjing"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"=== 十三经其余 3 部 ===")
    for key, name, fn in EXTRACTORS:
        records = fn()
        dst = out_dir / f"{key}.json"
        with dst.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        chars = sum(len(r["content"]) for r in records)
        print(
            f"  {name:6s}: {len(records):3d} 章, "
            f"{chars:>8,} 字  → {dst.relative_to(REPO_ROOT)}"
        )


if __name__ == "__main__":
    main()
