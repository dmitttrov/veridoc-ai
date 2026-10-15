"""Unit tests for prompt-masked label construction + truncation (no model)."""
from __future__ import annotations

import json

from veridoc_ft.config import TrainConfig
from veridoc_ft.dataset import Example
from veridoc_ft.train import tokenize_examples


class _FakeTok:
    """Minimal tokenizer: 1 token per character, distinct ids for prompt/target."""

    eos_token_id = 0

    def apply_chat_template(
        self, messages, tokenize=True, add_generation_prompt=True, enable_thinking=False
    ):
        n = sum(len(m["content"]) for m in messages)
        return [1] * n  # prompt tokens

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [7] * len(text)}  # target tokens


def _ex(question="Q", evidence=None, target=None) -> Example:
    return Example(
        id="t", family="f", category="answerable",
        question=question, evidence=evidence or ["E"],
        target=target or {"metric": "m", "value": "1", "supported": True},
    )


def _target_len(target: dict) -> int:
    return len(json.dumps(target, separators=(",", ":"), sort_keys=True))


def test_labels_mask_prompt_and_preserve_target() -> None:
    ex = _ex()
    [row] = tokenize_examples([ex], _FakeTok(), TrainConfig(max_seq_len=1024))
    assert len(row["input_ids"]) == len(row["labels"])
    tlen = _target_len(ex.target)
    # the final target_ids + eos survive unmasked; everything before is -100
    assert row["labels"][-(tlen + 1):] == [7] * tlen + [0]
    assert set(row["labels"][: -(tlen + 1)]) == {-100}
    assert row["input_ids"][-(tlen + 1):] == [7] * tlen + [0]


def test_oversized_prompt_truncates_prompt_not_target() -> None:
    target = {"metric": "m", "value": "1", "supported": True}
    tlen = _target_len(target)
    cfg = TrainConfig(max_seq_len=tlen + 1 + 5)  # target + eos + 5 prompt tokens
    ex = _ex(question="x" * 1000, evidence=["y" * 1000], target=target)
    [row] = tokenize_examples([ex], _FakeTok(), cfg)
    assert len(row["input_ids"]) == cfg.max_seq_len
    # target + eos is fully intact at the tail (never truncated)
    assert row["input_ids"][-(tlen + 1):] == [7] * tlen + [0]
    assert row["labels"][-(tlen + 1):] == [7] * tlen + [0]


def test_target_larger_than_budget_is_skipped() -> None:
    target = {"metric": "m", "value": "1", "supported": True}
    cfg = TrainConfig(max_seq_len=_target_len(target))  # budget < 0
    assert tokenize_examples([_ex(target=target)], _FakeTok(), cfg) == []
