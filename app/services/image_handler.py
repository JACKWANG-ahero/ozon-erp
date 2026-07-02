"""Image handler — download 1688 images, upload to GitHub CDN for OZON."""

from __future__ import annotations

import base64
import logging
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse, unquote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


async def upload_to_github_cdn(
    file_path: str | Path,
    repo: str = "ozon-cdn",
    folder: str = "products",
) -> str | None:
    """Upload a local image to GitHub repo and return a public raw URL.

    Flow: local file → base64 → PUT GitHub API → raw.githubusercontent.com URL

    Requires:
        settings.GITHUB_TOKEN — GitHub personal access token (repo scope)
        settings.GITHUB_OWNER  — GitHub username

    The target repo must exist and be public (or the token must have access).
    """
    token = getattr(settings, "GITHUB_TOKEN", "")
    owner = getattr(settings, "GITHUB_OWNER", "")
    if not token or not owner:
        logger.error("GITHUB_TOKEN or GITHUB_OWNER not configured")
        return None

    fp = Path(file_path)
    if not fp.exists():
        logger.error("File not found: %s", fp)
        return None

    ext = fp.suffix or ".jpg"
    remote_name = f"{uuid.uuid4().hex}{ext}"
    remote_path = f"{folder}/{remote_name}"

    # Read + base64 encode
    content_bytes = fp.read_bytes()
    content_b64 = base64.b64encode(content_bytes).decode("ascii")

    # GitHub API: create/update file
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{remote_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    body = {
        "message": f"Upload {remote_name}",
        "content": content_b64,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.put(url, json=body, headers=headers)
            if resp.status_code in (201, 200):
                data = resp.json()
                # Convert to raw URL
                sha = data.get("content", {}).get("sha", "")
                # raw URL pattern: https://raw.githubusercontent.com/{owner}/{repo}/main/{path}
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{remote_path}"
                logger.info("Uploaded %s → %s", fp.name, raw_url)
                return raw_url
            else:
                logger.error(
                    "GitHub upload failed HTTP %d: %s",
                    resp.status_code, resp.text[:300],
                )
                return None
        except Exception as e:
            logger.exception("GitHub upload error: %s", e)
            return None


async def upload_local_images_to_cdn(local_paths: list[str]) -> list[str]:
    """Batch upload local images to GitHub CDN. Returns list of raw URLs."""
    results = []
    for p in local_paths:
        url = await upload_to_github_cdn(p)
        if url:
            results.append(url)
        else:
            logger.warning("Failed to upload: %s", p)
    return results


class ImageHandler:
    """Download images from 1688 to local storage.

    Images are saved to: static/uploads/sourcing/{record_id}/
    And served at: {STATIC_URL}/uploads/sourcing/{record_id}/filename
    """

    def __init__(self, static_url: str | None = None) -> None:
        self.base_dir = settings.BASE_DIR / "app" / "static" / "uploads" / "sourcing"
        self.static_url = (static_url or "http://localhost:8000/static").rstrip("/")

    async def download_images(
        self,
        record_id: str,
        image_urls: list[str],
        detail_urls: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """Download all images for a sourcing record.

        Args:
            record_id: UUID of the sourcing record
            image_urls: Main product image URLs
            detail_urls: Detail/description image URLs

        Returns:
            Dict with 'main_paths', 'detail_paths', 'main_urls', 'detail_urls'
        """
        record_dir = self.base_dir / record_id
        record_dir.mkdir(parents=True, exist_ok=True)

        main_paths: list[str] = []
        main_urls: list[str] = []
        detail_paths: list[str] = []
        detail_urls: list[str] = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            # Download main images
            for i, url in enumerate(image_urls):
                try:
                    path, public_url = await self._download_one(
                        client, url, record_dir, f"main_{i:03d}"
                    )
                    if path:
                        main_paths.append(path)
                        main_urls.append(public_url)
                except Exception:
                    logger.warning("Failed to download main image %d: %s", i, url)

            # Download detail images
            if detail_urls:
                for i, url in enumerate(detail_urls):
                    try:
                        path, public_url = await self._download_one(
                            client, url, record_dir, f"detail_{i:03d}"
                        )
                        if path:
                            detail_paths.append(path)
                            detail_urls.append(public_url)
                    except Exception:
                        logger.warning("Failed to download detail image %d: %s", i, url)

        logger.info(
            "Downloaded %d main + %d detail images for record %s",
            len(main_paths), len(detail_paths), record_id,
        )

        return {
            "main_paths": main_paths,
            "detail_paths": detail_paths,
            "main_urls": main_urls,
            "detail_urls": detail_urls,
        }

    async def _download_one(
        self,
        client: httpx.AsyncClient,
        url: str,
        record_dir: Path,
        prefix: str,
    ) -> tuple[str | None, str | None]:
        """Download a single image. Returns (local_path, public_url)."""
        # Determine extension from URL
        parsed = urlparse(url)
        filename = unquote(os.path.basename(parsed.path))
        if not filename or "." not in filename:
            filename = f"{prefix}.jpg"

        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            ext = "jpg"
            filename = f"{prefix}.jpg"

        safe_name = f"{prefix}.{ext}"
        filepath = record_dir / safe_name

        # Skip if already downloaded
        if filepath.exists():
            public_url = self._public_url(record_dir.name, safe_name)
            return str(filepath), public_url

        # Download
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://detail.1688.com/",
        }

        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            filepath.write_bytes(response.content)
            public_url = self._public_url(record_dir.name, safe_name)
            return str(filepath), public_url

        logger.warning("HTTP %d downloading %s", response.status_code, url[:80])
        return None, None

    def _public_url(self, record_id: str, filename: str) -> str:
        return f"{self.static_url}/uploads/sourcing/{record_id}/{filename}"
