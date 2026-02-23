from typing import List

from ..models import MarketSnapshot


class MarketWatcher:
    def should_rebalance(self, market: List[MarketSnapshot]) -> bool:
        # TODO: 实现更复杂的监测逻辑
        return True
