import hashlib
from collections import defaultdict

from devdocs_rag.config import settings
from devdocs_rag.data.chunk import Chunk

SPLITS = ("train", "val", "test")


def source_kind(chunk: Chunk) -> str:
    if chunk.chunk_type == "api_reference":
        return "api"
    return "changelog" if chunk.chunk_type == "changelog" else "guide"


def assign_groups(sizes: dict[str, int], seed: int, ratios: tuple[float, ...]) -> dict[str, str]:
    order = sorted(sizes, key=lambda g: hashlib.sha256(f"{seed}:{g}".encode()).hexdigest())
    total = sum(sizes.values())
    target = {s: r * total for s, r in zip(SPLITS, ratios, strict=True)}
    filled = dict.fromkeys(SPLITS, 0)
    out = {}
    for group in order:
        split = max(SPLITS, key=lambda s: target[s] - filled[s])
        out[group] = split
        filled[split] += sizes[group]
    return out


def build_split(chunks: list[Chunk]) -> dict:
    by_kind: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in chunks:
        by_kind[source_kind(c)][c.group] += c.tokens
    groups = {}
    for kind in sorted(by_kind):
        groups.update(
            assign_groups(dict(by_kind[kind]), settings.split_seed, settings.split_ratios)
        )
    return {
        "seed": settings.split_seed,
        "ratios": list(settings.split_ratios),
        "groups": dict(sorted(groups.items())),
    }
