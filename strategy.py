from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeeConfig:
    commission_rate: float = 0.0003
    subscription_fee: float = 0.0
    redemption_fee_lt_7: float = 0.015
    redemption_fee_7_to_30: float = 0.001
    redemption_fee_gt_30: float = 0.0

    def get_redemption_fee(self, holding_days: int) -> float:
        if holding_days < 7:
            return self.redemption_fee_lt_7
        if holding_days <= 30:
            return self.redemption_fee_7_to_30
        return self.redemption_fee_gt_30


@dataclass
class Advice:
    action: str
    reason: str
    estimated_profit: float
    safety_margin: float
    convertible_units: float | None = None
    current_position_value: float | None = None
    spread_value: float | None = None


def _round_trip_stock_break_even(entry_price: float, commission_rate: float) -> float:
    return entry_price * (1 + commission_rate) / (1 - commission_rate)


def _switch_stock_to_fund_break_even(
    fund_price: float,
    commission_rate: float,
    subscription_fee: float,
) -> float:
    return fund_price * (1 + subscription_fee) / (1 - commission_rate)


def _redeem_fund_break_even(entry_price: float, redemption_fee_rate: float) -> float:
    return entry_price / (1 - redemption_fee_rate)


def _switch_fund_to_stock_break_even(
    stock_price: float,
    commission_rate: float,
    redemption_fee_rate: float,
) -> float:
    return stock_price * (1 + commission_rate) / (1 - redemption_fee_rate)


def validate_positive(value: float, label: str) -> None:
    if value <= 0:
        raise ValueError(f"{label} 必须大于 0")


def advise_for_stock_position(
    entry_stock_price: float,
    current_stock_price: float,
    current_fund_price: float,
    stock_held: float,
    fees: FeeConfig,
    switch_all_in: bool = True,
) -> Advice:
    validate_positive(entry_stock_price, "建仓股票价格")
    validate_positive(current_stock_price, "当前股票价格")
    validate_positive(current_fund_price, "当前基金价格")
    validate_positive(stock_held, "股票持仓数量")

    sell_proceeds = current_stock_price * stock_held * (1 - fees.commission_rate)
    stock_cost = entry_stock_price * stock_held * (1 + fees.commission_rate)
    realized_profit = sell_proceeds - stock_cost

    if current_stock_price > entry_stock_price and current_fund_price >= current_stock_price:
        safety_margin = _round_trip_stock_break_even(
            entry_stock_price, fees.commission_rate
        )
        if current_stock_price > safety_margin:
            return Advice(
                action="卖出股票，先落袋为安",
                reason="股票价格高于建仓价，且已经覆盖买卖双边佣金。",
                estimated_profit=realized_profit,
                safety_margin=safety_margin,
                current_position_value=sell_proceeds,
            )
        return Advice(
            action="继续持有股票",
            reason="股票虽上涨，但尚未完全跨过双边佣金的盈亏平衡线。",
            estimated_profit=realized_profit,
            safety_margin=safety_margin,
            current_position_value=sell_proceeds,
        )

    if current_stock_price <= entry_stock_price and current_stock_price > current_fund_price:
        safety_margin = _switch_stock_to_fund_break_even(
            current_fund_price, fees.commission_rate, fees.subscription_fee
        )
        spread_value = sell_proceeds - (
            stock_held * current_fund_price * (1 + fees.subscription_fee)
        )
        fund_units = sell_proceeds / (
            current_fund_price * (1 + fees.subscription_fee)
        )
        if current_stock_price > safety_margin:
            return Advice(
                action="卖出股票并全仓切换到基金"
                if switch_all_in
                else "可以考虑部分换仓到基金",
                reason="股票相对基金仍有溢价，卖股再申购基金后还能覆盖换仓成本。",
                estimated_profit=realized_profit,
                safety_margin=safety_margin,
                convertible_units=fund_units,
                current_position_value=sell_proceeds,
                spread_value=spread_value,
            )

        return Advice(
            action="继续持有股票",
            reason="虽然股票价格高于基金价格，但还不足以覆盖卖股加申购的成本。",
            estimated_profit=realized_profit,
            safety_margin=safety_margin,
            current_position_value=sell_proceeds,
            spread_value=spread_value,
        )

    return Advice(
        action="继续持有股票",
        reason="当前没有同时满足止盈或切换到基金的条件。",
        estimated_profit=realized_profit,
        safety_margin=_round_trip_stock_break_even(
            entry_stock_price, fees.commission_rate
        ),
        current_position_value=sell_proceeds,
    )


def advise_for_fund_position(
    entry_fund_price: float,
    current_fund_price: float,
    current_stock_price: float,
    fund_held: float,
    holding_days: int,
    fees: FeeConfig,
    switch_all_in: bool = True,
) -> Advice:
    validate_positive(entry_fund_price, "建仓基金价格")
    validate_positive(current_fund_price, "当前基金价格")
    validate_positive(current_stock_price, "当前股票价格")
    validate_positive(fund_held, "基金持仓份额")
    if holding_days < 0:
        raise ValueError("持有天数不能为负数")

    redemption_fee_rate = fees.get_redemption_fee(holding_days)
    redeem_value = current_fund_price * fund_held * (1 - redemption_fee_rate)
    fund_cost = entry_fund_price * fund_held
    redeem_profit = redeem_value - fund_cost

    if current_fund_price > entry_fund_price:
        safety_margin = _redeem_fund_break_even(entry_fund_price, redemption_fee_rate)
        if current_fund_price > safety_margin:
            return Advice(
                action="赎回基金，兑现利润",
                reason="基金价格已经高于赎回成本线，赎回后仍能保留正收益。",
                estimated_profit=redeem_profit,
                safety_margin=safety_margin,
                current_position_value=redeem_value,
            )
        return Advice(
            action="继续持有基金",
            reason="基金在上涨，但扣除赎回费后还没有完全转正。",
            estimated_profit=redeem_profit,
            safety_margin=safety_margin,
            current_position_value=redeem_value,
        )

    if current_fund_price > current_stock_price:
        safety_margin = _switch_fund_to_stock_break_even(
            current_stock_price, fees.commission_rate, redemption_fee_rate
        )
        spread_value = redeem_value - (
            fund_held * current_stock_price * (1 + fees.commission_rate)
        )
        stock_units = redeem_value / (
            current_stock_price * (1 + fees.commission_rate)
        )
        if current_fund_price > safety_margin:
            return Advice(
                action="赎回基金并全仓切换到股票"
                if switch_all_in
                else "可以考虑部分换仓到股票",
                reason="基金相对股票存在足够溢价，赎回并买入股票后仍可覆盖换仓成本。",
                estimated_profit=redeem_profit,
                safety_margin=safety_margin,
                convertible_units=stock_units,
                current_position_value=redeem_value,
                spread_value=spread_value,
            )

        return Advice(
            action="继续持有基金",
            reason="基金相对股票更贵，但还没有高到足以覆盖赎回和买股成本。",
            estimated_profit=redeem_profit,
            safety_margin=safety_margin,
            current_position_value=redeem_value,
            spread_value=spread_value,
        )

    return Advice(
        action="继续持有基金",
        reason="当前没有同时满足止盈或切换到股票的条件。",
        estimated_profit=redeem_profit,
        safety_margin=_redeem_fund_break_even(entry_fund_price, redemption_fee_rate),
        current_position_value=redeem_value,
    )
