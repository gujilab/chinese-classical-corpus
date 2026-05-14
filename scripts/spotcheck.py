"""Manual spot-check: print 20 stratified samples for human review."""

import json
import random
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "output" / "instruct" / "translate.jsonl"
OUT = REPO_ROOT / "output" / "spotcheck.md"

PER_CATEGORY = 5  # 5 each from 经/史/子/集 = 20 total

# Try to also span text length — some short, some long


def main() -> None:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    with SOURCE.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("task") != "c2m":
                continue
            by_cat[r.get("category", "?")].append(r)

    print(f"loaded c2m by category: {[(c, len(v)) for c, v in by_cat.items()]}")

    rng = random.Random(42)
    samples: list[dict] = []
    for cat in ("经", "史", "子", "集"):
        items = by_cat.get(cat, [])
        if not items:
            continue
        # stratify within category by length: short / medium / long mix
        items_sorted = sorted(items, key=lambda r: len(r["input"]))
        bucket_size = max(len(items_sorted) // PER_CATEGORY, 1)
        picked = []
        for i in range(PER_CATEGORY):
            start = i * len(items_sorted) // PER_CATEGORY
            end = (i + 1) * len(items_sorted) // PER_CATEGORY
            bucket = items_sorted[start:end] or items_sorted[-1:]
            picked.append(rng.choice(bucket))
        samples.extend(picked)

    lines = [
        "# Manual Spot-Check (20 stratified samples)",
        "",
        "Eyeball these and check whether 古/今 alignment looks correct.",
        "Sample is stratified: 5 per category (经/史/子/集), and within each",
        "category 5 length buckets (very short → very long).",
        "",
        "**What to look for:**",
        "- Does the 现代文 actually correspond to the 古文? (faithfulness)",
        "- Is the 现代文 readable Chinese? (fluency)",
        "- Are there obvious misalignments (古/今 swapped, wrong line, etc.)?",
        "",
        "---",
        "",
    ]

    for i, r in enumerate(samples, 1):
        lines += [
            f"## Sample {i} — {r['source']} ({r['category']})",
            f"",
            f"**古文 ({len(r['input'])} 字):**",
            f"> {r['input']}",
            f"",
            f"**现代文 ({len(r['output'])} 字):**",
            f"> {r['output']}",
            f"",
            f"**Verdict:** [ ] OK   [ ] 错位   [ ] 翻译质量差   [ ] 其他: ___________",
            f"",
            f"---",
            f"",
        ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(REPO_ROOT)} — open in editor and review")
    print(f"({len(samples)} samples across {len({s['category'] for s in samples})} categories)")


if __name__ == "__main__":
    main()
