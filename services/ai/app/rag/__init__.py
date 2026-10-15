"""Grounded retrieval-augmented generation (Phase 3).

Pipeline: question -> hybrid retrieval (+optional rerank) -> evidence assembly
-> LLM -> citation verification -> answer. Citation verification checks that
cited markers map to retrieved evidence; it does NOT verify that the evidence
semantically supports the claim (see docs).
"""
