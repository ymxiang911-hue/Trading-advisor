from __future__ import annotations

from dataclasses import dataclass

try:
    import efinance as ef
except ImportError:  # pragma: no cover - runtime fallback
    ef = None


@dataclass
class QuoteSnapshot:
    stock_code: str
    stock_price: float
    fund_code: str
    fund_price: float
    stock_name: str = ""
    fund_name: str = ""
    stock_time: str = ""
    fund_time: str = ""
    fund_source: str = ""


def _require_efinance() -> None:
    if ef is None:
        raise RuntimeError("未安装 efinance，当前只能使用手动输入模式。")


def _validate_quote_code(code: str, label: str) -> str:
    normalized = code.strip()
    if not normalized:
        raise ValueError(f"{label}不能为空")
    return normalized


def fetch_stock_price(stock_code: str) -> tuple[float, str, str]:
    _require_efinance()
    normalized_code = _validate_quote_code(stock_code, "股票代码")
    df = ef.stock.get_latest_quote([normalized_code])
    if df.empty:
        raise RuntimeError(f"未获取到股票 {normalized_code} 的实时行情")

    row = df.iloc[0]
    return (
        float(row["最新价"]),
        str(row.get("名称", "")),
        str(row.get("数据日期", "")),
    )


def fetch_fund_price(fund_code: str) -> tuple[float, str, str, str]:
    _require_efinance()
    normalized_code = _validate_quote_code(fund_code, "基金代码")

    df = ef.fund.get_realtime_increase_rate(normalized_code)
    if not df.empty:
        row = df.iloc[0]
        latest_nav = float(row["最新净值"])
        increase_rate = float(row["估算涨跌幅"])
        estimated_price = latest_nav * (1 + increase_rate / 100)
        return (
            estimated_price,
            str(row.get("基金名称", "")),
            str(row.get("估算时间", "")),
            "基金盘中估算",
        )

    history_df = ef.fund.get_quote_history(normalized_code, pz=1)
    if history_df.empty:
        raise RuntimeError(f"未获取到基金 {normalized_code} 的净值信息")

    row = history_df.iloc[0]
    return (
        float(row["单位净值"]),
        "",
        str(row.get("日期", "")),
        "最新公布净值",
    )


def fetch_market_snapshot(stock_code: str, fund_code: str) -> QuoteSnapshot:
    stock_price, stock_name, stock_time = fetch_stock_price(stock_code)
    fund_price, fund_name, fund_time, fund_source = fetch_fund_price(fund_code)
    return QuoteSnapshot(
        stock_code=stock_code.strip(),
        stock_price=stock_price,
        fund_code=fund_code.strip(),
        fund_price=fund_price,
        stock_name=stock_name,
        fund_name=fund_name,
        stock_time=stock_time,
        fund_time=fund_time,
        fund_source=fund_source,
    )
