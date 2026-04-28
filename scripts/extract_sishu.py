"""Normalize 四书 JSON from llm-dataset-chinese-poetry → unified schema."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_BASE = (
    Path.home()
    / "Documents/zion/reference/Chinese/classical/llm-dataset-chinese-poetry/data"
)
OUTPUT_DIR = REPO_ROOT / "output" / "sishu"

BOOKS = {
    "daxue": {
        "key": "daxue",
        "name": "大学",
        "author": "曾子（传）",
        "era": "春秋",
        "path": "四书五经/daxue.json",
    },
    "zhongyong": {
        "key": "zhongyong",
        "name": "中庸",
        "author": "子思",
        "era": "春秋",
        "path": "四书五经/zhongyong.json",
    },
    "lunyu": {
        "key": "lunyu",
        "name": "论语",
        "author": "孔子门徒（辑录）",
        "era": "春秋",
        "path": "论语/lunyu.json",
    },
    "mengzi": {
        "key": "mengzi",
        "name": "孟子",
        "author": "孟子",
        "era": "战国",
        "path": "四书五经/mengzi.json",
    },
}


def normalize_chapter(title: str, book_name: str) -> str:
    """Strip redundant book prefix from chapter titles, e.g. '论语·学而篇' → '学而'."""
    title = title.replace(f"{book_name}·", "")
    title = title.removesuffix("篇")
    return title.strip() or book_name


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = []

    for book in BOOKS.values():
        src = SOURCE_BASE / book["path"]
        raw = json.load(src.open(encoding="utf-8"))
        out = []
        for i, rec in enumerate(raw, 1):
            chapter = normalize_chapter(rec["title"], book["name"])
            out.append(
                {
                    "id": f"{book['key']}#{i}",
                    "source": book["name"],
                    "author": book["author"],
                    "era": book["era"],
                    "category": "经",
                    "chapter": chapter,
                    "section": i,
                    "content": rec["content"],
                }
            )
        dst = OUTPUT_DIR / f"{book['key']}.json"
        with dst.open("w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        summary.append((book["name"], len(out), dst))

    print("=== 四书 ===")
    for name, n, dst in summary:
        print(f"  {name:4s}: {n:3d} 章  →  {dst.relative_to(REPO_ROOT)}")
    total = sum(n for _, n, _ in summary)
    print(f"  total: {total} entries")


if __name__ == "__main__":
    main()
