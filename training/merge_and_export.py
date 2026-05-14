#!/usr/bin/env python3
"""Merge the trained LoRA adapter into the base Qwen2.5-7B-Instruct weights,
save a full FP16 (or BF16) checkpoint suitable for vLLM serving.

Optionally also export a GGUF (Q4_K_M) for llama.cpp by calling out to a
locally-cloned llama.cpp's `convert_hf_to_gguf.py`. If llama.cpp is missing,
the GGUF step is skipped with a clear log line (it is not required for the
vLLM eval flow).

Usage:
  python training/merge_and_export.py \\
      --adapter training/runs/qwen25-7b-classical-qlora/final-adapter \\
      --out training/exports/qwen25-7b-classical-merged

  # also produce GGUF (needs ~/llama.cpp checked out)
  python training/merge_and_export.py --adapter ... --out ... --gguf \\
      --llamacpp ~/llama.cpp --gguf-quant q4_k_m
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def fatal(msg: str, code: int = 1):
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(code)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", type=Path, required=True,
                    help="dir containing adapter_config.json + adapter weights")
    ap.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--out", type=Path, required=True,
                    help="output dir for merged FP16 weights")
    ap.add_argument("--dtype", type=str, default="bfloat16",
                    choices=("bfloat16", "float16"))
    ap.add_argument("--gguf", action="store_true",
                    help="also export a GGUF via llama.cpp")
    ap.add_argument("--llamacpp", type=Path, default=Path.home() / "llama.cpp",
                    help="path to llama.cpp checkout (for GGUF export)")
    ap.add_argument("--gguf-quant", default="q4_k_m",
                    help="GGUF quantisation (e.g. q4_k_m, q5_k_m, q8_0)")
    args = ap.parse_args()

    if not args.adapter.exists():
        fatal(f"adapter dir not found: {args.adapter}")
    if not (args.adapter / "adapter_config.json").exists():
        fatal(f"adapter_config.json missing under: {args.adapter}")

    # Lazy imports
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
    except ImportError as e:
        fatal(f"missing dependency ({e}); see training/requirements.txt")

    dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float16

    print(f"[merge] loading base: {args.base_model}  dtype={args.dtype}")
    base = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=dtype,
        trust_remote_code=True,
        device_map="cpu",          # merge on CPU to avoid VRAM blowup
        low_cpu_mem_usage=True,
    )

    print(f"[merge] applying adapter: {args.adapter}")
    merged = PeftModel.from_pretrained(base, str(args.adapter))
    merged = merged.merge_and_unload()

    args.out.mkdir(parents=True, exist_ok=True)
    print(f"[merge] saving merged model → {args.out}")
    merged.save_pretrained(str(args.out), safe_serialization=True)

    # tokenizer
    try:
        tok = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
        tok.save_pretrained(str(args.out))
    except Exception as e:
        print(f"[warn] tokenizer save failed ({e}); copying from adapter dir if any")
        for f in ("tokenizer.json", "tokenizer_config.json",
                  "special_tokens_map.json", "vocab.json", "merges.txt"):
            src = args.adapter / f
            if src.exists():
                shutil.copy2(src, args.out / f)

    print(f"[merge] done; serve with: vllm serve {args.out} --tensor-parallel-size 1")

    if args.gguf:
        cvt = args.llamacpp / "convert_hf_to_gguf.py"
        if not cvt.exists():
            print(f"[skip] GGUF: {cvt} not found — clone https://github.com/ggerganov/llama.cpp "
                  f"and retry, or omit --gguf")
            return 0
        gguf_f16 = args.out.parent / f"{args.out.name}.f16.gguf"
        gguf_q = args.out.parent / f"{args.out.name}.{args.gguf_quant}.gguf"
        print(f"[gguf] convert HF → {gguf_f16}")
        try:
            subprocess.run(
                [sys.executable, str(cvt), str(args.out),
                 "--outfile", str(gguf_f16), "--outtype", "f16"],
                check=True,
            )
            quantize = args.llamacpp / "build" / "bin" / "llama-quantize"
            if quantize.exists():
                print(f"[gguf] quantize → {gguf_q}")
                subprocess.run(
                    [str(quantize), str(gguf_f16), str(gguf_q), args.gguf_quant],
                    check=True,
                )
            else:
                print(f"[warn] llama-quantize not found at {quantize}; "
                      f"GGUF f16 kept, quant skipped")
        except subprocess.CalledProcessError as e:
            print(f"[error] GGUF export failed: {e}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
