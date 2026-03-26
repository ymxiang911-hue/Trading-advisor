from __future__ import annotations

from datetime import datetime

import streamlit as st

from market_data import QuoteSnapshot, fetch_market_snapshot
from strategy import (
    Advice,
    FeeConfig,
    advise_for_fund_position,
    advise_for_stock_position,
)


DEFAULTS = {
    "quote_mode": "manual",
    "position_type": "stock",
    "switch_all_in": True,
    "auto_evaluate": True,
    "stock_code": "161226",
    "fund_code": "161226",
    "entry_price": 1.0000,
    "current_stock_price": 1.0000,
    "current_fund_price": 1.0000,
    "position_amount": 1000.0,
    "holding_days": 10,
    "commission_rate": 0.0003,
    "subscription_fee": 0.0,
    "redemption_lt_7": 0.015,
    "redemption_7_30": 0.001,
    "redemption_gt_30": 0.0,
    "quote_status": "当前为手动输入模式。你也可以切换到实时抓取后点击按钮获取行情。",
    "action_status": "等待生成建议。",
    "advice_generated_at": "",
}


def init_session_state() -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("advice_payload", None)


def build_fees() -> FeeConfig:
    return FeeConfig(
        commission_rate=float(st.session_state.commission_rate),
        subscription_fee=float(st.session_state.subscription_fee),
        redemption_fee_lt_7=float(st.session_state.redemption_lt_7),
        redemption_fee_7_to_30=float(st.session_state.redemption_7_30),
        redemption_fee_gt_30=float(st.session_state.redemption_gt_30),
    )


def apply_snapshot(snapshot: QuoteSnapshot) -> None:
    st.session_state.current_stock_price = round(snapshot.stock_price, 4)
    st.session_state.current_fund_price = round(snapshot.fund_price, 4)

    stock_name = f"{snapshot.stock_name} " if snapshot.stock_name else ""
    fund_name = f"{snapshot.fund_name} " if snapshot.fund_name else ""
    st.session_state.quote_status = (
        f"股票 {snapshot.stock_code} {stock_name}最新价 {snapshot.stock_price:.4f}；"
        f"基金 {snapshot.fund_code} {fund_name}{snapshot.fund_source} {snapshot.fund_price:.4f}。"
        f" 股票时间: {snapshot.stock_time or '未知'}，基金时间: {snapshot.fund_time or '未知'}。"
    )


def fetch_quotes() -> None:
    try:
        snapshot = fetch_market_snapshot(
            st.session_state.stock_code, st.session_state.fund_code
        )
    except Exception as exc:
        st.session_state.quote_status = f"行情抓取失败：{exc}"
        st.error(str(exc))
        return

    apply_snapshot(snapshot)
    st.success("行情已更新。")
    if st.session_state.auto_evaluate:
        generate_advice(show_message=False)


def format_advice_lines(advice: Advice, fees: FeeConfig, holding_days: int) -> list[str]:
    if st.session_state.position_type == "stock":
        lines = [
            f"建议动作: {advice.action}",
            f"原因说明: {advice.reason}",
            f"若当前卖出股票，净收益估算: {advice.estimated_profit:.4f}",
            f"股票止盈安全边际价: {advice.safety_margin:.4f}",
        ]
        if advice.current_position_value is not None:
            lines.append(
                f"当前持仓按卖出后可回笼资金: {advice.current_position_value:.4f}"
            )
        if advice.spread_value is not None:
            lines.append(
                f"按同等数量比较，切换到基金后的价差结余: {advice.spread_value:.4f}"
            )
        if advice.convertible_units is not None:
            lines.append(f"若执行换仓，预计可获得基金份额: {advice.convertible_units:.4f}")
        return lines

    redemption_rate = fees.get_redemption_fee(holding_days)
    lines = [
        f"建议动作: {advice.action}",
        f"原因说明: {advice.reason}",
        f"当前赎回费率: {redemption_rate:.4%}",
        f"若当前赎回基金，净收益估算: {advice.estimated_profit:.4f}",
        f"基金止盈/换仓安全边际价: {advice.safety_margin:.4f}",
    ]
    if advice.current_position_value is not None:
        lines.append(f"当前持仓按赎回后可回笼资金: {advice.current_position_value:.4f}")
    if advice.spread_value is not None:
        lines.append(f"按同等数量比较，切换到股票后的价差结余: {advice.spread_value:.4f}")
    if advice.convertible_units is not None:
        lines.append(f"若执行换仓，预计可买入股票数量: {advice.convertible_units:.4f}")
    return lines


def generate_advice(show_message: bool = True) -> None:
    try:
        fees = build_fees()
        holding_days = int(st.session_state.holding_days)

        if st.session_state.position_type == "stock":
            advice = advise_for_stock_position(
                entry_stock_price=float(st.session_state.entry_price),
                current_stock_price=float(st.session_state.current_stock_price),
                current_fund_price=float(st.session_state.current_fund_price),
                stock_held=float(st.session_state.position_amount),
                fees=fees,
                switch_all_in=bool(st.session_state.switch_all_in),
            )
        else:
            advice = advise_for_fund_position(
                entry_fund_price=float(st.session_state.entry_price),
                current_fund_price=float(st.session_state.current_fund_price),
                current_stock_price=float(st.session_state.current_stock_price),
                fund_held=float(st.session_state.position_amount),
                holding_days=holding_days,
                fees=fees,
                switch_all_in=bool(st.session_state.switch_all_in),
            )

        st.session_state.advice_payload = {
            "advice": advice,
            "fees": fees,
            "holding_days": holding_days,
            "lines": format_advice_lines(advice, fees, holding_days),
        }
        st.session_state.advice_generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.action_status = (
            f"建议已更新：{st.session_state.advice_generated_at}"
        )
        if show_message:
            st.success("建议已生成。")
    except Exception as exc:
        st.session_state.action_status = "输入有误，未能生成建议。"
        st.session_state.advice_payload = None
        st.error(str(exc))


def reset_defaults() -> None:
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
    st.session_state.advice_payload = None


def render_metrics(payload: dict) -> None:
    advice: Advice = payload["advice"]
    fees: FeeConfig = payload["fees"]
    holding_days: int = payload["holding_days"]

    col1, col2, col3 = st.columns(3)
    col1.metric("建议动作", advice.action)
    col2.metric("净收益估算", f"{advice.estimated_profit:.4f}")
    col3.metric("安全边际价", f"{advice.safety_margin:.4f}")

    extra_cols = st.columns(3)
    extra_cols[0].metric(
        "当前可回笼资金",
        f"{advice.current_position_value:.4f}" if advice.current_position_value is not None else "-",
    )
    extra_cols[1].metric(
        "换仓价差结余",
        f"{advice.spread_value:.4f}" if advice.spread_value is not None else "-",
    )
    if st.session_state.position_type == "fund":
        extra_cols[2].metric("当前赎回费率", f"{fees.get_redemption_fee(holding_days):.4%}")
    else:
        extra_cols[2].metric(
            "可转换基金份额",
            f"{advice.convertible_units:.4f}" if advice.convertible_units is not None else "-",
        )


def main() -> None:
    st.set_page_config(
        page_title="基金 / 股票轮动建议助手",
        page_icon="📈",
        layout="wide",
    )
    init_session_state()

    st.title("基金 / 股票轮动建议助手")
    st.caption("桌面版逻辑已改为网页入口，适合部署到 Streamlit Cloud 或其他云端 Python 平台。")

    top_col1, top_col2 = st.columns([2, 1])
    with top_col1:
        st.info(st.session_state.quote_status)
    with top_col2:
        st.write(st.session_state.action_status)

    with st.sidebar:
        st.subheader("模式")
        st.radio(
            "行情来源",
            options=["manual", "auto"],
            format_func=lambda value: "手动输入" if value == "manual" else "实时抓取",
            key="quote_mode",
        )
        st.radio(
            "当前持仓",
            options=["stock", "fund"],
            format_func=lambda value: "当前持有股票" if value == "stock" else "当前持有基金",
            key="position_type",
        )
        st.checkbox("满足条件时按全仓方式换仓", key="switch_all_in")
        st.checkbox("抓取行情后自动重新生成建议", key="auto_evaluate")

        st.divider()
        st.subheader("行情代码")
        st.text_input("股票代码", key="stock_code")
        st.text_input("基金代码", key="fund_code")
        if st.button("抓取最新行情", use_container_width=True):
            fetch_quotes()

        st.divider()
        st.subheader("手续费参数")
        st.number_input("股票佣金率", key="commission_rate", min_value=0.0, format="%.6f")
        st.number_input("基金申购费率", key="subscription_fee", min_value=0.0, format="%.6f")
        st.number_input("基金赎回费率 (<7天)", key="redemption_lt_7", min_value=0.0, format="%.6f")
        st.number_input("基金赎回费率 (7-30天)", key="redemption_7_30", min_value=0.0, format="%.6f")
        st.number_input("基金赎回费率 (>30天)", key="redemption_gt_30", min_value=0.0, format="%.6f")

        st.divider()
        if st.button("恢复默认值", use_container_width=True):
            reset_defaults()
            st.rerun()

    st.subheader("输入参数")
    input_col1, input_col2 = st.columns(2)

    with input_col1:
        st.number_input(
            "基金参考建仓价" if st.session_state.position_type == "fund" else "股票参考建仓价",
            key="entry_price",
            min_value=0.0001,
            format="%.4f",
        )
        st.number_input(
            "当前股票价格",
            key="current_stock_price",
            min_value=0.0001,
            format="%.4f",
        )

    with input_col2:
        st.number_input(
            "当前基金价格",
            key="current_fund_price",
            min_value=0.0001,
            format="%.4f",
        )
        st.number_input(
            "基金份额" if st.session_state.position_type == "fund" else "股票持仓数量",
            key="position_amount",
            min_value=0.0001,
            format="%.4f",
        )

    if st.session_state.position_type == "fund":
        st.number_input("基金持有天数", key="holding_days", min_value=0, step=1)

    st.write("")
    if st.button("生成建议", type="primary", use_container_width=True):
        generate_advice()

    payload = st.session_state.advice_payload
    if payload is not None:
        st.subheader("策略输出")
        render_metrics(payload)
        with st.container(border=True):
            for line in payload["lines"]:
                st.write(line)
            if st.session_state.position_type == "stock":
                st.caption("说明：你可以实时抓取后再手动覆盖基金价格，多次试算。")
            else:
                st.caption("说明：如果基金盘中估算值和你的观察不一致，可以手动覆盖后重新评估。")


if __name__ == "__main__":
    main()
