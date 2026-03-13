import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 ---
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
        .metric-value { color: #A37F7D; font-size: 24px; font-weight: 700; }
        h2 { color: #A37F7D !important; font-size: 20px !important; border-left: 5px solid #A37F7D; padding-left: 10px; margin-top: 30px; margin-bottom: 20px; font-weight: 700; }
        h3 { color: #A37F7D !important; font-size: 16px !important; font-weight: 700 !important; margin-top: 5px !important; margin-bottom: 15px !important; }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. Supabase 데이터 로드 ---
@st.cache_data(ttl=30) # 실시간 확인을 위해 캐시 시간을 줄임
def get_supabase_data(table_name):
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"] 
        supabase: Client = create_client(url, key)
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"{table_name} 로드 실패: {e}")
        return pd.DataFrame()

df_raw_all = get_supabase_data("출고_RAW")
df_master_all = get_supabase_data("SS_Master")

# --- 3. 데이터 전처리 (2026년 인식 강화 로직) ⭐ ---
def preprocess_all(df, qty_col, rev_col, month_col, year_col_name):
    if df.empty: return df
    
    # 1) 연도 추출 로직 강화
    # '연도'나 'Y' 컬럼이 있으면 우선 사용, 없으면 날짜에서 추출
    if 'Y' in df.columns:
        df['year_val'] = pd.to_numeric(df['Y'], errors='coerce').fillna(0).astype(int)
    elif '연도' in df.columns:
        df['year_val'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    elif '매출인식_기준일(출고일)' in df.columns:
        # "2026. 4. 1" 형식에서 앞의 4자리만 가져옴
        df['year_val'] = df['매출인식_기준일(출고일)'].astype(str).str.extract(r'(\d{4})').fillna(0).astype(int)
    else:
        df['year_val'] = 0

    # 2) 숫자 변환 로직 강화 (콤마 제거 및 강제 변환)
    for col in [qty_col, rev_col, 'FOC']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # 3) 월 인덱스 (정렬용)
    if month_col in df.columns:
        df['month_idx'] = df[month_col].astype(str).str.extract(r'(\d+)').fillna(0).astype(int)
    
    return df

df_raw_all = preprocess_all(df_raw_all, "제품판매수량", "매출취합용_공급가액(원화기준)", "월", "Y")
df_master_all = preprocess_all(df_master_all, "출고_수량", "매출액", "월", "연도")

# --- 4. 사이드바 필터 ---
with st.sidebar:
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    # 데이터에 존재하는 연도 리스트 생성
    raw_years = set(df_raw_all['year_val'].unique())
    mst_years = set(df_master_all['year_val'].unique())
    combined_years = sorted([y for y in list(raw_years | mst_years) if y > 0], reverse=True)

    # ⭐ 무조건 2026년을 기본값으로 고정!
    if 2026 in combined_years:
        default_idx = combined_years.index(2026)
    else:
        # 만약 데이터에 아직 2026이 없으면 리스트 맨 앞에 추가해서라도 보여줌
        combined_years.insert(0, 2026)
        default_idx = 0
    
    selected_year = st.selectbox("📅 기준 연도 선택", combined_years, index=default_idx)
    
    # 거래처 필터
    ch_list = set(df_raw_all[df_raw_all['year_val'] == selected_year]['채널명'].unique())
    cu_list = set(df_master_all[df_master_all['year_val'] == selected_year]['CUSTOMER'].unique())
    all_ents = sorted(list(ch_list | cu_list))
    selected_ents = st.multiselect("🤝 거래처/채널 선택", all_ents, default=all_ents)

# --- 5. 필터링 및 대시보드 출력 ---
f_raw = df_raw_all[(df_raw_all['year_val'] == selected_year) & (df_raw_all['채널명'].isin(selected_ents))]
f_master = df_master_all[(df_master_all['year_val'] == selected_year) & (df_master_all['CUSTOMER'].isin(selected_ents))]

st.markdown(f'<h1 style="color: #A37F7D; font-size: 28px;">📊 {selected_year} hince Sales Analysis</h1>', unsafe_allow_html=True)

# 2026년 데이터가 정말 없는지 확인하기 위한 경고창
if f_raw.empty and selected_year == 2026:
    st.warning("⚠️ 현재 2026년으로 필터링된 데이터가 0건입니다. DB의 'Y' 컬럼 또는 '날짜' 컬럼값이 2026인지 확인해주세요.")

# KPI
k1, k2, k3, k4 = st.columns(4)
with k1:
    val = f_raw["매출취합용_공급가액(원화기준)"].sum() if not f_raw.empty else 0
    st.markdown(f'<div class="metric-card"><div class="metric-label">총 매출액</div><div class="metric-value">₩{val:,.0f}</div></div>', unsafe_allow_html=True)
with k2:
    qty = f_raw["제품판매수량"].sum() if not f_raw.empty else 0
    st.markdown(f'<div class="metric-card"><div class="metric-label">총 출고량</div><div class="metric-value">{qty:,.0f} EA</div></div>', unsafe_allow_html=True)
with k3:
    cnt = f_raw["채널명"].nunique() if not f_raw.empty else 0
    st.markdown(f'<div class="metric-card"><div class="metric-label">활성 채널</div><div class="metric-value">{cnt} 개</div></div>', unsafe_allow_html=True)
with k4:
    months = sorted(f_raw['month_idx'].unique()) if not f_raw.empty else []
    m_str = ", ".join([f"{int(m)}월" for m in months if m > 0])
    st.markdown(f'<div class="metric-card"><div class="metric-label">집계 월</div><div class="metric-value">{m_str if m_str else "데이터 없음"}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# 그래프 섹션 (3개 한 줄 배치)
c1, c2, c3 = st.columns(3)
palette = px.colors.qualitative.Pastel + px.colors.qualitative.Prism

with c1:
    st.markdown(f"### ■ {selected_year} 월별 Sell-In")
    if not f_raw.empty:
        si_df = f_raw.groupby(['월', 'month_idx', '채널명'])['제품판매수량'].sum().reset_index().sort_values('month_idx')
        fig = px.bar(si_df, x='월', y='제품판매수량', color='채널명', text_auto=',.0f', color_discrete_sequence=palette)
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', height=350, showlegend=False, xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    else: st.info("데이터가 없습니다.")

with c2:
    st.markdown(f"### ■ {selected_year} 카테고리 비중")
    if not f_raw.empty and '대' in f_raw.columns:
        fig_p = px.pie(f_raw, values='제품판매수량', names='대', hole=0.5, color_discrete_sequence=palette)
        fig_p.update_layout(height=350, showlegend=True, legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_p, use_container_width=True)
    else: st.info("카테고리 정보 없음")

with c3:
    st.markdown(f"### ■ {selected_year} Sell-Out 현황")
    if not f_master.empty:
        fig_so = px.bar(f_master, x='월', y='출고_수량', color='CUSTOMER', text_auto=',.0f', color_discrete_sequence=palette)
        fig_so.update_layout(plot_bgcolor='rgba(0,0,0,0)', height=350, showlegend=False, xaxis_title=None)
        st.plotly_chart(fig_so, use_container_width=True)
    else: st.info("데이터 없음")

# 상세 테이블 (KeyError 방지 로직 포함)
st.markdown("### 📋 상세 내역")
view_cols = ['월', '채널명', '제품명', '제품판매수량', '매출취합용_공급가액(원화기준)']
avail = [c for c in view_cols if c in f_raw.columns]
if not f_raw.empty:
    st.dataframe(f_raw.sort_values('month_idx', ascending=True)[avail], use_container_width=True, hide_index=True)