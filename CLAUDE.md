# CLAUDE.md

Project: Developer Docs Assistant, a measured RAG system with a fine-tuned generator. Full spec in [plan.md](plan.md). Read it before starting any phase.

## Working rules

1. **Eval first.** No component changes before the eval harness exists and the baselines are scored.
2. **One change at a time.** Each ablation row changes exactly one thing.
3. **Prompt before fine-tune.** A fine-tune is kept only if it beats the best prompted baseline (paired bootstrap).
4. **Never grade on what we trained on.** Splits are by page group. Golden-set questions come from held-out (test) pages only.
5. **Real questions for the golden set.** Synthetic questions are allowed only for training data, or flagged gap-fillers in the golden set.
6. **Report uncertainty.** 95% bootstrap CIs on every metric. Never claim a win inside the noise.
7. **Report failures.** Components that don't help stay in the report.
8. **Free stack.** Groq free tier, Ollama, Colab/Kaggle. Every LLM call is cached on disk.
9. **Branch only.** Work on a branch; nothing merges to `main` without review.
10. **License first.** Check licenses before publishing anything. Publish scripts and manifests, not data, unless a license clearly allows it.

## Every method needs a reason (mandatory)

No method, model, parameter or design choice enters the repo without a written justification in `DECISIONS.md`. This covers, at minimum:

- the target library
- the chunking strategy, chunk size and overlap
- the embedding model (and why not the others in the bake-off)
- the retriever type, k, fusion method, reranker and query rewriting
- the generator model, prompt design, refusal threshold and quantization level
- the fine-tuning method, hyperparameters and training-data recipe
- every metric and the judge model
- every library or tool added as a dependency

### Required format for each decision

Add one entry per decision to `DECISIONS.md`:

```
## D-NNN: <short title>
- Date / phase:
- Decision: what we chose.
- Why: the reason, tied to this project (our docs, our questions, our constraints).
- Alternatives considered: each one, and why it lost.
- Evidence: a measured result (table, CI, file path in results/), or "assumption" if not yet measured.
- Trade-offs / what we give up:
- Revisit if: the condition that would change this decision.
```

### Rules for decisions

- **"Popular" or "standard" is not a reason.** The reason must reference our data, our constraints (CPU inference, free tier, no GPU) or a measurement.
- **Name the rejected alternatives.** "Why X" is incomplete without "why not Y and Z". For the embedding model this means the full bake-off table: quality (hit@5, MRR, recall@k with CIs), indexing time, query latency, size.
- **Chunking:** justify against alternatives (fixed-size, sentence, recursive, heading-based, heading plus code-block-aware). Show the effect on retrieval metrics when tuned in Phase 4.
- **Mark assumptions.** If a choice is made before evidence exists, label the Evidence line "assumption" and link the experiment that will confirm or overturn it. Update the entry when the result arrives, and mark the old reasoning superseded rather than deleting it.
- **Same change as the code.** The `DECISIONS.md` entry lands in the same commit/PR as the code that implements it. A PR that adds a method without an entry is incomplete.
- **Code comments stay minimal.** The reasoning lives in `DECISIONS.md`, not in comments. A short comment may point to the decision ID (e.g. `# see D-012`).
- **Config values need reasons too.** Any non-default value in config (chunk cap, k, thresholds, temperature) traces to a decision ID.

### Where the reasoning shows up

- `DECISIONS.md`: the full entry (source of truth).
- `docs/PHASEn_GUIDE.md`: a teaching write-up that explains each choice with real code and real numbers.
- `README.md`: the final "why" for each major choice, plus the "what didn't help" section.
- Model card: why this base model, data recipe and hyperparameters.

## Living docs

- `DECISIONS.md` and `FLOW.md` are updated in the same change as the code.
- Each phase ends with `docs/PHASEn_GUIDE.md` containing real code and real numbers.
- Prune superseded entries only in the Phase 8 final pass; until then mark them superseded.

## Fine-tuning rule

- Fine-tuning is done in `.ipynb` notebooks only (`notebooks/`). No `.py` for that stage.
- Every code cell is preceded by a markdown cell explaining what the cell does and why.
- Training runs on Colab/Kaggle (no local GPU). Reference setup: `D:\Banking_FInetuning`.
- Training data comes from train-split pages only. Filters: verbatim-quote check, API names exist in the symbol list, second verification pass.

## Code conventions

- Package: `src/devdocs_rag/`. Python managed with `uv`. Config via pydantic-settings.
- Lint and format with `ruff`; tests with `pytest`; `pre-commit` and GitHub Actions CI must pass.
- Deterministic outputs: same inputs give byte-identical chunk IDs and corpus.
- Every eval run writes `results/<config>/report.json` and `report.md`, including the pinned library version and commit hash.
- Never commit data under `data/`, secrets, or `.env`.

## Definition of done for a change

- [ ] Tests and `ruff check` pass
- [ ] `DECISIONS.md` entry added or updated, with alternatives and evidence
- [ ] `FLOW.md` updated if the pipeline changed
- [ ] Results (with CIs) saved in `results/` if a metric could move
- [ ] Phase guide updated at phase end
