"""Load the base model or base+adapter and run deterministic extraction.

Both paths use identical decoding (greedy) so baseline and adapter are compared
fairly. This mirrors the OpenAI-compatible serving path in services/ai but runs
the HF model directly for evaluation.
"""
from __future__ import annotations

import time
from typing import Any

import torch

from veridoc_ft.config import TrainConfig
from veridoc_ft.prompt import build_messages
from veridoc_ft.schema import ExtractionResult, parse_extraction
from veridoc_ft.train import load_base


def load_model(config: TrainConfig, adapter_path: str | None = None) -> tuple[Any, Any]:
    model, tokenizer = load_base(config)
    label = "base"
    if adapter_path:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter_path)
        label = f"adapter:{adapter_path}"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    model.generation_label = label  # type: ignore[attr-defined]
    return model, tokenizer


@torch.no_grad()
def generate_text(
    model: Any, tokenizer: Any, question: str, evidence: list[str], config: TrainConfig
) -> str:
    messages = build_messages(question, evidence)
    enc = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
        return_dict=True,
        return_tensors="pt",
    )
    enc = {k: v.to(model.device) for k, v in enc.items()}
    out = model.generate(
        **enc,
        max_new_tokens=config.max_new_tokens,
        do_sample=False,  # greedy, deterministic
        temperature=None,
        top_p=None,
        top_k=None,
        pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
    )
    new_tokens = out[0][enc["input_ids"].shape[1] :]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


def extract(
    model: Any, tokenizer: Any, question: str, evidence: list[str], config: TrainConfig
) -> dict:
    start = time.perf_counter()
    text = generate_text(model, tokenizer, question, evidence, config)
    latency = time.perf_counter() - start
    result, status = parse_extraction(text)
    return {
        "raw": text,
        "status": status,
        "result": result.model_dump() if isinstance(result, ExtractionResult) else None,
        "latency_s": round(latency, 3),
    }
