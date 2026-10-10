import json
import subprocess
from pathlib import Path

from devdocs_rag.config import settings
from devdocs_rag.logging import get_logger

log = get_logger(__name__)


def raw_dir() -> Path:
    return settings.data_dir / "raw" / "polars"


def processed_dir() -> Path:
    return settings.data_dir / "processed"


def _git(*args: str, cwd: Path | None = None) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True, check=True, cwd=cwd)
    return out.stdout.strip()


def fetch() -> dict:
    target = raw_dir()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        log.info("cloning %s at %s", settings.docs_repo, settings.docs_tag)
        _git(
            "clone",
            "--quiet",
            "--depth",
            "1",
            "--branch",
            settings.docs_tag,
            f"https://github.com/{settings.docs_repo}",
            str(target),
        )
    commit = _git("rev-parse", "HEAD", cwd=target)
    manifest = {
        "repo": settings.docs_repo,
        "tag": settings.docs_tag,
        "commit": commit,
        "library_version": settings.library_version,
    }
    out = processed_dir() / "source.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
