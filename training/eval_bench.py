#!/usr/bin/env python3
"""Serve the merged QLoRA model on a local vLLM endpoint, then run
chinese-classical-bench/scripts/eval_runner.py against it.

Two modes:

  --start-vllm           (default) launch `vllm serve` as a subprocess, wait
                         for /v1/models to respond, run eval, then shut it down.
  --no-start-vllm        assume the user already has vLLM running at --base-url
                         (e.g., on g6e.xlarge via xs-llm-infra) and just run
                         the eval script against it.

After the run, prints a before/after diff against an optional baseline JSON.

Examples:
  # End-to-end: spin vLLM, eval, compare with baseline
  python training/eval_bench.py \\
      --merged training/exports/qwen25-7b-classical-merged \\
      --bench-repo ~/Documents/zion/chinese-classical-bench \\
      --baseline ~/Documents/zion/chinese-classical-bench/results/Qwen_Qwen2.5-7B-Instruct.json

  # Eval-only (vLLM already running on http://localhost:8000)
  python training/eval_bench.py --no-start-vllm \\
      --model qwen25-7b-classical \\
      --base-url http://localhost:8000/v1 \\
      --bench-repo ~/Documents/zion/chinese-classical-bench
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def fatal(msg: str, code: int = 1):
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(code)


def wait_for_vllm(base_url: str, timeout: int = 600) -> None:
    """Poll /v1/models until 200, or fatal after timeout seconds."""
    url = base_url.rstrip("/") + "/models"
    t0 = time.time()
    last_err: str | None = None
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    print(f"[vllm] ready after {time.time() - t0:.0f}s")
                    return
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last_err = str(e)
        time.sleep(3)
    fatal(f"vLLM didn't come up within {timeout}s — last error: {last_err}")


def launch_vllm(merged_dir: Path, served_name: str, port: int, log_path: Path):
    """Spawn `vllm serve` in the background, return Popen."""
    if not merged_dir.exists():
        fatal(f"merged model dir not found: {merged_dir}")
    cmd = [
        "vllm", "serve", str(merged_dir),
        "--served-model-name", served_name,
        "--host", "0.0.0.0",
        "--port", str(port),
        "--dtype", "bfloat16",
        "--max-model-len", "8192",
        # L40S = 48GB, leave headroom for KV cache; 0.85 is conservative.
        "--gpu-memory-utilization", "0.85",
        "--trust-remote-code",
    ]
    print(f"[vllm] launching: {' '.join(cmd)}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    f = log_path.open("w")
    proc = subprocess.Popen(
        cmd,
        stdout=f, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return proc, f


def stop_vllm(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    print("[vllm] stopping…")
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("[vllm] stopped")


def run_eval(bench_repo: Path, model: str, base_url: str, api_key: str,
             tasks: list[str] | None, out_path: Path, concurrency: int,
             limit: int | None) -> int:
    """Invoke chinese-classical-bench/scripts/eval_runner.py via subprocess."""
    runner = bench_repo / "scripts" / "eval_runner.py"
    if not runner.exists():
        fatal(f"eval runner missing: {runner}")
    cmd = [
        sys.executable, str(runner),
        "--model", model,
        "--base-url", base_url,
        "--api-key", api_key,
        "--concurrency", str(concurrency),
        "--out", str(out_path),
    ]
    if tasks:
        cmd += ["--tasks", *tasks]
    if limit:
        cmd += ["--limit", str(limit)]
    print(f"[eval] {' '.join(cmd)}")
    rc = subprocess.call(cmd, cwd=str(bench_repo))
    return rc


def load_summary(path: Path) -> dict[str, dict[str, float]]:
    """Extract per-task summary dicts from an eval_runner.py JSON result file."""
    if not path.exists():
        return {}
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, dict[str, float]] = {}
    for task, res in (blob.get("tasks") or {}).items():
        out[task] = (res or {}).get("summary") or {}
    return out


def print_diff(after: dict, before: dict | None) -> None:
    print("\n=== eval summary ===")
    all_tasks = sorted(set(after) | set(before or {}))
    for task in all_tasks:
        a = after.get(task, {})
        b = (before or {}).get(task, {})
        keys = sorted(set(a) | set(b))
        print(f"  {task}")
        for k in keys:
            av = a.get(k)
            bv = b.get(k)
            if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
                delta = av - bv
                marker = "↑" if delta > 0 else ("↓" if delta < 0 else "·")
                print(f"    {k:<18} {bv:7.4f} → {av:7.4f}  ({delta:+.4f} {marker})")
            else:
                print(f"    {k:<18} before={bv}  after={av}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", type=Path, default=None,
                    help="merged HF model dir (required if --start-vllm)")
    ap.add_argument("--model", type=str, default="qwen25-7b-classical",
                    help="model id sent to /v1/chat/completions")
    ap.add_argument("--bench-repo", type=Path, required=True,
                    help="path to chinese-classical-bench repo")
    ap.add_argument("--base-url", type=str, default="http://localhost:8000/v1")
    ap.add_argument("--api-key", type=str, default="EMPTY")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--start-vllm", dest="start_vllm", action="store_true",
                    default=True)
    ap.add_argument("--no-start-vllm", dest="start_vllm", action="store_false")
    ap.add_argument("--tasks", nargs="*", default=None,
                    help="subset of tasks (default: all 6)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out", type=Path, default=None,
                    help="result json (default: bench_repo/results/{model}.json)")
    ap.add_argument("--baseline", type=Path, default=None,
                    help="baseline eval JSON to diff against")
    args = ap.parse_args()

    bench_repo = args.bench_repo.expanduser().resolve()
    if not bench_repo.exists():
        fatal(f"bench repo not found: {bench_repo}")

    out_path = args.out or (bench_repo / "results" / f"{args.model}.json")

    proc, log_f = None, None
    try:
        if args.start_vllm:
            if not args.merged:
                fatal("--merged is required unless --no-start-vllm is set")
            log_path = REPO_ROOT / "training" / "runs" / "vllm.log"
            proc, log_f = launch_vllm(args.merged, args.model, args.port, log_path)
            wait_for_vllm(args.base_url, timeout=600)

        rc = run_eval(
            bench_repo=bench_repo,
            model=args.model,
            base_url=args.base_url,
            api_key=args.api_key,
            tasks=args.tasks,
            out_path=out_path,
            concurrency=args.concurrency,
            limit=args.limit,
        )
        if rc != 0:
            print(f"[error] eval_runner exited with rc={rc}", file=sys.stderr)
            return rc

        after = load_summary(out_path)
        before = load_summary(args.baseline) if args.baseline else None
        print_diff(after, before)
        print(f"\n[done] result → {out_path}")
        return 0
    finally:
        if proc is not None:
            with contextlib.suppress(Exception):
                stop_vllm(proc)
        if log_f is not None:
            with contextlib.suppress(Exception):
                log_f.close()


if __name__ == "__main__":
    sys.exit(main())
