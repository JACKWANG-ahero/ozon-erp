"""Profit calculation service — ported from rets-calculator mini program.

Computes: purchase cost + domestic shipping + international freight
          + OZON commission → suggested price & profit margin.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────


@dataclass
class CostInput:
    """Inputs for profit calculation."""

    purchase_price_cny: float  # 采购单价 (¥)
    quantity: int = 10  # 预期采购数量
    weight_kg: float = 0.5  # 单件重量
    length_cm: float = 30.0
    width_cm: float = 20.0
    height_cm: float = 5.0


@dataclass
class RateConfig:
    """Configurable rates for cost calculation."""

    # Domestic shipping: 1688 → Guangzhou warehouse (flat rate per order)
    domestic_shipping_cny: float = 10.0

    # International freight: ¥/kg (varies by logistics channel)
    freight_per_kg_cny: float = 65.0

    # Volume weight divisor (cm³/kg), standard air freight = 6000
    volume_weight_divisor: float = 6000.0

    # OZON commission rate (varies by category, 刺绣套装 ~10%)
    ozon_commission_rate: float = 0.10

    # Target profit margin (% of total cost)
    target_margin: float = 0.30

    # CNY → RUB exchange rate (approximate)
    cny_to_rub: float = 12.5


@dataclass
class CostResult:
    """Calculated cost breakdown."""

    purchase_total_cny: float
    domestic_shipping_cny: float
    actual_weight_kg: float
    volume_weight_kg: float
    chargeable_weight_kg: float
    freight_total_cny: float
    total_cost_cny: float
    cost_per_unit_cny: float
    suggested_price_rub: float
    ozon_commission_rub: float
    profit_per_unit_rub: float
    profit_margin_pct: float


# ── Calculator ───────────────────────────────────────────────────────


class CostCalculator:
    """Compute profit estimates for OZON product listings."""

    def __init__(self, rates: RateConfig | None = None) -> None:
        self.rates = rates or RateConfig()

    def calculate(self, inp: CostInput) -> CostResult:
        """Run full cost calculation.

        Args:
            inp: CostInput with product data

        Returns:
            CostResult with full breakdown
        """
        # 1. Purchase cost
        purchase_total = inp.purchase_price_cny * inp.quantity

        # 2. Domestic shipping
        domestic = self.rates.domestic_shipping_cny

        # 3. International freight (chargeable weight)
        actual_weight = inp.weight_kg
        volume_weight = (
            inp.length_cm * inp.width_cm * inp.height_cm
        ) / self.rates.volume_weight_divisor
        chargeable_weight = max(actual_weight, volume_weight)
        freight_total = chargeable_weight * self.rates.freight_per_kg_cny

        # 4. Total cost
        total_cost = purchase_total + domestic + freight_total
        cost_per_unit = total_cost / inp.quantity

        # 5. Suggested price in RUB
        # cost_per_unit_cny * (1 + target_margin) * cny_to_rub
        suggested_price_rub = (
            cost_per_unit * (1 + self.rates.target_margin) * self.rates.cny_to_rub
        )

        # 6. OZON commission (in RUB)
        commission_rub = suggested_price_rub * self.rates.ozon_commission_rate

        # 7. Profit
        revenue_after_commission_cny = (
            suggested_price_rub - commission_rub
        ) / self.rates.cny_to_rub
        profit_per_unit_cny = revenue_after_commission_cny - cost_per_unit
        profit_per_unit_rub = profit_per_unit_cny * self.rates.cny_to_rub
        profit_margin = (
            profit_per_unit_cny / cost_per_unit
        ) * 100 if cost_per_unit > 0 else 0.0

        return CostResult(
            purchase_total_cny=round(purchase_total, 2),
            domestic_shipping_cny=round(domestic, 2),
            actual_weight_kg=round(actual_weight, 3),
            volume_weight_kg=round(volume_weight, 3),
            chargeable_weight_kg=round(chargeable_weight, 3),
            freight_total_cny=round(freight_total, 2),
            total_cost_cny=round(total_cost, 2),
            cost_per_unit_cny=round(cost_per_unit, 2),
            suggested_price_rub=round(suggested_price_rub, 0),
            ozon_commission_rub=round(commission_rub, 0),
            profit_per_unit_rub=round(profit_per_unit_rub, 2),
            profit_margin_pct=round(profit_margin, 1),
        )

    def to_dict(self, inp: CostInput, result: CostResult) -> dict:
        """Serialize for JSON/DB storage."""
        return {
            "input": {
                "purchase_price_cny": inp.purchase_price_cny,
                "quantity": inp.quantity,
                "weight_kg": inp.weight_kg,
                "size_cm": f"{inp.length_cm}×{inp.width_cm}×{inp.height_cm}",
            },
            "rates": {
                "domestic_shipping_cny": self.rates.domestic_shipping_cny,
                "freight_per_kg_cny": self.rates.freight_per_kg_cny,
                "ozon_commission_rate": self.rates.ozon_commission_rate,
                "target_margin": self.rates.target_margin,
                "cny_to_rub": self.rates.cny_to_rub,
            },
            "result": {
                "purchase_total_cny": result.purchase_total_cny,
                "domestic_shipping_cny": result.domestic_shipping_cny,
                "actual_weight_kg": result.actual_weight_kg,
                "volume_weight_kg": result.volume_weight_kg,
                "chargeable_weight_kg": result.chargeable_weight_kg,
                "freight_total_cny": result.freight_total_cny,
                "total_cost_cny": result.total_cost_cny,
                "cost_per_unit_cny": result.cost_per_unit_cny,
                "suggested_price_rub": result.suggested_price_rub,
                "ozon_commission_rub": result.ozon_commission_rub,
                "profit_per_unit_rub": result.profit_per_unit_rub,
                "profit_margin_pct": result.profit_margin_pct,
            },
        }
