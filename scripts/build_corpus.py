"""Merge all output/*.json into a single corpus.jsonl + stats summary."""

import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "output"
CORPUS_PATH = OUTPUT_DIR / "corpus.jsonl"
STATS_PATH = OUTPUT_DIR / "stats.md"


def iter_json_files(root: Path):
    for p in sorted(root.rglob("*.json")):
        if p.name in {"corpus.json", "stats.json"}:
            continue
        yield p


def main() -> None:
    by_source = Counter()
    chars_by_source = Counter()
    total = 0

    with CORPUS_PATH.open("w", encoding="utf-8") as out:
        for path in iter_json_files(OUTPUT_DIR):
            data = json.load(path.open(encoding="utf-8"))
            for rec in data:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                source = rec.get("source", "unknown")
                by_source[source] += 1
                chars_by_source[source] += len(rec.get("content", ""))
                total += 1

    stats_lines = [
        "# Corpus Stats",
        "",
        f"Total records: **{total:,}**",
        f"Total chars:   **{sum(chars_by_source.values()):,}**",
        "",
        "## By source",
        "",
        "| 文献 | 条数 | 字数 |",
        "|------|------|------|",
    ]
    for src in sorted(by_source, key=lambda s: -chars_by_source[s]):
        stats_lines.append(
            f"| {src} | {by_source[src]:,} | {chars_by_source[src]:,} |"
        )
    STATS_PATH.write_text("\n".join(stats_lines) + "\n", encoding="utf-8")

    print(f"wrote {CORPUS_PATH.relative_to(REPO_ROOT)}: {total} records")
    print(f"wrote {STATS_PATH.relative_to(REPO_ROOT)}")
    print()
    for src in sorted(by_source, key=lambda s: -chars_by_source[s]):
        print(f"  {src:12s}: {by_source[src]:5,} records  {chars_by_source[src]:>10,} chars")


if __name__ == "__main__":
    main()
