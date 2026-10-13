"""Deterministic, reproducible chunking of normalized page text.

Chunks are word-aligned windows over a single page's normalized text, so:
  * every chunk's ``text`` equals ``page_text[char_start:char_end]`` exactly,
  * boundaries never split a word, and
  * the same input always yields the same chunks (stable offsets & indices).

Chunking is per page, which preserves page-level provenance for citations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_WORD = re.compile(r"\S+")


@dataclass(frozen=True)
class Chunk:
    index: int
    char_start: int
    char_end: int
    text: str


def chunk_page_text(
    page_text: str,
    *,
    size: int = 800,
    overlap: int = 150,
) -> list[Chunk]:
    """Split ``page_text`` into overlapping, word-aligned chunks.

    ``size`` and ``overlap`` are measured in characters. Empty/whitespace-only
    pages yield no chunks. A page shorter than ``size`` yields a single chunk.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if not 0 <= overlap < size:
        raise ValueError("overlap must satisfy 0 <= overlap < size")

    words = [(m.start(), m.end()) for m in _WORD.finditer(page_text)]
    if not words:
        return []

    chunks: list[Chunk] = []
    n = len(words)
    i = 0
    index = 0
    while i < n:
        start_offset = words[i][0]
        j = i
        # Grow the window while it stays within `size` characters; always take
        # at least one word so a single over-long word still forms a chunk.
        while j + 1 < n and (words[j + 1][1] - start_offset) <= size:
            j += 1
        end_offset = words[j][1]
        chunks.append(
            Chunk(
                index=index,
                char_start=start_offset,
                char_end=end_offset,
                text=page_text[start_offset:end_offset],
            )
        )
        index += 1

        if j + 1 >= n:
            break

        # Step the start back by `overlap` characters (word-aligned) to create
        # context overlap between consecutive chunks. Guarantee forward progress.
        next_i = j + 1
        k = j
        while k > i and (end_offset - words[k][0]) <= overlap:
            k -= 1
        if k + 1 < next_i:
            next_i = k + 1
        i = max(next_i, i + 1)

    return chunks
