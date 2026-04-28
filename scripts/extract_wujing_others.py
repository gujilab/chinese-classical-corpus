"""Extract 周易/尚书/礼记/春秋左传 from 殆知阁 → unified schema.

Strategy: each book has a body-section regex that ONLY matches body markers
(not TOC entries). For books where TOC and body share the same marker format,
we filter by the first big content-gap to find the TOC→body boundary.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DAIZHI = (
    Path.home() / "Documents/zion/reference/Chinese/classical/corpora/daizhigev20"
)
OUTPUT_DIR = REPO_ROOT / "output" / "wujing"

# TOC→body boundary: first marker pair whose gap > this many chars is the body start
TOC_GAP_THRESHOLD = 200


def find_body_markers(text: str, marker: re.Pattern) -> list[re.Match]:
    """If TOC and body use the same marker, drop TOC entries by finding the
    first big content gap; return only matches at/after the body start."""
    matches = list(marker.finditer(text))
    if len(matches) < 2:
        return matches
    for i in range(len(matches) - 1):
        gap = matches[i + 1].start() - matches[i].end()
        if gap > TOC_GAP_THRESHOLD:
            return matches[i:]
    return matches


def split_with_matches(text: str, matches: list[re.Match]) -> list[tuple[str, str]]:
    """Split text into (title, body) pairs given marker matches."""
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = m.group("title") if "title" in m.groupdict() else m.group(0).strip()
        body = text[m.end():end].strip()
        if body:
            out.append((title.strip(), body))
    return out


# Each book: source path, key, name, era, author, body marker regex.
BOOKS = [
    {
        "key": "zhouyi",
        "name": "周易",
        "author": "佚名（周）",
        "era": "周",
        "path": "易藏/易经/周易.txt",
        # 64 卦 + 5 commentaries (系辞上/系辞下/说卦/序卦/杂卦) all in body
        # commentaries appear in TOC too — gap filter strips TOC entries
        "marker": re.compile(
            r"^　*(?P<title>(?:\d{2}\.\s*[一-鿿]+（卦[一-鿿]+）"
            r"|系辞[上下]|说卦|序卦|杂卦))",
            re.M,
        ),
        "use_gap_filter": True,
    },
    {
        "key": "shangshu",
        "name": "尚书",
        "author": "佚名（先秦）",
        "era": "周",
        "path": "儒藏/尚书/尚书.txt",
        # 虞书 尧典第一 — TOC and body share format, filter via gap
        "marker": re.compile(
            r"^　*(?P<title>[虞夏商周]书\s+[一-鿿]+第[一-鿿]+)", re.M
        ),
        "use_gap_filter": True,
    },
    {
        "key": "liji",
        "name": "礼记",
        "author": "戴圣（汉）",
        "era": "汉",
        "path": "儒藏/礼经/礼记.txt",
        # body markers use 《礼记XXX》 format, distinct from bare TOC names
        "marker": re.compile(r"^　*《礼记(?P<title>[一-鿿]+)》", re.M),
        "use_gap_filter": False,
    },
    {
        "key": "zuozhuan",
        "name": "春秋左传",
        "author": "左丘明",
        "era": "春秋",
        "path": "儒藏/春秋/春秋左传.txt",
        # TOC and body share format, filter via gap
        "marker": re.compile(
            r"^　*(?P<title>[隐桓庄闵僖文宣成襄昭定哀]公（[一-鿿]+～[一-鿿]+）)",
            re.M,
        ),
        "use_gap_filter": True,
    },
]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"=== 五经其余 4 部 ===")

    for book in BOOKS:
        text = (DAIZHI / book["path"]).read_text(encoding="utf-8")
        if book["use_gap_filter"]:
            matches = find_body_markers(text, book["marker"])
        else:
            matches = list(book["marker"].finditer(text))
        chapters = split_with_matches(text, matches)

        out = []
        for i, (title, body) in enumerate(chapters, 1):
            out.append(
                {
                    "id": f"{book['key']}#{i}",
                    "source": book["name"],
                    "author": book["author"],
                    "era": book["era"],
                    "category": "经",
                    "chapter": title,
                    "section": i,
                    "content": body,
                }
            )

        dst = OUTPUT_DIR / f"{book['key']}.json"
        with dst.open("w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        chars = sum(len(d["content"]) for d in out)
        print(
            f"  {book['name']:6s}: {len(out):3d} 章, "
            f"{chars:>9,} 字  → {dst.relative_to(REPO_ROOT)}"
        )


if __name__ == "__main__":
    main()
