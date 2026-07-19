# AA期货研报回测榜

独立发布的 GitHub Pages 静态网站，按农产、金属、能化、黑色四大板块展示 AA 期货公司公开研报线索，并逐步接入观点结构化、历史行情回测和机构排名。

## 当前数据采集与回测

已完成首轮公开研报采集，时间窗口为最近约 90 天。只保留标题/摘要中命中的**主要期货品种**。

- 农产：134 条
- 金属：250 条
- 能化：366 条
- 黑色：91 条
- 合计：841 条板块研报记录

已新增日线级别回测原型：

- 行情：AKShare `futures_zh_daily_sina`
- 合约：对应品种连续主力序列 `品种0`
- 入场：研报发布日期后第一个可用交易日收盘价
- 退出：1、5、20 个交易日后的收盘价
- 看多收益：价格收益
- 看空收益：价格收益取负
- 中性/暂无：不纳入方向准确率
- 观点提取：当前为标题规则提取，标题证据置信度较低，需后续正文/摘要复核

输出文件：

```text
data/backtest/normalized_reports.json
 data/backtest/backtest_records.json
 data/backtest/rankings_1d.json
 data/backtest/rankings_5d.json
 data/backtest/rankings_20d.json
 data/backtest/{sector}_rankings_1d.json
```

**当前回测仅为可复现原型，不是正式投研结论。**原因是：当前只有标题/摘要级方向识别，部分品种和机构的有效样本不足；正式排名需增加正文观点、发布时间、具体合约和更严格的样本门槛。

## 页面

- 首页：`/`
- 农产：`/agri/`
- 金属：`/metals/`
- 能化：`/energy/`
- 黑色：`/ferrous/`

## FTShare 期货合约 K 线（可选数据源）

新增脚本 `scripts/collect_ftshare_kline.py`，仅接入 FTShare 的具体期货合约 K 线接口 `ft_futures_contract_kline`。它不替换现有 AKShare 主力连续回测，而是用于缓存真实合约的 OHLC、成交量、成交额、VWAP 和持仓量，便于后续做行情交叉验证与持仓量增强分析。

示例：

```bash
python scripts/collect_ftshare_kline.py --symbol M2609.DCE --interval daily --limit 500
```

多个合约可写入 JSON：

```json
{"symbols": ["M2609.DCE", "SR609.CZCE"]}
```

然后执行：

```bash
python scripts/collect_ftshare_kline.py --symbols-file config/ftshare_contracts.json
```

缓存写入 `data/market/ftshare_kline/`，默认被 Git 忽略。FTShare MCP 返回 markdown 表格，脚本会解析并保存为 JSON；请求失败或解析失败时不会写入空缓存。

> 当前项目的正式回测基准仍是 AKShare `品种0` 主力连续序列。FTShare 具体合约数据作为补充数据源，避免把不同合约直接拼接成错误的连续价格序列。


```bash
python -m http.server 8080
```

## GitHub Pages

```text
https://fuge0xsol.github.io/aa-futures-research-ranking/
```

数据仅用于研究，不构成投资建议。
