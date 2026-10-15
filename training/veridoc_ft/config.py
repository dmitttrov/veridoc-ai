"""Explicit, pinned training/inference configuration."""
from __future__ import annotations

from dataclasses import dataclass, field

# Base model identity — PINNED. See docs/MODEL_STRATEGY.md and ADR-0021.
BASE_MODEL_ID = "Qwen/Qwen3-0.6B"
BASE_MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"

# Qwen3 attention + MLP projection module names LoRA attaches to.
QWEN3_LORA_TARGETS = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
)


@dataclass
class TrainConfig:
    model_id: str = BASE_MODEL_ID
    model_revision: str = BASE_MODEL_REVISION

    # Data
    data_dir: str = "data/v1"
    output_dir: str = "artifacts/adapter-v1"
    max_seq_len: int = 1024

    # LoRA
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_targets: tuple[str, ...] = QWEN3_LORA_TARGETS

    # Optimization
    seed: int = 42
    learning_rate: float = 2e-4
    num_train_epochs: float = 3.0
    per_device_train_batch_size: int = 1
    per_device_eval_batch_size: int = 1
    gradient_accumulation_steps: int = 16
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    logging_steps: int = 5
    eval_steps: int = 20
    save_steps: int = 20
    # A small positive value runs a *pilot*; -1 means "use epochs".
    max_steps: int = -1

    # Hardware / precision
    gradient_checkpointing: bool = True
    use_qlora: bool = False  # 4-bit base; CUDA + bitsandbytes only
    # Precision is auto-selected at runtime (bf16 on Ampere+, else fp16 on CUDA,
    # else fp32 on CPU) unless overridden here.
    bf16: bool | None = None
    fp16: bool | None = None

    # Decoding (shared by baseline + adapter eval for a fair comparison).
    max_new_tokens: int = 160
    temperature: float = 0.0  # greedy

    extra: dict = field(default_factory=dict)
