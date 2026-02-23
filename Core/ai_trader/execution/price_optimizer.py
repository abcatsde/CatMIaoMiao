from typing import Optional, Tuple

from ..models import Order


class PriceOptimizer:
    def __init__(self, max_spread_pct: float = 0.002) -> None:
        self.max_spread_pct = max_spread_pct

    def optimize(self, order: Order, best_bid: Optional[float], best_ask: Optional[float]) -> Order:
        if best_bid is None or best_ask is None or best_bid <= 0 or best_ask <= 0:
            return order

        spread_pct = (best_ask - best_bid) / best_bid
        if spread_pct > self.max_spread_pct:
            return order

        if order.side == "buy":
            order.order_type = "limit"
            order.price = best_ask
        else:
            order.order_type = "limit"
            order.price = best_bid

        return order
