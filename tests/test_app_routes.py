import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
import limits


@pytest.fixture
def client():
    limits.reset()
    test_client = app_module.app.test_client()
    yield test_client
    limits.reset()


def test_a_url_is_required(client):
    response = client.post("/scan", json={"url": ""})
    assert response.status_code == 400
    assert response.get_json()["error"] == "URL is required"


def test_only_http_and_https_are_accepted(client):
    response = client.post("/scan", json={"url": "ftp://example.com"})
    assert response.status_code == 400


def test_internal_addresses_are_rejected_before_any_scan_runs(client, monkeypatch):
    started = []
    monkeypatch.setattr(app_module.subprocess, "run", lambda *a, **k: started.append(1))

    response = client.post("/scan", json={"url": "http://169.254.169.254/"})

    assert response.status_code == 400
    assert started == []  # the scanner (and its browser) never started


def test_a_safe_url_reaches_the_scanner(client, monkeypatch):
    started = []

    class FakeResult:
        stdout = '{"url": "http://example.com", "total_violations": 0, "violations": []}'
        stderr = ""

    def fake_run(*args, **kwargs):
        started.append(args)
        return FakeResult()

    monkeypatch.setattr(app_module.subprocess, "run", fake_run)
    monkeypatch.setenv("DISABLE_HISTORY_LOG", "true")

    response = client.post("/scan", json={"url": "http://example.com"})

    assert started  # the scanner was actually invoked
    assert response.status_code == 200
    assert response.get_json()["total_violations"] == 0


def test_writes_are_rate_limited(client, monkeypatch):
    monkeypatch.setenv("WRITE_LIMIT_PER_MINUTE", "1")

    first = client.post("/scan", json={"url": ""})   # fails validation, but still counts as a write attempt
    second = client.post("/scan", json={"url": ""})

    assert first.status_code == 400
    assert second.status_code == 429


def test_daily_scan_cap(client, monkeypatch):
    monkeypatch.setenv("DAILY_SCAN_LIMIT", "1")
    monkeypatch.setenv("DISABLE_HISTORY_LOG", "true")

    class FakeResult:
        stdout = '{"url": "http://example.com", "total_violations": 0, "violations": []}'
        stderr = ""

    monkeypatch.setattr(app_module.subprocess, "run", lambda *a, **k: FakeResult())

    first = client.post("/scan", json={"url": "http://example.com"})
    second = client.post("/scan", json={"url": "http://example.com"})

    assert first.status_code == 200
    assert second.status_code == 429


def test_history_log_can_be_disabled_for_public_deployments(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DISABLE_HISTORY_LOG", "true")
    monkeypatch.setattr(app_module, "HISTORY_PATH", tmp_path / "history.jsonl")

    class FakeResult:
        stdout = '{"url": "http://example.com", "total_violations": 0, "violations": []}'
        stderr = ""

    monkeypatch.setattr(app_module.subprocess, "run", lambda *a, **k: FakeResult())

    client.post("/scan", json={"url": "http://example.com"})

    assert not (tmp_path / "history.jsonl").exists()


def test_not_indexed_by_search_engines(client):
    assert "noindex" in client.get("/").headers["X-Robots-Tag"]
    assert "Disallow: /" in client.get("/robots.txt").get_data(as_text=True)
