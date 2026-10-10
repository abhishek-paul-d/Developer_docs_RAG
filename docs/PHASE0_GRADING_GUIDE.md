# Phase 0 grading guide

Reviewed on 2026-10-11 at your request. All 40 answers have a review note. These are assistant grades, not independently verified human labels. Decisions D-008 and D-009 explain the method and alternatives.

## 1. What I graded

The CSVs contain identifiers, links, verdicts and notes. The question, accepted answer and model answer live in the corresponding local `contamination_*.md` sheets. I read every item, checked the library/version it needed, then checked material API and code claims against official documentation, pinned source or focused execution.

I preserved the original five CSV columns, question IDs, links and order. Each note identifies the reviewer and date. No new model answers or judge calls were generated.

| Verdict | Meaning |
|---|---|
| correct | The answer works for the question; remaining caveats are not material failures. |
| outdated | The proposed approach belonged to an older API and fails in the relevant version. |
| wrong | A substantive claim is false, an API is invented, or the proposed solution fails. |
| excluded (blank verdict) | The required behavior belongs outside the candidate library's own docs. The note says why. |

I considered the whole answer, including proposed alternatives. A working first suggestion does not make a broken alternative or material false explanation correct. A harmless shape typo or missing better solution alone does not fail a usable answer. Borderline cases are recorded rather than hidden.

An accepted Stack Overflow answer is evidence to check, not a guarantee of correctness. The source sheets and fetched question data remain ignored because their redistribution needs a separate license review.

## 2. Why six questions were excluded

| Library | Rows | Required behavior outside its docs |
|---|---|---|
| Polars | 8 | plotnine axis ordering |
| Pydantic | 1 | interpreter/editor setup and FastAPI routing |
| Pydantic | 6 | Polars dtype inference and batch mapping |
| Pydantic | 14, 16, 18 | FastAPI uploads, query dependencies and Swagger behavior |

This leaves 19 eligible Polars questions and 15 Pydantic questions. Exclusions were not replaced after seeing the answers. Ancillary mistakes are still noted, such as the false Base64 claim in Pydantic row 14, but excluded rows do not affect the error rate.

## 3. Checks that changed the grades

Checks used isolated Polars 1.34.0 and the available Pydantic 2.13.5, NumPy 2.3.5 and Python 3.12.14. These are the actual check versions, not a claim that every question specified those versions. Pinned source hashes are in the report. The isolated packages do not change the project's dependency list.

### Invented APIs: Polars rows 1, 12 and 20

The model suggested `list.combinations`, `sink_parquet(partition_by=..., streaming=True)`, `cum_mean` and `cum_std`. Those APIs/arguments do not exist in the checked runtime. A direct check is more convincing than whether the answer sounds plausible:

```python
import inspect
import polars as pl

print(hasattr(pl.col("x").list, "combinations"))  # False
print(hasattr(pl.Expr, "cum_mean"))  # False
print(inspect.signature(pl.LazyFrame.sink_parquet))
```

Rows 1 and 20 need different operations. Partitioned or multiplexed sinks need the documented sink interface. These received `wrong`, rather than `outdated`, because the answer invents the central operation.

### Code that runs but produces the wrong result: Polars row 3

Renaming the right join key does not preserve it when join coalescing drops that key:

```python
left = pl.DataFrame({"a": [1], "lk": [10]})
right = pl.DataFrame({"rk": [10], "b": [2]}).rename({"rk": "lk"})
print(left.join(right, on="lk").columns)
# ['a', 'lk', 'b']; the suggested lk_right column is absent.
```

The fix is to use the documented `coalesce=False` behavior. Row 14 similarly has usable percentage expressions but materially incorrect displayed counts and rows; its actual output is recorded in the checks file.

### Version mixing: Pydantic rows 7 and 19

Pydantic v2 uses `RootModel` rather than a v1 `__root__` field. That answer is `outdated`. A v2 field validator receives `ValidationInfo`, so treating it as a dictionary fails:

```python
from pydantic import BaseModel, field_validator


class Example(BaseModel):
    first: int
    second: int

    @field_validator("second")
    @classmethod
    def validate_second(cls, value, info):
        return value if info.data.get("first") else 0
```

Here `info.data` provides earlier validated fields. Row 19 instead calls `values.get`, which raises `AttributeError`; it mixes v2 decorators with v1 assumptions and is `wrong`.

### Working answers with caveats

- Polars row 18: both concatenation approaches work and return nine unique values. The displayed shape is a typo; the speedup claim was not benchmarked. Grade: `correct` for the requested operation.
- Pydantic row 4: dumping the fields and validating them again catches the invalid value. The answer misses `revalidate_instances='always'`, but its workaround works. Grade: `correct`.
- Pydantic row 10: `from_attributes=True` with an explicit default solves the toy example, though it changes that default; an unchanged-model alternative is mentioned in the note. Grade: `correct`.
- Pydantic row 12: the `Annotated`/`BeforeValidator` factory accepted all four supplied input forms in execution. Grade: `correct`.

Execution limits matter: no live database, FastAPI integration, mypy invocation or speed benchmark was run. Pydantic row 20's typed alternative was reviewed against its type signatures. The serializer in row 8 recursively re-enters itself; after an unguarded run crashed, an instrumented guard confirmed the re-entry without repeating the crash. That guarded observation is not a claim about the exact unguarded exception.

## 4. The results

| Library | Correct | Outdated | Wrong | Excluded | Wrong or outdated / eligible (95% CI) |
|---|---:|---:|---:|---:|---|
| Polars | 3 | 2 | 14 | 1 | 16/19 = 84.2% (68.4% to 100.0%) |
| Pydantic | 4 | 1 | 10 | 5 | 11/15 = 73.3% (53.3% to 93.3%) |

The intervals come from 10,000 question-level bootstrap resamples, seed 0. A resample draws the same number of eligible questions, with replacement, and recomputes the rate. The 2.5th and 97.5th percentiles give the reported interval. No LLM is needed for this calculation.

Polars minus Pydantic is **10.9 percentage points**, with an independent-bootstrap 95% interval of **-16.8 to 38.9** (seed 1). These are different questions, so a paired comparison would be invalid. The interval includes zero: this sample does not establish which library has a higher underlying error rate.

The large observed rates show failures worth investigating. They do not demonstrate that retrieval fixes those failures, measure training-data contamination, or establish general model accuracy. Reviewer uncertainty is not inside these intervals. Phase 2 and Phase 3 will supply the trusted evaluation set and actual retrieval comparison.

## 5. Where to inspect and reproduce the summary

- [Polars verdicts](../results/selection/verdicts_polars.csv)
- [Pydantic verdicts](../results/selection/verdicts_pydantic.csv)
- [Every verdict and official references](../results/selection/grading_report.md)
- [Machine-readable report with hashes and all category intervals](../results/selection/grading_report.json)
- [Observed execution outcomes and runtime versions](../results/selection/grading_checks.json)
- [Summary implementation](../src/devdocs_rag/selection/grading.py)

```bash
uv run python -m devdocs_rag.selection.grading
```

This validates the CSV columns, reviewer notes, unique IDs and explicit exclusions before rebuilding the reports. It repeats the statistical summary; it does not automatically redo the manual review or code checks. The legacy `summarize` command calls excluded blanks `unfilled`; the new report identifies them correctly as exclusions.

Final checks: both CSVs retain their original 20 identifiers and row order; all 40 notes identify the reviewer; 23 focused runtime observations are recorded; rebuilding the JSON and Markdown reports gives byte-identical output. The five existing tests pass, and lint and formatting checks pass. No new tests were added.

Phase 0 still needs a final library decision and a verified CI run. Neither library has been selected or advanced into corpus building in this change.
