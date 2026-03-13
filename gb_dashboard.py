import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 (CSS) ---
st.set_page_config(page_title="hince SS_Master Dashboard", layout="wide")

def local_css():
    st.markdown("""
        <style>
        .main { background-color: #F8F9FA; }
        [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EEEEEE; }
        
        # --- hince 브랜드 스타일 미세 조정 ---
        .metric-card {
            background-color: #FFFFFF;
            padding: 20px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            border: 1px solid #F0F0F0;
            margin-bottom: 20px;
            text-align: center;
        }
        # KPI 카드의 메인 컬러를 hince 로고 색상(약 #A37F7D)으로 미세 조정
        .metric-label { color: #6B7280; font-size: 14px; font-weight: 500; margin-bottom: 8px; }
        .metric-value { color: #A37F7D; font-size: 26px; font-weight: 700; }
        
        h3 { color: #A37F7D !important; font-weight: 700 !important; margin-top: 10px !important; margin-bottom: 20px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 ---
def get_supabase_data():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        response = supabase.table("SS_Master").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Supabase 연결 실패: {e}")
        return pd.DataFrame()

df = get_supabase_data()

if df.empty:
    st.warning("데이터가 없거나 연결에 실패했습니다. Supabase 설정과 테이블 이름을 확인해주세요.")
    st.stop()

# --- 3. 데이터 전처리 ---
# 숫자형 변환
num_cols = ["출고_수량", "매출액", "FOC", "발주_수량"]
for col in num_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

# '월' 정렬 에러 방지 처리
if '월' in df.columns:
    df['month_idx'] = df['월'].astype(str).str.extract('(\d+)').fillna(0).astype(int)
    df = df.sort_values('month_idx')
else:
    df['month_idx'] = 0

# --- 4. 사이드바 필터 (로고 적용 부분 ⭐) ---
with st.sidebar:
    # --- hince 로고 이미지 삽입 (68번 줄 근처) ---
    # use_container_width=True로 설정하여 사이드바 너비에 맞춥니다.
    st.image("hince.png", use_container_width=True)
    
    st.markdown("---")
    
    # 연도 필터
    if '연도' in df.columns:
        years = sorted(df['연도'].unique(), reverse=True)
        selected_year = st.selectbox("📅 기준 연도", years)
    else:
        selected_year = None
    
    # 거래처 필터
    if 'CUSTOMER' in df.columns:
        customers = sorted(df['CUSTOMER'].unique())
        selected_customers = st.multiselect("🤝 거래처 선택", customers, default=customers)
    else:
        selected_customers = []

# 필터링 적용
mask = pd.Series(True, index=df.index)
if selected_year:
    mask &= (df['연도'] == selected_year)
if selected_customers:
    mask &= (df['CUSTOMER'].isin(selected_customers))

f_df = df[mask]

# --- 5. 메인 대시보드 UI ---
# 제목의 메인 컬러도 hince 로고 색상으로 미세 조정
st.markdown(f'<h1 style="color: #A37F7D;">📊 {selected_year if selected_year else ""} Sales Performance</h1>', unsafe_allow_html=True)
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
    st.markdown(f'<div class="metric-card"><div class="metric-label">거래처 수</div><div class="metric-value">{f_df["CUSTOMER"].nunique() if "CUSTOMER" in f_df.columns else 0}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# 그래프 섹션 1
col1, col2 = st.columns(2)

with col1:
    st.markdown("### ■ 거래처별 월별 Sell-Out 현황")
    # hince 브랜드 테마를 반영한 차트 색상 (약 #A37F7D 대시 보드 톤)
    hince_colors = px.colors.qualitative.Pastel + px.colors.qualitative.Safe
    fig_sellout = px.bar(f_df, x='월', y='출고_수량', color='CUSTOMER',
                        text_auto='.2s',
                        color_discrete_sequence=hince_colors)
    fig_sellout.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', barmode='stack', xaxis_title=None, height=450,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_sellout, use_container_width=True)

with col2:
    st.markdown("### ■ 품목별(Type) 주요 지표")
    if 'Type' in f_df.columns:
        trend_data = f_df.groupby(['월', 'month_idx', 'Type'])['출고_수량'].sum().reset_index().sort_values('month_idx')
        fig_trend = px.line(trend_data, x='월', y='출고_수량', color='Type', markers=True,
                            color_discrete_sequence=hince_colors)
        fig_trend.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=450,
            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Type 정보가 없습니다.")

# 그래프 섹션 2
st.markdown("---")
col_pie, col_table = st.columns([1, 1.5])

with col_pie:
    st.markdown("### ■ 거래처별 Sell-Out 비중")
    fig_pie = px.pie(f_df, values='출고_수량', names='CUSTOMER', hole=0.5,
                    color_discrete_sequence=hince_colors)
    fig_pie.update_traces(textinfo='percent+label')
    fig_pie.update_layout(showlegend=False, height=450, margin=dict(t=0, b=0, l=10, r=10))
    st.plotly_chart(fig_pie, use_container_width=True)

with col_table:
    st.markdown("### 📋 SS_Master 데이터 내역")
    cols_to_show = ['월', 'CUSTOMER', 'Type', '출고_수량', '매출액', 'FOC', '결제통화', 'Invoice#']
    available_cols = [c for c in cols_to_show if c in f_df.columns]
    view_df = f_df[available_cols].sort_values('월') # month_idx 기준으로 정렬된 상태 유지
    st.dataframe(view_df, use_container_width=True, hide_index=True, height=400)

# --- 6. 엑셀 다운로드 기능 ---
csv = f_df.to_csv(index=False).encode('utf-8-sig')
st.download_button(
    label="📥 필터링된 데이터 다운로드 (CSV)",
    data=csv,
    file_name=f'hince_dashboard_{selected_year}.csv',
    mime='text/csv',
)