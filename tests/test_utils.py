from types import SimpleNamespace

from src import utils


def test_cached_text_fetches_once_then_reads_from_cache(tmp_path, monkeypatch):
    calls = []

    def fake_http_get(url, *, headers=None, timeout=15.0, sleep_after=0.0):
        calls.append(url)
        return SimpleNamespace(text="hello world")

    monkeypatch.setattr(utils, "http_get", fake_http_get)
    cache_path = tmp_path / "nested" / "page.html"

    first = utils.cached_text("http://example.com/page", cache_path)
    assert first == "hello world"
    assert cache_path.read_text(encoding="utf-8") == "hello world"
    assert calls == ["http://example.com/page"]

    second = utils.cached_text("http://example.com/page", cache_path)
    assert second == "hello world"
    assert calls == ["http://example.com/page"]  # no second HTTP call


def test_cached_text_passes_through_headers_and_timeout(tmp_path, monkeypatch):
    seen = {}

    def fake_http_get(url, *, headers=None, timeout=15.0, sleep_after=0.0):
        seen["headers"] = headers
        seen["timeout"] = timeout
        return SimpleNamespace(text="ok")

    monkeypatch.setattr(utils, "http_get", fake_http_get)
    cache_path = tmp_path / "page.html"

    utils.cached_text("http://example.com", cache_path, headers={"User-Agent": "test"}, timeout=5.0)
    assert seen == {"headers": {"User-Agent": "test"}, "timeout": 5.0}
