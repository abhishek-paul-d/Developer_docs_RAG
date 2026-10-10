# FLOW

How data and requests move through the system. Updated in the same change as the code.

## Current state (Phase 0)

Skeleton plus the selection tooling. No RAG pipeline yet.

Selection flow: `python -m devdocs_rag.selection docs` -> `results/selection/docs_stats.json`; `questions` -> `questions.json`; `sheet <name>` -> `contamination_<name>.md` + `verdicts_<name>.csv`; reviewer checks answers against docs/source and focused runtime checks -> CSV verdicts and reasons. LLM calls go through `llm.CachedChat`.

Current review: all 40 answers graded by the assistant at the user's request (D-008), with six explicit scope exclusions. Empty verdicts with an `Excluded:` note are reviewed exclusions, not unfinished work. The existing `summarize <name>` command calls those blanks `unfilled`; use the review report to distinguish them.

`python -m devdocs_rag.selection.grading` reads the reviewed CSVs, docs pins and `grading_checks.json` -> validates reviewer notes and exclusions -> deterministic question bootstrap (D-009) -> `results/selection/grading_report.json` and `grading_report.md`. This adds no Groq calls. Input hashes and source/runtime versions accompany the summary. The report can be regenerated; the manual evidence checks are described in `docs/PHASE0_GRADING_GUIDE.md`.

Library chosen: Polars (D-001). Phase 0 is closed (CI green). The assistant labels above are provisional and do not replace the held-out golden set, the Phase 2 harness or the Phase 3 baseline comparisons. Corpus built in Phase 1 (see below).

## Phase 1: corpus build (`python -m devdocs_rag.data.pipeline`)

```
fetch_docs  clone pola-rs/polars at py-2.0.0 -> data/raw/polars, write source.json (tag + commit)
parse       user-guide + releases/upgrade .md -> resolve code_block/--8<-- snippets, drop exec/Rust, flatten tabs and admonitions -> Page
symbols     reference/**/*.rst names -> import polars==2.0.0 -> Symbol (signature, cleaned docstring)
chunk       Page -> heading/paragraph chunks (code stays with intro, cap 300)   Symbol -> api_reference chunks
split       group -> train/val/test (70/10/20, seed 0, stratified by guide/changelog/api)
write       data/processed/{chunks.jsonl, symbols.json, split.json, report.json}  (sorted, byte-identical per run)
```

All chunks go into the retrieval index; the split only restricts training data and golden-set questions. Decisions: D-010 to D-016. Walk-through: `docs/PHASE1_GUIDE.md`.

## Planned flow

docs repo (pinned commit) -> parse -> chunk -> symbols + split manifest -> index -> retrieve -> generate -> cite/validate -> answer

Eval harness runs the same pipeline over the golden set and writes `results/<config>/report.{json,md}`.
