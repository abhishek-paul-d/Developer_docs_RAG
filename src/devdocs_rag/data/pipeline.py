import json
from collections import Counter

from devdocs_rag.config import settings
from devdocs_rag.data.chunk import chunk_page, chunk_symbol
from devdocs_rag.data.fetch_docs import fetch, processed_dir
from devdocs_rag.data.parse import parse_corpus
from devdocs_rag.data.split import build_split
from devdocs_rag.data.symbols import extract_symbols
from devdocs_rag.logging import get_logger

log = get_logger(__name__)


def _write_json(name: str, obj) -> None:
    path = processed_dir() / name
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run() -> dict:
    source = fetch()
    pages = parse_corpus()
    symbols, unresolved = extract_symbols()
    chunks = [c for p in pages for c in chunk_page(p)]
    chunks += [c for s in symbols for c in chunk_symbol(s)]
    total_before = len(chunks)
    chunks = list({c.chunk_id: c for c in chunks}.values())
    chunks.sort(key=lambda c: (c.doc_path, c.section_path, c.chunk_id))
    split = build_split(chunks)

    out = processed_dir()
    with (out / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")
    _write_json(
        "symbols.json",
        {
            "library_version": source["library_version"],
            "qualified": sorted(s.qualified for s in symbols),
            "names": sorted({s.qualified.split(".")[-1] for s in symbols}),
            "unresolved": sorted(unresolved),
        },
    )
    _write_json("split.json", split)

    by_split = Counter(split["groups"][c.group] for c in chunks)
    report = {
        "source": source,
        "pages": len(pages),
        "symbols": len(symbols),
        "unresolved_symbols": len(unresolved),
        "chunks": len(chunks),
        "chunks_by_type": dict(Counter(c.chunk_type for c in chunks)),
        "chunks_by_split": dict(by_split),
        "chunks_over_cap": sum(c.tokens > settings.chunk_max_tokens for c in chunks),
        "exact_duplicates_removed": total_before - len(chunks),
    }
    _write_json("report.json", report)
    log.info("corpus built: %s", report)
    return report


if __name__ == "__main__":
    run()
