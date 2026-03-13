import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 Donezo 스타일 (CSS) ---
st.set_page_config(page_title="hince SS_Master Dashboard", layout="wide")

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
            text-align: center;
        }
        .metric-label { color: #6B7280; font-size: 14px; font-weight: 500; margin-bottom: 8px; }
        .metric-value { color: #1B4332; font-size: 26px; font-weight: 700; }
        h3 { color: #1B4332 !important; font-weight: 700 !important; margin-top: 10px !important; margin-bottom: 20px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 ---
def get_supabase_data():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"] 
    try:
        supabase: Client = create_client(url, key)
        # 테이블명을 SS_Master로 지정 (실제 DB 테이블 이름과 대소문자까지 맞춰주세요)
        response = supabase.table("SS_Master").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Supabase 연결 실패: {e}")
        return pd.DataFrame()

df = get_supabase_data()

if df.empty:
    st.warning("데이터가 없거나 연결에 실패했습니다.")
    st.stop()

# --- 3. 데이터 전처리 ---
# 숫자형 변환
num_cols = ["출고_수량", "매출액", "FOC", "발주_수량"]
for col in num_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

# '월' 정렬 (1월, 2월... 순서대로 보이게 처리)
df['month_idx'] = df['월'].str.extract('(\d+)').astype(int)
df = df.sort_values('month_idx')

# --- 4. 사이드바 필터 ---
with st.sidebar:
    st.title("Donezo Admin")
    st.markdown("---")
    
    # 연도 필터
    years = sorted(df['연도'].unique(), reverse=True)
    selected_year = st.selectbox("📅 기준 연도", years)
    
    # 거래처 필터
    customers = sorted(df['CUSTOMER'].unique())
    selected_customers = st.multiselect("🤝 거래처 선택", customers, default=customers)

# 필터링 적용
f_df = df[(df['연도'] == selected_year) & (df['CUSTOMER'].isin(selected_customers))]

# --- 5. 메인 대시보드 UI ---
st.title(f"📊 {selected_year} Sales Performance")
st.caption("SS_Master Real-time Analytics Dashboard")

# 상단 KPI 카드
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">총 출고 수량</div><div class="metric-value">{f_df["출고_수량"].sum():,.0f} EA</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">총 매출액</div><div class="metric-value">₩{f_df["매출액"].sum():,.0f}</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">총 FOC</div><div class="metric-value">{f_df["FOC"].sum():,.0f} EA</div></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="metric-card"><div class="metric-label">거래처 수</div><div class="metric-value">{f_df["CUSTOMER"].nunique()}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# 그래프 섹션 1 (Sell-Out 현황 & 품목별 트렌드)
col1, col2 = st.columns(2)

with col1:
    st.markdown("### ■ 거래처별 월별 Sell-Out 현황")
    # Stacked Bar Chart
    fig_sellout = px.bar(f_df, x='월', y='출고_수량', color='CUSTOMER',
                        text_auto='.2s',
                        color_discrete_sequence=px.colors.qualitative.Pastel)
    fig_sellout.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', barmode='stack', xaxis_title=None, height=450,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_sellout, use_container_width=True)

with col2:
    st.markdown("### ■ 품목별(Type) 주요 지표")
    # 품목 데이터 대신 'Type'을 기준으로 트렌드 시각화
    trend_data = f_df.groupby(['월', 'Type'])['출고_수량'].sum().reset_index()
    fig_trend = px.line(trend_data, x='월', y='출고_수량', color='Type', markers=True,
                       color_discrete_sequence=px.colors.qualitative.Safe)
    fig_trend.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=450,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# 그래프 섹션 2 (거래처별 비중 & 상세 테이블)
st.markdown("---")
col_pie, col_table = st.columns([1, 1.5])

with col_pie:
    st.markdown("### ■ 거래처별 Sell-Out 비중")
    # Donut Chart
    fig_pie = px.pie(f_df, values='출고_수량', names='CUSTOMER', hole=0.5,
                    color_discrete_sequence=px.colors.qualitative.Set3)
    fig_pie.update_traces(textinfo='percent+label')
    fig_pie.update_layout(showlegend=False, height=450, margin=dict(t=0, b=0, l=10, r=10))
    st.plotly_chart(fig_pie, use_container_width=True)

with col_table:
    st.markdown("### 📋 SS_Master 데이터 내역")
    # 주요 컬럼 위주로 보여주는 데이터 프레임
    view_df = f_df[['월', 'CUSTOMER', 'Type', '출고_수량', '매출액', 'FOC', '결제통화', 'Invoice#']].sort_values('month_idx')
    st.dataframe(view_df, use_container_width=True, hide_index=True, height=400)

# --- 6. 엑셀 다운로드 기능 ---
csv = f_df.to_csv(index=False).encode('utf-8-sig')
st.download_button(
    label="📥 필터링된 데이터 다운로드 (CSV)",
    data=csv,
    file_name=f'hince_dashboard_{selected_year}.csv',
    mime='text/csv',
)