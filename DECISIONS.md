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
