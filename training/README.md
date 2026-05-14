# QLoRA fine-tune: Qwen2.5-7B-Instruct → classical Chinese

Goal: lift Qwen2.5-7B-Instruct above its baseline score on
[chinese-classical-bench](../../chinese-classical-bench/leaderboard.md) by
QLoRA-tuning on the ~1.97M-record instruction corpus produced from this repo's
`output/instruct/`.

The current public leaderboard puts `Qwen3.5-35B-A3B` (a much bigger model) at
**0.407 avg**. The base 7B has not yet been benchmarked here but is expected
around 0.30–0.36 — we want to see whether a domain QLoRA on ~100K classical
records can close enough of that gap to justify a full-corpus Stage-2 run.

**This is a two-stage plan. Stage 1 is the POC and is what you launch first.**

## Hardware

- **g6e.xlarge** (1× L40S, 48 GB VRAM, 32 GB system RAM) — the same instance
  the user already has provisioned via `xs-llm-infra/scripts/vllm-control.sh`.
- CUDA 12.x, Python 3.11.
- ~80 GB disk for HF cache + checkpoints + merged FP16.

QLoRA was chosen over full FT because 7B-FP16 finetune needs ~110 GB VRAM
(weights + grads + Adam moments) — would force multi-GPU or DeepSpeed
ZeRO-3 offload. NF4 + LoRA fits in ~22 GB and trains 4–5× faster per step.

## Cost estimate

| Stage | Records | Steps | Wall-clock | Spot $/hr | Total $ |
|------:|--------:|------:|-----------:|----------:|--------:|
| **POC (Stage 1)** | 100K | ~6.25K | 6–12 h | ~$1.86 (g6e.xl) | **$15–25** |
| **Full (Stage 2)** | 1.97M | ~123K (1 epoch) | 5–9 days | ~$1.86 | **$220–400** |
| Eval (each) | 600 q | — | 10–20 min | — | <$1 |

Full FT would have been ~$500–1000 even on bigger instances — QLoRA is the
right size-of-effort for a "does this work at all" question.

## File layout

```
training/
├── README.md                # this file
├── requirements.txt         # pinned deps; install on the GPU box
├── qlora_config.yaml        # ALL hyperparameters live here
├── data_prep.py             # corpus → 100K ChatML JSONL (stratified sample)
├── train.py                 # TRL SFTTrainer driver
├── merge_and_export.py      # LoRA → merged FP16 (+ optional GGUF)
├── eval_bench.py            # spin vLLM + run chinese-classical-bench
└── data/
    ├── train.jsonl          # produced by data_prep.py
    └── val.jsonl            # produced by data_prep.py
```

## Stage 1 — POC (100K, 6–12 h)

Run these in order. All commands assume `cwd = /Users/zion/Documents/zion/classical-corpus`
on the GPU box (or sshfs-mounted from your Mac).

### 0. One-time install on the GPU box

```bash
cd /Users/zion/Documents/zion/classical-corpus
python -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r training/requirements.txt
# optional, only on Ada/L40S/H100; train.py auto-fallbacks if it can't build:
pip install flash-attn==2.7.4.post1 --no-build-isolation
```

### 1. Build the training data (~3 min, runs on Mac OR GPU box)

```bash
cd /Users/zion/Documents/zion/classical-corpus
python training/data_prep.py --n 100000 --n-val 1000 --seed 42
# → training/data/train.jsonl  (~100K lines, ~250 MB)
# → training/data/val.jsonl    (~1K lines)
```

Smoke-test first if you want to be safe:
```bash
python training/data_prep.py --dry-run --n 200 --max-scan 50000
```

### 2. Baseline eval (BEFORE fine-tuning) — establishes the comparison point

```bash
# On the GPU box, with vLLM already serving Qwen2.5-7B-Instruct base
# (use xs-llm-infra/scripts/vllm-control.sh start, then point it at the base model)
python training/eval_bench.py --no-start-vllm \
    --model Qwen/Qwen2.5-7B-Instruct \
    --base-url http://localhost:8000/v1 \
    --bench-repo /Users/zion/Documents/zion/chinese-classical-bench \
    --out /Users/zion/Documents/zion/chinese-classical-bench/results/Qwen_Qwen2.5-7B-Instruct.json
```

Keep that JSON — `eval_bench.py` diffs against it later.

### 3. Train (6–12 h on g6e.xlarge)

```bash
cd /Users/zion/Documents/zion/classical-corpus
source .venv/bin/activate
nohup python training/train.py \
    --config training/qlora_config.yaml \
    > training/runs/train.log 2>&1 &
tail -f training/runs/train.log
```

Monitor:
- `nvidia-smi -l 5` — expect ~20–24 GB VRAM, 80–95% util on L40S
- `tensorboard --logdir training/runs/qwen25-7b-classical-qlora`
- eval loss should drop within the first 1–2K steps; train loss should
  smooth out around 0.7–1.0 (lower for c2m than punctuate)

### 4. Merge LoRA → FP16 (~5 min, CPU-bound on the GPU box)

```bash
python training/merge_and_export.py \
    --adapter training/runs/qwen25-7b-classical-qlora/final-adapter \
    --out     training/exports/qwen25-7b-classical-merged
```

### 5. Eval the fine-tuned model

```bash
python training/eval_bench.py \
    --merged training/exports/qwen25-7b-classical-merged \
    --model  qwen25-7b-classical-poc \
    --bench-repo /Users/zion/Documents/zion/chinese-classical-bench \
    --baseline   /Users/zion/Documents/zion/chinese-classical-bench/results/Qwen_Qwen2.5-7B-Instruct.json
```

This script spawns `vllm serve …`, waits until `/v1/models` returns, runs
`eval_runner.py` against it for all 6 tasks, then prints a before/after diff
and shuts vLLM down. Total ~15–25 min.

## Decision gate (POC → Full)

> **Go for Stage 2 only if `avg(after) − avg(before) ≥ +0.03`** AND the tuned
> model regresses by no more than −0.02 on any individual task.

Reasoning: 0.03 is roughly the run-to-run noise floor we observed across
prior bench submissions; less than that and we can't tell signal from noise.
A regression cap protects against catastrophic forgetting of e.g. `compress`
or `idiom-source`, which depend on capabilities the SFT corpus doesn't
exercise.

If the POC hits the gate, scale to Stage 2 by editing `qlora_config.yaml`:
- `data.train_file: training/data/train_full.jsonl` (rebuild with `--n 1900000`)
- `training.save_steps: 5000`
- `training.num_train_epochs: 1` (still — 1 epoch over 1.9M ≈ 123K steps)
- consider `data.packing: true` for a ~30% wall-clock save

If the POC fails the gate, **do not just train longer**. Diagnose first:
1. Inspect failing task items in the eval JSON for systematic errors.
2. Check if filtering biased the sample (e.g., did the 50–500 char cap
   strip all short `punctuate` records?).
3. Try raising LoRA `r` from 16 → 32, or unfreezing the embedding layer
   (`modules_to_save: [embed_tokens, lm_head]`) if classical-only chars
   (Ext-B/C/D) are dragging down `fill-in`.

## Known unknowns (read before launching)

1. **Tokenizer coverage of rare CJK Ext-B/C/D**. Qwen2.5's tokenizer is
   Chinese-strong but we haven't audited it against the rare characters in
   the corpus. If `fill-in` doesn't move (or regresses), the bottleneck is
   probably at the embedding layer, not LoRA. Quick check:
   ```python
   from transformers import AutoTokenizer
   t = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
   for ch in "𠡠𡈽⿰":
       print(ch, t.encode(ch))   # multi-token = bad sign
   ```
2. **Catastrophic forgetting on `compress` / `idiom-source`**. Our SFT data
   is c2m / m2c / punctuate only. The model may lose generation diversity
   on idiom recall. The regression cap in the decision gate is the safety
   net; if breached, mix 10% general-purpose data into the next run.
3. **Punctuate label distribution**. Punctuate is only 4.9 万 (2.4% of the
   pool), so stratified sampling will give it ~2.5K records out of 100K.
   That may be too thin to move the `punctuate` task score. Watch for it.
4. **vLLM version drift**. `requirements.txt` pins vLLM 0.6.4 because that's
   the last release verified with `transformers==4.46`. If you bump one,
   bump both.
5. **L40S vs xs-llm-infra current setup**. xs-llm-infra runs `Qwen3.5-35B-A3B-AWQ`
   in a vLLM container at all times — training requires that container be
   STOPPED first (`vllm-control.sh stop`) to free the GPU.

## Rollback plan

Everything is additive — base model + adapter, then a merged dir.

- **Bad checkpoint?** Delete `training/exports/qwen25-7b-classical-merged/`,
  re-run `merge_and_export.py` against an earlier `checkpoint-N/` dir under
  `training/runs/qwen25-7b-classical-qlora/`.
- **Bad training data?** Just rerun `data_prep.py` with a new `--seed`; the
  previous `train.jsonl` is harmless on its own.
- **Want to go back to base?** Point vLLM at `Qwen/Qwen2.5-7B-Instruct`
  again; nothing in the base HF cache was modified.
- **Storage cleanup**: `training/runs/` holds checkpoints (3 × ~600 MB
  adapter + optimiser ≈ 2 GB) and `training/exports/` holds the merged
  FP16 (~14 GB). Both are safe to delete after pushing the adapter to HF.
