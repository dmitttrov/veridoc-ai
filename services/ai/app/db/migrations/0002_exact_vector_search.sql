-- Drop the approximate ivfflat index so vector search is EXACT and
-- DETERMINISTIC at the current corpus scale.
--
-- Rationale (see docs/DECISIONS.md, ADR-0016): ivfflat is an approximate-
-- nearest-neighbour index. On small tables most inverted lists are empty and a
-- single-probe search can miss relevant vectors, making retrieval results vary
-- run to run. That non-determinism undermines reproducible evaluation and the
-- project's correctness-first stance. Without the index, pgvector computes
-- exact cosine distances (a sequential scan) — fully deterministic and, at this
-- scale, fast. A tuned HNSW index can be reintroduced when the corpus grows
-- large enough to need approximate search.

DROP INDEX IF EXISTS idx_chunks_embedding;
