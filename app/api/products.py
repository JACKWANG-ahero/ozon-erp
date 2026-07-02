"""Product routes — CRUD, import, list, detail."""

import logging
from uuid import UUID

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_ozon_client, templates
from app.integrations.client import OzonClient
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


def _svc(db: AsyncSession, client: OzonClient | None = None) -> ProductService:
    return ProductService(db, client)


@router.get("/")
async def product_list(
    request: Request,
    status: str = Query("draft"),
    category_id: int | None = Query(None),
    search: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db)
    items, total = await svc.list_products(
        status=status, category_id=category_id, search=search,
        offset=offset, limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "products/list.html",
        {
            "page": "products",
            "products": items,
            "total": total,
            "offset": offset,
            "limit": limit,
            "status": status,
            "category_id": category_id,
            "search": search,
        },
    )


@router.get("/new")
async def product_create_form(request: Request):
    return templates.TemplateResponse(
        request,
        "products/form.html",
        {"page": "products", "product": None},
    )


@router.get("/{product_id}/edit")
async def product_edit_form(
    request: Request,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """编辑商品 — 显示预填表单"""
    svc = _svc(db)
    product = await svc.get_by_id(product_id)
    if not product:
        return templates.TemplateResponse(
            request,
            "base.html",
            {"page": "products", "error": "Product not found"},
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "products/form.html",
        {"page": "products", "product": product},
    )


@router.post("/new")
async def product_create(
    request: Request,
    offer_id: str = Form(...),
    name_zh: str = Form(""),
    name_ru: str = Form(...),
    category_id: int = Form(...),
    brand: str = Form(""),
    barcode: str = Form(""),
    price: str = Form("0"),
    old_price: str = Form("0"),
    vat: str = Form("0"),
    currency_code: str = Form("CNY"),
    image_files: list[UploadFile] = File(default_factory=list),
    height: float = Form(None),
    depth: float = Form(None),
    width: float = Form(None),
    weight: float = Form(None),
    description_ru: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    import uuid as uuid_module
    import aiofiles
    from pathlib import Path

    # Save files locally first, then upload to GitHub CDN for Ozon
    upload_dir = Path("app/static/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    local_paths: list[Path] = []

    for i, file in enumerate(image_files):
        if file.filename and file.size and file.size > 0:
            ext = Path(file.filename).suffix or ".jpg"
            safe_name = f"{uuid_module.uuid4().hex}{ext}"
            file_path = upload_dir / safe_name
            content = await file.read()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            local_paths.append(file_path)

    if not local_paths:
        return templates.TemplateResponse(
            request,
            "products/form.html",
            {
                "page": "products",
                "product": None,
                "error": "商品图片为必填项！请至少选择1张主图。",
            },
        )

    # Upload to GitHub CDN (if configured) for Ozon-accessible URLs
    from app.services.image_handler import upload_local_images_to_cdn
    cdn_urls = await upload_local_images_to_cdn([str(p) for p in local_paths])
    image_urls = cdn_urls if cdn_urls else [f"/static/uploads/{p.name}" for p in local_paths]

    if not cdn_urls:
        logger.warning("GitHub CDN not configured — images will not be accessible from Ozon")

    svc = _svc(db)
    await svc.create_product({
        "offer_id": offer_id,
        "name_ru": name_ru,
        "name_zh": name_zh or None,
        "category_id": category_id,
        "brand": brand or None,
        "barcode": barcode or None,
        "description_ru": description_ru or None,
        "height": height,
        "depth": depth,
        "width": width,
        "weight": weight,
        "images": image_urls,
        "price": price,
        "old_price": old_price,
        "vat": vat,
        "currency_code": currency_code,
    })
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/products/", status_code=303)


@router.get("/{product_id}")
async def product_detail(
    request: Request,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db)
    product = await svc.get_by_id(product_id)
    if not product:
        return templates.TemplateResponse(
            request,
            "base.html",
            {"page": "products", "error": "Product not found"},
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "products/detail.html",
        {"page": "products", "product": product},
    )


@router.post("/{product_id}/import")
async def product_import_to_ozon(
    request: Request,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    if not ozon_client:
        product = await _svc(db).get_by_id(product_id)
        return templates.TemplateResponse(
            request,
            "products/detail.html",
            {"page": "products", "product": product,
             "import_result": {"success": 0, "failed": 1,
             "errors": [{"offer_id": "", "errors": [{"message": "Ozon API 未配置，请在 .env 中设置 OZON_CLIENT_ID 和 OZON_API_KEY"}]}]}},
        )

    svc = _svc(db, ozon_client)
    try:
        result = await svc.import_to_ozon([product_id])
    except Exception as e:
        msg = str(e)
        hint = ""
        if "Rate limit" in msg or "429" in msg:
            hint = "（Ozon API 限流，请等待 5-10 分钟后再试。自动同步会在整点自动补推。）"
        result = {
            "success": 0, "failed": 1,
            "errors": [{"offer_id": "", "errors": [{"message": f"API 调用失败：{msg}{hint}"}]}],
        }

    product = await svc.get_by_id(product_id)
    return templates.TemplateResponse(
        request,
        "products/detail.html",
        {
            "page": "products",
            "product": product,
            "import_result": result,
        },
    )


@router.post("/batch/import")
async def product_batch_import(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    """批量推送选中商品到Ozon"""
    if not ozon_client:
        return {"error": "Ozon API not configured"}

    try:
        body = await request.json()
        ids = [UUID(p) for p in body.get("product_ids", [])]
    except (ValueError, TypeError):
        return {"error": "Invalid product_ids"}
    if not ids:
        return {"error": "No products selected"}

    svc = _svc(db, ozon_client)
    try:
        result = await svc.import_to_ozon(ids)
    except Exception as e:
        return {"success": 0, "failed": len(ids), "errors": [str(e)]}
    return result


@router.post("/batch/archive")
async def product_batch_archive(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    """批量归档"""
    try:
        body = await request.json()
        ids = [UUID(p) for p in body.get("product_ids", [])]
    except (ValueError, TypeError):
        return {"error": "Invalid product_ids"}
    if not ids:
        return {"error": "No products selected"}

    svc = _svc(db, ozon_client)
    count = await svc.archive_products(ids)
    return {"success": count, "failed": 0}


@router.post("/batch/delete")
async def product_batch_delete(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    """批量删除"""
    try:
        body = await request.json()
        ids = [UUID(p) for p in body.get("product_ids", [])]
    except (ValueError, TypeError):
        return {"error": "Invalid product_ids"}
    if not ids:
        return {"error": "No products selected"}

    svc = _svc(db, ozon_client)
    count = 0
    for pid in ids:
        if await svc.delete_product(pid):
            count += 1
    return {"success": count, "failed": len(ids) - count}


@router.post("/{product_id}/archive")
async def product_archive(
    request: Request,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    """归档商品（本地+Ozon双端）"""
    svc = _svc(db, ozon_client)
    try:
        result = await svc.archive_products([product_id])
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "products/detail.html",
            {
                "page": "products",
                "product": await svc.get_by_id(product_id),
                "import_result": {"success": 0, "failed": 1,
                "errors": [{"offer_id": "", "errors": [{"message": str(e)}]}]},
            },
        )

    product = await svc.get_by_id(product_id)
    return templates.TemplateResponse(
        request,
        "products/detail.html",
        {
            "page": "products",
            "product": product,
            "archive_result": {"archived": result > 0, "count": result},
        },
    )


@router.post("/{product_id}/delete")
async def product_delete(
    request: Request,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    ozon_client: OzonClient | None = Depends(get_ozon_client),
):
    """软删除商品（移入已删除列表）"""
    from fastapi.responses import RedirectResponse, Response

    svc = _svc(db, ozon_client)
    try:
        await svc.delete_product(product_id)
    except Exception as e:
        product = await svc.get_by_id(product_id)
        return templates.TemplateResponse(
            request,
            "products/detail.html",
            {"page": "products", "product": product,
             "error": f"删除失败：{e}"},
        )
    # HTMX redirect
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": "/products/?status=deleted"})
    return RedirectResponse(url="/products/?status=deleted", status_code=303)


@router.post("/{product_id}/restore")
async def product_restore(
    request: Request,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """恢复已删除商品到草稿状态"""
    from fastapi.responses import RedirectResponse, Response
    svc = _svc(db)
    await svc.restore_product(product_id)
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": "/products/?status=deleted"})
    return RedirectResponse(url="/products/?status=deleted", status_code=303)


@router.post("/api/translate")
async def api_translate(
    text: str = Form(...),
    target: str = Form("ru"),
):
    """翻译中文→俄语（DeepSeek）"""
    from app.services.translation import translate_text
    try:
        result = await translate_text(text, target)
        return {"translated": result}
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/generate-description")
async def api_generate_description(
    title_cn: str = Form(...),
    keywords_cn: str = Form(""),
    category: str = Form(""),
):
    """AI 生成俄语商品描述 + 关键词（DeepSeek）"""
    from app.services.translation import generate_ozon_description
    try:
        result = await generate_ozon_description(title_cn, keywords_cn, category)
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/api/resize-image")
async def api_resize_image(
    file: UploadFile = File(...),
    target_ratio: str = Form("3:4"),
):
    """将上传图片裁剪为指定比例（默认3:4 Ozon要求）"""
    from PIL import Image
    import io, uuid as uuid_module
    from pathlib import Path

    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content))
        # Parse ratio
        w_ratio, h_ratio = map(int, target_ratio.split(":"))
        target_w = img.width
        target_h = int(target_w * h_ratio / w_ratio)

        if target_h > img.height:
            target_h = img.height
            target_w = int(target_h * w_ratio / h_ratio)

        # Center crop
        left = (img.width - target_w) // 2
        top = (img.height - target_h) // 2
        cropped = img.crop((left, top, left + target_w, top + target_h))

        # Save
        upload_dir = Path("app/static/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{uuid_module.uuid4().hex}.jpg"
        out_path = upload_dir / safe_name
        cropped = cropped.convert("RGB")
        cropped.save(out_path, "JPEG", quality=90)

        return {
            "url": f"/static/uploads/{safe_name}",
            "width": target_w,
            "height": target_h,
            "original_width": img.width,
            "original_height": img.height,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/calculate-price")
async def api_calculate_price(
    purchase_cost: float = Query(..., gt=0),
    weight_kg: float = Query(..., gt=0),
    commission_rate: float = Query(0.15, ge=0, lt=1),
    profit_rate: float = Query(0.20, ge=0, lt=1),
    loss_rate: float = Query(0.02, ge=0, lt=1),
    destination: str = Query("RU"),
    db: AsyncSession = Depends(get_db),
):
    """定价计算器 — 根据采购成本+重量+佣金率迭代求解售价"""
    from app.services.pricing_calculator import compute_price
    try:
        result = await compute_price(
            db, purchase_cost, weight_kg,
            commission_rate=commission_rate,
            profit_rate=profit_rate,
            loss_rate=loss_rate,
            destination=destination,
        )
        return result
    except ValueError as e:
        return {"error": str(e)}
