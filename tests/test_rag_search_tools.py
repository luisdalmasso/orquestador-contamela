from types import SimpleNamespace

from app.tools import rag_search_tools


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        rag=SimpleNamespace(
            api_key_env="RAG_API_KEY",
            base_url="http://flamehaven:8000",
            default_store="catolico",
        )
    )


def test_search_rag_semantic_tolerates_nested_lists(monkeypatch) -> None:
    monkeypatch.setenv("RAG_API_KEY", "dummy")

    def fake_post(endpoint, payload, api_key, base_url):
        return {
            "status": "ok",
            "answer": "respuesta",
            "sources": [[{"title": "Doc A", "uri": "a.md"}], {"title": "Doc B", "uri": "b.md"}],
            "semantic_results": [[{"uri": "a.md", "score": 0.91}], {"uri": "b.md", "score": 0.77}],
            "request_id": "req-1",
        }

    monkeypatch.setattr(rag_search_tools, "_flamehaven_post", fake_post)

    result = rag_search_tools.search_rag_semantic(_config(), {"query": "eucaristía"})

    assert result["status"] == "ok"
    assert result["answer"] == "respuesta"
    assert result["sources"] == [
        {"title": "Doc A", "uri": "a.md"},
        {"title": "Doc B", "uri": "b.md"},
    ]
    assert result["semantic_results"] == [
        {"uri": "a.md", "score": 0.91},
        {"uri": "b.md", "score": 0.77},
    ]
