from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    name: str
    docs_repo: str
    docs_paths: tuple[str, ...]
    so_tag: str
    discussions_repo: str
    license_hint: str


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        "polars", "pola-rs/polars", ("docs/source",), "python-polars", "pola-rs/polars", "MIT"
    ),
    Candidate("pydantic", "pydantic/pydantic", ("docs",), "pydantic", "pydantic/pydantic", "MIT"),
    Candidate(
        "langgraph",
        "langchain-ai/docs",
        ("src/oss/langgraph",),
        "langgraph",
        "langchain-ai/langgraph",
        "MIT",
    ),
    Candidate("uv", "astral-sh/uv", ("docs",), "uv", "astral-sh/uv", "Apache-2.0 OR MIT"),
)


def by_name(name: str) -> Candidate:
    for c in CANDIDATES:
        if c.name == name:
            return c
    raise KeyError(name)
