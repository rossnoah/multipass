"""Offline tests for Arch, AlmaLinux, Rocky, Kali scrapers — mocks aiohttp.

These tests avoid network I/O so they can run in CI without reaching
upstream mirrors. Live end-to-end behavior is covered by the scheduled
`Update Cloud Images` workflow.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.models import ScraperResult
from scraper.scrapers.arch import ArchScraper
from scraper.scrapers.almalinux import AlmaLinuxScraper
from scraper.scrapers.rocky import RockyScraper
from scraper.scrapers.kali import KaliScraper


class _FakeResponse:
    def __init__(self, text="", status=200, headers=None):
        self._text = text
        self.status = status
        self.headers = headers or {}

    async def text(self):
        return self._text

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _fake_session_for_responses(response_map):
    """Build a fake aiohttp.ClientSession whose GET/HEAD look up response_map by URL."""
    session = MagicMock()

    def _get(url, **kwargs):
        resp = response_map.get(("GET", url)) or response_map.get(url)
        if resp is None:
            return _FakeResponse(status=404)
        return resp

    def _head(url, **kwargs):
        resp = response_map.get(("HEAD", url))
        if resp is None:
            return _FakeResponse(status=200, headers={"Content-Length": "12345"})
        return resp

    session.get = _get
    session.head = _head
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_arch_scraper_builds_valid_result():
    responses = {
        ("GET", "https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2.SHA256"):
            _FakeResponse(text="a" * 64 + "  Arch-Linux-x86_64-cloudimg.qcow2\n"),
        ("HEAD", "https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"):
            _FakeResponse(headers={"Content-Length": "555"}),
    }
    session = _fake_session_for_responses(responses)

    with patch("scraper.scrapers.arch.aiohttp.ClientSession", return_value=session):
        result = _run(ArchScraper().fetch())

    ScraperResult(**result)
    assert result["os"] == "Arch"
    assert list(result["items"]) == ["x86_64"]
    assert result["items"]["x86_64"]["id"] == "a" * 64
    assert result["items"]["x86_64"]["size"] == 555


def test_almalinux_scraper_falls_back_when_latest_missing():
    listing = '<a href="10/">10/</a> <a href="9/">9/</a>'
    checksum_9 = (
        "SHA256 (AlmaLinux-9-GenericCloud-latest.x86_64.qcow2) = " + "b" * 64 + "\n"
    )

    responses = {
        ("GET", "https://repo.almalinux.org/almalinux/"): _FakeResponse(text=listing),
        ("GET", "https://repo.almalinux.org/almalinux/10/cloud/x86_64/images/CHECKSUM"):
            _FakeResponse(status=404),
        ("GET", "https://repo.almalinux.org/almalinux/10/cloud/aarch64/images/CHECKSUM"):
            _FakeResponse(status=404),
        ("GET", "https://repo.almalinux.org/almalinux/10/cloud/s390x/images/CHECKSUM"):
            _FakeResponse(status=404),
        ("GET", "https://repo.almalinux.org/almalinux/10/cloud/ppc64le/images/CHECKSUM"):
            _FakeResponse(status=404),
        ("GET", "https://repo.almalinux.org/almalinux/9/cloud/x86_64/images/CHECKSUM"):
            _FakeResponse(text=checksum_9),
        ("GET", "https://repo.almalinux.org/almalinux/9/cloud/aarch64/images/CHECKSUM"):
            _FakeResponse(status=404),
        ("GET", "https://repo.almalinux.org/almalinux/9/cloud/s390x/images/CHECKSUM"):
            _FakeResponse(status=404),
        ("GET", "https://repo.almalinux.org/almalinux/9/cloud/ppc64le/images/CHECKSUM"):
            _FakeResponse(status=404),
        ("HEAD",
         "https://repo.almalinux.org/almalinux/9/cloud/x86_64/images/AlmaLinux-9-GenericCloud-latest.x86_64.qcow2"):
            _FakeResponse(headers={"Content-Length": "777"}),
    }
    session = _fake_session_for_responses(responses)

    with patch("scraper.scrapers.almalinux.aiohttp.ClientSession", return_value=session):
        result = _run(AlmaLinuxScraper().fetch())

    ScraperResult(**result)
    assert result["release"] == "9"
    assert "x86_64" in result["items"]
    assert result["items"]["x86_64"]["id"] == "b" * 64


def test_rocky_scraper_raises_when_no_candidate_has_images():
    listing = '<a href="10/">10/</a>'

    responses = {
        ("GET", "https://download.rockylinux.org/pub/rocky/"): _FakeResponse(text=listing),
    }
    session = _fake_session_for_responses(responses)

    with patch("scraper.scrapers.rocky.aiohttp.ClientSession", return_value=session):
        with pytest.raises(RuntimeError):
            _run(RockyScraper().fetch())


def test_kali_scraper_builds_valid_result():
    listing = '<a href="current/">current/</a> <a href="kali-2026.1/">kali-2026.1/</a> <a href="kali-2025.4/">kali-2025.4/</a>'
    sha256sums = (
        "a" * 64 + "  kali-linux-2026.1-cloud-genericcloud-amd64.tar.xz\n"
        + "b" * 64 + "  kali-linux-2026.1-cloud-genericcloud-arm64.tar.xz\n"
    )

    responses = {
        ("GET", "https://kali.download/cloud-images/"): _FakeResponse(text=listing),
        ("GET", "https://kali.download/cloud-images/kali-2026.1/SHA256SUMS"):
            _FakeResponse(text=sha256sums),
        ("HEAD", "https://kali.download/cloud-images/kali-2026.1/kali-linux-2026.1-cloud-genericcloud-amd64.tar.xz"):
            _FakeResponse(headers={"Content-Length": "200605491"}),
        ("HEAD", "https://kali.download/cloud-images/kali-2026.1/kali-linux-2026.1-cloud-genericcloud-arm64.tar.xz"):
            _FakeResponse(headers={"Content-Length": "187040972"}),
    }
    session = _fake_session_for_responses(responses)

    with patch("scraper.scrapers.kali.aiohttp.ClientSession", return_value=session):
        result = _run(KaliScraper().fetch())

    ScraperResult(**result)
    assert result["os"] == "Kali"
    assert result["release"] == "2026.1"
    assert set(result["items"]) == {"x86_64", "arm64"}
    assert result["items"]["x86_64"]["id"] == "a" * 64
    assert result["items"]["arm64"]["id"] == "b" * 64
    assert result["items"]["x86_64"]["size"] == 200605491


def test_kali_scraper_raises_when_no_versions_found():
    listing = '<a href="current/">current/</a>'

    responses = {
        ("GET", "https://kali.download/cloud-images/"): _FakeResponse(text=listing),
    }
    session = _fake_session_for_responses(responses)

    with patch("scraper.scrapers.kali.aiohttp.ClientSession", return_value=session):
        with pytest.raises(RuntimeError):
            _run(KaliScraper().fetch())
