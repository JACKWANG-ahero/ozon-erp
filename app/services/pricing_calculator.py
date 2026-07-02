"""RETS pricing calculator — iterative selling price solver.

Core formula:
    selling_price = (purchase_cost_cny + shipping_cny) / (1 - commission_rate - profit_rate)

Where shipping depends on channel, and channel depends on cargo_value (= selling_price * exchange_rate).
Fixed-point iteration (30 max, convergence < 0.005 CNY).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shipping_channel import ShippingChannel, RETS_CHANNELS

logger = logging.getLogger(__name__)

EXCHANGE_RATE_CNY_RUB = 12.5


async def get_channels(db: AsyncSession) -> list[ShippingChannel]:
    """Load all channels, seeding RETS defaults if table is empty."""
    result = await db.execute(select(ShippingChannel).where(ShippingChannel.active == True))
    channels = list(result.scalars().all())
    if not channels:
        for ch in RETS_CHANNELS:
            db.add(ShippingChannel(**ch))
        await db.commit()
        result = await db.execute(select(ShippingChannel).where(ShippingChannel.active == True))
        channels = list(result.scalars().all())
    return channels


def filter_channels(
    channels: list[ShippingChannel],
    destination: str = "RU",
    weight_kg: float = 0,
    cargo_value_rub: float = 0,
    battery_required: bool | None = None,
) -> list[ShippingChannel]:
    """Filter matching channels."""
    out = []
    for c in channels:
        if c.destination != destination:
            continue
        if not c.is_valid(weight_kg, cargo_value_rub):
            continue
        if battery_required is True and not c.battery_allowed:
            continue
        out.append(c)
    return out


async def compute_price(
    db: AsyncSession,
    purchase_cost_cny: float,
    weight_kg: float,
    commission_rate: float = 0.15,
    profit_rate: float = 0.20,
    loss_rate: float = 0.02,
    destination: str = "RU",
    exchange_rate: float = EXCHANGE_RATE_CNY_RUB,
) -> dict[str, Any]:
    """Iteratively solve selling price and return all channel options."""
    channels = await get_channels(db)

    total_rate = commission_rate + profit_rate
    if total_rate >= 1.0:
        return {"error": f"佣金({commission_rate:.0%}) + 利润({profit_rate:.0%}) ≥ 100%"}

    denom = 1 - total_rate
    selling_price = purchase_cost_cny * 1.5
    best_chan: ShippingChannel | None = None
    shipping_cny = 0.0
    converged = False
    iters = 0

    for iteration in range(1, 31):
        cargo_rub = selling_price * exchange_rate
        matched = filter_channels(channels, destination, weight_kg, cargo_rub)

        # Fallback: weight-only match
        if not matched:
            matched = [c for c in channels
                       if c.destination == destination
                       and c.min_weight_kg <= weight_kg <= c.max_weight_kg]

        if not matched:
            selling_price *= 1.1
            continue

        results = [(c, c.calculate(weight_kg)) for c in matched]
        results.sort(key=lambda x: x[1])
        best_chan, shipping_cny = results[0]  # rate_per_kg and per_ticket_fee are CNY
        loss_cny = purchase_cost_cny * loss_rate
        new_price = (purchase_cost_cny + shipping_cny + loss_cny) / denom

        if abs(new_price - selling_price) < 0.005:
            selling_price = new_price
            converged = True
            iters = iteration
            break

        selling_price = new_price
        iters = iteration

    cargo_rub = selling_price * exchange_rate

    # All available channels at final price
    all_matched = filter_channels(channels, destination, weight_kg, cargo_rub)
    if not all_matched:
        all_matched = [c for c in channels
                       if c.destination == destination
                       and c.min_weight_kg <= weight_kg <= c.max_weight_kg]

    channel_options = []
    loss_cny = purchase_cost_cny * loss_rate
    for c in all_matched:
        fee_cny = c.calculate(weight_kg)  # rate_per_kg and per_ticket_fee are CNY
        alt_price = (purchase_cost_cny + fee_cny + loss_cny) / denom
        channel_options.append({
            "id": c.id,
            "name": c.channel_name,
            "category": c.product_category,
            "speed": c.speed,
            "delivery_type": c.delivery_type,
            "transit_time": c.transit_time,
            "rate_per_kg": c.rate_per_kg,
            "per_ticket_fee": c.per_ticket_fee,
            "shipping_fee_cny": round(fee_cny, 2),
            "selling_price_cny": round(alt_price, 2),
            "selling_price_rub": round(alt_price * exchange_rate, 2),
            "commission_cny": round(alt_price * commission_rate, 2),
            "profit_cny": round(alt_price * profit_rate, 2),
            "loss_cny": round(loss_cny, 2),
            "battery_allowed": c.battery_allowed,
            "max_compensation_rub": int(c.max_compensation_rub),
            "note": c.note or "",
        })

    channel_options.sort(key=lambda x: x["selling_price_cny"])

    return {
        "selling_price_cny": round(selling_price, 2),
        "selling_price_rub": round(selling_price * exchange_rate, 2),
        "purchase_cost_cny": purchase_cost_cny,
        "best_channel": best_chan.channel_name if best_chan else "",
        "best_shipping_cny": round(shipping_cny, 2),  # CNY (rate_per_kg * kg + per_ticket_fee)
        "commission_cny": round(selling_price * commission_rate, 2),
        "profit_cny": round(selling_price * profit_rate, 2),
        "loss_reserve_cny": round(purchase_cost_cny * loss_rate, 2),
        "iterations": iters,
        "converged": converged,
        "exchange_rate": exchange_rate,
        "channels": channel_options,
        "verification": {
            "purchase": purchase_cost_cny,
            "shipping": round(shipping_cny, 2),
            "commission": round(selling_price * commission_rate, 2),
            "profit": round(selling_price * profit_rate, 2),
            "loss": round(purchase_cost_cny * loss_rate, 2),
            "sum": round(purchase_cost_cny + shipping_cny + selling_price * (commission_rate + profit_rate) + purchase_cost_cny * loss_rate, 2),
            "price": round(selling_price, 2),
        },
    }
