"""Load the base model or base+adapter and run deterministic extraction.

Both paths use identical decoding (greedy) so baseline and adapter are compared
fairly. This mirrors the OpenAI-compatible serving path in services/ai but runs
the HF model directly for evaluation.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import torch

from veridoc_ft.config import TrainConfig
from veridoc_ft.prompt import build_messages
from veridoc_ft.schema import ExtractionResult, parse_extraction
from veridoc_ft.train import load_base


def _check_adapter_base(adapter_path: str, model_id: str) -> None:
    """Fail fast if the LoRA adapter was trained on a different base.

    peft loads with strict=False and never cross-checks the adapter config:
    a shape-compatible wrong base loads SILENTLY (identity-initialized LoRA),
    publishing 'adapter' numbers measured on effectively no adapter at all; a
    shape-incompatible one fails late with a cryptic tensor-size error.
    """
    cfg_path = Path(adapter_path) / "adapter_config.json"
    if not cfg_path.exists():
        return  # unusual layouts (e.g. checkpoints) fall through to peft
    base = json.loads(cfg_path.read_text(encoding="utf-8")).get("base_model_name_or_path")
    if base and base != model_id:
        raise ValueError(
            f"adapter at {adapter_path} was trained on base '{base}' but the "
            f"configured model is '{model_id}' — refusing to combine them"
        )


def load_model(config: TrainConfig, adapter_path: str | None = None) -> tuple[Any, Any]:
    if adapter_path:
        _check_adapter_base(adapter_path, config.model_id)
    model, tokenizer = load_base(config)
    label = "base"
    if adapter_path:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter_path)
        label = f"adapter:{adapter_path}"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    model.generation_label = label
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
    text: str = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return text


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
