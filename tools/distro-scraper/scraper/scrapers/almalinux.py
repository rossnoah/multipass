import re
import aiohttp
import asyncio
from ..base import BaseScraper
from ..models import SUPPORTED_ARCHITECTURES


BASE_URL = "https://repo.almalinux.org/almalinux/"

ARCH_MAP = {
    "arm64": "aarch64",
    "power64le": "ppc64le",
}


class AlmaLinuxScraper(BaseScraper):
    @property
    def name(self) -> str:
        return "AlmaLinux"

    async def _candidate_versions(self, session: aiohttp.ClientSession) -> list[str]:
        text = await self._fetch_text(session, BASE_URL)
        versions = sorted(
            {int(m) for m in re.findall(r'href="(\d+)/"', text)},
            reverse=True,
        )
        if not versions:
            raise RuntimeError("No AlmaLinux versions discovered")
        self.logger.info("Candidate AlmaLinux versions (desc): %s", versions)
        return [str(v) for v in versions]

    async def _fetch_checksum(
        self, session: aiohttp.ClientSession, url: str, filename: str
    ) -> str | None:
        text = await self._fetch_text(session, url)
        m = re.search(rf"SHA256\s*\(\s*{re.escape(filename)}\s*\)\s*=\s*([0-9a-f]+)", text)
        if m:
            return m.group(1)
        m = re.search(rf"([0-9a-f]{{64}})\s+\*?{re.escape(filename)}", text)
        return m.group(1) if m else None

    async def _fetch_image_for_arch(
        self, session: aiohttp.ClientSession, version: str, label: str
    ) -> tuple[str, dict]:
        alma_arch = ARCH_MAP.get(label, label)
        filename = f"AlmaLinux-{version}-GenericCloud-latest.{alma_arch}.qcow2"
        image_url = f"{BASE_URL}{version}/cloud/{alma_arch}/images/{filename}"
        checksum_url = f"{BASE_URL}{version}/cloud/{alma_arch}/images/CHECKSUM"

        sha256 = await self._fetch_checksum(session, checksum_url, filename)
        if not sha256:
            raise RuntimeError(f"SHA256 not found for {filename}")

        size = await self._head_content_length(session, image_url)
        return label, {
            "image_location": image_url,
            "id": sha256,
            "version": version,
            "size": size or 0,
        }

    async def fetch(self) -> dict:
        async with aiohttp.ClientSession() as session:
            candidates = await self._candidate_versions(session)

            for version in candidates:
                results = await asyncio.gather(
                    *[self._fetch_image_for_arch(session, version, label)
                      for label in SUPPORTED_ARCHITECTURES],
                    return_exceptions=True,
                )

                items: dict[str, dict] = {}
                for label, result in zip(SUPPORTED_ARCHITECTURES, results):
                    if isinstance(result, Exception):
                        self.logger.info("Skipping AlmaLinux %s %s: %s", version, label, result)
                    else:
                        _, data = result
                        items[label] = data

                if items:
                    self.logger.info("Using AlmaLinux version %s", version)
                    return {
                        "aliases": "alma, almalinux",
                        "os": "AlmaLinux",
                        "release": version,
                        "release_codename": version,
                        "release_title": version,
                        "items": items,
                    }

            raise RuntimeError("No AlmaLinux images available for any candidate version")
