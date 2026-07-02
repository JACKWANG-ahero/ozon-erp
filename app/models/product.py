"""Product, ProductAttribute, and ProductImage models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import JSON as JSONB  # JSONB alias for compatibility
from sqlalchemy import Uuid as PG_UUID  # Uuid alias for compatibility
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.stock import Stock
    from app.models.price import Price
    from app.models.order import OrderItem
    from app.models.return_model import Return


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ozon_product_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    offer_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Names & descriptions
    name_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    name_zh: Mapped[str | None] = mapped_column(String(500))
    description_ru: Mapped[str | None] = mapped_column(Text)
    description_zh: Mapped[str | None] = mapped_column(Text)

    # Categorization
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id")
    )
    brand: Mapped[str | None] = mapped_column(String(255))
    barcode: Mapped[str | None] = mapped_column(String(100))

    # Dimensions (mm, g)
    height: Mapped[float | None] = mapped_column(Numeric(10, 3))
    depth: Mapped[float | None] = mapped_column(Numeric(10, 3))
    width: Mapped[float | None] = mapped_column(Numeric(10, 3))
    weight: Mapped[float | None] = mapped_column(Numeric(10, 3))

    primary_image_url: Mapped[str | None] = mapped_column(String(2000))

    # Status tracking
    status: Mapped[str] = mapped_column(String(30), default="draft")
    # draft | pending_import | imported | archived | import_error
    sync_status: Mapped[str] = mapped_column(String(30), default="local_only")
    # local_only | synced | modified | conflict
    ozon_visibility: Mapped[str | None] = mapped_column(String(30))
    # VISIBLE | INVISIBLE | ARCHIVED

    import_errors: Mapped[dict | None] = mapped_column(JSONB)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="products")
    attributes: Mapped[List["ProductAttribute"]] = relationship(
        "ProductAttribute", back_populates="product", cascade="all, delete-orphan"
    )
    images: Mapped[List["ProductImage"]] = relationship(
        "ProductImage", back_populates="product", cascade="all, delete-orphan"
    )
    stocks: Mapped[List["Stock"]] = relationship("Stock", back_populates="product")
    price: Mapped[Optional["Price"]] = relationship("Price", back_populates="product", uselist=False)
    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="product")
    returns: Mapped[List["Return"]] = relationship("Return", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product offer_id='{self.offer_id}' name='{self.name_ru}'>"


class ProductAttribute(Base):
    __tablename__ = "product_attributes"
    __table_args__ = (
        UniqueConstraint("product_id", "attribute_id", name="uq_product_attribute"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    attribute_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("category_attributes.id"), nullable=False
    )

    # Flexible value storage
    value_string: Mapped[str | None] = mapped_column(String(5000))
    value_int: Mapped[int | None] = mapped_column(BigInteger)
    value_numeric: Mapped[float | None] = mapped_column(Numeric(19, 4))
    value_json: Mapped[dict | None] = mapped_column(JSONB)
    value_image_url: Mapped[str | None] = mapped_column(String(2000))

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="attributes")

    def __repr__(self) -> str:
        return f"<ProductAttribute product={self.product_id} attr={self.attribute_id}>"


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="images")

    def __repr__(self) -> str:
        return f"<ProductImage url='{self.url[:50]}...'>"
