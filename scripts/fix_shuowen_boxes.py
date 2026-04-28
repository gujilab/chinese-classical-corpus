"""Fix 说文 □ chars by cross-referencing shuowenjiezi/shuowen GitHub repo.

殆知阁's 说文 has 2102 字头 as □ (CJK Extension B-G chars unrenderable in source).
shuowenjiezi/shuowen has each char in its own JSON with proper Unicode.

Strategy:
  1. Build lookup (fanqie + radical) → wordhead from shuowenjiezi
  2. For each □ entry, try matching:
     a. Unique by (fanqie, radical) — covers ~82%
     b. Disambiguate by explanation prefix (繁→简 first) — covers another ~7%
  3. Leave remaining ~10% unfixable, document
"""

import json
import re
from collections import defaultdict
from pathlib import Path
from opencc import OpenCC

REPO_ROOT = Path(__file__).resolve().parents[1]
SHUOWEN_DATA_DIR = (
    Path.home() / "Documents/zion/reference/Chinese/classical/corpora/shuowen/data"
)
TARGET = REPO_ROOT / "output" / "shuowen.json"

T2S = OpenCC("t2s")


def build_shuowen_lookup() -> tuple[dict, dict]:
    """Returns (lookup_2tuple, lookup_3tuple).
    2-tuple key: (fanqie, radical) → list of wordheads
    3-tuple key: (fanqie, radical, explanation_simp_prefix) → list of wordheads
    """
    lookup_2 = defaultdict(list)
    lookup_3 = defaultdict(list)
    for f in sorted(SHUOWEN_DATA_DIR.glob("*.json")):
        try:
            d = json.load(f.open(encoding="utf-8"))
        except Exception:
            continue
        wordhead = d.get("wordhead", "")
        radical = d.get("radical", "")
        pronunciation = d.get("pronunciation", "")
        explanation = d.get("explanation", "") or ""
        if not (wordhead and wordhead != "□" and pronunciation):
            continue
        # primary: (fanqie, radical)
        lookup_2[(pronunciation, radical)].append(wordhead)
        # secondary: + simplified explanation prefix (8 chars)
        expl_simp = T2S.convert(explanation)[:8]
        lookup_3[(pronunciation, radical, expl_simp)].append(wordhead)
    return lookup_2, lookup_3


def fix_entry(entry: dict, lookup_2: dict, lookup_3: dict) -> tuple[bool, str]:
    """Return (fixed, method). Mutates entry in place if fixable."""
    if entry["char"] != "□":
        return False, "not-box"
    fanqie = entry["fanqie"]
    radical = entry["radical"].replace("部", "")
    explanation = (entry.get("content", "") or "")[:8]

    # method 1: unique by (fanqie, radical)
    cands = lookup_2.get((fanqie, radical), [])
    if len(cands) == 1:
        entry["char"] = cands[0]
        return True, "fanqie+radical"

    # method 2: disambiguate using explanation prefix
    cands = lookup_3.get((fanqie, radical, explanation), [])
    if len(cands) == 1:
        entry["char"] = cands[0]
        return True, "fanqie+radical+expl"

    # method 3: ambiguous fanqie+radical, all candidates same wordhead
    cands = list(set(lookup_2.get((fanqie, radical), [])))
    if len(cands) == 1:
        entry["char"] = cands[0]
        return True, "fanqie+radical-dedup"

    return False, "no-match" if not lookup_2.get((fanqie, radical)) else "ambiguous"


def main() -> None:
    print("loading shuowenjiezi/shuowen...")
    lookup_2, lookup_3 = build_shuowen_lookup()
    print(f"  built {len(lookup_2)} (fanqie,radical) keys")

    print("loading my 说文...")
    data = json.load(TARGET.open(encoding="utf-8"))
    print(f"  {len(data)} entries, "
          f"{sum(1 for e in data if e['char']=='□')} are □")

    fixed = 0
    methods = defaultdict(int)
    for e in data:
        was_fixed, method = fix_entry(e, lookup_2, lookup_3)
        methods[method] += 1
        if was_fixed:
            fixed += 1

    remaining_box = sum(1 for e in data if e["char"] == "□")
    print()
    print(f"fixed: {fixed}")
    print(f"remaining □: {remaining_box}")
    print(f"breakdown:")
    for m, n in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"  {m}: {n}")

    with TARGET.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nupdated {TARGET.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
