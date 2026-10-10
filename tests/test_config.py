from pathlib import Path

from devdocs_rag.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.data_dir == Path("data")
    assert s.results_dir == Path("results")


def test_env_override(monkeypatch):
    monkeypatch.setenv("DEVDOCS_DATA_DIR", "elsewhere")
    assert Settings(_env_file=None).data_dir == Path("elsewhere")
