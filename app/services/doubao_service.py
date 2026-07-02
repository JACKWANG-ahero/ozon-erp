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

OZON_PROMPT = """Ты профессиональный копирайтер Ozon для товаров по рукоделию. Посмотри на фото товара и его китайское название. Создай:

1. title_ru: Заголовок для Ozon (80-120 символов).
   - Начинается с "Набор для вышивки" или "Полный набор вышивки"
   - Описывает ТОЛЬКО то, что видно на фото
   - Включает: техника вышивки + что изображено + размер 29 см + для кого
   - Пример: "Набор для вышивки гладью с рисунком птиц и цветов 29 см, объемная вышивка, в комплекте пяльцы, для начинающих"

2. description_ru: Полное Ozon-описание (500-1000 символов, без HTML-тегов!).
   Структура:
   - 1-й абзац: что это за набор, какая техника, что получится в итоге
   - 2-й абзац: ПОЛНЫЙ состав комплекта (канва с рисунком, маркированные нитки мулине, пара игл, деревянные пяльцы 20 см, подставка под пяльцы, цветовая схема, пошаговая инструкция)
   - 3-й абзац: размер готовой работы 29 см, варианты использования (настольный декор, на стену, подарок)
   - 4-й абзац: для кого подходит (новички без опыта, опытные), эмоции от процесса
   - Тёплый, доверительный тон. Опирайся ТОЛЬКО на то, что видно на фото.

3. keywords: МИНИМУМ 28 русских ключевых слов через #, разделённых пробелом.
   Требования Ozon:
   - Первое: #набор_для_вышивки
   - Включи: вид вышивки, технику, тематику, размер, аудиторию, повод, материал, стиль
   - Примеры: #вышивка_гладью #объемная_вышивка #птицы_на_канве #29см #для_начинающих #подарок_рукодельнице #набор_с_пяльцами #ручная_работа #хобби_для_женщин #творческий_подарок #вышивка_цветы #дизайн_интерьера #уютный_дом #сделай_сам #канва_с_рисунком #мулине #деревянные_пяльцы #пошаговая_инструкция #рукоделие_для_всех #настенный_декор #подарок_маме #антистресс_хобби #вечернее_хобби #творчество_для_души #ручная_работа_для_дома #декор_ручной_работы #украшение_интерьера #вышивка_для_релакса

ЗАПРЕЩЕНО: оптовая, оптом, поставщик, производитель, фабрика, полуфабрикат, рамка, фоторамка, заготовка, источник, настольная рамка, продажа, дешево, акция, скидка

Выведи ТОЛЬКО JSON:
{"title_ru": "...", "description_ru": "...", "keywords": "#tag1 #tag2 ..."}"""


async def doubao_ozon_listing(
    image_paths: list[str],
    title_cn: str,
) -> dict[str, str]:
    """Send image(s) + Chinese title to Doubao, get Ozon Russian listing.

    Returns: {"title_ru": ..., "description_ru": ..., "keywords": ...}
    """
    if not settings.DOUBAO_API_KEY:
        return {"error": "豆包 API 未配置"}

    # Build content array
    content: list[dict] = []

    # Add images (up to 5)
    for path in image_paths[:5]:
        try:
            img_bytes = Path(path).read_bytes()
            b64 = base64.b64encode(img_bytes).decode()
            content.append({
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{b64}",
            })
        except Exception as e:
            logger.warning("Failed to read image %s: %s", path, e)

    # Add text prompt
    content.append({
        "type": "input_text",
        "text": f"Китайское название товара: {title_cn}\n\n{OZON_PROMPT}",
    })

    payload = {
        "model": settings.DOUBAO_MODEL,
        "input": [{"role": "user", "content": content}],
    }

    url = f"{settings.DOUBAO_BASE_URL}/responses"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.DOUBAO_API_KEY}",
                "Content-Type": "application/json",
            },
        )

        if resp.status_code != 200:
            logger.error("Doubao API error %d: %s", resp.status_code, resp.text[:500])
            return {"error": f"豆包 API 返回 {resp.status_code}"}

        data = resp.json()

    # Parse response
    try:
        # ARK v3 responses API format
        output = data.get("output", [{}])[0]
        text = output.get("content", [{}])[0].get("text", "")
        if not text:
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Extract JSON from text
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            text = "\n".join(lines)

        result = json.loads(text)
        # Strip HTML tags
        import re
        result["description_ru"] = re.sub(r"</?p>", "", result.get("description_ru", ""))
        return result
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error("Failed to parse Doubao response: %s", e)
        return {"error": f"解析豆包返回失败: {e}", "raw": str(data)[:500]}
