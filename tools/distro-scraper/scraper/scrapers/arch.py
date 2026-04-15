import aiohttp
from ..base import BaseScraper


IMAGE_URL = "https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
CHECKSUM_URL = IMAGE_URL + ".SHA256"


class ArchScraper(BaseScraper):
    """
    Arch Linux cloud image scraper.

    Arch only publishes an official x86_64 cloud image; aarch64 is not available
    from upstream, so only x86_64 is populated here.
    """

    @property
    def name(self) -> str:
        return "Arch"

    async def fetch(self) -> dict:
        async with aiohttp.ClientSession() as session:
            checksum_text = await self._fetch_text(session, CHECKSUM_URL)
            sha256 = checksum_text.split()[0].strip()
            if len(sha256) != 64:
                raise RuntimeError(f"Unexpected Arch checksum format: {checksum_text!r}")

            size = await self._head_content_length(session, IMAGE_URL)

            return {
                "aliases": "arch, archlinux",
                "os": "Arch",
                "release": "rolling",
                "release_codename": "rolling",
                "release_title": "Rolling",
                "items": {
                    "x86_64": {
                        "image_location": IMAGE_URL,
                        "id": sha256,
                        "version": "latest",
                        "size": size or 0,
                    }
                },
            }
