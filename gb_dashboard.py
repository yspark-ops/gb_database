import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 (CSS) ---
st.set_page_config(page_title="hince Sales Dashboard", layout="wide")

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
@st.cache_data(ttl=60)
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

df_raw_all = get_supabase_data("출고_RAW")
df_master_all = get_supabase_data("SS_Master")

# --- 3. 데이터 공통 전처리 함수 ---
def preprocess_data(df, qty_col, rev_col, month_col, year_col):
    if df.empty: return df
    
    # 숫자형 변환 (콤마 제거)
    for col in [qty_col, rev_col]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # 연도 컬럼 숫자화
    if year_col in df.columns:
        df[year_col] = pd.to_numeric(df[year_col], errors='coerce').fillna(0).astype(int)
    
    # 월 정렬 인덱스 생성
    if month_col in df.columns:
        df['month_idx'] = df[month_col].astype(str).str.extract('(\d+)').fillna(0).astype(int)
    
    return df

df_raw_all = preprocess_data(df_raw_all, "제품판매수량", "매출취합용_공급가액(원화기준)", "월", "Y")
df_master_all = preprocess_data(df_master_all, "출고_수량", "매출액", "월", "연도")

# --- 4. 사이드바 필터 (연도 선택 활성화 ⭐) ---
with st.sidebar:
    st.image("hince.png", use_container_width=True) 
    st.markdown("---")
    
    # 연도 필터: 데이터에 있는 모든 연도를 가져오고 기본값을 2026으로 설정
    all_years = sorted(list(set(df_raw_all['Y'].unique()) | set(df_master_all['연도'].unique())), reverse=True)
    selected_year = st.selectbox("📅 기준 연도 선택", all_years, index=all_years.index(2026) if 2026 in all_years else 0)
    
    # 거래처 필터
    raw_ch = set(df_raw_all[df_raw_all['Y'] == selected_year]['채널명'].unique())
    mst_cu = set(df_master_all[df_master_all['연도'] == selected_year]['CUSTOMER'].unique())
    all_entities = sorted(list(raw_ch | mst_cu))
    selected_entities = st.multiselect("🤝 거래처/채널 선택", all_entities, default=all_entities)

# --- 5. 선택된 연도에 따른 데이터 필터링 ---
f_raw = df_raw_all[(df_raw_all['Y'] == selected_year) & (df_raw_all['채널명'].isin(selected_entities))].sort_values('month_idx')
f_master = df_master_all[(df_master_all['연도'] == selected_year) & (df_master_all['CUSTOMER'].isin(selected_entities))].sort_values('month_idx')

# --- 6. 메인 대시보드 UI ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 28px;">📊 {selected_year} hince Sales Performance</h1>', unsafe_allow_html=True)
st.caption(f"현재 {selected_year}년 데이터를 조회 중입니다.")

# KPI 카드
k1, k2, k3, k4 = st.columns(4)
with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">{selected_year} 총 매출액</div><div class="metric-value">₩{f_raw["매출취합용_공급가액(원화기준)"].sum():,.0f}</div></div>', unsafe_allow_html=True)
with k2: st.markdown(f'<div class="metric-card"><div class="metric-label">{selected_year} 총 출고량</div><div class="metric-value">{f_raw["제품판매수량"].sum():,.0f} EA</div></div>', unsafe_allow_html=True)
with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">운영 채널 수</div><div class="metric-value">{f_raw["채널명"].nunique()} 개</div></div>', unsafe_allow_html=True)
with k4: 
    months = f_raw[f_raw["제품판매수량"] > 0]["월"].unique()
    st.markdown(f'<div class="metric-card"><div class="metric-label">데이터 기준월</div><div class="metric-value">{", ".join(months) if len(months)>0 else "집계전"}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# 그래프 섹션 (Sell-In / Sell-Out)
c1, c2 = st.columns(2)
palette = px.colors.qualitative.Pastel

with c1:
    st.markdown(f"### 🟦 {selected_year} Sell-In 현황")
    si_df = f_raw.groupby(['월', 'month_idx', '채널명'])['제품판매수량'].sum().reset_index().sort_values('month_idx')
    fig_si = px.bar(si_df, x='월', y='제품판매수량', color='채널명', text_auto=',.0f', color_discrete_sequence=palette)
    fig_si.update_layout(plot_bgcolor='rgba(0,0,0,0)', barmode='stack', height=400, xaxis_title=None)
    st.plotly_chart(fig_si, use_container_width=True)

with c2:
    st.markdown(f"### 🟧 {selected_year} Sell-Out 현황")
    fig_so = px.bar(f_master, x='월', y='출고_수량', color='CUSTOMER', text_auto=',.0f', color_discrete_sequence=px.colors.qualitative.Safe)
    fig_so.update_layout(plot_bgcolor='rgba(0,0,0,0)', barmode='stack', height=400, xaxis_title=None)
    st.plotly_chart(fig_so, use_container_width=True)

# 상세 데이터 내역 (에러 수정 지점 ⭐)
st.markdown(f"### 📋 {selected_year} 상세 내역")
view_cols = ['월', '채널명', '제품명', '제품판매수량', '매출취합용_공급가액(원화기준)']
# 화면에 보여줄 컬럼만 안전하게 필터링
avail = [c for c in view_cols if c in f_raw.columns]

if not f_raw.empty:
    # 1. 정렬은 month_idx를 포함한 원본(f_raw)에서 수행합니다.
    # 2. 정렬된 결과에서 사용자가 보고 싶은 컬럼(avail)만 딱 골라서 출력합니다.
    sorted_view = f_raw.sort_values(['month_idx', '제품판매수량'], ascending=[True, False])[avail]
    st.dataframe(sorted_view, use_container_width=True, hide_index=True)
else:
    st.info("선택한 조건에 맞는 데이터가 없습니다.")