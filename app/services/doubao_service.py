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

3. keywords: ЧЕМ БОЛЬШЕ ТЕМ ЛУЧШЕ, минимум 15-25 русских ключевых слов через #.
   Формат: без пробелов и подчёркиваний, все слова слитно. Пример: #набордлявышивки #объемнаявышивка
   Первое всегда: #набордлявышивки
   Охвати ВСЕ категории (по 3-5 слов в каждой):
   - ТЕХНИКА: #объемнаявышивка #вышивкагладью #вышивкасвоимируками #ручнаявышивка
   - ЧТО НА ФОТО: опиши конкретные объекты (птицы, ёжик, цветы, листья и т.д.)
   - ИНСТРУМЕНТЫ: #круглыепяльцы20см #деревяннаяподставкадляпялец #цветныениткисмаркировкой #канвасрисунком
   - РАЗМЕР: #вышивка29см #набор29см
   - ДЛЯ КОГО: #рукоделиедляначинающих #DIYрукоделие #простоехобби #поделкисвоимируками
   - ИСПОЛЬЗОВАНИЕ: #настольныйдекор #настенныйдекор #домашнийукрашение #украшениедляспальни #украшениедлягостиной
   - ПОВОД: #подарокручнойработы #подарокнапраздник
   - МОТИВЫ: #цветочныемотивы #зоомотивы #леснойёжик #пионы
   - НАСТРОЕНИЕ: #уютныйдом #сделайсам #творчество

   ПРИМЕР ОТЛИЧНЫХ КЛЮЧЕВЫХ СЛОВ (формат):
   #набордлявышивки #объемнаявышивка #вышивкасвоимируками #вышивкасёжиком #леснойёжик #вышивкасцветами #пионынавышивке #круглыепяльцы20см #деревяннаяподставкадляпялец #DIYрукоделие #рукоделиедляначинающих #настольныйдекор #настенныйдекор #домашнийукрашение #вышивкагладью #полныйкомплектвышивки #цветныениткисмаркировкой #подарокручнойработы #украшениедляспальни #украшениедлягостиной #цветочныемотивы #зоомотивы #простоехобби #поделкисвоимируками

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

        # Ensure minimum 15+ keywords
        kws = [k.strip() for k in result.get("keywords", "").split("#") if k.strip()]
        if len(kws) < 15:
            fallback = [
                "набордлявышивки", "объемнаявышивка", "вышивкагладью",
                "вышивкасвоимируками", "круглыепяльцы20см",
                "деревяннаяподставкадляпялец", "цветныениткисмаркировкой",
                "канвасрисунком", "рукоделиедляначинающих", "DIYрукоделие",
                "полныйкомплектвышивки", "настольныйдекор", "настенныйдекор",
                "подарокручнойработы", "вышивка29см", "набор29см",
                "простоехобби", "поделкисвоимируками", "домашнийукрашение",
                "украшениедляспальни", "украшениедлягостиной",
                "цветочныемотивы", "зоомотивы", "ручнаяработа",
                "уютныйдом", "сделайсам", "творческийподарок",
                "подарокнапраздник", "пошаговаяинструкция",
                "ручнаявышивка",
            ]
            existing = set(kws)
            for fkw in fallback:
                if fkw not in existing:
                    kws.append(fkw)
                    existing.add(fkw)
            result["keywords"] = "#" + " #".join(kws)

        return result
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error("Failed to parse Doubao response: %s", e)
        return {"error": f"解析豆包返回失败: {e}", "raw": str(data)[:500]}
