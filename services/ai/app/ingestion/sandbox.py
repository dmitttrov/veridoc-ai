"""Run CPU-bound parsing of untrusted PDF bytes in a **separate process** with
an enforceable wall-clock timeout.

Why a process and not a thread: a thread (``asyncio.to_thread``) cannot be
killed, so a pathological PDF that makes pypdf spin would keep burning a CPU
core even after ``asyncio.wait_for`` "times out" — ``wait_for`` only abandons the
awaiting coroutine, the work goes on. Running the parse in a child process lets
us hard-kill it on timeout and actually reclaim the CPU. Combined with the
ingestion concurrency semaphore, this bounds the worst-case CPU/memory a burst
of malicious uploads can pin.
"""
from __future__ import annotations

import asyncio
import multiprocessing
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from typing import TypeVar

from app.ingestion.errors import PdfProcessingTimeout
from app.ingestion.pdf import ExtractedPdf, validate_and_extract

T = TypeVar("T")

# Use "spawn" everywhere: identical behaviour on Linux and Windows and no
# fork+threads hazards (the parent runs an event loop and a DB pool). Workers are
# one-shot and concurrency is bounded upstream, so the spawn cost is acceptable.
_MP_CONTEXT = multiprocessing.get_context("spawn")


def _worker(data: bytes, max_bytes: int, max_pages: int) -> ExtractedPdf:
    # Runs in a child process. Expected rejections raise IngestionError
    # subclasses, which ProcessPoolExecutor pickles and re-raises in the parent.
    return validate_and_extract(data, max_bytes=max_bytes, max_pages=max_pages)


def _kill_workers(executor: ProcessPoolExecutor) -> None:
    # Hard-terminate any live worker so a timeout actually frees the CPU.
    procs = getattr(executor, "_processes", None) or {}
    for proc in list(procs.values()):
        if proc.is_alive():
            proc.kill()


async def _run_in_process(fn: Callable[..., T], *args: object, timeout_s: float) -> T:
    """Execute ``fn(*args)`` in a one-shot worker process, killing it if it
    exceeds ``timeout_s``. Raises ``TimeoutError`` on timeout; any exception the
    worker raises is propagated (pickled) to the caller."""
    loop = asyncio.get_running_loop()
    executor = ProcessPoolExecutor(max_workers=1, mp_context=_MP_CONTEXT)
    try:
        future = loop.run_in_executor(executor, fn, *args)
        try:
            return await asyncio.wait_for(future, timeout=timeout_s)
        except TimeoutError:
            _kill_workers(executor)
            raise
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


async def extract_pdf_sandboxed(
    data: bytes, *, max_bytes: int, max_pages: int, timeout_s: float
) -> ExtractedPdf:
    """Validate + extract a PDF in a killable child process under a timeout."""
    try:
        return await _run_in_process(
            _worker, data, max_bytes, max_pages, timeout_s=timeout_s
        )
    except TimeoutError as exc:
        raise PdfProcessingTimeout("PDF processing exceeded the time limit.") from exc
