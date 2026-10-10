# Phase 1 Guide: the corpus

Goal: turn the Polars docs into a versioned, cleanly chunked corpus with metadata, an API symbol list and a train/val/test split. Every choice is recorded with its alternatives in [DECISIONS.md](../DECISIONS.md) (D-010 to D-016).

Run it:

```bash
uv run python -m devdocs_rag.data.pipeline     # or: make data
```

Outputs, all in `data/processed/` (git-ignored; rebuilt from the pin):

| File | What it holds |
|---|---|
| `source.json` | repo, tag, commit hash, library version |
| `chunks.jsonl` | one JSON chunk per line |
| `symbols.json` | every documented public API name (for the API-validity check) |
| `split.json` | page group -> train / val / test |
| `report.json` | counts for the run |

## 1. What a "chunk" is

A chunk is the unit the retriever finds and the generator cites. Each carries:

```
chunk_id, doc_path, section_path, url, library_version, chunk_type, group, tokens, text
```

Example `section_path`: `Basic operations > Basic arithmetic`. `chunk_type` is `prose`, `code`, `changelog` or `api_reference`.

## 2. The pin (D-010)

We pin `py-2.0.0`, commit `22a147de3d2bb2e44b97338a2510816c7105c9f2`. Polars 2.0.0 is the current stable release and made breaking changes, for example `collect()` now defaults to the streaming engine for lazy queries. A model trained mostly on 1.x often gets 2.0 behaviour wrong, which is where retrieval should help.

The cost is that some real Stack Overflow questions describe 1.x. That is the "version-sensitive" question type in the plan, and the upgrade guides (`releases/upgrade/1.md`, `2.md`) are in the corpus for it.

## 3. Surprise #1: the docs have no code in them (D-011)

Open a Polars guide page and you find this where an example should be:

```
{{code_block('user-guide/expressions/operations', 'arithmetic', ['operators'])}}
```

and this:

````
```python exec="on" result="text" session="expressions/operations"
--8<-- "python/user-guide/expressions/operations.py:arithmetic"
```
````

The examples live in separate `.py` files and are pasted in when the website is built. The text after `:` is a section name, marked in the `.py` file with `# --8<-- [start:arithmetic]` and `# --8<-- [end:arithmetic]`. Chunking the raw Markdown would give us prose that says "see the example below" with no example.

So the parser (`data/parse.py`) resolves those placeholders. The macro call is parsed with Python's own `ast` module, which handles every spelling of the arguments:

```python
call = ast.parse(f"code_block({m.group(1)})", mode="eval").body
args = [ast.literal_eval(a) for a in call.args]
```

What it does to a page:

| In the source | In the corpus |
|---|---|
| `code_block(...)` macro, snippet include | the real Python code, in a fenced block |
| `exec="on"` block (code that prints a table at build time) | dropped, output is not in the source |
| Rust tab, Rust snippet | dropped |
| `!!! warning "Careful"` | `**Careful:**` followed by the text |
| icons, HTML, images, link URLs | removed, link text kept |

Result: 77 pages, 60,422 words, and a leak check finds no leftover `{{`, `--8<--`, `exec=` or tab markers.

## 4. Chunking (D-012)

`data/chunk.py`, in order:

1. **Split on headings**, keeping the trail as `section_path`.
2. **Blocks**: paragraphs and fenced code blocks. A code block is never cut and is glued to the paragraph just before it, so an example keeps its introduction.
3. **Pack** blocks greedily up to 300 tokens.
4. Too-long prose splits at sentences, then lines. Too-long tables split by rows with the header repeated. A code block over the cap stays whole.
5. **No overlap.** Overlap repairs arbitrary cuts; heading and paragraph cuts don't need repair.
6. `chunk_id` = hash of path, section and text, so the same input always gives the same id.

Why not the usual alternatives: fixed windows cut code in half; sentence chunks lose context; whole pages are too big for a small encoder; semantic chunking adds cost and randomness to docs that already have structure.

Real numbers on the 717 guide chunks: median 152 tokens, 90th percentile 276, 9 over the cap (all single code blocks), 69 under 40 tokens. The 300 cap is a starting point; Phase 4.1 sweeps it as its own experiment.

### Bugs this step turned up

Worth knowing, because they show why we test on real data:

- **A table that would not split.** The 2.0 "removed functionality" page is one 2,715-token Markdown table. A sentence splitter cannot cut a table, so it stayed whole. Fix: split tables by row and repeat the header.
- **The token counter was wrong about dashes.** A table separator line `| ------ | ------ |` counted every dash as a token, so a normal chunk looked oversized. Fix: count a run of repeated punctuation once.

## 5. Surprise #2: the API reference is not in the repo (D-013)

`docs/source/api/reference.md` is a stub that points to a separate Sphinx site. That site is built from two things: the `.rst` index files in `py-polars/docs/source/reference/` (which names are public) and the docstrings in the Python code.

So we do the same: read the names from the `.rst` lists, then import the real `polars==2.0.0` and look each name up. This handles names like `Expr.str.contains`, where `str` is a namespace attribute:

```python
for i, part in enumerate(parts):
    obj = getattr(obj, part)
    if isinstance(obj, property) and i < len(parts) - 1:
        obj = typing.get_type_hints(obj.fget)["return"]  # the namespace class
```

Result: **1,477 symbols**, each with signature and docstring, becoming 3,919 `api_reference` chunks. Sphinx markup in the docstrings is turned into plain text; `versionadded`, `deprecated` and `engine-support` become readable lines such as `Engine support: in-memory, streaming, distributed`.

### The payoff: catching invented APIs

In the earlier grading, the plain model invented `Expr.cum_mean()`. Our symbol list says:

```
"cum_sum"  in names  -> True
"cum_mean" in names  -> False
```

That one check is the whole point of the API-validity metric in Phase 2.

Known gaps (D-016): the SQL function reference, selectors prose, `testing.parametric` (needs an optional package), Rust docs and example outputs.

A caution: API chunks are 85% of the corpus. An index that mixes everything will lean toward them. They carry their own `chunk_type`, so Phase 4 can score guide-only, API-only and combined as separate rows.

## 6. The split (D-014)

Group pages by topic, assign whole groups to a split. Details that matter:

- `Expr.str.contains` and `Series.str.contains` have near-identical docstrings. If one were in train and the other in test, the fine-tune would have seen the test answer. So API symbols are grouped by topic file across `expressions`, `series` and `dataframe`.
- Guide, changelog and API groups are split separately, so the test split holds all three kinds.
- Seeded and size-balanced, 70/10/20.

Real counts: train 3,351, val 420, test 865 chunks.

All chunks stay in the retrieval index. The split only decides which text may be used to build training data and which may hold golden-set questions.

## 7. Reproducibility (D-015) and a second bug

The plan says the same inputs must give byte-identical output. First check: two runs differed in 147 rows. Cause: some default parameter values are Python objects whose printed form contains a memory address, like `object at 0x00000235C7D72F90`, different every run. We strip addresses, sort everything, and write JSON with sorted keys. Verified: the SHA-256 of all four output files is identical across two runs.

A third catch, unrelated to the data: the first version of `.gitignore` had `data/`, which also ignored the source package `src/devdocs_rag/data/`. Those files would never have been committed. The rule is now `/data/`, which only matches the top-level folder.

## 8. Final numbers

| | |
|---|---|
| Guide pages parsed | 77 |
| API symbols | 1,477 (8 unresolved, listed in `symbols.json`) |
| Chunks | 4,636: 3,919 API, 449 prose, 83 code, 185 changelog |
| Exact duplicates removed | 4 |
| Split (chunks) | train 3,351, val 420, test 865 |
| Tests | 17 passing, including parsing, chunking, split and the `cum_mean` check |

## 9. Exit checklist

- [x] Docs pinned and commit recorded
- [x] Parse resolves code, tabs, admonitions
- [x] Structure-aware chunking with metadata
- [x] API symbol list and API chunks
- [x] Split manifest by page group
- [x] Two runs give identical hashes
- [x] Counts in `report.json`
- [ ] `make data` on a machine with `make` (not installed on this Windows box; the same command runs directly with `uv run`)

Next, Phase 2: build the golden set from real Stack Overflow questions mapped onto the test-split chunks, and the eval harness that scores retrieval, faithfulness, refusal, citation validity, API validity and code checks with bootstrap intervals.
