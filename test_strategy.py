import unittest

from strategy import FeeConfig, advise_for_fund_position, advise_for_stock_position


class StrategyTests(unittest.TestCase):
    def test_redemption_fee_tiers(self) -> None:
        fees = FeeConfig()
        self.assertEqual(fees.get_redemption_fee(3), 0.015)
        self.assertEqual(fees.get_redemption_fee(7), 0.001)
        self.assertEqual(fees.get_redemption_fee(31), 0.0)

    def test_stock_take_profit(self) -> None:
        advice = advise_for_stock_position(
            entry_stock_price=1.0,
            current_stock_price=1.02,
            current_fund_price=1.03,
            stock_held=1000,
            fees=FeeConfig(),
        )
        self.assertIn("卖出股票", advice.action)
        self.assertGreater(advice.estimated_profit, 0)
        self.assertIsNotNone(advice.current_position_value)

    def test_stock_switch_to_fund(self) -> None:
        advice = advise_for_stock_position(
            entry_stock_price=1.2,
            current_stock_price=1.0,
            current_fund_price=0.9,
            stock_held=1000,
            fees=FeeConfig(),
        )
        self.assertIsNotNone(advice.convertible_units)
        self.assertIsNotNone(advice.spread_value)
        self.assertIn("基金", advice.action)

    def test_fund_take_profit(self) -> None:
        advice = advise_for_fund_position(
            entry_fund_price=1.0,
            current_fund_price=1.02,
            current_stock_price=0.95,
            fund_held=1000,
            holding_days=40,
            fees=FeeConfig(),
        )
        self.assertIn("赎回基金", advice.action)
        self.assertGreater(advice.estimated_profit, 0)
        self.assertIsNotNone(advice.current_position_value)

    def test_fund_switch_to_stock(self) -> None:
        advice = advise_for_fund_position(
            entry_fund_price=1.1,
            current_fund_price=1.0,
            current_stock_price=0.9,
            fund_held=1000,
            holding_days=10,
            fees=FeeConfig(),
        )
        self.assertIsNotNone(advice.convertible_units)
        self.assertIsNotNone(advice.spread_value)
        self.assertIn("股票", advice.action)


if __name__ == "__main__":
    unittest.main()
