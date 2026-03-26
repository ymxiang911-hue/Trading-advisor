from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from tkinter.scrolledtext import ScrolledText

from market_data import QuoteSnapshot, fetch_market_snapshot
from strategy import (
    Advice,
    FeeConfig,
    advise_for_fund_position,
    advise_for_stock_position,
)


class TradingAdvisorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("基金/股票轮动建议助手")
        self.root.geometry("1100x920")
        self.root.minsize(760, 560)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.position_type = tk.StringVar(value="stock")
        self.quote_mode = tk.StringVar(value="manual")
        self.switch_all_in = tk.BooleanVar(value=True)
        self.auto_refresh = tk.BooleanVar(value=False)
        self.auto_evaluate = tk.BooleanVar(value=True)
        self.quote_status = tk.StringVar(
            value="当前为手动输入模式。你也可以切换到实时抓取并自动刷新。"
        )
        self.action_status = tk.StringVar(value="等待生成建议。")
        self.refresh_job: str | None = None
        self.is_fetching = False

        self.vars = {
            "stock_code": tk.StringVar(value="161226"),
            "fund_code": tk.StringVar(value="161226"),
            "refresh_interval": tk.StringVar(value="30"),
            "entry_price": tk.StringVar(value="1.0000"),
            "current_stock_price": tk.StringVar(value="1.0000"),
            "current_fund_price": tk.StringVar(value="1.0000"),
            "position_amount": tk.StringVar(value="1000"),
            "holding_days": tk.StringVar(value="10"),
            "commission_rate": tk.StringVar(value="0.0003"),
            "subscription_fee": tk.StringVar(value="0.0"),
            "redemption_lt_7": tk.StringVar(value="0.015"),
            "redemption_7_30": tk.StringVar(value="0.001"),
            "redemption_gt_30": tk.StringVar(value="0.0"),
        }

        self._build_ui()
        self._toggle_position_fields()
        self._toggle_quote_mode()

    def _build_ui(self) -> None:
        outer_frame = ttk.Frame(self.root)
        outer_frame.pack(fill="both", expand=True)
        outer_frame.columnconfigure(0, weight=1)
        outer_frame.rowconfigure(0, weight=1)

        self.main_canvas = tk.Canvas(outer_frame, highlightthickness=0)
        self.main_canvas.grid(row=0, column=0, sticky="nsew")

        self.main_scrollbar = ttk.Scrollbar(
            outer_frame, orient="vertical", command=self.main_canvas.yview
        )
        self.main_scrollbar.grid(row=0, column=1, sticky="ns")
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        container = ttk.Frame(self.main_canvas, padding=16)
        self.main_canvas_window = self.main_canvas.create_window(
            (0, 0), window=container, anchor="nw"
        )
        container.bind("<Configure>", self._on_container_configure)
        self.main_canvas.bind("<Configure>", self._on_canvas_configure)
        self.main_canvas.bind("<Enter>", self._bind_mousewheel)
        self.main_canvas.bind("<Leave>", self._unbind_mousewheel)

        container.columnconfigure(0, weight=1)

        title = ttk.Label(
            container,
            text="基金 / 股票轮动建议助手",
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(
            container,
            text="支持手动输入价格，也支持实时抓取股票最新价与基金盘中估算净值，再按轮动规则输出建议。",
            font=("Microsoft YaHei UI", 10),
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(6, 16))

        quote_frame = ttk.LabelFrame(container, text="行情来源", padding=12)
        quote_frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        quote_frame.columnconfigure(1, weight=1)
        quote_frame.columnconfigure(3, weight=1)

        ttk.Radiobutton(
            quote_frame,
            text="手动输入",
            value="manual",
            variable=self.quote_mode,
            command=self._toggle_quote_mode,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            quote_frame,
            text="实时抓取",
            value="auto",
            variable=self.quote_mode,
            command=self._toggle_quote_mode,
        ).grid(row=0, column=1, sticky="w")

        ttk.Label(quote_frame, text="股票代码").grid(row=1, column=0, sticky="w", pady=6)
        self.stock_code_entry = ttk.Entry(
            quote_frame, textvariable=self.vars["stock_code"]
        )
        self.stock_code_entry.grid(row=1, column=1, sticky="ew", padx=(8, 16), pady=6)

        ttk.Label(quote_frame, text="基金代码").grid(row=1, column=2, sticky="w", pady=6)
        self.fund_code_entry = ttk.Entry(
            quote_frame, textvariable=self.vars["fund_code"]
        )
        self.fund_code_entry.grid(row=1, column=3, sticky="ew", pady=6)

        self.fetch_button = ttk.Button(
            quote_frame,
            text="抓取最新行情",
            command=lambda: self.refresh_quotes(manual_trigger=True),
        )
        self.fetch_button.grid(row=2, column=0, sticky="w", pady=6)

        self.auto_refresh_check = ttk.Checkbutton(
            quote_frame,
            text="自动监测",
            variable=self.auto_refresh,
            command=self._toggle_auto_refresh,
        )
        self.auto_refresh_check.grid(row=2, column=1, sticky="w", pady=6)

        ttk.Label(quote_frame, text="刷新间隔(秒)").grid(
            row=2, column=2, sticky="e", pady=6
        )
        self.refresh_interval_entry = ttk.Entry(
            quote_frame, textvariable=self.vars["refresh_interval"], width=8
        )
        self.refresh_interval_entry.grid(row=2, column=3, sticky="w", pady=6)

        ttk.Checkbutton(
            quote_frame,
            text="抓取后自动重新生成建议",
            variable=self.auto_evaluate,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=6)

        self.quote_status_label = ttk.Label(
            quote_frame,
            textvariable=self.quote_status,
            font=("Microsoft YaHei UI", 9),
            foreground="#1f4e79",
        )
        self.quote_status_label.grid(row=4, column=0, columnspan=4, sticky="w", pady=(6, 0))

        position_frame = ttk.LabelFrame(container, text="当前持仓", padding=12)
        position_frame.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        position_frame.columnconfigure(0, weight=1)
        position_frame.columnconfigure(1, weight=1)

        ttk.Radiobutton(
            position_frame,
            text="当前持有股票",
            value="stock",
            variable=self.position_type,
            command=self._toggle_position_fields,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            position_frame,
            text="当前持有基金",
            value="fund",
            variable=self.position_type,
            command=self._toggle_position_fields,
        ).grid(row=0, column=1, sticky="w")

        input_frame = ttk.LabelFrame(container, text="输入参数", padding=12)
        input_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 12))
        input_frame.columnconfigure(1, weight=1)
        input_frame.columnconfigure(3, weight=1)

        self.entry_price_label = ttk.Label(input_frame, text="当前持仓的参考建仓价")
        self.entry_price_label.grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(input_frame, textvariable=self.vars["entry_price"]).grid(
            row=0, column=1, sticky="ew", padx=(8, 16), pady=6
        )

        ttk.Label(input_frame, text="当前股票价格").grid(row=0, column=2, sticky="w", pady=6)
        ttk.Entry(input_frame, textvariable=self.vars["current_stock_price"]).grid(
            row=0, column=3, sticky="ew", pady=6
        )

        ttk.Label(input_frame, text="当前基金价格").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(input_frame, textvariable=self.vars["current_fund_price"]).grid(
            row=1, column=1, sticky="ew", padx=(8, 16), pady=6
        )

        self.position_amount_label = ttk.Label(input_frame, text="持仓数量 / 份额")
        self.position_amount_label.grid(row=1, column=2, sticky="w", pady=6)
        ttk.Entry(input_frame, textvariable=self.vars["position_amount"]).grid(
            row=1, column=3, sticky="ew", pady=6
        )

        self.holding_days_label = ttk.Label(input_frame, text="基金持有天数")
        self.holding_days_label.grid(row=2, column=0, sticky="w", pady=6)
        self.holding_days_entry = ttk.Entry(
            input_frame, textvariable=self.vars["holding_days"]
        )
        self.holding_days_entry.grid(
            row=2, column=1, sticky="ew", padx=(8, 16), pady=6
        )

        ttk.Checkbutton(
            input_frame,
            text="满足条件时按全仓方式换仓",
            variable=self.switch_all_in,
        ).grid(row=2, column=2, columnspan=2, sticky="w", pady=6)

        fee_frame = ttk.LabelFrame(container, text="手续费参数", padding=12)
        fee_frame.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        fee_frame.columnconfigure(1, weight=1)
        fee_frame.columnconfigure(3, weight=1)

        ttk.Label(fee_frame, text="股票佣金率").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(fee_frame, textvariable=self.vars["commission_rate"]).grid(
            row=0, column=1, sticky="ew", padx=(8, 16), pady=6
        )

        ttk.Label(fee_frame, text="基金申购费率").grid(row=0, column=2, sticky="w", pady=6)
        ttk.Entry(fee_frame, textvariable=self.vars["subscription_fee"]).grid(
            row=0, column=3, sticky="ew", pady=6
        )

        ttk.Label(fee_frame, text="基金赎回费率 (<7天)").grid(
            row=1, column=0, sticky="w", pady=6
        )
        ttk.Entry(fee_frame, textvariable=self.vars["redemption_lt_7"]).grid(
            row=1, column=1, sticky="ew", padx=(8, 16), pady=6
        )

        ttk.Label(fee_frame, text="基金赎回费率 (7-30天)").grid(
            row=1, column=2, sticky="w", pady=6
        )
        ttk.Entry(fee_frame, textvariable=self.vars["redemption_7_30"]).grid(
            row=1, column=3, sticky="ew", pady=6
        )

        ttk.Label(fee_frame, text="基金赎回费率 (>30天)").grid(
            row=2, column=0, sticky="w", pady=6
        )
        ttk.Entry(fee_frame, textvariable=self.vars["redemption_gt_30"]).grid(
            row=2, column=1, sticky="ew", padx=(8, 16), pady=6
        )

        action_frame = ttk.Frame(container)
        action_frame.grid(row=6, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(action_frame, text="生成建议", command=lambda: self.generate_advice()).pack(
            side="left"
        )
        ttk.Button(action_frame, text="恢复默认值", command=self.reset_defaults).pack(
            side="left", padx=(12, 0)
        )
        ttk.Label(
            action_frame,
            textvariable=self.action_status,
            font=("Microsoft YaHei UI", 9),
            foreground="#1f4e79",
        ).pack(side="left", padx=(16, 0))

        result_frame = ttk.LabelFrame(container, text="策略输出", padding=12)
        result_frame.grid(row=7, column=0, sticky="nsew")
        container.rowconfigure(7, weight=1)

        self.result_text = ScrolledText(
            result_frame,
            wrap="char",
            font=("Microsoft YaHei UI", 11),
            padx=8,
            pady=8,
            height=24,
        )
        self.result_text.pack(fill="both", expand=True)
        self.result_text.insert(
            "1.0",
            "这里会显示操作建议、触发原因、预估收益、安全边际，以及换仓时可转换的目标份额。\n",
        )
        self.result_text.configure(state="disabled")

    def _on_container_configure(self, _event: tk.Event) -> None:
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.main_canvas.itemconfigure(self.main_canvas_window, width=event.width)

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event) -> None:
        self.main_canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.result_text.winfo_containing(event.x_root, event.y_root) == self.result_text:
            return
        self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _toggle_position_fields(self) -> None:
        is_fund = self.position_type.get() == "fund"
        state = "normal" if is_fund else "disabled"

        self.holding_days_label.configure(
            text="基金持有天数" if is_fund else "基金持有天数（仅持基时需要）"
        )
        self.entry_price_label.configure(
            text="基金参考建仓价" if is_fund else "股票参考建仓价"
        )
        self.position_amount_label.configure(
            text="基金份额" if is_fund else "股票持仓数量"
        )
        self.holding_days_entry.configure(state=state)

    def _toggle_quote_mode(self) -> None:
        is_auto = self.quote_mode.get() == "auto"
        state = "normal" if is_auto else "disabled"
        self.stock_code_entry.configure(state=state)
        self.fund_code_entry.configure(state=state)
        self.fetch_button.configure(state=state)
        self.auto_refresh_check.configure(state=state)
        self.refresh_interval_entry.configure(state=state)
        if not is_auto:
            self.auto_refresh.set(False)
            self._cancel_scheduled_refresh()
            self.quote_status.set("当前为手动输入模式。你可以直接修改价格后点击“生成建议”。")
        else:
            self.quote_status.set(
                "当前为实时抓取模式。点击“抓取最新行情”或开启自动监测。"
            )

    def _toggle_auto_refresh(self) -> None:
        if self.quote_mode.get() != "auto":
            self.auto_refresh.set(False)
            return
        if self.auto_refresh.get():
            self.refresh_quotes(manual_trigger=False)
        else:
            self._cancel_scheduled_refresh()

    def _cancel_scheduled_refresh(self) -> None:
        if self.refresh_job is not None:
            self.root.after_cancel(self.refresh_job)
            self.refresh_job = None

    def _schedule_next_refresh(self) -> None:
        self._cancel_scheduled_refresh()
        if self.quote_mode.get() != "auto" or not self.auto_refresh.get():
            return
        try:
            interval_seconds = int(self.vars["refresh_interval"].get())
        except ValueError:
            interval_seconds = 30
        interval_seconds = max(interval_seconds, 5)
        self.refresh_job = self.root.after(
            interval_seconds * 1000,
            lambda: self.refresh_quotes(manual_trigger=False),
        )

    def reset_defaults(self) -> None:
        defaults = {
            "stock_code": "161226",
            "fund_code": "161226",
            "refresh_interval": "30",
            "entry_price": "1.0000",
            "current_stock_price": "1.0000",
            "current_fund_price": "1.0000",
            "position_amount": "1000",
            "holding_days": "10",
            "commission_rate": "0.0003",
            "subscription_fee": "0.0",
            "redemption_lt_7": "0.015",
            "redemption_7_30": "0.001",
            "redemption_gt_30": "0.0",
        }
        for key, value in defaults.items():
            self.vars[key].set(value)
        self.quote_mode.set("manual")
        self.switch_all_in.set(True)
        self.position_type.set("stock")
        self.auto_refresh.set(False)
        self.auto_evaluate.set(True)
        self.action_status.set("默认值已恢复，等待生成建议。")
        self._toggle_position_fields()
        self._toggle_quote_mode()
        self._write_result("默认值已恢复。")

    def _build_fees(self) -> FeeConfig:
        return FeeConfig(
            commission_rate=float(self.vars["commission_rate"].get()),
            subscription_fee=float(self.vars["subscription_fee"].get()),
            redemption_fee_lt_7=float(self.vars["redemption_lt_7"].get()),
            redemption_fee_7_to_30=float(self.vars["redemption_7_30"].get()),
            redemption_fee_gt_30=float(self.vars["redemption_gt_30"].get()),
        )

    def _write_result(self, content: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", content)
        self.result_text.configure(state="disabled")

    def refresh_quotes(self, manual_trigger: bool) -> None:
        if self.quote_mode.get() != "auto":
            return
        if self.is_fetching:
            if manual_trigger:
                messagebox.showinfo("提示", "上一轮行情抓取还没有完成，请稍等。")
            return

        stock_code = self.vars["stock_code"].get().strip()
        fund_code = self.vars["fund_code"].get().strip()
        if not stock_code or not fund_code:
            if manual_trigger:
                messagebox.showerror("输入错误", "实时抓取模式下需要填写股票代码和基金代码。")
            return

        self.is_fetching = True
        self.quote_status.set("正在抓取最新行情，请稍候...")
        worker = threading.Thread(
            target=self._fetch_quotes_worker,
            args=(stock_code, fund_code, manual_trigger),
            daemon=True,
        )
        worker.start()

    def _fetch_quotes_worker(
        self, stock_code: str, fund_code: str, manual_trigger: bool
    ) -> None:
        try:
            snapshot = fetch_market_snapshot(stock_code, fund_code)
        except Exception as exc:  # pragma: no cover - network/runtime path
            self.root.after(
                0,
                lambda: self._handle_quote_error(str(exc), manual_trigger),
            )
            return

        self.root.after(
            0,
            lambda: self._apply_snapshot(snapshot, manual_trigger),
        )

    def _apply_snapshot(self, snapshot: QuoteSnapshot, manual_trigger: bool) -> None:
        self.is_fetching = False
        self.vars["current_stock_price"].set(f"{snapshot.stock_price:.4f}")
        self.vars["current_fund_price"].set(f"{snapshot.fund_price:.4f}")

        stock_name = f"{snapshot.stock_name} " if snapshot.stock_name else ""
        fund_name = f"{snapshot.fund_name} " if snapshot.fund_name else ""
        self.quote_status.set(
            f"股票 {snapshot.stock_code} {stock_name}最新价 {snapshot.stock_price:.4f}；"
            f"基金 {snapshot.fund_code} {fund_name}{snapshot.fund_source} {snapshot.fund_price:.4f}。"
            f" 股票时间: {snapshot.stock_time or '未知'}，基金时间: {snapshot.fund_time or '未知'}。"
        )

        if self.auto_evaluate.get():
            self.generate_advice(show_dialog=False)
        elif manual_trigger:
            self._write_result("行情已更新。你可以继续调整参数后点击“生成建议”。")

        self._schedule_next_refresh()

    def _handle_quote_error(self, error_message: str, manual_trigger: bool) -> None:
        self.is_fetching = False
        self.quote_status.set(f"行情抓取失败：{error_message}")
        self._schedule_next_refresh()
        if manual_trigger:
            messagebox.showerror("行情抓取失败", error_message)

    def generate_advice(self, show_dialog: bool = True) -> bool:
        try:
            entry_price = float(self.vars["entry_price"].get())
            current_stock_price = float(self.vars["current_stock_price"].get())
            current_fund_price = float(self.vars["current_fund_price"].get())
            position_amount = float(self.vars["position_amount"].get())
            holding_days = int(self.vars["holding_days"].get() or "0")
            fees = self._build_fees()

            if self.position_type.get() == "stock":
                advice = advise_for_stock_position(
                    entry_stock_price=entry_price,
                    current_stock_price=current_stock_price,
                    current_fund_price=current_fund_price,
                    stock_held=position_amount,
                    fees=fees,
                    switch_all_in=self.switch_all_in.get(),
                )
                result = self._format_stock_advice(advice)
            else:
                advice = advise_for_fund_position(
                    entry_fund_price=entry_price,
                    current_fund_price=current_fund_price,
                    current_stock_price=current_stock_price,
                    fund_held=position_amount,
                    holding_days=holding_days,
                    fees=fees,
                    switch_all_in=self.switch_all_in.get(),
                )
                result = self._format_fund_advice(advice, holding_days, fees)

            self._write_result(result)
            self.action_status.set(
                f"建议已更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return True
        except ValueError as exc:
            self.action_status.set("输入有误，未能生成建议。")
            if show_dialog:
                messagebox.showerror("输入错误", str(exc))
            return False
        except Exception as exc:
            self.action_status.set("程序异常，未能生成建议。")
            self._write_result(f"生成建议失败：{exc}")
            if show_dialog:
                messagebox.showerror("程序异常", str(exc))
            return False

    def _format_stock_advice(self, advice: Advice) -> str:
        lines = [
            f"建议动作: {advice.action}",
            f"原因说明: {advice.reason}",
            f"若当前卖出股票，净收益估算: {advice.estimated_profit:.4f}",
            f"股票止盈安全边际价: {advice.safety_margin:.4f}",
        ]
        if advice.current_position_value is not None:
            lines.append(f"当前持仓按卖出后可回笼资金: {advice.current_position_value:.4f}")
        if advice.spread_value is not None:
            lines.append(f"按同等数量比较，切换到基金后的价差结余: {advice.spread_value:.4f}")
        if advice.convertible_units is not None:
            lines.append(f"若执行换仓，预计可获得基金份额: {advice.convertible_units:.4f}")
        lines.append("")
        lines.append("说明: 实时模式下可自动刷新当前价格；手动模式下可直接覆盖基金价格反复试算。")
        return "\n".join(lines)

    def _format_fund_advice(
        self, advice: Advice, holding_days: int, fees: FeeConfig
    ) -> str:
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
        lines.append("")
        lines.append("说明: 如果基金盘中估算值和你的观察不一致，可以直接手动覆盖基金价格再重新评估。")
        return "\n".join(lines)

    def _on_close(self) -> None:
        self._cancel_scheduled_refresh()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    TradingAdvisorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
