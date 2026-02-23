from dataclasses import dataclass
from typing import List
import json
import logging
import time

import requests

from ..models import Signal, MarketSnapshot, AccountInfo, Position, Instrument, Plan
from .prompts import SYSTEM_PROMPT, USER_PROMPT, PLAN_SYSTEM_PROMPT, PLAN_USER_PROMPT


@dataclass
class LLMClient:
    provider: str
    model: str
    api_key: str
    base_url: str
    use_proxy: bool = True
    proxy_url: str = ""
    fail_on_error: bool = True
    retries: int = 2
    retry_backoff: float = 1.5
    timeout_sec: int = 60

    def _is_supported(self) -> bool:
        provider = (self.provider or "").strip().lower()
        base = (self.base_url or "").lower()
        if provider in {"siliconflow", "openai"}:
            return True
        return False

    def _dummy(self, market: List[MarketSnapshot]) -> List[Signal]:
        signals: List[Signal] = []
        for snap in market:
            signals.append(
                Signal(
                    symbol=snap.symbol,
                    action="hold",
                    confidence=0.1,
                    reason="Dummy strategy: no trade.",
                    stop_loss=None,
                    take_profit=None,
                    timeframes=["1m"],
                )
            )
        return signals

    def _parse_signals(self, content: str) -> List[Signal]:
        logger = logging.getLogger("LLMClient")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            logger.error("LLM signals JSON parse failed. content: %s", content[:500])
            return []

        signals: List[Signal] = []
        for item in payload:
            signals.append(
                Signal(
                    symbol=item.get("symbol", ""),
                    action=item.get("action", "hold"),
                    confidence=float(item.get("confidence", 0.0)),
                    reason=item.get("reason", ""),
                    stop_loss=item.get("stop_loss"),
                    take_profit=item.get("take_profit"),
                    timeframes=item.get("timeframes"),
                    protect_intent=item.get("protect_intent"),
                )
            )
        if not signals:
            logger.warning("LLM returned empty signals. content: %s", content[:500])
        return signals

    def _parse_plan(self, content: str) -> Plan | None:
        logger = logging.getLogger("LLMClient")
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("LLM plan JSON parse failed. content: %s", content[:500])
            return None
        symbols = payload.get("symbols") or []
        timeframes = payload.get("timeframes") or []
        notes = payload.get("notes", "")
        include_account = bool(payload.get("include_account", False))
        include_positions = bool(payload.get("include_positions", False))
        if not isinstance(symbols, list) or not isinstance(timeframes, list):
            logger.error("LLM plan invalid schema. content: %s", content[:500])
            return None
        return Plan(
            symbols=symbols,
            timeframes=timeframes,
            notes=notes,
            include_account=include_account,
            include_positions=include_positions,
        )

    def _siliconflow_chat(
        self,
        market: List[MarketSnapshot],
        account: AccountInfo,
        positions: List[Position],
        instruments: List[Instrument],
        candles: dict,
        last_thoughts: str,
    ) -> List[Signal]:
        logger = logging.getLogger("LLMClient")
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        user_prompt = USER_PROMPT.format(
            last_thoughts=last_thoughts or "无",
            instruments=[i.__dict__ for i in instruments],
            market=[m.__dict__ for m in market],
            account=account.__dict__,
            positions=[p.__dict__ for p in positions],
            candles=candles,
        )
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        proxies = self._get_proxies()

        attempts = max(1, self.retries + 1)
        for idx in range(attempts):
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    json=body,
                    timeout=self.timeout_sec,
                    proxies=proxies,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                signals = self._parse_signals(content)
                return signals
            except requests.HTTPError as exc:
                text = exc.response.text if exc.response is not None else ""
                logger.error("LLM HTTP error (attempt %s/%s): %s | response: %s", idx + 1, attempts, exc, text[:500])
            except Exception as exc:
                logger.error("LLM request failed (attempt %s/%s): %s", idx + 1, attempts, exc, exc_info=True)

            if idx < attempts - 1:
                time.sleep(self.retry_backoff * (idx + 1))

        if self.fail_on_error:
            raise RuntimeError("LLM request failed after retries.")
        return []

    def generate_plan(self, instruments: List[Instrument], last_thoughts: str) -> Plan | None:
        if not self._is_supported():
            logging.getLogger("LLMClient").warning("LLM provider not supported, skip plan.")
            return None
        logger = logging.getLogger("LLMClient")
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        user_prompt = PLAN_USER_PROMPT.format(
            last_thoughts=last_thoughts or "无",
            instruments=[i.__dict__ for i in instruments],
        )
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": PLAN_SYSTEM_PROMPT.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        proxies = self._get_proxies()
        attempts = max(1, self.retries + 1)
        for idx in range(attempts):
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    json=body,
                    timeout=self.timeout_sec,
                    proxies=proxies,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                plan = self._parse_plan(content)
                if not plan:
                    logger.warning("LLM plan empty/invalid. content: %s", content[:500])
                return plan
            except requests.HTTPError as exc:
                text = exc.response.text if exc.response is not None else ""
                logger.error("LLM plan HTTP error (attempt %s/%s): %s | response: %s", idx + 1, attempts, exc, text[:500])
            except Exception as exc:
                logger.error("LLM plan failed (attempt %s/%s): %s", idx + 1, attempts, exc, exc_info=True)

            if idx < attempts - 1:
                time.sleep(self.retry_backoff * (idx + 1))

        if self.fail_on_error:
            raise RuntimeError("LLM plan failed after retries.")
        return None

    def generate(
        self,
        market: List[MarketSnapshot],
        account: AccountInfo,
        positions: List[Position],
        instruments: List[Instrument],
        candles: dict,
        last_thoughts: str,
    ) -> List[Signal]:
        if self._is_supported():
            signals = self._siliconflow_chat(market, account, positions, instruments, candles, last_thoughts)
            if signals:
                return signals
            if self.fail_on_error:
                raise RuntimeError("LLM returned empty signals.")
            logging.getLogger("LLMClient").warning("LLM empty signals -> fallback to dummy.")
            return self._dummy(market)

        if self.fail_on_error:
            raise RuntimeError("Unsupported LLM provider.")
        return self._dummy(market)

    def _get_proxies(self) -> dict | None:
        if not self.use_proxy:
            return {"http": None, "https": None}
        if self.proxy_url:
            return {"http": self.proxy_url, "https": self.proxy_url}
        return None
