"""Scrape the 4 missing 南史 volumes (2, 7, 68, 74) from zh.wikisource.org
and merge them into output/histories/nanshi.json.

Usage: python scripts/scrape_nanshi_missing.py
"""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TARGET = REPO / "output" / "histories" / "nanshi.json"

# vol → (chapter cn, section)
MISSING = {
    2:  ("卷二",   "本纪"),
    7:  ("卷七",   "本纪"),
    68: ("卷六十八", "列传"),
    74: ("卷七十四", "列传"),
}

USER_AGENT = "chinese-classical-corpus/1.x (https://github.com/gujilab/chinese-classical-corpus)"


def fetch_raw(vol: int) -> str:
    title = urllib.parse.quote(f"南史/卷{vol:02d}", safe="")
    url = f"https://zh.wikisource.org/w/index.php?title={title}&action=raw"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def _strip_templates(s: str) -> str:
    """Remove every {{...}} template using balanced-brace matching, except
    keep {{YL|X}} → X (it wraps a year label we want to keep). Handles
    nested braces correctly (wikitext templates can contain other templates)."""
    out = []
    i = 0
    while i < len(s):
        if s[i:i+2] == "{{":
            # find matching }} accounting for nesting
            depth = 1
            j = i + 2
            while j < len(s) and depth > 0:
                if s[j:j+2] == "{{":
                    depth += 1; j += 2
                elif s[j:j+2] == "}}":
                    depth -= 1; j += 2
                else:
                    j += 1
            inner = s[i+2:j-2] if depth == 0 else s[i+2:]
            # Special-case: keep YL value
            if inner.startswith("YL|"):
                out.append(inner[3:])
            i = j
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def clean_wikitext(raw: str) -> str:
    """Strip all wiki/HTML markup from a wikisource raw page, return plain
    text body suitable for sentence splitting + t2s conversion."""
    body = raw
    # Cut off after the footer/license/categories (these are at the bottom)
    body = re.split(r"\{\{footer\b", body, maxsplit=1)[0]
    body = re.split(r"\[\[Category:", body)[0]
    # Strip all {{...}} templates (with balanced braces), preserving {{YL|X}}
    body = _strip_templates(body)
    # ==Section== markdown → plain section name on its own line
    body = re.sub(r"^==+\s*(.+?)\s*==+\s*$", r"\1", body, flags=re.MULTILINE)
    # Wiki links [[a|b]] → b, [[a]] → a
    body = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", body)
    body = re.sub(r"\[\[([^\]]+)\]\]", r"\1", body)
    # HTML comments + <ref>...</ref> + other tags
    body = re.sub(r"<!--[\s\S]*?-->", "", body)
    body = re.sub(r"<ref[\s\S]*?</ref>", "", body)
    body = re.sub(r"<[^>]+>", "", body)
    # Drop full-width / regular leading whitespace per line
    body = re.sub(r"^[　 \t]+", "", body, flags=re.MULTILINE)
    # Collapse > 2 blank lines
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def split_sentences(text: str) -> list[str]:
    """Mirror the project's convention: one sentence per line, split on 。！？."""
    # Keep the section/paragraph structure intact: split on terminators but
    # preserve them. Then drop pure-empty lines.
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # split keeping punctuation
        parts = re.split(r"(?<=[。！？])", line)
        for p in parts:
            p = p.strip()
            if p:
                out.append(p)
    return out


def to_simplified(s: str) -> str:
    from opencc import OpenCC
    cc = OpenCC("t2s")
    return cc.convert(s)


def build_record(vol: int, chapter: str, section: str, body: str, idx: int) -> dict:
    sents = split_sentences(body)
    content = "\n".join(sents)
    return {
        "id": f"nanshi#{idx}",
        "source": "南史",
        "author": "李延寿",
        "era": "唐",
        "category": "史",
        "volume": vol,
        "volume_suffix": "",
        "section": section,
        "chapter": chapter,
        "content": content,
        "_source": "wikisource",
    }


def main() -> int:
    existing = json.loads(TARGET.read_text(encoding="utf-8"))
    have = {r["volume"] for r in existing}
    missing = [v for v in MISSING if v not in have]
    if not missing:
        print("nothing to scrape — all 80 vols present")
        return 0
    print(f"scraping vols: {missing}")
    # next id
    next_id = 1 + max(int(r["id"].rsplit("#", 1)[1]) for r in existing)
    new_records = []
    for vol in missing:
        chapter, section = MISSING[vol]
        print(f"  fetching 南史/卷{vol:02d} ...")
        raw = fetch_raw(vol)
        body_trad = clean_wikitext(raw)
        body_simp = to_simplified(body_trad)
        rec = build_record(vol, chapter, section, body_simp, next_id)
        next_id += 1
        # sanity: at least 1000 chars
        if len(rec["content"]) < 1000:
            print(f"  WARN: vol {vol} extracted only {len(rec['content'])} chars; skipping write")
            print(f"  preview: {rec['content'][:200]!r}")
            continue
        new_records.append(rec)
        print(f"    ok — {len(rec['content']):,} chars, {rec['content'].count(chr(10))+1} lines")
        time.sleep(1)  # polite delay
    if not new_records:
        print("no records produced")
        return 1
    merged = existing + new_records
    # sort by volume for stability (matches project convention loosely)
    merged.sort(key=lambda r: (r["volume"], r["id"]))
    TARGET.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {len(new_records)} new records. nanshi.json now has {len(merged)} records "
          f"across {len({r['volume'] for r in merged})} volumes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
