import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestClassifier
import datetime
import time
import warnings

warnings.filterwarnings('ignore')

# ================= 1. 页面设置 =================
st.set_page_config(page_title="AI 全量量化终端", layout="wide")
st.title("🚀 AI 全量量化猎手 & 自选股监控")

# ================= 2. 获取大盘环境 =================
@st.cache_data(ttl=3600)
def get_market_status():
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df['MA20'] = df['close'].rolling(20).mean()
        df['MA60'] = df['close'].rolling(60).mean()
        latest = df.iloc[-1]
        is_bull = latest['MA20'] > latest['MA60']
        return is_bull, latest['close']
    except:
        return True, 3000.0

# ================= 3. 安全获取全市场数据 (带重试) =================
def get_spot_data_safe():
    st.info("⏳ 第一步：正在抓取全市场实时行情...")
    for i in range(3):
        try:
            # 尝试获取东财数据
            spot_df = ak.stock_zh_a_spot_em()
            if spot_df is not None and not spot_df.empty:
                return spot_df
        except Exception as e:
            time.sleep(2)
    return None

# ================= 4. 核心 AI 分析单只股票 =================
@st.cache_data(ttl=3600)
def analyze_stock_code(code, name):
    try:
        symbol = f"sh{code}" if code.startswith('6') else f"sz{code}"
        today = datetime.datetime.now().strftime("%Y%m%d")
        
        # 获取历史数据
        df = None
        for _ in range(2):
            try:
                df = ak.stock_zh_a_daily(symbol=symbol, start_date="20200101", end_date=today, adjust="qfq")
                if df is not None and not df.empty:
                    break
            except:
                time.sleep(1)
                
        if df is None or df.empty or len(df) < 200:
            return None
            
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 计算特征
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
        
        features = ['MA5', 'MA20', 'DIF', 'DEA', 'MACD', 'RSI']
        X = ml_df[features]
        y = ml_df['Target']
        
        split_idx = int(len(X) * 0.8)
        model = RandomForestClassifier(n_estimators=30, max_depth=3)
        model.fit(X[:split_idx], y[:split_idx])
        
        latest_X = X.tail(1)
        prob = model.predict_proba(latest_X)[0][1]
        
        latest_row = df.iloc[-1]
        tech_list = []
        if latest_row['MA5'] > latest_row['MA20']:
            tech_list.append("均线多头")
        else:
            tech_list.append("均线空头")
        if latest_row['MACD'] > 0:
            tech_list.append("MACD红柱")
        else:
            tech_list.append("MACD绿柱")
            
        tech_text = "，".join(tech_list)
        
        return {
            "代码": code,
            "名称": name,
            "最新价": df['close'].iloc[-1],
            "AI看涨(%)": round(prob * 100, 2),
            "技术面": tech_text,
            "df": df
        }
    except Exception:
        return None

# ================= 5. 主逻辑区 =================
st.sidebar.header("⚙️ 扫描设置")
scan_all_btn = st.sidebar.按钮("🔥 扫描全市场 (耗时较长)", use_container_width=真)

# 获取自选股列表 (备用)
@st.cache_data(ttl=86400)
def get_stock_dict():
    try:
        df = ak.stock_info_a_code_name()
        return df
    except:
        return pd.DataFrame()

if scan_all_btn:
    # 1. 大盘
    is_bull, idx_price = get_market_status()
    if is_bull:
        st.success(f"🌤️ 大盘环境：多头趋势 (上证 {idx_price:.2f})")
    否则:
        st.error(f"⛈️ 大盘警报：空头趋势！建议空仓！")

    # 2. 全市场行情
    spot_df = get_spot_data_safe()
    如果 spot_df 是 None:
        st.error("❌ 获取全市场行情失败，东财接口完全被限流。请稍后再试，或切换网络（如手机热点）。")
        st.stop()
        
    # 3. 粗筛 (选涨幅>3% 且 价格<100的)
    spot_df = spot_df.dropna(subset=['涨跌幅', '最新价'])
    filtered_df = spot_df[(spot_df['涨跌幅'] > 3) & (spot_df['最新价'] < 100)]
    filtered_df = filtered_df.sort_values(by='涨跌幅', ascending=False).head(20) # 取前20只
    
    st.markdown(f"### 🏆 AI 精选 TOP 20 (基于今天涨幅榜粗筛)")
    
    结果 = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, row in filtered_df.iterrows():
        code = row['代码']
        name = row['名称']
        status_text.text(f"AI 正在深度分析: {name} ({code})...")
        
        res = analyze_stock_code(code, name)
        如果 res:
结果。追加(res)
        进度条。进度((len(结果)) / 20)
        
    进度条。清空()
    status_text.empty()
    
    如果 结果:
        summary_df = pd.DataFrame(results).sort_values(by="AI看涨(%)", ascending=False)
        st.dataframe(summary_df[["代码", "名称", "最新价", "AI看涨(%)", "技术面"]], hide_index=True)
        
        # 画个图
        st.markdown("### 🔍 最强王者")
        top_stock = results[0]
[-60:], 开盘价=顶级股票['df']['开盘价'].iloc[-60:], 收盘价=顶级股票['df']['收盘价'].iloc[-60:], 最高价=顶级股票['df']['最高价'].iloc[-60:], 最低价=顶级股票['df']['最低价'
        st.plotly_chart(fig, use_container_width=True)
    否则:
        st.错误("未能成功分析出任何股票，请检查网络。")
