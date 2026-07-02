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
    """Translate product title: Chinese → Russian (Ozon-optimized)."""
    # Filter wholesale/supply/retail terms from Chinese
    banned_cn = ["批发", "货源", "供应商", "厂家", "工厂", "一手", "拿货", "进货", "代理", "桌面相框", "相框摆件", "摆件", "半成品"]
    for w in banned_cn:
        text = text.replace(w, "")
    if not settings.DEEPSEEK_API_KEY:
        return text

    prompt = f"""将此中文商品标题翻译为Ozon平台俄语标题。翻译规则：

1. 标题以"Набор для вышивки"或"Полный набор вышивки"开头
2. 图案描述用"рисунок с [主体]"，不是"[主体] с вышивкой"
3. 绣绷翻译为"пяльцы"，不是"рамка"
4. 禁止：оптовая, оптом, полуфабрикат, рамка, поставщик, источник, фоторамка, настольная рамка
5. 格式：品类 + 图案 + 尺寸29см + 技法 + 受众
6. 只返回翻译标题，不要解释

中文: {text}"""

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
            "description_ru": f"{title_cn}",
            "keywords": "",
        }

    kw_text = f"\n关键词提示: {keywords_cn}" if keywords_cn else ""
    cat_text = f"\n类目: {category}" if category else ""

    prompt = f"""你是Ozon刺绣类目的资深俄语运营。根据中文商品名生成俄语标题、描述、关键词。

商品中文: {title_cn}{cat_text}{kw_text}

=== 正确描述范例（必须模仿此风格和质量）===
Полный набор объемной вышивки гладью «Садовая сказка» – это всё необходимое для создания очаровательного панно с милым лесным ёжиком среди садовых цветов и зелени. В комплект входят: канва с нанесённым цветным рисунком, маркированные нитки мулине, пара вышивальных игл, деревянные круглые пяльцы диаметром 20 см, деревянная подставка под пяльцы, подробная цветовая схема и иллюстрированная пошаговая инструкция. Размер готового вышитого рисунка 29 см, изделие можно поставить на подставку как настольный декор или повесить на стену, также станет прекрасным душевным подарком. Набор идеально подойдёт как абсолютным новичкам без опыта, так и опытным любителям рукоделия. Творите с удовольствием!

=== 描述要求 ===
- 纯文本，不要<p>标签，200-400字符
- 第一句品类关键词：Полный набор объемной вышивки гладью（立体缎面绣）
- 图案描述基于中文标题如实描述，不要捏造不存在的花卉品种。中文没提的花不要加。用通用词：цветы, садовые цветы, полевые цветы, растительный орнамент
- 工具描述要详细：пара вышивальных игл（两根针）、маркированные нитки мулине（分色线）、деревянная подставка под пяльцы（绣绷支架）
- 使用场景明确：поставить на подставку как настольный декор или повесить на стену
- 受众精准：абсолютным новичкам без опыта（零基础）
- 图纸=цветовая схема（配色图），教程=иллюстрированная пошаговая инструкция（图文分步）
- 禁止：рамка, полуфабрикат, настольная рамка, фоторамка, оптовая, поставщик, производитель

=== 标题要求 ===
Набор для вышивки + 图案(рисунок с X) + 29 см + объемная вышивка гладью + пяльцы + 受众

=== 关键词 ===
首个 #набор_для_вышивки，5-10个，以#隔开

输出JSON（描述不要<p>）：
{{"title_ru": "...", "description_ru": "...", "keywords": "#tag1 #tag2 ..."}}"""

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
            result = json.loads(content)
            # Strip HTML tags from description
            import re
            result["description_ru"] = re.sub(r"</?p>", "", result.get("description_ru", ""))
            return result
        logger.error("Description generation failed: %s", resp.text[:300])
        return {
            "title_ru": title_cn,
            "description_ru": f"{title_cn}",
            "keywords": "",
        }
