"""DeepSeek translation service — Chinese → Russian for OZON product listings."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ── Translation prompt ──────────────────────────────────────────────

TRANSLATION_SYSTEM_PROMPT = """你是跨境电商的俄语翻译专家。将以下 1688 刺绣套装商品信息翻译为俄语，用于 OZON 平台上架。

要求：
1. 标题(title_ru) ≤500 字符，包含核心搜索关键词，突出"набор для вышивания"
2. 描述(description_ru) 300-1000 字符，HTML 格式，包含：套装内容、材质、用途、尺寸
3. 材质(material_ru) 简短准确
4. 包装(package_type_ru) 简短，2-5 个词
5. SKU spec_ru 中的尺寸/颜色使用 OZON 平台标准俄语表达

请严格输出以下 JSON 格式，不要输出任何其他内容：
{
  "title_ru": "...",
  "description_ru": "<p>...</p>",
  "material_ru": "...",
  "package_type_ru": "...",
  "skus_ru": [{"original_spec": "中文规格", "spec_ru": "русская спецификация"}]
}"""


# ── Service ─────────────────────────────────────────────────────────


class TranslationService:
    """Translates Chinese product info to Russian via DeepSeek API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = (base_url or settings.DEEPSEEK_BASE_URL).rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
        }

    async def translate_product(
        self,
        title_cn: str,
        material_cn: str | None = None,
        package_type_cn: str | None = None,
        description_cn: str | None = None,
        skus_cn: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Translate all product fields at once.

        Args:
            title_cn: Chinese product title
            material_cn: Chinese material description
            package_type_cn: Chinese packaging description
            description_cn: Optional longer description
            skus_cn: List of SKU dicts with 'spec' key

        Returns:
            Dict with title_ru, description_ru, material_ru,
            package_type_ru, skus_ru
        """
        if not self.is_configured:
            raise TranslationError("DEEPSEEK_API_KEY is not configured")

        # Build the user message
        user_data: dict[str, Any] = {"title_cn": title_cn}
        if material_cn:
            user_data["material_cn"] = material_cn
        if package_type_cn:
            user_data["package_type_cn"] = package_type_cn
        if description_cn:
            user_data["description_cn"] = description_cn
        if skus_cn:
            user_data["skus_cn"] = skus_cn

        user_message = json.dumps(user_data, ensure_ascii=False, indent=2)

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                response = await client.post(
                    f"{self.base_url}/v1/messages",
                    headers=self._headers,
                    json={
                        "model": "deepseek-v4-pro",
                        "max_tokens": 2048,
                        "temperature": 0.3,
                        "system": TRANSLATION_SYSTEM_PROMPT,
                        "messages": [
                            {"role": "user", "content": user_message},
                        ],
                    },
                )

            if response.status_code != 200:
                raise TranslationError(
                    f"DeepSeek API error {response.status_code}: "
                    f"{response.text[:500]}"
                )

            result = response.json()

            # Parse the DeepSeek (Anthropic-compatible) response
            content = (
                result.get("content", [{}])[0]
                .get("text", "")
            )

            if not content:
                # Try alternate response format
                content = result.get("choices", [{}])[0].get(
                    "message", {}
                ).get("content", "")

            if not content:
                raise TranslationError(
                    f"Empty response from DeepSeek: {json.dumps(result)[:500]}"
                )

            # Parse the JSON from the response
            translated = self._parse_json_response(content)

            logger.info(
                "Translated title: '%s' → '%s'",
                title_cn[:50],
                translated.get("title_ru", "")[:50],
            )
            return translated

        except httpx.TimeoutException:
            raise TranslationError("DeepSeek API request timed out")
        except json.JSONDecodeError as e:
            raise TranslationError(f"Failed to parse translation response: {e}")

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Extract JSON from LLM response, handling markdown code blocks."""
        content = content.strip()

        # Remove markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```json or ```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        return json.loads(content)


class TranslationError(Exception):
    """Raised when translation fails."""
