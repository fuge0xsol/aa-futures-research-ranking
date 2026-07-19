#!/usr/bin/env python3
"""Collect exact futures-contract daily K-lines from FTShare MCP.

This is intentionally separate from the existing AKShare continuous-series
backtest. FTShare's endpoint returns a concrete WIND contract, so callers must
provide symbols such as M2609.DCE rather than a product code such as M.

Examples:
  python scripts/collect_ftshare_kline.py --symbol M2609.DCE --interval daily --limit 500
  python scripts/collect_ftshare_kline.py --symbols-file config/ftshare_contracts.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
except ImportError as exc:  # pragma: no cover - environment error
    raise SystemExit("缺少 mcp 依赖，请先安装：pip install mcp") from exc

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "market" / "ftshare_kline"
MCP_URL = "https://market.ft.tech/gateway/mcp"
TOOL_NAME = "ft_futures_contract_kline"


def parse_scalar(value: str) -> Any:
    value = value.strip().strip("`")
    if value in {"", "-", "null", "None", "none"}:
        return None
    # Keep dates and contract names as strings; parse numeric fields only.
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            pass
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", value):
        try:
            return float(value)
        except ValueError:
            pass
    return value


def parse_markdown_table(text: str) -> list[dict[str, Any]]:
    """Parse the markdown table returned by FTShare's ft_* tools."""
    rows: list[dict[str, Any]] = []
    lines = [line.strip() for line in text.splitlines() if "|" in line]
    for i in range(len(lines) - 1):
        header = lines[i]
        separator = lines[i + 1]
        if not re.search(r"\|\s*:?-{2,}", separator):
            continue
        keys = [x.strip().strip("`") for x in header.strip("|").split("|")]
        for raw in lines[i + 2 :]:
            cells = [x.strip() for x in raw.strip("|").split("|")]
            if len(cells) != len(keys):
                if rows:
                    break
                continue
            rows.append({k: parse_scalar(v) for k, v in zip(keys, cells)})
        if rows:
            break
    return rows


def unwrap_result(result: Any) -> str:
    parts = getattr(result, "content", None) or []
    texts = [getattr(part, "text", "") for part in parts]
    return "\n".join(x for x in texts if x)


def normalize_row(row: dict[str, Any], requested_symbol: str) -> dict[str, Any]:
    # The service has used both snake_case and display labels in different
    # deployments; normalize only known fields and preserve the raw row.
    aliases = {
        "datetime": "ts_millis",
        "date": "trade_date",
        "open_interest": "open_interest",
    }
    out: dict[str, Any] = {}
    for key, value in row.items():
        key = aliases.get(key, key)
        out[key] = value
    out.setdefault("symbol", requested_symbol)
    return out


async def fetch_one(symbol: str, interval: str, start: int | None, end: int | None, limit: int) -> list[dict[str, Any]]:
    args: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
    if start is not None:
        args["start"] = start
    if end is not None:
        args["end"] = end
    async with streamablehttp_client(MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(TOOL_NAME, args)
            text = unwrap_result(result)
            if not text:
                raise RuntimeError(f"{symbol}: FTShare 返回空结果")
            rows = parse_markdown_table(text)
            if not rows:
                # Keep the raw response available for debugging rather than
                # silently writing an empty cache.
                raise RuntimeError(f"{symbol}: 无法解析 FTShare 表格：{text[:500]}")
            return [normalize_row(row, symbol) for row in rows]


def load_symbols(args: argparse.Namespace) -> list[str]:
    symbols = list(args.symbol or [])
    if args.symbols_file:
        data = json.loads(Path(args.symbols_file).read_text())
        if isinstance(data, dict):
            data = data.get("symbols", [])
        if not isinstance(data, list):
            raise ValueError("symbols-file 必须是字符串数组，或 {\"symbols\": [...]}")
        symbols.extend(str(x) for x in data)
    result = sorted({x.strip().upper() for x in symbols if x.strip()})
    if not result:
        raise ValueError("至少提供一个 --symbol 或 --symbols-file")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", action="append", help="WIND 合约全码，例如 M2609.DCE，可重复")
    parser.add_argument("--symbols-file", help="JSON 字符串数组或 {symbols: [...]} 文件")
    parser.add_argument("--interval", default="daily", help="daily/weekly/monthly/...，默认 daily")
    parser.add_argument("--start", type=int, help="开始时间戳（毫秒）")
    parser.add_argument("--end", type=int, help="结束时间戳（毫秒），必须与 --start 同时使用")
    parser.add_argument("--limit", type=int, default=500, help="每个合约最多返回条数")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="缓存目录")
    args = parser.parse_args()
    if (args.start is None) != (args.end is None):
        parser.error("--start 与 --end 必须同时提供，或都不提供")
    if args.limit < 1:
        parser.error("--limit 必须大于 0")

    try:
        symbols = load_symbols(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    args.out.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    for symbol in symbols:
        try:
            rows = asyncio.run(fetch_one(symbol, args.interval, args.start, args.end, args.limit))
        except Exception as exc:
            print(f"ERROR {symbol}: {exc}", file=sys.stderr)
            return 1
        payload = {
            "symbol": symbol,
            "interval": args.interval,
            "generated_at": generated_at,
            "source": "FTShare MCP ft_futures_contract_kline",
            "rows": rows,
        }
        path = args.out / f"{symbol.replace('.', '_')}_{args.interval}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(f"{symbol}: {len(rows)} rows -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
