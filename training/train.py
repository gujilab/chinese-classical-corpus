#!/usr/bin/env python3
"""QLoRA fine-tune Qwen2.5-7B-Instruct on classical Chinese instruction data.

Uses HuggingFace TRL `SFTTrainer` because:
  - Half the boilerplate of writing a Trainer subclass against peft directly
  - Native dataset text-field handling, gradient checkpointing wired up
  - Plays nice with peft + bitsandbytes via `peft_config` arg
  - Lets us swap to packing=true later for Stage-2 with one flag

Read all hyperparameters from training/qlora_config.yaml. The config is the
source of truth; this script is just plumbing.

Launch (single L40S):
  cd /Users/zion/Documents/zion/classical-corpus
  python training/train.py --config training/qlora_config.yaml

If you have an older accelerate setup, you can also do:
  accelerate launch --num_processes 1 training/train.py --config training/qlora_config.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def fatal(msg: str, code: int = 1) -> None:
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(code)


def load_config(path: Path) -> dict:
    if not path.exists():
        fatal(f"config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        fatal("config must be a YAML mapping at top level")
    return cfg


def check_gpu() -> None:
    try:
        import torch
    except ImportError:
        fatal("PyTorch not installed; see training/requirements.txt")
    if not torch.cuda.is_available():
        fatal("no CUDA GPU visible — refusing to start (this would OOM on CPU). "
              "On g6e.xlarge confirm `nvidia-smi` shows the L40S.")
    dev = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"[gpu] {dev}  vram={vram_gb:.1f} GB")


def resolve_path(p: str | None) -> Path | None:
    if not p:
        return None
    pp = Path(p)
    if not pp.is_absolute():
        pp = REPO_ROOT / pp
    return pp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path,
                    default=REPO_ROOT / "training" / "qlora_config.yaml")
    ap.add_argument("--resume", type=str, default=None,
                    help="resume from a checkpoint dir")
    args = ap.parse_args()

    cfg = load_config(args.config)
    check_gpu()

    # Lazy imports so config-only sanity (and --help) don't require the GPU stack.
    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, prepare_model_for_kbit_training
    from trl import SFTTrainer, SFTConfig

    m = cfg["model"]
    q = cfg["quantization"]
    l = cfg["lora"]
    d = cfg["data"]
    t = cfg["training"]
    misc = cfg.get("misc", {})

    # ---------------- tokenizer ----------------
    print(f"[load] tokenizer: {m['name_or_path']}")
    tokenizer = AutoTokenizer.from_pretrained(
        m["name_or_path"],
        trust_remote_code=m.get("trust_remote_code", True),
        use_fast=True,
    )
    if tokenizer.pad_token is None:
        # Qwen2.5 has <|endoftext|>; align pad to it.
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ---------------- quantization config ----------------
    compute_dtype = getattr(torch, q.get("bnb_4bit_compute_dtype", "bfloat16"))
    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=q.get("load_in_4bit", True),
        bnb_4bit_quant_type=q.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=q.get("bnb_4bit_use_double_quant", True),
    )

    # ---------------- model ----------------
    attn_impl = "flash_attention_2" if misc.get("use_flash_attn_2", True) else "sdpa"
    print(f"[load] model: {m['name_or_path']}  attn={attn_impl}")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            m["name_or_path"],
            quantization_config=bnb_cfg,
            torch_dtype=compute_dtype,
            attn_implementation=attn_impl,
            trust_remote_code=m.get("trust_remote_code", False),
            device_map="auto",
        )
    except (ImportError, ValueError, RuntimeError) as e:
        if attn_impl == "flash_attention_2":
            print(f"[warn] flash_attention_2 unavailable ({e}); falling back to sdpa")
            model = AutoModelForCausalLM.from_pretrained(
                m["name_or_path"],
                quantization_config=bnb_cfg,
                torch_dtype=compute_dtype,
                attn_implementation="sdpa",
                trust_remote_code=m.get("trust_remote_code", False),
                device_map="auto",
            )
        else:
            raise

    model.config.use_cache = False
    if t.get("gradient_checkpointing", True):
        model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs=t.get("gradient_checkpointing_kwargs",
                                                {"use_reentrant": False})
        )
    model = prepare_model_for_kbit_training(model)

    # ---------------- LoRA ----------------
    peft_cfg = LoraConfig(
        r=l["r"],
        lora_alpha=l["alpha"],
        lora_dropout=l["dropout"],
        bias=l.get("bias", "none"),
        task_type=l.get("task_type", "CAUSAL_LM"),
        target_modules=l["target_modules"],
    )

    # ---------------- datasets ----------------
    train_path = resolve_path(d["train_file"])
    val_path = resolve_path(d["eval_file"])
    if not train_path or not train_path.exists():
        fatal(f"train file missing: {train_path} — run training/data_prep.py first")
    if not val_path or not val_path.exists():
        fatal(f"val file missing: {val_path} — run training/data_prep.py first")

    print(f"[load] train: {train_path}")
    print(f"[load] val:   {val_path}")
    raw = load_dataset(
        "json",
        data_files={"train": str(train_path), "validation": str(val_path)},
    )

    text_field = d.get("text_field", "text")
    if text_field not in raw["train"].column_names:
        fatal(f"text_field '{text_field}' not in train columns: "
              f"{raw['train'].column_names}")

    # ---------------- SFTConfig ----------------
    out_dir = resolve_path(t["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    sft_cfg = SFTConfig(
        output_dir=str(out_dir),
        num_train_epochs=t["num_train_epochs"],
        per_device_train_batch_size=t["per_device_train_batch_size"],
        per_device_eval_batch_size=t["per_device_eval_batch_size"],
        gradient_accumulation_steps=t["gradient_accumulation_steps"],
        learning_rate=t["learning_rate"],
        lr_scheduler_type=t["lr_scheduler_type"],
        warmup_steps=t["warmup_steps"],
        weight_decay=t.get("weight_decay", 0.0),
        optim=t.get("optim", "paged_adamw_8bit"),
        bf16=t.get("bf16", True),
        fp16=t.get("fp16", False),
        tf32=t.get("tf32", True),
        gradient_checkpointing=t.get("gradient_checkpointing", True),
        gradient_checkpointing_kwargs=t.get("gradient_checkpointing_kwargs",
                                            {"use_reentrant": False}),
        logging_steps=t.get("logging_steps", 25),
        eval_strategy=t.get("eval_strategy", "steps"),
        eval_steps=t.get("eval_steps", 500),
        save_strategy=t.get("save_strategy", "steps"),
        save_steps=t.get("save_steps", 1000),
        save_total_limit=t.get("save_total_limit", 3),
        load_best_model_at_end=t.get("load_best_model_at_end", False),
        report_to=t.get("report_to", "tensorboard"),
        seed=t.get("seed", 42),
        data_seed=t.get("data_seed", 42),
        max_grad_norm=t.get("max_grad_norm", 1.0),
        group_by_length=t.get("group_by_length", True),
        ddp_find_unused_parameters=t.get("ddp_find_unused_parameters", False),
        # SFT-specific
        max_seq_length=d.get("max_seq_length", 2048),
        packing=d.get("packing", False),
        dataset_text_field=text_field,
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_cfg,
        train_dataset=raw["train"],
        eval_dataset=raw["validation"],
        peft_config=peft_cfg,
        tokenizer=tokenizer,
    )

    # ---------------- train ----------------
    print(f"[train] starting; resume={args.resume}")
    trainer.train(resume_from_checkpoint=args.resume)

    # Save the final LoRA adapter (small — typically <200 MB).
    final_dir = out_dir / "final-adapter"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"[done] adapter saved → {final_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
