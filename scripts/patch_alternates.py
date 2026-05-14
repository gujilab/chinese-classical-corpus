"""Patch 资治通鉴 158/171 + multiple 二十四史 from chtxt repo.

资治通鉴 158/171: 殆知阁 资治通鉴.txt (basic ●卷第N format) has these.
Multiple 二十四史: chtxt has clean ## XX‧卷N markers for several books we
extracted partially from 殆知阁.
"""

import json
import re
from pathlib import Path
from opencc import OpenCC

REPO_ROOT = Path(__file__).resolve().parents[1]
T2S = OpenCC("t2s")
DAIZHI = Path.home() / "Documents/zion/reference/Chinese/classical/corpora/daizhigev20"
CHTXT = Path.home() / "Documents/zion/reference/Chinese/classical/corpora/chtxt"

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


def patch_zizhi_tongjian() -> None:
    """Add 卷158 + 卷171 from 殆知阁 basic version."""
    target = REPO_ROOT / "output" / "zizhi-tongjian.json"
    data = json.load(target.open(encoding="utf-8"))
    existing_vols = {d["volume"] for d in data}

    text = (DAIZHI / "史藏/编年/资治通鉴.txt").read_text(encoding="utf-8")
    marker_re = re.compile(r"^●卷第([一二三四五六七八九十百千零]+)", re.M)
    matches = list(marker_re.finditer(text))
    target_vols = {158, 171}
    added = 0

    for i, m in enumerate(matches):
        vol = cn_to_int(m.group(1))
        if vol not in target_vols or vol in existing_vols:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.start():end].strip()
        era_m = re.search(r"【([一-鿿]+纪[一-鿿]+)】", body)
        period = era_m.group(1) if era_m else ""

        data.append(
            {
                "id": f"zizhi-tongjian#{vol}",
                "source": "资治通鉴",
                "author": "司马光",
                "era": "宋",
                "category": "史",
                "volume": vol,
                "period": period,
                "content": body,
                "_filled_from": "殆知阁 资治通鉴.txt 基础版",
            }
        )
        print(f"  卷{vol} ({period}): +{len(body):,} 字")
        added += 1

    if added:
        data.sort(key=lambda d: d["volume"])
        with target.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  → 资治通鉴: now {len(data)} 卷")
    else:
        print("  no patches needed")


def patch_chtxt_history(
    book_filename: str,  # "魏書" — chtxt filename without .txt
    book_zh_simp: str,  # "魏书" — simplified
    out_key: str,  # "weishu"
    author: str,
    era: str,
) -> None:
    """Replace history JSON with chtxt clean version."""
    target = REPO_ROOT / "output" / "histories" / f"{out_key}.json"
    src = CHTXT / "j.史書" / f"{book_filename}.txt"
    if not src.exists():
        print(f"  {book_zh_simp}: chtxt source missing, skip")
        return
    text = src.read_text(encoding="utf-8")

    marker_re = re.compile(
        rf"^## {re.escape(book_filename)}‧卷"
        r"([一二三四五六七八九十百千零]+)"
        r"([上中下]|之[一二三四五六七八九十]+)?"
        r"\s+(.+)$",
        re.M,
    )
    matches = list(marker_re.finditer(text))

    out = []
    seen_keys = set()
    for seq, m in enumerate(matches, 1):
        vol = cn_to_int(m.group(1))
        suffix = m.group(2) or ""
        title = m.group(0).removeprefix("## ").strip()
        key = f"{vol}{suffix}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        end = matches[seq].start() if seq < len(matches) else len(text)
        body = text[m.end():end].strip()
        out.append(
            {
                "id": f"{out_key}#{seq}",
                "source": book_zh_simp,
                "author": author,
                "era": era,
                "category": "史",
                "volume": vol,
                "volume_suffix": suffix,
                "chapter": T2S.convert(title),
                "content": T2S.convert(body),
                "_source": "chtxt (繁→简)",
            }
        )

    out.sort(key=lambda d: (d["volume"], d.get("volume_suffix", "")))
    with target.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    chars = sum(len(r["content"]) for r in out)
    print(f"  {book_zh_simp}: {len(out)} 卷, {chars:,} 字")


CHTXT_BOOKS = [
    # (chtxt_name, simp_name, key, author, era)
    ("晉書", "晋书", "jinshu", "房玄龄等", "唐"),
    ("宋書", "宋书", "songshu", "沈约", "南朝梁"),
    ("南齊書", "南齐书", "nanqishu", "萧子显", "南朝梁"),
    ("梁書", "梁书", "liangshu", "姚思廉", "唐"),
    ("陳書", "陈书", "chenshu", "姚思廉", "唐"),
    ("魏書", "魏书", "weishu", "魏收", "北齐"),
    ("北齊書", "北齐书", "beiqishu", "李百药", "唐"),
    ("北史", "北史", "beishi", "李延寿", "唐"),
    ("隋書", "隋书", "suishu", "魏徵等", "唐"),
]


def main() -> None:
    print("=== 资治通鉴 158/171 补全 ===")
    patch_zizhi_tongjian()
    print()
    print("=== 二十四史 chtxt 替换 ===")
    for args in CHTXT_BOOKS:
        patch_chtxt_history(*args)


if __name__ == "__main__":
    main()
