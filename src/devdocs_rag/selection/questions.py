import json
import subprocess

import httpx

from devdocs_rag.config import settings
from devdocs_rag.selection.candidates import CANDIDATES, Candidate

SE_API = "https://api.stackexchange.com/2.3"

DISCUSSIONS_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    hasDiscussionsEnabled
    all: discussions { totalCount }
    answered: discussions(answered: true) { totalCount }
  }
}
"""


def so_counts(tag: str, client: httpx.Client | None = None) -> dict:
    client = client or httpx.Client(timeout=30)
    base = {"site": "stackoverflow", "tagged": tag, "filter": "total"}
    total = client.get(f"{SE_API}/search/advanced", params=base).json()["total"]
    accepted = client.get(f"{SE_API}/search/advanced", params={**base, "accepted": "True"}).json()[
        "total"
    ]
    return {"tag": tag, "so_total": total, "so_accepted": accepted}


def discussion_counts(repo: str) -> dict:
    owner, name = repo.split("/")
    out = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={DISCUSSIONS_QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
        ],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        return {"discussions_repo": repo, "error": out.stderr.strip()}
    repo_data = json.loads(out.stdout)["data"]["repository"]
    return {
        "discussions_repo": repo,
        "discussions_enabled": repo_data["hasDiscussionsEnabled"],
        "discussions_total": repo_data["all"]["totalCount"],
        "discussions_answered": repo_data["answered"]["totalCount"],
    }


def candidate_counts(c: Candidate) -> dict:
    return {"name": c.name, **so_counts(c.so_tag), **discussion_counts(c.discussions_repo)}


def run() -> list[dict]:
    rows = [candidate_counts(c) for c in CANDIDATES]
    out = settings.results_dir / "selection" / "questions.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows
