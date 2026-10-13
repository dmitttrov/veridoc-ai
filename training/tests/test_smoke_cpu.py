"""CPU training smoke test — no network, no downloads.

Builds a TINY randomly initialized Qwen3 model, attaches LoRA, and runs two
optimizer steps on a handful of fake tokenized rows. This exercises the real
training path (LoRA wiring, prompt-masked labels collation, Trainer loop,
adapter save) deterministically in seconds, without the 0.6B base model.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

transformers = pytest.importorskip("transformers")
pytest.importorskip("peft")
pytest.importorskip("torch")

from veridoc_ft.config import TrainConfig  # noqa: E402
from veridoc_ft.train import attach_lora, train  # noqa: E402


def _tiny_model():
    from transformers import Qwen3Config, Qwen3ForCausalLM

    cfg = Qwen3Config(
        vocab_size=256,
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        max_position_embeddings=256,
        tie_word_embeddings=True,
    )
    return Qwen3ForCausalLM(cfg)


def _tiny_rows(n: int = 6, length: int = 16) -> list[dict]:
    rng = random.Random(0)
    rows = []
    for _ in range(n):
        ids = [rng.randint(1, 255) for _ in range(length)]
        labels = [-100] * (length // 2) + ids[length // 2 :]  # mask the "prompt"
        rows.append({"input_ids": ids, "attention_mask": [1] * length, "labels": labels})
    return rows


def test_cpu_training_smoke(tmp_path: Path) -> None:
    model = attach_lora(_tiny_model(), TrainConfig())
    config = TrainConfig(
        output_dir=str(tmp_path / "adapter"),
        max_steps=2,
        num_train_epochs=1,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=1,
        gradient_checkpointing=False,
        logging_steps=1,
        save_steps=2,
        eval_steps=2,
    )

    metrics = train(model, _tiny_rows(), None, config, pad_token_id=0)

    # Adapter artifacts were written.
    out = tmp_path / "adapter"
    assert (out / "adapter_config.json").exists()
    assert (out / "adapter_model.safetensors").exists()
    # A finite loss was logged.
    assert metrics["log_history"], "expected training logs"
    losses = [h["loss"] for h in metrics["log_history"] if "loss" in h]
    assert losses and all(v == v for v in losses)  # not NaN

    # The saved LoRA adapter can be re-read.
    saved = json.loads((out / "adapter_config.json").read_text())
    assert saved["peft_type"] == "LORA"
