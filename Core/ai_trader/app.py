import logging
import time
from typing import List

from .config import load_settings
from .logging_config import setup_logging
from .exchange.oxk_client import OKXClient
from .exchange.okx_ws import OKXWebSocket
from .exchange.mock_oxk_client import MockOKXClient
from .llm.llm_client import LLMClient
from .strategy.llm_strategy import LLMStrategy
from .risk.risk_manager import RiskManager
from .risk.stop_manager import StopManager
from .execution.order_executor import OrderExecutor
from .execution.price_optimizer import PriceOptimizer
from .data.trade_journal import TradeJournal
from .data.state_store import StateStore
from .data.order_tracker import OrderTracker
from .data.memory_store import MemoryStore
from .utils.volatility_guard import VolatilityGuard
from .analysis.analyzer import Analyzer
from .utils.action_guard import ActionGuard
from .models import MarketSnapshot


class TraderApp:
    def __init__(self) -> None:
        setup_logging()
        self.logger = logging.getLogger("TraderApp")
        self.settings = load_settings()

        self.ws_client = None
        if self.settings.paper_trading:
            self.exchange = MockOKXClient()
        else:
            if self.settings.use_websocket:
                self.ws_client = OKXWebSocket(
                    public_url=self.settings.okx_ws_public,
                    private_url=self.settings.okx_ws_private,
                    api_key=self.settings.okx_api_key,
                    api_secret=self.settings.okx_api_secret,
                    passphrase=self.settings.okx_api_passphrase,
                )

            self.exchange = OKXClient(
                base_url=self.settings.okx_base_url,
                api_key=self.settings.okx_api_key,
                api_secret=self.settings.okx_api_secret,
                passphrase=self.settings.okx_api_passphrase,
                use_proxy=self.settings.okx_use_proxy,
                proxy_url=self.settings.okx_proxy_url,
                ws_client=self.ws_client,
            )

        self.llm = LLMClient(
            provider=self.settings.llm_provider,
            model=self.settings.llm_model,
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            use_proxy=self.settings.llm_use_proxy,
            proxy_url=self.settings.llm_proxy_url,
            fail_on_error=self.settings.fail_on_llm_error,
            retries=self.settings.llm_retries,
            retry_backoff=self.settings.llm_retry_backoff,
            timeout_sec=self.settings.llm_timeout_sec,
        )
        self.strategy = LLMStrategy(self.llm)
        self.risk = RiskManager(
            max_risk_pct=self.settings.max_risk_pct,
            max_position_pct=self.settings.max_position_pct,
        )
        self.stop_manager = StopManager(
            trailing_stop_pct=self.settings.trailing_stop_pct,
            take_profit_pct=self.settings.take_profit_pct,
            min_profit_to_trail_pct=self.settings.min_profit_to_trail_pct,
            state_store=StateStore(self.settings.state_store_path),
        )
        self.order_tracker = OrderTracker()
        self.vol_guard = VolatilityGuard(
            window=self.settings.vol_window,
            threshold=self.settings.vol_threshold,
        )
        optimizer = PriceOptimizer(self.settings.max_spread_pct) if self.settings.use_bbo else None
        self.executor = OrderExecutor(self.exchange, optimizer=optimizer)
        self.journal = TradeJournal(self.settings.journal_path)
        self.analyzer = Analyzer(self.settings.analysis_log_path, self.settings.poll_interval_sec)
        self.memory = MemoryStore(self.settings.memory_path)
        self.action_guard = None
        if self.settings.action_guard_enabled:
            self.action_guard = ActionGuard(
                path=self.settings.action_guard_path,
                cooldown_sec=self.settings.action_cooldown_sec,
                override_confidence=self.settings.action_override_confidence,
            )

    def _next_interval(self, signals: List[dict]) -> int:
        has_opportunity = False
        for s in signals:
            action = s.get("action")
            confidence = float(s.get("confidence", 0.0))
            if action in {"buy", "sell"} and confidence >= self.settings.opportunity_confidence:
                has_opportunity = True
                break
        if has_opportunity:
            return max(1, self.settings.fast_poll_interval_sec)
        return max(1, self.settings.idle_poll_interval_sec or self.settings.poll_interval_sec)

    def _fetch_market(self, symbols: List[str]) -> List[MarketSnapshot]:
        snapshots = []
        for symbol in symbols:
            snapshots.append(self.exchange.get_market_snapshot(symbol))
        return snapshots

    def _resolve_universe(self) -> List[str]:
        if self.settings.trading_symbols:
            return self.settings.trading_symbols

        instruments = self.exchange.get_instruments(
            inst_types=self.settings.okx_inst_types,
            limit=self.settings.okx_inst_limit,
        )
        return [i.inst_id for i in instruments]

    def run(self) -> None:
        self.logger.info("Trader started. Paper trading=%s", self.settings.paper_trading)

        if self.ws_client:
            universe = self._resolve_universe()
            if universe:
                self.ws_client.start(universe)

        while True:
            account = self.exchange.get_account_info()
            positions = self.exchange.get_positions()
            instruments = self.exchange.get_instruments(
                inst_types=self.settings.okx_inst_types,
                limit=self.settings.okx_inst_limit,
            )

            last_thoughts = self.memory.load()

            plan = self.llm.generate_plan(instruments, last_thoughts)
            if plan and plan.symbols:
                universe = plan.symbols
            else:
                universe = self._resolve_universe()
            if not universe:
                self.logger.warning("No instruments resolved.")
                time.sleep(self.settings.poll_interval_sec)
                continue

            market = self._fetch_market(universe)
            kline_timeframes = plan.timeframes if plan and plan.timeframes else self.settings.kline_timeframes
            candles = {}
            try:
                for symbol in universe:
                    candles[symbol] = {}
                    for tf in kline_timeframes:
                        candles[symbol][tf] = [c.__dict__ for c in self.exchange.get_candles(symbol, tf, self.settings.kline_limit)]
            except Exception as exc:
                self.logger.error("Fetch candles failed: %s", exc, exc_info=True)
                time.sleep(self.settings.poll_interval_sec)
                continue

            if self.ws_client:
                for evt in self.ws_client.consume_order_events():
                    self.journal.write({"type": "order_event", "data": evt})
                    self.order_tracker.update(evt)

            if self.vol_guard.update(market):
                self.journal.write({"type": "circuit_breaker", "data": {"reason": "volatility"}})
                time.sleep(self.settings.poll_interval_sec)
                continue

            signals = self.strategy.generate_signals(market, account, positions, instruments, candles, last_thoughts)

            if self.action_guard:
                signals = self.action_guard.apply(signals)

            # STOP_BY_LLM 模式下，止损止盈由 LLM 自主决定，允许为空

            stop_updates = self.stop_manager.update_stops(
                positions,
                market,
                signals=signals,
                manage_by_llm=self.settings.stop_by_llm,
            )
            for update in stop_updates:
                self.journal.write({"type": "stop_update", "data": update})

            exit_orders = self.stop_manager.check_exits(positions, market)
            exit_exec = self.executor.execute_orders(exit_orders)
            for result in exit_exec:
                self.journal.write({"type": "exit", "data": result})
            orders = self.risk.apply(signals, account, positions, market, instruments)

            next_interval = self._next_interval([s.__dict__ for s in signals])
            self.analyzer.next_check_seconds = next_interval
            summary = self.analyzer.analyze(market, account, positions, signals, orders, plan)
            self.analyzer.report(summary)
            self.memory.save(summary.get("plan", ""))

            executions = self.executor.execute_orders(orders)
            for result in executions:
                self.journal.write({"type": "entry", "data": result})

            time.sleep(next_interval)
