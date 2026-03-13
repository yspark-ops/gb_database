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
        h2 { color: #A37F7D !important; font-size: 20px !important; border-left: 5px solid #A37F7D; padding-left: 10px; margin-top: 30px; margin-bottom: 20px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-size: 15px !important; font-weight: 700 !important; margin-top: 5px !important; margin-bottom: 15px !important; }
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

df_raw = get_supabase_data("출고_RAW")
df_master = get_supabase_data("SS_Master")

if df_raw.empty or df_master.empty:
    st.warning("데이터를 불러오는 중입니다... 테이블 이름을 확인해주세요.")
    st.stop()

# --- 3. 데이터 전처리 (제공해주신 신규 컬럼명 적용) ---

# 3-1. 출고_RAW (Sell-In) 전처리
raw_num_cols = ["제품판매수량", "매출취합용_공급가액(원화기준)", "최종_판매금액"]
for col in raw_num_cols:
    if col in df_raw.columns:
        df_raw[col] = pd.to_numeric(df_raw[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

if '월' in df_raw.columns:
    df_raw['month_idx'] = df_raw['월'].astype(str).str.extract('(\d+)').fillna(0).astype(int)
    df_raw = df_raw.sort_values('month_idx')

# 3-2. SS_Master (Sell-Out) 전처리
master_num_cols = ["출고_수량", "매출액", "FOC"]
for col in master_num_cols:
    if col in df_master.columns:
        df_master[col] = pd.to_numeric(df_master[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

if '월' in df_master.columns:
    df_master['month_idx'] = df_master['월'].astype(str).str.extract('(\d+)').fillna(0).astype(int)
    df_master = df_master.sort_values('month_idx')

# --- 4. 사이드바 필터 ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    # 연도 선택 (출고_RAW의 'Y' 컬럼 기준)
    years = sorted(df_raw['Y'].unique(), reverse=True) if 'Y' in df_raw.columns else [2025]
    selected_year = st.selectbox("📅 기준 연도", years)
    
    f_raw = df_raw[df_raw['Y'] == selected_year] if 'Y' in df_raw.columns else df_raw
    f_master = df_master[df_master['연도'] == selected_year] if '연도' in df_master.columns else df_master

# --- 5. 메인 대시보드 UI ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 26px;">📊 {selected_year} hince Integrated Sales Performance</h1>', unsafe_allow_html=True)

# ---------------------------------------------------------
# 상단 섹션: ■ Sell-In 현황 (출고_RAW 기반)
# ---------------------------------------------------------
st.markdown("## 🟦 Sell-In 현황 (본사 → 거래처)")

# 상단 KPI (Sell-In)
k1, k2, k3, k4 = st.columns(4)
with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">총 Sell-In 매출액</div><div class="metric-value">₩{f_raw["매출취합용_공급가액(원화기준)"].sum():,.0f}</div></div>', unsafe_allow_html=True)
with k2: st.markdown(f'<div class="metric-card"><div class="metric-label">총 Sell-In 수량</div><div class="metric-value">{f_raw["제품판매수량"].sum():,.0f} EA</div></div>', unsafe_allow_html=True)
with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">활성 채널 수</div><div class="metric-value">{f_raw["채널명"].nunique()} 개</div></div>', unsafe_allow_html=True)
with k4: st.markdown(f'<div class="metric-card"><div class="metric-label">FOC 발생</div><div class="metric-value">{len(f_raw[f_raw["FOC"] == "Y"])} 건</div></div>', unsafe_allow_html=True)

# Sell-In 그래프 3개 한 줄 배치
si1, si2, si3 = st.columns(3)
hince_colors = px.colors.qualitative.Pastel + px.colors.qualitative.Safe

with si1:
    st.markdown("### ■ 25년 월별 Sell-In 현황")
    fig_si_monthly = px.bar(f_raw, x='월', y='매출취합용_공급가액(원화기준)', color_discrete_sequence=['#A37F7D'])
    fig_si_monthly.update_layout(plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=330, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig_si_monthly, use_container_width=True)

with si2:
    st.markdown("### ■ 품목별 주요 지표 (대카테고리)")
    if '대' in f_raw.columns:
        fig_si_dae = px.bar(f_raw.groupby('대')['제품판매수량'].sum().reset_index(), x='대', y='제품판매수량', color_discrete_sequence=['#D4A5A5'])
        fig_si_dae.update_layout(plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=330, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig_si_dae, use_container_width=True)

with si3:
    st.markdown("### ■ 제품 카테고리별 비중 (중)")
    if '중' in f_raw.columns:
        fig_si_pie = px.pie(f_raw, values='매출취합용_공급가액(원화기준)', names='중', hole=0.5, color_discrete_sequence=hince_colors)
        fig_si_pie.update_traces(textinfo='percent')
        fig_si_pie.update_layout(showlegend=True, height=330, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5, font=dict(size=10)))
        st.plotly_chart(fig_si_pie, use_container_width=True)

# ---------------------------------------------------------
# 하단 섹션: ■ Sell-Out 현황 (SS_Master 기반)
# ---------------------------------------------------------
st.markdown("## 🟧 Sell-Out 현황 (거래처 → 소비자)")

so1, so2, so3 = st.columns(3)

with so1:
    st.markdown("### ■ 거래처별 월별 현황")
    fig_so_monthly = px.bar(f_master, x='월', y='출고_수량', color='CUSTOMER', color_discrete_sequence=hince_colors)
    fig_so_monthly.update_layout(plot_bgcolor='rgba(0,0,0,0)', barmode='stack', xaxis_title=None, height=330, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, font=dict(size=10)))
    st.plotly_chart(fig_so_monthly, use_container_width=True)

with so2:
    st.markdown("### ■ 품목별(Type) 트렌드")
    if 'Type' in f_master.columns:
        trend_data = f_master.groupby(['월', 'month_idx', 'Type'])['출고_수량'].sum().reset_index().sort_values('month_idx')
        fig_so_trend = px.line(trend_data, x='월', y='출고_수량', color='Type', markers=True, color_discrete_sequence=hince_colors)
        fig_so_trend.update_layout(plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=330, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5, font=dict(size=10)))
        st.plotly_chart(fig_so_trend, use_container_width=True)

with so3:
    st.markdown("### ■ 거래처별 판매 비중")
    fig_so_pie = px.pie(f_master, values='출고_수량', names='CUSTOMER', hole=0.5, color_discrete_sequence=hince_colors)
    fig_so_pie.update_traces(textinfo='percent')
    fig_so_pie.update_layout(showlegend=True, height=330, margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5, font=dict(size=10)))
    st.plotly_chart(fig_so_pie, use_container_width=True)

st.markdown("---")

# 하단 상세 데이터 내역 (Sell-In 기준)
st.markdown("### 📋 출고_RAW 상세 데이터")
raw_view_cols = ['월', '채널명', '제품명', '대', '중', '제품판매수량', '매출취합용_공급가액(원화기준)']
available_raw_cols = [c for c in raw_view_cols if c in f_raw.columns]

# 정렬 에러 해결 로직 ⭐
if 'month_idx' in f_raw.columns:
    view_df = f_raw.sort_values('month_idx')[available_raw_cols]
else:
    view_df = f_raw[available_raw_cols]

st.dataframe(view_df, use_container_width=True, hide_index=True, height=300)

# --- 6. 다운로드 버튼 ---
csv = f_raw.to_csv(index=False).encode('utf-8-sig')
st.download_button(label="📥 Sell-In 데이터 다운로드 (CSV)", data=csv, file_name=f'hince_sell_in_{selected_year}.csv', mime='text/csv')