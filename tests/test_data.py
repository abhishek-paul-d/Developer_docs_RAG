from pathlib import Path

import pytest

from devdocs_rag.data.chunk import Chunk, chunk_id, chunk_page, count_tokens
from devdocs_rag.data.parse import Page, parse_markdown, read_snippet
from devdocs_rag.data.split import assign_groups, build_split


@pytest.fixture
def src_root(tmp_path: Path) -> Path:
    snippet = tmp_path / "python" / "guide"
    snippet.mkdir(parents=True)
    (snippet / "ex.py").write_text(
        "# --8<-- [start:one]\nx = 1\n# --8<-- [end:one]\n"
        "# --8<-- [start:two]\ny = 2\n# --8<-- [end:two]\n",
        encoding="utf-8",
    )
    return tmp_path


def test_read_snippet_section(src_root):
    assert read_snippet(src_root, "python/guide/ex.py:two") == "y = 2"
    assert read_snippet(src_root, "rust/guide/ex.rs:two") is None


def test_macro_and_include_resolve_and_exec_dropped(src_root):
    raw = (
        "# T\n\n{{code_block('guide/ex', 'one', ['DataFrame'])}}\n\n"
        '```python exec="on" result="text"\n--8<-- "python/guide/ex.py:one"\n```\n\n'
        '```python\n--8<-- "python/guide/ex.py:two"\n```\n'
    )
    text, refs = parse_markdown(raw, src_root)
    assert "x = 1" in text and "y = 2" in text
    assert "--8<--" not in text and "{{" not in text and "exec=" not in text
    assert refs == ["DataFrame"]


def test_tabs_keep_python_drop_rust_and_admonition_flattens(src_root):
    raw = (
        '=== ":fontawesome-brands-python: Python"\n\n    ```python\n    a = 1\n    ```\n\n'
        '=== ":fontawesome-brands-rust: Rust"\n\n    ```rust\n    let a = 1;\n    ```\n\n'
        '!!! warning "Careful"\n\n    This is risky.\n'
    )
    text, _ = parse_markdown(raw, src_root)
    assert "a = 1" in text and "let a" not in text
    assert "**Careful:**" in text and "This is risky." in text


def make_page(text: str) -> Page:
    return Page(
        "user-guide/x.md", "https://docs.pola.rs/user-guide/x/", "X", "user-guide", "guide", text
    )


def test_code_stays_whole_and_with_intro():
    code = "```python\n" + "\n".join(f"v{i} = {i}" for i in range(400)) + "\n```"
    page = make_page(f"# X\n\n## A\n\nHere is the example:\n\n{code}\n")
    chunks = chunk_page(page, cap=100)
    holder = [c for c in chunks if "v0 = 0" in c.text]
    assert len(holder) == 1
    assert holder[0].text.startswith("Here is the example:")
    assert holder[0].text.count("```") == 2


def test_chunks_respect_cap_for_prose_and_split_on_headings():
    body = " ".join(f"Sentence number {i} is here." for i in range(200))
    page = make_page(f"# X\n\n## A\n\n{body}\n\n## B\n\nShort.\n")
    chunks = chunk_page(page, cap=100)
    assert all(c.tokens <= 100 for c in chunks)
    assert {c.section_path for c in chunks} == {"X > A", "X > B"}


def test_chunk_ids_deterministic_and_content_sensitive():
    assert chunk_id("a.md", "S", "t") == chunk_id("a.md", "S", "t")
    assert chunk_id("a.md", "S", "t") != chunk_id("a.md", "S", "u")
    page = make_page("# X\n\n## A\n\nHello world.\n")
    assert [c.chunk_id for c in chunk_page(page)] == [c.chunk_id for c in chunk_page(page)]


def test_token_count_ignores_table_separator_dashes():
    assert count_tokens("| a | b |\n| ------------- | ------------- |") < 15


def chunk(group: str, kind: str = "prose", tokens: int = 100) -> Chunk:
    return Chunk(group + kind, group, group, "u", "2.0.0", kind, group, tokens, "t")


def test_split_keeps_groups_together_and_is_deterministic():
    chunks = [chunk(f"g{i}") for i in range(10)] + [
        chunk(f"g{i}", "api_reference") for i in range(5)
    ]
    a, b = build_split(chunks), build_split(chunks)
    assert a == b
    assert set(a["groups"].values()) <= {"train", "val", "test"}


def test_assign_groups_hits_roughly_the_ratios():
    sizes = {f"g{i}": 100 for i in range(50)}
    out = assign_groups(sizes, 0, (0.7, 0.1, 0.2))
    share = {
        s: sum(sizes[g] for g, v in out.items() if v == s) / 5000 for s in ("train", "val", "test")
    }
    assert abs(share["train"] - 0.7) < 0.05 and abs(share["test"] - 0.2) < 0.05


def test_clean_rst_converts_roles_directives_and_ticks():
    from devdocs_rag.data.symbols import MEMORY_ADDRESS, clean_rst

    doc = (
        ".. versionadded:: 1.2\n:meth:`~polars.Expr.sum` uses ``mean``.\n"
        ".. engine-support:: in-memory, streaming\n.. code-block:: python\n    x = 1"
    )
    out = clean_rst(doc)
    assert "Added in 1.2" in out and "`polars.Expr.sum` uses `mean`." in out
    assert "Engine support: in-memory, streaming" in out
    assert "::" not in out and "x = 1" in out
    assert MEMORY_ADDRESS.sub(">", "<Foo object at 0x7F00AB>") == "<Foo object>"


def test_resolve_namespace_and_plain_names_on_installed_polars():
    from devdocs_rag.data.symbols import resolve

    assert callable(resolve("polars", "Expr.str.contains"))
    assert callable(resolve("polars", "DataFrame.select"))
    with pytest.raises(AttributeError):
        resolve("polars", "Expr.cum_mean")


def test_built_symbol_list_flags_invented_api(request):
    import json

    from devdocs_rag.data.fetch_docs import processed_dir

    path = processed_dir() / "symbols.json"
    if not path.exists():
        pytest.skip("run the data pipeline first")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "cum_sum" in data["names"] and "cum_mean" not in data["names"]
