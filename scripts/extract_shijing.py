"""Normalize 诗经 from chinese-poetry source → unified schema.

Source title format: 诗经·{大类}·{篇/什}·{标题}
  大类: 国风/小雅/大雅/周颂/鲁颂/商颂
  篇/什: 周南/邶风/鹿鸣之什/...
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    Path.home()
    / "Documents/zion/reference/Chinese/classical/llm-dataset-chinese-poetry/data/诗经/shijing.json"
)
OUTPUT = REPO_ROOT / "output" / "wujing" / "shijing.json"


def main() -> None:
    raw = json.load(SOURCE.open(encoding="utf-8"))
    out = []
    for i, rec in enumerate(raw, 1):
        parts = rec["title"].split("·")
        # parts[0] == "诗经"
        chapter = parts[1] if len(parts) > 1 else ""
        subchapter = parts[2] if len(parts) > 2 else ""
        title = parts[3] if len(parts) > 3 else parts[-1]
        out.append(
            {
                "id": f"shijing#{i}",
                "source": "诗经",
                "author": "佚名（西周至春秋）",
                "era": "周",
                "category": "经",
                "chapter": chapter,
                "subchapter": subchapter,
                "title": title,
                "section": i,
                "content": rec["content"],
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    from collections import Counter
    by_chapter = Counter(d["chapter"] for d in out)
    print(f"诗经: {len(out)} 篇  → {OUTPUT.relative_to(REPO_ROOT)}")
    for ch, n in by_chapter.most_common():
        print(f"  {ch}: {n}")


if __name__ == "__main__":
    main()
