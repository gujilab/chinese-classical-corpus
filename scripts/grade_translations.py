"""L3: Claude-graded translation quality sampling.

Samples N c2m (古→今) pairs from translate.jsonl, grades each via the Claude
API on a 1-5 faithfulness/fluency rubric. Uses prompt caching (system prompt
is reused 100x → ~90% cost savings on cached portion) and structured outputs
(json_schema) so each response is guaranteed-valid JSON.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path("/Users/zion/Documents/zion/classical-corpus")
SOURCE = REPO_ROOT / "output" / "instruct" / "translate.jsonl"
OUT_REPORT = REPO_ROOT / "output" / "quality_report.md"
OUT_GRADES = REPO_ROOT / "output" / "quality_grades.jsonl"

N_SAMPLE = 100
MODEL = "claude-opus-4-7"

GRADER_SYSTEM = """你是中国古典文献翻译评估专家。给定一对古文原文和现代汉语翻译，按以下两个维度各打 1-5 分：

**忠实度 (faithfulness)** — 译文是否准确传达原文（不漏译、不添译、不曲解）
- 5 = 完全准确
- 4 = 基本准确，细节小瑕疵
- 3 = 主要意思对，但有明显遗漏或失真
- 2 = 多处偏差，关键意思错误
- 1 = 严重错误，几乎无关

**通顺度 (fluency)** — 现代汉语本身是否自然流畅
- 5 = 自然流畅，符合现代汉语习惯
- 4 = 略显生硬但可读
- 3 = 明显机翻感或生涩
- 2 = 多处不通
- 1 = 难以理解

评分标准从严。comment 字段用一句话简述主要问题或亮点（10-30 字）。"""

GRADER_SCHEMA = {
    "type": "object",
    "properties": {
        "faithfulness": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "fluency": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "comment": {"type": "string"},
    },
    "required": ["faithfulness", "fluency", "comment"],
    "additionalProperties": False,
}


def load_c2m_pool() -> list[dict]:
    """Load all c2m records into memory (~960K records, ~300MB)."""
    pool = []
    with SOURCE.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("task") == "c2m":
                pool.append(r)
    return pool


def stratified_sample(records: list[dict], n: int, seed: int = 42) -> list[dict]:
    """Proportional stratified sample by category."""
    rng = random.Random(seed)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_cat[r.get("category", "?")].append(r)

    total = len(records)
    sample: list[dict] = []
    for cat, items in by_cat.items():
        k = max(1, round(n * len(items) / total))
        sample.extend(rng.sample(items, min(k, len(items))))
    rng.shuffle(sample)
    return sample[:n]


def grade_one(client, source: str, target: str) -> tuple[dict, object]:
    user_prompt = f"古文原文：\n{source}\n\n现代汉语翻译：\n{target}"
    msg = client.messages.create(
        model=MODEL,
        max_tokens=512,
        # Disable thinking — grading is a fast classification task
        thinking={"type": "disabled"},
        system=[
            {
                "type": "text",
                "text": GRADER_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
        output_config={
            "format": {"type": "json_schema", "schema": GRADER_SCHEMA}
        },
    )
    text_block = next(b for b in msg.content if b.type == "text")
    grade = json.loads(text_block.text)
    return grade, msg.usage


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set")

    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("anthropic SDK not installed: pip install anthropic")

    print(f"loading c2m pool from {SOURCE.name}...")
    pool = load_c2m_pool()
    print(f"  {len(pool):,} c2m records")

    sample = stratified_sample(pool, N_SAMPLE)
    cat_dist = defaultdict(int)
    for r in sample:
        cat_dist[r["category"]] += 1
    print(f"  stratified sample: {dict(cat_dist)}")

    client = Anthropic()
    grades: list[dict] = []
    totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0}

    print(f"\ngrading {len(sample)} records with {MODEL}...")
    t0 = time.time()
    for i, r in enumerate(sample, 1):
        try:
            grade, usage = grade_one(client, r["input"], r["output"])
        except Exception as e:
            print(f"  [{i:3d}/{len(sample)}] FAILED: {e}")
            continue
        grades.append(
            {
                **grade,
                "_id": r["id"],
                "_source": r["source"],
                "_category": r["category"],
                "_input": r["input"][:80],
                "_output": r["output"][:80],
            }
        )
        totals["input"] += usage.input_tokens
        totals["output"] += usage.output_tokens
        totals["cache_create"] += usage.cache_creation_input_tokens or 0
        totals["cache_read"] += usage.cache_read_input_tokens or 0

        marker = "⚠" if grade["faithfulness"] < 3 or grade["fluency"] < 3 else " "
        print(
            f"  [{i:3d}/{len(sample)}] {marker} "
            f"f={grade['faithfulness']} l={grade['fluency']} "
            f"{r['source'][:25]:<25s} | {grade['comment'][:40]}"
        )

    elapsed = time.time() - t0
    print(f"\ngraded {len(grades)} in {elapsed:.0f}s ({elapsed/len(grades):.1f}s/record)")

    # save raw grades
    with OUT_GRADES.open("w", encoding="utf-8") as f:
        for g in grades:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")

    # aggregate
    f_avg = sum(g["faithfulness"] for g in grades) / len(grades)
    l_avg = sum(g["fluency"] for g in grades) / len(grades)
    low = [g for g in grades if g["faithfulness"] < 3 or g["fluency"] < 3]

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for g in grades:
        by_cat[g["_category"]].append(g)

    # cost (opus-4-7: $5/$25/1M)
    cost = (
        totals["input"] * 5e-6
        + totals["cache_create"] * 5e-6 * 1.25
        + totals["cache_read"] * 5e-6 * 0.1
        + totals["output"] * 25e-6
    )

    lines = [
        "# Translation Quality Report (L3 LLM grading)",
        "",
        f"- **Model**: {MODEL}",
        f"- **Sample**: {len(grades)} c2m (古→今) pairs, stratified by category",
        f"- **Faithfulness avg**: {f_avg:.2f} / 5",
        f"- **Fluency avg**: {l_avg:.2f} / 5",
        f"- **Low-quality flags** (faithfulness or fluency ≤ 2): {len(low)} ({100*len(low)/len(grades):.0f}%)",
        "",
        "## Cost",
        f"- Input (uncached): {totals['input']:,} tokens",
        f"- Cache create: {totals['cache_create']:,} (×1.25)",
        f"- Cache read: {totals['cache_read']:,} (×0.1)",
        f"- Output: {totals['output']:,}",
        f"- Cache hit rate: {100*totals['cache_read']/(totals['cache_read']+totals['cache_create']+1):.1f}%",
        f"- **Total cost: ${cost:.3f}**",
        "",
        "## Quality by category",
        "",
        "| Category | N | Faithfulness | Fluency | Low-flag |",
        "|---|---|---|---|---|",
    ]
    for cat in sorted(by_cat):
        items = by_cat[cat]
        f_a = sum(g["faithfulness"] for g in items) / len(items)
        l_a = sum(g["fluency"] for g in items) / len(items)
        n_low = sum(1 for g in items if g["faithfulness"] < 3 or g["fluency"] < 3)
        lines.append(f"| {cat} | {len(items)} | {f_a:.2f} | {l_a:.2f} | {n_low} |")

    if low:
        lines += ["", "## Flagged samples (≤ 2 on either dimension)", ""]
        for g in low[:15]:
            lines += [
                f"### {g['_id']} ({g['_source']})",
                f"- **f={g['faithfulness']} l={g['fluency']}** — {g['comment']}",
                f"- 古: {g['_input']}",
                f"- 今: {g['_output']}",
                "",
            ]

    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nreport:  {OUT_REPORT.relative_to(REPO_ROOT)}")
    print(f"grades:  {OUT_GRADES.relative_to(REPO_ROOT)}")
    print(f"summary: faithfulness {f_avg:.2f}, fluency {l_avg:.2f}, "
          f"flagged {len(low)}/{len(grades)}, cost ${cost:.3f}")


if __name__ == "__main__":
    main()
