import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from supabase import create_client, Client

# --- 1. 페이지 설정 및 디자인 (CSS) ---
st.set_page_config(page_title="Donezo Sales Dashboard", layout="wide")

def local_css():
    st.markdown("""
        <style>
        .main { background-color: #F8F9FA; }
        [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EEEEEE; }
        .metric-card {
            background-color: #FFFFFF;
            padding: 20px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            border: 1px solid #F0F0F0;
            margin-bottom: 20px;
        }
        .metric-label { color: #6B7280; font-size: 14px; font-weight: 500; margin-bottom: 8px; }
        .metric-value { color: #1B4332; font-size: 28px; font-weight: 700; }
        .metric-delta { font-size: 12px; margin-top: 5px; }
        h1, h2, h3 { color: #1B4332 !important; font-weight: 700 !important; }
        .stButton>button {
            background-color: #1B4332;
            color: white;
            border-radius: 10px;
            border: none;
            padding: 10px 24px;
        }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. 데이터 로드 로직 ---

def get_supabase_data():
    # ★ 본인의 정보로 채워주세요 ★
    url = "https://ijmfubiiqwmwibptqwja.supabase.co" 
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlqbWZ1YmlpcXdtd2licHRxd2phIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI3NzM0MjcsImV4cCI6MjA4ODM0OTQyN30.qnM5Gy6DXrDWe1LKDDHklLmg15MpzD6TKj8RyCOqjaw"
    
    try:
        supabase: Client = create_client(url, key)
        # 테이블 이름이 '출고 RAW'인 경우
        response = supabase.table("출고_RAW").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Supabase 연결 에러: {e}")
        return pd.DataFrame()

# ★ 중요: Mock Data 대신 실제 Supabase 데이터를 불러오도록 설정 ★
df = get_supabase_data()
# 데이터가 비어있지 않은지 확인 후 전처리
if not df.empty:
    # 사용자님이 새로 바꾼 컬럼 리스트에 맞게 수정
    date_col = "매출인식_기준일(출고일)"             # 2번 항목
    sales_col = "매출취합용_공급가액(원화기준)"      # 10번 항목
    qty_col = "제품판매수량"                        # 8번 항목
    channel_col = "채널명"                          # 3번 항목
    foc_col = "FOC"                                # 23번 항목

    # 날짜 변환 (이제 에러가 나지 않을 겁니다!)
    df[date_col] = pd.to_datetime(df[date_col])
    df['Month'] = df[date_col].dt.strftime('%Y-%m')
    
    # 숫자형 변환 (계산을 위해 필수)
    df[sales_col] = pd.to_numeric(df[sales_col], errors='coerce').fillna(0)
    df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
    df[foc_col] = pd.to_numeric(df[foc_col], errors='coerce').fillna(0)
else:
    st.warning("데이터를 불러오지 못했습니다. Supabase 설정과 테이블 이름을 확인해주세요.")
    st.stop()

# --- 3. 사이드바 구성 ---
with st.sidebar:
    st.title("Donezo")
    st.markdown("---")
    menu = ["Dashboard", "Tasks", "Analytics"]
    st.selectbox("Menu", menu)
    
    st.markdown("### Filter")
    # '채널명' 컬럼이 실제 데이터에 있는지 확인하세요.
    channel_col = '채널명'
    selected_channel = st.multiselect("채널 선택", df[channel_col].unique(), default=df[channel_col].unique())

filtered_df = df[df[channel_col].isin(selected_channel)]

# --- 4. 메인 대시보드 UI ---
st.title("Dashboard")

# KPI 계산 (컬럼명은 사용자님의 DB에 맞춰져 있습니다)
# --- 4. KPI 계산 (기존 99번 줄 근처) ---
# 문자열을 직접 쓰지 말고, 위에서 선언한 변수명을 그대로 사용합니다.

monthly_agg = filtered_df.groupby('Month').agg({
    sales_col: 'sum',  # '매출취합용_공급가액(원화기준)' 대신 변수 사용
    qty_col: 'sum',    # '제품판매수량' 대신 변수 사용
    foc_col: 'sum'      # 'FOC' 대신 변수 사용 (아까 리스트 23번)
}).reset_index()

# 최근 달 데이터 추출
curr = monthly_agg.iloc[-1]

col1, col2, col3, col4 = st.columns(4)

def create_card(column, label, value, is_currency=False):
    fmt_value = f"₩{value:,.0f}" if is_currency else f"{value:,}"
    with column:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{fmt_value}</div>
                <div class="metric-delta" style="color: #2D6A4F;">↗ 분석 중</div>
            </div>
        """, unsafe_allow_html=True)

# --- 5. KPI 카드 출력 ---
col1, col2, col3, col4 = st.columns(4)

def create_card(column, label, value, is_currency=False):
    fmt_value = f"₩{value:,.0f}" if is_currency else f"{value:,.0f}"
    with column:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{fmt_value}</div>
                <div class="metric-delta" style="color: #2D6A4F;">↗ 실시간 데이터</div>
            </div>
        """, unsafe_allow_html=True)

# 여기서 ['매출취합용 공급가액(원화기준)'] 대신 변수 sales_col을 사용해야 합니다!
create_card(col1, "Monthly Revenue", curr[sales_col], True)
create_card(col2, "Monthly Quantity", curr[qty_col])
create_card(col3, "FOC Quantity", curr[foc_col])
create_card(col4, "Active Channels", filtered_df[channel_col].nunique())

# --- 6. 차트 구역 ---
st.markdown("### Monthly Trend")
fig = make_subplots(specs=[[{"secondary_y": True}]])

# y 값들을 모두 위에서 정의한 변수명으로 교체
fig.add_trace(go.Bar(x=monthly_agg['Month'], y=monthly_agg[sales_col], name="Revenue", marker_color='#1B4332'), secondary_y=False)
fig.add_trace(go.Scatter(x=monthly_agg['Month'], y=monthly_agg[qty_col], name="Quantity", line=dict(color='#74C69D', width=4)), secondary_y=True)

fig.update_layout(
    plot_bgcolor='rgba(0,0,0,0)', 
    paper_bgcolor='rgba(0,0,0,0)', 
    height=400,
    margin=dict(l=20, r=20, t=20, b=20)
)
st.plotly_chart(fig, use_container_width=True)

# --- 7. 하단 데이터 ---
st.markdown("### Channel Performance")
# 여기도 sales_col 변수 사용
channel_rev = filtered_df.groupby(channel_col)[sales_col].sum().sort_values()
st.bar_chart(channel_rev)

st.markdown("### Recent Data (Top 10)")
st.dataframe(filtered_df.tail(10), use_container_width=True)