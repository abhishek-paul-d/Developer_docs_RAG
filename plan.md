# Developer Docs Assistant: a measured RAG system with a fine-tuned generator

Build a documentation assistant for one fast-changing open-source library. It answers developer questions from the library's own docs, cites its sources, refuses when the docs don't cover the question, and checks that the APIs and code it suggests really exist. Every component is scored, and failures are reported alongside wins.

Interview story: "A plain LLM got X% of questions about <library> wrong or outdated. Docs-grounded retrieval cut that to Y%, a fine-tuned 4B model matched/beat the prompted baseline on Z, and here is what didn't help."

---

## 1. Why this project

| Property | Why it matters |
|---|---|
| Answers are checkable | An API either exists or it does not; a snippet either runs or it does not. Scoring is less subjective than for opinions. |
| Real users | Developers ask the library's Discussions / Stack Overflow every day, so real questions exist. |
| Retrieval can visibly help | If the library changes fast, the base LLM gives outdated answers and retrieval measurably fixes them. |
| Free stack | Public docs, Groq free tier, Ollama, Colab/Kaggle. |

**Primary user:** a developer using the library who wants a correct, cited answer in seconds instead of searching docs and forum threads.
**Out of scope:** general programming help, other libraries, answers not grounded in the docs.

## 2. Principles

1. **Eval first.** The harness exists before any component changes.
2. **One change at a time.** Each ablation row changes exactly one thing.
3. **Prompt before fine-tune.** The fine-tune must beat a strong prompted baseline to be kept.
4. **Real questions over synthetic ones** for the golden set. Synthetic questions are allowed for training data only.
5. **Never grade on what you trained on.** Split docs by page group; golden-set questions come from held-out pages.
6. **Report uncertainty.** Bootstrap confidence intervals on every metric; do not claim a win inside the noise.
7. **Report failures.** Components that do not help stay in the report.
8. **Free stack.** Groq free tier, Ollama, Colab/Kaggle. All LLM calls are cached on disk.
9. **Living docs.** `DECISIONS.md` and `FLOW.md` are updated in the same change as the code; code comments stay minimal. Each phase ends with `docs/PHASEn_GUIDE.md`, a teaching write-up with real code and real numbers.
10. **Fine-tuning is done in `.ipynb` notebooks**, each code cell preceded by a markdown cell explaining what it does and why. No `.py` for that stage.
11. **Every method has a reason.** Every choice (library, chunking strategy, embedding model, retriever, reranker, generator, prompt, hyperparameters, metrics, dependencies) gets a `DECISIONS.md` entry: why this, which alternatives were rejected and why, the evidence, and when to revisit. "Popular" is not a reason. See `CLAUDE.md` for the format.

## 3. Constraints and open items

- No local GPU. Training runs on Colab or Kaggle. Inference is CPU, so the generator is a small quantized model; latency is measured and reported.
- Groq free-tier limits pace teacher generation and judge calls.
- **License checks (before publishing anything):** the docs repo license; GitHub Discussions/Issues content (user-written, per-repo terms); Stack Overflow dump (CC BY-SA, attribution and share-alike); the benchmark license if CodeRAG-Bench is used. Publish scripts and manifests, not data, unless a license clearly allows it.
- **Target library is not chosen yet.** Phase 0 decides it with a test, not a guess.
- Work happens on a branch. Nothing merges to `main` without review.

## 4. Phases

### Phase 0: Choose the library and set up the repo
**Goal:** pick a library where retrieval should matter, and have a tested, CI-checked skeleton.

Selection test, run on 4 to 5 candidates (for example Polars, Pydantic v2, LangGraph, uv/Ruff, FastAPI):

| Criterion | How to measure | Pass condition |
|---|---|---|
| Docs size and license | Clone the docs repo; count pages/words; read the license | Permissive license; large enough for hundreds of pages |
| Real questions available | Count answered GitHub Discussions and Stack Overflow questions | At least a few hundred usable answered questions |
| Contamination | Ask a plain LLM 20 real questions with no retrieval; a human marks wrong/outdated | Many wrong or outdated answers (otherwise retrieval has nothing to fix) |

- Record the candidate scores in `DECISIONS.md`; choose one.
- Repo: `src/devdocs_rag/` package, `pyproject.toml` (uv), pydantic-settings config, ruff, pytest, pre-commit, GitHub Actions CI, `Makefile`.
- Create `DECISIONS.md`, `FLOW.md`, `CLAUDE.md` (notebook rule for fine-tuning).

**Exit:** library chosen with evidence; `uv sync && pytest && ruff check` pass locally and in CI.

### Phase 1: Corpus
**Goal:** a versioned, cleanly chunked docs corpus with metadata.

- Clone the docs repo at a pinned tag/commit. Record the commit hash.
- Parse Markdown/RST: strip frontmatter and build artefacts, keep headings, keep code blocks intact.
- **Chunk by structure, not by length alone:** split on headings; keep a code block with the paragraph that introduces it; split long sections at paragraph boundaries; cap the size (start at about 300 tokens, tune in Phase 4).
- Each chunk carries `chunk_id, doc_path, section_path (heading trail), url, library_version, chunk_type (prose | code | api_reference | changelog), text`.
- Extract an **API symbol list** (function/class/method names) from the API reference; used later to check generated answers.
- **Split by page group** (for example by top-level docs section) into train / val / test, saved as a manifest. Related pages stay in one split.
- Deterministic chunk IDs (hash of path + section + text); same inputs give byte-identical output.

**Exit:** `make data` reproduces the corpus, symbol list and split manifest; counts logged in `report.json`.

### Phase 2: Golden set and eval harness
**Goal:** a trusted yardstick before touching the pipeline.

**Golden set (about 100 to 150 questions), from real sources:**
- Answered GitHub Discussions / Stack Overflow questions for the library, where the accepted answer points to a docs page that is in the test split.
- Question types: single-section, multi-section, version-sensitive ("in v2, how do I...?"), unanswerable-from-docs (correct behaviour is refusal), multi-turn follow-up.
- Each item stores: question, gold chunk IDs, a reference answer written/verified by hand, and (where possible) a runnable check.
- Mechanical validation: every gold chunk exists; every quoted evidence string appears verbatim in its chunk. Hand-check about 20.
- Synthetic questions are allowed only to fill gaps, and are flagged as such.

**Metrics:**
- Retrieval (no LLM): hit@k, MRR, recall@k against gold chunk IDs.
- Generation: faithfulness and answer relevancy (RAGAS or equivalent), judge = Groq 70B with a disk cache.
- Custom: **refusal accuracy** on unanswerable questions; **citation validity** (cited IDs exist and support the claim); **API validity** (every API name in the answer exists in the symbol list for the pinned version); **code check** (where a runnable test exists, run the snippet in a sandbox).
- Every table reports 95% bootstrap confidence intervals over questions; compare configurations with a paired bootstrap.
- Judge noise: re-run one configuration three times and report the spread.

**Exit:** `python -m devdocs_rag.eval run --config <name>` writes a JSON + markdown report, reproducibly.

### Phase 3: Baselines (two rows, not one)
1. **No retrieval:** the plain LLM answers alone. This is the contamination baseline and shows what retrieval buys.
2. **Naive RAG:** dense MiniLM + FAISS, k=4, simple prompt.

**Exit:** both scored and committed in `results/`. They are rows 1 and 2 of every table.

### Phase 4: Retrieval ablation
One change per step, each scored on the same golden set:

| Step | Change |
|---|---|
| 4.0 | Naive RAG baseline |
| 4.0b | Embedding bake-off (below); winner becomes the encoder for later steps |
| 4.1 | Structure-aware chunk size and k as separate labelled experiments |
| 4.2 | + BM25 hybrid with reciprocal rank fusion (docs have exact identifiers, so lexical match should help) |
| 4.3 | + cross-encoder reranker |
| 4.4 | + version filter (restrict to the asked version) |
| 4.5 | + history-aware query rewriting |
| 4.6 | *(optional)* fine-tuned embeddings |

**Embedding bake-off:** MiniLM-L6, bge-small, bge-base, e5-base, nomic-embed-text, plus a code-aware option if code questions dominate. Score with non-LLM metrics only (hit@5, MRR, recall@k), plus indexing time and query latency. Per-model prefix settings are config. Pick on the quality/latency trade-off.

**Exit:** ablation table filled with real numbers, confidence intervals, and a short reading of each result.

### Phase 5: Prompted generation
- Strong prompt: strict citation format (`[1]`), fixed refusal phrase, instruction to prefer the pinned version, few-shot examples.
- Retrieval-confidence threshold: refuse before generating when nothing relevant was retrieved.
- Score base generators with retrieval fixed: Llama 3 8B, Qwen 4B, and a small code-capable model.

**Exit:** the best prompted generator is identified; its scores are the bar the fine-tune must beat.

### Phase 6: Fine-tuning (notebooks only, every cell explained)
**6A. Generator (main).**
- Teach behaviours, not facts: cite, refuse when unsupported, use only APIs present in the context, respect the version, handle follow-ups.
- Data: about 3 to 5k examples from **train-split pages only**, written by a stronger teacher (Groq 70B) from real chunks:
  - answerable with citations (single and multi-chunk),
  - unanswerable (context off-topic), target is the refusal,
  - distractor mix (gold chunk among irrelevant ones, retrieved by the real retriever),
  - version traps (outdated API in the prompt, correct current API in the docs),
  - multi-turn.
- Filters: verbatim-quote check; every API name in the target exists in the symbol list; a second verification pass; drop failures.
- Train: QLoRA on Qwen (4B class), on Colab/Kaggle; merge; export GGUF for Ollama. Reuse the setup from `D:\Banking_FInetuning` as a reference.
- Evaluate on test-split questions with retrieval fixed. **Keep the fine-tune only if it beats the best prompted generator** (paired bootstrap, not eyeballing). Report either way.

**6B. Embeddings (optional)** if retrieval metrics show headroom: triplets from train pages with hard negatives, `MultipleNegativesRankingLoss`, evaluated on held-out pages.
**6C. Reranker (optional)** only if the off-the-shelf one leaves a gap.

**Exit:** generator comparison table (no-retrieval, prompted base, few-shot, fine-tuned) with the fine-tune adopted or rejected on evidence.

### Phase 7: Serving and product
- FastAPI: `/chat` (streaming), `/health`, `/sources`.
- Streamlit (or simple web) UI showing citations, retrieved passages, and the library version.
- Structured logging, request IDs, per-stage latency (retrieve / rerank / generate).
- Dockerfile and `docker-compose.yml` (API + Ollama).
- Basic load test and latency table (CPU-only numbers, stated honestly).
- Optional: eval gate in CI on a small slice (as in the Banking project).

**Exit:** `docker compose up` gives a working demo; latency numbers recorded.

### Phase 8: Documentation and release
- README rewrite: architecture diagram, results tables with confidence intervals, "what didn't help", how to reproduce.
- Final pass on `DECISIONS.md` and `FLOW.md` (prune superseded entries).
- Model card for the fine-tune (data, license, limits).
- Short interview write-up.
- Open a PR, review, merge.

## 5. Results tables to fill

**Retrieval ablation** (95% CI in every cell)

| Config | Hit@5 | MRR | Faithfulness | Citation validity | API validity | Latency |
|---|---|---|---|---|---|---|
| No retrieval (plain LLM) | n/a | n/a | | n/a | | |
| Naive RAG | | | | | | |
| + best encoder | | | | | | |
| + hybrid | | | | | | |
| + reranker | | | | | | |
| + version filter | | | | | | |
| + query rewriting | | | | | | |

**Generator comparison** (retrieval fixed)

| Generator | Faithfulness | Refusal accuracy | Citation validity | API validity | Code-check pass |
|---|---|---|---|---|---|
| Llama 3 8B, simple prompt | | | | | |
| Llama 3 8B, strong prompt | | | | | |
| Qwen 4B, strong prompt | | | | | |
| Qwen 4B, fine-tuned | | | | | |

## 6. Risks

| Risk | Mitigation |
|---|---|
| Base LLM already knows the library, so retrieval shows no gain | Phase 0 contamination test; pick a fast-changing or recent library |
| Golden set too small for significant differences | Bootstrap CIs, paired tests, report "no significant difference" honestly |
| Teacher writes both training data and test questions, inflating the fine-tune | Golden set from real questions on held-out pages; teacher prompts differ |
| Question/answer licensing (CC BY-SA, user content) | Publish scripts and manifests, not data; record terms in `DECISIONS.md` |
| Docs change after the pin, so answers drift | Pin tag and commit; store the version on every chunk and in every report |
| Generated code looks right but fails | API-name check against the symbol list; sandboxed execution where tests exist |
| Groq free-tier limits | Cache every call; keep the golden set to about 100 to 150 |
| CPU inference is slow | Small quantized model; measure and report latency |
| Scope too large | Thin end-to-end demo right after Phase 3, before any ablation |

## 7. Target repo layout

```
devdocs-assistant/
  project.md  plan.md  DECISIONS.md  FLOW.md  README.md  CLAUDE.md
  pyproject.toml  Makefile  Dockerfile  docker-compose.yml
  .env.example  .github/workflows/ci.yml
  src/devdocs_rag/
    config.py  logging.py  exceptions.py
    data/        fetch_docs.py  parse.py  chunk.py  symbols.py  split.py  pipeline.py
    retrieval/   dense.py  bm25.py  hybrid.py  rerank.py  rewrite.py  filters.py
    generation/  prompts.py  generator.py  citations.py  api_check.py
    pipeline.py
    eval/        golden.py  metrics.py  bootstrap.py  code_check.py  report.py
    api/         app.py
    ui/          app.py
  notebooks/     sft_data_build.ipynb  qlora_train.ipynb  merge_export.ipynb  eval_finetuned.ipynb
  docs/          PHASE0_GUIDE.md ... PHASE8_GUIDE.md
  tests/
  results/       <config>/report.json|md
  data/          raw/ processed/ eval/   (git-ignored)
```

## 8. Sequence at a glance

```
0 Choose library + skeleton -> 1 Corpus -> 2 Golden set + harness -> 3 Baselines (no-retrieval, naive RAG)
   -> thin end-to-end demo
   -> 4 Retrieval ablation -> 5 Prompted generation
   -> 6 Fine-tuning (notebooks)
   -> 7 Serving -> 8 Docs + release
```

Phases 0 to 3 are the critical path: no component is changed until the baselines are scored.

## 9. Definition of done

- Both baselines and every ablation row scored with confidence intervals.
- Fine-tune adopted or rejected on paired evidence.
- `docker compose up` runs the demo with citations.
- `DECISIONS.md`, `FLOW.md`, and a guide per phase are current.
- README contains the results tables and a "what didn't help" section.
