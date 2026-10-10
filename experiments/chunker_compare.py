import json
import re
import statistics as st
from pathlib import Path

from langchain_text_splitters import (
    Language,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from devdocs_rag.config import settings
from devdocs_rag.data.chunk import chunk_page, count_tokens
from devdocs_rag.data.parse import parse_corpus

CAP = settings.chunk_max_tokens
MIN_TOKENS = 40
FENCE_LINE = re.compile(r"^\s*```", re.M)
TABLE_ROW = re.compile(r"^\s*\|", re.M)
TABLE_SEPARATOR = re.compile(r"^\s*\|[\s:|-]*-[\s:|-]*\|?\s*$", re.M)
HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4"), ("#####", "h5")]


def recursive_only(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter.from_language(
        Language.MARKDOWN, chunk_size=CAP, chunk_overlap=0, length_function=count_tokens
    )
    return splitter.split_text(text)


def header_then_recursive(text: str) -> list[str]:
    sections = MarkdownHeaderTextSplitter(HEADERS, strip_headers=False).split_text(text)
    splitter = RecursiveCharacterTextSplitter.from_language(
        Language.MARKDOWN, chunk_size=CAP, chunk_overlap=0, length_function=count_tokens
    )
    return [piece for s in sections for piece in splitter.split_text(s.page_content)]


def in_house(page) -> list[tuple[str, str]]:
    return [(c.text, c.section_path) for c in chunk_page(page, cap=CAP)]


def metrics(chunks_per_page: list[list[tuple[str, str | None]]]) -> dict:
    chunks = [c for page in chunks_per_page for c, _ in page]
    tokens = sorted(count_tokens(c) for c in chunks)
    broken = sum(len(FENCE_LINE.findall(c)) % 2 == 1 for c in chunks)
    orphan_code = sum(
        1
        for page in chunks_per_page
        for i, (c, section) in enumerate(page)
        if i > 0 and c.lstrip().startswith("```") and (section is None or page[i - 1][1] == section)
    )
    headerless_tables = sum(
        1 for c in chunks if TABLE_ROW.search(c) and not TABLE_SEPARATOR.search(c)
    )
    return {
        "chunks": len(chunks),
        "median_tokens": st.median(tokens),
        "p90_tokens": tokens[int(0.9 * len(tokens))],
        "max_tokens": tokens[-1],
        "over_cap": sum(t > CAP for t in tokens),
        "under_40_tokens": sum(t < MIN_TOKENS for t in tokens),
        "fences_cut_in_half": broken,
        "code_starts_chunk_after_other_text": orphan_code,
        "table_fragments_without_header": headerless_tables,
        "total_tokens": sum(tokens),
    }


def main() -> dict:
    pages = parse_corpus()
    runs = {
        "in_house": [in_house(p) for p in pages],
        "langchain_recursive_markdown": [
            [(c, None) for c in recursive_only(p.text)] for p in pages
        ],
        "langchain_header_then_recursive": [
            [(c, None) for c in header_then_recursive(p.text)] for p in pages
        ],
    }
    result = {
        "cap_tokens": CAP,
        "pages": len(pages),
        "chunkers": {k: metrics(v) for k, v in runs.items()},
    }
    out = Path(settings.results_dir) / "chunker_compare"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    res = main()
    names = list(res["chunkers"])
    keys = list(res["chunkers"][names[0]])
    print(f"{'metric':38}" + "".join(f"{n[:24]:>26}" for n in names))
    for k in keys:
        print(f"{k:38}" + "".join(f"{res['chunkers'][n][k]!s:>26}" for n in names))
