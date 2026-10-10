import csv
import html
import random
import re
from collections import Counter
from datetime import UTC, datetime

import httpx

from devdocs_rag.config import settings
from devdocs_rag.llm import CachedChat
from devdocs_rag.selection.candidates import by_name
from devdocs_rag.selection.questions import SE_API

SAMPLE_SIZE = 20
SEED = 0
FROM_DATE = int(datetime(2024, 6, 1, tzinfo=UTC).timestamp())
POOL_SIZE = 100
MAX_BODY_CHARS = 2000
VERDICTS = ("correct", "outdated", "wrong")

SYSTEM_PROMPT = (
    "You are a developer assistant. Answer the question about {library} as accurately as you can, "
    "with a short explanation and code if needed."
)


def html_to_text(raw: str) -> str:
    text = re.sub(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", r"\n```\n\1\n```\n", raw, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def fetch_pool(tag: str, client: httpx.Client) -> list[dict]:
    resp = client.get(
        f"{SE_API}/search/advanced",
        params={
            "site": "stackoverflow",
            "tagged": tag,
            "accepted": "True",
            "fromdate": FROM_DATE,
            "sort": "creation",
            "order": "desc",
            "pagesize": POOL_SIZE,
            "filter": "withbody",
        },
    )
    resp.raise_for_status()
    items = [q for q in resp.json()["items"] if len(q["body"]) <= MAX_BODY_CHARS]
    return items


def fetch_accepted_answers(ids: list[int], client: httpx.Client) -> dict[int, str]:
    resp = client.get(
        f"{SE_API}/answers/{';'.join(map(str, ids))}",
        params={"site": "stackoverflow", "filter": "withbody"},
    )
    resp.raise_for_status()
    return {a["answer_id"]: html_to_text(a["body"]) for a in resp.json()["items"]}


def sample_questions(name: str, client: httpx.Client | None = None) -> list[dict]:
    client = client or httpx.Client(timeout=30)
    pool = fetch_pool(by_name(name).so_tag, client)
    chosen = random.Random(SEED).sample(pool, min(SAMPLE_SIZE, len(pool)))
    answers = fetch_accepted_answers([q["accepted_answer_id"] for q in chosen], client)
    return [
        {
            "question_id": q["question_id"],
            "link": q["link"],
            "title": html.unescape(q["title"]),
            "body": html_to_text(q["body"]),
            "reference": answers.get(q["accepted_answer_id"], ""),
        }
        for q in chosen
    ]


def build_sheet(name: str) -> None:
    chat = CachedChat()
    library = by_name(name).name
    questions = sample_questions(name)
    out_dir = settings.results_dir / "selection"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Contamination sheet: {name}",
        "",
        f"Grade each as one of: {', '.join(VERDICTS)}.",
        "",
    ]
    for i, q in enumerate(questions, 1):
        prompt = f"{q['title']}\n\n{q['body']}"
        q["model_answer"] = chat.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT.format(library=library)},
                {"role": "user", "content": prompt},
            ]
        )
        lines += [
            f"## {i}. {q['title']}",
            f"Source: {q['link']}",
            "",
            "### Question",
            q["body"],
            "",
            "### Accepted answer (reference)",
            q["reference"][:1500],
            "",
            "### Plain LLM answer (no retrieval)",
            q["model_answer"],
            "",
            "---",
            "",
        ]
    (out_dir / f"contamination_{name}.md").write_text("\n".join(lines), encoding="utf-8")
    with (out_dir / f"verdicts_{name}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["n", "question_id", "link", "verdict", "note"])
        for i, q in enumerate(questions, 1):
            writer.writerow([i, q["question_id"], q["link"], "", ""])


def summarize(name: str) -> dict:
    path = settings.results_dir / "selection" / f"verdicts_{name}.csv"
    with path.open(newline="", encoding="utf-8") as f:
        verdicts = [row["verdict"].strip().lower() for row in csv.DictReader(f)]
    unfilled = sum(v not in VERDICTS for v in verdicts)
    counts = Counter(v for v in verdicts if v in VERDICTS)
    graded = sum(counts.values())
    bad = counts["outdated"] + counts["wrong"]
    return {
        "name": name,
        "graded": graded,
        "unfilled": unfilled,
        **{v: counts[v] for v in VERDICTS},
        "bad_rate": bad / graded if graded else None,
    }
