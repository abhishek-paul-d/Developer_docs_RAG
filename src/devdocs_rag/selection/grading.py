"""Rebuild the assistant's Phase 0 summary from reviewed CSVs; see D-008/D-009."""

import csv
import hashlib
import json
import random
from pathlib import Path

from devdocs_rag.config import settings

RESAMPLES = 10_000
SEED = 0
VERDICTS = ("correct", "outdated", "wrong")
SOURCES = {
    "polars": {
        "join": "https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.join.html",
        "list APIs": "https://docs.pola.rs/api/python/stable/reference/expressions/list.html",
        "map_batches": "https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.map_batches.html",
        "sinks": "https://docs.pola.rs/user-guide/lazy/sources_sinks/",
        "ADBC transactions": "https://arrow.apache.org/adbc/current/python/api/adbc_driver_manager.html",
    },
    "pydantic": {
        "migration": "https://docs.pydantic.dev/latest/migration/",
        "validators": "https://docs.pydantic.dev/latest/concepts/validators/",
        "models": "https://docs.pydantic.dev/latest/concepts/models/",
        "serialization": "https://docs.pydantic.dev/latest/concepts/serialization/",
        "settings": "https://docs.pydantic.dev/latest/concepts/pydantic_settings/",
        "2.10.2 dependencies": "https://raw.githubusercontent.com/pydantic/pydantic/v2.10.2/pyproject.toml",
        "Enum membership": "https://docs.python.org/3/library/enum.html",
    },
}
LIMITATIONS = [
    "Assistant review requested by the user; not independent human grading or a golden set.",
    "These rates measure answer errors, not training-data contamination or retrieval gain.",
    "Small convenience samples from the newest questions; no population-wide accuracy claim.",
    "Intervals condition on these verdicts; they do not include uncertainty in the reviewer.",
    "Different questions per library: the difference uses independent, not paired, resampling.",
    "Checks use Polars 1.34.0 and Pydantic 2.13.5, not every historical version in the questions.",
    "No live database, FastAPI integration, mypy run, or speed benchmark was performed.",
    "Serializer recursion was checked with a re-entry guard after an unguarded run crashed.",
    "Pinned source and live docs supplement runtime checks; live docs may move after review.",
    "Accepted answers are references to verify, not guaranteed correct or current answers.",
]


def interval(values: list[float]) -> list[float]:
    ordered = sorted(values)

    def percentile(p: float) -> float:
        index = (len(ordered) - 1) * p
        lower = int(index)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

    return [percentile(0.025), percentile(0.975)]


def summarize_review(name: str, directory: Path, pin: dict) -> tuple[dict, list[float]]:
    path = directory / f"verdicts_{name}.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["n", "question_id", "link", "verdict", "note"]:
            raise ValueError(f"Unexpected CSV columns: {path}")
        rows = list(reader)
    if len({row["question_id"] for row in rows}) != len(rows):
        raise ValueError(f"Duplicate question IDs: {path}")
    for row in rows:
        if row["verdict"] not in (*VERDICTS, ""):
            raise ValueError(f"Unknown verdict: {row}")
        if not row["note"].startswith("Assistant review (2026-10-11):"):
            raise ValueError(f"Missing reviewer provenance: {row['question_id']}")
        if not row["verdict"] and "Excluded:" not in row["note"]:
            raise ValueError(f"Unreviewed blank verdict: {row['question_id']}")
    eligible = [row["verdict"] for row in rows if row["verdict"]]
    if not eligible:
        raise ValueError(f"No eligible questions: {path}")
    rng = random.Random(SEED)
    draws = {key: [] for key in (*VERDICTS, "bad")}
    for _ in range(RESAMPLES):
        sample = rng.choices(eligible, k=len(eligible))
        for key in VERDICTS:
            draws[key].append(sample.count(key) / len(sample))
        draws["bad"].append(1 - sample.count("correct") / len(sample))
    counts = {key: eligible.count(key) for key in VERDICTS}
    counts["bad"] = counts["outdated"] + counts["wrong"]
    result = {
        "name": name,
        "total_reviewed": len(rows),
        "graded": len(eligible),
        "excluded": len(rows) - len(eligible),
        "counts": counts,
        "metrics": {
            key: {"value": count / len(eligible), "ci95": interval(draws[key])}
            for key, count in counts.items()
        },
        "csv": path.as_posix(),
        "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "docs_pin": pin,
        "sources": SOURCES[name],
        "rows": rows,
    }
    return result, draws["bad"]


def percentage(metric: dict) -> str:
    low, high = metric["ci95"]
    return f"{metric['value']:.1%} ({low:.1%} to {high:.1%})"


def run() -> None:
    directory = settings.results_dir / "selection"
    pins = {
        item["name"]: item
        for item in json.loads((directory / "docs_stats.json").read_text(encoding="utf-8"))
    }
    polars, _ = summarize_review("polars", directory, pins["polars"])
    pydantic, _ = summarize_review("pydantic", directory, pins["pydantic"])
    rng = random.Random(SEED + 1)
    samples = []
    for _ in range(RESAMPLES):
        rates = []
        for result in (polars, pydantic):
            eligible = [r["verdict"] for r in result["rows"] if r["verdict"]]
            sample = rng.choices(eligible, k=len(eligible))
            rates.append(1 - sample.count("correct") / len(sample))
        samples.append(rates[0] - rates[1])
    difference = {
        "value": polars["metrics"]["bad"]["value"] - pydantic["metrics"]["bad"]["value"],
        "ci95": interval(samples),
    }
    checks_path = directory / "grading_checks.json"
    report = {
        "review_date": "2026-10-11",
        "reviewer": "assistant",
        "human_validated": False,
        "answer_model": "openai/gpt-oss-120b (D-007)",
        "bootstrap": {"resamples": RESAMPLES, "seed": SEED, "difference_seed": SEED + 1},
        "checks_file": checks_path.as_posix(),
        "checks_sha256": hashlib.sha256(checks_path.read_bytes()).hexdigest(),
        "runtime_versions": {
            key: value
            for key, value in json.loads(checks_path.read_text(encoding="utf-8")).items()
            if key != "checks"
        },
        "candidates": [polars, pydantic],
        "bad_rate_difference_polars_minus_pydantic": difference,
        "limitations": LIMITATIONS,
    }
    (directory / "grading_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Phase 0 assistant grading report",
        "",
        "Reviewed 2026-10-11. Assistant grades, not independently human validated.",
        "Model: openai/gpt-oss-120b; no retrieval. See D-008 and D-009 for the method.",
        "",
        "| Library | Graded | Correct | Outdated | Wrong | Excluded | Bad rate (95% CI) |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for result in (polars, pydantic):
        c = result["counts"]
        lines.append(
            f"| {result['name']} | {result['graded']} | {c['correct']} | {c['outdated']} | "
            f"{c['wrong']} | {result['excluded']} | {percentage(result['metrics']['bad'])} |"
        )
    lines += [
        "",
        f"Polars minus Pydantic bad-rate difference: {100 * difference['value']:.1f} "
        f"percentage points (95% CI {100 * difference['ci95'][0]:.1f} to "
        f"{100 * difference['ci95'][1]:.1f}, independent bootstrap). The interval includes zero; "
        "this sample does not establish a winner.",
        "",
        "Bad rate = (wrong + outdated) / graded. Explicit scope exclusions are blank verdicts "
        "with an Excluded note; they are not missing reviews. All category rates and their "
        "intervals are in grading_report.json. Rebuild with:",
        "",
        "```bash",
        "uv run python -m devdocs_rag.selection.grading",
        "```",
        "",
        "## Evidence and limits",
        "",
        "Runtime observations: [grading_checks.json](grading_checks.json). "
        "The teaching guide explains the checks and borderline grades.",
        "",
        *[f"- {item}" for item in LIMITATIONS],
    ]
    for result in (polars, pydantic):
        lines += ["", f"## {result['name']}: every verdict", ""]
        pin = result["docs_pin"]
        lines += [f"Source snapshot: `{pin['docs_repo']}@{pin['commit']}`.", ""]
        for row in result["rows"]:
            lines.append(
                f"- [{row['n']}: question {row['question_id']}]({row['link']}): "
                f"**{row['verdict'] or 'excluded'}**. {row['note']}"
            )
        lines += ["", "### Official references", ""]
        lines.extend(f"- [{label}]({url})" for label, url in result["sources"].items())
    (directory / "grading_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
