import re
import aiohttp
import asyncio
from ..base import BaseScraper
from ..models import SUPPORTED_ARCHITECTURES


BASE_URL = "https://download.rockylinux.org/pub/rocky/"

ARCH_MAP = {
    "arm64": "aarch64",
    "power64le": "ppc64le",
}


class RockyScraper(BaseScraper):
    @property
    def name(self) -> str:
        return "Rocky"

    async def _candidate_versions(self, session: aiohttp.ClientSession) -> list[str]:
        text = await self._fetch_text(session, BASE_URL)
        versions = sorted(
            {int(m) for m in re.findall(r'href="(\d+)/"', text)},
            reverse=True,
        )
        if not versions:
            raise RuntimeError("No Rocky Linux versions discovered")
        self.logger.info("Candidate Rocky versions (desc): %s", versions)
        return [str(v) for v in versions]

    async def _fetch_image_for_arch(
        self, session: aiohttp.ClientSession, version: str, label: str
    ) -> tuple[str, dict]:
        rocky_arch = ARCH_MAP.get(label, label)
        # Rocky 10 renamed the base cloud image from "GenericCloud" to
        # "GenericCloud-Base" (alongside a new "GenericCloud-LVM" variant).
        # Try the current name first, then fall back to the legacy one.
        filename_candidates = [
            f"Rocky-{version}-GenericCloud-Base.latest.{rocky_arch}.qcow2",
            f"Rocky-{version}-GenericCloud.latest.{rocky_arch}.qcow2",
        ]

        last_error: Exception | None = None
        for filename in filename_candidates:
            image_url = f"{BASE_URL}{version}/images/{rocky_arch}/{filename}"
            checksum_url = f"{image_url}.CHECKSUM"
            try:
                text = await self._fetch_text(session, checksum_url)
            except aiohttp.ClientResponseError as e:
                if e.status == 404:
                    last_error = e
                    continue
                raise
            m = re.search(rf"SHA256\s*\(\s*{re.escape(filename)}\s*\)\s*=\s*([0-9a-f]+)", text)
            if not m:
                m = re.search(rf"([0-9a-f]{{64}})\s+\*?{re.escape(filename)}", text)
            if not m:
                raise RuntimeError(f"SHA256 not found for {filename}")
            sha256 = m.group(1)

            size = await self._head_content_length(session, image_url)
            return label, {
                "image_location": image_url,
                "id": sha256,
                "version": version,
                "size": size or 0,
            }

        raise RuntimeError(
            f"No Rocky image found for {version} {rocky_arch}: {last_error}"
        )

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
                        self.logger.info("Skipping Rocky %s %s: %s", version, label, result)
                    else:
                        _, data = result
                        items[label] = data

                if items:
                    self.logger.info("Using Rocky version %s", version)
                    return {
                        "aliases": "rocky, rockylinux",
                        "os": "Rocky",
                        "release": version,
                        "release_codename": version,
                        "release_title": version,
                        "items": items,
                    }

            raise RuntimeError("No Rocky images available for any candidate version")
