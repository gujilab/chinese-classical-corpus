#!/usr/bin/env python3
"""Sample + format instruction data for QLoRA fine-tuning of Qwen2.5-7B-Instruct.

Reads:
  output/instruct/translate.jsonl  (1 924 378 lines)
  output/instruct/punctuate.jsonl  (   46 546 lines)

Stratified sample across (category × task), with filters:
  - input  length in [50, 500] chars
  - output length in [50, 500] chars  (punctuate target uses unicode chars)
  - drop records where _has_box == true

Writes:
  training/data/train.jsonl  (N records, default 100 000)
  training/data/val.jsonl    (default 1 000, held-out from same dist)

Each output line is a single JSON object with one field:
  {"text": "<|im_start|>system\\n...<|im_end|>\\n<|im_start|>user\\n...<|im_end|>\\n<|im_start|>assistant\\n...<|im_end|>"}

This matches Qwen2.5's chat template exactly, so SFTTrainer can use packing=false
and treat each line as a complete training example.

Usage:
  python training/data_prep.py                       # full run: 100K train + 1K val
  python training/data_prep.py --n 50000             # 50K POC
  python training/data_prep.py --dry-run --n 100     # smoke test, no writes
  python training/data_prep.py --seed 7              # different sample
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]               # …/classical-corpus
INSTRUCT_DIR = REPO_ROOT / "output" / "instruct"
TRANSLATE_FILE = INSTRUCT_DIR / "translate.jsonl"
PUNCTUATE_FILE = INSTRUCT_DIR / "punctuate.jsonl"

OUT_DIR = REPO_ROOT / "training" / "data"

# ---------------------------------------------------------------------------
# Chat template — exact match of Qwen2.5 ChatML
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = "You are a helpful assistant skilled in classical Chinese."

CHATML_TEMPLATE = (
    "<|im_start|>system\n{system}<|im_end|>\n"
    "<|im_start|>user\n{user}<|im_end|>\n"
    "<|im_start|>assistant\n{assistant}<|im_end|>"
)

# Filters
MIN_LEN, MAX_LEN = 50, 500
CATEGORIES = ("经", "史", "子", "集")
TASKS = ("c2m", "m2c", "punctuate")


# ---------------------------------------------------------------------------
def iter_jsonl(path: Path) -> Iterator[dict]:
    """Yield parsed JSON dicts from a JSONL file. Skips malformed lines."""
    if not path.exists():
        print(f"[ERROR] file not found: {path}", file=sys.stderr)
        return
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] {path.name}:{ln} skip — {e}", file=sys.stderr)


def valid(rec: dict) -> bool:
    """Filter rule."""
    if rec.get("_has_box", False):
        return False
    inp, out = rec.get("input", ""), rec.get("output", "")
    if not isinstance(inp, str) or not isinstance(out, str):
        return False
    if not (MIN_LEN <= len(inp) <= MAX_LEN):
        return False
    if not (MIN_LEN <= len(out) <= MAX_LEN):
        return False
    if not rec.get("instruction"):
        return False
    return True


def stratum_key(rec: dict) -> tuple[str, str]:
    cat = rec.get("category") or "?"
    task = rec.get("task") or "?"
    return (cat, task)


# ---------------------------------------------------------------------------
def collect_pool(dry_run: bool, max_scan: int | None) -> list[dict]:
    """Stream both files, keep only valid records. Returns the full eligible pool."""
    pool: list[dict] = []
    cnt: Counter = Counter()

    sources = [TRANSLATE_FILE, PUNCTUATE_FILE]
    for src in sources:
        n_seen, n_kept = 0, 0
        for rec in iter_jsonl(src):
            n_seen += 1
            if max_scan is not None and n_seen > max_scan:
                break
            if valid(rec):
                pool.append(rec)
                cnt[stratum_key(rec)] += 1
                n_kept += 1
            if dry_run and n_kept >= 200:
                break
        print(f"  {src.name}: scanned {n_seen}, kept {n_kept}")
        if dry_run and len(pool) >= 200:
            break

    print(f"[pool] total kept = {len(pool):,}")
    print(f"[pool] strata (category, task):")
    for k, v in sorted(cnt.items()):
        print(f"    {k}: {v:,}")
    return pool


def stratified_sample(pool: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Sample n records, proportional to stratum size but with a min floor per stratum."""
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in pool:
        buckets[stratum_key(r)].append(r)

    if not buckets:
        return []

    total = sum(len(v) for v in buckets.values())
    if n >= total:
        rng.shuffle(pool)
        return pool[:]

    # Proportional allocation with a small floor so rare strata are not crushed.
    min_per_stratum = min(50, n // (2 * len(buckets)))
    alloc: dict[tuple[str, str], int] = {}
    leftover = n
    for k, items in buckets.items():
        share = max(min_per_stratum, round(n * len(items) / total))
        share = min(share, len(items))
        alloc[k] = share
        leftover -= share

    # Distribute / claw back to land on exactly n.
    keys = list(buckets.keys())
    while leftover != 0 and keys:
        for k in list(keys):
            if leftover > 0 and alloc[k] < len(buckets[k]):
                alloc[k] += 1
                leftover -= 1
            elif leftover < 0 and alloc[k] > 1:
                alloc[k] -= 1
                leftover += 1
            if leftover == 0:
                break

    out: list[dict] = []
    for k, items in buckets.items():
        rng.shuffle(items)
        out.extend(items[: alloc[k]])
    rng.shuffle(out)
    return out


def to_chatml(rec: dict) -> str:
    instr = rec["instruction"].strip()
    inp = rec["input"].strip()
    out = rec["output"].strip()
    # Some instruction strings already end with a colon and expect inline input;
    # we put them on separate lines for clarity — Qwen2.5 handles both equivalently.
    user = f"{instr}\n{inp}"
    return CHATML_TEMPLATE.format(system=SYSTEM_PROMPT, user=user, assistant=out)


def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            text = to_chatml(r)
            f.write(json.dumps({"text": text}, ensure_ascii=False))
            f.write("\n")
    print(f"  wrote {len(records):,} records → {path}")


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100_000, help="train size")
    ap.add_argument("--n-val", type=int, default=1_000, help="val size (held out)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true",
                    help="don't write files; smoke-test the pipeline")
    ap.add_argument("--max-scan", type=int, default=None,
                    help="cap records read per source file (debug)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    # Verify inputs first so the user gets a clear error before scanning.
    missing = [p for p in (TRANSLATE_FILE, PUNCTUATE_FILE) if not p.exists()]
    if missing:
        for p in missing:
            print(f"[FATAL] missing input file: {p}", file=sys.stderr)
        return 1

    rng = random.Random(args.seed)

    print(f"[step 1/3] collecting eligible records (dry_run={args.dry_run})")
    pool = collect_pool(dry_run=args.dry_run, max_scan=args.max_scan)
    if not pool:
        print("[FATAL] empty pool after filtering", file=sys.stderr)
        return 1

    n_train = min(args.n, max(1, len(pool) - args.n_val))
    n_val = min(args.n_val, len(pool) - n_train)
    print(f"[step 2/3] stratified sampling: train={n_train:,} val={n_val:,}")

    rng.shuffle(pool)
    val_records = pool[:n_val]
    rest = pool[n_val:]
    train_records = stratified_sample(rest, n_train, rng)

    print(f"[step 3/3] writing")
    if args.dry_run:
        print(f"  [dry-run] would write {len(train_records)} train + {len(val_records)} val")
        # Render one sample so the user can sanity-check the chat template
        print("\n--- example ChatML record ---")
        print(to_chatml(train_records[0])[:1200])
        print("--- end ---")
        return 0

    write_jsonl(train_records, args.out_dir / "train.jsonl")
    write_jsonl(val_records, args.out_dir / "val.jsonl")
    print("[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
