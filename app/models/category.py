"""Category, CategoryAttribute, and AttributeDictionary models.

Ozon category tree with LTREE-like path storage for hierarchical queries.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.product import Product


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id"), nullable=True
    )
    title_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    title_zh: Mapped[str | None] = mapped_column(String(500))
    path: Mapped[str | None] = mapped_column(String(500))  # "1.23.456"
    level: Mapped[int] = mapped_column(Integer, default=0)
    is_leaf: Mapped[bool] = mapped_column(Boolean, default=False)
    type_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # Ozon product type id
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        "Category", remote_side=[id], back_populates="children"
    )
    children: Mapped[List["Category"]] = relationship(
        "Category", back_populates="parent"
    )
    attributes: Mapped[List["CategoryAttribute"]] = relationship(
        "CategoryAttribute", back_populates="category", cascade="all, delete-orphan"
    )
    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category id={self.id} title='{self.title_ru}'>"


class CategoryAttribute(Base):
    __tablename__ = "category_attributes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("categories.id"), nullable=False
    )
    name_ru: Mapped[str] = mapped_column(String(500), nullable=False)
    name_zh: Mapped[str | None] = mapped_column(String(500))
    type: Mapped[str | None] = mapped_column(String(50))  # string|number|enum|dict|image
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_collection: Mapped[bool] = mapped_column(Boolean, default=False)
    dictionary_id: Mapped[int | None] = mapped_column(BigInteger)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="attributes")
    dictionary_values: Mapped[List["AttributeDictionary"]] = relationship(
        "AttributeDictionary", back_populates="attribute", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CategoryAttribute id={self.id} name='{self.name_ru}'>"


class AttributeDictionary(Base):
    __tablename__ = "attribute_dictionaries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attribute_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("category_attributes.id"), nullable=False
    )
    value_ru: Mapped[str] = mapped_column(String(1000), nullable=False)
    value_zh: Mapped[str | None] = mapped_column(String(1000))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    attribute: Mapped["CategoryAttribute"] = relationship(
        "CategoryAttribute", back_populates="dictionary_values"
    )

    def __repr__(self) -> str:
        return f"<AttributeDictionary id={self.id} value='{self.value_ru}'>"
