import httpx

from devdocs_rag import llm
from devdocs_rag.selection.contamination import html_to_text
from devdocs_rag.selection.docs_stats import count_words


def test_count_words_strips_frontmatter():
    assert count_words("---\ntitle: x\n---\nhello big world") == 3


def test_html_to_text_keeps_code_fenced():
    out = html_to_text("<p>use &lt;b&gt;</p><pre><code>df.select(1)</code></pre>")
    assert "use <b>" in out and "```\ndf.select(1)\n```" in out


def test_chat_caches_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(llm.settings, "groq_api_key", "test")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    chat = llm.CachedChat(httpx.Client(transport=httpx.MockTransport(handler)), tmp_path)
    msgs = [{"role": "user", "content": "q"}]
    assert chat.chat(msgs) == "hi"
    assert chat.chat(msgs) == "hi"
    assert len(calls) == 1
