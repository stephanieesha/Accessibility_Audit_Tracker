import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import limits


@pytest.fixture(autouse=True)
def reset_limits():
    limits.reset()
    yield
    limits.reset()


@pytest.mark.parametrize("url", [
    "http://localhost:5000",
    "http://127.0.0.1",
    "http://169.254.169.254/latest/meta-data",  # cloud metadata endpoint
    "http://192.168.1.5",
    "http://10.0.0.1",
    "http://metadata.google.internal",
])
def test_internal_addresses_are_blocked(url):
    safe, reason = limits.is_safe_url(url)
    assert safe is False
    assert reason


@pytest.mark.parametrize("url", ["ftp://example.com", "file:///etc/passwd", "not a url", ""])
def test_non_http_urls_are_blocked(url):
    safe, _ = limits.is_safe_url(url)
    assert safe is False


def test_a_normal_public_site_is_allowed():
    safe, reason = limits.is_safe_url("http://example.com")
    assert safe is True
    assert reason == ""


def test_write_rate_limit_is_off_by_default():
    for _ in range(100):
        assert limits.too_many_requests("1.2.3.4") is False


def test_write_rate_limit_when_configured(monkeypatch):
    monkeypatch.setenv("WRITE_LIMIT_PER_MINUTE", "2")
    results = [limits.too_many_requests("1.2.3.4") for _ in range(4)]
    assert results == [False, False, True, True]


def test_a_different_visitor_has_their_own_limit(monkeypatch):
    monkeypatch.setenv("WRITE_LIMIT_PER_MINUTE", "1")
    assert limits.too_many_requests("1.2.3.4") is False
    assert limits.too_many_requests("5.6.7.8") is False


def test_daily_scan_limit_is_off_by_default():
    for _ in range(100):
        assert limits.daily_scan_allowed() is True


def test_daily_scan_limit_when_configured(monkeypatch):
    monkeypatch.setenv("DAILY_SCAN_LIMIT", "2")
    results = [limits.daily_scan_allowed() for _ in range(3)]
    assert results == [True, True, False]
