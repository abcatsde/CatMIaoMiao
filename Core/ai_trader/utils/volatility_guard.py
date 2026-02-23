from collections import deque
from typing import Dict, Deque, List

from ..models import MarketSnapshot


class VolatilityGuard:
    def __init__(self, window: int = 20, threshold: float = 0.05) -> None:
        self.window = window
        self.threshold = threshold
        self.history: Dict[str, Deque[float]] = {}

    def update(self, market: List[MarketSnapshot]) -> bool:
        triggered = False
        for snap in market:
            q = self.history.setdefault(snap.symbol, deque(maxlen=self.window))
            q.append(snap.last_price)
            if len(q) >= 2:
                change = abs(q[-1] - q[0]) / max(q[0], 1e-9)
                if change >= self.threshold:
                    triggered = True
        return triggered
