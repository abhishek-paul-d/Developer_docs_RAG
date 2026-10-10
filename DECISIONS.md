# DECISIONS

One entry per decision. Format and rules are in [CLAUDE.md](CLAUDE.md).

## D-001: Target library
- Date / phase: Phase 0
- Decision: pending the selection test (Polars, Pydantic v2, LangGraph, uv/Ruff).
- Why: pending.
- Alternatives considered: pending (FastAPI dropped up front; models likely know it too well for retrieval to add much, assumption).
- Evidence: assumption until the Phase 0 scores are filled in.
- Trade-offs / what we give up: pending.
- Revisit if: contamination or question counts turn out different from the selection test.

## D-002: Python tooling (uv, ruff, pytest, pre-commit, pydantic-settings)
- Date / phase: Phase 0
- Decision: uv for environments and lockfile; ruff for lint and format; pytest; pre-commit; pydantic-settings for config; hatchling build backend.
- Why: one fast tool covers install, lock and run (uv) and one covers lint and format (ruff), which keeps CI and the Makefile short. pydantic-settings gives typed env-driven config, so thresholds and paths are explicit and testable. The plan names uv and the Windows no-GPU setup needs a reproducible lockfile.
- Alternatives considered: pip + venv (no lockfile, slower); poetry (heavier, slower resolver, no benefit here); black + flake8 + isort (three tools instead of ruff); plain env vars / dataclass config (no validation).
- Evidence: assumption; CI green on the skeleton is the only check.
- Trade-offs / what we give up: uv and ruff are younger tools with faster-moving CLIs.
- Revisit if: a dependency needed later does not resolve under uv.
