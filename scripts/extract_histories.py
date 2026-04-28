"""Extract 史记/汉书/后汉书/三国志 from 殆知阁 → unified schema.

Two parsing strategies depending on source format:
  A. 钦定四库全书 separator + first-line title  — for 史记四库/后汉书四库/三国志
  B. 卷X title (with optional indent) + gap filter — for 汉书 (no 四库 version)
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DAIZHI = (
    Path.home() / "Documents/zion/reference/Chinese/classical/corpora/daizhigev20"
)
OUTPUT_DIR = REPO_ROOT / "output" / "histories"

# Strategy A: split by 钦定四库全书, extract first 卷X line as title.
# Note: must use [\s　] not \s, as full-width space (U+3000) is not in default \s.
QKINDI_VOL_RE = re.compile(
    r"钦定四库全书[^\n]*\n"  # preamble line
    r"(?:[^\n]*\n){0,3}?"  # up to 3 lines of metadata (史部/编年类/etc.)
    # title: optional 1-4 char book-name prefix (史记/汉书/后汉书/三国志/魏志/...) + 卷N + optional 上中下
    r"[\s　]*(?P<title>[一-鿿]{0,4}[卷巻][一-鿿]+(?:[上中下])?)",
    re.M,
)

# Strategy B: 卷X title with optional indent and optional book-name prefix.
# Catches plain "卷一 帝纪第一" (汉书) AND "周书卷一　　帝纪第一" (周书 body markers).
INDENT_VOL_RE = re.compile(
    r"^[\s　]*(?P<title>[一-鿿]{0,4}卷[一-鿿]+(?:[上中下])?[\s　]+[一-鿿]+第[一-鿿]+(?:[上中下])?)",
    re.M,
)

# Strategy C: ordinal-only marker (帝纪/本纪/列传/载记/志) at line start, no 卷X prefix.
# Used by 晋书/宋书/南齐书/梁书/陈书. Allows optional 补 prefix (北齐书 has 补帝纪/补列传
# from chapters reconstructed after lost original text).
ORDINAL_RE = re.compile(
    r"^[\s　]*(?P<title>补?(?:帝纪|本纪|列传|载记|志)第[一-鿿]+(?:[上中下])?(?:[\s　]+[^\n]*)?)",
    re.M,
)

# Strategy D: reverse 第N卷 format with optional 补 + ordinal type
# Used by 北齐书 body: "第一卷　　补帝纪第一"
REVERSE_VOL_RE = re.compile(
    r"^[\s　]*(?P<title>第[一-鿿]+卷[\s　]+补?(?:帝纪|本纪|列传|载记|志)第[一-鿿]+(?:[上中下])?(?:[\s　]+[^\n]*)?)",
    re.M,
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


def vol_num_from_title(title: str) -> int:
    """Extract volume number from titles like '卷一' / '卷一上' / '魏志卷三'."""
    m = re.search(r"[卷巻]([一-鿿]+?)(?:[上中下])?(?:\s|$)", title)
    if not m:
        return 0
    return cn_to_int(m.group(1))


def extract_strategy_a(path: Path, key: str, name: str, author: str, era: str) -> list[dict]:
    """Use 钦定四库全书 separator. Each match is a volume start."""
    text = path.read_text(encoding="utf-8")
    matches = list(QKINDI_VOL_RE.finditer(text))
    out = []
    seen_titles = set()  # dedup by full title (handles 魏志卷一/蜀志卷一/吴志卷一)
    seq = 0
    for i, m in enumerate(matches):
        title = m.group("title").strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        if not body or title in seen_titles:
            continue
        seen_titles.add(title)
        seq += 1
        out.append(
            {
                "id": f"{key}#{seq}",
                "source": name,
                "author": author,
                "era": era,
                "category": "史",
                "volume": vol_num_from_title(title),
                "chapter": title,
                "content": body,
            }
        )
    return out


def extract_strategy_d(path: Path, key: str, name: str, author: str, era: str) -> list[dict]:
    """Use 第N卷 reverse-order markers. Used by 北齐书."""
    text = path.read_text(encoding="utf-8")
    matches = list(REVERSE_VOL_RE.finditer(text))
    if not matches:
        return []
    out = []
    for seq, m in enumerate(matches, 1):
        title = m.group("title").strip()
        end = matches[seq].start() if seq < len(matches) else len(text)
        body = text[m.end():end].strip()
        if not body:
            continue
        out.append(
            {
                "id": f"{key}#{seq}",
                "source": name, "author": author, "era": era, "category": "史",
                "volume": seq, "chapter": title, "content": body,
            }
        )
    return out


def extract_strategy_c(path: Path, key: str, name: str, author: str, era: str) -> list[dict]:
    """Use ordinal-only markers (帝纪/本纪/...) at line start. Skip TOC by gap filter."""
    text = path.read_text(encoding="utf-8")
    matches = list(ORDINAL_RE.finditer(text))
    if not matches:
        return []

    # gap filter: TOC has tight markers, body has spaced ones
    body_start_idx = 0
    for i in range(len(matches) - 1):
        if matches[i + 1].start() - matches[i].end() > 200:
            body_start_idx = i + 1
            break
    matches = matches[body_start_idx:]

    out = []
    for seq, m in enumerate(matches, 1):
        title = m.group("title").strip()
        end = matches[seq].start() if seq < len(matches) else len(text)
        body = text[m.end():end].strip()
        if not body:
            continue
        out.append(
            {
                "id": f"{key}#{seq}",
                "source": name,
                "author": author,
                "era": era,
                "category": "史",
                "volume": seq,
                "chapter": title,
                "content": body,
            }
        )
    return out


def extract_strategy_b(path: Path, key: str, name: str, author: str, era: str) -> list[dict]:
    """Use 卷X markers with TOC→body gap filter."""
    text = path.read_text(encoding="utf-8")
    matches = list(INDENT_VOL_RE.finditer(text))
    if not matches:
        return []

    # find first big-gap match (TOC→body boundary)
    body_start_idx = 0
    for i in range(len(matches) - 1):
        if matches[i + 1].start() - matches[i].end() > 200:
            body_start_idx = i + 1
            break
    matches = matches[body_start_idx:]

    out = []
    seen_titles = set()  # dedup by full title (handles 魏志卷一/蜀志卷一/吴志卷一)
    seq = 0
    for i, m in enumerate(matches):
        title = m.group("title").strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        if not body or title in seen_titles:
            continue
        seen_titles.add(title)
        seq += 1
        out.append(
            {
                "id": f"{key}#{seq}",
                "source": name,
                "author": author,
                "era": era,
                "category": "史",
                "volume": vol_num_from_title(title),
                "chapter": title,
                "content": body,
            }
        )
    return out


HISTORIES = [
    # v0.5
    {"key": "shiji", "name": "史记", "author": "司马迁", "era": "汉",
     "path": "史藏/正史/史记四库.txt", "strategy": "a", "expected": 130},
    {"key": "hanshu", "name": "汉书", "author": "班固", "era": "汉",
     "path": "史藏/正史/汉书.txt", "strategy": "b", "expected": 100},
    {"key": "houhanshu", "name": "后汉书", "author": "范晔", "era": "南朝宋",
     "path": "史藏/正史/后汉书四库.txt", "strategy": "a", "expected": 120},
    {"key": "sanguozhi", "name": "三国志", "author": "陈寿", "era": "晋",
     "path": "史藏/正史/三国志.txt", "strategy": "a", "expected": 65},
    # v0.7
    {"key": "jinshu", "name": "晋书", "author": "房玄龄等", "era": "唐",
     "path": "史藏/正史/晋书.txt", "strategy": "c", "expected": 130},
    {"key": "songshu", "name": "宋书", "author": "沈约", "era": "南朝梁",
     "path": "史藏/正史/宋书.txt", "strategy": "c", "expected": 100},
    {"key": "nanqishu", "name": "南齐书", "author": "萧子显", "era": "南朝梁",
     "path": "史藏/正史/南齐书.txt", "strategy": "c", "expected": 59},
    {"key": "liangshu", "name": "梁书", "author": "姚思廉", "era": "唐",
     "path": "史藏/正史/梁书.txt", "strategy": "c", "expected": 56},
    {"key": "chenshu", "name": "陈书", "author": "姚思廉", "era": "唐",
     "path": "史藏/正史/陈书.txt", "strategy": "c", "expected": 36},
    # v0.9
    {"key": "weishu", "name": "魏书", "author": "魏收", "era": "北齐",
     "path": "史藏/正史/魏书.txt", "strategy": "b", "expected": 130},
    {"key": "beiqishu", "name": "北齐书", "author": "李百药", "era": "唐",
     "path": "史藏/正史/北齐书.txt", "strategy": "d", "expected": 50},
    {"key": "zhoushu", "name": "周书", "author": "令狐德棻等", "era": "唐",
     "path": "史藏/正史/周书.txt", "strategy": "b", "expected": 50},
    {"key": "nanshi", "name": "南史", "author": "李延寿", "era": "唐",
     "path": "史藏/正史/南史.txt", "strategy": "b", "expected": 80},
    {"key": "beishi", "name": "北史", "author": "李延寿", "era": "唐",
     "path": "史藏/正史/北史.txt", "strategy": "c", "expected": 100},
    {"key": "suishu", "name": "隋书", "author": "魏徵等", "era": "唐",
     "path": "史藏/正史/隋书.txt", "strategy": "c", "expected": 85},
]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=== 二十四史前 15 部 ===")
    strategies = {"a": extract_strategy_a, "b": extract_strategy_b,
                  "c": extract_strategy_c, "d": extract_strategy_d}
    for h in HISTORIES:
        path = DAIZHI / h["path"]
        fn = strategies[h["strategy"]]
        records = fn(path, h["key"], h["name"], h["author"], h["era"])

        dst = OUTPUT_DIR / f"{h['key']}.json"
        with dst.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        chars = sum(len(r["content"]) for r in records)
        coverage = f"{len(records)}/{h['expected']}"
        print(
            f"  {h['name']:5s}: {coverage:>10s} 卷, "
            f"{chars:>9,} 字  → {dst.relative_to(REPO_ROOT)}"
        )


if __name__ == "__main__":
    main()
