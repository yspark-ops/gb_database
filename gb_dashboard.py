import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 (CSS) ---
st.set_page_config(page_title="hince Integrated Dashboard", layout="wide")

def local_css():
    st.markdown("""
        <style>
        .main { background-color: #F8F9FA; }
        [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EEEEEE; }
        .metric-card {
            background-color: #FFFFFF;
            padding: 15px;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            border: 1px solid #F0F0F0;
            margin-bottom: 10px;
            text-align: center;
        }
        .metric-label { color: #6B7280; font-size: 13px; font-weight: 500; margin-bottom: 5px; }
        .metric-value { color: #A37F7D; font-size: 22px; font-weight: 700; }
        h2 { color: #A37F7D !important; font-size: 22px !important; border-left: 5px solid #A37F7D; padding-left: 10px; margin-bottom: 20px; }
        h3 { color: #A37F7D !important; font-size: 16px !important; font-weight: 700 !important; margin-top: 5px !important; margin-bottom: 15px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 ---
def get_supabase_data(table_name):
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"{table_name} 데이터 로드 실패: {e}")
        return pd.DataFrame()

# 데이터 로드 (두 개 시트 모두)
df_raw = get_supabase_data("출고_RAW")
df_master = get_supabase_data("SS_Master")

if df_raw.empty or df_master.empty:
    st.warning("데이터를 불러오는 중입니다... 테이블 이름을 확인해주세요.")
    st.stop()

# --- 3. 데이터 전처리 ---
# 3-1. 출고_RAW (Sell-In) 전처리
# 컬럼명에 줄바꿈이나 공백이 있을 수 있으므로 매핑 필요
RAW_REVENUE = "매출취합용\n공급가액\n(원화기준)" if "매출취합용\n공급가액\n(원화기준)" in df_raw.columns else "매출취합용공급가액(원화기준)"
RAW_QTY = "제품 \n판매수량" if "제품 \n판매수량" in df_raw.columns else "제품판매수량"

for col in [RAW_REVENUE, RAW_QTY]:
    if col in df_raw.columns:
        df_raw[col] = pd.to_numeric(df_raw[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

if '월' in df_raw.columns:
    df_raw['month_idx'] = df_raw['월'].astype(str).str.extract('(\d+)').fillna(0).astype(int)
    df_raw = df_raw.sort_values('month_idx')

# 3-2. SS_Master (Sell-Out) 전처리
num_cols_master = ["출고_수량", "매출액", "FOC"]
for col in num_cols_master:
    if col in df_master.columns:
        df_master[col] = pd.to_numeric(df_master[col], errors='coerce').fillna(0)

if '월' in df_master.columns:
    df_master['month_idx'] = df_master['월'].astype(str).str.extract('(\d+)').fillna(0).astype(int)
    df_master = df_master.sort_values('month_idx')

# --- 4. 사이드바 필터 ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    years = sorted(df_raw['Y'].unique(), reverse=True) if 'Y' in df_raw.columns else [2025]
    selected_year = st.selectbox("📅 기준 연도", years)
    
    # 두 데이터프레임 모두에 적용
    f_raw = df_raw[df_raw['Y'] == selected_year] if 'Y' in df_raw.columns else df_raw
    f_master = df_master[df_master['연도'] == selected_year] if '연도' in df_master.columns else df_master

# --- 5. 메인 대시보드 UI ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 28px;">📊 {selected_year} hince Integrated Performance</h1>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 상단 섹션: ■ Sell-In 현황 (출고_RAW 기반)
# ---------------------------------------------------------
st.markdown("## 🟦 Sell-In Analysis (본사 → 거래처)")

# 상단 KPI (Sell-In)
k1, k2, k3 = st.columns(3)
with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">총 Sell-In 매출액</div><div class="metric-value">₩{f_raw[RAW_REVENUE].sum():,.0f}</div></div>', unsafe_allow_html=True)
with k2: st.markdown(f'<div class="metric-card"><div class="metric-label">총 Sell-In 수량</div><div class="metric-value">{f_raw[RAW_QTY].sum():,.0f} EA</div></div>', unsafe_allow_html=True)
with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">활성 채널 수</div><div class="metric-value">{f_raw["채널명"].nunique()} 개</div></div>', unsafe_allow_html=True)

# Sell-In 그래프 3개 한 줄 배치
si1, si2, si3 = st.columns(3)
hince_colors = px.colors.qualitative.Pastel + px.colors.qualitative.Safe

with si1:
    st.markdown("### ■ 월별 Sell-In 현황")
    fig_si_monthly = px.bar(f_raw.groupby('월')[RAW_REVENUE].sum().reset_index(), x='월', y=RAW_REVENUE, color_discrete_sequence=['#A37F7D'])
    fig_si_monthly.update_layout(plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=300, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig_si_monthly, use_container_width=True)

with si2:
    st.markdown("### ■ 품목별 주요 지표 (대카테고리)")
    if '대' in f_raw.columns:
        fig_si_cat = px.bar(f_raw.groupby('대')[RAW_QTY].sum().reset_index(), x='대', y=RAW_QTY, color_discrete_sequence=['#D4A5A5'])
        fig_si_cat.update_layout(plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=300, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_si_cat, use_container_width=True)

with si3:
    st.markdown("### ■ 카테고리별 매출 비중")
    if '중' in f_raw.columns:
        fig_si_pie = px.pie(f_raw, values=RAW_REVENUE, names='중', hole=0.4, color_discrete_sequence=hince_colors)
        fig_si_pie.update_traces(textinfo='percent')
        fig_si_pie.update_layout(showlegend=True, height=300, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5, font=dict(size=10)))
        st.plotly_chart(fig_si_pie, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 하단 섹션: ■ Sell-Out 현황 (SS_Master 기반)
# ---------------------------------------------------------
st.markdown("## 🟧 Sell-Out Analysis (거래처 → 소비자)")

so1, so2, so3 = st.columns(3)

with so1:
    st.markdown("### ■ 거래처별 월별 현황")
    fig_so_monthly = px.bar(f_master, x='월', y='출고_수량', color='CUSTOMER', color_discrete_sequence=hince_colors)
    fig_so_monthly.update_layout(plot_bgcolor='rgba(0,0,0,0)', barmode='stack', xaxis_title=None, height=300, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, font=dict(size=10)))
    st.plotly_chart(fig_so_monthly, use_container_width=True)

with so2:
    st.markdown("### ■ 품목별(Type) 트렌드")
    if 'Type' in f_master.columns:
        trend_data = f_master.groupby(['월', 'month_idx', 'Type'])['출고_수량'].sum().reset_index().sort_values('month_idx')
        fig_so_trend = px.line(trend_data, x='월', y='출고_수량', color='Type', markers=True, color_discrete_sequence=hince_colors)
        fig_so_trend.update_layout(plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=300, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, font=dict(size=10)))
        st.plotly_chart(fig_so_trend, use_container_width=True)

with so3:
    st.markdown("### ■ 거래처별 비중")
    fig_so_pie = px.pie(f_master, values='출고_수량', names='CUSTOMER', hole=0.4, color_discrete_sequence=hince_colors)
    fig_so_pie.update_traces(textinfo='percent')
    fig_so_pie.update_layout(showlegend=True, height=300, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5, font=dict(size=10)))
    st.plotly_chart(fig_so_pie, use_container_width=True)

st.markdown("---")

# 하단 상세 데이터 내역 (출고_RAW 기준)
st.markdown("### 📋 출고_RAW 상세 내역 (Sell-In)")
raw_cols_to_show = ['월', '채널명', '제품명', '대', '중', RAW_QTY, RAW_REVENUE, 'Y']
raw_available = [c for c in raw_cols_to_show if c in f_raw.columns]
st.dataframe(f_raw[raw_available].sort_values('month_idx'), use_container_width=True, hide_index=True, height=250)