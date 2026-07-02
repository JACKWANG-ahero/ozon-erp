"""RETS (俄通收) cross-border logistics channels — China → RU/KZ/BY.

Pricing formula: fee = rate_per_kg × weight_kg + per_ticket_fee
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ShippingChannel(Base):
    """A RETS logistics channel from China to RU/KZ/BY."""

    __tablename__ = "shipping_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_category: Mapped[str] = mapped_column(String(200), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(200), nullable=False)
    destination: Mapped[str] = mapped_column(String(10), default="RU")
    speed: Mapped[str] = mapped_column(String(20), default="标准")  # 特快/标准/经济
    delivery_type: Mapped[str] = mapped_column(String(50), default="到点/到门")
    prep_time: Mapped[str] = mapped_column(String(50), default="5天以下")
    transit_time: Mapped[str] = mapped_column(String(50), default="10-15天")

    # Pricing: fee = rate_per_kg × kg + per_ticket_fee
    rate_per_kg: Mapped[float] = mapped_column(Float, default=0)     # CNY/kg
    per_ticket_fee: Mapped[float] = mapped_column(Float, default=0)   # CNY

    # Constraints
    battery_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    min_weight_kg: Mapped[float] = mapped_column(Float, default=0.001)
    max_weight_kg: Mapped[float] = mapped_column(Float, default=30)
    min_value_rub: Mapped[float] = mapped_column(Float, default=0)
    max_value_rub: Mapped[float] = mapped_column(Float, default=999999)
    max_total_dim_cm: Mapped[float] = mapped_column(Float, default=150)
    max_side_cm: Mapped[float] = mapped_column(Float, default=60)
    max_compensation_rub: Mapped[float] = mapped_column(Float, default=5000)

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def calculate(self, weight_kg: float) -> float:
        return round(self.rate_per_kg * weight_kg + self.per_ticket_fee, 2)

    def is_valid(self, weight_kg: float, cargo_value_rub: float = 0) -> bool:
        return (
            self.min_weight_kg <= weight_kg <= self.max_weight_kg
            and self.min_value_rub <= cargo_value_rub <= self.max_value_rub
        )

    def __repr__(self) -> str:
        return f"<Channel {self.channel_name} {self.destination}>"


# ── RETS full channel data (48 entries) ─────────────────────────

RETS_CHANNELS: list[dict] = [
    # ═══ 俄罗斯 — Extra Small ═══
    {"product_category":"Extra Small","channel_name":"特快超级轻小件","destination":"RU","speed":"特快","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"4-9天","rate_per_kg":46.8,"per_ticket_fee":3.12,"battery_allowed":False,"min_weight_kg":0.001,"max_weight_kg":0.5,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":90,"max_side_cm":60,"max_compensation_rub":1500,"note":"适合3C/小饰品"},
    {"product_category":"Extra Small","channel_name":"标准超级轻小件","destination":"RU","speed":"标准","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":36.4,"per_ticket_fee":3.12,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":0.5,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":90,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"Extra Small","channel_name":"经济超级轻小件","destination":"RU","speed":"经济","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":26.0,"per_ticket_fee":3.12,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":0.5,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":90,"max_side_cm":60,"max_compensation_rub":1500},
    # ═══ 俄罗斯 — Small ═══
    {"product_category":"Small","channel_name":"特快轻小件","destination":"RU","speed":"特快","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"4-9天","rate_per_kg":46.8,"per_ticket_fee":16.64,"battery_allowed":False,"min_weight_kg":0.001,"max_weight_kg":2.0,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":7000},
    {"product_category":"Small","channel_name":"标准轻小件","destination":"RU","speed":"标准","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":36.4,"per_ticket_fee":16.64,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":2.0,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":7000},
    {"product_category":"Small","channel_name":"经济轻小件","destination":"RU","speed":"经济","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":26.0,"per_ticket_fee":16.64,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":2.0,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":7000},
    # ═══ 俄罗斯 — Budget ═══
    {"product_category":"Budget","channel_name":"标准低客单轻小件","destination":"RU","speed":"标准","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":26.0,"per_ticket_fee":23.92,"battery_allowed":True,"min_weight_kg":0.5,"max_weight_kg":30,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"Budget","channel_name":"经济低客单轻小件","destination":"RU","speed":"经济","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":17.68,"per_ticket_fee":23.92,"battery_allowed":True,"min_weight_kg":0.5,"max_weight_kg":30,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":1500},
    # ═══ 俄罗斯 — Premium Small ═══
    {"product_category":"Premium Small","channel_name":"特快高客单轻小件","destination":"RU","speed":"特快","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"4-9天","rate_per_kg":46.8,"per_ticket_fee":22.88,"battery_allowed":False,"min_weight_kg":0.001,"max_weight_kg":5.0,"min_value_rub":7001,"max_value_rub":250000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":250000},
    {"product_category":"Premium Small","channel_name":"标准高客单轻小件","destination":"RU","speed":"标准","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":36.4,"per_ticket_fee":22.88,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":5.0,"min_value_rub":7001,"max_value_rub":250000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":250000},
    {"product_category":"Premium Small","channel_name":"经济高客单轻小件","destination":"RU","speed":"经济","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":26.0,"per_ticket_fee":22.88,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":5.0,"min_value_rub":7001,"max_value_rub":250000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":250000},
    # ═══ 俄罗斯 — Big ═══
    {"product_category":"Big","channel_name":"标准大件","destination":"RU","speed":"标准","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":26.0,"per_ticket_fee":37.44,"battery_allowed":True,"min_weight_kg":2.0,"max_weight_kg":30,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":7700},
    # ═══ 俄罗斯 — Premium Big ═══
    {"product_category":"Premium Big","channel_name":"经济高客单大件","destination":"RU","speed":"经济","delivery_type":"到点/到门","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":23.92,"per_ticket_fee":64.48,"battery_allowed":True,"min_weight_kg":5.0,"max_weight_kg":30,"min_value_rub":7001,"max_value_rub":250000,"max_total_dim_cm":310,"max_side_cm":150,"max_compensation_rub":250000},
    # ═══ 白俄罗斯 ═══
    {"product_category":"Belarus Extra Small","channel_name":"白俄标准超级轻小件","destination":"BY","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":36.4,"per_ticket_fee":3.12,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":0.5,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":90,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"Belarus Extra Small","channel_name":"白俄经济超级轻小件","destination":"BY","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"25-30天","rate_per_kg":26.0,"per_ticket_fee":3.12,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":0.5,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":90,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"Belarus Budget","channel_name":"白俄标准低客单小件","destination":"BY","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":26.0,"per_ticket_fee":23.92,"battery_allowed":True,"min_weight_kg":0.5,"max_weight_kg":35,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"Belarus Budget","channel_name":"白俄经济低客单小件","destination":"BY","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"25-30天","rate_per_kg":17.68,"per_ticket_fee":23.92,"battery_allowed":True,"min_weight_kg":0.5,"max_weight_kg":35,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"Belarus Small","channel_name":"白俄标准轻小件","destination":"BY","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":36.4,"per_ticket_fee":16.64,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":2.0,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":7000},
    {"product_category":"Belarus Small","channel_name":"白俄经济轻小件","destination":"BY","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"25-30天","rate_per_kg":26.0,"per_ticket_fee":16.64,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":2.0,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":7000},
    {"product_category":"Belarus Big","channel_name":"白俄标准大件","destination":"BY","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":26.0,"per_ticket_fee":37.44,"battery_allowed":True,"min_weight_kg":2.0,"max_weight_kg":35,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":7000},
    {"product_category":"Belarus Big","channel_name":"白俄经济大件","destination":"BY","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"25-30天","rate_per_kg":17.68,"per_ticket_fee":37.44,"battery_allowed":True,"min_weight_kg":2.0,"max_weight_kg":35,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":7000},
    {"product_category":"Belarus Premium Small","channel_name":"白俄标准高客单小件","destination":"BY","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":36.4,"per_ticket_fee":22.88,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":5.0,"min_value_rub":7001,"max_value_rub":500000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":500000},
    {"product_category":"Belarus Premium Small","channel_name":"白俄经济高客单小件","destination":"BY","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"25-30天","rate_per_kg":26.0,"per_ticket_fee":22.88,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":5.0,"min_value_rub":7001,"max_value_rub":500000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":500000},
    {"product_category":"Belarus Premium Big","channel_name":"白俄标准高客单大件","destination":"BY","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"15-20天","rate_per_kg":29.12,"per_ticket_fee":64.48,"battery_allowed":True,"min_weight_kg":5.0,"max_weight_kg":35,"min_value_rub":7001,"max_value_rub":500000,"max_total_dim_cm":310,"max_side_cm":150,"max_compensation_rub":500000},
    {"product_category":"Belarus Premium Big","channel_name":"白俄经济高客单大件","destination":"BY","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"25-30天","rate_per_kg":23.92,"per_ticket_fee":64.48,"battery_allowed":True,"min_weight_kg":5.0,"max_weight_kg":35,"min_value_rub":7001,"max_value_rub":500000,"max_total_dim_cm":310,"max_side_cm":150,"max_compensation_rub":500000},
    # ═══ 哈萨克斯坦 ═══
    {"product_category":"KZ Extra Small","channel_name":"哈国标准超级轻小件","destination":"KZ","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":36.4,"per_ticket_fee":3.12,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":0.5,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":90,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"KZ Extra Small","channel_name":"哈国经济超级轻小件","destination":"KZ","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"20-25天","rate_per_kg":26.0,"per_ticket_fee":3.12,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":0.5,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":90,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"KZ Budget","channel_name":"哈国标准低客单小件","destination":"KZ","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":26.0,"per_ticket_fee":23.92,"battery_allowed":True,"min_weight_kg":0.5,"max_weight_kg":35,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"KZ Budget","channel_name":"哈国经济低客单小件","destination":"KZ","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"20-25天","rate_per_kg":17.68,"per_ticket_fee":23.92,"battery_allowed":True,"min_weight_kg":0.5,"max_weight_kg":35,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":1500},
    {"product_category":"KZ Small","channel_name":"哈国标准轻小件","destination":"KZ","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":36.4,"per_ticket_fee":16.64,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":2.0,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":7000},
    {"product_category":"KZ Small","channel_name":"哈国经济轻小件","destination":"KZ","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"20-25天","rate_per_kg":26.0,"per_ticket_fee":16.64,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":2.0,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":150,"max_side_cm":60,"max_compensation_rub":7000},
    {"product_category":"KZ Big","channel_name":"哈国标准大件","destination":"KZ","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":26.0,"per_ticket_fee":37.44,"battery_allowed":True,"min_weight_kg":2.0,"max_weight_kg":35,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":7000},
    {"product_category":"KZ Big","channel_name":"哈国经济大件","destination":"KZ","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"20-25天","rate_per_kg":17.68,"per_ticket_fee":37.44,"battery_allowed":True,"min_weight_kg":2.0,"max_weight_kg":35,"min_value_rub":1501,"max_value_rub":7000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":7000},
    {"product_category":"KZ Premium Small","channel_name":"哈国标准高客单小件","destination":"KZ","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":36.4,"per_ticket_fee":22.88,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":5.0,"min_value_rub":7001,"max_value_rub":500000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":500000},
    {"product_category":"KZ Premium Small","channel_name":"哈国经济高客单小件","destination":"KZ","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"20-25天","rate_per_kg":26.0,"per_ticket_fee":22.88,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":5.0,"min_value_rub":7001,"max_value_rub":500000,"max_total_dim_cm":250,"max_side_cm":150,"max_compensation_rub":500000},
    {"product_category":"KZ Premium Big","channel_name":"哈国标准高客单大件","destination":"KZ","speed":"标准","delivery_type":"到点","prep_time":"5天以下","transit_time":"10-15天","rate_per_kg":29.12,"per_ticket_fee":64.48,"battery_allowed":True,"min_weight_kg":5.0,"max_weight_kg":35,"min_value_rub":7001,"max_value_rub":500000,"max_total_dim_cm":310,"max_side_cm":150,"max_compensation_rub":500000},
    {"product_category":"KZ Premium Big","channel_name":"哈国经济高客单大件","destination":"KZ","speed":"经济","delivery_type":"到点","prep_time":"5天以下","transit_time":"20-25天","rate_per_kg":23.92,"per_ticket_fee":64.48,"battery_allowed":True,"min_weight_kg":5.0,"max_weight_kg":35,"min_value_rub":7001,"max_value_rub":500000,"max_total_dim_cm":310,"max_side_cm":150,"max_compensation_rub":500000},
    # ═══ 俄通收 WH ═══
    {"product_category":"WH","channel_name":"俄通收 WH","destination":"RU","speed":"经济","delivery_type":"到取货点","prep_time":"5天以下","transit_time":"20-35天","rate_per_kg":26.0,"per_ticket_fee":1.90,"battery_allowed":True,"min_weight_kg":0.001,"max_weight_kg":0.5,"min_value_rub":1,"max_value_rub":1500,"max_total_dim_cm":90,"max_side_cm":60,"max_compensation_rub":1500,"note":"不含揽收，带电/液体/危险品无法发货"},
]
