import json
import time
from pathlib import Path
from typing import List

from ..models import Signal


class ActionGuard:
    def __init__(self, path: str, cooldown_sec: int, override_confidence: float) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cooldown_sec = max(1, cooldown_sec)
        self.override_confidence = override_confidence

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def apply(self, signals: List[Signal]) -> List[Signal]:
        state = self._load()
        now = int(time.time())

        for s in signals:
            prev = state.get(s.symbol)
            if prev:
                last_action = prev.get("action")
                last_ts = prev.get("ts", 0)
                if last_action and s.action != last_action:
                    if now - last_ts < self.cooldown_sec and s.confidence < self.override_confidence:
                        s.action = last_action
                        s.reason = f"{s.reason}（一致性保护：保留上次动作）"
            state[s.symbol] = {"action": s.action, "ts": now}

        self._save(state)
        return signals
