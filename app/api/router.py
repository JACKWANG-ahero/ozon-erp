"""Aggregate router — includes all domain sub-routers."""

from fastapi import APIRouter

from app.api.products import router as products_router
from app.api.orders import router as orders_router
from app.api.inventory import router as inventory_router
from app.api.pricing import router as pricing_router
from app.api.finance import router as finance_router
from app.api.categories import router as categories_router
from app.api.returns import router as returns_router
from app.api.dashboard import router as dashboard_router
from app.api.sync import router as sync_router
from app.api.sourcing import router as sourcing_router

router = APIRouter()

router.include_router(dashboard_router)     # /
router.include_router(products_router)      # /products
router.include_router(categories_router)    # /categories
router.include_router(orders_router)        # /orders
router.include_router(inventory_router)     # /inventory
router.include_router(pricing_router)       # /pricing
router.include_router(finance_router)       # /finance
router.include_router(returns_router)       # /returns
router.include_router(sync_router)          # /sync
router.include_router(sourcing_router)      # /sourcing
