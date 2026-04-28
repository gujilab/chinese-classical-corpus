"""Fill 殆知阁 source gaps via ctext.org API + Wikisource (where possible).

Gaps to fill:
- 尚书 3 篇: 益稷 / 禹贡 / 泰誓上 (殆知阁 TOC has them but body empty)
- 周易 2 篇: 屯卦三 / 系辞上 (殆知阁 source format anomalies)
- 资治通鉴 卷 158, 171: NOT FILLABLE — no public source has this granularity

ctext API: https://api.ctext.org/gettext?urn=ctp:<book>/<section>
"""

import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from opencc import OpenCC

REPO_ROOT = Path(__file__).resolve().parents[1]
T2S = OpenCC("t2s")
UA = "classical-corpus/0.8 personal research"
DELAY = 1.0

# (book_key, urn, output_target_key, chapter_label_simp, output_field_path)
SHANGSHU_GAPS = [
    ("yi-and-ji", "虞书 益稷第五"),
    ("tribute-of-yu", "夏书 禹贡第一"),
    ("great-declaration-i", "周书 泰誓上第一"),
]

ZHOUYI_GAPS = [
    # 卦 3 屯 — note: 卦一 = 乾, 卦二 = 坤, 卦三 = 屯
    ("zhun", "03. 屯（卦三）"),
    ("xi-ci-shang", "系辞上"),
]


def fetch_ctext(urn_path: str) -> str:
    """Fetch text via ctext API. Returns concatenated lines (繁→简)."""
    url = f"https://api.ctext.org/gettext?urn=ctp:{urn_path}"
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "error" in data:
        raise RuntimeError(f"{data['error']['code']}: {data['error']['description']}")
    text = "\n".join(data.get("fulltext", []))
    return T2S.convert(text)


def patch_shangshu() -> None:
    """Add 3 missing 篇 to 尚书 JSON."""
    target = REPO_ROOT / "output" / "wujing" / "shangshu.json"
    data = json.load(target.open(encoding="utf-8"))
    existing_chapters = {d["chapter"] for d in data}

    next_seq = max(d["section"] for d in data) + 1
    for sub_urn, chapter in SHANGSHU_GAPS:
        if chapter in existing_chapters:
            print(f"  {chapter}: already present, skip")
            continue
        body = fetch_ctext(f"shang-shu/{sub_urn}")
        if not body.strip():
            print(f"  {chapter}: empty fetch, skip")
            continue
        data.append(
            {
                "id": f"shangshu#{next_seq}",
                "source": "尚书",
                "author": "佚名（先秦）",
                "era": "周",
                "category": "经",
                "chapter": chapter,
                "section": next_seq,
                "content": body,
                "_filled_from": "ctext.org",
            }
        )
        print(f"  {chapter}: +{len(body)} chars")
        next_seq += 1
        time.sleep(DELAY)

    with target.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → {target.relative_to(REPO_ROOT)}: now {len(data)} entries")


def patch_zhouyi() -> None:
    """Add 屯卦三 + 系辞上 to 周易 JSON."""
    target = REPO_ROOT / "output" / "wujing" / "zhouyi.json"
    data = json.load(target.open(encoding="utf-8"))
    existing_chapters = {d["chapter"] for d in data}

    next_seq = max(d["section"] for d in data) + 1
    for sub_urn, chapter in ZHOUYI_GAPS:
        if chapter in existing_chapters:
            print(f"  {chapter}: already present, skip")
            continue
        body = fetch_ctext(f"book-of-changes/{sub_urn}")
        if not body.strip():
            print(f"  {chapter}: empty fetch, skip")
            continue
        data.append(
            {
                "id": f"zhouyi#{next_seq}",
                "source": "周易",
                "author": "佚名（周）",
                "era": "周",
                "category": "经",
                "chapter": chapter,
                "section": next_seq,
                "content": body,
                "_filled_from": "ctext.org",
            }
        )
        print(f"  {chapter}: +{len(body)} chars")
        next_seq += 1
        time.sleep(DELAY)

    with target.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → {target.relative_to(REPO_ROOT)}: now {len(data)} entries")


def main() -> None:
    print("=== 尚书 缺漏补全 ===")
    patch_shangshu()
    print()
    print("=== 周易 缺漏补全 ===")
    patch_zhouyi()
    print()
    print("note: 资治通鉴 卷 158/171 cannot be filled — no public source"
          " indexes this corpus by individual juan.")


if __name__ == "__main__":
    main()
