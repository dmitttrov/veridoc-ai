"""Reproducible LoRA supervised fine-tuning.

Design: the trainer core (`train`) is decoupled from model/tokenizer loading so
it can be exercised by a fast, no-network CPU smoke test with a tiny randomly
initialized Qwen3 model. `run` wires the real pinned base model + dataset.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch

from veridoc_ft.config import TrainConfig
from veridoc_ft.prompt import build_messages

logger = logging.getLogger("veridoc.ft.train")


def precision_flags(config: TrainConfig) -> dict[str, bool]:
    if config.bf16 is not None or config.fp16 is not None:
        return {"bf16": bool(config.bf16), "fp16": bool(config.fp16)}
    if torch.cuda.is_available():
        if torch.cuda.is_bf16_supported():
            return {"bf16": True, "fp16": False}
        return {"bf16": False, "fp16": True}
    return {"bf16": False, "fp16": False}  # CPU -> fp32


class PadCollator:
    """Pads input_ids/attention_mask/labels to the longest item in the batch.
    Label pad is -100 so padded positions are ignored by the loss."""

    def __init__(self, pad_token_id: int, label_pad: int = -100) -> None:
        self.pad_token_id = pad_token_id
        self.label_pad = label_pad

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        max_len = max(len(f["input_ids"]) for f in features)
        batch: dict[str, list[list[int]]] = {"input_ids": [], "attention_mask": [], "labels": []}
        for f in features:
            ids = list(f["input_ids"])
            labels = list(f["labels"])
            mask = list(f.get("attention_mask", [1] * len(ids)))
            pad = max_len - len(ids)
            batch["input_ids"].append(ids + [self.pad_token_id] * pad)
            batch["attention_mask"].append(mask + [0] * pad)
            batch["labels"].append(labels + [self.label_pad] * pad)
        return {k: torch.tensor(v, dtype=torch.long) for k, v in batch.items()}


def attach_lora(model: Any, config: TrainConfig) -> Any:
    from peft import LoraConfig, get_peft_model

    lora = LoraConfig(
        task_type="CAUSAL_LM",
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=list(config.lora_targets),
        bias="none",
    )
    peft_model = get_peft_model(model, lora)
    return peft_model


def tokenize_examples(examples: list[Any], tokenizer: Any, config: TrainConfig) -> list[dict]:
    """Render each example to chat format and build prompt-masked labels."""
    rows: list[dict] = []
    for ex in examples:
        messages = build_messages(ex.question, ex.evidence)
        prompt_ids = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, enable_thinking=False
        )
        target = json.dumps(ex.target, separators=(",", ":"), sort_keys=True)
        target_ids = tokenizer(target, add_special_tokens=False)["input_ids"]
        eos = [tokenizer.eos_token_id] if tokenizer.eos_token_id is not None else []
        # Truncate the PROMPT, never the target: slicing the concatenation at the
        # end (the previous behaviour) could drop part or all of the supervised
        # target/EOS, yielding label rows that teach nothing (all -100).
        budget = config.max_seq_len - len(target_ids) - len(eos)
        if budget <= 0:
            logger.warning(
                "skipping example %s: target (%d) + EOS exceeds max_seq_len=%d",
                getattr(ex, "id", "?"), len(target_ids), config.max_seq_len,
            )
            continue
        if len(prompt_ids) > budget:
            logger.warning(
                "truncating prompt of example %s from %d to %d tokens to fit the target",
                getattr(ex, "id", "?"), len(prompt_ids), budget,
            )
            prompt_ids = prompt_ids[:budget]
        input_ids = prompt_ids + target_ids + eos
        labels = [-100] * len(prompt_ids) + target_ids + eos
        rows.append(
            {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}
        )
    return rows


def train(
    model: Any,
    train_rows: list[dict],
    eval_rows: list[dict] | None,
    config: TrainConfig,
    pad_token_id: int,
) -> dict:
    from transformers import Trainer, TrainingArguments, set_seed

    set_seed(config.seed)
    out = Path(config.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    precision = precision_flags(config)

    if config.gradient_checkpointing and hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
        if hasattr(model, "config"):
            model.config.use_cache = False

    args = TrainingArguments(
        output_dir=str(out),
        seed=config.seed,
        data_seed=config.seed,
        per_device_train_batch_size=config.per_device_train_batch_size,
        per_device_eval_batch_size=config.per_device_eval_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        num_train_epochs=config.num_train_epochs,
        max_steps=config.max_steps,
        warmup_ratio=config.warmup_ratio,
        weight_decay=config.weight_decay,
        logging_steps=config.logging_steps,
        eval_strategy="steps" if eval_rows else "no",
        eval_steps=config.eval_steps,
        save_strategy="steps",
        save_steps=config.save_steps,
        save_total_limit=2,
        gradient_checkpointing=config.gradient_checkpointing,
        report_to=[],
        remove_unused_columns=False,
        bf16=precision["bf16"],
        fp16=precision["fp16"],
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_rows,
        eval_dataset=eval_rows,
        data_collator=PadCollator(pad_token_id),
    )

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    result = trainer.train()
    trainer.save_model(str(out))  # saves the LoRA adapter

    metrics: dict = {
        "config": asdict(config),
        "train_runtime_s": round(result.metrics.get("train_runtime", 0.0), 3),
        "train_loss": round(result.metrics.get("train_loss", float("nan")), 6),
        "log_history": trainer.state.log_history,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
    }
    if torch.cuda.is_available():
        metrics["gpu_max_memory_mb"] = round(torch.cuda.max_memory_allocated() / 1e6, 1)
        metrics["gpu_name"] = torch.cuda.get_device_name(0)

    (out / "training_metrics.json").write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8"
    )
    logger.info("saved adapter + metrics to %s", out)
    return metrics


def load_base(config: TrainConfig) -> tuple[Any, Any]:
    """Load the PINNED base model + tokenizer (downloads on first use)."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        config.model_id, revision=config.model_revision
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    # Drive the load dtype from the SAME resolved precision as TrainingArguments,
    # so an explicit bf16/fp16 override (e.g. forcing fp32 to debug precision)
    # actually loads matching weights instead of silently using bf16/fp16.
    flags = precision_flags(config)
    dtype = torch.bfloat16 if flags["bf16"] else torch.float16 if flags["fp16"] else torch.float32
    if config.use_qlora:
        if not torch.cuda.is_available():
            raise ValueError("use_qlora=True requires CUDA; bitsandbytes is GPU-only.")
        from transformers import BitsAndBytesConfig

        quant = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        )
        model = AutoModelForCausalLM.from_pretrained(
            config.model_id, revision=config.model_revision, quantization_config=quant
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            config.model_id, revision=config.model_revision, dtype=dtype
        )
    return model, tokenizer


def run(config: TrainConfig) -> dict:
    from veridoc_ft.dataset import load_split

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    model, tokenizer = load_base(config)
    if config.use_qlora:
        from peft import prepare_model_for_kbit_training

        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=config.gradient_checkpointing
        )
    model = attach_lora(model, config)
    model.print_trainable_parameters()

    train_rows = tokenize_examples(load_split(config.data_dir, "train"), tokenizer, config)
    val_rows = tokenize_examples(load_split(config.data_dir, "val"), tokenizer, config)

    tokenizer.save_pretrained(config.output_dir)
    return train(model, train_rows, val_rows, config, pad_token_id=tokenizer.pad_token_id)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LoRA SFT for Veridoc extraction")
    parser.add_argument("--data-dir", default="data/v1")
    parser.add_argument("--output-dir", default="artifacts/adapter-v1")
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--epochs", type=float, default=3.0)
    args = parser.parse_args()
    cfg = TrainConfig(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        max_steps=args.max_steps,
        num_train_epochs=args.epochs,
    )
    print(json.dumps(run(cfg)["train_loss"], default=str))
