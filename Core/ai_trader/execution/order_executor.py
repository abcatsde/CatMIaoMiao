from typing import List

from ..models import Order
from .price_optimizer import PriceOptimizer


class OrderExecutor:
    def __init__(self, exchange_client, optimizer: PriceOptimizer | None = None) -> None:
        self.exchange = exchange_client
        self.optimizer = optimizer

    def execute_orders(self, orders: List[Order]) -> List[dict]:
        results = []
        for order in orders:
            if self.optimizer and hasattr(self.exchange, "get_best_bid_ask"):
                bbo = self.exchange.get_best_bid_ask(order.symbol)
                if bbo:
                    order = self.optimizer.optimize(order, bbo.get("bid"), bbo.get("ask"))
            results.append(self.exchange.place_order(order))
        return results
