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


async def translate_text(text: str, target: str = "ru") -> str:
    """Simple text translation: Chinese → Russian using DeepSeek."""
    # Filter wholesale/supply terms from Chinese text
    banned_cn = ["批发", "货源", "供应商", "厂家", "工厂", "一手", "拿货", "进货", "代理"]
    for w in banned_cn:
        text = text.replace(w, "")
    if not settings.DEEPSEEK_API_KEY:
        return text  # Return original if not configured

    prompt = f"Translate the following Chinese text to Russian. Return ONLY the translation, no explanation:\n\n{text}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.DEEPSEEK_BASE_URL}/v1/messages",
            headers={
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.3,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["content"][0]["text"].strip()
        logger.error("Translation failed: %s", resp.text[:300])
        return text


async def generate_ozon_description(
    title_cn: str,
    keywords_cn: str = "",
    category: str = "",
) -> dict[str, str]:
    """Generate Russian product description and keywords for Ozon using DeepSeek."""
    if not settings.DEEPSEEK_API_KEY:
        return {
            "title_ru": title_cn,
            "description_ru": f"<p>{title_cn}</p>",
            "keywords": "",
        }

    kw_text = f"\n关键词提示: {keywords_cn}" if keywords_cn else ""
    cat_text = f"\n类目: {category}" if category else ""

    prompt = f"""你是Ozon俄罗斯电商平台的资深俄语运营专家。为以下商品生成俄语标题、描述和关键词。

商品中文名称: {title_cn}{cat_text}{kw_text}

=== 正确标题范例（必须模仿）===
Полный набор объемной вышивки гладью, рисунок с лесным ёжиком и полевыми цветами размером 29 см, деревянные круглые пяльцы 20 см, DIY рукоделие для начинающих, домашний настенный декор

=== 标题规范 ===
1. 开头必须用"Полный набор вышивки"或"Набор для вышивки"，先说明品类
2. 用"рисунок с [主体] и [背景]"描述图案（рисунок с = 图案的内容是），不说"[主体] с вышивкой"
3. 尺寸29 см紧随图案描述
4. 专业词汇：绣绷=пяльцы（不是рамка），全套=полный набор/готовый комплект（不是полуфабрикат）
5. 以使用场景/受众收尾：для начинающих, домашний декор, подарок
6. 严禁出现：оптовая, оптом, поставщик, производитель, фабрика, полуфабрикат, рамка, заготовка, источник

=== 描述规范 ===
- HTML格式<p>...</p>，200-500字符
- 第一句说明这是全套刺绣套装（полный набор для вышивания）
- 列出包含内容：канва с рисунком, нитки мулине, игла, пяльцы, схема
- 面向个人买家，语气温暖自然
- 禁止批发/供应/工厂/半成品相关词汇

=== 关键词规范 ===
- 5-10个，以#隔开
- 首个必须是 #набор_для_вышивки
- 包含技法词、受众词、场景词

严格输出JSON，不要其他内容：
{{"title_ru": "...", "description_ru": "<p>...</p>", "keywords": "#tag1 #tag2 ..."}}"""

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.DEEPSEEK_BASE_URL}/v1/messages",
            headers={
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.7,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["content"][0]["text"].strip()
            # Parse JSON from response
            if content.startswith("```"):
                lines = content.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                content = "\n".join(lines)
            return json.loads(content)
        logger.error("Description generation failed: %s", resp.text[:300])
        return {
            "title_ru": title_cn,
            "description_ru": f"<p>{title_cn}</p>",
            "keywords": "",
        }
