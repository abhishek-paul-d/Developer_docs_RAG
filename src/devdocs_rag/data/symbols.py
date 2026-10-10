import importlib
import inspect
import re
import typing
from dataclasses import dataclass
from pathlib import Path

from devdocs_rag.data.fetch_docs import raw_dir
from devdocs_rag.logging import get_logger

log = get_logger(__name__)

API_URL_BASE = "https://docs.pola.rs/api/python/stable/reference/"
CURRENT_MODULE = re.compile(r"^\.\. currentmodule::\s*(\S+)")
AUTOSUMMARY = re.compile(r"^\.\. autosummary::")
SINGLE = re.compile(r"^\.\. auto(?:class|function|property|data|attribute)::\s*(\S+)")
AUTOMODULE = re.compile(r"^\.\. automodule::\s*(\S+)")


@dataclass
class Symbol:
    qualified: str
    module: str
    kind: str
    signature: str
    doc: str
    rst_path: str
    section: str
    url: str


def reference_dir() -> Path:
    return raw_dir() / "py-polars" / "docs" / "source" / "reference"


def rst_title(lines: list[str]) -> str:
    for i, line in enumerate(lines[:-1]):
        nxt = lines[i + 1].strip()
        if line.strip() and nxt and set(nxt) <= {"=", "-"}:
            return line.strip()
    return ""


def parse_rst(path: Path) -> list[tuple[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = rst_title(lines)
    module, in_list, entries = "polars", False, []
    for line in lines:
        cm = CURRENT_MODULE.match(line)
        single = SINGLE.match(line)
        auto_mod = AUTOMODULE.match(line)
        if cm:
            module = cm.group(1)
            in_list = False
        elif AUTOSUMMARY.match(line):
            in_list = True
        elif auto_mod:
            entries.append((auto_mod.group(1), "*"))
            in_list = False
        elif single:
            name = single.group(1)
            if title.startswith("polars."):
                entries.append(("polars", title.removeprefix("polars.")))
            else:
                entries.append((module, name))
            in_list = False
        elif in_list:
            stripped = line.strip()
            if not stripped or stripped.startswith(":"):
                continue
            if line.startswith((" ", "\t")):
                entries.append((module, stripped))
            else:
                in_list = False
    return entries


def resolve(module: str, dotted: str):
    obj = importlib.import_module(module)
    parts = dotted.lstrip("~").split(".")
    for i, part in enumerate(parts):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            if not inspect.ismodule(obj):
                raise
            obj = importlib.import_module(f"{obj.__name__}.{part}")
        if isinstance(obj, property) and i < len(parts) - 1:
            try:
                hints = typing.get_type_hints(obj.fget)
            except Exception:
                hints = {}
            if hints.get("return") is not None:
                obj = hints["return"]
    return obj


def module_members(module: str) -> list[str]:
    mod = importlib.import_module(module)
    names = getattr(mod, "__all__", None) or [n for n in dir(mod) if not n.startswith("_")]
    return [n for n in names if callable(getattr(mod, n, None))]


ROLE = re.compile(
    r":(?:meth|func|class|attr|mod|ref|data|exc|obj|math|type|any|sup|py:\w+):`~?([^`]+)`"
)
DOUBLE_TICKS = re.compile(r"``([^`]+)``")
DIRECTIVE = re.compile(r"^(\s*)\.\. ([\w-]+)::\s*(.*)$")
MEMORY_ADDRESS = re.compile(r" at 0x[0-9A-Fa-f]+>")
DIRECTIVE_LABELS = {
    "versionadded": "Added in",
    "versionchanged": "Changed in",
    "deprecated": "Deprecated since",
    "warning": "Warning:",
    "note": "Note:",
    "important": "Important:",
    "seealso": "See also:",
    "engine-support": "Engine support:",
}


def clean_rst(doc: str) -> str:
    out = []
    for line in doc.splitlines():
        m = DIRECTIVE.match(line)
        if m:
            indent, name, arg = m.groups()
            if name in DIRECTIVE_LABELS:
                out.append(f"{indent}{DIRECTIVE_LABELS[name]} {arg}".rstrip())
            continue
        out.append(line)
    text = "\n".join(out)
    return DOUBLE_TICKS.sub(r"`\1`", ROLE.sub(r"`\1`", text))


def describe(obj) -> tuple[str, str, str]:
    prop_doc = obj.fget.__doc__ if isinstance(obj, property) and obj.fget else None
    doc = inspect.getdoc(obj) or inspect.cleandoc(prop_doc or "")
    if inspect.isclass(obj):
        kind = "class"
    elif isinstance(obj, property):
        kind = "property"
    elif callable(obj):
        kind = "function"
    else:
        kind = "attribute"
    try:
        signature = str(inspect.signature(obj)) if callable(obj) else ""
    except (TypeError, ValueError):
        signature = ""
    return kind, MEMORY_ADDRESS.sub(">", signature), clean_rst(doc)


def qualify(module: str, dotted: str) -> str:
    if dotted.startswith("~"):
        return dotted.split(".")[-1]
    if module in {"polars", "polars.functions.col"}:
        return dotted
    return f"{module.removeprefix('polars.')}.{dotted}"


def extract_symbols() -> tuple[list[Symbol], list[str]]:
    base = reference_dir()
    symbols, unresolved, seen = [], [], set()
    for rst in sorted(base.rglob("*.rst")):
        rel = rst.relative_to(base)
        title = rst_title(rst.read_text(encoding="utf-8").splitlines())
        expanded = []
        for module, dotted in parse_rst(rst):
            if dotted == "*":
                expanded.extend((module, n) for n in module_members(module))
            else:
                expanded.append((module, dotted))
        for module, dotted in expanded:
            qualified = qualify(module, dotted)
            if qualified in seen:
                continue
            try:
                obj = resolve(module, dotted)
            except (AttributeError, ImportError, NameError, TypeError):
                unresolved.append(f"{module}:{dotted}")
                continue
            seen.add(qualified)
            kind, signature, doc = describe(obj)
            stem = qualified if module == "polars" else f"{module}.{dotted.lstrip('~')}"
            url_name = stem if stem.startswith("polars.") else f"polars.{stem}"
            url = f"{API_URL_BASE}{rel.parent.as_posix()}/api/{url_name}.html".replace("/./", "/")
            symbols.append(
                Symbol(qualified, module, kind, signature, doc, rel.as_posix(), title, url)
            )
    return symbols, unresolved
