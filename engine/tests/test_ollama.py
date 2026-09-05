from app.services.ollama import _highlight_map, ollama_available


def test_ollama_probe_does_not_require_daemon():
    assert ollama_available("http://127.0.0.1:9", timeout=0.2) is False


def test_ollama_parses_highlight_shapes():
    mapped = _highlight_map(
        {
            "highlights": {"work[0].highlights[0]": "Kept FastAPI on PostgreSQL."},
            "work": [{"highlights": [{"path": "work[1].highlights[0]", "text": "Cut latency 40%."}]}],
        }
    )
    assert mapped["work[0].highlights[0]"].startswith("Kept FastAPI")
    assert mapped["work[1].highlights[0]"].startswith("Cut latency")
