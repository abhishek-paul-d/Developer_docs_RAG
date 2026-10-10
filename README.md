# Developer Docs Assistant

A measured RAG system for one open-source library's docs: cited answers, refusal when the docs don't cover a question, API-existence checks, and a fine-tuned small generator. See [plan.md](plan.md) for the full plan and [DECISIONS.md](DECISIONS.md) for why each choice was made.

Status: Phase 1 (corpus) on branch phase-1. Target library: Polars 2.0.0 (see D-001, D-010). Build the corpus with `uv run python -m devdocs_rag.data.pipeline`.
