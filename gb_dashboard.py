import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. 페이지 설정 및 hince 스타일 ---
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

# --- 3. 데이터 전처리 (날짜 형식 완벽 대응) ---
def preprocess_data(df, qty_col, rev_col, month_col, date_col):
    if df.empty: return df
    
    # "2025. 4. 1" 등 점(.)으로 구분된 날짜 처리
    if date_col in df.columns:
        # 점을 기준으로 나누어 첫 번째 항목(연도) 추출
        df['year_extracted'] = df[date_col].astype(str).str.split('.').str[0].str.strip()
        df['year_extracted'] = pd.to_numeric(df['year_extracted'], errors='coerce').fillna(0).astype(int)
    else:
        for y_col in ['Y', '연도']:
            if y_col in df.columns:
                df['year_extracted'] = pd.to_numeric(df[y_col], errors='coerce').fillna(0).astype(int)
                break
    
    # 숫자 변환 및 월 인덱스
    for col in [qty_col, rev_col]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    if month_col in df.columns:
        df['month_idx'] = df[month_col].astype(str).str.extract('(\d+)').fillna(0).astype(int)
    
    return df

df_raw_all = preprocess_data(df_raw_all, "제품판매수량", "매출취합용_공급가액(원화기준)", "월", "매출인식_기준일(출고일)")
df_master_all = preprocess_data(df_master_all, "출고_수량", "매출액", "월", "매출인식_기준일(출고일)")

# --- 4. 사이드바 필터 ---
with st.sidebar:
    # 요청하신 hince.png 로고 적용
    st.image("hince.png", use_container_width=True)
    st.markdown("---")
    
    all_years = sorted([y for y in list(set(df_raw_all['year_extracted'].unique()) | set(df_master_all['year_extracted'].unique())) if y > 0], reverse=True)
    
    if not all_years:
        selected_year = 2026
    else:
        # 2026 우선 선택, 없으면 최신 연도
        default_idx = all_years.index(2026) if 2026 in all_years else 0
        selected_year = st.selectbox("📅 기준 연도 선택", all_years, index=default_idx)
    
    raw_ch = set(df_raw_all[df_raw_all['year_extracted'] == selected_year]['채널명'].unique())
    mst_cu = set(df_master_all[df_master_all['year_extracted'] == selected_year]['CUSTOMER'].unique())
    all_entities = sorted(list(raw_ch | mst_cu))
    selected_entities = st.multiselect("🤝 거래처/채널 선택", all_entities, default=all_entities)

# 필터링 결과
f_raw = df_raw_all[(df_raw_all['year_extracted'] == selected_year) & (df_raw_all['채널명'].isin(selected_entities))].sort_values('month_idx')
f_master = df_master_all[(df_master_all['year_extracted'] == selected_year) & (df_master_all['CUSTOMER'].isin(selected_entities))].sort_values('month_idx')

# --- 5. 메인 대시보드 ---
st.markdown(f'<h1 style="color: #A37F7D; font-size: 28px;">📊 {selected_year} hince Sales Dashboard</h1>', unsafe_allow_html=True)

if f_raw.empty and f_master.empty:
    st.info(f"선택하신 {selected_year}년 데이터가 존재하지 않습니다.")
    if selected_year == 2026:
        st.write("💡 Tip: DB에 '2026. 1. 1'과 같은 형식의 데이터가 입력되어 있는지 확인해주세요.")
else:
    # KPI
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">총 매출액</div><div class="metric-value">₩{f_raw["매출취합용_공급가액(원화기준)"].sum():,.0f}</div></div>', unsafe_allow_html=True)
    with k2: st.markdown(f'<div class="metric-card"><div class="metric-label">총 출고량</div><div class="metric-value">{f_raw["제품판매수량"].sum():,.0f} EA</div></div>', unsafe_allow_html=True)
    with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">활성 채널</div><div class="metric-value">{f_raw["채널명"].nunique()} 개</div></div>', unsafe_allow_html=True)
    with k4: 
        m_list = sorted(f_raw[f_raw["제품판매수량"] > 0]["month_idx"].unique())
        st.markdown(f'<div class="metric-card"><div class="metric-label">집계 월</div><div class="metric-value">{", ".join([f"{m}월" for m in m_list]) if m_list else "없음"}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    
    # 차트
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🟦 Sell-In 현황")
        si_df = f_raw.groupby(['월', 'month_idx', '채널명'])['제품판매수량'].sum().reset_index().sort_values('month_idx')
        st.plotly_chart(px.bar(si_df, x='월', y='제품판매수량', color='채널명', text_auto=',.0f', color_discrete_sequence=px.colors.qualitative.Pastel).update_layout(plot_bgcolor='rgba(0,0,0,0)', height=400, xaxis_title=None), use_container_width=True)
    with c2:
        st.markdown("### 🟧 Sell-Out 현황")
        st.plotly_chart(px.bar(f_master, x='월', y='출고_수량', color='CUSTOMER', text_auto=',.0f', color_discrete_sequence=px.colors.qualitative.Safe).update_layout(plot_bgcolor='rgba(0,0,0,0)', height=400, xaxis_title=None), use_container_width=True)

    # 테이블
    st.markdown("### 📋 상세 내역")
    view_cols = ['월', '채널명', '제품명', '제품판매수량', '매출취합용_공급가액(원화기준)', '매출인식_기준일(출고일)']
    avail = [c for c in view_cols if c in f_raw.columns]
    st.dataframe(f_raw.sort_values(['month_idx', '제품판매수량'], ascending=[True, False])[avail], use_container_width=True, hide_index=True)