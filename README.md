# 基金 / 股票轮动建议助手

这个项目现在同时提供两种形态：

- 桌面版：`Tkinter` 本地窗口，适合双击或打包成 `exe`
- 网页版：`Streamlit` Web 应用，适合部署到云端并通过网址访问

两者共用同一套策略逻辑和行情抓取逻辑。

## 运行方式

```powershell
python app.py
```

如果你想运行网页版：

```powershell
streamlit run streamlit_app.py
```

如果你想一键启动：

```powershell
.\start_trading_advisor.ps1
```

或者直接双击 [start_trading_advisor.bat](G:\Xiangyuming\stockfund\app\Trading\start_trading_advisor.bat)。

如果只是检查本地部署环境是否完整：

```powershell
.\start_trading_advisor.ps1 -CheckOnly
```

## 适合的使用方式

1. 如果你只想试算，保持“手动输入”模式，直接输入股票价、基金价、持仓与手续费参数。
2. 如果你想实时监测，切换到“实时抓取”模式，填写股票代码和基金代码，点击“抓取最新行情”或开启“自动监测”。
3. 如果你当前持有股票，输入股票参考建仓价、当前股票价、当前基金价和股票数量。
4. 如果你当前持有基金，输入基金参考建仓价、当前基金价、当前股票价、基金份额和持有天数。
5. 点击“生成建议”，查看程序给出的动作、原因、净收益估算、安全边际价和可换仓份额。

## 和原始脚本相比，这个版本修正了什么

- 不再依赖 `A/B/C` 多时点硬编码，而是改成“当前持仓状态”判断。
- 统一并修正了基金赎回费规则：`<7天`、`7-30天`、`>30天` 三段互斥。
- 避免了 `stock_C_price`、`profit`、`day_B` 这类只在某些分支定义、后续却直接使用的问题。
- 把“当前持仓平仓净收益”与“换仓后的可转换份额/价差结余”拆开计算，输出更直观。
- 新增实时抓取与自动刷新，可用盘中估算净值做连续监测；如果你更相信自己的观察，也可以手动覆盖基金价格再试算。
- 新增 `Streamlit` 网页入口 [streamlit_app.py](G:\Xiangyuming\stockfund\app\Trading\streamlit_app.py)，便于部署到 Streamlit Community Cloud 或 Render。

## 云端部署

最简单的方案是部署到 Streamlit Community Cloud：

1. 把当前项目推到 GitHub。
2. 登录 Streamlit Community Cloud。
3. 选择仓库后，将入口文件设置为 `streamlit_app.py`。
4. 平台会根据 [requirements.txt](G:\Xiangyuming\stockfund\app\Trading\requirements.txt) 自动安装依赖并生成网址。

如果你在本地先验证网页版本，直接运行：

```powershell
streamlit run streamlit_app.py
```

## 提醒

这个工具是按你原始思路整理出来的“规则型建议器”，适合做辅助判断，不应替代完整的投资风控或实盘交易决策。
