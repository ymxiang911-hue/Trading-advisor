import unittest
from unittest.mock import patch

import pandas as pd

from market_data import fetch_fund_price, fetch_market_snapshot, fetch_stock_price


class MarketDataTests(unittest.TestCase):
    @patch("market_data.ef")
    def test_fetch_stock_price_uses_latest_quote(self, mock_ef) -> None:
        mock_ef.stock.get_latest_quote.return_value = pd.DataFrame(
            [{"名称": "测试证券", "最新价": 1.2345, "数据日期": "2026-03-24 10:00:00"}]
        )

        price, name, quote_time = fetch_stock_price("161226")

        self.assertAlmostEqual(price, 1.2345)
        self.assertEqual(name, "测试证券")
        self.assertEqual(quote_time, "2026-03-24 10:00:00")

    @patch("market_data.ef")
    def test_fetch_fund_price_prefers_realtime_estimate(self, mock_ef) -> None:
        mock_ef.fund.get_realtime_increase_rate.return_value = pd.DataFrame(
            [
                {
                    "基金名称": "测试基金",
                    "最新净值": 1.2,
                    "估算涨跌幅": 5.0,
                    "估算时间": "2026-03-24 10:00:00",
                }
            ]
        )

        price, name, quote_time, source = fetch_fund_price("161226")

        self.assertAlmostEqual(price, 1.26)
        self.assertEqual(name, "测试基金")
        self.assertEqual(quote_time, "2026-03-24 10:00:00")
        self.assertEqual(source, "基金盘中估算")

    @patch("market_data.ef")
    def test_fetch_fund_price_falls_back_to_latest_nav(self, mock_ef) -> None:
        mock_ef.fund.get_realtime_increase_rate.return_value = pd.DataFrame()
        mock_ef.fund.get_quote_history.return_value = pd.DataFrame(
            [{"日期": "2026-03-23", "单位净值": 0.9876}]
        )

        price, name, quote_time, source = fetch_fund_price("161226")

        self.assertAlmostEqual(price, 0.9876)
        self.assertEqual(name, "")
        self.assertEqual(quote_time, "2026-03-23")
        self.assertEqual(source, "最新公布净值")

    @patch("market_data.fetch_fund_price")
    @patch("market_data.fetch_stock_price")
    def test_fetch_market_snapshot_combines_both_quotes(
        self, mock_stock, mock_fund
    ) -> None:
        mock_stock.return_value = (1.11, "测试证券", "2026-03-24 10:00:00")
        mock_fund.return_value = (
            1.02,
            "测试基金",
            "2026-03-24 10:00:00",
            "基金盘中估算",
        )

        snapshot = fetch_market_snapshot("161226", "161226")

        self.assertEqual(snapshot.stock_code, "161226")
        self.assertEqual(snapshot.fund_code, "161226")
        self.assertAlmostEqual(snapshot.stock_price, 1.11)
        self.assertAlmostEqual(snapshot.fund_price, 1.02)
        self.assertEqual(snapshot.stock_name, "测试证券")
        self.assertEqual(snapshot.fund_name, "测试基金")


if __name__ == "__main__":
    unittest.main()
