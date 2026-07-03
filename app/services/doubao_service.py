"""Doubao (豆包) multimodal translation — image + Chinese → Ozon Russian."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def _call_doubao(image_paths: list[str], prompt_text: str) -> str | None:
    """Call Doubao multimodal API. Returns text response or None on error."""
    if not settings.DOUBAO_API_KEY:
        return None

    content: list[dict] = []

    for path in image_paths[:5]:
        try:
            img_bytes = Path(path).read_bytes()
            b64 = base64.b64encode(img_bytes).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
        except Exception as e:
            logger.warning("Failed to read image %s: %s", path, e)

    content.append({"type": "text", "text": prompt_text})

    payload = {
        "model": settings.DOUBAO_MODEL,
        "messages": [{"role": "user", "content": content}],
    }

    url = f"{settings.DOUBAO_BASE_URL}/chat/completions"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            url, json=payload,
            headers={
                "Authorization": f"Bearer {settings.DOUBAO_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            logger.error("Doubao API error %d: %s", resp.status_code, resp.text[:500])
            return None

        data = resp.json()

    try:
        # ARK standard: {"choices": [{"message": {"content": "..."}}]}
        text = data["choices"][0]["message"]["content"]
        return text.strip()
    except (KeyError, IndexError):
        return None


async def doubao_translate_title(
    image_paths: list[str],
    title_cn: str,
) -> str:
    """Translate Chinese title → Ozon Russian title (via Doubao multimodal)."""
    prompt = f"你好豆包，请根据图片和中文标题，翻译成适合在OZON上架的俄语标题。\n\n中文标题：{title_cn}"

    text = await _call_doubao(image_paths, prompt)
    if text is None:
        return title_cn  # fallback to original
    return text.strip().strip('"')


async def doubao_generate_description(
    image_paths: list[str],
    title_cn: str,
) -> dict[str, str]:
    """Generate Ozon Russian keywords + description (via Doubao multimodal)."""
    prompt = f"你好豆包，请根据图片和中文标题，翻译成适合在OZON上架的俄语关键词和商品简介。关键词要以#号隔开。\n\n中文标题：{title_cn}"

    text = await _call_doubao(image_paths, prompt)
    if text is None:
        return {"description_ru": title_cn, "keywords": ""}

    # Parse response — may be JSON or free text
    text = text.strip()
    result: dict[str, str] = {}

    # Try JSON first
    try:
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines)
        parsed = json.loads(text)
        result["description_ru"] = parsed.get("description_ru", parsed.get("description", ""))
        result["keywords"] = parsed.get("keywords", "")
        return result
    except (json.JSONDecodeError, KeyError):
        pass

    # Free text: try to split into keywords + description
    lines = text.split("\n")
    keywords = ""
    desc_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "#" in line:
            keywords = line
        else:
            desc_lines.append(line)

    result["description_ru"] = " ".join(desc_lines) if desc_lines else text
    result["keywords"] = keywords

    # Remove underscore from keywords (Ozon format)
    import re
    result["description_ru"] = re.sub(r"</?p>", "", result.get("description_ru", ""))
    kw_str = result.get("keywords", "")
    kws = [k.strip().replace("_", "").replace(" ", "") for k in kw_str.split("#") if k.strip()]
    result["keywords"] = "#" + " #".join(kws)

    return result
