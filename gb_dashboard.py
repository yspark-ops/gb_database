import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 (CSS) ---
st.set_page_config(page_title="2026 hince Sales Dashboard", layout="wide")

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

# --- 3. 데이터 전처리 (2026년 기준) ---

# 숫자형 변환 및 month_idx 생성 함수
def preprocess_df(df, qty_col, rev_col, month_col):
    if qty_col in df.columns:
        df[qty_col] = pd.to_numeric(df[qty_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    if rev_col in df.columns:
        df[rev_col] = pd.to_numeric(df[rev_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    if month_col in df.columns:
        df['month_idx'] = df[month_col].astype(str).str.extract('(\d+)').fillna(0).astype(int)
    return df

df_raw = preprocess_df(df_raw, "제품판매수량", "매출취합용_공급가액(원화기준)", "월")
df_master = preprocess_df(df_master, "출고_수량", "매출액", "월")

# --- 4. 사이드바 필터 (2026년 고정) ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    # 연도 필터 (2026년 기본값)
    years = sorted(df_raw['Y'].unique(), reverse=True) if 'Y' in df_raw.columns else [2026]
    default_year_idx = years.index(2026) if 2026 in years else 0
    selected_year = st.selectbox("📅 기준 연도", years, index=default_year_idx)
    
    # 통합 거래처 필터
    raw_ch = set(df_raw['채널명'].unique()) if '채널명' in df_raw.columns else set()
    mst_cu = set(df_master['CUSTOMER'].unique()) if 'CUSTOMER' in df_master.columns else set()
    all_entities = sorted(list(raw_ch | mst_cu))
    selected_entities = st.multiselect("🤝 거래처/채널 선택", all_entities, default=all_entities)

# 데이터 필터링 (2026년 기준)
f_raw = df_raw[(df_raw['Y'] == selected_year) & (df_raw['채널명'].isin(selected_entities))]
f_master = df_master[(df_master['연도'] == selected_year) & (df_master['CUSTOMER'].isin(selected_entities))]

# --- 5. 메인 대시보드 UI ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 26px;">📊 {selected_year} hince Sales Dashboard</h1>', unsafe_allow_html=True)
st.caption(f"데이터 기준: {selected_year}년 1월 ~ 현재")

# 상단 KPI 섹션
k1, k2, k3, k4 = st.columns(4)
with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">총 매출액</div><div class="metric-value">₩{f_raw["매출취합용_공급가액(원화기준)"].sum():,.0f}</div></div>', unsafe_allow_html=True)
with k2: st.markdown(f'<div class="metric-card"><div class="metric-label">총 출고 수량</div><div class="metric-value">{f_raw["제품판매수량"].sum():,.0f} EA</div></div>', unsafe_allow_html=True)
with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">활성 거래처</div><div class="metric-value">{f_raw["채널명"].nunique()} 개</div></div>', unsafe_allow_html=True)
with k4: st.markdown(f'<div class="metric-card"><div class="metric-label">데이터 기준월</div><div class="metric-value">{f_raw["월"].max() if not f_raw.empty else "집계중"}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------
# 상단 섹션: Sell-In (3개 한 줄 배치)
# ---------------------------------------------------------
st.markdown(f"## 🟦 {selected_year} Sell-In Analysis (본사 → 거래처)")
si_c1, si_c2, si_c3 = st.columns(3)
palette = px.colors.qualitative.Pastel + px.colors.qualitative.Prism

with si_c1:
    st.markdown(f"### ■ {selected_year} 월별 Sell-In 현황")
    si_df = f_raw.groupby(['월', 'month_idx', '채널명'])['제품판매수량'].sum().reset_index().sort_values('month_idx')
    fig_si = px.bar(si_df, x='월', y='제품판매수량', color='채널명', text='제품판매수량', color_discrete_sequence=palette)
    fig_si.update_traces(texttemplate='%{text:,.0f}', textposition='inside', textfont=dict(size=9, color="white"))
    
    # 상단 총합 레이블
    totals = si_df.groupby('월')['제품판매수량'].sum().reset_index()
    for _, row in totals.iterrows():
        fig_si.add_annotation(x=row['월'], y=row['제품판매수량'], text=f"<b>{row['제품판매수량']:,.0f}</b>", showarrow=False, yshift=10)

    fig_si.update_layout(plot_bgcolor='rgba(0,0,0,0)', barmode='stack', xaxis_title=None, height=350, showlegend=True, legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", font=dict(size=9)))
    st.plotly_chart(fig_si, use_container_width=True)

with si_c2:
    st.markdown("### ■ 품목별 주요 지표 (대)")
    if '대' in f_raw.columns:
        fig_dae = px.bar(f_raw.groupby('대')['제품판매수량'].sum().reset_index().sort_values('제품판매수량', ascending=False), x='대', y='제품판매수량', color_discrete_sequence=['#D4A5A5'])
        fig_dae.update_layout(plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=350)
        st.plotly_chart(fig_dae, use_container_width=True)

with si_c3:
    st.markdown("### ■ 카테고리별 비중 (중)")
    if '중' in f_raw.columns:
        fig_jung = px.pie(f_raw, values='매출취합용_공급가액(원화기준)', names='중', hole=0.5, color_discrete_sequence=palette)
        fig_jung.update_layout(height=350, showlegend=True, legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center", font=dict(size=10)))
        st.plotly_chart(fig_jung, use_container_width=True)

# ---------------------------------------------------------
# 하단 섹션: Sell-Out (3개 한 줄 배치)
# ---------------------------------------------------------
st.markdown(f"## 🟧 {selected_year} Sell-Out Analysis (거래처 → 소비자)")
so_c1, so_c2, so_c3 = st.columns(3)

with so_c1:
    st.markdown("### ■ 거래처별 월별 현황")
    fig_so = px.bar(f_master, x='월', y='출고_수량', color='CUSTOMER', color_discrete_sequence=palette)
    fig_so.update_layout(plot_bgcolor='rgba(0,0,0,0)', barmode='stack', xaxis_title=None, height=350, legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", font=dict(size=9)))
    st.plotly_chart(fig_so, use_container_width=True)

with so_c2:
    st.markdown("### ■ 품목별(Type) 트렌드")
    if 'Type' in f_master.columns:
        trend_so = f_master.groupby(['월', 'month_idx', 'Type'])['출고_수량'].sum().reset_index().sort_values('month_idx')
        fig_tr = px.line(trend_so, x='월', y='출고_수량', color='Type', markers=True, color_discrete_sequence=palette)
        fig_tr.update_layout(plot_bgcolor='rgba(0,0,0,0)', xaxis_title=None, height=350, legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center", font=dict(size=9)))
        st.plotly_chart(fig_tr, use_container_width=True)

with so_c3:
    st.markdown("### ■ 거래처별 판매 비중")
    fig_so_p = px.pie(f_master, values='출고_수량', names='CUSTOMER', hole=0.5, color_discrete_sequence=palette)
    fig_so_p.update_layout(height=350, showlegend=True, legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center", font=dict(size=10)))
    st.plotly_chart(fig_so_p, use_container_width=True)

st.markdown("---")

# 하단 상세 데이터 (에러 수정 지점 ⭐)
st.markdown(f"### 📋 {selected_year} 출고_RAW 상세 내역")
view_cols = ['월', '채널명', '제품명', '제품판매수량', '매출취합용_공급가액(원화기준)']
avail = [c for c in view_cols if c in f_raw.columns]

# ⭐ 해결: 정렬을 먼저 수행한 뒤, 원하는 컬럼만 추출하여 출력합니다.
if 'month_idx' in f_raw.columns:
    sorted_df = f_raw.sort_values('month_idx')[avail]
else:
    sorted_df = f_raw[avail]

st.dataframe(sorted_df, use_container_width=True, hide_index=True)