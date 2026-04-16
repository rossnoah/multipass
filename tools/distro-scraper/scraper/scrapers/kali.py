import re
import asyncio
import aiohttp
from ..base import BaseScraper


BASE_URL = "https://kali.download/cloud-images/"

ARCH_MAP = {
    "x86_64": "amd64",
    "arm64": "arm64",
}


class KaliScraper(BaseScraper):
    """
    Kali Linux cloud image scraper.

    Kali publishes genericcloud images for amd64 and arm64 as tar.xz archives
    containing qcow2 disk images.
    """

    @property
    def name(self) -> str:
        return "Kali"

    async def _latest_version(self, session: aiohttp.ClientSession) -> str:
        text = await self._fetch_text(session, BASE_URL)
        versions = sorted(
            re.findall(r'href="kali-(\d{4}\.\d+)/"', text),
            reverse=True,
        )
        if not versions:
            raise RuntimeError("No Kali versions discovered")
        self.logger.info("Candidate Kali versions (desc): %s", versions)
        return versions[0]

    async def _fetch_checksum(
        self, session: aiohttp.ClientSession, version: str, kali_arch: str
    ) -> str:
        url = f"{BASE_URL}kali-{version}/SHA256SUMS"
        text = await self._fetch_text(session, url)
        filename = f"kali-linux-{version}-cloud-genericcloud-{kali_arch}.tar.xz"
        for line in text.strip().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].strip() == filename:
                sha256 = parts[0].strip()
                if len(sha256) == 64:
                    return sha256
        raise RuntimeError(f"SHA256 not found for {filename}")

    async def _fetch_image_for_arch(
        self, session: aiohttp.ClientSession, version: str, label: str
    ) -> tuple[str, dict]:
        kali_arch = ARCH_MAP[label]
        filename = f"kali-linux-{version}-cloud-genericcloud-{kali_arch}.tar.xz"
        image_url = f"{BASE_URL}kali-{version}/{filename}"

        sha256 = await self._fetch_checksum(session, version, kali_arch)
        size = await self._head_content_length(session, image_url)

        return label, {
            "image_location": image_url,
            "id": sha256,
            "version": version,
            "size": size or 0,
        }

    async def fetch(self) -> dict:
        async with aiohttp.ClientSession() as session:
            version = await self._latest_version(session)

            results = await asyncio.gather(
                *[
                    self._fetch_image_for_arch(session, version, label)
                    for label in ARCH_MAP
                ],
                return_exceptions=True,
            )

            items: dict[str, dict] = {}
            for label, result in zip(ARCH_MAP, results):
                if isinstance(result, Exception):
                    self.logger.info("Skipping Kali %s %s: %s", version, label, result)
                else:
                    _, data = result
                    items[label] = data

            if not items:
                raise RuntimeError(f"No Kali images available for version {version}")

            return {
                "aliases": "kali, kalilinux, kali-linux",
                "os": "Kali",
                "release": version,
                "release_codename": version,
                "release_title": version,
                "items": items,
            }
