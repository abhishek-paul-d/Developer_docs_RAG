# DECISIONS

One entry per decision. Format and rules are in [CLAUDE.md](CLAUDE.md).

## D-001: Target library
- Date / phase: 2026-10-11 / Phase 0
- Decision: **Polars** (docs from `pola-rs/polars`, `docs/source`, pinned at the commit in results/selection/docs_stats.json). Chosen by the user from two finalists after the evidence below left the error test tied.
- Why: retrieval only adds value where the plain LLM is wrong or outdated, and the golden set needs hundreds of real answered questions. Polars passes both: a strong plain model was wrong or outdated on most sampled questions, and Stack Overflow has 1,828 accepted-answer questions with few off-topic ones (1 of 20 sampled were out of scope, against 5 of 20 for Pydantic). Its errors are mostly invented or removed API names, which the planned API-validity check can detect mechanically. The user chose Polars over Pydantic v2 on 2026-10-11.
- Alternatives considered:
  - FastAPI: dropped up front. Models likely know it too well for retrieval to add much (assumption, not measured).
  - LangGraph: eliminated. Only 26 Stack Overflow questions with accepted answers, GitHub Discussions disabled. Docs also moved out of its own repo into `langchain-ai/docs`, 43 pages there.
  - uv: eliminated. 73 accepted-answer Stack Overflow questions, Discussions disabled.
  - Pydantic v2: runner-up. 73.3% error rate (not separable from Polars), 568 answered Discussions and many v1-to-v2 version-sensitive questions, but 5 of 20 sampled questions fell outside the library's own docs and the user is more likely to be able to verify answers about it. Revisit it first if Polars fails below.
- Evidence (results/selection/*.json, docs pinned at the commits recorded there):

  | Candidate | License | Doc pages (>=100 words) | Words | SO accepted | Discussions answered |
  |---|---|---|---|---|---|
  | Polars | MIT | 87 (75) | 63,824 | 1,828 | disabled |
  | Pydantic | MIT | 91 (51) | 82,211 | 1,099 | 568 |
  | LangGraph | MIT | 43 (41) | 127,445 | 26 | disabled |
  | uv | Apache-2.0 OR MIT | 81 (67) | 71,402 | 73 | disabled |

  Assistant-reviewed preliminary error rates (2026-10-11, D-008/D-009): Polars 16/19 = 84.2% (95% CI 68.4% to 100.0%); Pydantic 11/15 = 73.3% (53.3% to 93.3%). All 40 sampled answers reviewed; six scope exclusions. Evidence: [grading report](results/selection/grading_report.md). The difference interval includes zero, so these samples do not establish a winner. These are observed error rates, not proof of training-data contamination or a measured retrieval gain. Interval for the difference (Polars minus Pydantic): -16.8 to +38.9 points, so the error test does not pick a winner.
- Trade-offs / what we give up:
  - The user does not know Polars yet. The plan needs hand-verified reference answers and a hand-check of about 20 golden items (Phase 2), so verification will be slower. Mitigation: learn from `docs/PHASE0_GRADING_GUIDE.md` and the official user guide, and mark every golden label that was not personally verified.
  - No candidate has the "hundreds of pages" the plan assumed (43 to 91). For Polars it is 87 pages and about 64k words.
  - Polars' API reference is generated from docstrings and is not counted. Phase 1 must build the symbol list from `py-polars` docstrings or the built reference.
  - No GitHub Discussions, so real questions come from Stack Overflow only.
  - The assistant-graded error rates are provisional until a human validates them (see D-008).
- Revisit if: the Phase 1 corpus is too small to be useful, the symbol list cannot be extracted reliably, or the golden set cannot be verified at an acceptable pace.

## D-002: Python tooling (uv, ruff, pytest, pre-commit, pydantic-settings)
- Date / phase: Phase 0
- Decision: uv for environments and lockfile; ruff for lint and format; pytest; pre-commit; pydantic-settings for config; hatchling build backend.
- Why: one fast tool covers install, lock and run (uv) and one covers lint and format (ruff), which keeps CI and the Makefile short. pydantic-settings gives typed env-driven config, so thresholds and paths are explicit and testable. The plan names uv and the Windows no-GPU setup needs a reproducible lockfile.
- Alternatives considered: pip + venv (no lockfile, slower); poetry (heavier, slower resolver, no benefit here); black + flake8 + isort (three tools instead of ruff); plain env vars / dataclass config (no validation).
- Evidence: assumption; CI green on the skeleton is the only check.
- Trade-offs / what we give up: uv and ruff are younger tools with faster-moving CLIs.
- Revisit if: a dependency needed later does not resolve under uv.

## D-003: httpx as the only HTTP client
- Date / phase: Phase 0
- Decision: use `httpx` for the Stack Exchange API and Groq's chat endpoint.
- Why: both are plain HTTPS JSON calls. httpx ships `MockTransport`, so the Groq cache and retry code is unit-tested offline with no key and no network.
- Alternatives considered: `requests` (no built-in mock transport, would need an extra mocking library); the official `groq` SDK (extra dependency to wrap a single POST, and it hides the request we hash for the cache).
- Evidence: assumption. `tests/test_selection.py::test_chat_caches_on_disk` shows the mock approach works.
- Trade-offs / what we give up: we maintain our own 429 retry loop.
- Revisit if: we need streaming or tool-calling features the SDK handles better.

## D-004: Selection test measures (shallow clone, word counts, SO and Discussions counts)
- Date / phase: Phase 0
- Decision: `git clone --depth 1` of each docs repo; count `.md/.mdx/.rst` pages and words (frontmatter stripped); count Stack Overflow questions with the library tag and an accepted answer; count total and answered GitHub Discussions via GraphQL.
- Why: the phase only needs size, license and question availability, so history is waste. An accepted answer is a human-verified reference, which is what the golden set needs. Pages over 100 words separate real content from stubs and redirects.
- Alternatives considered: full clone (slow, no benefit); counting all SO questions (many have no verified answer, so they cannot become golden items); scraping Issues (noisier than Discussions and Stack Overflow, and many are bug reports, not usage questions).
- Evidence: results/selection/docs_stats.json and questions.json.
- Clarification (2026-10-11): acceptance is a reference-selection signal, not technical validation; the original "human-verified" wording is superseded by the verification requirements in D-008. Counts remain upper bounds on usable questions.
- Trade-offs / what we give up: tag-based counts include off-topic questions (one sampled Pydantic question was about uvicorn). Counts are upper bounds on usable questions.
- Revisit if: the library's docs are generated at build time, so source files undercount (this applies to Polars' API reference).

## D-005: Contamination test design
- Date / phase: Phase 0
- Decision: for each surviving candidate, sample 20 Stack Overflow questions (accepted answer, body up to 2,000 characters, created since 2024-06-01, fixed seed 0 from the 100 newest) and ask the plain Groq 70B model at temperature 0 with no retrieval. A human grades each answer correct, outdated or wrong against the accepted answer. The contamination rate is (outdated + wrong) / graded.
- Why: recent questions are the ones most likely to touch behaviour the model has not seen, which is the gap retrieval must fill. A fixed seed and cached calls make the sample and answers reproducible. Human grading is the plan's requirement, since an LLM judge could share the same blind spots as the model being tested.
- Alternatives considered: random sample over all years (dominated by old, well-known behaviour, so it would understate the gap); LLM-as-judge grading (cheaper but circular here); more than 20 questions (more precise, but costs human time per candidate).
- Evidence: original human-review plan superseded for this selection pass by the user's request for assistant grading (2026-10-11); see D-008 and [results](results/selection/grading_report.md). Model choice was superseded by D-007, which used gpt-oss-120b. The sample size remains 20 per candidate, before scope exclusions. Human validation is still needed before these become trusted evaluation labels.
- Trade-offs / what we give up: the date cut-off is a guess about the model's training window; the pool of 100 newest questions is a convenience sample.
- Revisit if: the two finalists land within noise of each other. Then extend to 40 questions.

## D-006: Disk-cached LLM client
- Date / phase: Phase 0
- Decision: every chat call goes through `CachedChat`, keyed by SHA-256 of (model, messages, temperature), stored as JSON under `.cache/llm/`.
- Why: CLAUDE.md requires cached LLM calls. It keeps the Groq free tier usable, makes re-runs free and makes results reproducible.
- Alternatives considered: in-memory memoization (lost between runs); sqlite (no benefit at this scale, harder to inspect).
- Evidence: assumption; covered by the cache test.
- Trade-offs / what we give up: changing the prompt or model creates new entries, so stale files accumulate (the cache directory is git-ignored and safe to delete).
- Revisit if: the cache grows large during teacher-data generation in Phase 6.

## D-007: Groq model for the contamination test (and default chat model)
- Date / phase: Phase 0
- Decision: `openai/gpt-oss-120b`, set as `groq_model` in config.
- Why: it is the strongest production-status chat model on the account's live model list. A stronger, newer plain model is the conservative choice for contamination: if it still answers Polars or Pydantic questions wrongly, retrieval has real headroom. Production status means it is less likely to be withdrawn mid-project than a preview model.
- Alternatives considered:
  - `llama-3.3-70b-versatile` (my first default): not on the account's live list (`GET /openai/v1/models`, 2026-10-11), although Groq's public docs page still showed it. Cannot be used.
  - `openai/gpt-oss-20b`: weaker, no reason to prefer it for the baseline.
  - `qwen/qwen3.8-27b`: preview, may be discontinued at short notice.
- Evidence: live model list shows 11 models, only three general chat models (gpt-oss-120b, gpt-oss-20b, qwen3.8-27b). One smoke call returned a clean answer in the content field.
- Trade-offs / what we give up: gpt-oss is a reasoning model, so calls use hidden reasoning tokens against free-tier limits and latency is higher. Its training cutoff is later than Llama 3.3's, so the measured contamination may be lower than for an older model.
- Revisit if: the judge in Phase 2 needs a different model (compare against gpt-oss-20b and qwen), or Groq withdraws this model. Note: the plan's Llama 3 8B baseline is not available on Groq and moves to Ollama (Phase 5).

## D-008: Assistant grading, scope exclusions and evidence checks
- Date / phase: 2026-10-11 / Phase 0
- Decision: review all 40 existing answers as the assistant, label every note with reviewer and date, and preserve the CSV schema. Grade substantive correctness of the whole answer: `correct` for a workable answer with no material contradiction; `outdated` for a formerly valid approach broken by the relevant API version; `wrong` for invented APIs, failing code, or material false claims. A harmless display typo or omission of a better solution alone does not fail a working answer. Questions requiring another library's docs are explicitly excluded with a blank verdict and an `Excluded:` note.
- Why: the user requested grading now. The assistant is scoped to one library's own docs; counting plotting, FastAPI endpoint behavior or editor setup as Pydantic/Polars failures would distort the selection test. Official documentation, pinned source and focused execution provide stronger evidence than agreement with a forum answer alone.
- Alternatives considered:
  - Wait for human labels: preferred for final trusted evaluation, but does not carry out the user's requested assistant review.
  - Accepted-answer agreement only: an accepted answer can be old or wrong, and a different solution may work.
  - Ask the answer-generating model to score itself: shares possible blind spots and consumes more free-tier calls; use explicit API and execution checks instead.
  - Count every tagged question: rejected because six depend on behavior outside the candidate docs. Do not replace excluded questions in this pass, which would change the sample after seeing its answers.
  - Grade only the first code block: would miss materially broken alternatives and false API explanations. State borderline judgments in the notes.
- Evidence: [Polars CSV](results/selection/verdicts_polars.csv), [Pydantic CSV](results/selection/verdicts_pydantic.csv), [runtime observations](results/selection/grading_checks.json), and [review report](results/selection/grading_report.md). Polars: 3 correct, 2 outdated, 14 wrong, 1 excluded. Pydantic: 4 correct, 1 outdated, 10 wrong, 5 excluded. CSV question IDs, links and order were preserved.
- Trade-offs / what we give up: these are assistant judgments, not independent human grades. Execution used isolated Polars 1.34.0 (an explicitly asked version) and the available Pydantic 2.13.5/NumPy 2.3.5 on Python 3.12.14; it is not a historical version matrix. Those packages are grading tools, not project dependencies. Database integration, mypy and claimed speedups were not tested. A serializer re-entry guard replaced an unguarded check that crashed. Source snapshots and live docs supplement the runtime checks. The spreadsheet artifact tool edited only the two grading columns; a manual CSV writer retained the required CSV format because the tool exposes workbook rather than CSV export.
- Revisit if: a human disagrees with a verdict, the exact historical runtime changes a result, or replacements are needed to restore 20 eligible questions per candidate. Keep the earlier grades and report the revision.

## D-009: Reproducible uncertainty for the Phase 0 grades
- Date / phase: 2026-10-11 / Phase 0
- Decision: report (wrong + outdated) / eligible questions and each category rate with 95% percentile bootstrap intervals. Resample whole question verdicts 10,000 times, seed 0; compare the two libraries with independent resampling, seed 1. Record exclusions separately, input hashes, source commits, runtime versions and reviewer provenance. Rebuild via `python -m devdocs_rag.selection.grading`.
- Why: the plan requires bootstrap uncertainty, and these small samples need visible intervals. Questions are the scoring unit. The libraries have different questions, so paired resampling would invent a correspondence. Fixed seeds and hashes make this report repeatable on CPU without any LLM calls.
- Alternatives considered:
  - Point estimates alone: hide the large sampling uncertainty.
  - Paired bootstrap: reserved for configurations answering the same questions in later phases.
  - Wilson/exact binomial intervals: useful sensitivity checks, but this project explicitly asks for bootstrap intervals; the small-sample limitation is stated.
  - 1,000 resamples: cheaper but less stable at the percentile endpoints; 100,000: more CPU work without fixing small-sample or reviewer uncertainty. 10,000 is an assumption for an inexpensive selection report; revisit with a resample-count sensitivity check if the choice depends on an endpoint.
  - NumPy/SciPy bootstrap: unnecessary dependencies for 34 labels; Python's standard library suffices.
- Evidence: [JSON report](results/selection/grading_report.json). Bad-rate difference, Polars minus Pydantic: 10.9 percentage points, 95% CI -16.8 to 38.9. Zero is inside the interval; no statistical winner is claimed.
- Trade-offs / what we give up: intervals condition on the recorded grades and convenience sample. They do not measure reviewer uncertainty or guarantee coverage at these sample sizes. The module rebuilds summary statistics, not the documentation review or snippet executions. This selection script is not the Phase 2 eval harness or a scored RAG baseline.
- Revisit if: labels change, more questions are added, or a decision is sensitive to bootstrap settings. Use paired comparisons once configurations share a fixed golden set.

## D-010: Pin the Polars docs at release py-2.0.0
- Date / phase: 2026-10-11 / Phase 1
- Decision: clone `pola-rs/polars` at tag `py-2.0.0` (commit `22a147de3d2bb2e44b97338a2510816c7105c9f2`); `library_version = 2.0.0` on every chunk. Settings: `docs_tag`, `library_version`.
- Why: it is the current stable release, so the corpus matches the docs a developer reads today. 2.0 has breaking changes (new streaming default, removed deprecated APIs), which a model trained on 1.x often gets wrong; that is where retrieval should help most. A tag plus commit hash makes the corpus reproducible.
- Alternatives considered: latest 1.x (`py-1.44.2`): matches the era of most sampled Stack Overflow questions, but is no longer what the docs site shows. `main`: moves daily, not reproducible. Both 1.x and 2.0 in one index: doubles the corpus and needs the version filter of Phase 4.4 before it is safe.
- Evidence: assumption. The first error grading ran snippets on Polars 1.34.0, so some golden questions will describe 1.x behaviour that 2.0 changed.
- Trade-offs / what we give up: accepted answers about 1.x may not match the 2.0 docs. These become the plan's "version-sensitive" question type; the upgrade guides are in the corpus for them.
- Revisit if: too few Stack Overflow questions map onto 2.0 pages in Phase 2. Then add 1.44.2 as a second pinned version and test the version filter.

## D-011: Guide-page scope and parsing rules
- Date / phase: 2026-10-11 / Phase 1
- Decision: include `docs/source/user-guide/**` and `docs/source/releases/upgrade/**` (77 pages). Resolve `{{code_block(...)}}` and `{{ code_header(...) }}` macros and `--8<--` snippet includes to the real Python snippet text (sections cut at `# --8<-- [start:x]` markers). Drop `exec="on"` blocks, Rust tabs and snippets, images, HTML tags, icons and attribute lists. Keep Python tabs and admonitions (as `**Note:**`-style labels). Link URLs are dropped, link text kept. Record the macro's API names as `api_refs` on the page.
- Why: the Polars docs hold no inline code; examples live in separate `.py` files pulled in at build time. Without resolving them the corpus is prose saying "see the example below" with no example, which would hurt exactly the code questions we want to answer. Execution output is not stored in the source, and Rust would add noise to Python questions. Macro calls are parsed with Python's `ast` module, so every argument spelling works.
- Alternatives considered: raw Markdown chunking (no code at all); rendering the site with mkdocs and scraping HTML (needs the full docs toolchain, executes code, brittle); keeping Rust tabs (answers are Python-only); keeping execution output by running the snippets ourselves (adds a 290-block execution step and version-dependent output; maybe later).
- Evidence: parser leak check finds no `{{`, `--8<--`, `exec=` or tab/admonition markers; tests in `tests/test_data.py`. Excluded: `development/` (contributor docs), `index.md` (marketing), `api/reference.md` (a stub pointing to the Sphinx site).
- Trade-offs / what we give up: output tables shown in the real docs are missing, so some "what does this print" questions cannot be answered from guide chunks alone (the API docstrings contain doctest outputs).
- Revisit if: golden-set failures cluster on questions that need example output.

## D-012: Chunking strategy and size
- Date / phase: 2026-10-11 / Phase 1
- Decision: split on Markdown headings and keep the heading trail as `section_path`. Fenced code blocks are atomic and are merged with the paragraph directly before them. Pack paragraphs greedily up to `chunk_max_tokens = 300`. Over-long prose is split at sentence boundaries, then at line boundaries; over-long tables are split by rows with the header repeated; a code block over the cap stays whole. A trailing chunk under 40 tokens merges into the previous one if it fits. No overlap. Chunk id = first 16 hex chars of SHA-256 over doc path, section path and text. Token count is an approximation (words and punctuation, runs of repeated punctuation counted once).
- Why: documentation has real structure, so cutting on headings keeps each chunk about one topic and gives a natural citation anchor. Code without its introduction (or cut in half) is useless to a reader and to an LLM. Overlap exists to repair arbitrary cuts; heading and paragraph boundaries do not need it. The cap is the plan's starting point (about 300 tokens); it also stays near common small-encoder input limits, which matters because encoders truncate silently. The token counter is a placeholder because the real tokenizer depends on the encoder chosen in Phase 4.
- Alternatives considered: fixed-size windows with overlap (cut code and sentences in half, ignore headings); sentence-level chunks (too small, lose the surrounding explanation); a general recursive character splitter (respects paragraphs but not code fences or headings); whole-page chunks (far over encoder limits and dilute the match); semantic chunking with embeddings (extra cost and non-determinism for little gain on already well-structured docs). Existing libraries (added 2026-10-11 after review): LangChain `MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter` (both measured, below), LlamaIndex `MarkdownNodeParser` and `semchunk` (named, not measured). The in-house chunker was first written without measuring any of them.
- Structural comparison (2026-10-11, `experiments/chunker_compare.py`, `results/chunker_compare/report.json`): same 77 parsed pages, same 300-token cap, no overlap, same token counter.

  | Metric | In-house | LangChain recursive (Markdown) | LangChain header + recursive |
  |---|---|---|---|
  | Chunks | 717 | 599 | 731 |
  | Median / p90 / max tokens | 152 / 276 / 522 | 209 / 283 / 300 | 146 / 288 / 300 |
  | Over the cap | 9 | 0 | 0 |
  | Under 40 tokens | 69 | 30 | 79 |
  | Chunks with a code fence cut in half | 0 | 240 | 208 |
  | Code starting a chunk, separated from text in its section | 6 | 154 | 14 |
  | Table fragments without header | 4 | 14 | 16 |

  Reading: the belief that off-the-shelf splitters cut code fences is confirmed (28% to 40% of their chunks), and they separate code from its introduction far more often (recursive) or about as often (header + recursive, 14 vs 6). The price of the in-house design is 9 chunks over the cap (single code blocks kept whole) and a handful of header-less table fragments. This measures chunk shape only, not retrieval quality.
- Pending experiment: in Phase 4.1, add a row that swaps in the LangChain header + recursive splitter at the same cap, scored on hit@k and MRR with confidence intervals. Keep the in-house chunker only if it is not worse; otherwise replace it and delete the code.
- Evidence: assumption for the size. Result on the guide corpus: 717 chunks, median 152 tokens, 90th percentile 276, 9 chunks over the cap (all single code blocks), 69 under 40 tokens. Phase 4.1 tests other sizes and k as separate labelled experiments.
- Trade-offs / what we give up: 69 very short chunks (one-line "see X" sections) are weak retrieval units; merging them is deliberately left for Phase 4 so only one thing changes at a time. The cap is soft for code and some API chunks.
- Revisit if: the Phase 4.1 chunk-size sweep shows a different optimum, or the chosen encoder's real tokenizer disagrees with the approximation.

## D-013: API reference from introspection, with a symbol list
- Date / phase: 2026-10-11 / Phase 1
- Decision: read the names listed in `py-polars/docs/source/reference/**/*.rst` (autosummary lists, single-object directives and `automodule`), resolve each against the installed `polars==2.0.0` (including namespaces such as `Expr.str.contains`) and take its signature and docstring. Produce 1,477 symbols, saved as `symbols.json` (qualified names plus bare names), and one or more `api_reference` chunks per symbol (header = name and signature, repeated in each piece). Sphinx roles and directives are converted to plain text; `versionadded`, `deprecated` and `engine-support` are kept as readable lines. Memory addresses in default-value reprs are stripped.
- Why: the API reference is not stored as pages; the Sphinx site is built from docstrings. The rst files define exactly what counts as public, documented API, which is the right definition of "exists" for the API-validity check. Importing the real package gives accurate signatures and handles dynamic namespaces that source parsing would not. The same installed package is needed for the Phase 2 code check.
- Alternatives considered: AST-parsing the source (no install, but namespace classes and decorators make name resolution fragile); `dir()` over classes (includes private and undocumented names, so invented-but-plausible names could slip through); scraping the built Sphinx site (needs a doc build); leaving the API reference out (it is the library's main documentation, and most Stack Overflow answers are API-level).
- Evidence: `cum_sum` is in the symbol list and `cum_mean` (an invented method in the earlier grading) is not; test `test_built_symbol_list_flags_invented_api`. 8 symbols unresolved (`testing.parametric.*`, one plugin method): they need the optional `hypothesis` package. `DataSourceFormat` and `TableType` have no docstring.
- Trade-offs / what we give up: API chunks are 85% of the corpus (3,919 of 4,636), so an unfiltered index leans toward them. They carry `chunk_type = api_reference`, so Phase 4 can run guide-only, API-only and combined as separate rows. The symbol check will use bare method names as well, so a real method on the wrong class is not flagged.
- Revisit if: the API-validity check shows false positives on attribute-style names or aliases such as the `cs` import for selectors.

## D-014: Train/val/test split by page group
- Date / phase: 2026-10-11 / Phase 1
- Decision: ratios 70/10/20 by token count (`split_ratios`), seed 0 (`split_seed`). Groups: guide pages by their top-two path segments (for example `user-guide/expressions`); each upgrade guide is its own group; API symbols by the rst file name across `expressions`, `series` and `dataframe` (for example `api/string`). Guide, changelog and API groups are split separately, in a seeded hash order, filling whichever split is furthest below its target.
- Why: the plan requires related pages to stay together so the golden set is never graded on text the fine-tune saw. `Expr.str.contains` and `Series.str.contains` have near-identical docstrings, so grouping API by topic file across classes prevents leakage between train and test. Splitting per kind guarantees the test split contains guide, API and changelog chunks. Test is 20% (larger than the usual 10-15%) because the share of Stack Overflow questions that map to a docs page is not yet known. All chunks stay in the retrieval index; the split only controls which pages may feed training data and which may hold golden questions.
- Alternatives considered: random chunk-level split (leaks near-duplicates across splits); one global shuffle (can leave a kind out of test); fixed hand-picked groups (arbitrary and unreproducible); hash modulo per group (uneven sizes with so few groups).
- Evidence: chunks by split: train 3,351, val 420, test 865. Unit tests cover determinism and group integrity.
- Trade-offs / what we give up: with about 11 guide groups the guide share can drift a few points from the targets. Guide pages and API docs on the same topic can still sit in different splits.
- Revisit if: Phase 2 finds too few test chunks that answer real questions.

## D-015: Deterministic output and exact-duplicate removal
- Date / phase: 2026-10-11 / Phase 1
- Decision: sort chunks by path, section and id; write JSON with sorted keys and LF newlines; strip `at 0x...` addresses from signatures; drop chunks whose id (hence text) is repeated.
- Why: the plan requires byte-identical output. A first check found two runs differing in 147 rows because object reprs held memory addresses; the fix was verified by identical SHA-256 hashes of all four output files across two runs. Four exact duplicates (an example repeated inside a docstring) added nothing to retrieval.
- Alternatives considered: ignoring tiny differences (breaks chunk ids, so every downstream label would drift); keeping duplicates (inflates hit rates).
- Evidence: hashes of `chunks.jsonl`, `symbols.json`, `split.json`, `report.json` identical across runs.
- Trade-offs / what we give up: none significant.
- Revisit if: a dependency upgrade changes docstrings, in which case the pin and hashes change together.

## D-016: Known corpus gaps (accepted for now)
- Date / phase: 2026-10-11 / Phase 1
- Decision: Phase 1 does not include (a) the SQL reference pages under `reference/sql/` (hand-written tables of SQL functions), (b) the hand-written prose in `reference/selectors.rst` (the selector functions themselves are in the symbol list), (c) `polars.testing.parametric`, (d) Rust and other-language docs, (e) example output from executed snippets.
- Why: each needs its own parsing or an optional dependency, and none is the main source of the Python-usage questions we sampled. Recording them avoids silent holes.
- Alternatives considered: building a parser for the SQL tables now (large effort for a niche area); stopping until everything is covered (blocks the critical path).
- Evidence: assumption. None of the 20 sampled Polars questions was about SQL (checked by reading the titles).
- Trade-offs / what we give up: SQL questions and "how do selectors compose" questions will be answered from less context.
- Revisit if: golden-set failures cluster on SQL or selectors.

## D-017: langchain-text-splitters as an experiment-only dependency
- Date / phase: 2026-10-11 / Phase 1
- Decision: install `langchain-text-splitters` in a separate `experiments` dependency group (not in the default groups, not in CI). It is used only by `experiments/chunker_compare.py`.
- Why: the chunking decision (D-012) needs a comparison against an off-the-shelf splitter; LangChain's are the most widely used, and the same library supplies the Phase 4.1 retrieval comparison row. Keeping it out of the main install avoids pulling `langchain-core` and its dependencies into the product.
- Alternatives considered: LlamaIndex node parsers (heavier dependency tree, would need its own document objects); `semchunk` (token-aware but not Markdown-structure aware); copying splitter logic by hand (would not test the real library).
- Evidence: structural comparison in D-012. Retrieval comparison is pending (Phase 4.1).
- Trade-offs / what we give up: the experiment only runs with `uv run --group experiments`.
- Revisit if: the Phase 4.1 result makes LangChain the production chunker; then move it into the main dependencies and delete the in-house code.
