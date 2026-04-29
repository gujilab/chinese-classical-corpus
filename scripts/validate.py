"""L1+L2 validation: structural integrity + statistics.

Checks:
- Every JSON parses
- Required fields present
- No duplicate IDs (per file)
- No empty/whitespace-only content
- UTF-8 encoding clean
- Length distributions per source
- Suspicious entries (too short, too long, weird chars)
- Cross-file ID uniqueness in corpus.jsonl
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path("/Users/zion/Documents/zion/classical-corpus")
OUT = REPO_ROOT / "output"

REQUIRED_BASE = {"id", "source", "content"}
WARN = "\033[33m⚠"
FAIL = "\033[31m✗"
PASS = "\033[32m✓"
RESET = "\033[0m"


class Issues:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def report(self, name: str) -> None:
        if not self.errors and not self.warnings:
            print(f"{PASS} {name}: clean{RESET}")
            return
        if self.errors:
            print(f"{FAIL} {name}: {len(self.errors)} errors{RESET}")
            for e in self.errors[:10]:
                print(f"    {e}")
            if len(self.errors) > 10:
                print(f"    ... and {len(self.errors) - 10} more")
        if self.warnings:
            print(f"{WARN} {name}: {len(self.warnings)} warnings{RESET}")
            for w in self.warnings[:5]:
                print(f"    {w}")
            if len(self.warnings) > 5:
                print(f"    ... and {len(self.warnings) - 5} more")


def validate_record(rec: dict, idx: int, fname: str, issues: Issues) -> None:
    """Per-record schema check."""
    missing = REQUIRED_BASE - rec.keys()
    if missing:
        issues.err(f"[{fname}#{idx}] missing fields: {missing}")
        return
    if not isinstance(rec.get("id"), str):
        issues.err(f"[{fname}#{idx}] id not string")
    if not isinstance(rec.get("content"), str):
        issues.err(f"[{fname}#{idx}] content not string")
    elif not rec["content"].strip():
        issues.err(f"[{fname}#{idx}] empty content (id={rec.get('id')})")


def check_duplicates(records: list[dict], fname: str, issues: Issues) -> None:
    """Find duplicate IDs in a single file."""
    seen = Counter(r["id"] for r in records if "id" in r)
    dups = {k: v for k, v in seen.items() if v > 1}
    for k, v in list(dups.items())[:5]:
        issues.err(f"[{fname}] duplicate id '{k}': {v}x")
    if len(dups) > 5:
        issues.err(f"[{fname}] ... {len(dups) - 5} more duplicate ids")


def length_stats(records: list[dict]) -> dict:
    lens = sorted(len(r.get("content", "")) for r in records)
    n = len(lens)
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "min": lens[0],
        "p10": lens[n // 10] if n >= 10 else lens[0],
        "median": lens[n // 2],
        "p90": lens[n * 9 // 10] if n >= 10 else lens[-1],
        "max": lens[-1],
        "total_chars": sum(lens),
    }


def find_suspicious(records: list[dict], fname: str, issues: Issues) -> None:
    """Detect anomalies: too short, weird chars, possible OCR errors."""
    for r in records:
        c = r.get("content", "")
        if not c:
            continue
        # entries with mostly non-CJK chars in classical text
        cjk_chars = sum(1 for ch in c if "一" <= ch <= "鿿")
        if len(c) > 100 and cjk_chars / len(c) < 0.3:
            issues.warn(f"[{fname}] {r['id']}: only {cjk_chars}/{len(c)} CJK chars")
        # very high □ ratio (corruption indicator)
        box_count = c.count("□")
        if box_count > 5 and box_count / len(c) > 0.05:
            issues.warn(
                f"[{fname}] {r['id']}: {box_count} □ chars ({box_count/len(c):.1%})"
            )


def validate_json_file(path: Path) -> tuple[Issues, dict]:
    """Validate a single JSON file (array of records)."""
    issues = Issues()
    rel = path.relative_to(REPO_ROOT)
    try:
        records = json.load(path.open(encoding="utf-8"))
    except json.JSONDecodeError as e:
        issues.err(f"JSON parse error: {e}")
        return issues, {}
    except UnicodeDecodeError as e:
        issues.err(f"UTF-8 decode error: {e}")
        return issues, {}

    if not isinstance(records, list):
        issues.err("not a JSON array")
        return issues, {}

    for i, rec in enumerate(records):
        validate_record(rec, i, str(rel), issues)

    check_duplicates(records, str(rel), issues)
    find_suspicious(records, str(rel), issues)
    return issues, {"records": len(records), **length_stats(records)}


def validate_jsonl_file(path: Path) -> tuple[Issues, dict]:
    """Validate JSONL (instruction datasets)."""
    issues = Issues()
    rel = path.relative_to(REPO_ROOT)
    n = 0
    by_task: Counter = Counter()
    by_category: Counter = Counter()
    input_lens: list[int] = []
    output_lens: list[int] = []
    seen_ids: set = set()
    dup_count = 0

    try:
        with path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as e:
                    issues.err(f"line {line_no}: parse error: {e}")
                    continue
                n += 1
                # required fields
                for fld in ("id", "task", "instruction", "input", "output"):
                    if fld not in rec:
                        issues.err(f"line {line_no}: missing '{fld}'")
                        break
                else:
                    rid = rec["id"]
                    if rid in seen_ids:
                        dup_count += 1
                        if dup_count <= 5:
                            issues.err(f"line {line_no}: duplicate id '{rid}'")
                    seen_ids.add(rid)
                    by_task[rec["task"]] += 1
                    by_category[rec.get("category", "")] += 1
                    if not rec["input"].strip() or not rec["output"].strip():
                        issues.err(f"line {line_no}: empty input/output")
                    input_lens.append(len(rec["input"]))
                    output_lens.append(len(rec["output"]))
    except UnicodeDecodeError as e:
        issues.err(f"UTF-8 decode error: {e}")

    if dup_count > 5:
        issues.err(f"... {dup_count - 5} more duplicate ids")

    def pct(xs: list[int], p: int) -> int:
        if not xs:
            return 0
        s = sorted(xs)
        return s[len(s) * p // 100]

    stats = {
        "records": n,
        "by_task": dict(by_task),
        "by_category": dict(by_category),
        "input_p10": pct(input_lens, 10),
        "input_median": pct(input_lens, 50),
        "input_p90": pct(input_lens, 90),
        "output_p10": pct(output_lens, 10),
        "output_median": pct(output_lens, 50),
        "output_p90": pct(output_lens, 90),
    }
    return issues, stats




def validate_jsonl_corpus(path):
    """Validate corpus.jsonl — plain records (no task field)."""
    issues = Issues()
    rel = path.relative_to(REPO_ROOT)
    n = 0
    by_source = Counter()
    by_category = Counter()
    seen_ids = set()
    dups = 0
    try:
        with path.open(encoding='utf-8') as f:
            for ln, line in enumerate(f, 1):
                line = line.strip()
                if not line: continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as e:
                    issues.err(f'line {ln}: parse error: {e}')
                    continue
                n += 1
                missing = REQUIRED_BASE - rec.keys()
                if missing:
                    issues.err(f'line {ln}: missing {missing}')
                    continue
                if not rec.get('content', '').strip():
                    issues.err(f'line {ln}: empty content')
                rid = rec['id']
                if rid in seen_ids:
                    dups += 1
                    if dups <= 3:
                        issues.err(f'line {ln}: duplicate id {rid}')
                seen_ids.add(rid)
                by_source[rec.get('source', '?')] += 1
                by_category[rec.get('category', '')] += 1
    except UnicodeDecodeError as e:
        issues.err(f'UTF-8 decode error: {e}')
    if dups > 3:
        issues.err(f'... {dups - 3} more duplicate ids')
    stats = {
        'records': n,
        'unique_sources': len(by_source),
        'top_sources': dict(by_source.most_common(5)),
        'by_category': dict(by_category),
    }
    return issues, stats


def main() -> None:
    print("=" * 60)
    print("CLASSICAL-CORPUS VALIDATION (L1 + L2)")
    print("=" * 60)
    print()

    total_errors = 0
    total_warnings = 0
    total_records = 0
    total_chars = 0

    # JSON files (corpus + per-source)
    print("--- JSON files ---")
    json_files = sorted(OUT.rglob("*.json"))
    for path in json_files:
        if path.name in {"stats.json", "box_recovery.json"}:
            continue
        issues, stats = validate_json_file(path)
        rel = path.relative_to(REPO_ROOT)
        if "n" in stats and stats.get("records"):
            line = (
                f"{rel}: {stats['records']:>5d} recs, "
                f"len[{stats['min']}|{stats['median']}|{stats['max']}]"
            )
            print(f"  {line}")
            total_records += stats["records"]
            total_chars += stats.get("total_chars", 0)
        if issues.errors or issues.warnings:
            issues.report(str(rel))
        total_errors += len(issues.errors)
        total_warnings += len(issues.warnings)

    # JSONL files: corpus.jsonl is plain records, instruct/*.jsonl is task-formatted
    print()
    print("--- JSONL files ---")
    jsonl_files = sorted(OUT.rglob("*.jsonl"))
    for path in jsonl_files:
        is_instruct = "instruct" in path.parts
        issues, stats = (validate_jsonl_file(path) if is_instruct
                          else validate_jsonl_corpus(path))
        rel = path.relative_to(REPO_ROOT)
        if stats.get("records"):
            print(f"  {rel}: {stats['records']:,} recs")
            if 'by_task' in stats:
                print(f"    by_task: {stats['by_task']}")
            elif 'top_sources' in stats:
                print(f"    unique sources: {stats['unique_sources']}, top 5: {stats['top_sources']}")
            print(f"    by_category: {stats['by_category']}")
            if 'input_median' in stats:
                print(
                    f"    input  p10|med|p90: {stats['input_p10']}|"
                    f"{stats['input_median']}|{stats['input_p90']}"
                )
                print(
                    f"    output p10|med|p90: {stats['output_p10']}|"
                    f"{stats['output_median']}|{stats['output_p90']}"
                )
            total_records += stats["records"]
        if issues.errors or issues.warnings:
            issues.report(str(rel))
        total_errors += len(issues.errors)
        total_warnings += len(issues.warnings)

    print()
    print("=" * 60)
    print(f"TOTAL: {total_records:,} records, {total_chars:,} chars (corpus only)")
    print(f"  errors:   {total_errors}")
    print(f"  warnings: {total_warnings}")
    print("=" * 60)

    if total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
