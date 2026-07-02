"""ORM models package — imports all models for Alembic auto-detection."""

from app.models.base import Base
from app.models.category import Category, CategoryAttribute, AttributeDictionary
from app.models.product import Product, ProductAttribute, ProductImage
from app.models.warehouse import Warehouse
from app.models.stock import Stock
from app.models.price import Price, PriceHistory
from app.models.order import Order, OrderItem, OrderStatusHistory
from app.models.finance import FinanceTransaction
from app.models.return_model import Return
from app.models.chat import Chat, ChatMessage
from app.models.sync_log import SyncLog
from app.models.shipping_channel import ShippingChannel
from app.models.sourcing import SourcingRecord, SourcingSku

__all__ = [
    "Base",
    "Category",
    "CategoryAttribute",
    "AttributeDictionary",
    "Product",
    "ProductAttribute",
    "ProductImage",
    "Warehouse",
    "Stock",
    "Price",
    "PriceHistory",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "FinanceTransaction",
    "Return",
    "Chat",
    "ChatMessage",
    "SyncLog",
    "SourcingRecord",
    "SourcingSku",
]
