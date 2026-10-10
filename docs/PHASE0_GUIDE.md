# Phase 0 Guide: choose the library and set up the repo

Status: closed (CI green on main). The key works and all 40 sampled answers have now been reviewed by the assistant at your request. See the [grading guide](PHASE0_GRADING_GUIDE.md). The library is chosen: **Polars** (D-001). CI is green on GitHub (the remote now exists). This guide explains what we did, why, the real code, and the real numbers. Every choice is recorded with alternatives in [DECISIONS.md](../DECISIONS.md).

## 0. The big idea

The whole project claims "retrieval over docs fixes the mistakes a plain LLM makes". That claim is only interesting if the plain LLM actually makes mistakes on the library we pick. If we pick a library the model knows perfectly, every later improvement shrinks to noise and the project has nothing to show.

So Phase 0 is a small experiment, not a guess. We score candidate libraries on three things and pick on evidence:

| Criterion | Question it answers | Why it matters later |
|---|---|---|
| Docs size and license | Is there enough permissive text to build a corpus? | Phase 1 chunks it; we may publish scripts based on it |
| Real questions available | Can we build a golden set from real, human-answered questions? | Phase 2 needs about 100 to 150 of them |
| Contamination | Does the plain LLM get real questions wrong or outdated? | It is the room retrieval has to improve |

## 1. Repo skeleton (done)

What was built and why each piece exists:

| Piece | Why |
|---|---|
| `pyproject.toml` + `uv.lock` | One command (`uv sync`) rebuilds the exact environment on any machine and in CI |
| `src/devdocs_rag/` package layout | Code under `src/` is imported only after install, which catches packaging mistakes early |
| `config.py` (pydantic-settings) | Paths, API key and model name come from env vars / `.env`, typed and testable. No hard-coded values |
| `ruff`, `pytest`, `pre-commit`, GitHub Actions | Same checks locally and in CI, so "works on my machine" cannot hide failures |
| `Makefile` | Short names for the common commands (`make test`, `make lint`) |
| `DECISIONS.md`, `FLOW.md` | The "why" and the "how it fits together", updated with the code |
| Branch `phase-0`, `main` untouched | CLAUDE.md rule: nothing merges to `main` without review |

Check it yourself:

```bash
uv sync && uv run ruff check . && uv run pytest
```

## 2. Selection tooling (done)

All of it lives in `src/devdocs_rag/selection/` and runs with `python -m devdocs_rag.selection <step>`.

### 2.1 The candidate list: `candidates.py`

One frozen dataclass per library: where its docs live, which Stack Overflow tag to count, which repo hosts Discussions. Keeping this as data means adding a fifth candidate is one line.

```python
Candidate("polars", "pola-rs/polars", ("docs/source",), "python-polars", "pola-rs/polars", "MIT")
```

Finding the docs paths was real work, not a lookup. Surprises:

- **LangGraph's docs are not in its own repo any more.** `langgraph/docs` holds only redirects. The pages moved to `langchain-ai/docs` under `src/oss/langgraph`. If we had counted the code repo we would have reported zero pages.
- **Polars' API reference is generated from Python docstrings**, so no hand-written API page exists in `docs/source/api`. We will deal with that in Phase 1 when we extract the symbol list.

### 2.2 Docs stats: `docs_stats.py`

Shallow-clones each docs repo (`--depth 1`: we want the latest files, not history), then counts pages and words in `.md/.mdx/.rst` files, after stripping YAML frontmatter.

```python
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def count_words(text: str) -> int:
    return len(FRONTMATTER.sub("", text).split())
```

It also records the commit hash, because later phases pin the docs to one exact commit.

Bug found on the way: the first version named each clone folder after the repo, and LangGraph's docs repo is just called `docs`, which collided with a duplicate clone. Fixed by naming folders after the candidate.

### 2.3 Question counts: `questions.py`

Two sources, both free:

- **Stack Overflow** via the Stack Exchange API: count questions with the library's tag, and how many have an accepted answer. Acceptance provides a useful reference, but it does not guarantee technical correctness or a current answer; verify it before using it in the golden set.
- **GitHub Discussions** via `gh api graphql`: total vs answered. Some repos have Discussions turned off, and the query reports that.

### 2.4 The cached LLM client: `llm.py`

Every LLM call goes through `CachedChat`. It hashes `(model, messages, temperature)`, and if that file exists on disk it returns the saved answer without calling Groq.

```python
payload = json.dumps([model, messages, temperature], sort_keys=True)
key = hashlib.sha256(payload.encode()).hexdigest()
```

Why: Groq's free tier is rate-limited, and a reproducible project must give the same answers when re-run. A unit test uses a fake HTTP server to prove the second identical call never hits the network.

### 2.5 The contamination script: `contamination.py`

What it does, in order:

1. Fetch the 100 newest Stack Overflow questions for the library that have an accepted answer, were created since 2024-06-01 and are under 2,000 characters.
2. Pick 20 with a fixed random seed, so you and I get the same 20.
3. Fetch each accepted answer.
4. Ask the plain LLM each question, no docs, temperature 0.
5. Write a grading sheet (`contamination_<name>.md`) and a CSV (`verdicts_<name>.csv`) with an empty verdict column.

Then `summarize <name>` reads the verdicts and computes `(outdated + wrong) / graded`. The assistant review report adds explicit scope exclusions, provenance and confidence intervals; rebuild it with `python -m devdocs_rag.selection.grading`.

## 3. Results so far (real numbers)

Docs, pinned at the commits stored in `results/selection/docs_stats.json`:

| Candidate | License | Pages | Pages over 100 words | Words |
|---|---|---|---|---|
| Polars | MIT | 87 | 75 | 63,824 |
| Pydantic | MIT | 91 | 51 | 82,211 |
| LangGraph | MIT | 43 | 41 | 127,445 |
| uv | Apache-2.0 OR MIT | 81 | 67 | 71,402 |

Questions, from `results/selection/questions.json`:

| Candidate | SO total | SO with accepted answer | Discussions answered |
|---|---|---|---|
| Polars | 2,836 | 1,828 | Discussions disabled |
| Pydantic | 2,390 | 1,099 | 568 |
| LangGraph | 142 | 26 | Discussions disabled |
| uv | 182 | 73 | Discussions disabled |

How to read this:

- **All four licenses are permissive.** No blocker.
- **LangGraph and uv fail the real-questions test.** 26 and 73 usable questions cannot support a 100 to 150 item golden set. They are out. (We still cannot publish their data anyway; see the license notes in `plan.md`.)
- **Polars and Pydantic pass easily**, so the contamination test decides between them.
- **No candidate has "hundreds of pages".** The plan assumed that; reality is 43 to 91. It is a corpus of roughly 60k to 130k words, which is small but workable (a few hundred to a couple thousand chunks). Worth saying plainly in the final write-up.
- **Tag-based counts are upper bounds.** One sampled Pydantic question was really about running uvicorn in VS Code. That is why a human reviews the questions.

## 4. Selection answers: reviewed

The following steps explain how the existing sheets were produced. They are already completed; rebuilding a sheet overwrites its CSV, so preserve the reviewed file before regenerating answers.

1. Create `.env` in the repo root (it is git-ignored) with:
   ```
   DEVDOCS_GROQ_API_KEY=your_key_here
   ```
   Free keys come from the Groq console. The default model is `openai/gpt-oss-120b` (see D-007). Llama models are not on the account list; check `GET /openai/v1/models` if Groq changes things.
2. Build the sheets:
   ```bash
   uv run python -m devdocs_rag.selection sheet polars
   uv run python -m devdocs_rag.selection sheet pydantic
   ```
3. Open `results/selection/contamination_polars.md`. For each of the 20 items compare the plain LLM answer to the accepted answer and write one word in `verdicts_polars.csv`:
   - `correct`: would work as given
   - `outdated`: was true for an older version, or uses an API that has since changed
   - `wrong`: just incorrect or made-up
4. Summarize:
   ```bash
   uv run python -m devdocs_rag.selection summarize polars
   ```

Current assistant grades (D-008/D-009): Polars 16/19 wrong or outdated, 84.2% (95% CI 68.4% to 100.0%); Pydantic 11/15, 73.3% (53.3% to 93.3%). Six questions were explicitly excluded because the required behavior belonged outside the candidate's docs. Every question still has a review note.

How to read the outcome: the independent-bootstrap difference interval is -16.8 to 38.9 percentage points and includes zero. No statistical winner is established. These assistant grades are preliminary; a final library choice can also use question availability, scope fit and how checkable its APIs are, with the reason recorded in D-001. The [grading guide](PHASE0_GRADING_GUIDE.md) explains the individual checks and limitations. Retrieval benefit is still unmeasured.

## 5. Exit checklist

- [x] Repo skeleton, tests and lint green locally
- [x] CI green (GitHub Actions passes on main and on the Phase 1 PR)
- [x] Docs size, license and question counts for all candidates
- [x] Preliminary assistant-reviewed error rates for the finalists, with CIs (not human validated)
- [x] D-001 finalized: Polars
