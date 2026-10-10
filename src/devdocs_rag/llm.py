import hashlib
import json
import time
from pathlib import Path

import httpx

from devdocs_rag.config import settings
from devdocs_rag.exceptions import ConfigError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_RETRIES = 5


class CachedChat:
    def __init__(self, client: httpx.Client | None = None, cache_dir: Path | None = None):
        self.client = client or httpx.Client(timeout=120)
        self.cache_dir = cache_dir or settings.cache_dir

    def _key(self, model: str, messages: list[dict], temperature: float) -> str:
        payload = json.dumps([model, messages, temperature], sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def chat(self, messages: list[dict], model: str | None = None, temperature: float = 0.0) -> str:
        model = model or settings.groq_model
        path = self.cache_dir / f"{self._key(model, messages, temperature)}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["text"]
        if not settings.groq_api_key:
            raise ConfigError("DEVDOCS_GROQ_API_KEY is not set (put it in .env)")
        text = self._call(messages, model, temperature)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"model": model, "text": text}), encoding="utf-8")
        return text

    def _call(self, messages: list[dict], model: str, temperature: float) -> str:
        body = {"model": model, "messages": messages, "temperature": temperature}
        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        for attempt in range(MAX_RETRIES):
            resp = self.client.post(GROQ_URL, json=body, headers=headers)
            if resp.status_code == 429:
                time.sleep(float(resp.headers.get("retry-after", 2**attempt)))
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        raise RuntimeError("Groq rate limit: retries exhausted")
