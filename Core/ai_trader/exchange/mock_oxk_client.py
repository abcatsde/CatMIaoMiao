import logging
from typing import List
from datetime import datetime

from ..models import AccountInfo, Position, MarketSnapshot, Order, Instrument, Candle


class MockOKXClient:
    def __init__(self) -> None:
        self.logger = logging.getLogger("MockOXKClient")

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(balance=10000.0, equity=10050.0, available=9200.0)

    def get_positions(self) -> List[Position]:
        return []

    def get_instruments(self, inst_types: List[str], limit: int) -> List[Instrument]:
        return [
            Instrument(
                inst_id="BTC-USDT",
                inst_type="SPOT",
                inst_family="BTC-USDT",
                base_ccy="BTC",
                quote_ccy="USDT",
                tick_sz="0.1",
                lot_sz="0.0001",
            )
        ][:limit]

    def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        now = datetime.utcnow().isoformat()
        return MarketSnapshot(symbol=symbol, last_price=100.0, bid=99.9, ask=100.1, timestamp=now)

    def get_candles(self, symbol: str, bar: str, limit: int) -> List[Candle]:
        now = int(datetime.utcnow().timestamp() * 1000)
        candles = []
        price = 100.0
        for i in range(limit):
            ts = now - i * 60_000
            candles.append(Candle(ts=ts, o=price, h=price + 1, l=price - 1, c=price, vol=1.0))
        return candles

    def place_order(self, order: Order) -> dict:
        self.logger.info("[PAPER] Placing order: %s", order)
        return {"status": "paper_filled", "order": order.__dict__}

    def cancel_order(self, order_id: str) -> dict:
        return {"status": "paper_cancelled", "order_id": order_id}

    def get_open_orders(self) -> List[dict]:
        return []
