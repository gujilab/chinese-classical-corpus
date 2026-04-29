"""Build 古译今 / 今译古 instruction tuning dataset from NiuTrans/Classical-Modern.

Output format (JSONL, each line is one instruction record):
  {
    "id": "instruct#N",
    "task": "c2m" | "m2c",
    "instruction": "...",
    "input": "<source line>",
    "output": "<target line>",
    "source": "论语·学而篇",
    "category": "经"
  }

Filters:
- Drop lines shorter than 4 chars (too short to be meaningful)
- Drop lines longer than 500 chars (likely concatenation errors)
- Drop pairs where source/target length ratio is extreme (>10x)
"""

import json
import random
import re
from pathlib import Path

REPO_ROOT = Path("/Users/zion/Documents/zion/classical-corpus")
NIUTRANS = Path(
    "/Users/zion/Documents/zion/reference/Chinese/classical/corpora/Classical-Modern/双语数据"
)
OUT_PATH = REPO_ROOT / "output" / "instruct" / "translate.jsonl"

# Instruction prompt variety (古→今)
C2M_PROMPTS = [
    "将下列古文翻译成现代汉语：",
    "把这句文言文译成白话文：",
    "请用现代汉语翻译这段古文：",
    "解释下列古文的含义：",
    "翻译：",
    "用白话解释这句古文：",
]

# Instruction prompt variety (今→古)
M2C_PROMPTS = [
    "将下列现代汉语翻译成古文：",
    "用文言文表达这句话：",
    "把这段白话改写为古文：",
    "请用古文表达：",
]

# Books → category mapping (best-effort; defaults to other)
CATEGORY_MAP = {
    # 经
    "论语": "经", "孟子": "经", "中庸": "经", "大学": "经",
    "诗经": "经", "尚书": "经", "周易": "经", "礼记": "经",
    "周礼": "经", "仪礼": "经", "左传": "经", "公羊传": "经",
    "穀梁传": "经", "孝经": "经", "尔雅": "经",
    # 史
    "史记": "史", "汉书": "史", "后汉书": "史", "三国志": "史",
    "晋书": "史", "宋书": "史", "南齐书": "史", "梁书": "史",
    "陈书": "史", "魏书": "史", "北齐书": "史", "周书": "史",
    "南史": "史", "北史": "史", "隋书": "史", "旧唐书": "史",
    "新唐书": "史", "宋史": "史", "辽史": "史", "金史": "史",
    "元史": "史", "明史": "史", "资治通鉴": "史",
    # 子
    "老子": "子", "庄子": "子", "列子": "子", "墨子": "子",
    "荀子": "子", "韩非子": "子", "孙子兵法": "子", "六韬": "子",
    "三略": "子", "司马法": "子", "吴子": "子", "孙膑兵法": "子",
    "尉缭子": "子", "黄帝内经": "子", "伤寒论": "子",
    "公孙龙子": "子", "吕氏春秋": "子", "商君书": "子",
    "管子": "子",
}

CATEGORY_DEFAULT = "集"  # 文集/笔记/其他


def categorize(book: str) -> str:
    return CATEGORY_MAP.get(book, CATEGORY_DEFAULT)


def is_valid_pair(src: str, tgt: str) -> bool:
    src, tgt = src.strip(), tgt.strip()
    if len(src) < 4 or len(tgt) < 4:
        return False
    if len(src) > 500 or len(tgt) > 500:
        return False
    # ratio check: extreme imbalance suggests misalignment
    ratio = max(len(src), len(tgt)) / max(min(len(src), len(tgt)), 1)
    if ratio > 10:
        return False
    return True


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    random.seed(42)

    book_dirs = sorted(d for d in NIUTRANS.iterdir() if d.is_dir())
    print(f"processing {len(book_dirs)} books...")

    n_records = 0
    n_skipped = 0
    by_book: dict[str, int] = {}

    with OUT_PATH.open("w", encoding="utf-8") as out:
        for book_dir in book_dirs:
            book = book_dir.name
            cat = categorize(book)
            book_count = 0

            for src_path in sorted(book_dir.rglob("source.txt")):
                tgt_path = src_path.parent / "target.txt"
                if not tgt_path.exists():
                    continue
                # chapter = directory chain after book name
                rel = src_path.parent.relative_to(book_dir)
                chapter = str(rel) if rel.parts else ""
                source_label = f"{book}·{chapter}" if chapter else book

                src_lines = src_path.read_text(encoding="utf-8").splitlines()
                tgt_lines = tgt_path.read_text(encoding="utf-8").splitlines()

                for s, t in zip(src_lines, tgt_lines):
                    if not is_valid_pair(s, t):
                        n_skipped += 1
                        continue

                    s, t = s.strip(), t.strip()

                    # 古→今
                    n_records += 1
                    out.write(
                        json.dumps(
                            {
                                "id": f"instruct#{n_records}",
                                "task": "c2m",
                                "instruction": random.choice(C2M_PROMPTS),
                                "input": s,
                                "output": t,
                                "source": source_label,
                                "category": cat,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    book_count += 1

                    # 今→古
                    n_records += 1
                    out.write(
                        json.dumps(
                            {
                                "id": f"instruct#{n_records}",
                                "task": "m2c",
                                "instruction": random.choice(M2C_PROMPTS),
                                "input": t,
                                "output": s,
                                "source": source_label,
                                "category": cat,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    book_count += 1

            by_book[book] = book_count

    print(f"\nwritten: {n_records:,} records (skipped {n_skipped:,} invalid pairs)")
    print(f"output: {OUT_PATH.relative_to(REPO_ROOT)}")
    size_mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"size: {size_mb:.1f} MB")
    print()
    print("=== top 15 books by record count ===")
    for book, cnt in sorted(by_book.items(), key=lambda x: -x[1])[:15]:
        print(f"  {book:15s}: {cnt:>7,}")


if __name__ == "__main__":
    main()
