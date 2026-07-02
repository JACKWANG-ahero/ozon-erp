"""Sourcing API — receive 1688 scraped data, manage translations, push to OZON."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_ozon_client, templates, flash
from app.integrations.client import OzonClient, OzonAPIError
from app.models.sourcing import SourcingRecord, SourcingSku
from app.services.translation import TranslationService, TranslationError
from app.services.costing import CostCalculator, CostInput, RateConfig
from app.services.image_handler import ImageHandler
from app.services.product_builder import ProductBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sourcing", tags=["Sourcing"])


# ── Helper ──────────────────────────────────────────────────────────


def _record_to_dict(r: SourcingRecord) -> dict:
    """Serialize a SourcingRecord for template rendering."""
    return {
        "id": str(r.id),
        "source_url": r.source_url,
        "article_number": r.article_number,
        "title_cn": r.title_cn,
        "title_ru": r.title_ru,
        "material_cn": r.material_cn,
        "material_ru": r.material_ru,
        "package_type_cn": r.package_type_cn,
        "package_type_ru": r.package_type_ru,
        "description_ru": r.description_ru,
        "weight_kg": r.weight_kg,
        "length_cm": r.length_cm,
        "width_cm": r.width_cm,
        "height_cm": r.height_cm,
        "images_1688_urls": r.images_1688_urls or [],
        "images_local_paths": r.images_local_paths or [],
        "images_ozon_urls": r.images_ozon_urls or [],
        "status": r.status,
        "ozon_offer_id": r.ozon_offer_id,
        "ozon_product_id": r.ozon_product_id,
        "push_errors": r.push_errors,
        "cost_data": r.cost_data,
        "skus": [{"spec_cn": s.spec_cn, "spec_ru": s.spec_ru,
                   "price_cny": s.price_cny, "moq": s.moq}
                  for s in (r.skus or [])],
        "created_at": str(r.created_at),
        "pushed_at": str(r.pushed_at) if r.pushed_at else None,
    }


# ── Pages ────────────────────────────────────────────────────────────


@router.get("/")
async def sourcing_list(
    request: Request,
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List all sourcing records."""
    query = select(SourcingRecord).order_by(desc(SourcingRecord.created_at))
    count_query = select(func.count(SourcingRecord.id))

    if status:
        query = query.where(SourcingRecord.status == status)
        count_query = count_query.where(SourcingRecord.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query.offset(offset).limit(limit))
    records = result.scalars().all()

    items = [_record_to_dict(r) for r in records]

    return templates.TemplateResponse(
        request,
        "sourcing/list.html",
        {
            "page": "sourcing",
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
            "status_filter": status,
        },
    )


@router.get("/{record_id}")
async def sourcing_detail(
    request: Request,
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """View and edit a single sourcing record."""
    result = await db.execute(
        select(SourcingRecord).where(SourcingRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return templates.TemplateResponse(
            request,
            "sourcing/not_found.html",
            {"page": "sourcing", "record_id": str(record_id)},
            status_code=404,
        )

    return templates.TemplateResponse(
        request,
        "sourcing/detail.html",
        {"page": "sourcing", "record": _record_to_dict(record)},
    )


# ── API: Import from 1688 ───────────────────────────────────────────


@router.post("/api/import")
async def sourcing_import(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive scraped JSON from the 1688 browser script via AJAX."""
    body = await request.json()

    record = SourcingRecord(
        source_url=body.get("source_url", ""),
        article_number=body.get("article_number"),
        title_cn=body.get("title_cn", ""),
        material_cn=body.get("material_cn"),
        package_type_cn=body.get("package_type_cn"),
        description_cn=body.get("description_cn"),
        weight_kg=body.get("weight_kg"),
        length_cm=body.get("package_size", {}).get("length_cm")
                   if isinstance(body.get("package_size"), dict) else None,
        width_cm=body.get("package_size", {}).get("width_cm")
                  if isinstance(body.get("package_size"), dict) else None,
        height_cm=body.get("package_size", {}).get("height_cm")
                   if isinstance(body.get("package_size"), dict) else None,
        images_1688_urls=body.get("images_1688_urls", []),
        detail_images_1688_urls=body.get("detail_images_1688_urls", []),
        raw_data=body,
        status="draft",
    )
    db.add(record)
    await db.flush()  # get record.id

    # Save SKUs
    for sku_data in body.get("skus", []):
        sku = SourcingSku(
            record_id=record.id,
            spec_cn=sku_data.get("spec", ""),
            price_cny=sku_data.get("price_cny"),
            moq=sku_data.get("moq"),
            stock=sku_data.get("stock"),
        )
        db.add(sku)

    flash(request, f"已接收商品: {record.title_cn[:60]}", "success")
    return {
        "ok": True,
        "record_id": str(record.id),
        "redirect_url": f"/sourcing/{record.id}",
    }


# ── API: Translate ──────────────────────────────────────────────────


@router.post("/api/{record_id}/translate")
async def sourcing_translate(
    request: Request,
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Translate the Chinese fields of a sourcing record to Russian."""
    result = await db.execute(
        select(SourcingRecord).where(SourcingRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return {"ok": False, "error": "Record not found"}

    # Build SKU list
    skus_cn = [{"spec": s.spec_cn} for s in (record.skus or [])]

    try:
        translation = TranslationService()
        translated = await translation.translate_product(
            title_cn=record.title_cn,
            material_cn=record.material_cn,
            package_type_cn=record.package_type_cn,
            description_cn=record.description_cn,
            skus_cn=skus_cn if skus_cn else None,
        )

        # Update record
        record.title_ru = translated.get("title_ru", "")
        record.description_ru = translated.get("description_ru")
        record.material_ru = translated.get("material_ru")
        record.package_type_ru = translated.get("package_type_ru")

        # Update SKU translations
        skus_ru = translated.get("skus_ru", [])
        if skus_ru and record.skus:
            for i, sku in enumerate(record.skus):
                if i < len(skus_ru):
                    sku.spec_ru = skus_ru[i].get("spec_ru", "")

        record.status = "translated"
        await db.flush()

        flash(request, "翻译完成！请检查并修改。", "success")
        return {"ok": True, "translated": translated}

    except TranslationError as e:
        logger.exception("Translation failed for record %s", record_id)
        flash(request, f"翻译失败: {e}", "error")
        return {"ok": False, "error": str(e)}


# ── API: Calculate cost ─────────────────────────────────────────────


@router.post("/api/{record_id}/calculate")
async def sourcing_calculate(
    request: Request,
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Calculate profit estimate for a sourcing record."""
    result = await db.execute(
        select(SourcingRecord).where(SourcingRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return {"ok": False, "error": "Record not found"}

    # Get primary SKU price (lowest)
    purchase_price = 0.0
    if record.skus:
        prices = [s.price_cny for s in record.skus if s.price_cny]
        purchase_price = min(prices) if prices else 0.0

    inp = CostInput(
        purchase_price_cny=purchase_price,
        quantity=10,
        weight_kg=record.weight_kg or 0.5,
        length_cm=record.length_cm or 30.0,
        width_cm=record.width_cm or 20.0,
        height_cm=record.height_cm or 5.0,
    )

    calculator = CostCalculator()
    calc_result = calculator.calculate(inp)
    cost_dict = calculator.to_dict(inp, calc_result)

    record.cost_data = cost_dict
    record.status = "cost_calculated"
    await db.flush()

    flash(request, "试算完成！", "success")
    return {"ok": True, "cost": cost_dict}


# ── API: Update translation manually ───────────────────────────────


@router.post("/api/{record_id}/update")
async def sourcing_update(
    request: Request,
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Update editable fields (title_ru, description_ru, etc.)."""
    result = await db.execute(
        select(SourcingRecord).where(SourcingRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return {"ok": False, "error": "Record not found"}

    body = await request.json()

    for field in (
        "title_ru", "description_ru", "material_ru",
        "package_type_ru", "title_cn", "weight_kg",
        "length_cm", "width_cm", "height_cm",
    ):
        if field in body:
            setattr(record, field, body[field])

    # Update SKUs if provided
    if "skus" in body:
        for i, sku_data in enumerate(body["skus"]):
            if i < len(record.skus or []):
                if "spec_ru" in sku_data:
                    record.skus[i].spec_ru = sku_data["spec_ru"]
                if "spec_cn" in sku_data:
                    record.skus[i].spec_cn = sku_data["spec_cn"]

    flash(request, "已更新。", "success")
    return {"ok": True}


# ── API: Download images ────────────────────────────────────────────


@router.post("/api/{record_id}/download-images")
async def sourcing_download_images(
    request: Request,
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download 1688 images to local storage."""
    result = await db.execute(
        select(SourcingRecord).where(SourcingRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return {"ok": False, "error": "Record not found"}

    if not record.images_1688_urls:
        flash(request, "没有可下载的图片", "warning")
        return {"ok": False, "error": "No image URLs"}

    handler = ImageHandler()
    try:
        dl_result = await handler.download_images(
            record_id=str(record_id),
            image_urls=record.images_1688_urls,
            detail_urls=record.detail_images_1688_urls,
        )
        record.images_local_paths = (
            dl_result["main_paths"] + dl_result["detail_paths"]
        )
        record.images_ozon_urls = (
            dl_result["main_urls"] + dl_result["detail_urls"]
        )
        await db.flush()

        flash(
            request,
            f"已下载 {len(dl_result['main_paths'])} 张主图 + "
            f"{len(dl_result['detail_paths'])} 张详情图",
            "success",
        )
        return {"ok": True, "downloaded": len(record.images_local_paths)}
    except Exception as e:
        logger.exception("Image download failed for %s", record_id)
        flash(request, f"图片下载失败: {e}", "error")
        return {"ok": False, "error": str(e)}


# ── API: Push to OZON ───────────────────────────────────────────────


@router.post("/api/{record_id}/push-to-ozon")
async def sourcing_push_to_ozon(
    request: Request,
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    client: OzonClient | None = Depends(get_ozon_client),
):
    """Push the sourcing record to OZON as a product listing."""
    if not client:
        flash(request, "OZON API 未配置，请在 .env 中设置 OZON_CLIENT_ID 和 OZON_API_KEY", "error")
        return {"ok": False, "error": "Ozon client not configured"}

    result = await db.execute(
        select(SourcingRecord).where(SourcingRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return {"ok": False, "error": "Record not found"}

    if not record.title_ru:
        flash(request, "请先翻译为俄文再上架", "warning")
        return {"ok": False, "error": "Translation required"}

    # Build import items
    builder = ProductBuilder()
    items = builder.build_import_items(record)

    if not items:
        flash(request, "没有可上架的商品数据", "warning")
        return {"ok": False, "error": "No items to push"}

    try:
        from app.integrations.endpoints.products import ProductEndpoints
        endpoints = ProductEndpoints(client)
        results = await endpoints.import_products(items)

        # Check for errors
        errors = []
        offer_ids = []
        for r in results:
            if r.get("errors"):
                errors.append(r)
            else:
                offer_ids.append(r.get("offer_id", ""))

        if errors:
            record.push_errors = {"errors": errors}
            record.status = "push_failed"
            flash(
                request,
                f"部分上架失败: {len(errors)}/{len(results)} 个有错误",
                "error",
            )
        else:
            record.ozon_offer_id = ",".join(offer_ids) if len(offer_ids) > 1 else (offer_ids[0] if offer_ids else "")
            if results and results[0].get("product_id"):
                record.ozon_product_id = results[0]["product_id"]
            record.status = "pushed"
            record.pushed_at = datetime.now()
            flash(request, f"✅ 已成功上架 {len(results)} 个商品到 OZON!", "success")

        await db.flush()
        return {
            "ok": len(errors) == 0,
            "total": len(results),
            "success_count": len(offer_ids),
            "error_count": len(errors),
            "offer_ids": offer_ids,
            "errors": [e.get("errors") for e in errors] if errors else [],
        }

    except OzonAPIError as e:
        logger.exception("Ozon push failed for %s", record_id)
        record.status = "push_failed"
        record.push_errors = {"error": str(e)}
        await db.flush()
        flash(request, f"OZON API 错误: {e}", "error")
        return {"ok": False, "error": str(e)}
