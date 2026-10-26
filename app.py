import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.ensemble import RandomForestClassifier
import datetime
import time
import warnings

warnings.filterwarnings('ignore')

# ================= 1. 页面基础配置 (暗黑主题) =================
st.set_page_config(page_title="AI 智能量化终端", page_icon="🏦", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #2e334d; }
    h1, h2, h3 { color: #00d2ff !important; }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stButton>button:hover { background-color: #ff2b2b; }
</style>
""", unsafe_allow_html=True)

st.title("🏦 AI 智能量化预测与交易终端")
st.markdown("---")

# ================= 2. 模拟账户初始化 =================
if 'cash' not in st.session_state:
    st.session_state.cash = 100000.0
if 'positions' not in st.session_state:
    st.session_state.positions = {} # 格式: { '600519': {'name': '茅台', 'shares': 100, 'cost': 1500.0} }
if 'trade_log' not in st.session_state:
    st.session_state.trade_log = []

# ================= 3. 数据缓存与获取 =================
@st.cache_data(ttl=86400)
def get_stock_dict():
    try:
        df = ak.stock_info_a_code_name()
        df['display'] = df['code'] + " - " + df['name']
        return df
    except:
        return pd.DataFrame([{"code": "600519", "name": "贵州茅台", "display": "600519 - 贵州茅台"}])

stock_df = get_stock_dict()
stock_options = stock_df['display'].tolist()

@st.cache_data(ttl=3600)
def get_stock_data(stock_code):
    symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
    today = datetime.datetime.now().strftime("%Y%m%d")
    df = None
    for _ in range(3):
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date="20140101", end_date=today, adjust="qfq")
            if df is not None and not df.empty: break
        except: time.sleep(1)
    if df is not None:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df
    return None

@st.cache_data(ttl=3600)
def get_market_status():
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df['MA20'] = df['close'].rolling(20).mean()
        df['MA60'] = df['close'].rolling(60).mean()
        return df['MA20'].iloc[-1] > df['MA60'].iloc[-1]
    except: return True

# ================= 4. 侧边栏控制台 =================
with st.sidebar:
    st.header("🎯 全局控制台")
    
    # 搜索与选择
    selected_stock = st.selectbox("🔍 搜索并选择股票", options=stock_options, index=0)
    stock_code = selected_stock.split(" - ")[0]
    stock_name = selected_stock.split(" - ")[1]
    
    # 时间跨度
    time_range = st.select_slider("📅 K线时间跨度", options=["30天", "3个月", "半年", "1年", "3年", "5年", "10年"], value="1年")
    range_days = {"30天": 30, "3个月": 90, "半年": 120, "1年": 250, "3年": 750, "5年": 1250, "10年": 2500}[time_range]
    
    st.markdown("---")
    st.subheader("💼 我的账户")
    st.metric("可用资金", f"¥{st.session_state.cash:,.2f}")
    
    # 计算总资产
    total_asset = st.session_state.cash
    for code, pos in st.session_state.positions.items():
        total_asset += pos['shares'] * pos['cost'] # 粗略计算，暂按成本价
    st.metric("总资产 (预估)", f"¥{total_asset:,.2f}")

# ================= 5. 主界面逻辑 =================
is_bull = get_market_status()
if is_bull:
    st.success("🌤️ **大盘环境监控**：上证指数多头趋势，适合进行交易。")
else:
    st.error("⛈️ **大盘环境监控**：大盘处于空头趋势，请降低仓位，注意风险！")

# 获取数据
with st.spinner("AI 正在拉取数据并进行深度计算..."):
    df = get_stock_data(stock_code)

if df is not None:
    # 特征计算
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD'] = 2 * (df['DIF'] - df['DEA'])
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + gain / loss))
    df['Target'] = (df['close'].shift(-1) > df['close']).astype(int)
    
    ml_df = df.dropna().copy()
    
    # AI 预测
    if len(ml_df) > 100:
        features = ['MA5', 'MA20', 'DIF', 'DEA', 'MACD', 'RSI']
        X = ml_df[features]
        y = ml_df['Target']
        model = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42)
        model.fit(X, y)
        prob = model.predict_proba(X.tail(1))[0][1]
    else:
        prob = 0.5
        
    latest_price = df['close'].iloc[-1]
    pct_chg = df['close'].pct_change().iloc[-1] * 100
    
    # 顶部数据面板
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(f"{stock_name} 最新价", f"¥{latest_price:.2f}", f"{pct_chg:.2f}%", delta_color="inverse" if pct_chg<0 else "normal")
    
    if prob > 0.55:
        c2.metric("AI 明日预测", "上涨 📈", f"胜率 {prob*100:.1f}%", delta_color="normal")
    elif prob < 0.45:
        c2.metric("AI 明日预测", "下跌 📉", f"胜率 {(1-prob)*100:.1f}%", delta_color="inverse")
    else:
        c2.metric("AI 明日预测", "震荡 ⚖️", f"观望", delta_color="off")
        
    c3.metric("MACD状态", "红柱放大" if df['MACD'].iloc[-1]>0 else "绿柱缩短")
    c4.metric("RSI状态", f"{df['RSI'].iloc[-1]:.1f}", "超买" if df['RSI'].iloc[-1]>70 else ("超卖" if df['RSI'].iloc[-1]<30 else "中性"))
    
    # 模拟交易状态
    held = st.session_state.positions.get(stock_code)
    if held:
        c5.metric("当前持仓", f"{held['shares']}股", f"成本 ¥{held['cost']:.2f}")
    else:
        c5.metric("当前持仓", "未持仓")

    # 页面 Tabs
    tab1, tab2, tab3 = st.tabs(["📊 行情分析与图表", "💼 模拟实盘交易", "📜 历史交易流水"])
    
    # ------ Tab 1: 图表 ------
    with tab1:
        plot_df = df.iloc[-range_days:] if len(df) > range_days else df
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
        
        # K线
        fig.add_trace(go.Candlestick(x=plot_df.index, open=plot_df['open'], high=plot_df['high'], low=plot_df['low'], close=plot_df['close'], increasing_line_color='red', decreasing_line_color='green', name='K线'), row=1, col=1)
        # 均线
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA5'], line=dict(color='blue', width=1), name='MA5'), row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['MA20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
        # 成交量
        colors = ['red' if c >= o else 'green' for c, o in zip(plot_df['close'], plot_df['open'])]
        fig.add_trace(go.Bar(x=plot_df.index, y=plot_df['volume'], marker_color=colors, name='成交量'), row=2, col=1)
        
        # 强制X轴分为10段
        fig.update_xaxes(nticks=10, tickangle=-45)
        fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # ------ Tab 2: 交易 ------
    with tab2:
        st.subheader("💼 模拟交易面板")
        col_buy, col_sell = st.columns(2)
        
        with col_buy:
            buy_shares = st.number_input("买入数量 (股)", min_value=100, step=100, value=100, key="buy_input")
            buy_cost = buy_shares * latest_price
            st.write(f"预计花费: **¥{buy_cost:,.2f}**")
            if st.button("🔴 确认买入", key="btn_buy"):
                if not is_bull:
                    st.error("🚨 风控拦截：大盘处于空头趋势，禁止开新仓！")
                elif st.session_state.cash >= buy_cost:
                    st.session_state.cash -= buy_cost
                    if stock_code in st.session_state.positions:
                        pos = st.session_state.positions[stock_code]
                        total_cost = pos['cost'] * pos['shares'] + buy_cost
                        pos['shares'] += buy_shares
                        pos['cost'] = total_cost / pos['shares']
                    else:
                        st.session_state.positions[stock_code] = {'name': stock_name, 'shares': buy_shares, 'cost': latest_price}
                    
                    log = f"🔴 {datetime.datetime.now().strftime('%H:%M:%S')} 买入 {stock_name} {buy_shares}股 @ ¥{latest_price:.2f}"
                    st.session_state.trade_log.insert(0, log)
                    st.success("✅ 买入成功！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 资金不足！")

        with col_sell:
            sell_shares = st.number_input("卖出数量 (股)", min_value=0, step=100, value=0, key="sell_input")
            if st.button("🟢 确认卖出", key="btn_sell"):
                if stock_code in st.session_state.positions and st.session_state.positions[stock_code]['shares'] >= sell_shares > 0:
                    revenue = sell_shares * latest_price
                    st.session_state.cash += revenue
                    st.session_state.positions[stock_code]['shares'] -= sell_shares
                    
                    if st.session_state.positions[stock_code]['shares'] == 0:
                        del st.session_state.positions[stock_code]
                        
                    log = f"🟢 {datetime.datetime.now().strftime('%H:%M:%S')} 卖出 {stock_name} {sell_shares}股 @ ¥{latest_price:.2f}"
                    st.session_state.trade_log.insert(0, log)
                    st.success("✅ 卖出成功！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 持仓不足！")

    # ------ Tab 3: 流水 ------
    with tab3:
        st.subheader("📜 实时交易流水")
        if not st.session_state.trade_log:
            st.info("暂无交易记录，请在“模拟实盘交易”面板进行操作。")
        else:
            for log in st.session_state.trade_log:
                st.text(log)
else:
    st.error("数据加载失败，请刷新重试。")
