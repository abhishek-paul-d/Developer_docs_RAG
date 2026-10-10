import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from devdocs_rag.data.fetch_docs import raw_dir
from devdocs_rag.logging import get_logger

log = get_logger(__name__)

DOC_ROOTS = ("user-guide", "releases/upgrade")
URL_BASE = "https://docs.pola.rs/"

FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
MACRO = re.compile(r"\{\{\s*code_block\((.*?)\)\s*\}\}", re.DOTALL)
SNIPPET_LINE = re.compile(r'^\s*--8<--\s+"([^"]+)"\s*$')
SNIPPET_MARK = re.compile(r"^\s*(?:#|//)\s*--8<--\s*\[(start|end):([\w\-]+)\]\s*$")
FENCE = re.compile(r"^(\s*)```(\S*)(.*)$")
TAB = re.compile(r'^(\s*)=== "(.*)"\s*$')
ADMONITION = re.compile(r'^(\s*)(?:!!!|\?\?\?\+?) ([\w-]+)(?: "(.*)"| (.+))?\s*$')
CODE_HEADER = re.compile(
    r'^(\s*)\{\{\s*code_header\(\s*"(\w+)"\s*,\s*\[.*?\]\s*,\s*(\[.*?\])\s*\)\s*\}\}\s*$'
)
ICON = re.compile(r":(?:material|fontawesome|octicons|simple)-[\w-]+:")
ATTR_LIST = re.compile(r"\{[.#:][^}]*\}")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


@dataclass
class Page:
    doc_path: str
    url: str
    title: str
    group: str
    kind: str
    text: str
    api_refs: list[str] = field(default_factory=list)


def read_snippet(src_root: Path, ref: str) -> str | None:
    path_part, _, section = ref.partition(":")
    if not path_part.startswith("python/"):
        return None
    path = src_root / path_part
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if section:
        picked, inside = [], False
        for line in lines:
            m = SNIPPET_MARK.match(line)
            if m and m.group(2) == section:
                inside = m.group(1) == "start"
            elif inside and not m:
                picked.append(line)
        lines = picked
    else:
        lines = [ln for ln in lines if not SNIPPET_MARK.match(ln)]
    return "\n".join(lines).strip("\n")


def expand_macros(text: str, src_root: Path, api_refs: list[str]) -> str:
    def repl(m: re.Match) -> str:
        call = ast.parse(f"code_block({m.group(1)})", mode="eval").body
        args = [ast.literal_eval(a) for a in call.args]
        kwargs = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
        path = args[0] if args else kwargs["path"]
        section = args[1] if len(args) > 1 else kwargs.get("section")
        api = (args[2] if len(args) > 2 else kwargs.get("api_functions")) or []
        py_api = (args[3] if len(args) > 3 else kwargs.get("python_api_functions")) or []
        code = read_snippet(src_root, f"python/{path}.py" + (f":{section}" if section else ""))
        if code is None:
            return ""
        api_refs.extend([*api, *py_api])
        return f"```python\n{code}\n```"

    return MACRO.sub(repl, text)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _body(lines: list[str], i: int, base: int) -> tuple[list[str], int]:
    body = []
    while i < len(lines) and (not lines[i].strip() or _indent(lines[i]) >= base + 4):
        body.append(lines[i][base + 4 :] if lines[i].strip() else "")
        i += 1
    return body, i


def flatten_blocks(lines: list[str]) -> list[str]:
    out, i = [], 0
    in_fence = False
    while i < len(lines):
        line = lines[i]
        if FENCE.match(line):
            in_fence = not in_fence
        tab = None if in_fence else TAB.match(line)
        adm = None if in_fence else ADMONITION.match(line)
        hdr = None if in_fence else CODE_HEADER.match(line)
        if hdr:
            body, i = _body(lines, i + 1, len(hdr.group(1)))
            if hdr.group(2) != "rust":
                out.extend(flatten_blocks(body))
        elif tab:
            body, i = _body(lines, i + 1, len(tab.group(1)))
            if "rust" not in tab.group(2).lower():
                out.extend(flatten_blocks(body))
        elif adm:
            body, i = _body(lines, i + 1, len(adm.group(1)))
            label = adm.group(3) or adm.group(4) or adm.group(2).capitalize()
            out.append(f"**{label}:**")
            out.extend(flatten_blocks(body))
        else:
            out.append(line)
            i += 1
    return out


def resolve_fences(lines: list[str], src_root: Path) -> list[str]:
    out, i = [], 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not FENCE.match(lines[j]):
            j += 1
        content = lines[i + 1 : j]
        i = j + 1
        if 'exec="on"' in m.group(3) or 'exec="on"' in m.group(2):
            continue
        resolved = []
        for line in content:
            sm = SNIPPET_LINE.match(line)
            if sm:
                code = read_snippet(src_root, sm.group(1))
                if code is None:
                    resolved = None
                    break
                resolved.extend(code.splitlines())
            else:
                resolved.append(line)
        if resolved is None:
            continue
        out.extend([f"```{m.group(2)}", *resolved, "```"])
    return out


def clean_prose(lines: list[str]) -> list[str]:
    out, in_fence = [], False
    for line in lines:
        if FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
        elif in_fence:
            out.append(line)
        elif SNIPPET_LINE.match(line):
            continue
        else:
            line = HTML_TAG.sub("", ICON.sub("", ATTR_LIST.sub("", IMAGE.sub("", line))))
            out.append(LINK.sub(r"\1", line).rstrip())
    return out


def parse_markdown(raw: str, src_root: Path) -> tuple[str, list[str]]:
    api_refs: list[str] = []
    text = HTML_COMMENT.sub("", FRONTMATTER.sub("", raw))
    text = expand_macros(text, src_root, api_refs)
    lines = resolve_fences(flatten_blocks(text.splitlines()), src_root)
    text = "\n".join(clean_prose(lines))
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text, list(dict.fromkeys(api_refs))


def page_url(doc_path: str) -> str:
    stem = doc_path.removesuffix(".md").removesuffix("index").rstrip("/")
    return f"{URL_BASE}{stem}/" if stem else URL_BASE


def page_group(doc_path: str) -> str:
    parts = doc_path.split("/")
    if parts[0] == "releases":
        return doc_path.removesuffix(".md")
    return "/".join(parts[:2]) if len(parts) > 2 else parts[0]


def parse_corpus() -> list[Page]:
    docs_root = raw_dir() / "docs" / "source"
    src_root = docs_root / "src"
    pages = []
    for root in DOC_ROOTS:
        for path in sorted((docs_root / root).rglob("*.md")):
            doc_path = path.relative_to(docs_root).as_posix()
            text, api_refs = parse_markdown(path.read_text(encoding="utf-8"), src_root)
            title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), "")
            pages.append(
                Page(
                    doc_path=doc_path,
                    url=page_url(doc_path),
                    title=title or path.stem,
                    group=page_group(doc_path),
                    kind="changelog" if root == "releases/upgrade" else "guide",
                    text=text,
                    api_refs=api_refs,
                )
            )
    return pages
