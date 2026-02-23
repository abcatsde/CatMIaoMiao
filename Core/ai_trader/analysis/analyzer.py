import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from logging.handlers import TimedRotatingFileHandler

from ..models import MarketSnapshot, AccountInfo, Position, Signal, Order


class Analyzer:
    def __init__(self, log_path: str, next_check_seconds: int) -> None:
        self.logger = logging.getLogger("Analyzer")
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.next_check_seconds = max(5, next_check_seconds)
        self.file_logger = self._init_file_logger()

    def _init_file_logger(self) -> logging.Logger:
        logger = logging.getLogger("AnalyzerFile")
        if logger.handlers:
            return logger

        handler = TimedRotatingFileHandler(
            self.log_path,
            when="h",
            interval=6,
            backupCount=30,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        return logger

    def _format_pct(self, value: Optional[float]) -> str:
        if value is None:
            return "未设定"
        return f"{value * 100:.2f}%"

    def _risk_level(self, confidence: float) -> str:
        if confidence >= 0.7:
            return "中"
        if confidence >= 0.4:
            return "中高"
        return "高"

    def _calc_return(self, last_price: float, signal: Signal) -> Optional[float]:
        if last_price <= 0:
            return None
        if signal.take_profit is None:
            return None
        if signal.action == "buy":
            return (signal.take_profit - last_price) / last_price
        if signal.action == "sell":
            return (last_price - signal.take_profit) / last_price
        return None

    def _build_plan(
        self,
        market: List[MarketSnapshot],
        signals: List[Signal],
        positions: List[Position],
    ) -> str:
        market_map = {m.symbol: m for m in market}
        signal_map = {s.symbol: s for s in signals}
        pos_map = {p.symbol: p for p in positions}

        lines = []
        lines.append("规划摘要：")
        for symbol, snap in market_map.items():
            signal = signal_map.get(symbol)
            if not signal:
                continue
            exp_return = self._calc_return(snap.last_price, signal)
            timeframes = signal.timeframes or []
            tf_text = "、".join(timeframes) if timeframes else "未说明"
            lines.append(f"- 标的：{symbol}")
            lines.append(f"  查看级别：{tf_text}")
            pos = pos_map.get(symbol)
            if pos:
                if pos.side == "short":
                    pnl = (pos.entry_price - snap.last_price)
                    pnl_pct = (pos.entry_price - snap.last_price) / pos.entry_price if pos.entry_price else 0
                else:
                    pnl = (snap.last_price - pos.entry_price)
                    pnl_pct = (snap.last_price - pos.entry_price) / pos.entry_price if pos.entry_price else 0

                mgn_mode = pos.mgn_mode or "未知"
                margin = f"{pos.margin:.2f}" if pos.margin is not None else "未知"
                mmr = f"{pos.mmr * 100:.2f}%" if pos.mmr is not None else "未知"

                if signal.stop_loss is not None or signal.take_profit is not None:
                    attitude = "设置止损/设置止盈"
                else:
                    attitude = "继续持有" if signal.action == "hold" else f"执行{signal.action}"

                lines.append(
                    f"  当前持仓（{symbol}）：开仓成本/当前价格 {pos.entry_price:.2f}/{snap.last_price:.2f}"
                    f" +{pnl:.2f} (+{pnl_pct * 100:.2f}%)，{mgn_mode}，保证金：{margin}，维持保证金率:{mmr}，态度：{attitude}"
                )
            lines.append("  走势评估：基于所查看级别的K线与当前价格快照综合判断")
            lines.append(f"  预测：短期偏{signal.action}（置信度 {signal.confidence:.2f}）")
            lines.append(f"  投资风险：{self._risk_level(signal.confidence)}")
            lines.append(f"  预期回报率：{self._format_pct(exp_return)}")
            lines.append(f"  我的想法：{signal.reason}")
            if signal.protect_intent:
                lines.append(f"  保护意向：{signal.protect_intent}")

        lines.append(f"我会在 {self.next_check_seconds} 秒后重新查看走势。")
        return "\n".join(lines)

    def analyze(
        self,
        market: List[MarketSnapshot],
        account: AccountInfo,
        positions: List[Position],
        signals: List[Signal],
        orders: List[Order],
        plan=None,
    ) -> Dict[str, Any]:
        plan_text = self._build_plan(market, signals, positions)
        summary = {
            "symbols": [m.symbol for m in market],
            "equity": account.equity,
            "available": account.available,
            "positions": [p.__dict__ for p in positions],
            "signals": [s.__dict__ for s in signals],
            "orders": [o.__dict__ for o in orders],
            "plan_selection": plan.__dict__ if plan else None,
            "plan": plan_text,
        }
        return summary

    def report(self, summary: Dict[str, Any]) -> None:
        self.logger.info("Analysis Plan:\n%s", summary.get("plan", ""))
        ts = datetime.now().isoformat(timespec="seconds")
        plan_text = summary.get("plan", "")
        self.file_logger.info("[%s]\n%s\n", ts, plan_text)
        self.file_logger.info("%s", json.dumps(summary, ensure_ascii=False))
