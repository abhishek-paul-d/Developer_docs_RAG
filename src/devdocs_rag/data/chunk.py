import hashlib
import re
from dataclasses import asdict, dataclass

from devdocs_rag.config import settings
from devdocs_rag.data.parse import FENCE, Page

TOKEN = re.compile(r"\w+|[^\w\s]")
REPEATED_PUNCT = re.compile(r"([-=_*~#])\1{2,}")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
CODE_SHARE_FOR_CODE_CHUNK = 0.6
MIN_TOKENS = 40


@dataclass
class Chunk:
    chunk_id: str
    doc_path: str
    section_path: str
    url: str
    library_version: str
    chunk_type: str
    group: str
    tokens: int
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


def count_tokens(text: str) -> int:
    return len(TOKEN.findall(REPEATED_PUNCT.sub(r"\1", text)))


def slugify(heading: str) -> str:
    return re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", heading.lower())).strip("-")


def split_sections(text: str) -> list[tuple[list[str], list[str]]]:
    sections, trail, current, in_fence = [], [], [], False
    start_trail: list[str] = []
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        m = None if in_fence else HEADING.match(line)
        if m:
            if any(ln.strip() for ln in current):
                sections.append((start_trail, current))
            level = len(m.group(1))
            trail = [*trail[: level - 1], m.group(2)]
            start_trail, current = list(trail), []
        else:
            current.append(line)
    if any(ln.strip() for ln in current):
        sections.append((start_trail, current))
    return sections


def split_blocks(lines: list[str]) -> list[tuple[str, bool]]:
    blocks, buf, i = [], [], 0
    while i < len(lines):
        if FENCE.match(lines[i]):
            if buf:
                blocks.append(("\n".join(buf), False))
                buf = []
            j = i + 1
            while j < len(lines) and not FENCE.match(lines[j]):
                j += 1
            blocks.append(("\n".join(lines[i : j + 1]), True))
            i = j + 1
        elif not lines[i].strip():
            if buf:
                blocks.append(("\n".join(buf), False))
                buf = []
            i += 1
        else:
            buf.append(lines[i])
            i += 1
    if buf:
        blocks.append(("\n".join(buf), False))
    return blocks


def build_units(blocks: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    units: list[tuple[str, bool]] = []
    for text, is_code in blocks:
        if is_code and units and not units[-1][1]:
            units[-1] = (units[-1][0] + "\n\n" + text, True)
        else:
            units.append((text, is_code))
    return units


def split_prose(text: str, cap: int) -> list[str]:
    pieces, cur = [], []
    for sentence in SENTENCE_END.split(text):
        if cur and count_tokens(" ".join([*cur, sentence])) > cap:
            pieces.append(" ".join(cur))
            cur = []
        cur.append(sentence)
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def split_lines(text: str, cap: int) -> list[str]:
    pieces, cur = [], []
    for line in text.splitlines():
        if cur and count_tokens("\n".join([*cur, line])) > cap:
            pieces.append("\n".join(cur))
            cur = []
        cur.append(line)
    if cur:
        pieces.append("\n".join(cur))
    return pieces


def split_table(text: str, cap: int) -> list[str]:
    lines = text.splitlines()
    head, rows = lines[:2], lines[2:]
    pieces, cur = [], []
    for row in rows:
        if cur and count_tokens("\n".join([*head, *cur, row])) > cap:
            pieces.append("\n".join([*head, *cur]))
            cur = []
        cur.append(row)
    if cur:
        pieces.append("\n".join([*head, *cur]))
    return pieces


def pack(units: list[tuple[str, bool]], cap: int) -> list[str]:
    chunks: list[str] = []
    cur: list[str] = []
    cur_tokens = 0

    def flush() -> None:
        nonlocal cur, cur_tokens
        if cur:
            chunks.append("\n\n".join(cur))
        cur, cur_tokens = [], 0

    for text, has_code in units:
        t = count_tokens(text)
        if t > cap:
            flush()
            if has_code:
                chunks.append(text)
                continue
            is_table = text.lstrip().startswith("|")
            parts = split_table(text, cap) if is_table else split_prose(text, cap)
            parts = [
                q
                for part in parts
                for q in (split_lines(part, cap) if count_tokens(part) > cap else [part])
            ]
        else:
            parts = [text]
        for part in parts:
            pt = count_tokens(part)
            if cur and cur_tokens + pt > cap:
                flush()
            cur.append(part)
            cur_tokens += pt
    flush()
    if len(chunks) > 1 and count_tokens(chunks[-1]) < MIN_TOKENS:
        if count_tokens(chunks[-2]) + count_tokens(chunks[-1]) <= cap:
            chunks[-2:] = ["\n\n".join(chunks[-2:])]
    return chunks


def chunk_type(text: str, page_kind: str) -> str:
    if page_kind == "changelog":
        return "changelog"
    code_chars = sum(len(b) for b, is_code in split_blocks(text.splitlines()) if is_code)
    return "code" if code_chars / max(len(text), 1) >= CODE_SHARE_FOR_CODE_CHUNK else "prose"


def chunk_id(doc_path: str, section_path: str, text: str) -> str:
    return hashlib.sha256(f"{doc_path}\0{section_path}\0{text}".encode()).hexdigest()[:16]


def chunk_page(page: Page, cap: int | None = None) -> list[Chunk]:
    cap = cap or settings.chunk_max_tokens
    chunks = []
    for trail, lines in split_sections(page.text):
        section_path = " > ".join(trail) or page.title
        anchor = f"#{slugify(trail[-1])}" if len(trail) > 1 else ""
        units = build_units(split_blocks(lines))
        for text in pack(units, cap):
            chunks.append(
                Chunk(
                    chunk_id=chunk_id(page.doc_path, section_path, text),
                    doc_path=page.doc_path,
                    section_path=section_path,
                    url=page.url + anchor,
                    library_version=settings.library_version,
                    chunk_type=chunk_type(text, page.kind),
                    group=page.group,
                    tokens=count_tokens(text),
                    text=text,
                )
            )
    return chunks


def api_group(rst_path: str) -> str:
    return f"api/{rst_path.removesuffix('.rst').split('/')[-1]}"


def chunk_symbol(symbol, cap: int | None = None) -> list[Chunk]:
    cap = cap or settings.chunk_max_tokens
    header = f"{symbol.qualified}{symbol.signature}"
    if symbol.kind == "class":
        header = f"class {header}"
    body_cap = max(cap - count_tokens(header), 50)
    paragraphs = [(p, False) for p in re.split(r"\n\s*\n", symbol.doc.strip()) if p.strip()]
    pieces = pack(paragraphs, body_cap) or [""]
    section_path = f"{symbol.section} > {symbol.qualified}"
    doc_path = f"api/{symbol.rst_path}"
    chunks = []
    for body in pieces:
        text = f"{header}\n\n{body}".strip()
        chunks.append(
            Chunk(
                chunk_id=chunk_id(doc_path, section_path, text),
                doc_path=doc_path,
                section_path=section_path,
                url=symbol.url,
                library_version=settings.library_version,
                chunk_type="api_reference",
                group=api_group(symbol.rst_path),
                tokens=count_tokens(text),
                text=text,
            )
        )
    return chunks
