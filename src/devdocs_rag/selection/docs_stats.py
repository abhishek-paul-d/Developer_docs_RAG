import json
import re
import subprocess
from pathlib import Path

from devdocs_rag.config import settings
from devdocs_rag.selection.candidates import CANDIDATES, Candidate

DOC_SUFFIXES = {".md", ".mdx", ".rst"}
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
MIN_REAL_PAGE_WORDS = 100


def clone_dir(c: Candidate) -> Path:
    return settings.data_dir / "raw" / "selection" / c.name


def ensure_clone(c: Candidate) -> Path:
    target = clone_dir(c)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--depth",
                "1",
                f"https://github.com/{c.docs_repo}",
                str(target),
            ],
            check=True,
        )
    return target


def head_commit(repo_dir: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def count_words(text: str) -> int:
    return len(FRONTMATTER.sub("", text).split())


def doc_stats(c: Candidate) -> dict:
    repo = ensure_clone(c)
    word_counts = []
    for sub in c.docs_paths:
        for path in sorted((repo / sub).rglob("*")):
            if path.suffix in DOC_SUFFIXES and path.is_file():
                word_counts.append(count_words(path.read_text(encoding="utf-8", errors="ignore")))
    return {
        "name": c.name,
        "docs_repo": c.docs_repo,
        "commit": head_commit(repo),
        "license_hint": c.license_hint,
        "pages": len(word_counts),
        "pages_over_100_words": sum(w >= MIN_REAL_PAGE_WORDS for w in word_counts),
        "total_words": sum(word_counts),
    }


def run() -> list[dict]:
    rows = [doc_stats(c) for c in CANDIDATES]
    out = settings.results_dir / "selection" / "docs_stats.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows
