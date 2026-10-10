# Phase 0 assistant grading report

Reviewed 2026-10-11. Assistant grades, not independently human validated.
Model: openai/gpt-oss-120b; no retrieval. See D-008 and D-009 for the method.

| Library | Graded | Correct | Outdated | Wrong | Excluded | Bad rate (95% CI) |
|---|---:|---:|---:|---:|---:|---|
| polars | 19 | 3 | 2 | 14 | 1 | 84.2% (68.4% to 100.0%) |
| pydantic | 15 | 4 | 1 | 10 | 5 | 73.3% (53.3% to 93.3%) |

Polars minus Pydantic bad-rate difference: 10.9 percentage points (95% CI -16.8 to 38.9, independent bootstrap). The interval includes zero; this sample does not establish a winner.

Bad rate = (wrong + outdated) / graded. Explicit scope exclusions are blank verdicts with an Excluded note; they are not missing reviews. All category rates and their intervals are in grading_report.json. Rebuild with:

```bash
uv run python -m devdocs_rag.selection.grading
```

## Evidence and limits

Runtime observations: [grading_checks.json](grading_checks.json). The teaching guide explains the checks and borderline grades.

- Assistant review requested by the user; not independent human grading or a golden set.
- These rates measure answer errors, not training-data contamination or retrieval gain.
- Small convenience samples from the newest questions; no population-wide accuracy claim.
- Intervals condition on these verdicts; they do not include uncertainty in the reviewer.
- Different questions per library: the difference uses independent, not paired, resampling.
- Checks use Polars 1.34.0 and Pydantic 2.13.5, not every historical version in the questions.
- No live database, FastAPI integration, mypy run, or speed benchmark was performed.
- Serializer recursion was checked with a re-entry guard after an unguarded run crashed.
- Pinned source and live docs supplement runtime checks; live docs may move after review.
- Accepted answers are references to verify, not guaranteed correct or current answers.

## polars: every verdict

Source snapshot: `pola-rs/polars@803d71650c8496e1e8bae40ff326076a6443e1d9`.

- [1: question 79581533](https://stackoverflow.com/questions/79581533/find-pairs-of-keys-for-rows-that-have-at-least-one-property-in-common): **wrong**. Assistant review (2026-10-11): Invents list.combinations(2), which does not exist in Polars 1.34.0. Also uses removed groupby/apply APIs and a non-callable list namespace. Use a self-join on StockCode and filter ordered customer pairs.
- [2: question 79766024](https://stackoverflow.com/questions/79766024/group-by-with-polars-concatenating-values): **outdated**. Assistant review (2026-10-11): Uses the old groupby, Expr.list() aggregation and arr namespace for list values. Modern code is group_by(...).agg(pl.all().unique().str.join('|')). The explanation that agg needs expressions is right.
- [3: question 79612706](https://stackoverflow.com/questions/79612706/how-do-i-keep-both-columns-as-the-result-of-a-polars-join-with-left-on-and-right): **wrong**. Assistant review (2026-10-11): Renaming rk to lk does not preserve the right join key: the demonstrated join returns only a, lk and b. lk_right does not exist. Use coalesce=False.
- [4: question 79576828](https://stackoverflow.com/questions/79576828/get-a-grouped-sum-in-polars-but-keep-all-individual-rows): **correct**. Assistant review (2026-10-11): sum().over('a') broadcasts the grouped sums while retaining every row. The executable example gives 2, 5, 2, 5, 3 as requested.
- [5: question 79761286](https://stackoverflow.com/questions/79761286/write-database-engine-adbc-with-autocommit-false): **wrong**. Assistant review (2026-10-11): ADBC DB-API supports manual transactions and defaults autocommit to false. Polars write_database calls conn.commit() itself. The proposed SQLAlchemy workaround passes engine rather than the transaction connection and sets AUTOCOMMIT.
- [6: question 79923877](https://stackoverflow.com/questions/79923877/polars-expr-rolling-mean-with-chained-over-yields-inconsistent-results-compa): **wrong**. Assistant review (2026-10-11): Nested windows are evaluated within the outer grouping, not prohibited by a universal one-window rule. The two-step example actually returns null, 1.5, null, 1.5 ranks, unlike the claimed all-1.5 output. The apply workaround also fails.
- [7: question 79804255](https://stackoverflow.com/questions/79804255/reference-column-named-in-polars): **wrong**. Assistant review (2026-10-11): pl.col('`*`') searches for a column literally named with backticks and raises ColumnNotFoundError. Use pl.col(r'^\*$') for the literal asterisk. Direct df['*'] access is a valid alternative.
- [8: question 79725340](https://stackoverflow.com/questions/79725340/order-of-columns-in-a-plotnine-bar-plot-using-a-polars-dataframe): **excluded**. Assistant review (2026-10-11): Excluded: the required result is plotnine axis ordering. Plotnine's scales and UI behavior are outside the Polars-only docs scope. The scale_x_discrete idea is plausible but the claimed categories/output are not validated.
- [9: question 79736447](https://stackoverflow.com/questions/79736447/polars-map-batches-return-dtype-argument-for-arrays): **wrong**. Assistant review (2026-10-11): pl.Array(pl.Int8, 9) is the right dtype, but Expr.map_batches passes a Series. The proposed callback treats it as a DataFrame and accesses batch.height, raising AttributeError; it also omits alias('signals').
- [10: question 79765276](https://stackoverflow.com/questions/79765276/how-can-i-efficiently-get-both-a-column-and-a-scalar-using-polars-expressions): **wrong**. Assistant review (2026-10-11): The arithmetic works, but the answer guarantees zero allocation and deduplication across plan stages without justification, then runs another collection for the scalar. Scalar columns can materialize. Use implode() for a one-row mean plus list result if that layout is required.
- [11: question 79599115](https://stackoverflow.com/questions/79599115/how-to-filter-all-columns-in-a-polars-dataframe-by-expression): **correct**. Assistant review (2026-10-11): all_horizontal(pl.col('*').is_not_null()) produces the requested three rows. The any-null negation and drop_nulls alternatives are valid. filter also accepts multiple explicit predicates, so its single-expression wording is overbroad.
- [12: question 79783704](https://stackoverflow.com/questions/79783704/how-to-perform-sinking-lazyframes-with-diverging-queries-to-different-partitions): **wrong**. Assistant review (2026-10-11): Invents sink_parquet(partition_by=..., streaming=True) keywords for the checked version. Use a partitioning object, or lazy=True sinks with collect_all. Its claim that collect_all never shares scans also contradicts the docs.
- [13: question 79737525](https://stackoverflow.com/questions/79737525/connection-string-to-read-and-write-database-with-different-engines): **wrong**. Assistant review (2026-10-11): Uses nonexistent module-level pl.write_database and unsupported uri= write argument instead of df.write_database(connection=...). The read-only URL cannot allow writes. No live PostgreSQL/ConnectorX integration was run.
- [14: question 79766854](https://stackoverflow.com/questions/79766854/how-to-create-a-cross-table-with-percentages-in-polars): **wrong**. Assistant review (2026-10-11): The percentage expressions are usable, but the claimed output loses an input row, invents a=3, and gives the (a=0,b=1) cell as 16.67% instead of 33.33%. Actual pivot is 3 rows and counts sum to 6.
- [15: question 79661702](https://stackoverflow.com/questions/79661702/how-to-specify-relevant-columns-with-read-excel): **wrong**. Assistant review (2026-10-11): fastexcel accepts lists of indices/names, not only callbacks. Converting the tuple to a list fixes the reported dispatch issue. pl.io.xlsx.ColumnInfoNoDtype is also an invented Polars location; the type belongs to fastexcel.
- [16: question 79819187](https://stackoverflow.com/questions/79819187/polars-print-changed-values-between-2-dataframes): **wrong**. Assistant review (2026-10-11): The proposed function calls nonexistent DataFrame.is_null()/is_nan() methods and treats DataFrame.sum().sum() as a scalar. It therefore fails on the supplied mixed-type data. Compare individual Series with null-aware logic.
- [17: question 79568479](https://stackoverflow.com/questions/79568479/sink-scan-parquet-temporarily-under-the-polars-streaming-engine): **wrong**. Assistant review (2026-10-11): Calls nonexistent LazyFrame.set_streaming(True) and contradicts itself about file-like input support. delete=False plus manual cleanup is not automatic on errors; collect() also does not enforce the requested streaming execution.
- [18: question 79862254](https://stackoverflow.com/questions/79862254/get-unique-elements-in-multiple-list-columns): **correct**. Assistant review (2026-10-11): Both concatenation approaches flatten and deduplicate in Polars, producing the nine values 1, 2, 4, 5, 6, 7, 8, 9, 10. The displayed shape of 10 is a typo and the quoted speedup is unsupported; no performance benchmark was run.
- [19: question 79783956](https://stackoverflow.com/questions/79783956/how-do-i-get-polars-expr-str-json-decode-to-decode-simple-map-to-liststructk): **outdated**. Assistant review (2026-10-11): The JSON-object-to-key/value-list conversion is a viable workaround, but Expr.apply was renamed to map_elements and is absent in the question's Polars 1.34.0. Replace it with map_elements(..., return_dtype=desired_type). json_decode also handles other JSON shapes with matching dtypes.
- [20: question 79621854](https://stackoverflow.com/questions/79621854/compute-cumulative-mean-std-on-polars-dataframe-using-over): **wrong**. Assistant review (2026-10-11): Invents Expr.cum_mean() and Expr.cum_std(), absent in Polars 1.34.0. Use cumulative sum/count or rolling_mean/rolling_std with a sufficiently large window and min_samples=1 within each group.

### Official references

- [join](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.join.html)
- [list APIs](https://docs.pola.rs/api/python/stable/reference/expressions/list.html)
- [map_batches](https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.map_batches.html)
- [sinks](https://docs.pola.rs/user-guide/lazy/sources_sinks/)
- [ADBC transactions](https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html)

## pydantic: every verdict

Source snapshot: `pydantic/pydantic@68a839f0712c367f17be497b6850ebcb6825d76c`.

- [1: question 78953814](https://stackoverflow.com/questions/78953814/i-cant-run-correctly-a-uvicorn-server-on-vscode-versions3-9-2-64-bit-among-new): **excluded**. Assistant review (2026-10-11): Excluded: Python interpreter selection, VS Code imports and FastAPI routing are the actual issues. These are outside a Pydantic-docs assistant's scope.
- [2: question 78920271](https://stackoverflow.com/questions/78920271/is-there-a-best-practice-for-defining-optional-fields-in-pydantic-models): **wrong**. Assistant review (2026-10-11): The recommended int | None = None declaration is right, but int = None does not accept an explicitly supplied None in v2. The answer also falsely says v1 requiredness was identical; v1 Optional without a default could be omitted.
- [3: question 79790056](https://stackoverflow.com/questions/79790056/how-to-use-pydantic-field-in-another-field-for-serialization-deserialization-pur): **wrong**. Assistant review (2026-10-11): The complete NumPy model lacks arbitrary_types_allowed and fails schema generation. ValidationInfo.data holds earlier validated fields, not the entire raw input. Re-parsing its serialized combined array would append the path array again, contradicting its round-trip claim.
- [4: question 79549000](https://stackoverflow.com/questions/79549000/pydantic-object-self-validation): **correct**. Assistant review (2026-10-11): Dumping and validating the raw fields does validate the supplied invalid instances. The answer misses the cleaner revalidate_instances='always' option and overstates the default fast path. obj1 has an invalid default id, rather than a missing id.
- [5: question 79241135](https://stackoverflow.com/questions/79241135/pydantic-vs-python-3-13-0-no-module-named-typing-extensions): **wrong**. Assistant review (2026-10-11): Installing typing-extensions in the active environment is sensible, but it is a mandatory dependency in Pydantic 2.10.2, not optional on Python 3.12+. The claimed guarded-import fix in 2.10.3 is unsupported by the versioned package metadata.
- [6: question 79245015](https://stackoverflow.com/questions/79245015/pydantic-objects-as-elements-in-a-polars-dataframe-get-automatically-converted-t): **excluded**. Assistant review (2026-10-11): Excluded: the behavior being tested is Polars dtype inference and map_batches, even though its values happen to be Pydantic instances. This belongs in a Polars evaluation, not the Pydantic-docs score.
- [7: question 79372245](https://stackoverflow.com/questions/79372245/how-to-build-pydantic-models-that-do-not-produce-nesting-on-serialization): **outdated**. Assistant review (2026-10-11): Gives Pydantic v1 __root__ and custom-validator patterns. A v2 BaseModel with __root__ raises TypeError; use RootModel[str] for the requested scalar serialization.
- [8: question 78950017](https://stackoverflow.com/questions/78950017/python-pydantic-serialiser-transform-in-other-model): **wrong**. Assistant review (2026-10-11): A plain model_serializer calling self.model_dump() re-enters itself. The instrumented check detects recursive serialization. It also never converts resourceid to str and leaves the required name entry out of attributes. Use a wrap serializer and its handler.
- [9: question 78753126](https://stackoverflow.com/questions/78753126/how-to-clear-pydantic-object-to-default-values-reset-to-defaults): **correct**. Assistant review (2026-10-11): Resetting fields on the existing instance preserves external references, and the sample assertion passes. It creates a temporary default instance, so it assumes all fields have defaults. It does not clear model_fields_set; instance-level field access is deprecated in recent v2.
- [10: question 79499893](https://stackoverflow.com/questions/79499893/cleanly-initialize-one-model-from-another-model-without-using-model-dump): **correct**. Assistant review (2026-10-11): The from_attributes=True approach with an explicit number default is a valid no-dump alternative for this toy case. It changes the model's default, and model_copy(update=...) skips update validation. A better unchanged-model option is dict(external_data) merged with number.
- [11: question 79259261](https://stackoverflow.com/questions/79259261/generic-of-class-ignored-by-generic-pydantic-constructor): **wrong**. Assistant review (2026-10-11): For GetValue[int].get_value, cls is the ordinary GetValue class. cls.__orig_bases__ contains Generic[T], so the proposed helper returns T rather than int. It would work differently for a concrete subclass, which the question does not use.
- [12: question 79455366](https://stackoverflow.com/questions/79455366/allow-enum-names-as-valid-inputs-with-pydantics-validate-call): **correct**. Assistant review (2026-10-11): The generic Annotated plus BeforeValidator factory accepts 0, the enum instance, WEST, and the whitespace/case-normalized SOUTH string. All four checked calls succeed. The helper's return annotation is awkward for static checking but the runtime solution works.
- [13: question 79187373](https://stackoverflow.com/questions/79187373/how-do-i-create-a-managed-attribute-compatible-with-pydantic): **wrong**. Assistant review (2026-10-11): ValidationInfo has no model attribute, so the validator cannot update info.model._parent_ref. The public parent field also retains a strong reference, defeating weak-reference ownership. A decorated property setter is still a function call; the explanation misses generic binding.
- [14: question 79622540](https://stackoverflow.com/questions/79622540/how-to-send-receive-binary-data-to-an-web-application-in-python): **excluded**. Assistant review (2026-10-11): Excluded: multipart uploads and endpoint request parsing require FastAPI docs. The answer additionally makes a false Pydantic claim: plain bytes treats a JSON string as UTF-8, not automatic Base64 decoding. Use Base64Bytes or explicit decoding for that separate issue.
- [15: question 78818197](https://stackoverflow.com/questions/78818197/pydantic-settings-isnt-calling-before-validators-properly): **wrong**. Assistant review (2026-10-11): The supplied classmethod decorator order is supported. Settings JSON decoding fails before the field validator. The suggested v2 imports of BaseSettings from pydantic and pydantic.settings are invalid. Use JSON environment values or disable decoding with an appropriate settings source/NoDecode.
- [16: question 79709133](https://stackoverflow.com/questions/79709133/problem-with-multiple-query-in-view-of-fastapi-application-endpoint): **excluded**. Assistant review (2026-10-11): Excluded: the required fix concerns FastAPI query dependencies and its OpenAPI generation, outside Pydantic's docs. Bare Depends does not establish that a list field becomes the intended query parameter.
- [17: question 79509277](https://stackoverflow.com/questions/79509277/is-an-instance-of-my-pydantic-model-also-in-my-enum): **wrong**. Assistant review (2026-10-11): The member.value helper works, but putting __contains__ on the Enum subclass does not override class membership, which is controlled by EnumType/EnumMeta. The answer also wrongly claims v2 models of different non-generic classes compare equal without the user's custom equality.
- [18: question 78726520](https://stackoverflow.com/questions/78726520/swagger-api-should-not-accept-null): **excluded**. Assistant review (2026-10-11): Excluded: Swagger dropdown behavior and FastAPI Query requiredness are outside the Pydantic-docs scope. Optional/omittable is not the same as nullable, so the answer's blanket OpenAPI claim is also unreliable.
- [19: question 79726058](https://stackoverflow.com/questions/79726058/pydantic-model-validator-raise-valueerror-to-field): **wrong**. Assistant review (2026-10-11): The v2 validator's third argument is ValidationInfo, not a dict: values.get raises AttributeError. Use info.data.get. check_fields does not enable cross-field access, and the ErrorWrapper alternative is v1-only.
- [20: question 79144471](https://stackoverflow.com/questions/79144471/how-can-i-specify-the-data-structure-so-requirements-of-mypy-and-pydantic-are-sa): **wrong**. Assistant review (2026-10-11): parse_obj(data) and casting to Any are workable (parse_obj is deprecated in v2), but the TypedDict alternative still passes list[_VaultDict] where the typed constructor expects list[Vault]. Casting to that TypedDict cannot fix the reported type mismatch. Use model_validate(data).

### Official references

- [migration](https://docs.pydantic.dev/latest/migration/)
- [validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [models](https://docs.pydantic.dev/latest/concepts/models/)
- [serialization](https://docs.pydantic.dev/latest/concepts/serialization/)
- [settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [2.10.2 dependencies](https://raw.githubusercontent.com/pydantic/pydantic/v2.10.2/pyproject.toml)
- [Enum membership](https://docs.python.org/3/library/enum.html)
