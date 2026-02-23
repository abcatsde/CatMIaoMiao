# AI 炒股机器人（框架）

这是一个 **Python LLM 交易机器人框架**，提供：
- 交易所（OKX）接口接入
- LLM 策略决策
- 风险控制（止损/止盈、仓位控制）
- 订单执行
- 市场监测与复盘
- 交易数据记录

> 注意：当前为**框架与占位实现**，未连接真实交易所，也未启用真实下单。

## 目录结构
```
Core/
  ai_trader/
    app.py
    config.py
    logging_config.py
    models.py
    llm/
    exchange/
    strategy/
    risk/
    execution/
    data/
    utils/
  run.py
  requirements.txt
```

## 快速开始
1. 复制环境变量：
   - 复制 `.env.example` 为 `.env`
2. 安装依赖
3. 运行：
   - `python run.py`

## 重要说明
- 框架默认启用**模拟交易**（PAPER_TRADING=true）
- 你需要配置 OKX 的 API Key/Secret/Passphrase
- 通过 OKX 公共接口拉取产品列表，LLM 从中选择 instId
- 可通过 `OKX_INST_TYPES` 指定允许的产品类型（例如 SPOT,SWAP,FUTURES,OPTION）
- 止损止盈会被动态更新并存储在 `STATE_STORE_PATH`
- 可通过 `USE_WEBSOCKET=true` 开启 OKX WebSocket 低延迟数据
- 内置波动率熔断：`VOL_WINDOW` 与 `VOL_THRESHOLD`
- BBO 价差优化：`USE_BBO` 与 `MAX_SPREAD_PCT`
- 分析系统日志：`ANALYSIS_LOG_PATH`
- LLM 失败即停止：`FAIL_ON_LLM_ERROR=true`
- LLM 记忆存储：`MEMORY_PATH`
- LLM 客户端支持 SiliconFlow（OpenAI 兼容接口），请配置 `LLM_BASE_URL`
